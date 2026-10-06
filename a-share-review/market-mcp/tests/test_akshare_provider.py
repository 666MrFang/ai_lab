"""AkShare provider tests using an injected fake client (no network).

Every upstream response is a fixture DataFrame that mirrors the columns and
units observed live during the capability probe. The fake client deliberately
ignores date ranges in some places to verify the provider's defensive as-of
filtering.
"""

import datetime as dt
import unittest

import pandas as pd

from domain.reference import INDEX_CODES, TOTAL_TURNOVER_CODES
from errors import ErrorCode, MarketError
from providers.akshare_provider import AkShareProvider

STOCK_COLUMNS = [
    "date", "open", "high", "low", "close",
    "volume", "amount", "outstanding_share", "turnover",
]
INDEX_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
SSE_COLUMNS = ["单日情况", "股票", "主板A", "主板B", "科创板", "股票回购"]
SZSE_COLUMNS = ["证券类别", "数量", "成交金额", "总市值", "流通市值"]
SH_COLUMNS = ["证券代码", "证券简称", "证券全称", "公司简称", "公司全称", "上市日期"]
SZ_COLUMNS = [
    "板块", "A股代码", "A股简称", "A股上市日期",
    "A股总股本", "A股流通股本", "所属行业",
]


def _d(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def stock_frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=STOCK_COLUMNS)


def index_frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=INDEX_COLUMNS)


def sse_frame(amount_yi) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"单日情况": "成交金额", "股票": amount_yi, "主板A": 0, "主板B": 0,
             "科创板": 0, "股票回购": 0},
            {"单日情况": "市价总值", "股票": 1, "主板A": 0, "主板B": 0,
             "科创板": 0, "股票回购": 0},
        ],
        columns=SSE_COLUMNS,
    )


def szse_frame(amount_cny) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"证券类别": "股票", "数量": 1, "成交金额": amount_cny,
             "总市值": 1, "流通市值": 1},
            {"证券类别": "主板A股", "数量": 1, "成交金额": 0.0,
             "总市值": 1, "流通市值": 1},
        ],
        columns=SZSE_COLUMNS,
    )


def three_index_frames():
    return {
        "sh000001": index_frame([
            {"date": _d("2026-09-29"), "open": 3790, "high": 3810,
             "low": 3780, "close": 3800, "volume": 1},
            {"date": _d("2026-09-30"), "open": 3801, "high": 3850,
             "low": 3799, "close": 3842, "volume": 1},
        ]),
        "sz399001": index_frame([
            {"date": _d("2026-09-29"), "open": 13000, "high": 13100,
             "low": 12900, "close": 13000, "volume": 1},
            {"date": _d("2026-09-30"), "open": 13010, "high": 13200,
             "low": 13000, "close": 13100, "volume": 1},
        ]),
        "sz399006": index_frame([
            {"date": _d("2026-09-29"), "open": 2800, "high": 2820,
             "low": 2790, "close": 2800, "volume": 1},
            {"date": _d("2026-09-30"), "open": 2801, "high": 2860,
             "low": 2799, "close": 2850, "volume": 1},
        ]),
    }


