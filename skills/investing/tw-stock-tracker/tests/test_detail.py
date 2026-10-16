"""個股詳情的離線測試：月營收／財報／法說會／新聞解析、詳情計算、儀表板詳情頁。不打網路、不碰正式 DB。"""

import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import dashboard  # noqa: E402
import dashboard_detail  # noqa: E402
import db  # noqa: E402
import detail  # noqa: E402
import fetch_events  # noqa: E402
import fetch_fundamentals  # noqa: E402

EVIL = "<script>alert(1)</script>"
REVENUE_API = [{"資料年月": "11509", "公司代號": "2330", "營業收入-當月營收": "511857399",
                "營業收入-上月營收": "514805337", "營業收入-去年當月營收": "330980920",
                "累計營業收入-當月累計營收": "3898726974", "累計營業收入-去年累計營收": "2762963851",
                "備註": "因先進製程產品需求增加所致。"},
               {"資料年月": "11509", "公司代號": "9999", "營業收入-當月營收": "", "備註": "-"}]
HTML_ROW = ("<tr align=right><td align=center>%s</td><td align=left>名稱</td><td nowrap> 1,100</td>"
            "<td nowrap> 1,000</td><td nowrap> 1,000</td><td nowrap> 10.00</td><Td nowrap> 10.00</td>"
            "<td nowrap> 5,000</td><td nowrap> 4,000</td><td nowrap> 25.00</td><td align=center>-</td></tr>")
HTML_TOTAL = "<tr align=right><td colspan=2>合計</td><td>9</td></tr>"
HTML_TITLE = "<b>上市公司115年9月份(累計與當月)營業收入統計表</b>"
CONFERENCE_ROW = (
    "<tr class='even' data-type='body' ><td style='text-align:left !important;'>2330</td><td>台積電</td>"
    "<td align='center'>115/03/03 至 115/03/06</td><td align='center'>00:30</td><td>Palace Hotel</td>"
    "<td>公布 2026 年第 1 季業績展望 &amp; 說明</td>"
    "<td><a href='#' onclick='document.fm_fileDownload.fileName.value=\"233020260115M001.pdf\";'>x</a></td>"
    "<td>&nbsp;</td><td><a href='https://investor.tsmc.com/q4' target='_blink'>x</a></td><td></td>"
    "<td>無。</td><td><input type='button'></td></tr>")
RSS = """<?xml version="1.0" encoding="UTF-8"?><rss><channel>
<item><title>新的</title><link>https://news.example/1</link><pubDate>Tue, 13 Oct 2026 08:00:00 GMT</pubDate>
<source url="x">來源甲</source></item>
<item><title>舊的</title><link>https://news.example/2</link><pubDate>Tue, 01 Jul 2026 08:00:00 GMT</pubDate></item>
<item><title>較早</title><link>https://news.example/3</link><pubDate>Mon, 12 Oct 2026 08:00:00 GMT</pubDate></item>
<item><title>超過兩週</title><link>https://news.example/4</link><pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate></item>
</channel></rss>"""


