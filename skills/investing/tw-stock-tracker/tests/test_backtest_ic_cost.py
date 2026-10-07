"""回測 Rank IC 統計與可成交口徑（次日開盤、交易成本、漲跌停）的離線測試。"""

import math
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import backtest_execution  # noqa: E402
import backtest_stats  # noqa: E402
import db  # noqa: E402


class RankTest(unittest.TestCase):
    def test_ties_get_average_rank(self):
        self.assertEqual(backtest_stats.average_ranks([10, 30, 20, 30]), [1.0, 3.5, 2.0, 3.5])

    def test_spearman_perfect_reverse_and_no_variance(self):
        self.assertAlmostEqual(backtest_stats.spearman([1, 2, 3, 4], [10, 20, 35, 90]), 1.0)
        self.assertAlmostEqual(backtest_stats.spearman([1, 2, 3, 4], [9, 7, 5, 1]), -1.0)
        self.assertIsNone(backtest_stats.spearman([50, 50, 50], [1, 2, 3]))   # 當週全部同分

    def test_weekly_ic_skips_thin_weeks(self):
        rows = [{"as_of": "2026-01-09", "score": s, "ret": s / 10} for s in range(5)]
        rows += [{"as_of": "2026-01-16", "score": s, "ret": -s} for s in range(4)]   # 只有 4 檔
        self.assertEqual(backtest_stats.weekly_ic(rows, "score", "ret"), [((2026, 2), 1.0)])


class SummaryTest(unittest.TestCase):
    def test_t_value_discounts_overlapping_horizons(self):
        weekly = [((2026, w), ic) for w, ic in enumerate([0.1, 0.3, 0.2, 0.0, 0.4, 0.2, 0.1, 0.3], 1)]
        short = backtest_stats.summarize_ic(weekly, 7)
        long = backtest_stats.summarize_ic(weekly, 30)
        self.assertEqual((short["overlap"], long["overlap"]), (1, 5))
        self.assertAlmostEqual(short["t"], short["icir"] * math.sqrt(8))
        self.assertAlmostEqual(long["t"], short["t"] / math.sqrt(5))
        self.assertIn("不下結論", backtest_stats.verdict(short))   # 8 週 < 10 有效週
        weekly = weekly * 2
        self.assertEqual(backtest_stats.verdict(backtest_stats.summarize_ic(weekly, 7)), "統計上可分辨")

    def test_few_overlapping_weeks_do_not_get_a_verdict(self):
        summary = backtest_stats.summarize_ic([((2026, 1), 0.8), ((2026, 2), 0.9)], 30)
        self.assertGreater(abs(summary["t"]), 2)
        self.assertIn("不下結論", backtest_stats.verdict(summary))

    def test_insufficient_or_constant_ic(self):
        self.assertIsNone(backtest_stats.summarize_ic([((2026, 1), 0.2)], 7))
        self.assertIsNone(backtest_stats.summarize_ic([((2026, 1), 0.2), ((2026, 2), 0.2)], 7))
        self.assertEqual(backtest_stats.verdict(None), "樣本不足")


class TradableReturnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def seed(self, ticker, bars):
        """bars: [(date, open, high, low, close, adj_close)]"""
        self.conn.executemany(
            "INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume, is_exdiv,"
            " adj_close) VALUES (?, ?, ?, ?, ?, ?, 1000, 0, ?)",
            [(ticker, *bar) for bar in bars])
        self.conn.commit()

    def test_enters_next_open_and_deducts_stock_costs(self):
        self.seed("2330", [("2026-01-05", 100, 101, 99, 100, 100),
                           ("2026-01-06", 102, 104, 101, 103, 103),
                           ("2026-01-12", 110, 111, 109, 110, 110)])
        entry, value, reason = backtest_execution.tradable_return(
            self.conn, "2330", ("2026-01-05", "2026-01-12"), 1.0)
        expected = (110 * (1 - 0.001425 - 0.003) / (102 * 1.001425) - 1) * 100
        self.assertEqual((entry, reason), ("2026-01-06", None))
        self.assertAlmostEqual(value, expected, places=3)

    def test_etf_tax_and_fee_discount(self):
        self.assertEqual(backtest_execution.round_trip_rates("0050", 0.6),
                         (0.001425 * 0.6, 0.001425 * 0.6 + 0.001))

    def test_open_uses_same_adjustment_basis_as_close(self):
        # 進場日之後才除息：進場日還原價 = 原始 × 0.9，開盤也要乘 0.9
        self.seed("2412", [("2026-01-05", 100, 101, 99, 100, 90),
                           ("2026-01-06", 100, 101, 99, 100, 90),
                           ("2026-01-12", 91, 92, 90, 91, 91)])
        _, value, _ = backtest_execution.tradable_return(
            self.conn, "2412", ("2026-01-05", "2026-01-12"), 1.0)
        expected = (91 * (1 - 0.001425 - 0.003) / (90 * 1.001425) - 1) * 100
        self.assertAlmostEqual(value, expected, places=3)

    def test_limit_up_open_cannot_buy(self):
        self.seed("3490", [("2026-01-05", 100, 100, 100, 100, 100),
                           ("2026-01-06", 110, 110, 110, 110, 110),
                           ("2026-01-12", 120, 121, 119, 120, 120)])
        self.assertEqual(backtest_execution.tradable_return(
            self.conn, "3490", ("2026-01-05", "2026-01-12"), 1.0)[2], "entry_limit_up")

    def test_locked_limit_down_cannot_sell(self):
        self.seed("6234", [("2026-01-05", 100, 101, 99, 100, 100),
                           ("2026-01-06", 100, 101, 99, 100, 100),
                           ("2026-01-09", 100, 101, 99, 100, 100),
                           ("2026-01-12", 90, 90, 90, 90, 90)])
        self.assertEqual(backtest_execution.tradable_return(
            self.conn, "6234", ("2026-01-05", "2026-01-12"), 1.0)[2], "exit_limit_down")



class ReportEdgeTest(unittest.TestCase):
    def row(self, **overrides):
        base = {"as_of": "2026-01-09", "score": 50, "return_pct": 1.0, "entry_date": None,
                "tradable_return_pct": None, "tradable_excluded_reason": None,
                "excluded_reason": None}
        base.update(overrides)
        return base

    def test_all_limit_blocked_new_run_is_not_called_legacy(self):
        import backtest_report
        blocked = [self.row(entry_date="2026-01-12", tradable_excluded_reason="entry_limit_up")]
        self.assertFalse(backtest_report.is_legacy_run(blocked))
        self.assertTrue(backtest_report.is_legacy_run([self.row()]))


if __name__ == "__main__":
    unittest.main()