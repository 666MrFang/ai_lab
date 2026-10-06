"""Runtime configuration for the A-Share Market MCP server.

Only two environment variables are read:

- ``MARKET_DATA_MODE``: ``real`` (default) or ``mock``.
- ``TUSHARE_TOKEN``: token for the Tushare Pro provider (real mode only).

The token is never logged, never written to disk, and never returned in tool
output. Missing token is a hard failure (``TUSHARE_TOKEN_NOT_CONFIGURED``);
there is no silent fallback to mock data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

DATA_MODE_REAL = "real"
DATA_MODE_MOCK = "mock"
VALID_DATA_MODES = (DATA_MODE_REAL, DATA_MODE_MOCK)
DEFAULT_DATA_MODE = DATA_MODE_REAL


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings."""

    data_mode: str
    tushare_token: Optional[str]


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Load settings from the environment (or a provided mapping)."""

    source = os.environ if env is None else env
    mode = _clean(source.get("MARKET_DATA_MODE")) or DEFAULT_DATA_MODE
    token = _clean(source.get("TUSHARE_TOKEN"))
    return Settings(data_mode=mode.lower(), tushare_token=token)
