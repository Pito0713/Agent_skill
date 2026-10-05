"""上櫃日線解析測試：量能單位換算、除權息反推、以及反推結果接回還原股價。

除權息反推是本模組唯一的推論步驟（TWSE 是直接讀標記），
推錯會讓整條均線位移，故以 5425 台半 2026-07-27 的真實數字當基準案例。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import db             # noqa: E402
import fetch_tpex     # noqa: E402
import fetch_twse     # noqa: E402


def tpex_row(roc_date, open_, high, low, close, change, lots):
    """TPEx 個股日成交資訊的原始列序：日期/仟股/仟元/開/高/低/收/漲跌/筆數。"""
    return [roc_date, lots, "0", open_, high, low, close, change, "100"]


class TpexParseTest(unittest.TestCase):
    def test_volume_is_converted_from_lots_to_shares(self):
        rows, _ = fetch_tpex.parse_days([
            tpex_row("115/09/01", "94.40", "97.60", "94.10", "95.20", "0.40", "13,402"),
        ])
        self.assertEqual(rows[0]["volume"], 13402000)
        self.assertEqual(rows[0]["date"], "2026-09-01")

    def test_normal_day_is_not_flagged_as_exdiv(self):
        rows, events = fetch_tpex.parse_days([
            tpex_row("115/09/01", "94.40", "97.60", "94.10", "95.20", "0.40", "100"),
            tpex_row("115/09/02", "93.50", "94.70", "92.50", "92.50", "-2.70", "100"),
        ])
        self.assertEqual([r["is_exdiv"] for r in rows], [0, 0])
        self.assertEqual(events, [])

    def test_exdiv_day_is_detected_and_amount_derived(self):
        # 5425 實際：前收 85.0、收 82.8、漲跌 -0.2 → 參考價 83.0 → 配息 2.0
        rows, events = fetch_tpex.parse_days([
            tpex_row("115/07/24", "86.90", "89.20", "85.00", "85.00", "-3.80", "100"),
            tpex_row("115/07/27", "82.50", "83.80", "80.10", "82.80", "-0.20", "100"),
        ])
        self.assertEqual([r["is_exdiv"] for r in rows], [0, 1])
        self.assertEqual(events, [("2026-07-27", 2.0)])

    def test_unparsable_change_is_flagged_without_guessing_amount(self):
        rows, events = fetch_tpex.parse_days([
            tpex_row("115/07/24", "86.90", "89.20", "85.00", "85.00", "-3.80", "100"),
            tpex_row("115/07/27", "82.50", "83.80", "80.10", "82.80", "除息", "100"),
        ])
        self.assertEqual(rows[1]["is_exdiv"], 1)
        self.assertEqual(events, [])   # 金額未知時不得補數字

    def test_suspended_day_without_price_is_skipped(self):
        rows, _ = fetch_tpex.parse_days([
            tpex_row("115/09/01", "94.40", "97.60", "94.10", "95.20", "0.40", "100"),
            tpex_row("115/09/02", "--", "--", "--", "--", "--", "0"),
            tpex_row("115/09/03", "95.00", "96.00", "94.00", "95.60", "0.40", "100"),
        ])
        self.assertEqual([r["date"] for r in rows], ["2026-09-01", "2026-09-03"])


class TpexAdjustmentTest(unittest.TestCase):
    """反推出的金額必須能直接餵進 rebuild_adj_close，不需另外換算。"""

    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp.close()
        self.conn = db.connect(self.temp.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.temp.name)

    def test_derived_amount_feeds_back_into_adj_close(self):
        rows, events = fetch_tpex.parse_days([
            tpex_row("115/07/24", "86.90", "89.20", "85.00", "85.00", "-3.80", "100"),
            tpex_row("115/07/27", "82.50", "83.80", "80.10", "82.80", "-0.20", "100"),
        ])
        fetch_twse.save_quotes(self.conn, "5425", rows)
        fetch_tpex.save_implied_dividends(self.conn, "5425", events)
        _, unknown = fetch_twse.rebuild_adj_close(self.conn, "5425")

        self.assertEqual(unknown, [])   # 反推成功者不應再被當成未還原
        adjusted = dict(self.conn.execute(
            "SELECT date, adj_close FROM daily_quotes WHERE ticker = '5425'").fetchall())
        # 除息前一日 85.0 × (83.0 / 85.0) = 83.0；除息當日不調整
        self.assertAlmostEqual(adjusted["2026-07-24"], 83.0, places=4)
        self.assertAlmostEqual(adjusted["2026-07-27"], 82.8, places=4)


if __name__ == "__main__":
    unittest.main()
