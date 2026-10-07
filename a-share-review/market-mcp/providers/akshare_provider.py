"""AkShare implementation of the market data provider (Real Provider V0.1).

Only AkShare interfaces that were actually verified reachable in the current
environment are used. Each one is pinned with its ``library``/``source``/
``endpoint`` lineage:

- ``tool_trade_date_hist_sina``  calendar          source=sina
- ``stock_zh_a_daily``           stock OHLC (raw)  source=sina
- ``stock_zh_index_daily``       index OHLC        source=sina
- ``stock_sse_deal_daily``       SSE market total  source=sse
- ``stock_szse_summary``         SZSE market total source=szse
- ``stock_info_sh_name_code``    security master   source=sse
- ``stock_info_sz_name_code``    security master   source=szse
- ``stock_zt_pool_em``           limit-up pool     source=eastmoney
- ``stock_zt_pool_dtgc_em``      limit-down pool   source=eastmoney
- ``stock_zt_pool_zbgc_em``      broken-board pool source=eastmoney
- ``stock_zt_pool_previous_em``  prior-day pool    source=eastmoney
- ``stock_market_activity_legu`` current breadth   source=legulegu (CURRENT_ONLY)

Eastmoney-backed endpoints (``stock_zh_a_hist``, ``index_zh_a_hist``,
``stock_zh_a_spot_em``) are intentionally NOT used: the capability probe showed
those endpoints are not reliably reachable here.

Unit rules are based on observed payloads, not function names:

- ``stock_zh_a_daily`` ``volume`` is shares (股); ``amount`` is CNY (元);
  ``turnover`` is a decimal ratio (fraction of free float).
- ``stock_sse_deal_daily`` values are 亿元; ``stock_szse_summary``
  ``成交金额`` is 元.

Missing values stay ``None`` and are never coerced to zero. Nothing is ever
synthetically filled: no mock fallback exists inside the provider.
"""

from __future__ import annotations

import json
from datetime import date as _date
from datetime import datetime as _datetime
from datetime import timedelta
from pathlib import Path
from statistics import median as _median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from domain.metricdefs import METRIC_DEFINITIONS, SUPPORTED_BASELINE_METRICS
from domain.models import (
    DataLineage,
    FieldProvenance,
    IndexQuote,
    IndexTrend,
    LimitEcology,
    MarketBreadth,
    MarketHistorySummary,
    MetricBaseline,
    SectorHistorySummary,
    SectorMember,
    SectorMembershipSnapshot,
    SectorSnapshot,
    StockQuote,
    TurnoverBaseline,
)
from domain.reference import INDEX_NAMES
from errors import ErrorCode, MarketError
from normalize.codes import normalize_code_parts
from normalize.dates import (
    coerce_to_iso_date,
    shift_calendar_days,
    to_provider_date,
)
from normalize.metrics import change_pct, mean, pct_change_over_closes
from normalize.units import (
    ratio_to_pct,
    to_float,
    wan_yuan_to_cny,
    yi_yuan_to_cny,
)
from providers.base import MarketDataProvider

# Calendar-day lookback that safely covers 20 trading days + previous close.
LOOKBACK_CALENDAR_DAYS = 60
INDEX_TREND_SHORT = 5
INDEX_TREND_LONG = 20
TURNOVER_SHORT = 5
TURNOVER_LONG = 20

# Eastmoney limit-pool family. The AkShare client refuses dates older than
# now-30 calendar days for dtgc/zbgc; zt/prev share the same effective window.
LIMIT_POOL_RETENTION_CALENDAR_DAYS = 30

_POOL_ENDPOINTS = {
    "zt": "stock_zt_pool_em",
    "dtgc": "stock_zt_pool_dtgc_em",
    "zbgc": "stock_zt_pool_zbgc_em",
    "prev": "stock_zt_pool_previous_em",
}
_POOL_REQUIRED_COLUMNS = {
    "zt": ("代码", "连板数", "涨跌幅"),
    "dtgc": ("代码",),
    "zbgc": ("代码",),
    "prev": ("代码", "涨跌幅"),
}

# Missing-reason vocabulary (machine-readable, not free text).
REASON_OUT_OF_RETENTION = "OUT_OF_RETENTION"
REASON_EMPTY_UPSTREAM = "EMPTY_UPSTREAM_RESPONSE"
REASON_CURRENT_ONLY = "CURRENT_ONLY_SOURCE"
REASON_NO_SOURCE = "NO_RELIABLE_SOURCE"

# Canonical index code -> Sina symbol (verified reachable).
_INDEX_SINA_SYMBOL = {
    "000001.SH": "sh000001",
    "399001.SZ": "sz399001",
    "399006.SZ": "sz399006",
}

# Field-level provenance for index quotes: OHLC/change_pct always come from
# Sina; turnover (when available) comes from the exchange aggregate.
_PRICE_LINEAGE = DataLineage(
    library="akshare", source="sina", endpoint="stock_zh_index_daily"
)
_SSE_TURNOVER_LINEAGE = DataLineage(
    library="akshare", source="sse", endpoint="stock_sse_deal_daily"
)
_SZSE_TURNOVER_LINEAGE = DataLineage(
    library="akshare", source="szse", endpoint="stock_szse_summary"
)

# Indices with a reliable independent turnover source. Anything absent (e.g.
# 399006.SZ / ChiNext, a Shenzhen subset) has turnover provenance ``None``.
_INDEX_TURNOVER_LINEAGE = {
    "000001.SH": _SSE_TURNOVER_LINEAGE,
    "399001.SZ": _SZSE_TURNOVER_LINEAGE,
}

_STOCK_DAILY_COLUMNS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover",
)
_INDEX_DAILY_COLUMNS = ("date", "open", "high", "low", "close")
_SSE_DEAL_COLUMNS = ("单日情况", "股票")
_SZSE_SUMMARY_COLUMNS = ("证券类别", "成交金额")
_SH_NAME_COLUMNS = ("证券代码", "证券简称")
_SZ_NAME_COLUMNS = ("A股代码", "A股简称")

_NETWORK_KEYWORDS = (
    "max retries",
    "connection",
    "timed out",
    "timeout",
    "proxy",
    "ssl",
    "getaddrinfo",
    "temporary failure",
    "remote end closed",
    "connectionpool",
    "failed to establish",
    "read timed out",
    "network is unreachable",
)


def _classify_exception(exc: Exception) -> str:
    """Map an upstream exception onto a stable, non-leaky error code."""

    text = f"{type(exc).__name__} {exc}".lower()
    if any(keyword in text for keyword in _NETWORK_KEYWORDS):
        return ErrorCode.NETWORK_ERROR
    return ErrorCode.INTERNAL_ERROR


