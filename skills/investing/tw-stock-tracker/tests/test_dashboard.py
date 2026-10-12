"""本機儀表板的離線測試：唯讀、跳脫、資料計算、log 解析、伺服器只綁本機。"""

import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import dashboard  # noqa: E402
import dashboard_data  # noqa: E402
import dashboard_views  # noqa: E402
import db  # noqa: E402
import open_dashboard  # noqa: E402

EVIL = '<script>alert(1)</script>'


def seed(path):
    conn = db.connect(path)
    days, cursor = [], date.today() - timedelta(days=150)
    while len(days) < 90:
        if cursor.weekday() < 5:
            days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    conn.executemany("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume, is_exdiv, adj_close)"
                     " VALUES ('2330', ?, ?, ?, ?, ?, 1000, 0, ?)",
                     [(d, 100 + i, 101 + i, 99 + i, 100 + i, 100 + i) for i, d in enumerate(days)])
    conn.execute("INSERT INTO stock_names VALUES ('2330', ?, 'TWSE', ?)", (EVIL, days[-1]))
    conn.execute("INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred, adj_close_at_pred,"
                 " score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi, signal, thesis, status)"
                 " VALUES (?, '2330', 30, 160, 160, 60, 0, 0, 0, 0, 0, 0, '偏多', ?, 'open')", (days[60], EVIL))
    conn.commit()
    conn.close()
    return days


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tracker.db")
        self.days = seed(self.path)
        patcher = mock.patch.dict(os.environ, {"STOCK_TRACKER_DB": self.path})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_connection_is_read_only(self):
        conn = dashboard_data.connect_readonly()
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM predictions")
        conn.close()

    def test_missing_db_is_not_created(self):
        missing = os.path.join(self.tmp.name, "nope.db")
        with self.assertRaises(RuntimeError):
            dashboard_data.connect_readonly(missing)
        self.assertFalse(os.path.exists(missing))

    def test_open_prediction_due_and_unrealized_return(self):
        conn = dashboard_data.connect_readonly()
        item = dashboard_data.open_predictions(conn)[0]
        conn.close()
        due = date.fromisoformat(self.days[60]) + timedelta(days=30)
        self.assertEqual((item["due"], item["days_left"]), (due.isoformat(), (due - date.today()).days))
        self.assertAlmostEqual(item["unrealized"], (189 / 160 - 1) * 100, places=6)   # 最後一根收盤 189

    def test_unknown_exdiv_in_window_hides_unrealized_return(self):
        conn = db.connect(self.path)
        conn.execute("UPDATE daily_quotes SET is_exdiv = 1 WHERE date = ?", (self.days[70],))
        conn.commit()
        conn.close()
        conn = dashboard_data.connect_readonly()
        item = dashboard_data.open_predictions(conn)[0]
        conn.close()
        self.assertIsNone(item["unrealized"])
        self.assertIn("未還原", dashboard.build_page({}))

    def test_missing_start_quote_is_not_labelled_exdiv(self):
        conn = db.connect(self.path)
        conn.execute("DELETE FROM daily_quotes WHERE date = ?", (self.days[60],))
        conn.commit()
        conn.close()
        conn = dashboard_data.connect_readonly()
        item = dashboard_data.open_predictions(conn)[0]
        conn.close()
        self.assertEqual((item["unrealized"], item["exdiv_unknown"]), (None, False))
        self.assertNotIn("未還原", dashboard.build_page({}))

    def test_recent_resolved_ordered_by_resolve_date(self):
        conn = db.connect(self.path)
        for created, horizon, resolved in (("2026-01-05", 7, "2026-01-12"), ("2026-01-06", 90, "2026-04-06"),
                                           ("2026-01-07", 7, "2026-01-14")):
            conn.execute("INSERT INTO predictions (created_at, ticker, horizon_days, close_at_pred,"
                         " adj_close_at_pred, score, s_trend, s_bias, s_support, s_volume, s_macd, s_rsi,"
                         " signal, thesis, status, resolve_date, return_pct, hit) VALUES (?, '2330', ?, 100,"
                         " 100, 60, 0, 0, 0, 0, 0, 0, '偏多', '', 'resolved', ?, 1.0, 1)",
                         (created, horizon, resolved))
        conn.commit()
        conn.close()
        conn = dashboard_data.connect_readonly()
        recent = dashboard_data.resolved_summary(conn)["recent"]
        conn.close()
        self.assertEqual([r["resolve_date"] for r in recent], ["2026-04-06", "2026-01-14", "2026-01-12"])

    def test_page_escapes_database_strings(self):
        page = dashboard.build_page({})
        self.assertNotIn(EVIL, page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("不是選股訊號", page)
        self.assertIn("偏空&lt;45", page)              # 模板裡的「<」也要跳脫，否則後文被當成標籤吃掉

    def test_schedule_log_parsing(self):
        logs = os.path.join(self.tmp.name, "logs")
        os.makedirs(logs)
        with open(os.path.join(logs, "update-20261012.log"), "w") as handle:
            handle.write("== 2026-10-12 16:30:00 track.py reconcile\n!! 失敗：track.py reconcile\n"
                         "== 2026-10-12 16:31:00 結束 status=1\n"
                         "== 2026-10-12 16:40:00 另一個更新仍在執行，本次略過\n")
        with open(os.path.join(logs, "update-20261013.log"), "w") as handle:
            handle.write("== 2026-10-13 16:35:00 結束 status=0\n")
        result = dashboard_data.schedule_status(logs)
        self.assertEqual([r["date"] for r in result], ["20261013", "20261012"])
        self.assertEqual((result[0]["last_status"], result[1]["last_status"]), (0, 1))
        self.assertEqual((result[1]["failures"], result[1]["skips"]), (["!! 失敗：track.py reconcile"], 1))
        self.assertIn("失敗", dashboard_views.render_schedule(result))

    def test_server_binds_localhost_and_serves_get_only(self):
        self.assertEqual(dashboard.HOST, "127.0.0.1")
        server = dashboard.ThreadingHTTPServer((dashboard.HOST, 0), dashboard.make_handler({}))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            with mock.patch("sys.stderr"):
                with urllib.request.urlopen(base + "/") as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
                rebinding = urllib.request.Request(base + "/", headers={"Host": "evil.example:8765"})
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(rebinding)
                self.assertEqual(caught.exception.code, 403)
                for path, method in (("/other", "GET"), ("/", "POST")):
                    with self.assertRaises(urllib.error.HTTPError):
                        urllib.request.urlopen(urllib.request.Request(base + path, method=method, data=b""
                                                                      if method == "POST" else None))
        finally:
            server.shutdown()
            server.server_close()


class BacktestCacheTest(unittest.TestCase):
    def test_complete_run_summary_is_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(os.path.join(tmp, "tracker.db"))
            conn.execute("INSERT INTO backtest_runs (created_at, start_date, end_date, tickers, params, status)"
                         " VALUES ('2026-10-07', '2023-10-08', '2026-10-07', '[\"2330\"]', ?, 'complete')",
                         (json.dumps({"horizons": [7]}),))
            cache = {}
            first = dashboard_data.backtest_runs(conn, cache)
            with mock.patch.object(dashboard_data.backtest_report, "load_samples") as load:
                second = dashboard_data.backtest_runs(conn, cache)
            load.assert_not_called()
            self.assertEqual(first, second)
            self.assertEqual(first[0]["horizons"][0]["n"], 0)
            conn.close()



class LauncherTest(unittest.TestCase):
    def run_with(self, states, ready=True, open_code=0):
        with mock.patch.object(open_dashboard, "probe", side_effect=states), \
                mock.patch.object(open_dashboard, "start_server") as start, \
                mock.patch.object(open_dashboard, "wait_until_ready", return_value=ready), \
                mock.patch.object(open_dashboard, "notify") as notify, \
                mock.patch.object(open_dashboard.subprocess, "run") as run:
            run.return_value.returncode = open_code
            code = open_dashboard.ensure_and_open(8765)
        opened = [c for c in run.call_args_list if c.args[0][0] == "open"]
        return code, start, notify, opened

    def test_running_dashboard_is_reused(self):
        code, start, notify, opened = self.run_with(["ours"])
        self.assertEqual(code, 0)
        start.assert_not_called()
        self.assertEqual(opened[0].args[0], ["open", "http://127.0.0.1:8765/"])

    def test_down_starts_then_opens(self):
        code, start, _, opened = self.run_with(["down"])
        self.assertEqual(code, 0)
        start.assert_called_once_with(8765)
        self.assertEqual(len(opened), 1)

    def test_port_taken_by_other_program_notifies_and_does_not_open(self):
        code, start, notify, opened = self.run_with(["other"])
        self.assertEqual(code, 2)
        start.assert_not_called()
        notify.assert_called_once()
        self.assertEqual(opened, [])

    def test_startup_timeout_notifies(self):
        code, start, notify, opened = self.run_with(["down"], ready=False)
        self.assertEqual(code, 1)
        start.return_value.terminate.assert_called_once()     # 沒就緒的子程序要收掉
        notify.assert_called_once()
        self.assertEqual(opened, [])

    def test_browser_open_failure_notifies(self):
        code, _, notify, opened = self.run_with(["ours"], open_code=1)
        self.assertEqual(code, 3)
        self.assertEqual(len(opened), 1)
        notify.assert_called_once()

    def test_port_zero_rejected(self):
        with mock.patch("sys.argv", ["open_dashboard.py", "--port", "0"]), mock.patch("sys.stderr"), \
                self.assertRaises(SystemExit) as caught:
            open_dashboard.main()
        self.assertEqual(caught.exception.code, 2)

    def test_health_endpoint_returns_marker(self):
        server = dashboard.ThreadingHTTPServer((dashboard.HOST, 0), dashboard.make_handler({}))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch("sys.stderr"):
                self.assertEqual(open_dashboard.probe(server.server_address[1]), "ours")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
