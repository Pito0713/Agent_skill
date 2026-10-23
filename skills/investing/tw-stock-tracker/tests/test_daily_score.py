"""daily_score.py 的離線測試：不打網路、不碰 ~/.stock-tracker。

涵蓋：
  - happy path（run 寫入、trend、rank）
  - 日線不足 60 根略過
  - 同日重跑 live 冪等更新
  - backfill 不覆蓋既有 live 列
  - rank 的 5 日 Δ、20 日 Δ 計算
"""

import json
import math
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import daily_score  # noqa: E402
import db           # noqa: E402
import score        # noqa: E402

FIRST_DAY = date(2024, 1, 2)  # 週二


def trading_days(count):
    days, cursor = [], FIRST_DAY
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def seed_quotes(conn, ticker="2330", count=120):
    """插入 count 根合成日線（adj_close = close，無除權息）。"""
    rows = []
    for index, day in enumerate(trading_days(count)):
        close = 100.0 + 5 * math.sin(index / 8) + index * 0.02
        rows.append((
            ticker, day.isoformat(),
            close * 0.99, close * 1.01, close * 0.98, close,
            1000 + 200 * math.cos(index / 4), 0, close,
        ))
    conn.executemany(
        "INSERT INTO daily_quotes (ticker, date, open, high, low, close,"
        " volume, is_exdiv, adj_close) VALUES (?,?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    return [day.isoformat() for day in trading_days(count)]


def seed_watchlist(conn, tickers):
    """把 tickers 寫進 predictions，讓 load_watchlist 能取到。"""
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
    """TestCase mixin：每個 test 拿到獨立的臨時 DB。"""
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
        self.assertEqual(row["score"], 70)  # live 覆蓋 live

    def test_backfill_does_not_overwrite_live(self):
        live_result = self._fake_result(score_val=65)
        daily_score.upsert_score(self.conn, live_result, daily_score.SOURCE_LIVE)
        self.conn.commit()

        backfill_result = self._fake_result(score_val=30)
        inserted = daily_score.upsert_score(self.conn, backfill_result, daily_score.SOURCE_BACKFILL)
        self.conn.commit()

        self.assertFalse(inserted)  # 回傳 False 表示保護生效
        row = self.conn.execute(
            "SELECT score FROM daily_scores WHERE ticker='2330' AND date='2024-06-01'"
        ).fetchone()
        self.assertEqual(row["score"], 65)  # 仍是 live 的值

    def test_live_overwrites_backfill(self):
        backfill_result = self._fake_result(score_val=30)
        daily_score.upsert_score(self.conn, backfill_result, daily_score.SOURCE_BACKFILL)
        self.conn.commit()

        live_result = self._fake_result(score_val=65)
        daily_score.upsert_score(self.conn, live_result, daily_score.SOURCE_LIVE)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT score, source FROM daily_scores WHERE ticker='2330' AND date='2024-06-01'"
        ).fetchone()
        self.assertEqual(row["score"], 65)
        self.assertEqual(row["source"], "live")


