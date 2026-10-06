"""Routing / service / server-mode tests (no network)."""

import importlib
import os
import sys
import unittest
from pathlib import Path

MARKET_MCP_DIR = Path(__file__).resolve().parent.parent
if str(MARKET_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MARKET_MCP_DIR))

from config import Settings  # noqa: E402
from errors import ErrorCode, MarketError  # noqa: E402
from routing import config_mode_error, unimplemented_error  # noqa: E402
from service import MarketService  # noqa: E402


class RoutingTest(unittest.TestCase):
    def test_real_mode_unimplemented_returns_error(self):
        # Real mode must not silently fall back to mock.
        result = unimplemented_error("get_market_breadth", Settings("real"))
        self.assertIsNotNone(result)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED)

    def test_mock_mode_unimplemented_allows_mock(self):
        self.assertIsNone(unimplemented_error("get_market_breadth", Settings("mock")))

    def test_invalid_mode_is_reported(self):
        result = config_mode_error(Settings("weird"))
        self.assertIsNotNone(result)
        self.assertEqual(result["error_code"], ErrorCode.INVALID_DATA_MODE)


class ServiceProviderTest(unittest.TestCase):
    def test_invalid_date_rejected_before_provider(self):
        # Real mode needs no token; date validation still happens first.
        service = MarketService(Settings("real"))
        with self.assertRaises(MarketError) as ctx:
            service.get_index_performance("2026/10/08")
        self.assertEqual(ctx.exception.error_code, ErrorCode.INVALID_DATE)

    def test_injected_provider_is_used(self):
        class FakeProvider:
            def get_index_performance(self, date, index_codes):
                return ["sentinel"]

        service = MarketService(Settings("real"), provider=FakeProvider())
        self.assertEqual(service.get_index_performance("2026-10-08"), ["sentinel"])


class ServerRealModeTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MARKET_DATA_MODE")
        os.environ["MARKET_DATA_MODE"] = "real"
        import server  # noqa: F401

        self.server = importlib.reload(server)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MARKET_DATA_MODE", None)
        else:
            os.environ["MARKET_DATA_MODE"] = self._saved
        importlib.reload(self.server)

    def test_implemented_tools_validate_date_without_network(self):
        # Real mode validates the date before touching any provider/network.
        for result in (
            self.server.get_index_performance("2026/10/08"),
            self.server.get_stock_detail("2026/10/08", "600519.SH"),
            self.server.get_market_history_summary("2026/10/08"),
            self.server.get_market_breadth("2026/10/08"),
            self.server.get_market_metric_baseline("2026/10/08", "limit_up_count", 5),
            self.server.get_sector_ranking("2026/10/08"),
            self.server.get_sector_history_summary("2026/10/08", "半导体"),
            self.server.get_sector_detail("2026/10/08", "半导体"),
        ):
            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], ErrorCode.INVALID_DATE)

    def test_unimplemented_tools_do_not_fallback_to_mock(self):
        for result in (self.server.get_stock_news("2026-10-08", "688981.SH"),):
            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED)


class ServerMockModeTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MARKET_DATA_MODE")
        os.environ["MARKET_DATA_MODE"] = "mock"
        import server  # noqa: F401

        self.server = importlib.reload(server)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MARKET_DATA_MODE", None)
        else:
            os.environ["MARKET_DATA_MODE"] = self._saved
        importlib.reload(self.server)

    def test_mock_mode_still_works(self):
        result = self.server.get_index_performance("2026-10-08")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["indices"]), 3)

    def test_mock_mode_unimplemented_tool_uses_mock(self):
        result = self.server.get_market_breadth("2026-10-08")
        self.assertTrue(result["success"])
        self.assertIn("limit_state", result)

    def test_mock_mode_baseline_is_not_supported(self):
        result = self.server.get_market_metric_baseline("2026-10-08", "limit_up_count", 5)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], ErrorCode.MOCK_NOT_SUPPORTED)


if __name__ == "__main__":
    unittest.main()
