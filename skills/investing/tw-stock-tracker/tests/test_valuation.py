"""估值抓取與百分位的離線測試：不打網路、不碰正式 DB。"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import db  # noqa: E402
import fetch_valuation  # noqa: E402
import valuation  # noqa: E402

TWSE_PAYLOAD = {"stat": "OK",
                "fields": ["證券代號", "證券名稱", "收盤價", "殖利率(%)", "股利年度", "本益比",
                           "股價淨值比", "財報年/季"],
                "data": [["2330", "台積電", "533.00", "2.06", 111, "14.31", "4.33", "112/2"],
                         ["2002", "中鋼", "25.00", "0.00", 111, "-", "1.10", "112/2"]]}
TPEX_PAYLOAD = {"stat": "ok", "tables": [{"fields": ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度",
                                       "殖利率(%)", "股價淨值比"],
                            "data": [["5425", "台半", "13.20", "2.6", 111, "3.50", "1.00"]]}]}


class ParseTest(unittest.TestCase):
    def test_twse_rows_and_loss_making_pe(self):
        rows = fetch_valuation.parse_twse(TWSE_PAYLOAD)
        self.assertEqual(rows, [("2330", 14.31, 4.33, 2.06, "112/2"), ("2002", None, 1.10, 0.0, "112/2")])

    def test_tpex_rows_have_no_fiscal_period(self):
        self.assertEqual(fetch_valuation.parse_tpex(TPEX_PAYLOAD), [("5425", 13.2, 1.0, 3.5, None)])

    def test_holiday_responses_are_empty(self):
        self.assertEqual(fetch_valuation.parse_twse({"stat": "很抱歉，沒有符合條件的資料!"}), [])
        self.assertEqual(fetch_valuation.parse_tpex({"stat": "ok", "tables": [{"data": []}]}), [])

    def test_service_errors_raise_instead_of_looking_like_holidays(self):
        with self.assertRaises(RuntimeError):
            fetch_valuation.parse_twse({"stat": "系統忙碌，請稍後再試"})
        with self.assertRaises(RuntimeError):
            fetch_valuation.parse_tpex({"stat": "error"})
        for malformed in ({"stat": "OK"}, {"stat": "OK", "data": []}):
            with self.assertRaises(RuntimeError):
                fetch_valuation.parse_twse(malformed)
        with self.assertRaises(RuntimeError):
            fetch_valuation.parse_tpex({"stat": "ok", "tables": [{}]})

    def test_service_error_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(os.path.join(tmp, "tracker.db"))
            old_day = date(2024, 3, 8)
            with mock.patch.object(fetch_valuation.fetch_twse, "_get_json",
                                   return_value={"stat": "系統忙碌，請稍後再試"}), \
                    self.assertRaises(RuntimeError):
                fetch_valuation.fetch_date(conn, old_day, "TWSE")
            self.assertFalse(fetch_valuation.is_fetched(conn, old_day, "TWSE"))
            conn.close()

    def test_changed_fields_raise(self):
        with self.assertRaises(RuntimeError):
            fetch_valuation.parse_twse({"fields": ["代號"], "data": [["2330"]]})

    def test_fridays_between(self):
        fridays = list(fetch_valuation.fridays_between(date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual([d.day for d in fridays], [4, 11, 18, 25])


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))
        patcher = mock.patch.object(fetch_valuation.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_holiday_falls_back_to_previous_trading_day_and_is_remembered(self):
        friday = date(2024, 2, 9)                            # 春節休市
        responses = {date(2024, 2, 9): [], date(2024, 2, 8): [],
                     date(2024, 2, 7): [("2330", 15.0, 4.0, 2.0, "112/4")]}
        with mock.patch.object(fetch_valuation, "_request",
                               side_effect=lambda day, market: (responses[day], "BWIBBU_d")) as request:
            self.assertEqual(fetch_valuation.backfill_week(self.conn, friday, "TWSE"), date(2024, 2, 7))
            self.assertEqual(fetch_valuation.backfill_week(self.conn, friday, "TWSE"), date(2024, 2, 7))
        self.assertEqual(request.call_count, 3)              # 第二次全部走快取

    def test_recent_empty_day_is_not_recorded_as_holiday(self):
        today = date.today()
        with mock.patch.object(fetch_valuation, "_request", return_value=([], "BWIBBU_d")):
            fetch_valuation.fetch_date(self.conn, today, "TWSE")
        self.assertFalse(fetch_valuation.is_fetched(self.conn, today, "TWSE"))


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def seed_weekly(self, weeks, end=date(2026, 9, 25), pe_of=lambda i: 10.0 + i):
        for i in range(weeks):
            day = end - timedelta(weeks=weeks - 1 - i)
            self.conn.execute("INSERT INTO valuations (ticker, date, pe, pb, dividend_yield, source)"
                              " VALUES ('2330', ?, ?, 2.0, 3.0, 'BWIBBU_d')",
                              (day.isoformat(), pe_of(i)))
        self.conn.commit()

    def test_percentile_uses_only_history_before_as_of(self):
        self.seed_weekly(101)                                 # PE 10..110，最後一筆 110
        snap = valuation.snapshot(self.conn, "2330", "2026-09-25")
        self.assertEqual(snap["pe"], 110.0)
        self.assertEqual(snap["pe_percentile"], 100.0)
        earlier = valuation.snapshot(self.conn, "2330", "2026-07-31")   # 當時 PE = 102
        self.assertEqual(earlier["pe"], 102.0)
        self.assertEqual(earlier["pe_history_n"], 92)          # 不含之後的週
        self.assertEqual(earlier["pe_percentile"], 100.0)

    def test_middle_value_percentile(self):
        self.seed_weekly(60, pe_of=lambda i: 30.0 if i == 59 else float(i))
        snap = valuation.snapshot(self.conn, "2330", "2026-09-25")
        self.assertEqual(snap["pe_percentile"], round(31 / 59 * 100, 1))   # 0..30 共 31 筆 ≤ 30

    def test_dense_daily_rows_count_once_per_week(self):
        self.seed_weekly(60, end=date(2026, 9, 18), pe_of=lambda i: 10.0)
        for offset in range(1, 5):                            # 同一週多補四筆高值
            self.conn.execute("INSERT INTO valuations (ticker, date, pe, source) VALUES"
                              " ('2330', ?, 99.0, 'BWIBBU_d')",
                              ((date(2026, 9, 18) - timedelta(days=offset)).isoformat(),))
        self.conn.execute("INSERT INTO valuations (ticker, date, pe, source) VALUES"
                          " ('2330', '2026-09-25', 50.0, 'BWIBBU_d')")
        snap = valuation.snapshot(self.conn, "2330", "2026-09-25")
        self.assertEqual(snap["pe_history_n"], 60)
        self.assertEqual(snap["pe_percentile"], 100.0)        # 9/14–9/17 的 99 被同週 9/18 取代

    def test_fifty_two_daily_rows_are_not_a_year_of_history(self):
        end = date(2026, 9, 25)
        for offset in range(1, 53):
            self.conn.execute("INSERT INTO valuations (ticker, date, pe, source) VALUES"
                              " ('2330', ?, 10.0, 'BWIBBU_d')", ((end - timedelta(days=offset)).isoformat(),))
        self.conn.execute("INSERT INTO valuations (ticker, date, pe, source) VALUES"
                          " ('2330', ?, 12.0, 'BWIBBU_d')", (end.isoformat(),))
        self.assertIsNone(valuation.snapshot(self.conn, "2330", end.isoformat())["pe_percentile"])

    def test_short_history_gives_no_percentile(self):
        self.seed_weekly(20)
        snap = valuation.snapshot(self.conn, "2330", "2026-09-25")
        self.assertIsNone(snap["pe_percentile"])
        self.assertIn("不足", valuation.describe(snap))

    def test_loss_making_and_stale_and_missing(self):
        self.seed_weekly(60, pe_of=lambda i: None if i == 59 else 10.0)
        snap = valuation.snapshot(self.conn, "2330", "2026-09-25")
        self.assertIsNone(snap["pe"])
        self.assertIsNone(snap["pe_percentile"])
        self.assertIsNotNone(snap["pb_percentile"])
        self.assertIsNone(valuation.snapshot(self.conn, "2330", "2026-10-07"))   # 最近一筆已逾 7 天
        self.assertIsNone(valuation.snapshot(self.conn, "0050", "2026-09-25"))
        self.assertEqual(valuation.percentile_values(None), (None, None, None))

    def test_attach_to_prediction(self):
        self.seed_weekly(60)
        self.conn.execute("INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
                          " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd,"
                          " s_rsi, signal, status) VALUES ('2026-09-25', '2330', 30, 1, 1, 50,"
                          " 0, 0, 0, 0, 0, 0, '中性', 'open')")
        valuation.attach_to_prediction(self.conn, 1, valuation.snapshot(self.conn, "2330", "2026-09-25"))
        row = self.conn.execute("SELECT pe, pe_percentile FROM predictions").fetchone()
        self.assertEqual((row["pe"], row["pe_percentile"]), (69.0, 100.0))


if __name__ == "__main__":
    unittest.main()
