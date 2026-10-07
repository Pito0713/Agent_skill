"""TWT49U 歷史除權息的離線測試：解析、落庫、與 rebuild_adj_close 的銜接。"""

import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import db  # noqa: E402
import fetch_exright  # noqa: E402
import fetch_twse  # noqa: E402

FIELDS = ["資料日期", "股票代號", "股票名稱", "除權息前收盤價", "除權息參考價", "權值+息值", "權/息"]
# 2330 與 2412 為 2023 年實際回應的列（截取前 7 欄）
PAYLOAD = {"stat": "OK", "fields": FIELDS, "data": [
    ["112年06月15日", "2330", "台積電", "590.00", "587.25", "2.749820", "息"],
    ["112年06月29日", "2412", "中華電", "121.50", "116.79", "4.702000", "息"],
    ["112年07月03日", "9999", "現增", "50.00", "52.00", "0", "權"],      # 認購價高於前收
    ["112年07月04日", "8888", "無差額", "30.00", "30.00", "0", "息"],
    ["112年07月05日", "7777", "缺值", "--", "10.00", "0", "息"],
]}


class ParseTest(unittest.TestCase):
    def test_parses_cash_equivalent_and_ratio_skipping_missing_values(self):
        events = {e[0]: e for e in fetch_exright.parse_events(PAYLOAD)}
        self.assertEqual(set(events), {"2330", "2412", "9999", "8888"})   # 7777 缺前收被略過
        self.assertEqual(events["2330"][1:3], ("2023-06-15", 2.75))
        self.assertAlmostEqual(events["2330"][3], 587.25 / 590.0)
        self.assertEqual(events["9999"][2], -2.0)                         # 現增：參考價高於前收
        self.assertEqual(events["8888"][2:], (0.0, 1.0))                  # 零差額仍保存

    def test_empty_response_returns_nothing(self):
        self.assertEqual(fetch_exright.parse_events({"stat": "很抱歉，沒有符合條件的資料!"}), [])

    def test_changed_fields_raise_instead_of_reading_wrong_column(self):
        broken = {"fields": ["日期", "代號"], "data": [["112年06月15日", "2330"]]}
        with self.assertRaises(RuntimeError):
            fetch_exright.parse_events(broken)

    def test_build_url_uses_compact_dates(self):
        url = fetch_exright.build_url("2023-01-01", "2023-12-31")
        self.assertTrue(url.endswith("startDate=20230101&endDate=20231231"))


class AdjustmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def seed_quotes(self, ticker="2330", closes=(("2023-06-14", 590, 0), ("2023-06-15", 588, 1))):
        rows = [{"date": day, "open": close, "high": close, "low": close, "close": close,
                 "volume": 1000, "is_exdiv": exdiv} for day, close, exdiv in closes]
        fetch_twse.save_quotes(self.conn, ticker, rows)

    def adj_close(self, ticker, day):
        return self.conn.execute("SELECT adj_close FROM daily_quotes WHERE ticker = ? AND date = ?",
                                 (ticker, day)).fetchone()["adj_close"]

    def test_existing_forecast_event_is_not_overwritten(self):
        self.conn.execute("INSERT INTO dividends (ticker, ex_date, cash, source)"
                          " VALUES ('2330', '2023-06-15', 2.75, 'TWT48U_ALL')")
        added = fetch_exright.save_events(self.conn, fetch_exright.parse_events(PAYLOAD))
        self.assertEqual(added, 3)
        source = self.conn.execute("SELECT source FROM dividends WHERE ticker = '2330'"
                                   ).fetchone()["source"]
        self.assertEqual(source, "TWT48U_ALL")

    def test_filled_event_makes_adj_close_match_reference_price(self):
        self.seed_quotes()
        _, unknown = fetch_twse.rebuild_adj_close(self.conn, "2330")
        self.assertEqual(unknown, ["2023-06-15"])
        fetch_exright.save_events(self.conn, fetch_exright.parse_events(PAYLOAD))
        _, unknown = fetch_twse.rebuild_adj_close(self.conn, "2330")
        self.assertEqual(unknown, [])
        self.assertAlmostEqual(self.adj_close("2330", "2023-06-14"), 587.25, places=2)

    def test_local_gap_uses_official_ratio_not_local_previous_close(self):
        # 本地缺了官方前收那天，上一根是 500；正確還原 = 500 × 587.25/590
        self.seed_quotes(closes=(("2023-06-12", 500, 0), ("2023-06-15", 588, 1)))
        fetch_exright.save_events(self.conn, fetch_exright.parse_events(PAYLOAD))
        fetch_twse.rebuild_adj_close(self.conn, "2330")
        self.assertAlmostEqual(self.adj_close("2330", "2023-06-12"), 500 * 587.25 / 590, places=3)

    def test_multiple_events_multiply_and_rights_issue_raises_factor(self):
        payload = {"fields": FIELDS, "data": [
            ["112年03月16日", "2330", "", "511.00", "508.25", "", "息"],
            ["112年06月15日", "2330", "", "590.00", "587.25", "", "息"],
            ["112年07月03日", "9999", "", "50.00", "52.00", "", "權"]]}
        fetch_exright.save_events(self.conn, fetch_exright.parse_events(payload))
        self.seed_quotes(closes=(("2023-03-15", 511, 0), ("2023-03-16", 509, 1),
                                 ("2023-06-14", 590, 0), ("2023-06-15", 588, 1)))
        self.seed_quotes("9999", (("2023-06-30", 50, 0), ("2023-07-03", 52, 1)))
        fetch_twse.rebuild_adj_close(self.conn, "2330")
        fetch_twse.rebuild_adj_close(self.conn, "9999")
        both = (508.25 / 511) * (587.25 / 590)
        self.assertAlmostEqual(self.adj_close("2330", "2023-03-15"), 511 * both, places=3)
        self.assertAlmostEqual(self.adj_close("2330", "2023-06-14"), 587.25, places=3)
        self.assertAlmostEqual(self.adj_close("9999", "2023-06-30"), 52.0, places=3)

    def test_forecast_sync_keeps_official_ratio(self):
        fetch_exright.save_events(self.conn, fetch_exright.parse_events(PAYLOAD))
        forecast = [{"Code": "2330", "Date": "1120615", "CashDividend": "2.749820"}]
        with mock.patch.object(fetch_twse, "_get_json", return_value=forecast):
            fetch_twse.sync_dividends(self.conn)
        row = self.conn.execute("SELECT source, ref_ratio FROM dividends WHERE ticker = '2330'"
                                ).fetchone()
        self.assertEqual(row["source"], "TWT48U_ALL")
        self.assertAlmostEqual(row["ref_ratio"], 587.25 / 590)

    def test_zero_difference_event_is_no_longer_unknown(self):
        self.seed_quotes("8888", (("2023-07-03", 30, 0), ("2023-07-04", 30, 1)))
        fetch_exright.save_events(self.conn, fetch_exright.parse_events(PAYLOAD))
        _, unknown = fetch_twse.rebuild_adj_close(self.conn, "8888")
        self.assertEqual(unknown, [])
        self.assertAlmostEqual(self.adj_close("8888", "2023-07-03"), 30.0)

    def test_sync_ticker_fills_unknown_listed_exdiv_once(self):
        rows = [{"date": "2023-06-14", "open": 590, "high": 591, "low": 585, "close": 590,
                 "volume": 1000, "is_exdiv": 0},
                {"date": "2023-06-15", "open": 588, "high": 590, "low": 586, "close": 588,
                 "volume": 1000, "is_exdiv": 1}]
        with mock.patch.object(fetch_twse, "fetch_months", return_value=rows), \
                mock.patch.object(fetch_twse, "_get_json", return_value=PAYLOAD) as get_json, \
                mock.patch.object(fetch_twse.time, "sleep"):
            summary = fetch_twse.sync_ticker(self.conn, "2330", months=1)
            fetch_twse.sync_ticker(self.conn, "2330", months=1)    # 第二次不應再查
        self.assertEqual(summary["unadjusted_exdiv"], [])
        self.assertEqual(get_json.call_count, 1)
        self.assertIn("startDate=20230615&endDate=20230615", get_json.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
