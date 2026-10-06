"""Mode routing helpers.

Kept free of MCP imports so the routing rules can be unit tested without
starting the server. The MCP tool layer uses these helpers to decide between
real mode, mock mode, and explicit failures.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import DATA_MODE_MOCK, DATA_MODE_REAL, VALID_DATA_MODES, Settings
from errors import ErrorCode, error_payload


def config_mode_error(settings: Settings) -> Optional[Dict[str, Any]]:
    """Return an error payload if ``MARKET_DATA_MODE`` is not supported."""

    if settings.data_mode not in VALID_DATA_MODES:
        return error_payload(
            ErrorCode.INVALID_DATA_MODE,
            f"unsupported MARKET_DATA_MODE: {settings.data_mode!r} "
            f"(expected one of {', '.join(VALID_DATA_MODES)})",
        )
    return None


def unimplemented_error(tool_name: str, settings: Settings) -> Optional[Dict[str, Any]]:
    """Return ``REAL_PROVIDER_NOT_IMPLEMENTED`` for tools still on mock data.

    In real mode an unimplemented tool must fail loudly instead of silently
    serving mock data. In mock mode this returns ``None`` so the caller may
    serve mock data.
    """

    if settings.data_mode == DATA_MODE_REAL:
        return error_payload(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{tool_name} is not implemented for real market data yet; "
            f"set MARKET_DATA_MODE=mock to use mock data",
        )
    if settings.data_mode == DATA_MODE_MOCK:
        return None
    return error_payload(
        ErrorCode.INVALID_DATA_MODE,
        f"unsupported MARKET_DATA_MODE: {settings.data_mode!r}",
    )
