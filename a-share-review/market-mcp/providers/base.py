"""Stable, provider-agnostic data provider interface.

Implementations talk to exactly one vendor and return internal domain objects.
Vendor field names and units never cross this boundary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Sequence

from domain.models import IndexQuote, MarketHistorySummary, StockQuote


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
