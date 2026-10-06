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
        # 9. Real mode must not silently fall back to mock.
        result = unimplemented_error("get_market_breadth", Settings("real", None))
        self.assertIsNotNone(result)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED)

    def test_mock_mode_unimplemented_allows_mock(self):
        self.assertIsNone(unimplemented_error("get_market_breadth", Settings("mock", None)))

    def test_invalid_mode_is_reported(self):
        result = config_mode_error(Settings("weird", None))
        self.assertIsNotNone(result)
        self.assertEqual(result["error_code"], ErrorCode.INVALID_DATA_MODE)


class ServiceTokenTest(unittest.TestCase):
    def test_missing_token_fails_loudly(self):
        # 10. Missing TUSHARE_TOKEN must fail, never fall back to mock.
        service = MarketService(Settings("real", None))
        with self.assertRaises(MarketError) as ctx:
            service.get_index_performance("2026-10-08")
        self.assertEqual(ctx.exception.error_code, ErrorCode.TUSHARE_TOKEN_NOT_CONFIGURED)

    def test_invalid_date_rejected_before_provider(self):
        service = MarketService(Settings("real", "dummy-token"))
        with self.assertRaises(MarketError) as ctx:
            service.get_index_performance("2026/10/08")
        self.assertEqual(ctx.exception.error_code, ErrorCode.INVALID_DATE)


class ServerRealModeTest(unittest.TestCase):
    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in ("MARKET_DATA_MODE", "TUSHARE_TOKEN")}
        os.environ["MARKET_DATA_MODE"] = "real"
        os.environ.pop("TUSHARE_TOKEN", None)
        import server  # noqa: F401

        self.server = importlib.reload(server)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(self.server)

    def test_implemented_tools_require_token(self):
        for result in (
            self.server.get_index_performance("2026-10-08"),
            self.server.get_stock_detail("2026-10-08", "600519.SH"),
            self.server.get_market_history_summary("2026-10-08"),
        ):
            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], ErrorCode.TUSHARE_TOKEN_NOT_CONFIGURED)

    def test_unimplemented_tools_do_not_fallback_to_mock(self):
        for result in (
            self.server.get_market_breadth("2026-10-08"),
            self.server.get_sector_ranking("2026-10-08"),
            self.server.get_sector_detail("2026-10-08", "半导体"),
            self.server.get_stock_news("2026-10-08", "688981.SH"),
        ):
            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED)


class ServerMockModeTest(unittest.TestCase):
    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in ("MARKET_DATA_MODE", "TUSHARE_TOKEN")}
        os.environ["MARKET_DATA_MODE"] = "mock"
        import server  # noqa: F401

        self.server = importlib.reload(server)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(self.server)

    def test_mock_mode_still_works(self):
        result = self.server.get_index_performance("2026-10-08")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["indices"]), 3)

    def test_mock_mode_unimplemented_tool_uses_mock(self):
        result = self.server.get_market_breadth("2026-10-08")
        self.assertTrue(result["success"])
        self.assertIn("limit_state", result)


if __name__ == "__main__":
    unittest.main()