def _pad_symbol(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = text.split(".")[0]
    if not digits.isdigit():
        return None
    return digits.zfill(6)


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> Optional[int]:
    number = to_float(value)
    return None if number is None else int(round(number))


class AkShareProvider(MarketDataProvider):
    """Real provider backed by AkShare.

    ``client`` mirrors the AkShare module namespace and may be injected for
    offline tests; otherwise AkShare is imported lazily so mock-mode and unit
    tests never require the dependency.
    """

    def __init__(self, client: Any = None, today: Any = None):
        if client is None:
            import akshare as ak  # imported lazily

            client = ak
        self._client = client
        # ``today`` (date or callable) is injectable for deterministic tests.
        self._today_override = today
        self._trade_dates_cache: Optional[List[str]] = None
        self._trade_date_set_cache: Optional[set] = None
        self._security_master_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._index_series_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._pool_cache: Dict[Tuple[str, str], Tuple[Optional[List[Dict[str, Any]]], Optional[str]]] = {}
        self._sector_taxonomy_cache: Optional[Dict[str, str]] = None
        self._sector_mapping_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def _today(self) -> _date:
        if callable(self._today_override):
            return self._today_override()
        if isinstance(self._today_override, _datetime):
            return self._today_override.date()
        if isinstance(self._today_override, _date):
            return self._today_override
        return _date.today()

    # ------------------------------------------------------------------
    # Low level helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _to_records(frame: Any) -> List[Dict[str, Any]]:
        if frame is None:
            return []
        if hasattr(frame, "to_dict"):
            try:
                records = frame.to_dict("records")
            except Exception:
                return []
            return [row for row in records if isinstance(row, dict)]
        if isinstance(frame, (list, tuple)):
            return [row for row in frame if isinstance(row, dict)]
        return []

    def _require_columns(self, frame: Any, columns: Sequence[str], endpoint: str) -> None:
        """Raise ``UPSTREAM_SCHEMA_CHANGED`` when expected columns are absent."""

        if hasattr(frame, "columns"):
            try:
                present = set(map(str, frame.columns))
            except Exception:
                return
            if not present:
                return
            missing = [column for column in columns if column not in present]
            if missing:
                raise MarketError(
                    ErrorCode.UPSTREAM_SCHEMA_CHANGED,
                    f"{endpoint} is missing expected fields: {missing}",
                )
        elif isinstance(frame, (list, tuple)) and frame and isinstance(frame[0], dict):
            present = set(frame[0].keys())
            missing = [column for column in columns if column not in present]
            if missing:
                raise MarketError(
                    ErrorCode.UPSTREAM_SCHEMA_CHANGED,
                    f"{endpoint} is missing expected fields: {missing}",
                )

    def _call(self, endpoint: str, **kwargs: Any) -> Any:
        func = getattr(self._client, endpoint, None)
        if func is None:
            raise MarketError(
                ErrorCode.INTERNAL_ERROR, f"akshare endpoint unavailable: {endpoint}"
            )
        try:
            return func(**kwargs)
        except MarketError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak vendor internals
            raise MarketError(
                _classify_exception(exc),
                f"{endpoint} call failed ({type(exc).__name__})",
            ) from exc

    # ------------------------------------------------------------------
    # Trading calendar
    # ------------------------------------------------------------------
    def _trade_dates(self) -> List[str]:
        if self._trade_dates_cache is None:
            frame = self._call("tool_trade_date_hist_sina")
            self._require_columns(frame, ("trade_date",), "tool_trade_date_hist_sina")
            dates = []
            for row in self._to_records(frame):
                iso = coerce_to_iso_date(row.get("trade_date"))
                if iso is not None:
                    dates.append(iso)
            ordered = sorted(set(dates))
            if not ordered:
                raise MarketError(
                    ErrorCode.DATA_NOT_AVAILABLE, "trading calendar is empty"
                )
            self._trade_dates_cache = ordered
            self._trade_date_set_cache = set(ordered)
        return self._trade_dates_cache

    def is_trading_day(self, date: str) -> bool:
        self._trade_dates()
        return date in (self._trade_date_set_cache or set())

    def _trading_days_up_to(self, date: str) -> List[str]:
        return [day for day in self._trade_dates() if day <= date]

    # ------------------------------------------------------------------
    # Security master
    # ------------------------------------------------------------------
    def _security_master_map(self) -> Dict[str, Dict[str, Any]]:
        if self._security_master_cache is None:
            sh_main = self._call("stock_info_sh_name_code", symbol="主板A股")
            self._require_columns(sh_main, _SH_NAME_COLUMNS, "stock_info_sh_name_code")
            sh_star = self._call("stock_info_sh_name_code", symbol="科创板")
            self._require_columns(sh_star, _SH_NAME_COLUMNS, "stock_info_sh_name_code")
            sz_list = self._call("stock_info_sz_name_code", symbol="A股列表")
            self._require_columns(sz_list, _SZ_NAME_COLUMNS, "stock_info_sz_name_code")

            master: Dict[str, Dict[str, Any]] = {}
            for frame, code_col, name_col, exchange in (
                (sh_main, "证券代码", "证券简称", "SH"),
                (sh_star, "证券代码", "证券简称", "SH"),
                (sz_list, "A股代码", "A股简称", "SZ"),
            ):
                for row in self._to_records(frame):
                    symbol = _pad_symbol(row.get(code_col))
                    if symbol is None:
                        continue
                    master[f"{symbol}.{exchange}"] = {"name": _clean_text(row.get(name_col))}
            if not master:
                raise MarketError(
                    ErrorCode.DATA_NOT_AVAILABLE, "security master is empty"
                )
            self._security_master_cache = master
        return self._security_master_cache

    def _resolve_stock_code(self, stock_code: str) -> str:
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

        matches = [code for code in master if code.split(".")[0] == symbol]
        if len(matches) == 1:
            return matches[0]
        raise MarketError(
            ErrorCode.INVALID_STOCK_CODE, f"cannot resolve stock code: {stock_code}"
        )

    # ------------------------------------------------------------------
    # Series fetchers
    # ------------------------------------------------------------------
    def _stock_daily_series(self, canonical: str, date: str) -> List[Dict[str, Any]]:
        symbol, exchange = canonical.split(".")
        sina_symbol = exchange.lower() + symbol
        start = to_provider_date(shift_calendar_days(date, -LOOKBACK_CALENDAR_DAYS))
        end = to_provider_date(date)
        frame = self._call(
            "stock_zh_a_daily",
            symbol=sina_symbol,
            start_date=start,
            end_date=end,
            adjust="",
        )
        self._require_columns(frame, _STOCK_DAILY_COLUMNS, "stock_zh_a_daily")

        rows: List[Dict[str, Any]] = []
        for row in self._to_records(frame):
            iso = coerce_to_iso_date(row.get("date"))
            # Defensive as-of filter: never accept rows after the review date.
            if iso is None or iso > date:
                continue
            rows.append(
                {
                    "date": iso,
                    "open": to_float(row.get("open")),
                    "high": to_float(row.get("high")),
                    "low": to_float(row.get("low")),
                    "close": to_float(row.get("close")),
                    "volume_shares": to_float(row.get("volume")),
                    "turnover_cny": to_float(row.get("amount")),
                    "turnover_rate_pct": ratio_to_pct(row.get("turnover")),
                }
            )
        rows.sort(key=lambda item: item["date"])
        return rows

    def _index_series(self, canonical: str) -> List[Dict[str, Any]]:
        if canonical in self._index_series_cache:
            return self._index_series_cache[canonical]
        sina_symbol = _INDEX_SINA_SYMBOL.get(canonical)
        if sina_symbol is None:
            self._index_series_cache[canonical] = []
            return []
        frame = self._call("stock_zh_index_daily", symbol=sina_symbol)
        self._require_columns(frame, _INDEX_DAILY_COLUMNS, "stock_zh_index_daily")
        rows: List[Dict[str, Any]] = []
        for row in self._to_records(frame):
            iso = coerce_to_iso_date(row.get("date"))
            if iso is None:
                continue
            rows.append(
                {
                    "date": iso,
                    "open": to_float(row.get("open")),
                    "high": to_float(row.get("high")),
                    "low": to_float(row.get("low")),
                    "close": to_float(row.get("close")),
                }
            )
        rows.sort(key=lambda item: item["date"])
        self._index_series_cache[canonical] = rows
        return rows

    # ------------------------------------------------------------------
    # Exchange market totals
    # ------------------------------------------------------------------
    def _sse_stock_turnover(self, date: str) -> Optional[float]:
        frame = self._call("stock_sse_deal_daily", date=to_provider_date(date))
        self._require_columns(frame, _SSE_DEAL_COLUMNS, "stock_sse_deal_daily")
        for row in self._to_records(frame):
            if _clean_text(row.get("单日情况")) == "成交金额":
                return yi_yuan_to_cny(row.get("股票"))  # 亿元 -> 元
        return None

    def _szse_stock_turnover(self, date: str) -> Optional[float]:
        frame = self._call("stock_szse_summary", date=to_provider_date(date))
        self._require_columns(frame, _SZSE_SUMMARY_COLUMNS, "stock_szse_summary")
        for row in self._to_records(frame):
            if _clean_text(row.get("证券类别")) == "股票":
                return to_float(row.get("成交金额"))  # already 元
        return None

    def _index_turnover(self, code: str, date: str) -> Optional[float]:
        """Market turnover for an index, or ``None`` when unsupported.

        ``000001.SH`` -> SSE stock turnover, ``399001.SZ`` -> SZSE stock
        turnover. ``399006.SZ`` (ChiNext, a Shenzhen subset) has no reliable
        independent turnover and is explicitly unsupported -> ``None``.

        Upstream failures are NOT swallowed: a ``NETWORK_ERROR``,
        ``UPSTREAM_SCHEMA_CHANGED`` or ``INTERNAL_ERROR`` raised while fetching
        a supported index propagates to the caller. Missing data must never be
        confused with an upstream failure.
        """

        if code == "000001.SH":
            return self._sse_stock_turnover(date)
        if code == "399001.SZ":
            return self._szse_stock_turnover(date)
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_index_performance(
        self, date: str, index_codes: Sequence[str]
    ) -> List[IndexQuote]:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        quotes: List[IndexQuote] = []
        for code in index_codes:
            series = [row for row in self._index_series(code) if row["date"] <= date]
            target = next((row for row in series if row["date"] == date), None)
            if target is None:
                continue
            previous = series[-2] if len(series) >= 2 else None
            previous_close = previous["close"] if previous else None
            # Fetch turnover before building the quote so upstream failures
            # propagate instead of being silently replaced by None.
            turnover_cny = self._index_turnover(code, date)
            quotes.append(
                IndexQuote(
                    code=code,
                    name=INDEX_NAMES.get(code),
                    date=date,
                    open=target["open"],
                    previous_close=previous_close,
                    high=target["high"],
                    low=target["low"],
                    close=target["close"],
                    change_pct=change_pct(target["close"], previous_close),
                    turnover_cny=turnover_cny,
                    provenance=FieldProvenance(
                        price=_PRICE_LINEAGE,
                        turnover=_INDEX_TURNOVER_LINEAGE.get(code),
                    ),
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
        rows = self._stock_daily_series(code, date)
        index = next((i for i, row in enumerate(rows) if row["date"] == date), None)
        if index is None:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                f"stock data not available for {code} on {date}",
            )

        target = rows[index]
        previous_close = rows[index - 1]["close"] if index >= 1 else None
        info = self._security_master_map().get(code, {})

        return StockQuote(
            code=code,
            name=info.get("name"),
            # No stable, non-mixed real sector taxonomy available this round.
            sector_name=None,
            date=date,
            previous_close=previous_close,
            open=target["open"],
            high=target["high"],
            low=target["low"],
            close=target["close"],
            change_pct=change_pct(target["close"], previous_close),
            volume_shares=target["volume_shares"],
            turnover_cny=target["turnover_cny"],
            turnover_rate_pct=target["turnover_rate_pct"],
            lineage=DataLineage(
                library="akshare", source="sina", endpoint="stock_zh_a_daily"
            ),
        )

    def get_stock_history_summary(self, date: str, stock_code: str) -> Dict[str, Any]:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")
        code = self._resolve_stock_code(stock_code)
        rows = [row for row in self._stock_daily_series(code, date) if row["date"] <= date]
        target_index = next((i for i, row in enumerate(rows) if row["date"] == date), None)
        if target_index is None:
            raise MarketError(ErrorCode.DATA_NOT_AVAILABLE, f"stock data not available for {code} on {date}")

        def window_return(window: int) -> Tuple[Optional[float], bool, int]:
            # A W-session return requires W+1 closes: target versus close W
            # completed sessions earlier. Never shorten the window silently.
            start_index = target_index - window
            if start_index < 0:
                return None, False, target_index + 1
            start_close = rows[start_index].get("close")
            end_close = rows[target_index].get("close")
            return change_pct(end_close, start_close), True, window

        r5, c5, n5 = window_return(5)
        r20, c20, n20 = window_return(20)
        return {
            "date": date,
            "stock_code": code,
            "change_pct_5d": r5,
            "change_pct_20d": r20,
            "history_5d_complete": c5,
            "history_20d_complete": c20,
            "sample_count_5d": n5,
            "sample_count_20d": n20,
            "source_family": "sina",
            "lineage": {
                "library": "akshare", "source": "sina", "endpoint": "stock_zh_a_daily"
            },
        }

    def get_market_history_summary(
        self,
        date: str,
        index_codes: Sequence[str],
        total_turnover_codes: Sequence[str],
    ) -> MarketHistorySummary:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        days = self._trading_days_up_to(date)
        if date not in days:
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        # Market total turnover = SSE + SZSE stock turnover only. The ChiNext
        # index is a subset of Shenzhen and is never added.
        window = days[-TURNOVER_LONG:]
        turnover_by_date: Dict[str, float] = {}
        for day in window:
            sse = self._sse_stock_turnover(day)
            szse = self._szse_stock_turnover(day)
            if sse is not None and szse is not None:
                turnover_by_date[day] = sse + szse

        current = turnover_by_date.get(date)
        if current is None:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                f"market turnover not available for {date}",
            )

        previous = turnover_by_date.get(days[-2]) if len(days) >= 2 else None

        def complete_average(periods: int) -> Optional[float]:
            if len(days) < periods:
                return None
            sample = days[-periods:]
            if any(day not in turnover_by_date for day in sample):
                return None
            return mean([turnover_by_date[day] for day in sample])

        avg_5d = complete_average(TURNOVER_SHORT)
        avg_20d = complete_average(TURNOVER_LONG)

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
            closes = [
                row["close"]
                for row in self._index_series(code)
                if row["date"] <= date
            ]
            trends.append(
                IndexTrend(
                    code=code,
                    name=INDEX_NAMES.get(code),
                    change_5d_pct=pct_change_over_closes(closes, INDEX_TREND_SHORT),
                    change_20d_pct=pct_change_over_closes(closes, INDEX_TREND_LONG),
                )
            )

        return MarketHistorySummary(
            turnover=turnover,
            indices=trends,
            lineage=[
                DataLineage(
                    library="akshare",
                    source="sse+szse",
                    endpoint="stock_sse_deal_daily+stock_szse_summary",
                ),
                DataLineage(
                    library="akshare", source="sina", endpoint="stock_zh_index_daily"
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Market breadth / limit ecology (Round 2B)
    # ------------------------------------------------------------------
    def _within_limit_retention(self, date: str) -> bool:
        """Whether ``date`` is inside the Eastmoney limit-pool retention window.

        AkShare refuses dtgc/zbgc older than ``now - 30 calendar days``; we use
        a strict ``>`` so we never trigger that guard, and mark anything older
        as ``OUT_OF_RETENTION`` instead of querying.
        """

        threshold = self._today() - timedelta(days=LIMIT_POOL_RETENTION_CALENDAR_DAYS)
        return _date.fromisoformat(date) > threshold

    def _fetch_pool(
        self, pool: str, date: str
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Fetch one limit pool.

        Returns ``(records, None)`` on success or ``(None, reason)`` when the
        metric is unavailable. An empty upstream response is NEVER treated as
        zero: it yields ``(None, EMPTY_UPSTREAM_RESPONSE)``. Network / schema /
        internal failures propagate as ``MarketError``.
        """

        key = (pool, date)
        if key in self._pool_cache:
            return self._pool_cache[key]

        if not self._within_limit_retention(date):
            result: Tuple[Optional[List[Dict[str, Any]]], Optional[str]] = (
                None,
                REASON_OUT_OF_RETENTION,
            )
        else:
            endpoint = _POOL_ENDPOINTS[pool]
            frame = self._call(endpoint, date=to_provider_date(date))
            self._require_columns(frame, _POOL_REQUIRED_COLUMNS[pool], endpoint)
            records = self._to_records(frame)
            result = (records, None) if records else (None, REASON_EMPTY_UPSTREAM)

        self._pool_cache[key] = result
        return result

    def _pool_count(self, pool: str, date: str) -> Tuple[Optional[int], Optional[str]]:
        records, reason = self._fetch_pool(pool, date)
        if records is None:
            return None, reason
        return len(records), None

    @staticmethod
    def _codes(records: Sequence[Dict[str, Any]]) -> set:
        return {code for code in (_pad_symbol(row.get("代码")) for row in records) if code}

    def _metric_value(self, metric: str, date: str) -> Tuple[Optional[float], Optional[str]]:
        if metric == "limit_up_count":
            return self._pool_count("zt", date)
        if metric == "limit_down_count":
            return self._pool_count("dtgc", date)
        if metric == "broken_limit_count":
            return self._pool_count("zbgc", date)
        if metric == "broken_limit_rate":
            zbgc, zbgc_reason = self._pool_count("zbgc", date)
            zt, zt_reason = self._pool_count("zt", date)
            if zbgc is None or zt is None:
                return None, (zbgc_reason or zt_reason)
            denominator = zbgc + zt
            if denominator == 0:
                return None, None
            return round(zbgc / denominator * 100, 2), None
        if metric in ("first_limit_up_count", "multi_limit_up_count", "max_consecutive_limit_up"):
            records, reason = self._fetch_pool("zt", date)
            if records is None:
                return None, reason
            boards = [
                board
                for board in (_to_int(row.get("连板数")) for row in records)
                if board is not None
            ]
            if not boards:
                return None, REASON_EMPTY_UPSTREAM
            if metric == "first_limit_up_count":
                return sum(1 for board in boards if board == 1), None
            if metric == "multi_limit_up_count":
                return sum(1 for board in boards if board >= 2), None
            return max(boards), None
        if metric == "previous_limit_up_positive_rate":
            records, reason = self._fetch_pool("prev", date)
            if records is None:
                return None, reason
            positive = sum(
                1
                for change in (to_float(row.get("涨跌幅")) for row in records)
                if change is not None and change > 0
            )
            return round(positive / len(records) * 100, 2), None
        if metric == "promotion_rate":
            prev, prev_reason = self._fetch_pool("prev", date)
            zt, zt_reason = self._fetch_pool("zt", date)
            if prev is None or zt is None:
                return None, (prev_reason or zt_reason)
            prev_codes = self._codes(prev)
            if not prev_codes:
                return None, None
            promotion = len(prev_codes & self._codes(zt))
            return round(promotion / len(prev_codes) * 100, 2), None
        return None, REASON_NO_SOURCE

    def _current_breadth(
        self, date: str, missing: Dict[str, str]
    ) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
        """legulegu current snapshot; only valid when ``date`` is the latest session."""

        days = self._trading_days_up_to(self._today().isoformat())
        latest = days[-1] if days else None
        if latest is None or date != latest:
            for field in ("advance_count", "decline_count", "flat_count"):
                missing[field] = REASON_CURRENT_ONLY
            return None, None, None, None

        frame = self._call("stock_market_activity_legu")
        self._require_columns(frame, ("item", "value"), "stock_market_activity_legu")
        mapping: Dict[str, Any] = {}
        for row in self._to_records(frame):
            item = _clean_text(row.get("item"))
            if item is not None:
                mapping[item] = row.get("value")

        raw_as_of = _clean_text(mapping.get("统计日期"))
        as_of = coerce_to_iso_date(raw_as_of[:10]) if raw_as_of else None
        if as_of != date:
            for field in ("advance_count", "decline_count", "flat_count"):
                missing[field] = REASON_CURRENT_ONLY
            return None, None, None, as_of

        return (
            _to_int(mapping.get("上涨")),
            _to_int(mapping.get("下跌")),
            _to_int(mapping.get("平盘")),
            as_of,
        )

    _BREADTH_METRIC_NAMES = (
        "limit_up_count",
        "limit_down_count",
        "broken_limit_count",
        "broken_limit_rate",
        "first_limit_up_count",
        "multi_limit_up_count",
        "max_consecutive_limit_up",
        "previous_limit_up_sample_size",
        "previous_limit_up_average_change_pct",
        "previous_limit_up_median_change_pct",
        "previous_limit_up_positive_rate",
        "promotion_rate",
        "advance_count",
        "decline_count",
        "flat_count",
    )

    def get_market_breadth(self, date: str) -> MarketBreadth:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        missing: Dict[str, str] = {}
        zt, zt_reason = self._fetch_pool("zt", date)
        dtgc, dtgc_reason = self._fetch_pool("dtgc", date)
        zbgc, zbgc_reason = self._fetch_pool("zbgc", date)
        prev, prev_reason = self._fetch_pool("prev", date)

        limit_up = len(zt) if zt is not None else None
        if limit_up is None:
            missing["limit_up_count"] = zt_reason
        limit_down = len(dtgc) if dtgc is not None else None
        if limit_down is None:
            missing["limit_down_count"] = dtgc_reason
        broken = len(zbgc) if zbgc is not None else None
        if broken is None:
            missing["broken_limit_count"] = zbgc_reason

        if zt is not None:
            boards = [
                board
                for board in (_to_int(row.get("连板数")) for row in zt)
                if board is not None
            ]
            first = sum(1 for board in boards if board == 1)
            multi = sum(1 for board in boards if board >= 2)
            max_height = max(boards) if boards else None
            if max_height is None:
                missing["max_limit_height"] = REASON_EMPTY_UPSTREAM
        else:
            first = multi = max_height = None
            for field in (
                "first_limit_up_count",
                "multi_limit_up_count",
                "max_limit_height",
            ):
                missing[field] = zt_reason

        if zbgc is not None and zt is not None:
            denominator = len(zbgc) + len(zt)
            broken_rate = round(len(zbgc) / denominator * 100, 2) if denominator else None
        else:
            broken_rate = None
            missing["broken_limit_rate"] = zbgc_reason or zt_reason

        if prev is not None:
            sample_size = len(prev)
            changes = [
                change
                for change in (to_float(row.get("涨跌幅")) for row in prev)
                if change is not None
            ]
            avg = round(mean(changes), 4) if changes else None
            median = round(_median(changes), 4) if changes else None
            positive = sum(1 for change in changes if change > 0)
            positive_rate = round(positive / sample_size * 100, 2) if sample_size else None
        else:
            sample_size = avg = median = positive_rate = None
            for field in (
                "previous_limit_up_sample_size",
                "previous_limit_up_average_change_pct",
                "previous_limit_up_median_change_pct",
                "previous_limit_up_positive_rate",
            ):
                missing[field] = prev_reason

        if prev is not None and zt is not None:
            prev_codes = self._codes(prev)
            promotion = len(prev_codes & self._codes(zt)) if prev_codes else 0
            promotion_rate = round(promotion / len(prev_codes) * 100, 2) if prev_codes else None
        else:
            promotion_rate = None
            missing["promotion_rate"] = prev_reason or zt_reason

        advance, decline, flat, as_of = self._current_breadth(date, missing)

        definitions = {
            name: METRIC_DEFINITIONS[name] for name in self._BREADTH_METRIC_NAMES
        }

        return MarketBreadth(
            date=date,
            limit=LimitEcology(
                limit_up_count=limit_up,
                limit_down_count=limit_down,
                broken_limit_count=broken,
                broken_limit_rate=broken_rate,
                first_limit_up_count=first,
                multi_limit_up_count=multi,
                max_consecutive_limit_up=max_height,
                previous_sample_size=sample_size,
                previous_average_change_pct=avg,
                previous_median_change_pct=median,
                previous_positive_rate=positive_rate,
                previous_promotion_rate=promotion_rate,
            ),
            advance_count=advance,
            decline_count=decline,
            flat_count=flat,
            breadth_as_of=as_of,
            missing_reasons=missing,
            definitions=definitions,
        )

    def get_limit_up_stocks(self, date: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return date-exact limit-up/continuation candidates from Eastmoney.

        This is a historical short-term-attention fact set, not a popularity
        ranking and not a causal/leader conclusion. Ranking is deterministic:
        consecutive boards desc, turnover desc, code asc.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise MarketError(ErrorCode.INVALID_WINDOW, "limit must be a positive integer")
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, "%s is not a trading day" % date)
        records, reason = self._fetch_pool("zt", date)
        if records is None:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                "limit-up stock pool unavailable for %s: %s" % (date, reason),
            )
        items: List[Dict[str, Any]] = []
        for row in records:
            code = _pad_symbol(row.get("代码"))
            if not code:
                continue
            items.append({
                "date": date,
                "stock_code": code,
                "stock_name": _clean_text(row.get("名称")),
                "change_pct": to_float(row.get("涨跌幅")),
                "consecutive_limit_up": _to_int(row.get("连板数")),
                "turnover_cny": to_float(row.get("成交额")),
                "turnover_rate_pct": to_float(row.get("换手率")),
                "total_market_cap_cny": to_float(row.get("总市值")),
                "circulating_market_cap_cny": to_float(row.get("流通市值")),
                "industry_name": _clean_text(row.get("所属行业")),
                "first_limit_time": _clean_text(row.get("首次封板时间")),
                "last_limit_time": _clean_text(row.get("最后封板时间")),
                "broken_count": _to_int(row.get("炸板次数")),
                "temporal_semantics": "EXACT_TRADING_DATE",
                "source_family": "eastmoney_limit_pool",
                "lineage": {
                    "library": "akshare", "source": "eastmoney",
                    "endpoint": "stock_zt_pool_em",
                },
            })
        items.sort(key=lambda x: (
            -(x.get("consecutive_limit_up") or 0),
            -(x.get("turnover_cny") or 0),
            x.get("stock_code") or "",
        ))
        return items[:limit]

    def get_market_metric_baseline(
        self, date: str, metric: str, window: int
    ) -> MetricBaseline:
        if isinstance(window, bool) or not isinstance(window, int) or window < 1:
            raise MarketError(
                ErrorCode.INVALID_WINDOW,
                f"window must be a positive integer, got {window!r}",
            )
        if metric not in SUPPORTED_BASELINE_METRICS:
            raise MarketError(
                ErrorCode.UNSUPPORTED_METRIC, f"unsupported metric: {metric!r}"
            )
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, f"{date} is not a trading day")

        current, _ = self._metric_value(metric, date)
        if current is None:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                f"metric {metric} not available for {date}",
            )

        # Baseline sample = the ``window`` completed trading days strictly
        # before ``date``. ``current`` never enters its own baseline.
        days = self._trading_days_up_to(date)
        prior = [day for day in days if day < date]
        window_dates = prior[-window:]

        values: List[float] = []
        missing_dates: List[str] = []
        for sample_date in window_dates:
            value, _ = self._metric_value(metric, sample_date)
            if value is None:
                missing_dates.append(sample_date)
            else:
                values.append(value)

        sample_count = len(values)
        complete = len(window_dates) == window and sample_count == window
        if complete:
            avg = round(mean(values), 4)
            median = round(_median(values), 4)
            percentile = round(
                sum(1 for value in values if value <= current) / sample_count * 100, 2
            )
        else:
            # Never shorten the window and relabel it: report Missing instead.
            avg = median = percentile = None

        definition = METRIC_DEFINITIONS[metric]
        return MetricBaseline(
            metric=metric,
            date=date,
            unit=definition.unit,
            window=window,
            current=current,
            avg=avg,
            median=median,
            percentile=percentile,
            sample_count=sample_count,
            complete=complete,
            sample_start=window_dates[0] if window_dates else None,
            sample_end=window_dates[-1] if window_dates else None,
            missing_dates=tuple(missing_dates),
            definition=definition,
        )


    # ------------------------------------------------------------------
    # Sector (Round 5B): THS industry family + Sina membership family
    # ------------------------------------------------------------------
    def _latest_completed_trading_day(self) -> str:
        days = self._trading_days_up_to(self._today().isoformat())
        if not days:
            raise MarketError(ErrorCode.DATA_NOT_AVAILABLE, "no completed trading session")
        return days[-1]

    def _ths_industry_taxonomy(self) -> Dict[str, str]:
        """Map THS industry name -> THS code (stable sector identity)."""

        if self._sector_taxonomy_cache is None:
            frame = self._call("stock_board_industry_name_ths")
            self._require_columns(frame, ("name", "code"), "stock_board_industry_name_ths")
            mapping: Dict[str, str] = {}
            for row in self._to_records(frame):
                name = _clean_text(row.get("name"))
                code = _clean_text(row.get("code"))
                if name and code:
                    mapping[name] = code
            if not mapping:
                raise MarketError(
                    ErrorCode.DATA_NOT_AVAILABLE, "THS industry taxonomy is empty"
                )
            self._sector_taxonomy_cache = mapping
        return self._sector_taxonomy_cache

    def _sector_mapping(self) -> Dict[str, Dict[str, Any]]:
        if self._sector_mapping_cache is None:
            path = Path(__file__).resolve().parent.parent / "domain" / "sector_mapping.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._sector_mapping_cache = data.get("mappings", {})
            except Exception:
                self._sector_mapping_cache = {}
        return self._sector_mapping_cache

    def _resolve_sector_id(self, sector_name: str) -> str:
        taxonomy = self._ths_industry_taxonomy()
        code = taxonomy.get(sector_name)
        if code is None:
            raise MarketError(
                ErrorCode.SECTOR_ID_UNRESOLVED,
                "sector name %r not found in THS industry taxonomy" % sector_name,
            )
        return code

    def get_sector_ranking(
        self, date: str, direction: str = "top", limit: int = 10
    ) -> List[SectorSnapshot]:
        normalized_direction = {"gainers": "top", "losers": "bottom"}.get(
            direction, direction
        )
        if normalized_direction not in ("top", "bottom"):
            raise MarketError(
                ErrorCode.INVALID_DIRECTION,
                "direction must be 'top'/'bottom' (or gainers/losers), got %r" % direction,
            )
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise MarketError(ErrorCode.INVALID_WINDOW, "limit must be a positive integer")
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, "%s is not a trading day" % date)

        latest = self._latest_completed_trading_day()
        taxonomy = self._ths_industry_taxonomy()
        snapshots: List[SectorSnapshot] = []

        if date == latest:
            frame = self._call("stock_board_industry_summary_ths")
            self._require_columns(
                frame, ("板块", "涨跌幅", "总成交额", "上涨家数", "下跌家数"),
                "stock_board_industry_summary_ths",
            )
            lineage = DataLineage(
                library="akshare", source="ths",
                endpoint="stock_board_industry_summary_ths"
            )
            for row in self._to_records(frame):
                name = _clean_text(row.get("板块"))
                if name is None or name not in taxonomy:
                    continue
                snapshots.append(
                    SectorSnapshot(
                        date=date, sector_id=taxonomy[name], sector_name=name,
                        taxonomy="industry", source_family="ths",
                        change_pct=to_float(row.get("涨跌幅")),
                        turnover_cny=yi_yuan_to_cny(row.get("总成交额")),
                        up_count=_to_int(row.get("上涨家数")),
                        down_count=_to_int(row.get("下跌家数")),
                        flat_count=None, constituent_count=None,
                        date_semantics="CURRENT_ONLY", lineage=lineage,
                    )
                )
        else:
            # Reconstruct the historical cross-section from THS industry-index
            # history. We require the target session and its immediately
            # preceding trading session; no current snapshot is substituted.
            trading_days = self._trading_days_up_to(date)
            if len(trading_days) < 2:
                raise MarketError(
                    ErrorCode.DATA_NOT_AVAILABLE,
                    "no previous trading session for historical sector ranking",
                )
            previous = trading_days[-2]
            start_date = to_provider_date(shift_calendar_days(previous, -3))
            end_date = to_provider_date(date)
            lineage = DataLineage(
                library="akshare", source="ths",
                endpoint="stock_board_industry_index_ths"
            )
            for name, sector_id in taxonomy.items():
                try:
                    frame = self._call(
                        "stock_board_industry_index_ths", symbol=name,
                        start_date=start_date, end_date=end_date,
                    )
                    self._require_columns(
                        frame, ("日期", "收盘价", "成交额"),
                        "stock_board_industry_index_ths",
                    )
                except MarketError:
                    # One unavailable industry must not manufacture a value or
                    # erase the independently observable industries.
                    continue
                by_date: Dict[str, Dict[str, Any]] = {}
                for row in self._to_records(frame):
                    iso = coerce_to_iso_date(row.get("日期"))
                    if iso in (previous, date):
                        by_date[iso] = row
                if previous not in by_date or date not in by_date:
                    continue
                prev_close = to_float(by_date[previous].get("收盘价"))
                close = to_float(by_date[date].get("收盘价"))
                if prev_close in (None, 0) or close is None:
                    continue
                snapshots.append(
                    SectorSnapshot(
                        date=date, sector_id=sector_id, sector_name=name,
                        taxonomy="industry", source_family="ths",
                        change_pct=round((close / prev_close - 1) * 100, 2),
                        turnover_cny=to_float(by_date[date].get("成交额")),
                        up_count=None, down_count=None, flat_count=None,
                        constituent_count=None,
                        date_semantics="HISTORICAL_RECONSTRUCTED",
                        lineage=lineage,
                    )
                )

        if not snapshots:
            raise MarketError(
                ErrorCode.EMPTY_UPSTREAM_RESPONSE,
                "THS industry ranking has no observable sectors for %s" % date,
            )
        snapshots.sort(
            key=lambda item: (
                item.change_pct if item.change_pct is not None else float("-inf")
            ),
            reverse=(normalized_direction == "top"),
        )
        return snapshots[:limit]

    def get_sector_history_summary(self, date: str, sector_name: str) -> SectorHistorySummary:
        if not self.is_trading_day(date):
            raise MarketError(ErrorCode.NOT_TRADING_DAY, "%s is not a trading day" % date)
        sector_id = self._resolve_sector_id(sector_name)
        start = to_provider_date(shift_calendar_days(date, -LOOKBACK_CALENDAR_DAYS))
        end = to_provider_date(date)
        frame = self._call(
            "stock_board_industry_index_ths",
            symbol=sector_name,
            start_date=start,
            end_date=end,
        )
        self._require_columns(
            frame, ("日期", "收盘价", "成交额"), "stock_board_industry_index_ths"
        )
        rows: List[Dict[str, Any]] = []
        for row in self._to_records(frame):
            iso = coerce_to_iso_date(row.get("日期"))
            if iso is None or iso > date:
                continue
            rows.append(
                {
                    "date": iso,
                    "close": to_float(row.get("收盘价")),
                    "turnover_cny": to_float(row.get("成交额")),
                }
            )
        rows.sort(key=lambda item: item["date"])
        if not rows or rows[-1]["date"] != date:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                "sector index does not cover %s for %s" % (date, sector_name),
            )

        closes = [item["close"] for item in rows]
        turnovers = [item["turnover_cny"] for item in rows]

        def change_pct_over(periods: int) -> Optional[float]:
            if len(closes) < periods:
                return None
            base = closes[-periods]
            if base is None or closes[-1] is None or base == 0:
                return None
            return round((closes[-1] / base - 1) * 100, 2)

        def avg_over(periods: int) -> Optional[float]:
            if len(turnovers) < periods:
                return None
            return mean(turnovers[-periods:])

        return SectorHistorySummary(
            date=date,
            sector_id=sector_id,
            sector_name=sector_name,
            taxonomy="industry",
            source_family="ths",
            change_pct_5d=change_pct_over(INDEX_TREND_SHORT),
            change_pct_20d=change_pct_over(INDEX_TREND_LONG),
            turnover_cny=turnovers[-1],
            turnover_avg_5d_cny=avg_over(TURNOVER_SHORT),
            turnover_avg_20d_cny=avg_over(TURNOVER_LONG),
            history_5d_complete=len(rows) >= INDEX_TREND_SHORT,
            history_20d_complete=len(rows) >= INDEX_TREND_LONG,
            sample_count_5d=min(len(rows), INDEX_TREND_SHORT),
            sample_count_20d=min(len(rows), INDEX_TREND_LONG),
            lineage=DataLineage(
                library="akshare", source="ths", endpoint="stock_board_industry_index_ths"
            ),
        )

    @staticmethod
    def _ths_amount_to_cny(value: Any) -> Optional[float]:
        """Parse THS human-readable CNY amounts without inventing units."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text or text in ("--", "-", "None", "nan"):
            return None
        multipliers = {"万": 10_000.0, "亿": 100_000_000.0}
        suffix = text[-1]
        multiplier = multipliers.get(suffix, 1.0)
        if suffix in multipliers:
            text = text[:-1]
        try:
            return float(text) * multiplier
        except (TypeError, ValueError):
            return None

    def _get_ths_sector_membership(
        self, sector_name: str, sector_id: str
    ) -> Optional[SectorMembershipSnapshot]:
        """Use the same THS taxonomy as ranking/history when the client exposes it.

        Some AkShare releases do not export stock_board_industry_cons_ths.
        Absence of the endpoint is a compatibility condition, not permission to
        fabricate a cross-taxonomy mapping; the caller may use the explicitly
        VERIFIED Sina fallback below.
        """
        if getattr(self._client, "stock_board_industry_cons_ths", None) is None:
            return None
        frame = self._call("stock_board_industry_cons_ths", symbol=sector_name)
        self._require_columns(
            frame,
            ("代码", "名称", "涨跌幅", "换手", "成交额"),
            "stock_board_industry_cons_ths",
        )
        members: List[SectorMember] = []
        for row in self._to_records(frame):
            code = _pad_symbol(row.get("代码"))
            if code is None:
                continue
            members.append(
                SectorMember(
                    stock_code=code,
                    stock_name=_clean_text(row.get("名称")),
                    change_pct=to_float(row.get("涨跌幅")),
                    turnover_cny=self._ths_amount_to_cny(row.get("成交额")),
                    turnover_rate_pct=to_float(row.get("换手")),
                    # Keep total and circulating market cap semantically
                    # separate. Circulating cap can be used only as a lower
                    # bound for total cap (circulating <= total).
                    market_cap_cny=None,
                    circulating_market_cap_cny=self._ths_amount_to_cny(
                        row.get("流通市值")
                    ),
                )
            )
        if not members:
            raise MarketError(
                ErrorCode.EMPTY_UPSTREAM_RESPONSE,
                "THS membership for %s is empty" % sector_name,
            )
        return SectorMembershipSnapshot(
            date=self._latest_completed_trading_day(),
            sector_id=sector_id,
            sector_name=sector_name,
            taxonomy="industry",
            source_family="ths",
            membership_semantics="CURRENT_MEMBERSHIP_ONLY",
            stocks=members,
            lineage=DataLineage(
                library="akshare", source="ths",
                endpoint="stock_board_industry_cons_ths"
            ),
        )

    def get_sector_membership(self, sector_name: str) -> SectorMembershipSnapshot:
        sector_id = self._resolve_sector_id(sector_name)

        # Preferred path: ranking, history and membership all share THS
        # taxonomy, eliminating the old cross-provider identity problem.
        ths_membership = self._get_ths_sector_membership(sector_name, sector_id)
        if ths_membership is not None:
            return ths_membership

        # Compatibility fallback for AkShare builds where THS constituents are
        # not exported. Only an explicitly VERIFIED THS->Sina mapping is legal.
        mapping = self._sector_mapping().get("ths:%s" % sector_id)
        if not mapping or mapping.get("mapping_status") != "VERIFIED":
            raise MarketError(
                ErrorCode.SECTOR_MEMBERSHIP_UNAVAILABLE,
                "THS constituent endpoint unavailable and no VERIFIED THS->Sina "
                "membership mapping for %s (ths:%s)" % (sector_name, sector_id),
            )
        label = mapping["sina_sector_label"]
        frame = self._call("stock_sector_detail", sector=label)
        self._require_columns(
            frame,
            ("code", "name", "changepercent", "amount", "turnoverratio", "mktcap"),
            "stock_sector_detail",
        )
        members: List[SectorMember] = []
        for row in self._to_records(frame):
            code = _clean_text(row.get("code"))
            if code is None:
                continue
            market_cap = to_float(row.get("mktcap"))
            members.append(
                SectorMember(
                    stock_code=code,
                    stock_name=_clean_text(row.get("name")),
                    change_pct=to_float(row.get("changepercent")),
                    turnover_cny=to_float(row.get("amount")),
                    turnover_rate_pct=to_float(row.get("turnoverratio")),
                    market_cap_cny=wan_yuan_to_cny(market_cap),
                )
            )
        if not members:
            raise MarketError(
                ErrorCode.EMPTY_UPSTREAM_RESPONSE,
                "Sina membership for %s is empty" % label,
            )
        return SectorMembershipSnapshot(
            date=self._latest_completed_trading_day(),
            sector_id=sector_id,
            sector_name=sector_name,
            taxonomy="industry",
            source_family="sina",
            membership_semantics="CURRENT_MEMBERSHIP_ONLY",
            stocks=members,
            lineage=DataLineage(
                library="akshare", source="sina", endpoint="stock_sector_detail"
            ),
        )

    def get_stock_disclosures(
        self, date: str, stock_code: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Official company disclosures for one calendar date.

        Prefer CNINFO information disclosure. If the installed AkShare build
        does not expose that endpoint, use Eastmoney's individual notice
        endpoint as an explicit compatibility fallback. A disclosure is event
        evidence only; it is never labelled as a price-move cause here.
        """
        symbol = _pad_symbol(stock_code)
        if symbol is None:
            raise MarketError(
                ErrorCode.INVALID_STOCK_CODE, "invalid stock code: %s" % stock_code
            )
        compact = date.replace("-", "")
        if getattr(self._client, "stock_zh_a_disclosure_report_cninfo", None) is not None:
            frame = self._call(
                "stock_zh_a_disclosure_report_cninfo",
                symbol=symbol, market="沪深京", keyword="", category="",
                start_date=compact, end_date=compact,
            )
            self._require_columns(
                frame, ("代码", "简称", "公告标题", "公告时间", "公告链接"),
                "stock_zh_a_disclosure_report_cninfo",
            )
            source, endpoint = "cninfo", "stock_zh_a_disclosure_report_cninfo"
            items = [{
                "published_at": _clean_text(row.get("公告时间")),
                "source": "巨潮资讯",
                "title": _clean_text(row.get("公告标题")),
                "category": None,
                "url": _clean_text(row.get("公告链接")),
                "lineage": {"library": "akshare", "source": source, "endpoint": endpoint},
            } for row in self._to_records(frame)]
        elif getattr(self._client, "stock_individual_notice_report", None) is not None:
            frame = self._call(
                "stock_individual_notice_report", security=symbol, symbol="全部",
                begin_date=compact, end_date=compact,
            )
            self._require_columns(
                frame, ("代码", "名称", "公告标题", "公告类型", "公告日期", "网址"),
                "stock_individual_notice_report",
            )
            source, endpoint = "eastmoney", "stock_individual_notice_report"
            items = [{
                "published_at": _clean_text(row.get("公告日期")),
                "source": "东方财富公告",
                "title": _clean_text(row.get("公告标题")),
                "category": _clean_text(row.get("公告类型")),
                "url": _clean_text(row.get("网址")),
                "lineage": {"library": "akshare", "source": source, "endpoint": endpoint},
            } for row in self._to_records(frame)]
        else:
            raise MarketError(
                ErrorCode.DATA_NOT_AVAILABLE,
                "installed AkShare exposes no supported stock disclosure endpoint",
            )
        items = [x for x in items if x.get("title")]
        items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        return items[:limit]

    def get_stock_news(self, date: str, stock_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Eastmoney latest stock-news facts filtered to the requested calendar date.

        The upstream endpoint exposes only a recent rolling window. An empty
        filtered result means "no item observed in returned window", never
        "no news existed".
        """

        symbol = _pad_symbol(stock_code)
        if symbol is None:
            raise MarketError(
                ErrorCode.INVALID_STOCK_CODE, "invalid stock code: %s" % stock_code
            )
        frame = self._call("stock_news_em", symbol=symbol)
        self._require_columns(
            frame,
            ("新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"),
            "stock_news_em",
        )
        items: List[Dict[str, Any]] = []
        for row in self._to_records(frame):
            published = _clean_text(row.get("发布时间"))
            if not published:
                continue
            # AkShare currently returns an ISO-like datetime string. Keep the
            # original timestamp and use only its date prefix for filtering.
            if published[:10] != date:
                continue
            items.append({
                "published_at": published,
                "source": _clean_text(row.get("文章来源")),
                "title": _clean_text(row.get("新闻标题")),
                "summary": _clean_text(row.get("新闻内容")),
                "url": _clean_text(row.get("新闻链接")),
                "lineage": {
                    "library": "akshare",
                    "source": "eastmoney",
                    "endpoint": "stock_news_em",
                },
            })
        items.sort(key=lambda item: item.get("published_at") or "", reverse=True)
        return items[:limit]