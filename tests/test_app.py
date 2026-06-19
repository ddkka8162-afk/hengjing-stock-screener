import tempfile
import unittest
from pathlib import Path

from stock_screener.providers import DemoMarketDataProvider
from stock_screener.repository import StockRepository
from stock_screener.screening import ScreenQuery, parse_screen_query
from stock_screener.crypto import CryptoMarketProvider


class ScreenerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = StockRepository(Path(self.temp.name) / "test.db")
        self.repo.initialize()
        provider = DemoMarketDataProvider()
        self.repo.replace_all(provider.load_snapshot())
        self.repo.replace_concepts(provider.load_concepts())

    def tearDown(self):
        self.temp.cleanup()

    def test_seed_and_sort(self):
        rows, total = self.repo.screen(ScreenQuery(page_size=10))
        self.assertEqual(total, 40)
        self.assertEqual(len(rows), 10)
        self.assertGreaterEqual(rows[0].score, rows[-1].score)

    def test_filters_are_combined(self):
        rows, total = self.repo.screen(ScreenQuery(min_roe=15, max_pe=30, page_size=100))
        self.assertEqual(total, len(rows))
        self.assertTrue(all(row.roe_ttm >= 15 and row.pe_ttm <= 30 for row in rows))

    def test_query_rejects_unknown_sort(self):
        with self.assertRaises(ValueError):
            parse_screen_query({"sort": ["score; DROP TABLE stocks"]})

    def test_page_size_is_capped(self):
        query = parse_screen_query({"page_size": ["99999"]})
        self.assertEqual(query.page_size, 100)

    def test_market_overview_has_chart_series(self):
        indexes = DemoMarketDataProvider().load_index_overview()
        self.assertEqual(len(indexes), 3)
        self.assertTrue(all(len(index["points"]) == 61 for index in indexes))
        self.assertTrue(all(index["value"] > 0 for index in indexes))

    def test_sectors_are_ranked_by_heat(self):
        sectors = self.repo.metadata()["sectors"]
        self.assertGreater(len(sectors), 5)
        self.assertTrue(all(sectors[i]["heat"] >= sectors[i + 1]["heat"] for i in range(len(sectors) - 1)))
        self.assertEqual(sum(1 for sector in sectors if sector["is_hot"]), 6)

    def test_stocks_can_be_ranked_by_heat(self):
        rows, _ = self.repo.screen(ScreenQuery(sort="heat_score", page_size=40))
        self.assertTrue(all(rows[i].heat_score >= rows[i + 1].heat_score for i in range(len(rows) - 1)))
        self.assertGreater(rows[0].heat_score, 0)

    def test_concept_and_industry_rankings_are_descending(self):
        rankings = self.repo.sector_rankings()
        self.assertGreater(len(rankings["concepts"]), 5)
        self.assertGreater(len(rankings["industries"]), 5)
        for key in ("concepts", "industries"):
            values = [item["change_pct"] for item in rankings[key]]
            self.assertEqual(values, sorted(values, reverse=True))

    def test_watchlist_is_sorted_by_change(self):
        codes = [stock.code for stock in DemoMarketDataProvider().load_snapshot()[:8]]
        rows = self.repo.get_by_codes(codes)
        self.assertEqual(len(rows), 8)
        self.assertEqual(
            [row.change_pct for row in rows],
            sorted((row.change_pct for row in rows), reverse=True),
        )

    def test_crypto_demo_fallback_is_explicit(self):
        payload = CryptoMarketProvider()._demo_payload("test")
        self.assertEqual(payload["data_mode"], "demo")
        self.assertEqual(len(payload["items"]), 12)
        self.assertTrue(all(len(item["sparkline"]) == 168 for item in payload["items"]))

    def test_crypto_history_fallback_supports_intervals(self):
        provider = CryptoMarketProvider()
        for interval in ("5m", "15m", "1h", "4h", "1d", "1w"):
            payload = provider._demo_history("bitcoin", interval, "test")
            self.assertEqual(payload["interval"], interval)
            self.assertEqual(len(payload["points"]), 120)
        with self.assertRaises(ValueError):
            provider.get_history("bitcoin", "2m")


if __name__ == "__main__":
    unittest.main()

