"""Tushare Pro implementation of the market data provider.

Provider-specific knowledge (``ts_code``, ``trade_date``, ``pct_chg``,
``amount``, ``vol``) is confined to this module. Every value is normalized
into the internal domain model before returning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from domain.models import (
    IndexQuote,
    IndexTrend,
    MarketHistorySummary,
    StockQuote,
    TurnoverBaseline,
)
from domain.reference import INDEX_NAMES
from errors import ErrorCode, MarketError
from normalize.codes import normalize_code_parts
from normalize.dates import from_provider_date, shift_calendar_days, to_provider_date
from normalize.metrics import change_pct, mean, pct_change_over_closes
from normalize.series import total_turnover_by_date
from normalize.units import hands_to_shares, qian_yuan_to_cny, to_float
from providers.base import MarketDataProvider

# Calendar-day lookback that safely covers 20 trading days incl. holidays.
LOOKBACK_CALENDAR_DAYS = 90
INDEX_TREND_SHORT = 5
INDEX_TREND_LONG = 20
TURNOVER_SHORT = 5
TURNOVER_LONG = 20


class TushareProvider(MarketDataProvider):
    def __init__(self, token: Optional[str] = None, client: Any = None):
        """Create the provider.

        ``client`` may be injected for tests; otherwise a Tushare Pro client is
        created lazily from ``token``. The token is never stored on the
        instance and never logged.
        """

        if client is None:
            if not token:
                raise MarketError(
                    ErrorCode.TUSHARE_TOKEN_NOT_CONFIGURED,
                    "TUSHARE_TOKEN is not configured",
                )
            import tushare as ts  # imported lazily so mock/tests need no tushare

            client = ts.pro_api(token)
        self._client = client
        self._security_master: Optional[Dict[str, Dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # Low level helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _records(frame: Any) -> List[Dict[str, Any]]:
        """Convert a provider frame (DataFrame or records) into a list of dicts."""

        if frame is None:
            return []
        if hasattr(frame, "to_dict"):
            try:
                return [row for row in frame.to_dict("records") if isinstance(row, dict)]
            except Exception:
                return []
        if isinstance(frame, (list, tuple)):
            return [row for row in frame if isinstance(row, dict)]
        try:
            return [row for row in frame if isinstance(row, dict)]
        except TypeError:
            return []

    def _call(self, func: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        try:
            frame = func(**kwargs)
        except MarketError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface a safe, generic error
            raise MarketError(
                ErrorCode.PROVIDER_ERROR,
                f"provider call failed ({type(exc).__name__})",
            ) from exc
        return self._records(frame)

    def is_trading_day(self, date: str) -> bool:
        compact = to_provider_date(date)
        rows = self._call(
            self._client.trade_cal,
            exchange="SSE",
            start_date=compact,
            end_date=compact,
            is_open="1",
        )
        return any(str(row.get("cal_date")) == compact for row in rows)

    def _security_master_map(self) -> Dict[str, Dict[str, Any]]:
        if self._security_master is None:
            rows = self._call(
                self._client.stock_basic,
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,market,exchange",
            )
            self._security_master = {
                str(row.get("ts_code")): row for row in rows if row.get("ts_code")
            }
        return self._security_master

    def _resolve_stock_code(self, stock_code: str) -> str:
        """Resolve to a canonical code using the security master as truth."""

        try:
            symbol, exchange = normalize_code_parts(stock_code)
        except ValueError as exc:
            raise MarketError(
                ErrorCode.INVALID_STOCK_CODE, f"invalid stock code: {stock_code}"
            ) from exc

        master = self._security_master_map()
        if exchange is not None:
            code = f"{symbol}.{exchange}"
            if code not in master:
                raise MarketError(
                    ErrorCode.INVALID_STOCK_CODE, f"unknown stock code: {code}"
                )
            return code

        matches = [ts_code for ts_code in master if ts_code.split(".")[0] == symbol]
        if len(matches) == 1:
            return matches[0]
        raise MarketError(
            ErrorCode.INVALID_STOCK_CODE, f"cannot resolve stock code: {stock_code}"
        )

    def _index_daily_row(self, code: str, compact: str) -> Optional[Dict[str, Any]]:
        rows = self._call(
            self._client.index_daily,
            ts_code=code,
            start_date=compact,
            end_date=compact,
        )
        for row in rows:
            if str(row.get("trade_date")) == compact:
                return row
        return None

    def _stock_daily_row(self, code: str, compact: str) -> Optional[Dict[str, Any]]:
        rows = self._call(
            self._client.daily,
            ts_code=code,
            start_date=compact,
            end_date=compact,
        )
        for row in rows:
            if str(row.get("trade_date")) == compact:
                return row
        return None

    def _stock_daily_basic_row(self, code: str, compact: str) -> Optional[Dict[str, Any]]:
        rows = self._call(
            self._client.daily_basic,
            ts_code=code,
            start_date=compact,
            end_date=compact,
            fields="ts_code,trade_date,turnover_rate,total_mv,circ_mv",
        )
        for row in rows:
            if str(row.get("trade_date")) == compact:
                return row
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_index_performance(self, date: str, index_codes: Sequence[str]) -> List[IndexQuote]:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        compact = to_provider_date(date)
        quotes: List[IndexQuote] = []
        for code in index_codes:
            row = self._index_daily_row(code, compact)
            if row is None:
                continue
            quotes.append(
                IndexQuote(
                    code=code,
                    name=INDEX_NAMES.get(code),
                    date=date,
                    open=to_float(row.get("open")),
                    previous_close=to_float(row.get("pre_close")),
                    high=to_float(row.get("high")),
                    low=to_float(row.get("low")),
                    close=to_float(row.get("close")),
                    change_pct=to_float(row.get("pct_chg")),
                    turnover_cny=qian_yuan_to_cny(row.get("amount")),
                )
            )

        if not quotes:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE, f"index data not available for {date}"
            )
        return quotes

    def get_stock_detail(self, date: str, stock_code: str) -> StockQuote:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        code = self._resolve_stock_code(stock_code)
        compact = to_provider_date(date)

        row = self._stock_daily_row(code, compact)
        if row is None:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                f"stock data not available for {code} on {date}",
            )

        info = self._security_master_map().get(code, {})
        basic = self._stock_daily_basic_row(code, compact)

        return StockQuote(
            code=code,
            name=info.get("name"),
            sector_name=info.get("industry"),
            date=date,
            previous_close=to_float(row.get("pre_close")),
            open=to_float(row.get("open")),
            high=to_float(row.get("high")),
            low=to_float(row.get("low")),
            close=to_float(row.get("close")),
            change_pct=to_float(row.get("pct_chg")),
            volume_shares=hands_to_shares(row.get("vol")),
            turnover_cny=qian_yuan_to_cny(row.get("amount")),
            turnover_rate_pct=to_float(basic.get("turnover_rate")) if basic else None,
        )

    def get_market_history_summary(
        self,
        date: str,
        index_codes: Sequence[str],
        total_turnover_codes: Sequence[str],
    ) -> MarketHistorySummary:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        compact = to_provider_date(date)
        start_compact = to_provider_date(shift_calendar_days(date, -LOOKBACK_CALENDAR_DAYS))

        series_by_code: Dict[str, List[Dict[str, Any]]] = {}
        for code in index_codes:
            rows = self._call(
                self._client.index_daily,
                ts_code=code,
                start_date=start_compact,
                end_date=compact,
            )
            normalized: List[Dict[str, Any]] = []
            for row in rows:
                row_date = from_provider_date(str(row.get("trade_date")))
                # Defensive as-of filter: never accept data after the review date.
                if row_date is None or row_date > date:
                    continue
                normalized.append(
                    {
                        "date": row_date,
                        "close": to_float(row.get("close")),
                        "turnover_cny": qian_yuan_to_cny(row.get("amount")),
                    }
                )
            normalized.sort(key=lambda item: item["date"])
            series_by_code[code] = normalized

        turnover_by_date = total_turnover_by_date(series_by_code, total_turnover_codes)
        as_of_dates = sorted(day for day in turnover_by_date if day <= date)
        if date not in turnover_by_date:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE, f"turnover data not available for {date}"
            )

        current = turnover_by_date[date]
        previous = turnover_by_date[as_of_dates[-2]] if len(as_of_dates) >= 2 else None
        avg_5d = mean([turnover_by_date[day] for day in as_of_dates[-TURNOVER_SHORT:]])
        avg_20d = mean([turnover_by_date[day] for day in as_of_dates[-TURNOVER_LONG:]])

        turnover = TurnoverBaseline(
            current_cny=current,
            previous_cny=previous,
            avg_5d_cny=avg_5d,
            avg_20d_cny=avg_20d,
            vs_previous_pct=change_pct(current, previous),
            vs_5d_pct=change_pct(current, avg_5d),
            vs_20d_pct=change_pct(current, avg_20d),
        )

        trends: List[IndexTrend] = []
        for code in index_codes:
            closes = [item["close"] for item in series_by_code.get(code, [])]
            trends.append(
                IndexTrend(
                    code=code,
                    name=INDEX_NAMES.get(code),
                    change_5d_pct=pct_change_over_closes(closes, INDEX_TREND_SHORT),
                    change_20d_pct=pct_change_over_closes(closes, INDEX_TREND_LONG),
                )
            )

        return MarketHistorySummary(turnover=turnover, indices=trends)
