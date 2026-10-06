"""Series helpers for as-of (point-in-time) aggregation.

All helpers are pure and only ever operate on dates ``<= end_date`` so that no
future data can leak into a review.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Sequence


def as_of(rows: Iterable[Mapping], end_date: str) -> List[Mapping]:
    """Keep only rows whose ``date`` is on or before ``end_date``."""

    return [row for row in rows if row["date"] <= end_date]


def latest_n(rows: Iterable[Mapping], n: int) -> List[Mapping]:
    """Return the ``n`` most recent rows (ascending order preserved)."""

    if n < 1:
        return []
    ordered = sorted(rows, key=lambda row: row["date"])
    return ordered[-n:]


def total_turnover_by_date(
    series_by_code: Mapping[str, Sequence[Mapping]],
    total_codes: Sequence[str],
) -> Dict[str, float]:
    """Sum ``turnover_cny`` across ``total_codes`` for each date.

    A date is only emitted when every code in ``total_codes`` has a non-null
    value (partial sums are omitted). Codes outside ``total_codes`` (e.g. the
    ChiNext index, which is a subset of the Shenzhen market) are never added.
    """

    per_code: Dict[str, Dict[str, float]] = {}
    for code in total_codes:
        per_code[code] = {
            row["date"]: row["turnover_cny"]
            for row in series_by_code.get(code, [])
            if row.get("turnover_cny") is not None
        }

    dates = set()
    for mapping in per_code.values():
        dates.update(mapping.keys())

    result: Dict[str, float] = {}
    for day in dates:
        values = [per_code[code].get(day) for code in total_codes]
        if any(value is None for value in values):
            continue
        result[day] = sum(values)
    return result
