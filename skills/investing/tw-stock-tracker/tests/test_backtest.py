"""歷史重演回測的離線測試：不偷看未來、還原比例不影響分數、取樣與對帳口徑。"""

import argparse
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

import backtest  # noqa: E402
import backtest_report  # noqa: E402
import db  # noqa: E402
import fetch_tpex  # noqa: E402
import fetch_twse  # noqa: E402
import score  # noqa: E402

FIRST_DAY = date(2025, 1, 6)   # 週一


def trading_days(count):
    days, cursor = [], FIRST_DAY
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def seed_quotes(conn, ticker="2330", count=200):
    """波動的合成日線：讓各維度分數會變動，評分不至於恆定。"""
    rows = []
    for index, day in enumerate(trading_days(count)):
        close = 100 + 10 * math.sin(index / 7) + index * 0.05
        rows.append((ticker, day.isoformat(), close, close * 1.01, close * 0.99, close,
                     1000 + 300 * math.cos(index / 3), 0, close))
    conn.executemany("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume,"
                     " is_exdiv, adj_close) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return [day.isoformat() for day in trading_days(count)]


class BacktestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_evaluation_ignores_bars_after_as_of(self):
        days = seed_quotes(self.conn)
        as_of = days[120]
        before = score.evaluate(self.conn, "2330", as_of=as_of)
        self.conn.execute("UPDATE daily_quotes SET close = close * 3, adj_close = adj_close * 3,"
                          " volume = volume * 9 WHERE date > ?", (as_of,))
        after = score.evaluate(self.conn, "2330", as_of=as_of)
        self.assertEqual(before["date"], as_of)
        self.assertEqual((before["parts"], before["final_score"]), (after["parts"], after["final_score"]))

    def test_uniform_back_adjustment_does_not_change_score(self):
        days = seed_quotes(self.conn)
        before = score.evaluate(self.conn, "2330", as_of=days[150])
        # 日後除息會把評估日以前的還原價整段乘上同一比例
        self.conn.execute("UPDATE daily_quotes SET adj_close = adj_close * 0.97")
        after = score.evaluate(self.conn, "2330", as_of=days[150])
        self.assertEqual((before["parts"], before["final_score"]), (after["parts"], after["final_score"]))

    def test_weekly_dates_take_last_trading_day_of_each_week(self):
        seed_quotes(self.conn, count=10)
        dates = backtest.weekly_dates(self.conn, "2330", "2025-01-01", "2025-12-31")
        self.assertEqual(dates, ["2025-01-10", "2025-01-17"])

    def test_forward_return_pending_excluded_and_normal(self):
        days = seed_quotes(self.conn)
        self.assertIsNone(backtest.forward_return(self.conn, "2330", days[-1], 7))
        # 挑一個「到期日落在週末」的評估日，驗證順延到下一個交易日
        as_of = next(d for d in days[60:150]
                     if (date.fromisoformat(d) + timedelta(days=30)).weekday() >= 5)
        due = (date.fromisoformat(as_of) + timedelta(days=30)).isoformat()
        expected_end = min(d for d in days if d >= due)
        self.assertNotEqual(expected_end, due)
        end_date, value, reason = backtest.forward_return(self.conn, "2330", as_of, 30)
        self.assertEqual(end_date, expected_end)
        start, end = (self.conn.execute("SELECT adj_close FROM daily_quotes WHERE date = ?", (d,))
                      .fetchone()["adj_close"] for d in (as_of, expected_end))
        self.assertAlmostEqual(value, (end / start - 1) * 100, places=3)
        self.assertIsNone(reason)
        self.conn.execute("UPDATE daily_quotes SET is_exdiv = 1 WHERE date = ?", (days[102],))
        self.assertEqual(backtest.forward_return(self.conn, "2330", days[100], 7)[2],
                         "unknown_exdiv_in_window")

    def test_quote_far_after_due_is_excluded(self):
        days = seed_quotes(self.conn)
        due = date.fromisoformat(days[100]) + timedelta(days=7)
        self.conn.execute("DELETE FROM daily_quotes WHERE date >= ? AND date < ?",
                          (due.isoformat(), (due + timedelta(days=20)).isoformat()))
        self.assertEqual(backtest.forward_return(self.conn, "2330", days[100], 7)[2],
                         "no_quote_near_due")

    def test_no_quote_long_after_due_is_excluded_not_pending(self):
        days = seed_quotes(self.conn)
        market_days = seed_quotes(self.conn, "0050", 230)    # 市場資料延伸到更晚
        self.conn.execute("DELETE FROM daily_quotes WHERE ticker = '2330' AND date > ?", (days[150],))
        self.assertEqual(backtest.forward_return(self.conn, "2330", days[150], 7),
                         (None, None, "no_quote_near_due"))
        self.assertIsNone(backtest.forward_return(self.conn, "0050", market_days[-1], 7))

    def test_overdue_exclusion_does_not_depend_on_ticker_order(self):
        days = seed_quotes(self.conn)
        self.conn.execute("DELETE FROM daily_quotes WHERE date > ?", (days[150],))  # 2330 停牌

        def fetch_later_market_data(conn, ticker, start):
            if ticker == "0050":                       # 後處理的標的才把市場資料延伸到更晚
                seed_quotes(conn, "0050", 230)
        args = argparse.Namespace(tickers=["2330", "0050"], years=1, no_fetch=False)
        with mock.patch.object(backtest, "ensure_history", side_effect=fetch_later_market_data), \
                mock.patch.object(backtest, "date") as fake_date, mock.patch("builtins.print"):
            fake_date.today.return_value = date.fromisoformat(days[-1]) + timedelta(days=60)
            backtest.cmd_run(self.conn, args)
        excluded = self.conn.execute("SELECT COUNT(*) FROM backtest_samples WHERE ticker = '2330'"
                                     " AND excluded_reason = 'no_quote_near_due'").fetchone()[0]
        self.assertGreater(excluded, 0)

    def test_ticker_without_samples_is_skipped(self):
        args = argparse.Namespace(tickers=["9999"], years=1, no_fetch=True)
        with mock.patch("builtins.print"):
            backtest.cmd_run(self.conn, args)
        skipped = json.loads(self.conn.execute("SELECT skipped FROM backtest_runs").fetchone()[0])
        self.assertEqual([item["ticker"] for item in skipped], ["9999"])

    def test_thresholds_adopted_after_as_of_are_not_used(self):
        days = seed_quotes(self.conn)
        self.conn.execute("INSERT INTO calibrations (created_at, bull_threshold, bear_threshold,"
                          " train_n, valid_n, train_metric, valid_metric, baseline_metric, adopted)"
                          " VALUES (?, 50, 30, 1, 1, 0, 0, 0, 1)", (days[130],))
        self.assertEqual(score.evaluate(self.conn, "2330", as_of=days[120])["thresholds"]["bull"], 60)
        self.assertEqual(score.evaluate(self.conn, "2330", as_of=days[140])["thresholds"]["bull"], 50)

    def test_failing_ticker_is_skipped_and_run_marked_complete(self):
        days = seed_quotes(self.conn)
        args = argparse.Namespace(tickers=["2330", "9999"], years=1, no_fetch=False)

        def fake_history(conn, ticker, start):
            if ticker == "9999":
                raise RuntimeError("無任何日線資料")
        with mock.patch.object(backtest, "ensure_history", side_effect=fake_history), \
                mock.patch.object(backtest, "date") as fake_date, mock.patch("builtins.print"):
            fake_date.today.return_value = date.fromisoformat(days[-1])
            backtest.cmd_run(self.conn, args)
        run = self.conn.execute("SELECT status, skipped FROM backtest_runs").fetchone()
        self.assertEqual(run["status"], "complete")
        self.assertEqual([item["ticker"] for item in json.loads(run["skipped"])], ["9999"])

    def test_run_without_fetch_writes_only_matured_samples(self):
        days = seed_quotes(self.conn)
        args = argparse.Namespace(tickers=["2330"], years=1, no_fetch=True)
        with mock.patch.object(backtest, "date") as fake_date, mock.patch("builtins.print"):
            fake_date.today.return_value = date.fromisoformat(days[-1])
            backtest.cmd_run(self.conn, args)
        rows = self.conn.execute("SELECT * FROM backtest_samples").fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(r["as_of"] >= days[59] for r in rows))     # 前 60 根不足以評分
        self.assertTrue(all(r["end_date"] <= days[-1] for r in rows))  # 不含未到期樣本
        self.assertEqual({r["horizon_days"] for r in rows}, set(backtest.HORIZONS))