class FundamentalsParseTest(unittest.TestCase):
    def test_revenue_api_rows_and_blank_revenue_skipped(self):
        rows = fetch_fundamentals.parse_revenue_api(REVENUE_API)
        self.assertEqual(rows, [("2330", "2026-09", 511857399, 514805337, 330980920, 3898726974, 2762963851,
                                 "因先進製程產品需求增加所致。")])

    def test_revenue_api_format_change_raises(self):
        with self.assertRaises(RuntimeError):
            fetch_fundamentals.parse_revenue_api([{"code": "2330"}])

    def test_revenue_html_handles_uppercase_td_and_skips_totals(self):
        rows = fetch_fundamentals.parse_revenue_html(HTML_TITLE + HTML_ROW % "2330" + HTML_TOTAL, "2026-08")
        self.assertEqual(rows, [("2330", "2026-08", 1100, 1000, 1000, 5000, 4000, None)])

    def test_revenue_html_cell_count_change_raises(self):
        with self.assertRaises(RuntimeError):
            fetch_fundamentals.parse_revenue_html(
                HTML_TITLE + (HTML_ROW % "2330").replace("<Td nowrap> 10.00</td>", ""), "2026-08")

    def test_revenue_maintenance_page_raises_instead_of_empty_month(self):
        with self.assertRaises(RuntimeError):
            fetch_fundamentals.parse_revenue_html("<html>系統維護中</html>", "2026-08")

    def test_eps_both_markets_and_missing_operating_income(self):
        twse = [{"年度": "115", "季別": "2", "公司代號": "2881", "基本每股盈餘(元)": "6.67", "營業收入": "172468262.00",
                 "營業利益": "--", "營業外收入及支出": "--", "稅後淨利": "97780594.00", "出表日期": "1151014"}]
        tpex = [{"Year": "115", "季別": "2", "SecuritiesCompanyCode": "5425", "基本每股盈餘": "1.52",
                 "營業收入": "9470509.00", "營業利益": "851083.00", "營業外收入及支出": "28438.00",
                 "稅後淨利": "668256.00", "Date": "1151014"}]
        self.assertEqual(fetch_fundamentals.parse_eps_api(twse, "TWSE"),
                         [("2881", 2026, 2, 6.67, 172468262, None, None, 97780594, "2026-10-14")])
        self.assertEqual(fetch_fundamentals.parse_eps_api(tpex, "TPEx")[0][:4], ("5425", 2026, 2, 1.52))

    def test_recent_months_excludes_current_month_and_wraps_year(self):
        self.assertEqual(fetch_fundamentals.recent_months(3, date(2026, 2, 5)), ["2025-11", "2025-12", "2026-01"])


class RevenueBackfillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _backfill(self, months, today, page):
        with mock.patch.object(fetch_fundamentals, "get_text", return_value=page) as getter, \
                mock.patch.object(fetch_fundamentals.time, "sleep"):
            fetch_fundamentals.backfill(self.conn, months, today)
        return getter.call_count

    def test_month_marked_done_only_after_deadline(self):
        page = HTML_TITLE + HTML_ROW % "2330"
        # 兩個市場 × 國內／國外兩頁
        self.assertEqual(self._backfill(["2026-09"], date(2026, 10, 14), page), 4)
        self.assertEqual(self._backfill(["2026-09"], date(2026, 10, 14), page), 4)  # 未過期限，重抓
        self._backfill(["2026-09"], date(2026, 10, 15), page)
        self.assertEqual(self._backfill(["2026-09"], date(2026, 10, 20), page), 0)

    def test_foreign_company_page_is_fetched(self):
        pages = {0: HTML_TITLE + HTML_ROW % "2330", 1: HTML_TITLE + HTML_ROW % "4958"}
        with mock.patch.object(fetch_fundamentals, "get_text",
                               side_effect=lambda url, encoding: pages[int(url[-6])]), \
                mock.patch.object(fetch_fundamentals.time, "sleep"):
            fetch_fundamentals.backfill(self.conn, ["2026-08"], date(2026, 10, 1))
        tickers = {r[0] for r in self.conn.execute("SELECT ticker FROM monthly_revenue")}
        self.assertEqual(tickers, {"2330", "4958"})

    def test_month_with_missing_foreign_page_is_not_marked_done(self):
        pages = {0: HTML_TITLE + HTML_ROW % "2330", 1: None}
        with mock.patch.object(fetch_fundamentals, "get_text",
                               side_effect=lambda url, encoding: pages[int(url[-6])]), \
                mock.patch.object(fetch_fundamentals.time, "sleep"):
            fetch_fundamentals.backfill(self.conn, ["2026-08"], date(2026, 10, 1))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM revenue_fetches").fetchone())

    def test_html_refetch_updates_corrected_html_row(self):
        self._backfill(["2026-09"], date(2026, 10, 1), HTML_TITLE + HTML_ROW % "2330")
        corrected = HTML_TITLE + (HTML_ROW % "2330").replace(" 1,100</td>", " 1,500</td>", 1)
        self._backfill(["2026-09"], date(2026, 10, 2), corrected)
        self.assertEqual(self.conn.execute("SELECT revenue FROM monthly_revenue").fetchone()[0], 1500)

    def test_unpublished_month_404_is_not_recorded(self):
        self._backfill(["2026-09"], date(2026, 11, 1), None)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM revenue_fetches").fetchone())

    def test_html_does_not_overwrite_openapi_row(self):
        fetch_fundamentals.save_revenue(self.conn, [("2330", "2026-08", 7, None, None, None, None, None)], "OPENAPI")
        self._backfill(["2026-08"], date(2026, 10, 1), HTML_TITLE + HTML_ROW % "2330")
        row = self.conn.execute("SELECT revenue, source FROM monthly_revenue WHERE ticker = '2330'").fetchone()
        self.assertEqual(tuple(row), (7, "OPENAPI"))


