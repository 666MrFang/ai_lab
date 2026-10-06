"""Build review records, settle future outcomes, and create calibrated outlooks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from .patterns import PatternEngine, compound_returns


def _index_change(normalized: Dict[str, Any], code: str = "000001.SH") -> Optional[float]:
    for item in (normalized.get("evidence") or {}).values():
        if item.get("evidence_type") == "index_quote" and item.get("index") == code:
            return item.get("change_pct")
    return None


def _sector_rows(normalized: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list((normalized.get("sector_ranking") or {}).get("sectors") or [])


def build_review_record(
    date: str,
    review: Dict[str, Any],
    normalized: Dict[str, Any],
    run_manifest: Optional[Dict[str, Any]] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    rows = sorted(
        _sector_rows(normalized),
        key=lambda row: row.get("change_pct")
        if row.get("change_pct") is not None else float("-inf"),
        reverse=True,
    )
    market_change = _index_change(normalized)
    states = []
    for rank, sector in enumerate(rows[:top_n], start=1):
        states.append({
            "sector_id": sector.get("sector_id"),
            "sector_name": sector.get("sector_name"),
            "sector_rank": rank,
            "sector_change_pct": sector.get("change_pct"),
            "market_change_pct": market_change,
            "outcomes": {},
        })
    return {
        "version": "review-memory/v1",
        "date": date,
        "status": "OPEN",
        "review_snapshot": {
            "market_regime": deepcopy(review.get("market_regime")),
            "main_theme_candidates": deepcopy(
                (review.get("sectors") or {}).get("main_theme_candidates") or []
            ),
            "tomorrow_watch_conditions": deepcopy(review.get("tomorrow_watch_conditions") or []),
            "metric_claims": deepcopy(review.get("metric_claims") or []),
        },
        "pattern_states": states,
        "run_identity": {
            key: (run_manifest or {}).get(key)
            for key in ("run_id", "skill_sha256", "schema_sha256", "eval_sha256")
        },
        "settlement": {"horizons": {}, "complete": False},
    }


def _find_sector_change(
    normalized: Dict[str, Any], sector_id: Any, sector_name: Any
) -> Optional[float]:
    for row in _sector_rows(normalized):
        if sector_id and row.get("sector_id") == sector_id:
            return row.get("change_pct")
        if not sector_id and sector_name and row.get("sector_name") == sector_name:
            return row.get("change_pct")
    return None


def settle_record(
    record: Dict[str, Any],
    future_daily_evidence: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    # Input must be chronological completed trading-session snapshots.
    result = deepcopy(record)
    future = list(future_daily_evidence)
    horizons = {"t1": 1, "t3": 3, "t5": 5}
    settlement = {"horizons": {}, "complete": False}

    for label, count in horizons.items():
        if len(future) < count:
            settlement["horizons"][label] = {"complete": False, "sessions": len(future)}
            continue
        days = future[:count]
        settlement["horizons"][label] = {
            "complete": True,
            "sessions": count,
            "end_date": days[-1].get("date"),
        }
        for state in result.get("pattern_states") or []:
            changes = [
                _find_sector_change(day, state.get("sector_id"), state.get("sector_name"))
                for day in days
            ]
            if all(value is not None for value in changes):
                state.setdefault("outcomes", {})[
                    "%s_sector_return_pct" % label
                ] = compound_returns(changes)

    settlement["complete"] = all(
        item.get("complete") for item in settlement["horizons"].values()
    )
    result["settlement"] = settlement
    result["status"] = "SETTLED" if settlement["complete"] else "PARTIALLY_SETTLED"
    return result


def build_outlook(
    date: str,
    current_record: Dict[str, Any],
    historical_records: Iterable[Dict[str, Any]],
    min_sample: int = 8,
) -> Dict[str, Any]:
    engine = PatternEngine(min_sample=min_sample)
    patterns = []
    history = list(historical_records)
    for state in current_record.get("pattern_states") or []:
        item = {
            "sector_id": state.get("sector_id"),
            "sector_name": state.get("sector_name"),
            "current_state": {
                "sector_rank": state.get("sector_rank"),
                "sector_change_pct": state.get("sector_change_pct"),
                "market_change_pct": state.get("market_change_pct"),
            },
            "statistics": {},
        }
        for horizon in ("t1", "t3", "t5"):
            item["statistics"][horizon] = engine.match(
                history, date, state, horizon
            )
        patterns.append(item)

    calibrated = sum(
        1 for item in patterns
        if item["statistics"]["t1"]["status"] == "CALIBRATED"
    )
    return {
        "version": "historical-outlook/v1",
        "date": date,
        "nature": "HISTORICAL_CALIBRATION_NOT_PREDICTION",
        "patterns": patterns,
        "calibrated_pattern_count": calibrated,
        "evidence_gaps": [] if calibrated else [
            "历史已结算相似样本不足；禁止使用通常/大概率等方向性措辞"
        ],
    }
