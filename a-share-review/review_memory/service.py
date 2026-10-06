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
    history_map = normalized.get("sector_history") or {}
    states = []
    for rank, sector in enumerate(rows[:top_n], start=1):
        sector_id = sector.get("sector_id")
        history = history_map.get(str(sector_id)) or {}
        turnover = sector.get("turnover_cny")
        avg5 = history.get("turnover_avg_5d_cny")
        turnover_vs_5d = (
            round((float(turnover) / float(avg5) - 1.0) * 100.0, 2)
            if turnover is not None and avg5 not in (None, 0) else None
        )
        states.append({
            "sector_id": sector_id,
            "sector_name": sector.get("sector_name"),
            "sector_rank": rank,
            "sector_change_pct": sector.get("change_pct"),
            "sector_change_5d_pct": history.get("change_pct_5d"),
            "sector_change_20d_pct": history.get("change_pct_20d"),
            "sector_history_5d_complete": history.get("history_5d_complete"),
            "sector_history_20d_complete": history.get("history_20d_complete"),
            "sector_turnover_vs_5d_pct": turnover_vs_5d,
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
            "stock_candidates": [
                {
                    "code": stock.get("code"),
                    "name": stock.get("name"),
                    "sector_name": stock.get("sector_name"),
                    "roles": deepcopy(stock.get("roles") or []),
                    "facts": deepcopy(stock.get("facts") or []),
                    "evidence_gaps": deepcopy(stock.get("evidence_gaps") or []),
                }
                for stock in (review.get("stocks") or [])
                if "STRONG_STOCK" in (stock.get("roles") or [])
                or "CAPACITY_CORE_CANDIDATE" in (stock.get("roles") or [])
            ],
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
    """Settle only from unique, strictly-future, chronologically ordered sessions.

    A horizon is complete only when every tracked sector is observable in every
    required session. Missing sector evidence is never converted to zero and
    never allows the record to become SETTLED.
    """
    result = deepcopy(record)
    record_date = str(record.get("date") or "")

    by_date: Dict[str, Dict[str, Any]] = {}
    rejected: List[Dict[str, str]] = []
    for item in future_daily_evidence:
        date = str((item or {}).get("date") or "")
        if not date:
            rejected.append({"date": "", "reason": "MISSING_DATE"})
            continue
        if date <= record_date:
            rejected.append({"date": date, "reason": "NOT_STRICTLY_FUTURE"})
            continue
        if date in by_date:
            rejected.append({"date": date, "reason": "DUPLICATE_SESSION"})
            continue
        by_date[date] = item

    future = [by_date[date] for date in sorted(by_date)]
    horizons = {"t1": 1, "t3": 3, "t5": 5}
    settlement: Dict[str, Any] = {
        "horizons": {}, "complete": False, "rejected_sessions": rejected,
    }

    for label, count in horizons.items():
        available = min(len(future), count)
        if len(future) < count:
            settlement["horizons"][label] = {
                "complete": False, "sessions": available,
                "reason": "INSUFFICIENT_FUTURE_SESSIONS",
            }
            continue

        days = future[:count]
        missing_states = []
        pending_outcomes: Dict[int, float] = {}
        for index, state in enumerate(result.get("pattern_states") or []):
            changes = [
                _find_sector_change(day, state.get("sector_id"), state.get("sector_name"))
                for day in days
            ]
            if any(value is None for value in changes):
                missing_states.append({
                    "sector_id": state.get("sector_id"),
                    "sector_name": state.get("sector_name"),
                })
                continue
            pending_outcomes[index] = compound_returns(changes)

        horizon_complete = not missing_states
        settlement["horizons"][label] = {
            "complete": horizon_complete,
            "sessions": count,
            "end_date": days[-1].get("date"),
            "missing_states": missing_states,
            "reason": None if horizon_complete else "SECTOR_OUTCOME_NOT_OBSERVABLE",
        }
        if horizon_complete:
            for index, value in pending_outcomes.items():
                result["pattern_states"][index].setdefault("outcomes", {})[
                    "%s_sector_return_pct" % label
                ] = value

    settlement["complete"] = all(
        settlement["horizons"].get(label, {}).get("complete") is True
        for label in horizons
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
