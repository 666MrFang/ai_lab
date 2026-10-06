"""Stock / index code normalization.

Canonical form is ``XXXXXX.SH`` / ``XXXXXX.SZ`` / ``XXXXXX.BJ``. Exchange is
never inferred from the numeric prefix here; when an exchange suffix is absent
the caller must resolve it through the provider security master.
"""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"^(\d{6})(?:\.([A-Za-z]{2}))?$")
VALID_EXCHANGES = ("SH", "SZ", "BJ")


def normalize_code_parts(code: object) -> tuple[str, str | None]:
    """Split a code into ``(symbol, exchange_or_None)``.

    Raises ``ValueError`` for malformed input or an unsupported exchange.
    """

    if not isinstance(code, str):
        raise ValueError(f"invalid code: {code!r}")
    match = _CODE_RE.match(code.strip())
    if match is None:
        raise ValueError(f"invalid code: {code!r}")
    symbol = match.group(1)
    exchange = match.group(2)
    if exchange is not None:
        exchange = exchange.upper()
        if exchange not in VALID_EXCHANGES:
            raise ValueError(f"unsupported exchange: {exchange!r}")
    return symbol, exchange


def normalize_code(code: str) -> str:
    """Return the canonical code, dropping to a bare symbol when unresolved."""

    symbol, exchange = normalize_code_parts(code)
    return f"{symbol}.{exchange}" if exchange is not None else symbol