def months(first, last):
    return set(backtest.month_span(first, last))


class HistoryBlocksTest(unittest.TestCase):
    def test_empty_cache_fetches_whole_range(self):
        self.assertEqual(backtest.history_blocks(set(), "202511", "202602"),
                         [["202511", "202512", "202601", "202602"]])

    def test_extends_older_end_refetching_earliest_cached_month(self):
        blocks = backtest.history_blocks(months("202603", "202610"), "202601", "202610")
        self.assertEqual(blocks, [["202601", "202602", "202603"], ["202610"]])

    def test_fully_cached_only_refreshes_latest_month_onward(self):
        self.assertEqual(backtest.history_blocks(months("202501", "202609"), "202503", "202610"),
                         [["202609", "202610"]])

    def test_single_cached_month_is_not_requested_twice(self):
        self.assertEqual(backtest.history_blocks({"202603"}, "202601", "202605"),
                         [["202601", "202602", "202603"], ["202604", "202605"]])

    def test_middle_gap_is_refetched_from_month_before_first_missing(self):
        cached = {"202601", "202602", "202605", "202606"}
        self.assertEqual(backtest.history_blocks(cached, "202601", "202606"),
                         [["202602", "202603", "202604", "202605", "202606"]])


class TpexPreviousCloseTest(unittest.TestCase):
    """重抓既有月份時，第一根要拿 DB 的前收比對，否則原有的除權息標記被覆蓋成 0。"""

    RAW = [["115/09/01", "1", "0", "90", "91", "89", "90.00", "0.00"]]   # 前收 100、漲跌 0 → 除息

    def test_first_row_uses_given_previous_close(self):
        rows, events = fetch_tpex.parse_days(self.RAW, prev_close=100.0)
        self.assertEqual(rows[0]["is_exdiv"], 1)
        self.assertEqual(events, [("2026-09-01", 10.0)])
        self.assertEqual(fetch_tpex.parse_days(self.RAW)[0][0]["is_exdiv"], 0)

    def test_close_before_reads_last_cached_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(os.path.join(tmp, "tracker.db"))
            seed_quotes(conn, "5425", 30)
            last = conn.execute("SELECT close FROM daily_quotes WHERE date < '2025-02-01'"
                                " ORDER BY date DESC LIMIT 1").fetchone()["close"]
            self.assertEqual(fetch_twse._close_before(conn, "5425", "202502"), last)
            self.assertIsNone(fetch_twse._close_before(conn, "5425", "202401"))
            self.assertIsNone(fetch_twse._close_before(conn, "5425", "202504"))  # 前一月無快取
            conn.close()


