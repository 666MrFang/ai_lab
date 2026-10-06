"""Deterministic historical pattern matching; statistics are not predictions."""

from __future__ import annotations

from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional

MIN_SAMPLE_DEFAULT = 8


def _direction(value: Optional[float]) -> str:
    if value is None:
        return "UNKNOWN"
    if value > 0.5:
        return "UP"
    if value < -0.5:
        return "DOWN"
    return "FLAT"


def _sector_move_bucket(value: Optional[float]) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= 4.0:
        return "SURGE_4P"
    if value >= 2.0:
        return "STRONG_2P"
    if value <= -2.0:
        return "WEAK_M2P"
    return "NORMAL"


def _rank_bucket(rank: Optional[int]) -> str:
    if rank is None:
        return "UNKNOWN"
    if rank <= 1:
        return "TOP1"
    if rank <= 3:
        return "TOP3"
    if rank <= 5:
        return "TOP5"
    return "OTHER"


def _persistence_bucket(value: Optional[float], complete: Any) -> str:
    if complete is not True or value is None:
        return "UNKNOWN"
    if value >= 5.0:
        return "UP_5P"
    if value >= 0.0:
        return "UP"
    if value <= -5.0:
        return "DOWN_5P"
    return "DOWN"


def _volume_bucket(value: Optional[float]) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= 30.0:
        return "EXPANDED_30P"
    if value <= -20.0:
        return "CONTRACTED_20P"
    return "NORMAL"


def state_signature(state: Dict[str, Any]) -> Dict[str, str]:
    return {
        "market_direction": _direction(state.get("market_change_pct")),
        "sector_move": _sector_move_bucket(state.get("sector_change_pct")),
        "sector_rank": _rank_bucket(state.get("sector_rank")),
        "sector_5d": _persistence_bucket(
            state.get("sector_change_5d_pct"), state.get("sector_history_5d_complete")
        ),
        "sector_volume": _volume_bucket(state.get("sector_turnover_vs_5d_pct")),
    }


def _same_sector(current_state: Dict[str, Any], historical_state: Dict[str, Any]) -> bool:
    current_id = current_state.get("sector_id")
    if current_id:
        return historical_state.get("sector_id") == current_id
    current_name = current_state.get("sector_name")
    if current_name:
        return historical_state.get("sector_name") == current_name
    return True


def compound_returns(values: Iterable[float]) -> float:
    value = 1.0
    for change in values:
        value *= 1.0 + float(change) / 100.0
    return round((value - 1.0) * 100.0, 4)


class PatternEngine:
    def __init__(self, min_sample: int = MIN_SAMPLE_DEFAULT):
        self.min_sample = min_sample

    def match(
        self,
        records: Iterable[Dict[str, Any]],
        as_of_date: str,
        current_state: Dict[str, Any],
        horizon: str = "t1",
    ) -> Dict[str, Any]:
        signature = state_signature(current_state)
        metric = "%s_sector_return_pct" % horizon
        samples: List[float] = []
        sample_dates: List[str] = []

        for record in records:
            if record.get("date", "") >= as_of_date or record.get("status") != "SETTLED":
                continue
            for state in record.get("pattern_states") or []:
                # Sector-specific outlooks must never borrow outcomes from a
                # different industry that merely shares the same numeric state.
                if not _same_sector(current_state, state):
                    continue
                if state_signature(state) != signature:
                    continue
                value = (state.get("outcomes") or {}).get(metric)
                if value is not None:
                    samples.append(float(value))
                    sample_dates.append(record["date"])

        complete = len(samples) >= self.min_sample
        result = {
            "as_of_date": as_of_date,
            "signature": signature,
            "horizon": horizon,
            "sample_size": len(samples),
            "minimum_sample": self.min_sample,
            "status": "CALIBRATED" if complete else "INSUFFICIENT_SAMPLE",
            "sample_dates": sample_dates,
            "positive_rate": None,
            "average_return_pct": None,
            "median_return_pct": None,
        }
        if complete:
            result["positive_rate"] = round(
                100.0 * sum(value > 0 for value in samples) / len(samples), 2
            )
            result["average_return_pct"] = round(mean(samples), 4)
            result["median_return_pct"] = round(median(samples), 4)
        return result
