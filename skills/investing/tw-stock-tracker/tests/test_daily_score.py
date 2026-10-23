"""daily_score.py 的資料庫與評分快照操作測試。

涵蓋：
  - load_watchlist（predictions, detail_views, positions 聯集）
  - upsert_score（live 寫入、同日冪等、原子 DO UPDATE 保護、live 覆蓋 backfill）
  - trend 與 rank（5 日 Δ、20 日 Δ、格式化標籤、資料不足 N/A）
"""

import math
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import daily_score  # noqa: E402
import db           # noqa: E402

FIRST_DAY = date(2024, 1, 2)


def trading_days(count):
    days, cursor = [], FIRST_DAY
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def seed_watchlist(conn, tickers):
    conn.executemany(
        "INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
        " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd,"
        " s_rsi, signal, hard_rules, flags, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open')",
        [("2024-01-02", t, 30, 100.0, 100.0, 60, 10, 14, 10, 11, 11, 10,
          "偏多", "[]", "[]") for t in tickers]
    )
    conn.commit()


class TempDbMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()


class TestLoadWatchlist(TempDbMixin, unittest.TestCase):
    def test_union_of_three_tables(self):
        seed_watchlist(self.conn, ["2330"])
        self.conn.execute("INSERT INTO detail_views (ticker, refreshed_at) VALUES ('5425','2024-01-02')")
        self.conn.execute(
            "INSERT INTO positions (ticker, buy_date, buy_price, shares, basis_date,"
            " basis_close, score, signal) VALUES ('0050','2024-01-02',100,1000,'2024-01-02',100,55,'中性')"
        )
        self.conn.commit()
        result = daily_score.load_watchlist(self.conn)
        self.assertIn("2330", result)
        self.assertIn("5425", result)
        self.assertIn("0050", result)
        self.assertEqual(result, sorted(result))

    def test_empty_watchlist(self):
        self.assertEqual(daily_score.load_watchlist(self.conn), [])


class TestUpsertScore(TempDbMixin, unittest.TestCase):
    def _fake_result(self, ticker="2330", date_str="2024-06-01", score_val=65):
        return {
            "ticker": ticker, "date": date_str,
            "final_score": score_val,
            "parts": {"trend": 20, "bias": 15, "support": 10, "volume": 11, "macd": 6, "rsi": 3},
            "signal": "偏多",
            "hard_rules": [],
        }

    def test_live_upsert_writes_row(self):
        result = self._fake_result()
        inserted = daily_score.upsert_score(self.conn, result, daily_score.SOURCE_LIVE)
        self.conn.commit()
        self.assertTrue(inserted)
        row = self.conn.execute(
            "SELECT * FROM daily_scores WHERE ticker='2330' AND date='2024-06-01'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["score"], 65)
        self.assertEqual(row["source"], "live")

    def test_same_day_live_reruns_idempotent(self):
        r1 = self._fake_result(score_val=65)
        daily_score.upsert_score(self.conn, r1, daily_score.SOURCE_LIVE)
        self.conn.commit()
        r2 = self._fake_result(score_val=70)
        daily_score.upsert_score(self.conn, r2, daily_score.SOURCE_LIVE)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT score FROM daily_scores WHERE ticker='2330' AND date='2024-06-01'"
        ).fetchone()
        self.assertEqual(row["score"], 70)

    def test_backfill_does_not_overwrite_live_atomic_rowcount(self):
        """原子操作驗收：backfill 遇到既有 live 列不覆蓋，且 upsert 回傳 False（rowcount=0）。"""
        live_result = self._fake_result(score_val=65)
        inserted_live = daily_score.upsert_score(self.conn, live_result, daily_score.SOURCE_LIVE)
        self.conn.commit()
        self.assertTrue(inserted_live)

        backfill_result = self._fake_result(score_val=30)
        inserted_backfill = daily_score.upsert_score(
            self.conn, backfill_result, daily_score.SOURCE_BACKFILL)
        self.conn.commit()

        self.assertFalse(inserted_backfill)
        row = self.conn.execute(
            "SELECT score, source FROM daily_scores WHERE ticker='2330' AND date='2024-06-01'"
        ).fetchone()
        self.assertEqual(row["score"], 65)
        self.assertEqual(row["source"], "live")

    def test_live_overwrites_backfill(self):
        backfill_result = self._fake_result(score_val=30)
        daily_score.upsert_score(self.conn, backfill_result, daily_score.SOURCE_BACKFILL)
        self.conn.commit()

        live_result = self._fake_result(score_val=65)
        inserted_live = daily_score.upsert_score(self.conn, live_result, daily_score.SOURCE_LIVE)
        self.conn.commit()

        self.assertTrue(inserted_live)
        row = self.conn.execute(
            "SELECT score, source FROM daily_scores WHERE ticker='2330' AND date='2024-06-01'"
        ).fetchone()
        self.assertEqual(row["score"], 65)
        self.assertEqual(row["source"], "live")


class TestTrendAndRank(TempDbMixin, unittest.TestCase):
    def _insert_scores(self, ticker, score_list):
        for date_str, score_val in score_list:
            self.conn.execute(
                "INSERT INTO daily_scores (ticker, date, score, s_trend, s_bias,"
                " s_support, s_volume, s_macd, s_rsi, signal, hard_rules, source, computed_at)"
                " VALUES (?,?,?,0,0,0,0,0,0,'中性','[]','backfill','2024-01-01 00:00:00')",
                (ticker, date_str, score_val)
            )
        self.conn.commit()

    def test_delta_5_and_20_calculated_correctly(self):
        days = trading_days(25)
        scores = list(range(50, 75))
        data = [(d.isoformat(), s) for d, s in zip(days, scores)]
        self._insert_scores("2330", data)
        seed_watchlist(self.conn, ["2330"])

        latest_row = daily_score._latest_score_row(self.conn, "2330")
        delta_5 = latest_row["score"] - daily_score._score_n_rows_ago(
            self.conn, "2330", latest_row["date"], 5)
        delta_20 = latest_row["score"] - daily_score._score_n_rows_ago(
            self.conn, "2330", latest_row["date"], 20)

        self.assertEqual(latest_row["score"], 74)
        self.assertEqual(delta_5, 74 - 69)
        self.assertEqual(delta_20, 74 - 54)

    def test_rank_shows_na_when_insufficient_history(self):
        days = trading_days(3)
        data = [(d.isoformat(), 60) for d in days]
        self._insert_scores("2330", data)
        seed_watchlist(self.conn, ["2330"])

        latest_row = daily_score._latest_score_row(self.conn, "2330")
        result = daily_score._score_n_rows_ago(self.conn, "2330", latest_row["date"], 5)
        self.assertIsNone(result)

    def test_delta_label_formatting(self):
        self.assertEqual(daily_score._delta_label(5), "+5")
        self.assertEqual(daily_score._delta_label(-3), "-3")
        self.assertEqual(daily_score._delta_label(0), "+0")
        self.assertEqual(daily_score._delta_label(None), "  N/A")


if __name__ == "__main__":
    unittest.main()
