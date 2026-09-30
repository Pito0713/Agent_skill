"""輸入驗證與還原價基準的離線測試：不打網路、不碰正式 DB。

每條對應一個「靜默給出看似合理錯數字」的缺陷，修正前應為紅。
"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import db  # noqa: E402
import fetch_twse  # noqa: E402
import score  # noqa: E402
import track  # noqa: E402

EXDIV_INDEX = 70
BAR_COUNT = 80


def synthetic_rows(cash_dividend=5.0, volume=1000):
    """80 根平盤日線：除息前收 100、除息後收 95，高低各 ±1。"""
    rows = []
    for index in range(BAR_COUNT):
        close = 100.0 if index < EXDIV_INDEX else 100.0 - cash_dividend
        rows.append({
            "date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "open": close, "high": close + 1, "low": close - 1, "close": close,
            "volume": volume, "is_exdiv": 1 if index == EXDIV_INDEX else 0,
        })
    return rows


def insert_dividend(conn, ticker, ex_date, cash, stock_ratio=0.0):
    conn.execute("INSERT INTO dividends (ticker, ex_date, cash, stock_ratio, source)"
                 " VALUES (?, ?, ?, ?, 'test')", (ticker, ex_date, cash, stock_ratio))


def insert_prediction(conn, created_at, adj_close_at_pred, horizon=1):
    conn.execute(
        "INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
        " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi,"
        " signal, status) VALUES (?, '2330', ?, ?, ?, 70, 20, 15, 10, 10, 10, 5, '偏多', 'open')",
        (created_at, horizon, adj_close_at_pred, adj_close_at_pred))
    return conn.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 1").fetchone()


class InputValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_stock_dividend_ratio_is_already_per_share(self):
        # TWSE 實際回應（2026-09-30 興泰）：配股 0.5 元 = 每股配 0.05 股
        payload = [{"Date": "1150924", "Code": "1235", "StockDividendRatio": "0.04999999",
                    "CashDividend": "0.500000"}]
        with mock.patch.object(fetch_twse, "_get_json", return_value=payload):
            fetch_twse.sync_dividends(self.conn)
        row = self.conn.execute("SELECT stock_ratio FROM dividends").fetchone()
        self.assertAlmostEqual(row["stock_ratio"], 0.04999999)

    def test_reconcile_uses_same_adjustment_basis_for_both_ends(self):
        fetch_twse.save_quotes(self.conn, "2330", [
            {"date": "2026-09-01", "open": 100, "high": 101, "low": 99, "close": 100,
             "volume": 1000, "is_exdiv": 0},
            {"date": "2026-09-02", "open": 95, "high": 96, "low": 94, "close": 95,
             "volume": 1000, "is_exdiv": 1},
        ])
        insert_dividend(self.conn, "2330", "2026-09-02", 5.0)
        # 預測建立於除息前，當時的還原價 = 原始價 100
        prediction = insert_prediction(self.conn, "2026-09-01", 100.0)
        fetch_twse.rebuild_adj_close(self.conn, "2330")

        self.assertEqual(track._resolve_one(self.conn, prediction), "resolved")
        row = self.conn.execute("SELECT return_pct FROM predictions").fetchone()
        self.assertAlmostEqual(row["return_pct"], 0.0)   # 價格只掉了股利，總報酬為 0

    def test_reconcile_without_start_quote_needs_review(self):
        fetch_twse.save_quotes(self.conn, "2330", [
            {"date": "2026-09-02", "open": 95, "high": 96, "low": 94, "close": 95,
             "volume": 1000, "is_exdiv": 0}])
        fetch_twse.rebuild_adj_close(self.conn, "2330")
        prediction = insert_prediction(self.conn, "2026-09-01", 100.0)
        self.assertEqual(track._resolve_one(self.conn, prediction), "needs_review")

    def test_score_adjusts_high_low_with_close(self):
        rows = synthetic_rows()
        fetch_twse.save_quotes(self.conn, "2330", rows)
        insert_dividend(self.conn, "2330", rows[EXDIV_INDEX]["date"], 5.0)
        fetch_twse.rebuild_adj_close(self.conn, "2330")

        result = score.evaluate(self.conn, "2330")
        # 還原後每根真實波幅約 2；混用原始高低價會把除息前的波幅灌成 6
        self.assertLess(result["indicators"]["atr14"], 2.5)
        self.assertAlmostEqual(result["indicators"]["high60"], 96.0)

    def test_score_zero_average_volume_does_not_crash(self):
        fetch_twse.save_quotes(self.conn, "2330", synthetic_rows(cash_dividend=0.0, volume=0))
        fetch_twse.rebuild_adj_close(self.conn, "2330")
        result = score.evaluate(self.conn, "2330")
        self.assertIsNone(result["indicators"]["volume_ratio"])

    def test_non_positive_horizon_is_rejected(self):
        for horizon in ("0", "-5"):
            argv = ["track.py", "record", "2330", "--horizon", horizon]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(track.db, "connect", return_value=mock.MagicMock()), \
                    mock.patch.object(track, "cmd_record") as cmd_record, \
                    mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    track.main()
                cmd_record.assert_not_called()

    def test_malformed_ticker_is_rejected_before_request(self):
        with mock.patch.object(fetch_twse, "fetch_months", return_value=[]) as fetch_months:
            for ticker in ("2330&date=20200101", "", "23"):
                with self.assertRaisesRegex(RuntimeError, "代號格式"):
                    fetch_twse.sync_ticker(self.conn, ticker)
            fetch_months.assert_not_called()


if __name__ == "__main__":
    unittest.main()