class FakeAkShareClient:
    def __init__(
        self,
        trade_dates=(),
        stock_frames=None,
        index_frames=None,
        sse=None,
        szse=None,
        sh_main=None,
        sh_star=None,
        sz=None,
    ):
        self._trade_dates = list(trade_dates)
        self._stock_frames = stock_frames or {}
        self._index_frames = index_frames or {}
        self._sse = sse or {}
        self._szse = szse or {}
        self._sh_main = sh_main if sh_main is not None else self._default_sh()
        self._sh_star = sh_star if sh_star is not None else self._default_sh(star=True)
        self._sz = sz if sz is not None else self._default_sz()

    @staticmethod
    def _default_sh(star: bool = False) -> pd.DataFrame:
        code, name = ("688981", "中芯国际") if star else ("600519", "贵州茅台")
        return pd.DataFrame(
            [{"证券代码": code, "证券简称": name, "证券全称": name,
              "公司简称": name, "公司全称": name, "上市日期": _d("2001-08-27")}],
            columns=SH_COLUMNS,
        )

    @staticmethod
    def _default_sz() -> pd.DataFrame:
        return pd.DataFrame(
            [{"板块": "主板", "A股代码": "000001", "A股简称": "平安银行",
              "A股上市日期": _d("1991-04-03"), "A股总股本": 1,
              "A股流通股本": 1, "所属行业": "J 金融业"}],
            columns=SZ_COLUMNS,
        )

    # akshare-like surface
    def tool_trade_date_hist_sina(self) -> pd.DataFrame:
        return pd.DataFrame({"trade_date": [_d(day) for day in self._trade_dates]})

    def stock_zh_a_daily(self, symbol=None, start_date=None, end_date=None, adjust=None):
        assert adjust == "", "provider must request raw (unadjusted) prices"
        frame = self._stock_frames.get(symbol)
        return frame if frame is not None else pd.DataFrame(columns=STOCK_COLUMNS)

    def stock_zh_index_daily(self, symbol=None) -> pd.DataFrame:
        frame = self._index_frames.get(symbol)
        return frame if frame is not None else pd.DataFrame(columns=INDEX_COLUMNS)

    def stock_sse_deal_daily(self, date=None) -> pd.DataFrame:
        frame = self._sse.get(date)
        return frame if frame is not None else pd.DataFrame(columns=SSE_COLUMNS)

    def stock_szse_summary(self, date=None) -> pd.DataFrame:
        frame = self._szse.get(date)
        return frame if frame is not None else pd.DataFrame(columns=SZSE_COLUMNS)

    def stock_info_sh_name_code(self, symbol="主板A股") -> pd.DataFrame:
        return self._sh_star if symbol == "科创板" else self._sh_main

    def stock_info_sz_name_code(self, symbol="A股列表") -> pd.DataFrame:
        return self._sz


