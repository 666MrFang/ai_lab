"""Stable, provider-agnostic data provider interface.

Implementations talk to exactly one vendor and return internal domain objects.
Vendor field names and units never cross this boundary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Sequence

from domain.models import (
    IndexQuote,
    MarketBreadth,
    MarketHistorySummary,
    MetricBaseline,
    SectorHistorySummary,
    SectorMembershipSnapshot,
    SectorSnapshot,
    StockQuote,
)
from errors import ErrorCode, MarketError


class MarketDataProvider(ABC):
    @abstractmethod
    def get_index_performance(self, date: str, index_codes: Sequence[str]) -> List[IndexQuote]:
        """Daily quotes for the requested index codes on ``date``."""

    @abstractmethod
    def get_stock_detail(self, date: str, stock_code: str) -> StockQuote:
        """Daily quote for a single stock on ``date``."""

    @abstractmethod
    def get_market_history_summary(
        self,
        date: str,
        index_codes: Sequence[str],
        total_turnover_codes: Sequence[str],
    ) -> MarketHistorySummary:
        """As-of turnover baselines and index 5d/20d trends."""

    @abstractmethod
    def is_trading_day(self, date: str) -> bool:
        """Whether ``date`` is an open trading day."""

    def get_market_breadth(self, date: str) -> MarketBreadth:
        """Breadth for ``date`` (limit ecology historical; breadth current-only)."""

        raise MarketError(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{type(self).__name__} does not implement get_market_breadth",
        )

    def get_market_metric_baseline(
        self, date: str, metric: str, window: int
    ) -> MetricBaseline:
        """As-of historical baseline for a single breadth metric."""

        raise MarketError(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{type(self).__name__} does not implement get_market_metric_baseline",
        )

    def get_sector_ranking(
        self, date: str, direction: str = "top", limit: int = 10
    ) -> List[SectorSnapshot]:
        raise MarketError(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{type(self).__name__} does not implement get_sector_ranking",
        )

    def get_sector_history_summary(
        self, date: str, sector_name: str
    ) -> SectorHistorySummary:
        raise MarketError(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{type(self).__name__} does not implement get_sector_history_summary",
        )

    def get_sector_membership(self, sector_name: str) -> SectorMembershipSnapshot:
        raise MarketError(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{type(self).__name__} does not implement get_sector_membership",
        )

    def get_stock_news(self, date: str, stock_code: str, limit: int = 10) -> list[dict]:
        """Timestamped stock-news facts; never a causal conclusion."""

        raise MarketError(
            ErrorCode.REAL_PROVIDER_NOT_IMPLEMENTED,
            f"{type(self).__name__} does not implement get_stock_news",
        )
