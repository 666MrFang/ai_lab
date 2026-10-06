"""Internal domain objects with explicit units.

``to_tool_dict`` maps the domain object onto the *existing* MCP tool contract
(open/previous_close/close/change_pct/turnover/volume/turnover_rate) so the
Tool layer never has to know about provider fields or internal unit names.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


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

    def to_tool_dict(self) -> dict:
        return {
            "turnover": self.turnover.to_tool_dict(),
            "indices": [trend.to_tool_dict() for trend in self.indices],
        }
