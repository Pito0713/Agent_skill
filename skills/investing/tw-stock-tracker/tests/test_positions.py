"""持股紀錄的離線測試：停損固定、還原基準、未知除息不給數字、平倉驗證、儀表板呈現。"""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import dashboard  # noqa: E402
import dashboard_data  # noqa: E402
import db  # noqa: E402
import fetch_twse  # noqa: E402
import positions  # noqa: E402

EVIL = '<script>alert(1)</script>'
BAR_COUNT = 90
BUY_INDEX = 70


def trading_days(count):
    days, cursor = [], date.today() - timedelta(days=150)
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def rising_rows(days, exdiv_index=None, cash=0.0):
    """每天漲 1 元；exdiv_index 那天起原始價扣掉 cash（模擬除息）。"""
    rows = []
    for index, day in enumerate(days):
        close = 100.0 + index - (cash if exdiv_index is not None and index >= exdiv_index else 0)
        rows.append({"date": day, "open": close, "high": close + 1, "low": close - 1, "close": close,
                     "volume": 1000, "is_exdiv": 1 if index == exdiv_index else 0})
    return rows


class PositionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tracker.db")
        self.conn = db.connect(self.path)
        self.days = trading_days(BAR_COUNT)
        patcher = mock.patch.dict(os.environ, {"STOCK_TRACKER_DB": self.path})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def load(self, rows, dividend=None):
        fetch_twse.save_quotes(self.conn, "2330", rows)
        if dividend:
            self.conn.execute("INSERT INTO dividends (ticker, ex_date, cash, source) VALUES ('2330', ?, ?, 'test')",
                              dividend)
        fetch_twse.rebuild_adj_close(self.conn, "2330")
        self.conn.commit()

    def add(self, price=150.0, shares=2000, buy_index=BUY_INDEX):
        return positions.add_position(self.conn, "2330", self.days[buy_index], price, shares)

    def test_stop_loss_fixed_at_buy_date(self):
        self.load(rising_rows(self.days))
        position_id, result, stop = self.add()
        self.assertEqual(result["date"], self.days[BUY_INDEX])
        later_stop = positions.scoring.evaluate(self.conn, "2330")["stop_loss"]
        self.assertNotEqual(stop, later_stop)              # 重算會移動，測資才能證明有固定
        item = positions.open_positions(self.conn)[0]
        self.assertEqual(item["stop_loss"], stop)
        self.assertEqual(item["amount"], 300000)

    def test_buy_before_today_bar_uses_latest_bar_as_basis(self):
        self.load(rising_rows(self.days[:-1]))
        _, result, _ = positions.add_position(self.conn, "2330", self.days[-1], 180.0, 1000)
        self.assertEqual(result["date"], self.days[-2])

    def test_future_buy_date_rejected(self):
        self.load(rising_rows(self.days))
        future = (date.today() + timedelta(days=3)).isoformat()
        with self.assertRaises(RuntimeError):
            positions.add_position(self.conn, "2330", future, 100.0, 1000)

    def test_known_dividend_not_counted_as_loss_or_stop_breach(self):
        # 買進價 = 當天收盤 170；之後除息 40 元，原始價掉到比停損還低，但還原後是賺的
        self.load(rising_rows(self.days, exdiv_index=80, cash=40.0), dividend=(self.days[80], 40.0))
        _, _, stop = self.add(price=170.0)
        item = positions.open_positions(self.conn)[0]
        self.assertLess(item["now"]["close"], stop)      # 不還原就會誤判跌破
        self.assertGreater(item["return_pct"], 0)
        self.assertNotIn("收盤跌破買進時停損", item["alerts"])
        self.assertGreater(item["stop_distance_pct"], 0)

    def test_unknown_dividend_hides_pnl_and_stop_comparison(self):
        self.load(rising_rows(self.days, exdiv_index=80, cash=30.0))
        self.add(price=170.0)
        item = positions.open_positions(self.conn)[0]
        self.assertTrue(item["exdiv_unknown"])
        self.assertEqual((item["return_pct"], item["pnl"], item["stop_distance_pct"]), (None, None, None))
        self.assertIn("未還原", dashboard.build_page({}))

    def test_close_below_stop_raises_alert(self):
        rows = rising_rows(self.days)
        for row in rows[BUY_INDEX + 1:]:
            row.update(close=60.0, open=60.0, high=61.0, low=59.0)
        self.load(rows)
        self.add(price=170.0)
        item = positions.open_positions(self.conn)[0]
        self.assertIn("收盤跌破買進時停損", item["alerts"])
        self.assertLess(item["pnl"], 0)

    def test_close_position_validation(self):
        self.load(rising_rows(self.days))
        position_id, _, _ = self.add()
        with self.assertRaises(RuntimeError):
            positions.close_position(self.conn, position_id, 160.0, self.days[BUY_INDEX - 1])
        positions.close_position(self.conn, position_id, 160.0, self.days[-1])
        with self.assertRaises(RuntimeError):
            positions.close_position(self.conn, position_id, 160.0, self.days[-1])
        self.assertEqual(positions.open_positions(self.conn), [])

    def test_closed_positions_realized_pnl_newest_first(self):
        self.load(rising_rows(self.days))
        first, _, _ = self.add(price=150.0, shares=350)
        second, _, _ = self.add(price=100.0, shares=1000, buy_index=65)
        positions.close_position(self.conn, first, 140.0, self.days[80])
        positions.close_position(self.conn, second, 110.0, self.days[85])
        items = positions.closed_positions(self.conn)
        self.assertEqual([i["id"] for i in items], [second, first])
        self.assertAlmostEqual(items[1]["pnl"], -3500.0)
        self.assertAlmostEqual(items[1]["return_pct"], (140 / 150 - 1) * 100)
        self.assertFalse(items[0]["had_exdiv"])
        page = dashboard.build_page({})
        self.assertLess(page.index("我的持股"), page.index("已平倉"))
        self.assertIn("+6500", page)                      # 合計 = +10000 − 3500

    def test_closed_position_across_exdiv_marked_without_dividend(self):
        self.load(rising_rows(self.days, exdiv_index=80, cash=40.0), dividend=(self.days[80], 40.0))
        position_id, _, _ = self.add(price=170.0)
        positions.close_position(self.conn, position_id, 150.0, self.days[85])
        self.assertTrue(positions.closed_positions(self.conn)[0]["had_exdiv"])
        self.assertIn("未含股利", dashboard.build_page({}))

    def test_no_closed_positions_hides_section(self):
        self.load(rising_rows(self.days))
        self.add()
        self.assertNotIn("<h2>已平倉", dashboard.build_page({}))

    def test_dashboard_shows_positions_first_and_escapes_names(self):
        self.load(rising_rows(self.days))
        self.conn.execute("INSERT INTO stock_names VALUES ('2330', ?, 'TWSE', ?)", (EVIL, self.days[-1]))
        self.conn.commit()
        self.add()
        page = dashboard.build_page({})
        self.assertNotIn(EVIL, page)
        self.assertLess(page.index("我的持股"), page.index("預測現況"))
        self.assertIn("2 張", page)

    def test_old_db_without_positions_table_reads_empty(self):
        legacy = os.path.join(self.tmp.name, "legacy.db")
        sqlite3.connect(legacy).close()
        conn = dashboard_data.connect_readonly(legacy)
        self.assertEqual(dashboard_data.open_positions(conn), [])
        conn.close()


if __name__ == "__main__":
    unittest.main()
