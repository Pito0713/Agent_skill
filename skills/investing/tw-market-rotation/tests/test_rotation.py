"""離線測試：fixture 為 2026-09-29 的真實 TWSE 回應（已裁掉無關表格）。"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import fetch_market  # noqa: E402
import rotation  # noqa: E402
import schema  # noqa: E402
import sectors  # noqa: E402

# 2026-09-29 t187ap03_L 實際出現的產業別代碼
LISTED_INDUSTRY_CODES = ["01", "02", "03", "04", "05", "06", "08", "09", "10", "11", "12",
                         "14", "15", "16", "17", "18", "20", "21", "22", "23", "24", "25",
                         "26", "27", "28", "29", "30", "31", "35", "36", "37", "38", "91"]


def load_fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as handle:
        return json.load(handle)


class ParseFixtureTest(unittest.TestCase):
    def setUp(self):
        self.market = fetch_market.parse_mi_index(load_fixture("mi_index_20260929.json"))
        self.turnovers = fetch_market.parse_bfiamu(load_fixture("bfiamu_20260929.json"))

    def test_market_fields(self):
        self.assertEqual(self.market["advances"], 374)
        self.assertEqual(self.market["declines"], 586)
        self.assertEqual(self.market["taiex"], 47631.96)
        self.assertEqual(self.market["turnover"], 769588137154)

    def test_every_listed_code_maps_in_both_sources(self):
        for code in LISTED_INDUSTRY_CODES:
            if code in sectors.UNMAPPED_CODES:
                continue
            self.assertIn(code, self.market["index_closes"], "MI_INDEX 缺 %s" % code)
            self.assertIn(code, self.turnovers, "BFIAMU 缺 %s" % code)

    def test_parent_indices_excluded(self):
        mapped_names = set(sectors.MI_INDEX_TO_CODE) | set(sectors.BFIAMU_TO_CODE)
        self.assertFalse(mapped_names & sectors.PARENT_INDEX_NAMES)
        self.assertEqual(len(self.turnovers), len(sectors.INDUSTRIES))

    def test_sector_turnover_does_not_exceed_market(self):
        # 母類股若混入會重複計算，加總就會超過大盤
        self.assertLessEqual(sum(self.turnovers.values()), self.market["turnover"])


class MarketContextTest(unittest.TestCase):
    def make_rows(self, count, last_turnover=100.0, advances=60, declines=40):
        rows = [{"date": "d%02d" % i, "turnover": 100.0, "advances": advances,
                 "declines": declines} for i in range(count)]
        rows[-1]["turnover"] = last_turnover
        return rows

    def test_insufficient_data_is_null(self):
        output = rotation.compute_market_context(self.make_rows(19))
        self.assertTrue(all(r["market_state"] is None for r in output))
        self.assertIsNone(output[-1]["turnover_ratio"])

    def test_strong_market(self):
        last = rotation.compute_market_context(self.make_rows(20, last_turnover=150.0))[-1]
        self.assertAlmostEqual(last["turnover_ratio"], 150.0 / (19 * 100 + 150) * 20)
        self.assertEqual(last["market_state"], "充足")

    def test_weak_breadth_dominates(self):
        rows = self.make_rows(20, last_turnover=150.0, advances=30, declines=70)
        self.assertEqual(rotation.compute_market_context(rows)[-1]["market_state"], "不足")

    def test_zero_advance_decline_day_gives_null_breadth(self):
        rows = self.make_rows(20)
        rows[-1]["advances"] = rows[-1]["declines"] = 0
        self.assertIsNone(rotation.compute_market_context(rows)[-1]["breadth_5d"])


class SectorSeriesTest(unittest.TestCase):
    def test_outperforming_sector_is_leading(self):
        days = 30
        taiex = [100.0] * days
        closes = [100.0 * (1.01 ** i) for i in range(days)]      # 持續跑贏大盤且加速
        turnovers = [10.0] * 20 + [20.0] * 10                     # 近期成交比重上升
        output = rotation.compute_sector_series(closes, turnovers, taiex, [100.0] * days)
        self.assertEqual(output[-1]["quadrant"], "Leading")
        self.assertGreater(output[-1]["share_delta"], 0)

    def test_underperforming_sector_is_lagging(self):
        days = 30
        closes = [100.0 * (0.99 ** i) for i in range(days)]
        output = rotation.compute_sector_series(closes, [10.0] * days, [100.0] * days,
                                                [100.0] * days)
        self.assertEqual(output[-1]["quadrant"], "Lagging")
        self.assertAlmostEqual(output[-1]["share_delta"], 0.0)

    def test_insufficient_or_missing_data_is_null(self):
        short = rotation.compute_sector_series([100.0] * 24, [1.0] * 24, [100.0] * 24,
                                               [10.0] * 24)
        self.assertIsNone(short[-1]["quadrant"])          # 需 20 + 5 天才有動能
        self.assertIsNotNone(short[-1]["rs_ratio"])
        closes = [100.0] * 30
        closes[-3] = None                                # 缺一天 → 含該天的窗口全 NULL
        gap = rotation.compute_sector_series(closes, [1.0] * 30, [100.0] * 30, [10.0] * 30)
        self.assertIsNone(gap[-1]["rs_ratio"])
        self.assertIsNone(gap[-1]["quadrant"])


class DatabaseFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = schema.connect(os.path.join(self.tmp.name, "test.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def seed(self, days):
        start = date(2026, 8, 1)
        for i in range(days):
            day = (start + timedelta(days=i)).isoformat()
            self.conn.execute("INSERT INTO market_daily VALUES (?, 1000, 60, 40, 100)", (day,))
            self.conn.execute("INSERT INTO sector_daily VALUES (?, '24', ?, 100)",
                              (day, 100 * 1.01 ** i))

    def test_rebuild_and_report(self):
        self.seed(30)
        rotation.rebuild_context(self.conn)
        context = self.conn.execute(
            "SELECT * FROM sector_context WHERE industry_code='24' ORDER BY date DESC").fetchone()
        self.assertEqual(context["quadrant"], "Leading")
        report = rotation.render_report(self.conn)
        self.assertIn("半導體", report)
        self.assertIn("大盤狀態：普通", report)

    def test_rebuild_with_insufficient_data_writes_null(self):
        self.seed(10)
        rotation.rebuild_context(self.conn)
        states = {r["market_state"] for r in self.conn.execute("SELECT * FROM market_context")}
        self.assertEqual(states, {None})

    def test_sync_days_logs_holidays_but_not_today(self):
        today = date(2026, 9, 30)                         # 週三
        holiday = date(2026, 9, 29)
        trading_days = []

        def fake_fetch(conn, day):
            if day in (today, holiday):
                return False
            trading_days.append(day)
            conn.execute("INSERT INTO rotation_fetch_log VALUES (?, 1)", (day.isoformat(),))
            return True

        with mock.patch.object(fetch_market, "fetch_day", side_effect=fake_fetch), \
                mock.patch.object(fetch_market.time, "sleep"):
            fetched, trading = fetch_market.sync_days(self.conn, 3, today=today)
        self.assertEqual(trading, 3)
        self.assertEqual(fetched, 5)
        logged = {r["date"]: r["is_trading"] for r in self.conn.execute(
            "SELECT * FROM rotation_fetch_log")}
        self.assertEqual(logged.get(holiday.isoformat()), 0)
        self.assertNotIn(today.isoformat(), logged)


if __name__ == "__main__":
    unittest.main()