class TestCmdRun(TempDbMixin, unittest.TestCase):
    """cmd_run：抓日線 → 評分 → upsert；日線不足略過；單檔失敗不中斷。"""

    def setUp(self):
        super().setUp()
        seed_watchlist(self.conn, ["2330", "9999"])
        seed_quotes(self.conn, ticker="2330", count=120)
        # 9999 只插入 30 根（不足 60），評分必須拋錯並略過

        rows = []
        for index, day in enumerate(trading_days(30)):
            close = 50.0 + index * 0.1
            rows.append(("9999", day.isoformat(), close, close * 1.01,
                          close * 0.99, close, 500, 0, close))
        self.conn.executemany(
            "INSERT INTO daily_quotes (ticker, date, open, high, low, close,"
            " volume, is_exdiv, adj_close) VALUES (?,?,?,?,?,?,?,?,?)",
            rows
        )
        self.conn.commit()

    def test_happy_path_writes_live_row(self):
        """2330 足量 → 評分 → 寫入一筆 live。9999 不足量 → 略過（不寫入）。
        因 9999 失敗 cmd_run 最終 exit(1)，測試只驗資料正確性。"""
        args = argparse.stub()
        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", return_value={"market": "TWSE"}):
            with self.assertRaises(SystemExit):
                daily_score.cmd_run(self.conn, args)

        row = self.conn.execute(
            "SELECT * FROM daily_scores WHERE ticker='2330'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["source"], "live")

        row_9999 = self.conn.execute(
            "SELECT * FROM daily_scores WHERE ticker='9999'"
        ).fetchone()
        self.assertIsNone(row_9999)

    def test_run_exits_nonzero_on_any_failure(self):
        """有任何失敗（資料不足也算）→ 最終 sys.exit(1)。"""
        args = argparse.stub()
        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", return_value={}):
            with self.assertRaises(SystemExit) as context:
                daily_score.cmd_run(self.conn, args)
        self.assertEqual(context.exception.code, 1)

    def test_run_idempotent_same_day(self):
        """同日重跑 → 同一筆 live 列更新，不新增列。"""
        args = argparse.stub()
        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", return_value={"market": "TWSE"}):
            try:
                daily_score.cmd_run(self.conn, args)
            except SystemExit:
                pass
            count_before = self.conn.execute(
                "SELECT COUNT(*) FROM daily_scores WHERE ticker='2330'"
            ).fetchone()[0]
            try:
                daily_score.cmd_run(self.conn, args)
            except SystemExit:
                pass
            count_after = self.conn.execute(
                "SELECT COUNT(*) FROM daily_scores WHERE ticker='2330'"
            ).fetchone()[0]
        self.assertEqual(count_before, count_after)  # 冪等，列數不變


class TestCmdBackfill(TempDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        seed_watchlist(self.conn, ["2330"])
        self.days = seed_quotes(self.conn, ticker="2330", count=120)

    def test_backfill_writes_backfill_rows(self):
        args = _args(days=5)
        daily_score.cmd_backfill(self.conn, args)
        rows = self.conn.execute(
            "SELECT source FROM daily_scores WHERE ticker='2330'"
        ).fetchall()
        self.assertTrue(len(rows) > 0)
        self.assertTrue(all(r["source"] == "backfill" for r in rows))

    def test_backfill_does_not_overwrite_live(self):
        """先有一筆 live，backfill 不覆蓋它。"""
        # 先用 upsert 寫一筆 live（取 days 最後一天）
        latest_date = self.days[-1]
        result = score.evaluate(self.conn, "2330", as_of=latest_date)
        daily_score.upsert_score(self.conn, result, daily_score.SOURCE_LIVE)
        self.conn.commit()

        args = _args(days=10)
        daily_score.cmd_backfill(self.conn, args)

        row = self.conn.execute(
            "SELECT source FROM daily_scores WHERE ticker='2330' AND date=?",
            (latest_date,)
        ).fetchone()
        self.assertEqual(row["source"], "live")  # 未被 backfill 覆蓋

    def test_insufficient_data_skipped(self):
        """若某檔日線不足 60 根，backfill 對該評估日略過，不寫入。"""
        seed_watchlist(self.conn, ["9999"])
        rows = []
        for index, day in enumerate(trading_days(30)):
            close = 50.0 + index * 0.1
            rows.append(("9999", day.isoformat(), close, close * 1.01,
                          close * 0.99, close, 500, 0, close))
        self.conn.executemany(
            "INSERT INTO daily_quotes (ticker, date, open, high, low, close,"
            " volume, is_exdiv, adj_close) VALUES (?,?,?,?,?,?,?,?,?)",
            rows
        )
        self.conn.commit()

        args = _args(days=5)
        # 9999 全部日線不足 → cmd_backfill 以 exit(1) 結束，測試只驗資料不寫入
        with self.assertRaises(SystemExit):
            daily_score.cmd_backfill(self.conn, args)

        count = self.conn.execute(
            "SELECT COUNT(*) FROM daily_scores WHERE ticker='9999'"
        ).fetchone()[0]
        self.assertEqual(count, 0)


class TestCmdRank(TempDbMixin, unittest.TestCase):
    """rank 的 Δ 計算：插入已知資料後驗算 5 日與 20 日差值。"""

    def _insert_scores(self, ticker, score_list):
        """score_list 為 [(date_str, score), ...]，由舊到新插入 backfill 快照。"""
        for date_str, score_val in score_list:
            self.conn.execute(
                "INSERT INTO daily_scores (ticker, date, score, s_trend, s_bias,"
                " s_support, s_volume, s_macd, s_rsi, signal, hard_rules, source, computed_at)"
                " VALUES (?,?,?,0,0,0,0,0,0,'中性','[]','backfill','2024-01-01 00:00:00')",
                (ticker, date_str, score_val)
            )
        self.conn.commit()

    def test_delta_5_and_20_calculated_correctly(self):
        """共插入 25 筆，驗算 5 日 Δ = latest - 5th-newest、20 日 Δ = latest - 20th-newest。"""
        days = trading_days(25)
        scores = list(range(50, 75))  # 50, 51, ..., 74
        data = [(d.isoformat(), s) for d, s in zip(days, scores)]
        self._insert_scores("2330", data)
        seed_watchlist(self.conn, ["2330"])

        latest_score = scores[-1]       # 74
        score_5_ago = scores[-1 - 5]   # 69
        score_20_ago = scores[-1 - 20] # 54

        latest_row = daily_score._latest_score_row(self.conn, "2330")
        delta_5 = latest_row["score"] - daily_score._score_n_rows_ago(
            self.conn, "2330", latest_row["date"], 5)
        delta_20 = latest_row["score"] - daily_score._score_n_rows_ago(
            self.conn, "2330", latest_row["date"], 20)

        self.assertEqual(latest_row["score"], latest_score)
        self.assertEqual(delta_5, latest_score - score_5_ago)
        self.assertEqual(delta_20, latest_score - score_20_ago)

    def test_rank_shows_na_when_insufficient_history(self):
        """不足 5 筆 → 5 日 Δ 應為 None（顯示 N/A）。"""
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


# ── helper ───────────────────────────────────────────────────────────────────

class _ArgsNamespace:
    """輕量 argparse.Namespace 替代，供測試使用。"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _args(**kwargs):
    return _ArgsNamespace(**kwargs)


# argparse.stub() 供 cmd_run（不需要 args 欄位）使用
class _ArgparseStub:
    @staticmethod
    def stub():
        return _ArgsNamespace()


# 掛到 argparse 命名空間讓上面測試可用 argparse.stub()
import argparse  # noqa: E402
argparse.stub = _ArgparseStub.stub


if __name__ == "__main__":
    unittest.main()
