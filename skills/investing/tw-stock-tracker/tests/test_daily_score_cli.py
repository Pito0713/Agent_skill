"""daily_score.py 的 CLI 指令與例外流程測試。

涵蓋：
  - run：足量日線評分、資料不足正常略過（不 exit 1）、真實錯誤不中斷整批且最後 exit 1
  - backfill：回補寫入、遇到既有 live 列不覆蓋、資料不足略過
  - CLI：--days 必須為正整數，拒絕 0 與負數
"""

import argparse
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

FIRST_DAY = date(2024, 1, 2)


def trading_days(count):
    days, cursor = [], FIRST_DAY
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def seed_quotes(conn, ticker="2330", count=120):
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
    conn.executemany(
        "INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
        " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd,"
        " s_rsi, signal, hard_rules, flags, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open')",
        [("2024-01-02", t, 30, 100.0, 100.0, 60, 10, 14, 10, 11, 11, 10,
          "偏多", "[]", "[]") for t in tickers]
    )
    conn.commit()


class _ArgsNamespace:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _args(**kwargs):
    return _ArgsNamespace(**kwargs)


class TempDbMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()


class TestCmdRun(TempDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        seed_watchlist(self.conn, ["2330", "9999"])
        seed_quotes(self.conn, ticker="2330", count=120)
        seed_quotes(self.conn, ticker="9999", count=30)  # 少於 60 根

    def test_insufficient_bars_skipped_without_exit_error(self):
        """日線不足 60 根為正常略過，不觸發 exit 1，exit code 為 0。"""
        args = _args()
        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", return_value={"market": "TWSE"}):
            daily_score.cmd_run(self.conn, args)

        row_2330 = self.conn.execute("SELECT * FROM daily_scores WHERE ticker='2330'").fetchone()
        self.assertIsNotNone(row_2330)
        self.assertEqual(row_2330["source"], "live")

        row_9999 = self.conn.execute("SELECT * FROM daily_scores WHERE ticker='9999'").fetchone()
        self.assertIsNone(row_9999)

    def test_real_error_continues_others_and_exits_nonzero(self):
        """真實錯誤（mock sync 拋 ValueError）時其他檔仍被處理且最後 exit 1。"""
        seed_watchlist(self.conn, ["1101"])
        seed_quotes(self.conn, ticker="1101", count=120)

        def fake_sync(_conn, ticker):
            if ticker == "1101":
                raise ValueError("1101 上游資料損毀")
            return {"market": "TWSE"}

        args = _args()
        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", side_effect=fake_sync):
            with self.assertRaises(SystemExit) as ctx:
                daily_score.cmd_run(self.conn, args)
            self.assertEqual(ctx.exception.code, 1)

        row_1101 = self.conn.execute("SELECT * FROM daily_scores WHERE ticker='1101'").fetchone()
        self.assertIsNone(row_1101)
        row_2330 = self.conn.execute("SELECT * FROM daily_scores WHERE ticker='2330'").fetchone()
        self.assertIsNotNone(row_2330)

    def test_run_idempotent_same_day(self):
        args = _args()
        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", return_value={"market": "TWSE"}):
            daily_score.cmd_run(self.conn, args)
            count_before = self.conn.execute(
                "SELECT COUNT(*) FROM daily_scores WHERE ticker='2330'"
            ).fetchone()[0]
            daily_score.cmd_run(self.conn, args)
            count_after = self.conn.execute(
                "SELECT COUNT(*) FROM daily_scores WHERE ticker='2330'"
            ).fetchone()[0]
        self.assertEqual(count_before, count_after)


class TestCmdBackfill(TempDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        seed_watchlist(self.conn, ["2330"])
        self.days = seed_quotes(self.conn, ticker="2330", count=120)

    def test_backfill_writes_backfill_rows(self):
        args = _args(days=5)
        daily_score.cmd_backfill(self.conn, args)
        rows = self.conn.execute("SELECT source FROM daily_scores WHERE ticker='2330'").fetchall()
        self.assertTrue(len(rows) > 0)
        self.assertTrue(all(r["source"] == "backfill" for r in rows))

    def test_backfill_does_not_overwrite_live(self):
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
        self.assertEqual(row["source"], "live")

    def test_insufficient_data_skipped_without_exit_error(self):
        """backfill 日線不足 60 根略過，不造成 exit 1。"""
        seed_watchlist(self.conn, ["9999"])
        seed_quotes(self.conn, ticker="9999", count=30)
        args = _args(days=5)
        daily_score.cmd_backfill(self.conn, args)

        count = self.conn.execute(
            "SELECT COUNT(*) FROM daily_scores WHERE ticker='9999'"
        ).fetchone()[0]
        self.assertEqual(count, 0)


class TestCLIParser(unittest.TestCase):
    def test_positive_int_validator(self):
        self.assertEqual(daily_score._positive_int("1"), 1)
        self.assertEqual(daily_score._positive_int("60"), 60)
        with self.assertRaises(argparse.ArgumentTypeError):
            daily_score._positive_int("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            daily_score._positive_int("-5")
        with self.assertRaises(argparse.ArgumentTypeError):
            daily_score._positive_int("not_a_number")

    def test_days_zero_and_negative_rejected(self):
        parser = daily_score.build_parser()
        for subcmd in ["backfill", "trend"]:
            for invalid_val in ["0", "-1", "-60"]:
                cmd_args = [subcmd, "--days", invalid_val]
                if subcmd == "trend":
                    cmd_args.append("2330")
                with self.assertRaises(SystemExit):
                    with mock.patch("sys.stderr"):
                        parser.parse_args(cmd_args)

    def test_days_positive_accepted(self):
        parser = daily_score.build_parser()
        args_bf = parser.parse_args(["backfill", "--days", "15"])
        self.assertEqual(args_bf.days, 15)
        args_tr = parser.parse_args(["trend", "2330", "--days", "30"])
        self.assertEqual(args_tr.days, 30)


if __name__ == "__main__":
    unittest.main()
