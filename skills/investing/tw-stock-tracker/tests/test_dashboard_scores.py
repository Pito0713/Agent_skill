"""評分快照資料、頁面整合與 SVG 的離線測試。"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock
from xml.etree import ElementTree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import dashboard
import dashboard_data
import dashboard_scores
import db


class DashboardScoresTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = os.path.join(temporary.name, 'tracker.db')
        environment = mock.patch.dict(os.environ, {"STOCK_TRACKER_DB": path})
        environment.start()
        self.addCleanup(environment.stop)
        logs = mock.patch.object(dashboard_data, 'schedule_status', return_value=[])
        logs.start()
        self.addCleanup(logs.stop)
        self.connection = db.connect(path)
        self.addCleanup(self.connection.close)
        self.connection.execute("INSERT INTO detail_views VALUES ('2330', '2026-01-01', '[]')")
        self.connection.execute("INSERT INTO stock_names VALUES ('2330', '<script>alert(1)</script>',"
                                " 'TWSE', '2026-01-01')")
        self.connection.commit()

    def insert_scores(self, ticker, scores):
        self.connection.executemany(
            "INSERT INTO daily_scores (ticker, date, score, s_trend, s_bias, s_support,"
            " s_volume, s_macd, s_rsi, signal, source, computed_at)"
            " VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, '', ?, '2026-10-01')",
            [(ticker, (date(2026, 1, 1) + timedelta(days=index * 3)).isoformat(), value,
              "live" if index % 2 else "backfill") for index, value in enumerate(scores)])
        self.connection.commit()

    def assert_disclaimer(self, page):
        self.assertIn("未驗證", page)
        self.assertNotIn("買入", page)
        self.assertNotIn("賣出", page)

    def test_missing_table_and_pages(self):
        self.connection.execute("DROP TABLE daily_scores")
        self.connection.commit()
        self.assertEqual(dashboard_data.score_rankings(self.connection), [])
        self.assertEqual(dashboard_data.score_trend(self.connection, '2330'), [])
        for page in (dashboard.build_page({}), dashboard.build_detail_page('2330')):
            self.assertIn(dashboard_scores.EMPTY_MESSAGE, page)
            self.assert_disclaimer(page)

    def test_ranking_order_deltas_and_escape(self):
        self.insert_scores('2330', list(range(21)))
        self.insert_scores('2317', [90, 80])
        self.insert_scores('2454', [50, 45, 40, 35, 30, 25])
        rankings = dashboard_data.score_rankings(self.connection)
        self.assertEqual([item['ticker'] for item in rankings], ['2317', '2454', '2330'])
        self.assertEqual([(item['delta_5'], item['delta_20']) for item in rankings],
                         [(None, None), (-25, None), (5, 20)])
        page = dashboard_scores.render_rankings(rankings)
        for text in ('—', '+20', '-25', '&lt;script&gt;', '/stock/2330'):
            self.assertIn(text, page)
        self.assertNotIn('<script>', page)
        self.assert_disclaimer(page)
        self.assertIn('評分排行', dashboard.build_page({}))

    def test_sixty_points_and_source_styles(self):
        self.insert_scores('2330', list(range(70)))
        trend = dashboard_data.score_trend(self.connection, '2330')
        self.assertEqual([item['score'] for item in trend], list(range(10, 70)))
        self.assertEqual(dashboard_data.score_trend(self.connection, '9999'), [])
        page = dashboard_scores.render_trend(trend)
        svg = ElementTree.fromstring(page[page.index('<svg'):page.index('</svg>') + 6])
        markers = svg.findall('circle')
        self.assertEqual(len(markers), 60)
        self.assertEqual({point.attrib['class'] for point in markers}, {'score-live', 'score-backfill'})
        self.assertEqual({point.attrib['fill'] for point in markers}, {'currentColor', 'var(--card)'})
        self.assertTrue(all(20 <= float(point.attrib['cy']) <= 220 for point in markers))
        self.assert_disclaimer(page)
        detail = dashboard.build_detail_page('2330')
        self.assertIn('score-live', detail)
        self.assertIn('score-backfill', detail)
        self.assertNotIn('<script>', detail)

    def test_zero_and_one_point(self):
        for count in (0, 1):
            with self.subTest(count=count):
                self.insert_scores('2330', [50] * count)
                page = dashboard_scores.render_trend(dashboard_data.score_trend(self.connection, '2330'))
                self.assertNotIn('<svg', page)
                self.assertIn('至少 2 筆' if count else dashboard_scores.EMPTY_MESSAGE, page)
                self.assert_disclaimer(page)

    def test_ranking_links_only_tickers_with_detail_page(self):
        base = {"date": "2026-10-22", "score": 60, "delta_5": None, "delta_20": None, "name": None}
        page = dashboard_scores.render_rankings([dict(base, ticker="5425", has_detail=True),
                                                 dict(base, ticker="2330", has_detail=False)])
        self.assertIn('href="/stock/5425"', page)
        self.assertNotIn('href="/stock/2330"', page)

    def test_svg_escape_and_axis_endpoints(self):
        items = [{'date': '<script>alert(1)</script>', 'score': 0, 'source': '<script>'},
                 {'date': '2026-01-02', 'score': 100, 'source': 'live'}]
        page = dashboard_scores.render_trend(items)
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('cy="220.00"', page)
        self.assertIn('cy="20.00"', page)
