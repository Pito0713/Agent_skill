"""現金增資納入還原價的離線測試：不打網路、不碰正式 DB。

預期參考價由 TWSE 試算頁（announcement/ex-right/cal.html）的原始 JS 公式以 node 獨立算出，
不是用本專案的 Python 實作反推：
  (前收 − 現金股利 + 認購價 × 增資率) / (1 + 股票股利元/10 + 增資率)
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import db  # noqa: E402
import fetch_twse  # noqa: E402

# TWT48U_ALL 實際回應（2026-10-02）
ROW_2614 = {"Date": "1151006", "Code": "2614", "StockDividendRatio": "0.08000000",
            "SubscriptionRatio": "0.38195352", "SubscriptionPricePerShare": "12.8000",
            "CashDividend": "0.400000"}
ROW_2890 = {"Date": "1151007", "Code": "2890", "StockDividendRatio": "",
            "SubscriptionRatio": "0.04329540", "SubscriptionPricePerShare": "35.1500",
            "CashDividend": "0"}
ROW_1727 = {"Date": "1151013", "Code": "1727", "StockDividendRatio": "",
            "SubscriptionRatio": "0.10779602", "SubscriptionPricePerShare": "尚未公告",
            "CashDividend": "0"}

LEGACY_DIVIDENDS = """
CREATE TABLE dividends (
    ticker TEXT NOT NULL, ex_date TEXT NOT NULL, cash REAL NOT NULL DEFAULT 0,
    stock_ratio REAL NOT NULL DEFAULT 0, source TEXT, PRIMARY KEY (ticker, ex_date));
INSERT INTO dividends VALUES ('2330', '2026-06-12', 5.0, 0.0, 'TWT48U_ALL');
"""


def quote(day, close, is_exdiv=0):
    return {"date": day, "open": close, "high": close, "low": close, "close": close,
            "volume": 1000, "is_exdiv": is_exdiv}


class RightsOfferingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tracker.db")
        self.conn = db.connect(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def sync(self, *rows):
        with mock.patch.object(fetch_twse, "_get_json", return_value=list(rows)):
            fetch_twse.sync_dividends(self.conn)
        return {r["ticker"]: r for r in self.conn.execute("SELECT * FROM dividends")}

    def adj_before_exdiv(self, ticker, prev_close):
        fetch_twse.save_quotes(self.conn, ticker, [
            quote("2026-10-05", prev_close), quote("2026-10-06", prev_close * 0.9, is_exdiv=1)])
        self.conn.execute("UPDATE dividends SET ex_date = '2026-10-06' WHERE ticker = ?", (ticker,))
        fetch_twse.rebuild_adj_close(self.conn, ticker)
        return self.conn.execute("SELECT adj_close FROM daily_quotes WHERE ticker = ?"
                                 " AND date = '2026-10-05'", (ticker,)).fetchone()["adj_close"]

    def test_sync_stores_subscription_fields(self):
        row = self.sync(ROW_2614)["2614"]
        self.assertAlmostEqual(row["sub_ratio"], 0.38195352)
        self.assertAlmostEqual(row["sub_price"], 12.8)
        self.assertAlmostEqual(row["stock_ratio"], 0.08)

    def test_pure_rights_offering_is_recorded(self):
        # 無現金股利、無配股，舊版整筆跳過 → 除權日永遠被當成金額未知
        self.assertIn("2890", self.sync(ROW_2890))

    def test_unannounced_subscription_price_stays_unknown(self):
        # 認購價未公告不可當 0 算——那會把參考價壓低成錯數字；不寫入 = 維持「金額未知」標記
        self.assertNotIn("1727", self.sync(ROW_1727, ROW_2890))

    def test_adj_close_matches_twse_formula_with_dividend_stock_and_rights(self):
        self.sync(ROW_2614)
        self.assertAlmostEqual(self.adj_before_exdiv("2614", 20.0), 16.750878, places=4)

    def test_adj_close_matches_twse_formula_for_pure_rights(self):
        self.sync(ROW_2890)
        self.assertAlmostEqual(self.adj_before_exdiv("2890", 40.0), 39.798731, places=4)

    def test_legacy_dividends_table_gains_columns_and_keeps_rows(self):
        self.conn.close()
        legacy_path = os.path.join(self.tmp.name, "legacy.db")
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript(LEGACY_DIVIDENDS)
        legacy.close()
        for _ in range(2):                                 # 第二次 connect 不可報錯
            self.conn = db.connect(legacy_path)
            row = self.conn.execute("SELECT * FROM dividends").fetchone()
            if _ == 0:
                self.conn.close()
        self.assertEqual((row["cash"], row["sub_ratio"], row["sub_price"]), (5.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
