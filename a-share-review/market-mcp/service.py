"""Market service.

The MCP tool layer talks only to this service. The service owns provider
selection, config/token validation, date validation, and translation of
provider failures into stable ``MarketError`` codes.
"""

from __future__ import annotations

from typing import Optional, Sequence

from config import Settings
from domain.reference import INDEX_CODES, TOTAL_TURNOVER_CODES
from errors import ErrorCode, MarketError
from normalize.dates import is_valid_iso_date
from providers.base import MarketDataProvider


class MarketService:
    def __init__(self, settings: Settings, provider: Optional[MarketDataProvider] = None):
        self._settings = settings
        self._provider = provider

    @property
    def data_mode(self) -> str:
        return self._settings.data_mode

    @property
    def settings(self) -> Settings:
        return self._settings

    def _get_provider(self) -> MarketDataProvider:
        if self._provider is not None:
            return self._provider

        if not self._settings.tushare_token:
            raise MarketError(
                ErrorCode.TUSHARE_TOKEN_NOT_CONFIGURED,
                "TUSHARE_TOKEN environment variable is not configured",
            )

        try:
            from providers.tushare_provider import TushareProvider

            self._provider = TushareProvider(token=self._settings.tushare_token)
        except MarketError:
            raise
        except Exception as exc:  # noqa: BLE001 - do not leak provider internals
            raise MarketError(
                ErrorCode.PROVIDER_ERROR,
                f"failed to initialize provider ({type(exc).__name__})",
            ) from exc
        return self._provider

    @staticmethod
    def _validate_date(date: object) -> None:
        if not is_valid_iso_date(date):
            raise MarketError(
                ErrorCode.INVALID_DATE,
                f"invalid date: {date!r} (expected YYYY-MM-DD)",
            )

    def get_index_performance(self, date: str, index_codes: Sequence[str] = INDEX_CODES):
        self._validate_date(date)
        provider = self._get_provider()
        return provider.get_index_performance(date, index_codes)

    def get_stock_detail(self, date: str, stock_code: str):
        self._validate_date(date)
        provider = self._get_provider()
        return provider.get_stock_detail(date, stock_code)

    def get_market_history_summary(
        self,
        date: str,
        index_codes: Sequence[str] = INDEX_CODES,
        total_turnover_codes: Sequence[str] = TOTAL_TURNOVER_CODES,
    ):
        self._validate_date(date)
        provider = self._get_provider()
        return provider.get_market_history_summary(
            date, index_codes, total_turnover_codes
        )