class EventsParseTest(unittest.TestCase):
    def test_conference_row(self):
        [conference] = fetch_events.parse_conferences("<table id='myTable'>%s</table>" % CONFERENCE_ROW, "2330")
        self.assertEqual((conference["date"], conference["end_date"], conference["time"]),
                         ("2026-03-03", "2026-03-06", "00:30"))
        self.assertEqual(conference["summary"], "公布 2026 年第 1 季業績展望 & 說明")
        self.assertEqual(conference["slides_zh"], "https://mopsov.twse.com.tw/nas/STR/233020260115M001.pdf")
        self.assertIsNone(conference["slides_en"])
        self.assertEqual(conference["website"], "https://investor.tsmc.com/q4")

    def test_conference_no_data_and_format_change(self):
        self.assertEqual(fetch_events.parse_conferences("<p>查無資料</p>", "2330"), [])
        with self.assertRaises(RuntimeError):
            fetch_events.parse_conferences("<html>系統維護中</html>", "2330")
        broken = CONFERENCE_ROW.replace("<td>無。</td>", "")
        with self.assertRaises(RuntimeError):
            fetch_events.parse_conferences("<table id='myTable'>%s</table>" % broken, "2330")

    def test_news_filters_old_and_sorts_newest_first(self):
        now = datetime(2026, 10, 14, tzinfo=timezone.utc)
        items = fetch_events.parse_news(RSS, now=now)
        self.assertEqual([i["title"] for i in items], ["新的", "較早"])
        self.assertEqual((items[0]["source"], items[0]["published"]), ("來源甲", "2026-10-13 16:00"))

    def test_bad_rss_raises(self):
        with self.assertRaises(RuntimeError):
            fetch_events.parse_news("<rss><channel>")

    def test_rss_with_entity_declarations_is_rejected(self):
        bomb = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel></channel></rss>'
        with self.assertRaises(RuntimeError):
            fetch_events.parse_news(bomb)


def seed_detail(conn):
    days = ["2026-09-%02d" % d for d in range(1, 31)] + ["2026-10-%02d" % d for d in range(1, 31)]
    conn.executemany("INSERT INTO daily_quotes (ticker, date, open, high, low, close, volume, is_exdiv, adj_close)"
                     " VALUES ('2330', ?, ?, ?, ?, ?, 1000, 0, ?)",
                     [(d, 100 + i, 101 + i, 99 + i, 100 + i, 100 + i) for i, d in enumerate(days)])
    conn.executemany("INSERT INTO monthly_revenue VALUES ('2330', ?, ?, ?, ?, ?, ?, ?, 'OPENAPI')",
                     [("2026-08", 900, 800, 1000, 5000, 4000, None), ("2026-09", 1100, 900, 1000, 6100, 5000, EVIL)])
    conn.executemany("INSERT INTO quarterly_financials VALUES ('2330', ?, ?, ?, 1000, 400, 0, 300, '2026-10-14', 'x')",
                     [(2026, 1, 20.0), (2026, 2, 49.33), (2025, 2, 30.0)])
    conn.execute("INSERT INTO investor_conferences VALUES ('2330', '2026-10-01', NULL, '14:00', 'x', ?, ?, NULL,"
                 " 'javascript:alert(1)', '2026-10-14')", (EVIL, "https://mopsov.twse.com.tw/nas/STR/a.pdf"))
    conn.commit()
    return days


class DetailBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tracker.db")
        self.conn = db.connect(self.path)
        self.days = seed_detail(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _build(self, **kwargs):
        return detail.build(self.conn, "2330", today=date(2026, 10, 14), **kwargs)

    def test_revenue_growth_and_single_quarter_eps(self):
        result = self._build(include_news=False)
        self.assertEqual(result["revenue"]["latest"]["yoy_pct"], 10.0)
        self.assertEqual(result["revenue"]["latest"]["mom_pct"], 22.22)
        self.assertEqual(result["revenue"]["latest"]["cum_yoy_pct"], 22.0)
        self.assertEqual([h["month"] for h in result["revenue"]["history"]], ["2026-08", "2026-09"])
        financials = result["financials"]
        self.assertEqual((financials["period"], financials["eps_quarter_approx"]), ("2026Q2", 29.33))
        self.assertEqual(financials["eps_cumulative_last_year"], 30.0)
        self.assertEqual((financials["operating_margin_pct"], financials["net_margin_pct"]), (40.0, 30.0))

    def test_price_returns_and_flows_without_coverage(self):
        result = self._build(include_news=False)
        self.assertEqual(result["price"]["returns_pct"]["1d"], round((159 / 158 - 1) * 100, 2))
        self.assertEqual(result["flows_lots"], {"5d": None, "20d": None})
        self.assertNotIn("valuation", result["score"])

    def test_flows_sum_in_lots_when_both_markets_covered(self):
        for day in self.days[-5:]:
            self.conn.executemany("INSERT INTO flow_fetches VALUES (?, ?, 100)", [(day, "TWSE"), (day, "TPEx")])
            self.conn.execute("INSERT INTO institutional_flows VALUES ('2330', ?, 2000, -1000, 0, 1000)", (day,))
        self.assertEqual(self._build(include_news=False)["flows_lots"]["5d"],
                         {"foreign": 10.0, "trust": -5.0, "dealer": 0.0, "total": 5.0})

    def test_unknown_exdiv_hides_returns_spanning_it(self):
        self.conn.execute("UPDATE daily_quotes SET is_exdiv = 1 WHERE date = ?", (self.days[-3],))
        result = self._build(include_news=False)
        returns = result["price"]["returns_pct"]
        self.assertIsNotNone(returns["1d"])
        self.assertIsNone(returns["5d"])
        self.assertEqual(result["price"]["unknown_exdiv_dates"], [self.days[-3]])
        self.assertTrue(any(m.startswith("price") for m in result["missing"]))

    def test_valuation_shown_even_when_score_fails(self):
        self.conn.execute("DELETE FROM daily_quotes WHERE date < ?", (self.days[-10],))
        self.conn.execute("INSERT INTO valuations VALUES ('2330', ?, 20.0, 5.0, 2.0, NULL, 'BWIBBU_d')",
                          (self.days[-1],))
        result = self._build(include_news=False)
        self.assertIsNone(result["score"])
        self.assertEqual(result["valuation"]["pe"], 20.0)
        self.conn.execute("DELETE FROM daily_quotes")
        self.conn.execute("UPDATE valuations SET date = '2026-10-13'")
        self.assertEqual(self._build(include_news=False)["valuation"]["pe"], 20.0)

    def test_growth_not_given_on_negative_base(self):
        self.conn.execute("UPDATE monthly_revenue SET last_year_revenue = -500 WHERE month = '2026-09'")
        self.assertIsNone(self._build(include_news=False)["revenue"]["latest"]["yoy_pct"])

    def test_no_name_skips_news_query(self):
        with mock.patch.object(fetch_events, "fetch_news") as fetcher:
            result = detail.build(self.conn, "0050", today=date(2026, 10, 14))
        fetcher.assert_not_called()
        self.assertTrue(any(m.startswith("news") for m in result["missing"]))

    def test_refresh_records_time_and_failed_steps(self):
        self.assertIsNone(self._build(include_news=False)["refreshed"])
        with mock.patch.object(detail.fetch_twse, "sync_ticker"), \
                mock.patch.object(detail.fetch_valuation, "sync_latest", side_effect=RuntimeError("down")), \
                mock.patch.object(detail.fetch_flows, "backfill"), \
                mock.patch.object(detail.fetch_fundamentals, "sync_latest"), \
                mock.patch.object(detail.fetch_fundamentals, "backfill"), \
                mock.patch.object(detail.fetch_events, "sync_conferences"), mock.patch("sys.stderr"):
            detail.refresh(self.conn, "2330")
        refreshed = self._build(include_news=False)["refreshed"]
        self.assertEqual(refreshed["failed_steps"], ["估值"])
        self.assertEqual(refreshed["at"][:10], date.today().isoformat())

    def test_dashboard_lists_viewed_stocks_with_update_time(self):
        import dashboard_data
        import dashboard_views
        self.conn.execute("INSERT INTO detail_views VALUES ('2330', '2026-10-01 09:00', ?)", ('["%s"]' % EVIL,))
        self.conn.commit()
        [item] = dashboard_data.detail_views(self.conn)
        self.assertEqual((item["revenue_month"], item["financial_period"]), ("2026-09", "2026Q2"))
        html = dashboard_views.render_detail_views([item])
        self.assertIn('href="/stock/2330"', html)
        self.assertIn("2026-10-01 09:00", html)
        self.assertNotIn(EVIL, html)
        page = dashboard_detail.render_detail(self._build(include_news=False))
        self.assertIn("資料更新於 2026-10-01 09:00", page)

    def test_news_failure_is_reported_not_raised(self):
        self.conn.execute("INSERT INTO stock_names VALUES ('2330', '台積電', 'TWSE', '2026-10-14')")
        with mock.patch.object(fetch_events, "fetch_news", side_effect=RuntimeError("blocked")):
            result = self._build()
        self.assertIsNone(result["news"])
        self.assertIn("news：blocked", result["missing"])

    def test_etf_without_fundamentals_lists_missing(self):
        result = detail.build(self.conn, "0050", include_news=False, today=date(2026, 10, 14))
        self.assertIsNone(result["revenue"])
        self.assertTrue(any(m.startswith("financials") for m in result["missing"]))

    def test_detail_page_escapes_and_rejects_non_http_links(self):
        page = dashboard_detail.render_detail(self._build(include_news=False))
        self.assertNotIn(EVIL, page)
        self.assertNotIn("javascript:", page)
        self.assertIn("https://mopsov.twse.com.tw/nas/STR/a.pdf", page)

    def test_dashboard_serves_detail_route_and_rejects_bad_ticker(self):
        server = dashboard.ThreadingHTTPServer((dashboard.HOST, 0), dashboard.make_handler({}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            with mock.patch.dict(os.environ, {"STOCK_TRACKER_DB": self.path}), mock.patch("sys.stderr"):
                with self.assertRaises(urllib.error.HTTPError) as caught:   # 沒跑過 --fetch 的沒有詳情頁
                    urllib.request.urlopen(base + "/stock/2330")
                self.assertEqual(caught.exception.code, 404)
                self.conn.execute("INSERT INTO detail_views VALUES ('2330', '2026-10-14 09:00', '[]')")
                self.conn.commit()
                with urllib.request.urlopen(base + "/stock/2330") as response:
                    self.assertIn("月營收", response.read().decode("utf-8"))
                for bad in ("/stock/../etc", "/stock/%3Cx%3E", "/stock/"):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(base + bad)
                    self.assertEqual(caught.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