class ReportTest(unittest.TestCase):
    def test_same_week_spread_compares_within_week_only(self):
        rows = [{"as_of": "2026-01-09", "score": 70, "return_pct": 5.0},
                {"as_of": "2026-01-09", "score": 30, "return_pct": 4.0},
                {"as_of": "2026-01-16", "score": 70, "return_pct": -3.0},   # 該週沒有低分組
                {"as_of": "2026-01-23", "score": 30, "return_pct": -9.0}]   # 該週沒有高分組
        spreads = backtest_report.same_week_spreads(rows, 60, 45)
        self.assertEqual(spreads, [((2026, 2), 1.0)])
        self.assertIsNone(backtest_report.summarize_spreads(spreads))

    def test_spread_requires_enough_samples_each_side(self):
        rows = [{"score": 70, "return_pct": 2.0}] * 5 + [{"score": 30, "return_pct": -1.0}] * 4
        self.assertEqual(backtest_report.score_spread(rows, 60, 45), (None, 5, 4))
        rows += [{"score": 30, "return_pct": -1.0}]
        self.assertEqual(backtest_report.score_spread(rows, 60, 45), (3.0, 5, 5))

    def test_quarter_label(self):
        self.assertEqual(backtest_report.quarter_of("2026-09-30"), "2026Q3")
        self.assertEqual(backtest_report.quarter_of("2026-10-01"), "2026Q4")


if __name__ == "__main__":
    unittest.main()
