"""Unit normalization.

Tushare raw units:
- price: CNY (元)
- ``vol``: lots / 手 (1 lot = 100 shares)
- ``amount``: thousand CNY (千元)
- ``pct_chg`` / ``turnover_rate``: percent (e.g. ``4.35`` means 4.35%)
- ``total_mv`` / ``circ_mv``: ten-thousand CNY (万元)

AkShare raw units (verified from payloads, not function names):
- ``stock_zh_a_daily`` ``volume``: shares (股), ``amount``: CNY (元),
  ``turnover``: decimal ratio (fraction of free float).
- ``stock_sse_deal_daily`` values: 亿元 (hundred-million CNY).
- ``stock_szse_summary`` ``成交金额``: CNY (元).

Internal domain units:
- ``turnover_cny``: CNY (元)
- ``volume_shares``: shares (股)
- ``market_cap_cny``: CNY (元)
- percentages: percent

Missing values stay ``None`` and are never coerced to 0. NaN is treated as
missing.
"""

from __future__ import annotations

QIAN_YUAN_PER_CNY = 1000.0
SHARES_PER_HAND = 100.0
WAN_YUAN_PER_CNY = 10000.0
YI_YUAN_PER_CNY = 100_000_000.0


def to_float(value: object) -> float | None:
    """Best-effort conversion to float; ``None``/blank/NaN -> ``None``."""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        value = stripped
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


def qian_yuan_to_cny(value: object) -> float | None:
    """Tushare ``amount`` (千元) -> CNY (元)."""

    amount = to_float(value)
    return None if amount is None else amount * QIAN_YUAN_PER_CNY


def hands_to_shares(value: object) -> float | None:
    """Tushare ``vol`` (手) -> shares (股)."""

    lots = to_float(value)
    return None if lots is None else lots * SHARES_PER_HAND


def wan_yuan_to_cny(value: object) -> float | None:
    """Tushare ``total_mv`` / ``circ_mv`` (万元) -> CNY (元)."""

    amount = to_float(value)
    return None if amount is None else amount * WAN_YUAN_PER_CNY


def yi_yuan_to_cny(value: object) -> float | None:
    """SSE ``stock_sse_deal_daily`` values (亿元) -> CNY (元)."""

    amount = to_float(value)
    return None if amount is None else amount * YI_YUAN_PER_CNY


def ratio_to_pct(value: object) -> float | None:
    """A decimal ratio (e.g. Sina turnover 0.01) -> percent (1.0).

    Missing stays ``None`` and is never coerced to 0.
    """

    ratio = to_float(value)
    return None if ratio is None else ratio * 100.0
