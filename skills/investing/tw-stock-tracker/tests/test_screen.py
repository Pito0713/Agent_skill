"""全市場日線與篩選的離線測試：不打網路、不碰正式 DB。"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import db  # noqa: E402
import fetch_market_daily as market  # noqa: E402
import screen  # noqa: E402

DAY = date(2026, 10, 7)
TWSE_FIELDS = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價",
               "漲跌(+/-)", "漲跌價差", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"]
TWSE_PAYLOAD = {"stat": "OK", "date": "20261007", "tables": [
    {"title": "價格指數"},
    {"title": "115年10月07日 每日收盤行情(全部)", "fields": TWSE_FIELDS, "data": [
        ["2330", "台積電", "16,941,183", "70,880", "1", "2,565.00", "2,585.00", "2,560.00", "2,585.00",
         "<p> </p>", "0.00", "", "", "", "", ""],
        ["00940", "元大台灣價值高息", "13,020,608", "1", "1", "13.27", "13.28", "13.21", "13.28",
         "<p>X</p>", "0.00", "", "", "", "", ""],
        ["9999", "無成交", "0", "0", "0", "--", "--", "--", "--", "<p> </p>", "0.00", "", "", "", "", ""]]}]}
TPEX_FIELDS = ["代號", "名稱", "收盤 ", "漲跌", "開盤 ", "最高 ", "最低", "成交股數  ", " 成交金額(元)"]
TPEX_PAYLOAD = {"stat": "ok", "date": "20261007", "tables": [{"fields": TPEX_FIELDS, "data": [
    ["5425", "台半", "104.50", "+4.00", "100.00", "105.50", "99.50", "15,439,000", "1,586,515,800"],
    ["6666", "停牌", "---", "---", "---", "---", "---", "0", "0"]]}]}


class ParseTest(unittest.TestCase):
    def test_twse_parses_exdiv_and_skips_untraded(self):
        quotes = market.parse_twse(TWSE_PAYLOAD, DAY)
        self.assertEqual([(q["ticker"], q["close"], q["volume"], q["is_exdiv"]) for q in quotes],
                         [("2330", 2585.0, 16941183, 0), ("00940", 13.28, 13020608, 1)])

    def test_tpex_matches_fields_with_stray_spaces(self):
        quotes = market.parse_tpex(TPEX_PAYLOAD, DAY)
        self.assertEqual(len(quotes), 1)
        self.assertEqual((quotes[0]["open"], quotes[0]["high"], quotes[0]["low"], quotes[0]["close"],
                          quotes[0]["change"], quotes[0]["turnover"]), (100.0, 105.5, 99.5, 104.5, 4.0, 1586515800.0))

    def test_holidays_errors_and_wrong_dates(self):
        self.assertEqual(market.parse_twse({"stat": "很抱歉，沒有符合條件的資料!"}, DAY), [])
        self.assertEqual(market.parse_tpex({"stat": "ok", "date": "20261007", "tables": [{"data": []}]}, DAY), [])
        for bad in ({"stat": "系統忙碌"}, dict(TWSE_PAYLOAD, date="20261006"), dict(TWSE_PAYLOAD, tables=[])):
            with self.assertRaises(RuntimeError):
                market.parse_twse(bad, DAY)
        with self.assertRaises(RuntimeError):
            market.parse_tpex(dict(TPEX_PAYLOAD, date="20261004"), DAY)
        with self.assertRaises(RuntimeError):   # 錯日期的空表不能當休市
            market.parse_tpex({"stat": "ok", "date": "20261004", "tables": [{"data": []}]}, DAY)


class TempDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "market.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def add_day(self, day, market_name, quotes):
        market.save_day(self.conn, date.fromisoformat(day), market_name, quotes)


def tpex_quote(ticker, close, change, volume=1000):
    return {"ticker": ticker, "name": ticker, "open": close, "high": close, "low": close,
            "close": close, "volume": volume, "change": change, "turnover": close * volume}


class TpexExdivTest(TempDbTest):
    def test_change_mismatch_marks_exdiv_and_implies_cash(self):
        self.add_day("2026-07-01", "TPEx", [tpex_quote("5425", 100.0, 0.0)])
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, 1.0)])   # 參考價 98 → 配 2 元
        self.assertEqual(market.detect_tpex_exdiv(self.conn), 1)
        flag = self.conn.execute("SELECT is_exdiv FROM daily_quotes WHERE date = '2026-07-02'").fetchone()[0]
        cash = self.conn.execute("SELECT cash FROM dividends WHERE ticker = '5425'").fetchone()[0]
        self.assertEqual((flag, cash), (1, 2.0))

    def test_gap_after_suspension_is_not_judged(self):
        self.add_day("2026-07-01", "TPEx", [tpex_quote("5425", 100.0, 0.0), tpex_quote("3490", 50.0, 0.0)])
        self.add_day("2026-07-02", "TPEx", [tpex_quote("3490", 50.0, 0.0)])   # 5425 停牌一天
        self.add_day("2026-07-03", "TPEx", [tpex_quote("5425", 90.0, 1.0), tpex_quote("3490", 50.0, 0.0)])
        self.assertEqual(market.detect_tpex_exdiv(self.conn), 0)
        self.assertEqual(self.conn.execute("SELECT SUM(is_exdiv) FROM daily_quotes").fetchone()[0], 0)

    def test_unfetched_whole_day_is_not_judged(self):
        self.add_day("2026-07-01", "TPEx", [tpex_quote("5425", 100.0, 0.0)])
        self.add_day("2026-07-03", "TPEx", [tpex_quote("5425", 99.0, 1.0)])   # 7/2 漏抓，不是休市
        self.assertEqual(market.detect_tpex_exdiv(self.conn), 0)
        self.conn.execute("INSERT INTO market_fetches VALUES ('2026-07-02', 'TPEx', 0)")   # 單邊 0 不可信
        self.assertEqual(market.detect_tpex_exdiv(self.conn), 0)
        self.conn.execute("INSERT INTO market_fetches VALUES ('2026-07-02', 'TWSE', 0)")   # 兩市場皆 0 才算休市
        self.assertEqual(market.detect_tpex_exdiv(self.conn), 1)

    def test_one_sided_holiday_records_are_dropped(self):
        self.conn.executemany("INSERT INTO market_fetches VALUES (?, ?, ?)",
                              [("2026-07-02", "TPEx", 0), ("2026-07-02", "TWSE", 900),
                               ("2026-07-03", "TPEx", 0), ("2026-07-03", "TWSE", 0)])
        self.assertEqual(market.drop_one_sided_holidays(self.conn), 1)
        self.assertEqual(market.confirmed_holidays(self.conn), {"2026-07-03"})

    def test_refetch_keeps_unknown_amount_flag(self):
        self.add_day("2026-07-01", "TPEx", [tpex_quote("5425", 100.0, 0.0)])
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, None)])   # 漲跌非數字：金額未知
        market.detect_tpex_exdiv(self.conn)
        self.conn.execute("DELETE FROM market_fetches WHERE date = '2026-07-01'")
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, None)])
        market.detect_tpex_exdiv(self.conn)
        flag = self.conn.execute("SELECT is_exdiv FROM daily_quotes WHERE date = '2026-07-02'").fetchone()[0]
        self.assertEqual(flag, 1)

    def test_rejudged_normal_day_clears_flag(self):
        self.add_day("2026-07-01", "TPEx", [tpex_quote("5425", 100.0, 0.0)])
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, 1.0)])
        market.detect_tpex_exdiv(self.conn)
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, -1.0)])   # 官方更正：其實是正常下跌
        market.detect_tpex_exdiv(self.conn)
        flag = self.conn.execute("SELECT is_exdiv FROM daily_quotes WHERE date = '2026-07-02'").fetchone()[0]
        self.assertEqual(flag, 0)

    def test_refetch_keeps_known_event_when_it_cannot_rejudge(self):
        self.add_day("2026-07-01", "TPEx", [tpex_quote("5425", 100.0, 0.0)])
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, 1.0)])
        market.detect_tpex_exdiv(self.conn)
        self.conn.execute("DELETE FROM market_fetches WHERE date = '2026-07-01'")   # 前一日資訊不再確定
        self.add_day("2026-07-02", "TPEx", [tpex_quote("5425", 99.0, 1.0)])         # 重抓重設旗標
        market.detect_tpex_exdiv(self.conn)
        flag = self.conn.execute("SELECT is_exdiv FROM daily_quotes WHERE date = '2026-07-02'").fetchone()[0]
        self.assertEqual(flag, 1)


class ExrightTest(TempDbTest):
    EXRIGHT_FIELDS = ["除權息日期", "代號", "名稱", "除權息前收盤價", "除權息參考價", "權值"]

    def test_tpex_exright_gives_official_ratio(self):
        payload = {"stat": "ok", "tables": [{"fields": self.EXRIGHT_FIELDS, "data": [
            ["115/08/03", "3306", "鼎天              ", "43.75", "42.05", "0"],
            ["115/08/03", "9999", "缺價", "--", "10", "0"]]}]}
        self.assertEqual(market.parse_tpex_exright(payload), [("3306", "2026-08-03", round(42.05 / 43.75, 8))])
        with self.assertRaises(RuntimeError):
            market.parse_tpex_exright({"stat": "error"})

    def twse_day(self, day, tickers):
        market.save_day(self.conn, date.fromisoformat(day), "TWSE",
                        [dict(tpex_quote(t, 10.0, 0.0), is_exdiv=flag) for t, flag in tickers])

    def test_no_comparison_after_untraded_day_is_not_exdiv(self):
        self.twse_day("2026-07-01", [("2330", 0), ("2317", 0)])
        self.twse_day("2026-07-02", [("2330", 0)])                     # 1439 型：2317 這天沒成交
        self.twse_day("2026-07-03", [("2330", 1), ("2317", 1)])        # 兩檔都是「不比價」
        self.assertEqual(market.clear_twse_no_comparison(self.conn), 1)
        flags = dict(self.conn.execute("SELECT ticker, is_exdiv FROM daily_quotes WHERE date = '2026-07-03'"))
        self.assertEqual(flags, {"2317": 0, "2330": 1})   # 2330 前一日有行情卻查無事件：維持未知

    def test_no_comparison_is_kept_when_previous_day_is_uncertain(self):
        self.twse_day("2026-07-01", [("2330", 0)])
        self.twse_day("2026-07-03", [("2330", 1)])     # 7/2 漏抓：無法確定前一日沒成交
        self.assertEqual(market.clear_twse_no_comparison(self.conn), 0)


class FetchDayTest(TempDbTest):
    OLD_DAY = date(2024, 3, 8)

    def run_fetch(self, twse, tpex):
        responses = {"TWSE": twse, "TPEx": tpex}
        with mock.patch.object(market, "_request", side_effect=lambda day, m: responses[m]), \
                mock.patch.object(market.time, "sleep"):
            return market.fetch_day(self.conn, self.OLD_DAY)

    def test_one_sided_empty_is_an_error_not_a_holiday(self):
        with self.assertRaises(RuntimeError):
            self.run_fetch([], [tpex_quote("5425", 100.0, 0.0)])
        self.assertFalse(market.is_fetched(self.conn, self.OLD_DAY, "TWSE"))
        self.assertTrue(market.is_fetched(self.conn, self.OLD_DAY, "TPEx"))

    def test_both_empty_old_day_is_a_holiday(self):
        self.assertEqual(self.run_fetch([], []), 2)
        rows = self.conn.execute("SELECT rows FROM market_fetches WHERE date = ?",
                                 (self.OLD_DAY.isoformat(),)).fetchall()
        self.assertEqual([r[0] for r in rows], [0, 0])

    def test_recent_empty_day_is_retried(self):
        with mock.patch.object(market, "_request", return_value=[]), mock.patch.object(market.time, "sleep"):
            market.fetch_day(self.conn, date.today())
        self.assertFalse(market.is_fetched(self.conn, date.today(), "TWSE"))


class ScreenTest(TempDbTest):
    DAYS = ["2026-09-%02d" % (index + 1) for index in range(20)]

    def setUp(self):
        super().setUp()
        for day in self.DAYS:
            for market_name in market.MARKETS:
                self.conn.execute("INSERT INTO market_fetches VALUES (?, ?, 100)", (day, market_name))

    def seed(self, ticker, turnover, days=None):
        for day in days or self.DAYS:
            self.conn.execute("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume,"
                              " turnover) VALUES (?, ?, 10, 10, 10, 10, 1000, ?)", (ticker, day, turnover))

    def test_universe_excludes_etf_and_illiquid(self):
        self.seed("2330", 20_000_000)
        self.seed("1234", 500_000)
        self.seed("0050", 900_000_000)               # ETF
        self.seed("2002", 30_000_000, self.DAYS[9:])   # 前 9 天停牌：均額 = 11/20 × 3,000 萬
        self.seed("2603", 15_000_000, self.DAYS[10:])  # 前 10 天停牌：均額 750 萬，不得用更早的成交補位
        self.conn.execute("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume)"
                          " VALUES ('2881', ?, 10, 10, 10, 10, 9999999)", (self.DAYS[-1],))   # 缺成交金額
        picked = dict(screen.universe(self.conn, self.DAYS[-1], screen.MIN_TURNOVER))
        self.assertEqual(sorted(picked), ["2002", "2330"])
        self.assertAlmostEqual(picked["2002"], 30_000_000 * 11 / 20)

    def test_zero_threshold_skips_missing_turnover_instead_of_crashing(self):
        self.seed("2330", 20_000_000)
        self.conn.execute("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume)"
                          " VALUES ('2881', ?, 10, 10, 10, 10, 1)", (self.DAYS[-1],))
        self.assertEqual([t for t, _ in screen.universe(self.conn, self.DAYS[-1], 0)], ["2330"])

    def test_window_with_unfetched_weekday_is_rejected(self):
        self.assertIsNotNone(screen.recent_trading_days(self.conn, self.DAYS[-1], 10))
        self.conn.execute("DELETE FROM market_fetches WHERE date = '2026-09-15'")   # 窗口內的週二漏抓
        self.assertIsNone(screen.recent_trading_days(self.conn, self.DAYS[-1], 10))

    def test_verify_rejects_a_different_as_of(self):
        later = {"date": "2026-10-08", "final_score": 70}
        with mock.patch.object(screen.fetch_twse, "sync_ticker"), \
                mock.patch.object(screen.scoring, "evaluate", return_value=later) as evaluate, \
                mock.patch("sys.stderr"):
            verified = screen.verify_with_tracker(self.conn, [{"ticker": "5425"}], "2026-10-07")
        self.assertEqual(evaluate.call_args.kwargs["as_of"], "2026-10-07")
        self.assertIsInstance(verified["5425"], str)

    def test_calibrations_are_copied_from_tracker(self):
        tracker = db.connect(os.path.join(self.tmp.name, "tracker.db"))
        tracker.execute("INSERT INTO calibrations (created_at, bull_threshold, bear_threshold, train_n, valid_n,"
                        " train_metric, valid_metric, baseline_metric, adopted)"
                        " VALUES ('2026-09-01', 70, 40, 100, 40, 1, 1, 0, 1)")
        tracker.commit()
        screen.sync_calibrations(self.conn, tracker)
        self.assertEqual(screen.scoring.load_thresholds(self.conn)["bull"], 70)
        tracker.close()

    def test_latest_day_requires_both_markets(self):
        for day, market_name in (("2026-10-06", "TWSE"), ("2026-10-06", "TPEx"), ("2026-10-07", "TWSE")):
            self.conn.execute("INSERT INTO market_fetches VALUES (?, ?, 100)", (day, market_name))
        self.assertEqual(screen.latest_trading_day(self.conn), "2026-10-06")

    def test_top_n_reports_ties_left_out(self):
        results = [{"ticker": t, "final_score": s} for t, s in (("2", 70), ("1", 80), ("3", 70), ("4", 70))]
        chosen, left_out = screen.top_n(results, 2)
        self.assertEqual([r["ticker"] for r in chosen], ["1", "2"])
        self.assertEqual(left_out, 2)

    def test_sector_flows_rank_by_share_delta(self):
        self.conn.executescript("CREATE TABLE sector_context (date TEXT, industry_code TEXT, rs_ratio REAL,"
                                " rs_momentum REAL, quadrant TEXT, share_delta REAL);")
        self.conn.executemany("INSERT INTO sector_context VALUES ('2026-10-07', ?, 1, 1, ?, ?)",
                              [("24", "Leading", 0.01), ("26", "Lagging", -0.02), ("01", None, None)])
        flows, flow_date = screen.sector_flows(self.conn, "2026-10-07")
        self.assertEqual(flow_date, "2026-10-07")
        self.assertEqual(flows, {"24": (1, 0.01, "Leading"), "26": (2, -0.02, "Lagging")})
        self.assertEqual(screen.sector_flows(self.conn, "2026-10-01"), ({}, None))


if __name__ == "__main__":
    unittest.main()
