"""Production Capability Set V0.1 for market evidence collection.

Frozen for this round:

REQUIRED (collection completeness depends on these):
    get_index_performance
    get_market_history_summary
    get_market_breadth
    get_market_metric_baseline {broken_limit_rate, promotion_rate} x {5, 20}

OPTIONAL (failure does not fail the collection):
    get_stock_detail

UNIMPLEMENTED (recorded as missing_capabilities, never fails collection):
    get_sector_ranking / get_sector_detail / get_stock_news
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

REQUIRED_CURRENT_TOOLS = (
    "get_index_performance",
    "get_market_history_summary",
    "get_market_breadth",
)
# Sector ranking is CURRENT_ONLY upstream, so it must be collected every day and
# stored in full (not just Top-10) to allow future replay/re-ranking.
REQUIRED_SECTOR_TOOLS = ("get_sector_ranking",)
REQUIRED_BASELINE_METRICS: Tuple[Tuple[str, int], ...] = (
    ("broken_limit_rate", 5),
    ("broken_limit_rate", 20),
    ("promotion_rate", 5),
    ("promotion_rate", 20),
)
OPTIONAL_REQUESTS: Tuple[Tuple[str, Dict[str, Any]], ...] = (
    ("get_stock_detail", {"stock_code": "600519.SH"}),
)
UNIMPLEMENTED_TOOLS: Tuple[str, ...] = ()

ERROR_NOT_IMPLEMENTED = "REAL_PROVIDER_NOT_IMPLEMENTED"

# --- deterministic evidence keys -------------------------------------------
def metric_key(metric: str, date: str) -> str:
    return "market_metric:%s:%s" % (metric, date)


def baseline_key(metric: str, date: str, window: int) -> str:
    return "market_metric_baseline:%s:%s:%s" % (metric, date, window)


def index_key(code: str, date: str) -> str:
    return "index_quote:%s:%s" % (code, date)


def stock_key(code: str, date: str) -> str:
    return "stock_detail:%s:%s" % (code, date)


def required_requests(date: str) -> List[Tuple[str, Dict[str, Any], str]]:
    requests = [(tool, {"date": date}, "current") for tool in REQUIRED_CURRENT_TOOLS]
    for tool in REQUIRED_SECTOR_TOOLS:
        requests.append(
            (tool, {"date": date, "direction": "top", "limit": 1000}, "current")
        )
    for metric, window in REQUIRED_BASELINE_METRICS:
        requests.append(
            (
                "get_market_metric_baseline",
                {"date": date, "metric": metric, "window": window},
                "baseline",
            )
        )
    return requests


def optional_requests(date: str) -> List[Tuple[str, Dict[str, Any], str]]:
    return [(tool, {"date": date, **extra}, "optional") for tool, extra in OPTIONAL_REQUESTS]


def unimplemented_requests(date: str) -> List[Tuple[str, Dict[str, Any], str]]:
    extra: Dict[str, Dict[str, Any]] = {
        "get_stock_news": {"stock_code": "600519.SH"},
    }
    return [(tool, {"date": date, **extra[tool]}, "unimplemented") for tool in UNIMPLEMENTED_TOOLS]
