"""watchlist.py 隱藏管理與「連續一週偏空」自動隱藏的離線測試。"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import daily_score      # noqa: E402
import dashboard_data   # noqa: E402
import dashboard_scores  # noqa: E402
import db               # noqa: E402
import watchlist        # noqa: E402

DAYS = ["2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10"]


class WatchlistTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = os.path.join(temporary.name, "tracker.db")
        self.conn = db.connect(self.path)
        self.addCleanup(self.conn.close)
        # 交易日曆來自 daily_quotes（全市場同一套日期）
        self.conn.executemany("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume)"
                              " VALUES ('0050', ?, 1, 1, 1, 1, 1)", [(day,) for day in DAYS])
        self.conn.commit()

    def add_detail_view(self, ticker):
        self.conn.execute("INSERT INTO detail_views (ticker, refreshed_at) VALUES (?, '2026-11-01 10:00')", (ticker,))
        self.conn.commit()

    def add_scores(self, ticker, scores, days=None):
        days = days or DAYS[-len(scores):]
        self.conn.executemany(
            "INSERT INTO daily_scores (ticker, date, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi,"
            " signal, source, computed_at) VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, '', 'live', '2026-11-10')",
            [(ticker, day, score) for day, score in zip(days, scores)])
        self.conn.commit()

    def add_open_position(self, ticker):
        self.conn.execute("INSERT INTO positions (ticker, buy_date, buy_price, shares, basis_date, basis_close,"
                          " score, signal) VALUES (?, '2026-11-01', 100, 1000, '2026-11-01', 100, 40, '偏空')", (ticker,))
        self.conn.commit()

    def candidates(self, tickers):
        return watchlist.find_auto_hide_candidates(self.conn, tickers)

    def test_five_days_below_threshold_is_candidate(self):
        self.add_scores("2327", [44, 30, 32, 38, 40])
        self.assertEqual(self.candidates(["2327"]), ["2327"])

    def test_one_day_at_threshold_breaks_streak(self):
        self.add_scores("2327", [44, 30, 45, 38, 40])
        self.assertEqual(self.candidates(["2327"]), [])

    def test_missing_day_breaks_streak(self):
        self.add_scores("2327", [30, 30, 30, 30], days=[DAYS[1], DAYS[2], DAYS[4], DAYS[5]])
        self.assertEqual(self.candidates(["2327"]), [])

    def test_older_scores_outside_window_ignored(self):
        self.add_scores("2327", [80, 30, 30, 30, 30, 30])
        self.assertEqual(self.candidates(["2327"]), ["2327"])

    def test_fewer_than_five_trading_days_hides_nothing(self):
        self.conn.execute("DELETE FROM daily_quotes WHERE date < '2026-11-06'")
        self.add_scores("2327", [30, 30])
        self.assertEqual(self.candidates(["2327"]), [])

    def test_threshold_follows_adopted_calibration(self):
        self.add_scores("2327", [42, 42, 42, 42, 42])
        self.conn.execute(
            "INSERT INTO calibrations (created_at, bull_threshold, bear_threshold, train_n, valid_n, train_metric,"
            " valid_metric, baseline_metric, adopted) VALUES ('2026-10-01', 60, 40, 1, 1, 0, 0, 0, 1)")
        self.conn.commit()
        self.assertEqual(self.candidates(["2327"]), [], "偏空門檻校準為 40 後，42 分不算偏空")

    def test_open_position_exempt_but_open_prediction_not(self):
        self.add_scores("2327", [30] * 5)
        self.add_scores("2481", [30] * 5)
        self.add_open_position("2327")
        self.conn.execute(
            "INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred, adj_close_at_pred, score,"
            " s_trend, s_bias, s_support, s_volume, s_macd, s_rsi, signal, hard_rules, flags, status)"
            " VALUES ('2026-11-01', '2481', 30, 1, 1, 30, 0, 0, 0, 0, 0, 0, '偏空', '[]', '[]', 'open')")
        self.conn.commit()
        self.assertEqual(self.candidates(["2327", "2481"]), ["2481"])

    def test_apply_hides_once_and_excludes_from_watchlist(self):
        self.add_detail_view("2327")
        self.add_scores("2327", [30] * 5)
        self.assertEqual(watchlist.apply_auto_hide(self.conn, ["2327"], dry_run=True), ["2327"])
        self.assertEqual(watchlist.hidden_tickers(self.conn), set(), "dry-run 不寫入")
        self.assertEqual(watchlist.apply_auto_hide(self.conn, ["2327"]), ["2327"])
        self.assertEqual(watchlist.apply_auto_hide(self.conn, ["2327"]), [], "已隱藏不重複隱藏")
        self.assertNotIn("2327", daily_score.load_watchlist(self.conn))
        row = watchlist.list_hidden(self.conn)[0]
        self.assertEqual(row["reason"], watchlist.REASON_AUTO_BEARISH)

    def test_manual_hide_keeps_original_reason_and_unhide_restores(self):
        self.add_detail_view("2330")
        self.assertTrue(watchlist.hide(self.conn, "2330", note="不看"))
        self.assertFalse(watchlist.hide(self.conn, "2330", watchlist.REASON_AUTO_BEARISH))
        self.assertEqual(watchlist.list_hidden(self.conn)[0]["reason"], watchlist.REASON_MANUAL)
        self.assertTrue(watchlist.unhide(self.conn, "2330"))
        self.assertFalse(watchlist.unhide(self.conn, "2330"))
        self.assertIn("2330", daily_score.load_watchlist(self.conn))

    def test_dashboard_excludes_hidden_and_lists_them(self):
        self.add_detail_view("2327")
        self.add_detail_view("2330")
        self.add_scores("2327", [30] * 5)
        self.add_scores("2330", [70] * 5)
        watchlist.hide(self.conn, "2327", watchlist.REASON_AUTO_BEARISH)
        with mock.patch.object(dashboard_data, "_latest_entry", return_value=None):
            rankings = dashboard_data.score_rankings(self.conn)
        self.assertEqual([item["ticker"] for item in rankings], ["2330"])
        self.assertEqual([item["ticker"] for item in dashboard_data.detail_views(self.conn)], ["2330"])
        page = dashboard_scores.render_rankings(rankings, dashboard_data.hidden_list(self.conn))
        self.assertIn("已隱藏 1 檔", page)
        self.assertIn("連續一週偏空", page)

    def test_daily_run_auto_hides_even_when_another_ticker_fails(self):
        self.add_detail_view("2327")
        self.add_detail_view("2330")
        self.add_scores("2327", [30] * 5)

        def fake_sync(_conn, ticker):
            if ticker == "2330":
                raise RuntimeError("network down")
            return {"market": "TWSE"}

        with mock.patch.object(daily_score.fetch_twse, "sync_ticker", side_effect=fake_sync):
            with self.assertRaises(SystemExit):
                daily_score.cmd_run(self.conn, None)
        self.assertEqual(watchlist.hidden_tickers(self.conn), {"2327"})

    def test_dashboard_tolerates_db_without_hidden_table(self):
        self.conn.execute("DROP TABLE hidden_tickers")
        self.conn.commit()
        self.assertEqual(dashboard_data.hidden_tickers(self.conn), set())
        self.assertEqual(dashboard_data.hidden_list(self.conn), [])


if __name__ == "__main__":
    unittest.main()
