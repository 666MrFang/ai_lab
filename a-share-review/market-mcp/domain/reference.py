"""Reference metadata (not market data).

Index display names and the market-total turnover口径 live here because they
are stable reference facts, not provider payloads. The market total is the
sum of the Shanghai and Shenzhen markets only; the ChiNext index is a subset
of Shenzhen and must never be added again.
"""

from __future__ import annotations

INDEX_NAMES = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
}

# Indices returned by get_index_performance / get_market_history_summary.
INDEX_CODES = ("000001.SH", "399001.SZ", "399006.SZ")

# Turnover口径 for the market total: Shanghai + Shenzhen only.
TOTAL_TURNOVER_CODES = ("000001.SH", "399001.SZ")