class StockDetailTest(unittest.TestCase):
    def _provider(self, **kwargs):
        rows = kwargs.pop(
            "rows",
            [
                {"date": _d("2026-09-29"), "open": 99, "high": 101, "low": 98,
                 "close": 100, "volume": 500, "amount": 4_000_000,
                 "outstanding_share": 1000, "turnover": 0.005},
                {"date": _d("2026-09-30"), "open": 101, "high": 103, "low": 100,
                 "close": 102, "volume": 1000, "amount": 5_000_000,
                 "outstanding_share": 1000, "turnover": 0.01},
            ],
        )
        client = FakeAkShareClient(
            trade_dates=["2026-09-29", "2026-09-30"],
            stock_frames={"sh600519": stock_frame(rows), **kwargs.pop("stock_frames", {})},
            **kwargs,
        )
        return AkShareProvider(client=client)

    def test_units_and_derived_fields(self):
        quote = self._provider().get_stock_detail("2026-09-30", "600519.SH")
        self.assertEqual(quote.code, "600519.SH")
        self.assertEqual(quote.name, "贵州茅台")
        self.assertIsNone(quote.sector_name)
        self.assertEqual(quote.previous_close, 100.0)
        self.assertEqual(quote.open, 101.0)
        self.assertEqual(quote.close, 102.0)
        self.assertEqual(quote.change_pct, 2.0)  # (102/100 - 1) * 100
        self.assertEqual(quote.volume_shares, 1000.0)  # shares, unchanged
        self.assertEqual(quote.turnover_cny, 5_000_000.0)  # CNY, unchanged
        self.assertEqual(quote.turnover_rate_pct, 1.0)  # 0.01 ratio -> 1.0%

    def test_bare_symbol_resolved_via_security_master(self):
        quote = self._provider().get_stock_detail("2026-09-30", "600519")
        self.assertEqual(quote.code, "600519.SH")

    def test_unknown_code_rejected(self):
        with self.assertRaises(MarketError) as ctx:
            self._provider().get_stock_detail("2026-09-30", "111111.SH")
        self.assertEqual(ctx.exception.error_code, ErrorCode.INVALID_STOCK_CODE)

    def test_not_trading_day(self):
        with self.assertRaises(MarketError) as ctx:
            self._provider().get_stock_detail("2026-10-01", "600519.SH")
        self.assertEqual(ctx.exception.error_code, ErrorCode.NOT_TRADING_DAY)

    def test_missing_values_stay_none(self):
        rows = [
            {"date": _d("2026-09-29"), "open": 99, "high": 101, "low": 98,
             "close": 100, "volume": 500, "amount": 4_000_000,
             "outstanding_share": 1000, "turnover": 0.005},
            {"date": _d("2026-09-30"), "open": 101, "high": 103, "low": 100,
             "close": 102, "volume": float("nan"), "amount": float("nan"),
             "outstanding_share": 1000, "turnover": None},
        ]
        quote = self._provider(rows=rows).get_stock_detail("2026-09-30", "600519.SH")
        self.assertIsNone(quote.volume_shares)
        self.assertIsNone(quote.turnover_cny)
        self.assertIsNone(quote.turnover_rate_pct)

    def test_future_rows_do_not_leak(self):
        rows = [
            {"date": _d("2026-09-29"), "open": 99, "high": 101, "low": 98,
             "close": 100, "volume": 500, "amount": 4_000_000,
             "outstanding_share": 1000, "turnover": 0.005},
            {"date": _d("2026-09-30"), "open": 101, "high": 103, "low": 100,
             "close": 102, "volume": 1000, "amount": 5_000_000,
             "outstanding_share": 1000, "turnover": 0.01},
            {"date": _d("2026-10-08"), "open": 999, "high": 999, "low": 999,
             "close": 999, "volume": 0, "amount": 0,
             "outstanding_share": 1000, "turnover": 0.0},
        ]
        quote = self._provider(rows=rows).get_stock_detail("2026-09-30", "600519.SH")
        self.assertEqual(quote.previous_close, 100.0)  # 09-29, not 10-08
        self.assertEqual(quote.close, 102.0)

    def test_missing_expected_column_is_schema_changed(self):
        bad = pd.DataFrame(
            [{"date": _d("2026-09-30"), "open": 1, "high": 1, "low": 1,
              "close": 1, "volume": 1, "amount": 1, "outstanding_share": 1}],
            columns=["date", "open", "high", "low", "close", "volume",
                     "amount", "outstanding_share"],
        )
        provider = self._provider(stock_frames={"sh600519": bad})
        with self.assertRaises(MarketError) as ctx:
            provider.get_stock_detail("2026-09-30", "600519.SH")
        self.assertEqual(ctx.exception.error_code, ErrorCode.UPSTREAM_SCHEMA_CHANGED)

    def test_data_not_available_when_no_row(self):
        provider = self._provider(stock_frames={"sh600519": stock_frame([])})
        with self.assertRaises(MarketError) as ctx:
            provider.get_stock_detail("2026-09-30", "600519.SH")
        self.assertEqual(ctx.exception.error_code, ErrorCode.DATA_NOT_AVAILABLE)


