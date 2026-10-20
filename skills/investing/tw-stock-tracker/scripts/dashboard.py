"""本機唯讀儀表板：python3 dashboard.py [--port 8765]，瀏覽器開 http://127.0.0.1:8765

只綁 127.0.0.1（同網路其他裝置連不到個人交易紀錄）、只開唯讀 DB、只回應 GET。
每次重新整理都以最新資料重算；回測摘要依 run id 快取（跑完的 run 不會再變）。
"""

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dashboard_data
import dashboard_detail
import dashboard_views
from fetch_twse import TICKER_PATTERN

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
ALLOWED_HOSTNAMES = ("127.0.0.1", "localhost")
HEALTH_PATH = "/healthz"
HEALTH_MARKER = b"tw-stock-tracker-dashboard"   # open_dashboard.py 用來確認埠上是這個儀表板
STOCK_PREFIX = "/stock/"


def build_page(backtest_cache):
    conn = dashboard_data.connect_readonly()
    try:
        data = {"positions": dashboard_data.open_positions(conn),
                "closed_positions": dashboard_data.closed_positions(conn),
                "detail_views": dashboard_data.detail_views(conn),
                "predictions": dashboard_data.open_predictions(conn),
                "resolved": dashboard_data.resolved_summary(conn),
                "backtests": dashboard_data.backtest_runs(conn, backtest_cache),
                "schedule": dashboard_data.schedule_status(),
                "freshness": dashboard_data.freshness(conn)}
    finally:
        conn.close()
    return dashboard_views.render_page(data)


def build_detail_page(ticker):
    conn = dashboard_data.connect_readonly()
    try:
        return dashboard_detail.render_detail(dashboard_data.stock_detail(conn, ticker))
    finally:
        conn.close()


def make_handler(backtest_cache):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — http.server 規定的方法名
            # 擋 DNS rebinding：惡意網域解析到 127.0.0.1 時，瀏覽器送來的 Host 是那個網域
            hostname = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if hostname not in ALLOWED_HOSTNAMES:
                self.send_error(403)
                return
            if self.path == HEALTH_PATH:
                self._send(200, "text/plain; charset=utf-8", HEALTH_MARKER)
                return
            ticker = self.path[len(STOCK_PREFIX):] if self.path.startswith(STOCK_PREFIX) else None
            if ticker is not None and not TICKER_PATTERN.match(ticker):
                self.send_error(404)
                return
            if ticker is None and self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            try:
                page = build_detail_page(ticker) if ticker else build_page(backtest_cache)
                body = page.encode("utf-8")
                status = 200
            except LookupError:
                self.send_error(404)
                return
            except Exception as error:  # noqa: BLE001 — 任何錯誤都要回成頁面，不能讓伺服器掛掉
                self.log_error("render failed: %r", error)
                body = ("<!doctype html><meta charset=utf-8><p>儀表板產生失敗：%s</p>"
                        % dashboard_views.escape(str(error))).encode("utf-8")
                status = 500
            self._send(status, "text/html; charset=utf-8", body)

        def _send(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            sys.stderr.write("[dashboard] %s\n" % (fmt % args))

    return Handler


def main():
    parser = argparse.ArgumentParser(description="台股追蹤本機儀表板（唯讀）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    server = ThreadingHTTPServer((HOST, args.port), make_handler({}))
    print("儀表板：http://%s:%d （Ctrl+C 結束）" % (HOST, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
