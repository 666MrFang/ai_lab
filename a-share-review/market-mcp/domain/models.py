"""Internal domain objects with explicit units.

``to_tool_dict`` maps the domain object onto the *existing* MCP tool contract
(open/previous_close/close/change_pct/turnover/volume/turnover_rate) so the
Tool layer never has to know about provider fields or internal unit names.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DataLineage:
    """Internal provenance metadata (never part of the tool contract).

    ``library`` is the client library, ``source`` the upstream vendor, and
    ``endpoint`` the concrete function/URL used to build a value.
    """

    library: str
    source: str
    endpoint: str

    def to_dict(self) -> dict:
        return {
            "library": self.library,
            "source": self.source,
            "endpoint": self.endpoint,
        }


@dataclass(frozen=True)
class FieldProvenance:
    """Field-level provenance for a composite quote.

    A single quote can mix upstream sources (e.g. index OHLC from Sina but
    market turnover from SSE/SZSE), so a single object-level lineage would be
    incorrect. Each field group carries its own lineage; ``None`` means the
    field is unsupported or has no reliable source.
    """

    price: Optional[DataLineage] = None
    turnover: Optional[DataLineage] = None

    def to_dict(self) -> dict:
        return {
            "price": self.price.to_dict() if self.price is not None else None,
            "turnover": self.turnover.to_dict() if self.turnover is not None else None,
        }


@dataclass(frozen=True)
class IndexQuote:
    code: str
    name: Optional[str]
    date: str
    open: Optional[float]
    previous_close: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    change_pct: Optional[float]
    turnover_cny: Optional[float]
    provenance: Optional[FieldProvenance] = None

    def to_tool_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "open": self.open,
            "previous_close": self.previous_close,
            "close": self.close,
            "change_pct": self.change_pct,
            "turnover": self.turnover_cny,
        }


@dataclass(frozen=True)
class StockQuote:
    code: str
    name: Optional[str]
    sector_name: Optional[str]
    date: str
    previous_close: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    change_pct: Optional[float]
    volume_shares: Optional[float]
    turnover_cny: Optional[float]
    turnover_rate_pct: Optional[float]
    lineage: Optional[DataLineage] = None

    def to_tool_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "sector_name": self.sector_name,
            "previous_close": self.previous_close,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "change_pct": self.change_pct,
            "volume": self.volume_shares,
            "turnover": self.turnover_cny,
            "turnover_rate": self.turnover_rate_pct,
        }


@dataclass(frozen=True)
class TurnoverBaseline:
    current_cny: Optional[float]
    previous_cny: Optional[float]
    avg_5d_cny: Optional[float]
    avg_20d_cny: Optional[float]
    vs_previous_pct: Optional[float]
    vs_5d_pct: Optional[float]
    vs_20d_pct: Optional[float]

    def to_tool_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IndexTrend:
    code: str
    name: Optional[str]
    change_5d_pct: Optional[float]
    change_20d_pct: Optional[float]

    def to_tool_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MarketHistorySummary:
    turnover: TurnoverBaseline
    indices: List[IndexTrend] = field(default_factory=list)
    lineage: List[DataLineage] = field(default_factory=list)

    def to_tool_dict(self) -> dict:
        return {
            "turnover": self.turnover.to_tool_dict(),
            "indices": [trend.to_tool_dict() for trend in self.indices],
        }


# ============================================================
# Sector (Round 5B): THS industry family + Sina membership family
# ============================================================


@dataclass(frozen=True)
class SectorSnapshot:
    """A sector's current cross-sectional snapshot (THS industry family)."""

    date: str
    sector_id: Optional[str]
    sector_name: str
    taxonomy: str
    source_family: str
    change_pct: Optional[float]
    turnover_cny: Optional[float]
    up_count: Optional[int]
    down_count: Optional[int]
    flat_count: Optional[int]
    constituent_count: Optional[int]
    date_semantics: str
    lineage: Optional[DataLineage] = None

    def to_tool_dict(self) -> dict:
        return {
            "sector_id": self.sector_id,
            "sector_name": self.sector_name,
            "taxonomy": self.taxonomy,
            "source_family": self.source_family,
            "change_pct": self.change_pct,
            "turnover": self.turnover_cny,
            "turnover_cny": self.turnover_cny,
            "up_count": self.up_count,
            "down_count": self.down_count,
            "flat_count": self.flat_count,
            "constituent_count": self.constituent_count,
            "date_semantics": self.date_semantics,
        }


@dataclass(frozen=True)
class SectorHistorySummary:
    date: str
    sector_id: Optional[str]
    sector_name: str
    taxonomy: str
    source_family: str
    change_pct_5d: Optional[float]
    change_pct_20d: Optional[float]
    turnover_cny: Optional[float]
    turnover_avg_5d_cny: Optional[float]
    turnover_avg_20d_cny: Optional[float]
    history_5d_complete: bool
    history_20d_complete: bool
    sample_count_5d: int
    sample_count_20d: int
    lineage: Optional[DataLineage] = None

    def to_tool_dict(self) -> dict:
        return {
            "sector_id": self.sector_id,
            "sector_name": self.sector_name,
            "taxonomy": self.taxonomy,
            "source_family": self.source_family,
            "change_pct_5d": self.change_pct_5d,
            "change_pct_20d": self.change_pct_20d,
            "turnover_cny": self.turnover_cny,
            "turnover_avg_5d_cny": self.turnover_avg_5d_cny,
            "turnover_avg_20d_cny": self.turnover_avg_20d_cny,
            "history_5d_complete": self.history_5d_complete,
            "history_20d_complete": self.history_20d_complete,
            "sample_count_5d": self.sample_count_5d,
            "sample_count_20d": self.sample_count_20d,
        }