class IndexPerformanceTest(unittest.TestCase):
    def _provider(self):
        return AkShareProvider(
            client=FakeAkShareClient(
                trade_dates=["2026-09-29", "2026-09-30"],
                index_frames=three_index_frames(),
                sse={"20260930": sse_frame(6800.23)},
                szse={"20260930": szse_frame(759_333_800_000.0)},
            )
        )

    def test_index_units_and_turnover_sources(self):
        quotes = self._provider().get_index_performance("2026-09-30", list(INDEX_CODES))
        by_code = {quote.code: quote for quote in quotes}

        sh = by_code["000001.SH"]
        self.assertEqual(sh.previous_close, 3800.0)
        self.assertEqual(sh.close, 3842.0)
        self.assertEqual(sh.change_pct, round((3842 / 3800 - 1) * 100, 2))
        self.assertEqual(sh.turnover_cny, 6800.23 * 1e8)  # 亿元 -> 元

        sz = by_code["399001.SZ"]
        self.assertEqual(sz.turnover_cny, 759_333_800_000.0)  # already 元

        self.assertIsNone(by_code["399006.SZ"].turnover_cny)  # no independent ChiNext

    def test_index_not_trading_day(self):
        with self.assertRaises(MarketError) as ctx:
            self._provider().get_index_performance("2026-10-01", list(INDEX_CODES))
        self.assertEqual(ctx.exception.error_code, ErrorCode.NOT_TRADING_DAY)

    # --- DATA-F001: field-level provenance ---------------------------------
    def test_price_and_turnover_provenance_are_distinct(self):
        quotes = self._provider().get_index_performance("2026-09-30", list(INDEX_CODES))
        by_code = {quote.code: quote for quote in quotes}

        for code in INDEX_CODES:
            prov = by_code[code].provenance
            self.assertEqual(prov.price.source, "sina")
            self.assertEqual(prov.price.endpoint, "stock_zh_index_daily")

        sh_prov = by_code["000001.SH"].provenance
        self.assertEqual(sh_prov.turnover.source, "sse")
        self.assertEqual(sh_prov.turnover.endpoint, "stock_sse_deal_daily")

        sz_prov = by_code["399001.SZ"].provenance
        self.assertEqual(sz_prov.turnover.source, "szse")
        self.assertEqual(sz_prov.turnover.endpoint, "stock_szse_summary")

        cy_prov = by_code["399006.SZ"].provenance
        self.assertEqual(cy_prov.price.source, "sina")
        self.assertIsNone(cy_prov.turnover)  # unsupported independent turnover

    # --- DATA-F002: upstream failure must propagate -------------------------
    def test_sse_network_error_propagates(self):
        class BoomSSE(FakeAkShareClient):
            def stock_sse_deal_daily(self, date=None):
                raise ConnectionError("Max retries exceeded with url /api/qt")

        client = BoomSSE(
            trade_dates=["2026-09-29", "2026-09-30"],
            index_frames=three_index_frames(),
            szse={"20260930": szse_frame(1.0)},
        )
        provider = AkShareProvider(client=client)
        with self.assertRaises(MarketError) as ctx:
            provider.get_index_performance("2026-09-30", ["000001.SH"])
        self.assertEqual(ctx.exception.error_code, ErrorCode.NETWORK_ERROR)

    def test_sse_schema_change_propagates(self):
        bad = pd.DataFrame(
            [{"单日情况": "成交金额", "主板A": 1.0}], columns=["单日情况", "主板A"]
        )
        provider = AkShareProvider(
            client=FakeAkShareClient(
                trade_dates=["2026-09-29", "2026-09-30"],
                index_frames=three_index_frames(),
                sse={"20260930": bad},
                szse={"20260930": szse_frame(1.0)},
            )
        )
        with self.assertRaises(MarketError) as ctx:
            provider.get_index_performance("2026-09-30", ["000001.SH"])
        self.assertEqual(ctx.exception.error_code, ErrorCode.UPSTREAM_SCHEMA_CHANGED)

    def test_unsupported_chinext_turnover_does_not_call_exchange(self):
        class ExplodingSSE(FakeAkShareClient):
            def stock_sse_deal_daily(self, date=None):
                raise AssertionError("SSE must not be called for ChiNext turnover")

        client = ExplodingSSE(
            trade_dates=["2026-09-29", "2026-09-30"],
            index_frames=three_index_frames(),
        )
        provider = AkShareProvider(client=client)
        quotes = provider.get_index_performance("2026-09-30", ["399006.SZ"])
        self.assertIsNone(quotes[0].turnover_cny)
        self.assertIsNone(quotes[0].provenance.turnover)


def _history_days(n: int):
    return [f"2026-09-{i:02d}" for i in range(1, n + 1)]


