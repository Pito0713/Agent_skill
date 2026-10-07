"""背景欄位（market_state / sector_quadrant）的離線測試：不打網路、不碰正式 DB。"""

import argparse
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import db  # noqa: E402
import track  # noqa: E402

# 加欄位前的 predictions 結構（main 分支 303d4c4 版本）
LEGACY_PREDICTIONS = """
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, ticker TEXT NOT NULL,
    horizon_days INTEGER NOT NULL, close_at_pred REAL NOT NULL, adj_close_at_pred REAL NOT NULL,
    score INTEGER NOT NULL, s_trend INTEGER NOT NULL, s_bias INTEGER NOT NULL,
    s_support INTEGER NOT NULL, s_volume INTEGER NOT NULL, s_macd INTEGER NOT NULL,
    s_rsi INTEGER NOT NULL, signal TEXT NOT NULL, entry_low REAL, entry_high REAL,
    stop_loss REAL, hard_rules TEXT NOT NULL DEFAULT '[]', flags TEXT NOT NULL DEFAULT '[]',
    thesis TEXT, status TEXT NOT NULL, resolve_date TEXT, close_at_resolve REAL,
    adj_close_at_resolve REAL, return_pct REAL, hit INTEGER
);
INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred, adj_close_at_pred,
    score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi, signal, status)
VALUES ('2026-08-01', '2330', 30, 1000, 1000, 70, 20, 15, 10, 10, 10, 5, '偏多', 'open');
"""

CONTRACT_TABLES = """
CREATE TABLE stock_industry (ticker TEXT PRIMARY KEY, industry_code TEXT, updated_at TEXT);
CREATE TABLE market_context (date TEXT PRIMARY KEY, turnover_ratio REAL, breadth_5d REAL,
                             market_state TEXT);
CREATE TABLE sector_context (date TEXT, industry_code TEXT, rs_ratio REAL, rs_momentum REAL,
                             quadrant TEXT, share_delta REAL, PRIMARY KEY(date, industry_code));
INSERT INTO stock_industry VALUES ('2330', '24', '2026-09-29');
INSERT INTO market_context VALUES ('2026-09-29', 1.2, 0.55, '充足');
INSERT INTO sector_context VALUES ('2026-09-29', '24', 101.5, 100.8, 'Leading', 0.01);
"""

FAKE_RESULT = {
    "date": "2026-09-29", "close": 1000.0, "adj_close": 1000.0, "final_score": 68,
    "parts": {"trend": 20, "bias": 15, "support": 10, "volume": 11, "macd": 8, "rsi": 4},
    "signal": "偏多", "entry_low": 980.0, "entry_high": 1000.0, "stop_loss": 950.0,
    "hard_rules": [], "flags": [], "thresholds": {"calibration_id": None, "bull": 60, "bear": 45},
}


class ContextFieldsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tracker.db")

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, conn, ticker="2330"):
        args = argparse.Namespace(ticker=ticker, horizon=30, thesis="test")
        with mock.patch.object(track.fetch_twse, "sync_ticker"), \
                mock.patch.object(track.scoring, "evaluate", return_value=dict(FAKE_RESULT)), \
                mock.patch("builtins.print"):
            track.cmd_record(conn, args)
        return conn.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 1").fetchone()

    def test_legacy_db_upgrade_is_idempotent_and_keeps_data(self):
        legacy = sqlite3.connect(self.path)
        legacy.executescript(LEGACY_PREDICTIONS)
        legacy.close()
        for _ in range(2):                                 # 第二次 connect 不可報錯
            conn = db.connect(self.path)
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(predictions)")}
            rows = conn.execute("SELECT * FROM predictions").fetchall()
            conn.close()
        self.assertTrue({"market_state", "sector_quadrant"} <= columns)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "2330")
        self.assertIsNone(rows[0]["market_state"])

    def test_record_writes_context_when_available(self):
        conn = db.connect(self.path)
        conn.executescript(CONTRACT_TABLES)
        row = self.record(conn)
        conn.close()
        self.assertEqual(row["market_state"], "充足")
        self.assertEqual(row["sector_quadrant"], "Leading")

    def test_record_writes_null_without_contract_tables(self):
        conn = db.connect(self.path)
        row = self.record(conn)
        conn.close()
        self.assertIsNone(row["market_state"])
        self.assertIsNone(row["sector_quadrant"])
        self.assertEqual(row["status"], "open")

    def test_record_writes_null_for_unmapped_ticker_or_date(self):
        conn = db.connect(self.path)
        conn.executescript(CONTRACT_TABLES)
        self.assertEqual(track.lookup_context(conn, "9999", "2026-09-29"), ("充足", None))
        self.assertEqual(track.lookup_context(conn, "2330", "2026-09-30"), (None, None))
        conn.close()

    def test_group_stats_marks_small_samples(self):
        rows = ([{"market_state": "充足", "hit": 1, "return_pct": 2.0}] * 5
                + [{"market_state": None, "hit": 0, "return_pct": -1.0}] * 2
                + [{"market_state": "不足", "hit": None, "return_pct": 0.5}] * 9)
        stats = {label: rest for label, *rest in track.context_group_stats(rows, "market_state")}
        self.assertEqual(stats["充足"], [5, 100.0, 2.0])
        self.assertEqual(stats["無資料"], [2, None, None])
        self.assertNotIn("不足", stats)                   # 中性（hit NULL）不計入


if __name__ == "__main__":
    unittest.main()
