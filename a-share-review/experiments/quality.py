"""Decision-usefulness scoring for A-share review A/B experiments."""

from __future__ import annotations
from typing import Any, Dict

def score_review(review: Dict[str, Any]) -> Dict[str, Any]:
    market = review.get("market") or {}
    sectors = review.get("sectors") or {}
    stocks = review.get("stocks") or []
    watches = review.get("tomorrow_watch_conditions") or []
    gaps = review.get("evidence_gaps") or []
    themes = sectors.get("main_theme_candidates") or []
    facts = market.get("facts") or []
    inferences = market.get("inferences") or []
    dimensions = {
        "market_picture": min(2, int(bool(facts)) + int(bool(inferences))),
        "theme_synthesis": min(2, int(bool(themes)) + int(any((x.get("evidence") or x.get("evidence_refs")) for x in themes))),
        "stock_focus": min(2, int(bool(stocks)) + int(any(x.get("possible_drivers") for x in stocks))),
        "tomorrow_verification": min(2, int(bool(watches)) + int(any(x.get("meaning") for x in watches))),
        "evidence_honesty": min(2, int(bool(gaps)) + int(bool(review.get("evidence_registry")))),
    }
    return {
        "protocol": "a-share-review-quality/v1",
        "score": sum(dimensions.values()), "max_score": 10,
        "dimensions": dimensions,
        "counts": {"market_facts": len(facts), "market_inferences": len(inferences),
                   "theme_candidates": len(themes), "stocks": len(stocks),
                   "watch_conditions": len(watches), "evidence_gaps": len(gaps)},
        "note": "Deterministic coverage proxy; not a substitute for investor judgment.",
    }
