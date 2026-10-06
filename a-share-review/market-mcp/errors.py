"""Error codes and the error payload helper for the Market MCP.

Error payloads never contain tokens, secrets, or other sensitive provider
details. Only the error type name of an underlying exception is surfaced.
"""

from __future__ import annotations

from typing import Any, Dict


class ErrorCode:
    TUSHARE_TOKEN_NOT_CONFIGURED = "TUSHARE_TOKEN_NOT_CONFIGURED"
    INVALID_DATE = "INVALID_DATE"
    NOT_TRADING_DAY = "NOT_TRADING_DAY"
    DATA_NOT_AVAILABLE = "DATA_NOT_AVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    REAL_PROVIDER_NOT_IMPLEMENTED = "REAL_PROVIDER_NOT_IMPLEMENTED"
    INVALID_DATA_MODE = "INVALID_DATA_MODE"
    INVALID_STOCK_CODE = "INVALID_STOCK_CODE"
    NETWORK_ERROR = "NETWORK_ERROR"
    UPSTREAM_SCHEMA_CHANGED = "UPSTREAM_SCHEMA_CHANGED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNSUPPORTED_METRIC = "UNSUPPORTED_METRIC"
    INVALID_WINDOW = "INVALID_WINDOW"
    MOCK_NOT_SUPPORTED = "MOCK_NOT_SUPPORTED"


class MarketError(Exception):
    """Domain error carrying a stable machine-readable ``error_code``."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def error_payload(error_code: str, message: str, **context: Any) -> Dict[str, Any]:
    """Build the ``success=false`` payload returned by every tool."""

    payload: Dict[str, Any] = {
        "success": False,
        "error_code": error_code,
        "error": message,
    }
    for key, value in context.items():
        payload[key] = value
    return payload