@dataclass(frozen=True)
class SectorMember:
    stock_code: str
    stock_name: Optional[str]
    change_pct: Optional[float]
    turnover_cny: Optional[float]
    turnover_rate_pct: Optional[float]
    market_cap_cny: Optional[float]

    def to_tool_dict(self) -> dict:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "change_pct": self.change_pct,
            "turnover_cny": self.turnover_cny,
            "turnover_rate_pct": self.turnover_rate_pct,
            "market_cap_cny": self.market_cap_cny,
        }


@dataclass(frozen=True)
class SectorMembershipSnapshot:
    date: str
    sector_id: Optional[str]
    sector_name: str
    taxonomy: str
    source_family: str
    membership_semantics: str
    stocks: List[SectorMember] = field(default_factory=list)
    lineage: Optional[DataLineage] = None

    def to_tool_dict(self) -> dict:
        return {
            "sector_id": self.sector_id,
            "sector_name": self.sector_name,
            "taxonomy": self.taxonomy,
            "source_family": self.source_family,
            "membership_semantics": self.membership_semantics,
            "count": len(self.stocks),
            "stocks": [stock.to_tool_dict() for stock in self.stocks],
        }


# ============================================================
# Market breadth / limit ecology
# ============================================================


@dataclass(frozen=True)
class MetricDefinition:
    """Machine-readable definition of a breadth metric.

    ``universe_definition`` records the *verified* universe (based on live
    payloads), never a vendor docstring. ``historical`` says whether the metric
    can be queried for a past trading day.
    """

    metric: str
    source: str
    endpoint: str
    unit: str
    universe_definition: str
    date_semantics: str
    historical: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LimitEcology:
    """Historical-queryable limit-up/down ecology metrics for a trading day."""

    limit_up_count: Optional[int]
    limit_down_count: Optional[int]
    broken_limit_count: Optional[int]
    broken_limit_rate: Optional[float]
    first_limit_up_count: Optional[int]
    multi_limit_up_count: Optional[int]
    max_consecutive_limit_up: Optional[int]
    previous_sample_size: Optional[int]
    previous_average_change_pct: Optional[float]
    previous_median_change_pct: Optional[float]
    previous_positive_rate: Optional[float]
    previous_promotion_rate: Optional[float]


@dataclass(frozen=True)
class MarketBreadth:
    """Breadth for a trading day.

    Limit ecology is historical-queryable (Eastmoney limit pools).
    ``advance_count`` / ``decline_count`` / ``flat_count`` are CURRENT_ONLY
    (legulegu snapshot) and are ``None`` for any historical date.
    """

    date: str
    limit: LimitEcology
    advance_count: Optional[int]
    decline_count: Optional[int]
    flat_count: Optional[int]
    breadth_as_of: Optional[str] = None
    missing_reasons: Dict[str, str] = field(default_factory=dict)
    definitions: Dict[str, MetricDefinition] = field(default_factory=dict)

    def to_tool_dict(self) -> dict:
        return {
            "breadth": {
                "rising_count": self.advance_count,
                "falling_count": self.decline_count,
                "flat_count": self.flat_count,
            },
            "limit_state": {
                "limit_up_count": self.limit.limit_up_count,
                "limit_down_count": self.limit.limit_down_count,
                "first_limit_up_count": self.limit.first_limit_up_count,
                "multi_limit_up_count": self.limit.multi_limit_up_count,
                "max_limit_height": self.limit.max_consecutive_limit_up,
                "broken_limit_count": self.limit.broken_limit_count,
                "broken_limit_rate": self.limit.broken_limit_rate,
            },
            "previous_limit_up": {
                "sample_size": self.limit.previous_sample_size,
                "average_change_pct": self.limit.previous_average_change_pct,
                "median_change_pct": self.limit.previous_median_change_pct,
                "positive_rate": self.limit.previous_positive_rate,
                "promotion_rate": self.limit.previous_promotion_rate,
            },
            "extreme_move": {
                "large_rise_count": None,
                "large_fall_count": None,
            },
            "evidence": {
                "breadth_as_of": self.breadth_as_of,
                "missing_reasons": dict(self.missing_reasons),
                "definitions": {
                    name: definition.to_dict()
                    for name, definition in self.definitions.items()
                },
            },
        }


@dataclass(frozen=True)
class MetricBaseline:
    """As-of historical baseline for a single metric.

    The sample is the ``window`` most recent completed trading days strictly
    before ``date`` (``sample_date < date``); ``current`` is stored separately
    and never enters the sample. When ``complete`` is false the aggregate
    statistics are ``None`` and must not be read as a shortened-window result.
    """

    metric: str
    date: str
    unit: str
    window: int
    current: Optional[float]
    avg: Optional[float]
    median: Optional[float]
    percentile: Optional[float]
    sample_count: int
    complete: bool
    sample_start: Optional[str]
    sample_end: Optional[str]
    missing_dates: Tuple[str, ...] = ()
    definition: Optional[MetricDefinition] = None

    def to_tool_dict(self) -> dict:
        payload = {
            "metric": self.metric,
            "date": self.date,
            "unit": self.unit,
            "window": self.window,
            "current": self.current,
            "avg": self.avg,
            "median": self.median,
            "percentile": self.percentile,
            "sample_count": self.sample_count,
            "complete": self.complete,
            "sample_start": self.sample_start,
            "sample_end": self.sample_end,
            "missing_dates": list(self.missing_dates),
            "evidence_status": "COMPLETE" if self.complete else "INSUFFICIENT_HISTORY",
        }
        if self.definition is not None:
            payload["definition"] = self.definition.to_dict()
        return payload
