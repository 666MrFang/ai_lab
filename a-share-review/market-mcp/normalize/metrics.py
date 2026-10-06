"""Small numeric metrics used to build domain aggregates."""

from __future__ import annotations

from typing import Iterable, Optional


def change_pct(current: Optional[float], base: Optional[float]) -> Optional[float]:
    """Percent change from ``base`` to ``current``; ``None`` when undefined."""

    if current is None or base is None or base == 0:
        return None
    return round((current - base) / base * 100, 2)


def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    """Mean over non-null values; ``None`` when there is no value."""

    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def pct_change_over_closes(closes: Iterable[Optional[float]], periods: int) -> Optional[float]:
    """Percent change over ``periods`` trading days using a close series.

    The series is expected in ascending date order. ``None`` values are
    dropped. ``None`` is returned when there are not enough observations.
    """

    if periods < 1:
        raise ValueError("periods must be >= 1")
    clean = [value for value in closes if value is not None]
    if len(clean) < periods + 1:
        return None
    return change_pct(clean[-1], clean[-(periods + 1)])