class MarketHistorySummaryTest(unittest.TestCase):
    def _provider(self, n_days: int, with_turnover: bool = True):
        days = _history_days(n_days)
        index_frames = {}
        for code, sina in (
            ("000001.SH", "sh000001"),
            ("399001.SZ", "sz399001"),
            ("399006.SZ", "sz399006"),
        ):
            index_frames[sina] = index_frame([
                {"date": _d(day), "open": 100 + i, "high": 100 + i,
                 "low": 100 + i, "close": 100 + i, "volume": 1}
                for i, day in enumerate(days)
            ])
        sse, szse = {}, {}
        if with_turnover:
            for i, day in enumerate(days):
                compact = day.replace("-", "")
                sse[compact] = sse_frame(100 + i)  # 亿元
                szse[compact] = szse_frame(float((100 + i) * 1e8))  # 元
        return AkShareProvider(
            client=FakeAkShareClient(
                trade_dates=days,
                index_frames=index_frames,
                sse=sse,
                szse=szse,
            )
        ), days

    def test_sse_plus_szse_total(self):
        provider, days = self._provider(25)
        summary = provider.get_market_history_summary(
            days[-1], INDEX_CODES, TOTAL_TURNOVER_CODES
        )
        # day i: (100+i)亿 + (100+i)亿 = 2*(100+i)*1e8 元
        expected_current = 2 * (100 + 24) * 1e8
        self.assertEqual(summary.turnover.current_cny, expected_current)
        expected_previous = 2 * (100 + 23) * 1e8
        self.assertEqual(summary.turnover.previous_cny, expected_previous)
        self.assertEqual(
            summary.turnover.avg_5d_cny,
            sum(2 * (100 + i) * 1e8 for i in range(20, 25)) / 5,
        )
        self.assertEqual(
            summary.turnover.avg_20d_cny,
            sum(2 * (100 + i) * 1e8 for i in range(5, 25)) / 20,
        )
        # exactly SSE + SZSE, no ChiNext double count
        self.assertEqual(
            summary.turnover.current_cny,
            124.0 * 1e8 + 124.0 * 1e8,
        )

    def test_incomplete_20d_window_is_not_faked(self):
        provider, days = self._provider(10)
        summary = provider.get_market_history_summary(
            days[-1], INDEX_CODES, TOTAL_TURNOVER_CODES
        )
        self.assertIsNotNone(summary.turnover.avg_5d_cny)
        self.assertIsNone(summary.turnover.avg_20d_cny)
        self.assertIsNone(summary.turnover.vs_20d_pct)

    def test_missing_current_turnover_is_data_not_available(self):
        provider, days = self._provider(25, with_turnover=False)
        with self.assertRaises(MarketError) as ctx:
            provider.get_market_history_summary(
                days[-1], INDEX_CODES, TOTAL_TURNOVER_CODES
            )
        self.assertEqual(ctx.exception.error_code, ErrorCode.DATA_NOT_AVAILABLE)

    def test_history_excludes_future_index_rows(self):
        days = _history_days(25)
        future_day = "2026-10-08"
        index_frames = {}
        for code, sina in (
            ("000001.SH", "sh000001"),
            ("399001.SZ", "sz399001"),
            ("399006.SZ", "sz399006"),
        ):
            rows = [
                {"date": _d(day), "open": 100 + i, "high": 100 + i,
                 "low": 100 + i, "close": 100 + i, "volume": 1}
                for i, day in enumerate(days)
            ]
            rows.append(
                {"date": _d(future_day), "open": 9999, "high": 9999,
                 "low": 9999, "close": 9999, "volume": 1}
            )
            index_frames[sina] = index_frame(rows)
        sse = {day.replace("-", ""): sse_frame(100 + i) for i, day in enumerate(days)}
        szse = {day.replace("-", ""): szse_frame(float((100 + i) * 1e8))
                for i, day in enumerate(days)}
        provider = AkShareProvider(
            client=FakeAkShareClient(
                trade_dates=days, index_frames=index_frames, sse=sse, szse=szse
            )
        )
        summary = provider.get_market_history_summary(
            days[-1], INDEX_CODES, TOTAL_TURNOVER_CODES
        )
        # close[-1] must be days[-1] close (124), never the future 9999.
        self.assertEqual(summary.indices[0].change_5d_pct,
                         round((124 / 119 - 1) * 100, 2))


if __name__ == "__main__":
    unittest.main()
