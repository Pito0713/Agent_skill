"""三大法人抓取與因子的離線測試：不打網路、不碰正式 DB。"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import backtest_report  # noqa: E402
import db  # noqa: E402
import fetch_flows  # noqa: E402
import flows  # noqa: E402

DAY = date(2026, 10, 7)
TWSE_FIELDS = ["證券代號", "證券名稱", "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)",
               "外陸資買賣超股數(不含外資自營商)", "外資自營商買進股數", "外資自營商賣出股數",
               "外資自營商買賣超股數", "投信買進股數", "投信賣出股數", "投信買賣超股數", "自營商買賣超股數",
               "自營商買進股數(自行買賣)", "自營商賣出股數(自行買賣)", "自營商買賣超股數(自行買賣)",
               "自營商買進股數(避險)", "自營商賣出股數(避險)", "自營商買賣超股數(避險)", "三大法人買賣超股數"]
TWSE_PAYLOAD = {"stat": "OK", "date": "20261007", "fields": TWSE_FIELDS, "data": [
    ["1301", "台塑            ", "50,263,875", "14,595,540", "35,668,335", "0", "0", "0", "10,282,000",
     "0", "10,282,000", "1,952,676", "788,561", "228,000", "560,561", "1,637,235", "245,120",
     "1,392,115", "47,903,011"]]}
# 2026-10-07 上櫃實際資料（5425 台半）
TPEX_ROW = ["5425", "台半", "5,581,077", "3,267,700", "2,313,377", "0", "0", "0", "5,581,077", "3,267,700",
            "2,313,377", "0", "0", "0", "42,000", "22,000", "20,000", "446,122", "30,888", "415,234",
            "488,122", "52,888", "435,234", "2,748,611"]
TPEX_FIELDS = ["代號", "名稱"] + ["買進股數", "賣出股數", "買賣超股數"] * 7 + ["三大法人買賣超股數合計"]


def tpex_payload(rows, day="20261007"):
    return {"stat": "ok", "date": day, "tables": [{"fields": TPEX_FIELDS, "data": rows}, {}]}


class ParseTest(unittest.TestCase):
    def test_twse_picks_named_columns(self):
        self.assertEqual(fetch_flows.parse_twse(TWSE_PAYLOAD, DAY),
                         [("1301", 35668335, 10282000, 1952676, 47903011)])

    def test_tpex_uses_verified_column_positions(self):
        self.assertEqual(fetch_flows.parse_tpex(tpex_payload([TPEX_ROW]), DAY),
                         [("5425", 2313377, 0, 435234, 2748611)])

    def test_tpex_shifted_columns_fail_loudly(self):
        shifted = TPEX_ROW[:11] + TPEX_ROW[14:17] + TPEX_ROW[11:14] + TPEX_ROW[17:]   # 投信與自營自行對調
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_tpex(tpex_payload([shifted]), DAY)
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_tpex({"stat": "ok", "date": "20261007",
                                    "tables": [{"fields": TPEX_FIELDS[:-1], "data": [TPEX_ROW]}]}, DAY)

    def test_tpex_total_excluding_foreign_dealer_is_accepted(self):
        row = list(TPEX_ROW)
        row[5:8] = ["10", "0", "10"]                     # 外資自營商淨買 10
        row[8:11] = ["5,581,087", "3,267,700", "2,313,387"]   # 外資合計 = 外資 + 外資自營商
        self.assertEqual(fetch_flows.parse_tpex(tpex_payload([row]), DAY)[0][1], 2313377)
        row[23] = "2,748,621"                            # 合計含外資自營商的算法也接受
        self.assertEqual(fetch_flows.parse_tpex(tpex_payload([row]), DAY)[0][4], 2748621)

    def test_tpex_trust_and_dealer_swap_fails_loudly(self):
        swapped = TPEX_ROW[:11] + TPEX_ROW[20:23] + TPEX_ROW[14:20] + TPEX_ROW[11:14] + TPEX_ROW[23:]
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_tpex(tpex_payload([swapped]), DAY)

    def test_tpex_wrong_date_empty_table_is_not_a_holiday(self):
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_tpex(tpex_payload([], "20261004"), date(2024, 3, 8))

    def test_holidays_are_empty(self):
        self.assertEqual(fetch_flows.parse_twse({"stat": "很抱歉，沒有符合條件的資料!"}, DAY), [])
        self.assertEqual(fetch_flows.parse_tpex(tpex_payload([], "20261004"), date(2026, 10, 4)), [])

    def test_service_errors_and_wrong_dates_raise(self):
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_twse({"stat": "系統忙碌，請稍後再試"}, DAY)
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_twse(TWSE_PAYLOAD, DAY - timedelta(days=1))
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_tpex(tpex_payload([TPEX_ROW]), DAY - timedelta(days=1))
        with self.assertRaises(RuntimeError):
            fetch_flows.parse_tpex({"stat": "error"}, DAY)


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_service_error_is_not_cached(self):
        old_day = date(2024, 3, 8)
        with mock.patch.object(fetch_flows.fetch_twse, "_get_json",
                               return_value={"stat": "系統忙碌，請稍後再試"}), \
                self.assertRaises(RuntimeError):
            fetch_flows.fetch_date(self.conn, old_day, "TWSE")
        self.assertFalse(fetch_flows.is_fetched(self.conn, old_day, "TWSE"))

    def test_recent_empty_day_is_not_recorded_as_holiday(self):
        today = date.today()
        with mock.patch.object(fetch_flows.fetch_twse, "_get_json",
                               return_value={"stat": "很抱歉，沒有符合條件的資料!"}):
            fetch_flows.fetch_date(self.conn, today, "TWSE")
            fetch_flows.fetch_date(self.conn, date(2024, 2, 12), "TWSE")
        self.assertFalse(fetch_flows.is_fetched(self.conn, today, "TWSE"))
        self.assertTrue(fetch_flows.is_fetched(self.conn, date(2024, 2, 12), "TWSE"))

    def test_backfill_skips_weekends_and_fetched_days(self):
        self.conn.execute("INSERT INTO flow_fetches VALUES ('2024-03-04', 'TWSE', 900)")
        with mock.patch.object(fetch_flows, "fetch_date", return_value=1) as fetch, \
                mock.patch.object(fetch_flows.time, "sleep"):
            requested = fetch_flows.backfill(self.conn, date(2024, 3, 2), date(2024, 3, 5))
        self.assertEqual(requested, 3)   # 週一 TPEx、週二兩市場；週末與已抓的週一 TWSE 略過
        self.assertEqual({(c.args[1], c.args[2]) for c in fetch.call_args_list},
                         {(date(2024, 3, 4), "TPEx"), (date(2024, 3, 5), "TWSE"),
                          (date(2024, 3, 5), "TPEx")})


class FactorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "tracker.db"))
        self.days = [d.isoformat() for d in fetch_flows.weekdays_between(date(2025, 1, 6), date(2025, 2, 14))]
        for index, day in enumerate(self.days):
            self.conn.execute("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume)"
                              " VALUES ('5425', ?, 10, 10, 10, 10, 1000)", (day,))
            for market in fetch_flows.MARKETS:
                self.conn.execute("INSERT INTO flow_fetches VALUES (?, ?, 800)", (day, market))
            if index % 2 == 0:   # 奇數日不在名單上 = 法人零買賣
                self.conn.execute("INSERT INTO institutional_flows VALUES ('5425', ?, 100, -50, 7, 57)",
                                  (day,))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def factors(self, as_of):
        return dict(zip(flows.FACTOR_COLUMNS, flows.factor_values(self.conn, "5425", as_of)))

    def test_net_buy_over_volume(self):
        as_of = self.days[24]   # 偶數 index：近 5 日有 3 天上榜，近 20 日有 10 天
        values = self.factors(as_of)
        self.assertAlmostEqual(values["flow_foreign_5d"], 300 / 5000)
        self.assertAlmostEqual(values["flow_trust_5d"], -150 / 5000)
        self.assertAlmostEqual(values["flow_foreign_20d"], 1000 / 20000)
        self.assertAlmostEqual(values["flow_trust_20d"], -500 / 20000)

    def test_ignores_data_after_as_of(self):
        as_of = self.days[24]
        before = self.factors(as_of)
        self.conn.execute("UPDATE institutional_flows SET foreign_net = foreign_net * 99 WHERE date > ?",
                          (as_of,))
        self.conn.execute("UPDATE daily_quotes SET volume = 1 WHERE date > ?", (as_of,))
        self.assertEqual(before, self.factors(as_of))

    def test_missing_history_gives_none(self):
        values = self.factors(self.days[10])   # 只有 11 根日線，20 日因子不給
        self.assertIsNotNone(values["flow_foreign_5d"])
        self.assertIsNone(values["flow_foreign_20d"])
        self.conn.execute("DELETE FROM flow_fetches WHERE date = ? AND market = 'TPEx'", (self.days[23],))
        self.assertIsNone(self.factors(self.days[24])["flow_foreign_5d"])   # 有一天沒抓到就不猜 0


class ReportTest(unittest.TestCase):
    def test_flow_ic_splits_weeks_into_halves(self):
        rows = []
        monday = date(2025, 1, 6)
        for week in range(24):
            as_of = (monday + timedelta(weeks=week, days=4)).isoformat()
            for rank in range(6):
                sign = 1 if week < 12 else -1   # 前半正相關、後半負相關
                noisy_rank = {0: 1, 1: 0}.get(rank, rank) if week % 3 == 0 else rank   # 讓每週 IC 不全相同
                rows.append({"as_of": as_of, "flow_foreign_5d": rank / 10,
                             "tradable_return_pct": sign * noisy_rank})
        cut = backtest_report.half_cut(rows)
        whole, first, second = backtest_report.flow_ic(rows, "flow_foreign_5d", 7, cut)
        self.assertGreater(first["mean"], 0)
        self.assertLess(second["mean"], 0)
        self.assertEqual(whole["weeks"], 24)

    def test_cut_comes_from_all_weeks_not_valid_ic_weeks(self):
        rows = []
        monday = date(2025, 1, 6)
        for week in range(24):
            as_of = (monday + timedelta(weeks=week, days=4)).isoformat()
            tickers = 2 if week < 12 else 6   # 前 12 週橫斷面太薄，算不出 IC
            for rank in range(tickers):
                noisy_rank = {0: 1, 1: 0}.get(rank, rank) if week % 3 == 0 else rank
                rows.append({"as_of": as_of, "flow_foreign_5d": rank / 10,
                             "tradable_return_pct": noisy_rank})
        cut = backtest_report.half_cut(rows)
        whole, first, second = backtest_report.flow_ic(rows, "flow_foreign_5d", 7, cut)
        self.assertIsNone(first)   # 前半沒有有效週，不能把後段的週當成前半
        self.assertEqual(second["weeks"], whole["weeks"])


class ReportCutTest(unittest.TestCase):
    """cmd_report 走真實 DB：長期間尾端未到期不落庫，切點仍須由整個 run 決定。"""

    def test_cut_is_shared_across_horizons(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(os.path.join(tmp, "tracker.db"))
            conn.execute("INSERT INTO backtest_runs (id, created_at, start_date, end_date, tickers, params,"
                         " status) VALUES (1, '2025-07-01', '2025-01-06', '2025-07-01', '[]',"
                         " '{\"horizons\": [7, 30], \"bull\": 60, \"bear\": 45}', 'complete')")
            weeks = [(date(2025, 1, 10) + timedelta(weeks=w)).isoformat() for w in range(20)]
            for horizon, saved in ((7, weeks), (30, weeks[:15])):   # 30 天最後 5 週未到期
                for as_of in saved:
                    conn.execute("INSERT INTO backtest_samples (run_id, ticker, as_of, horizon_days, score,"
                                 " s_trend, s_bias, s_support, s_volume, s_macd, s_rsi, signal, entry_date, return_pct,"
                                 " tradable_return_pct)"
                                 " VALUES (1, '2330', ?, ?, 50, 0, 0, 0, 0, 0, 0, '中性', ?, 1, 1)",
                                 (as_of, horizon, as_of))
            conn.commit()
            with mock.patch.object(backtest_report, "print_flow_ic") as printed, \
                    mock.patch.object(backtest_report, "print_quarterly"), \
                    mock.patch.object(backtest_report, "print_valuation_grid"), \
                    mock.patch("builtins.print"):
                backtest_report.cmd_report(conn, mock.Mock(run=None, horizon=30))
            cuts = {c.args[2] for c in printed.call_args_list}
            self.assertEqual(cuts, {backtest_report.week_of(weeks[10])})
            conn.close()


if __name__ == "__main__":
    unittest.main()
