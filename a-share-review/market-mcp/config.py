"""Runtime configuration for the A-Share Market MCP server.

Only one environment variable is read:

- ``MARKET_DATA_MODE``: ``real`` (default) or ``mock``.

The default real provider is AkShare, which requires no token. The legacy
Tushare provider is still importable and unit-tested, but it is not part of
the default real routing and is never selected from configuration; it takes
its token as a direct constructor argument if used at all.

There is no silent fallback to mock data in real mode.
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


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Load settings from the environment (or a provided mapping)."""

    source = os.environ if env is None else env
    mode = _clean(source.get("MARKET_DATA_MODE")) or DEFAULT_DATA_MODE
    return Settings(data_mode=mode.lower())
