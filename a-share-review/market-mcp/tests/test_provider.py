"""Provider tests using an injected fake Tushare client (no network)."""

import unittest

from domain.reference import INDEX_CODES, TOTAL_TURNOVER_CODES
from errors import ErrorCode, MarketError
from providers.tushare_provider import TushareProvider


class FakeClient:
    """Mimics the subset of the Tushare Pro client used by the provider.

    ``index_daily`` deliberately ignores the requested date range to verify the
    provider's defensive as-of filtering.
    """

    def __init__(self, open_days=(), index_rows=None, stock_rows=None,
                 basic_rows=None, security_master=None):
        self.open_days = set(open_days)
        self.index_rows = index_rows or []
        self.stock_rows = stock_rows or []
        self.basic_rows = basic_rows or []
        self.security_master = security_master or []

    def trade_cal(self, exchange=None, start_date=None, end_date=None, is_open=None, **kwargs):
        return [
            {"cal_date": day, "is_open": "1"}
            for day in self.open_days
            if (start_date is None or start_date <= day) and (end_date is None or day <= end_date)
        ]

    def index_daily(self, ts_code=None, start_date=None, end_date=None, **kwargs):
        return [row for row in self.index_rows if row.get("ts_code") == ts_code]

    def daily(self, ts_code=None, **kwargs):
        return [row for row in self.stock_rows if row.get("ts_code") == ts_code]

    def daily_basic(self, ts_code=None, fields=None, **kwargs):
        return [row for row in self.basic_rows if row.get("ts_code") == ts_code]

    def stock_basic(self, exchange="", list_status="L", fields=None, **kwargs):
        return list(self.security_master)


class IndexPerformanceTest(unittest.TestCase):
    def test_units_and_fields(self):
        client = FakeClient(
            open_days={"20261008"},
            index_rows=[
                {
                    "ts_code": "000001.SH",
                    "trade_date": "20261008",
                    "open": "3900",
                    "high": "3920",
                    "low": "3890",
                    "close": "3915",
                    "pre_close": "3880",
                    "pct_chg": "0.90",
                    "vol": "1",
                    "amount": "620000000",
                }
            ],
        )
        provider = TushareProvider(client=client)
        quotes = provider.get_index_performance("2026-10-08", ["000001.SH"])
        quote = quotes[0]
        self.assertEqual(quote.code, "000001.SH")
        self.assertEqual(quote.turnover_cny, 620_000_000_000.0)  # 千元 -> 元
        self.assertEqual(quote.previous_close, 3880.0)
        self.assertEqual(quote.change_pct, 0.9)  # percent unchanged

    def test_not_trading_day(self):
        provider = TushareProvider(client=FakeClient(open_days=set()))
        with self.assertRaises(MarketError) as ctx:
            provider.get_index_performance("2026-10-05", ["000001.SH"])
        self.assertEqual(ctx.exception.error_code, ErrorCode.NOT_TRADING_DAY)


class StockDetailTest(unittest.TestCase):
    def _provider(self):
        return TushareProvider(
            client=FakeClient(
                open_days={"20261008"},
                stock_rows=[
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20261008",
                        "open": "1405",
                        "high": "1410",
                        "low": "1375",
                        "close": "1379.7",
                        "pre_close": "1400",
                        "pct_chg": "-1.45",
                        "vol": "22",
                        "amount": "3050000",
                    }
                ],
                basic_rows=[
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20261008",
                        "turnover_rate": "0.35",
                    }
                ],
                security_master=[
                    {
                        "ts_code": "600519.SH",
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "industry": "白酒",
                        "exchange": "SSE",
                    }
                ],
            )
        )

    def test_units_and_metadata(self):
        quote = self._provider().get_stock_detail("2026-10-08", "600519.SH")
        self.assertEqual(quote.code, "600519.SH")
        self.assertEqual(quote.name, "贵州茅台")
        self.assertEqual(quote.sector_name, "白酒")
        self.assertEqual(quote.turnover_cny, 3_050_000_000.0)  # 千元 -> 元
        self.assertEqual(quote.volume_shares, 2_200.0)  # 手 -> 股
        self.assertEqual(quote.turnover_rate_pct, 0.35)
        self.assertEqual(quote.change_pct, -1.45)

    def test_bare_symbol_resolved_via_security_master(self):
        quote = self._provider().get_stock_detail("2026-10-08", "600519")
        self.assertEqual(quote.code, "600519.SH")

    def test_unknown_code_rejected(self):
        with self.assertRaises(MarketError) as ctx:
            self._provider().get_stock_detail("2026-10-08", "111111.SH")
        self.assertEqual(ctx.exception.error_code, ErrorCode.INVALID_STOCK_CODE)


class MarketHistorySummaryTest(unittest.TestCase):
    def test_market_total_excludes_chinext(self):
        client = FakeClient(
            open_days={"20261008"},
            index_rows=[
                {"ts_code": "000001.SH", "trade_date": "20261008", "close": "3915", "amount": "1000"},
                {"ts_code": "399001.SZ", "trade_date": "20261008", "close": "13320", "amount": "2000"},
                {"ts_code": "399006.SZ", "trade_date": "20261008", "close": "2875", "amount": "999999"},
            ],
        )
        provider = TushareProvider(client=client)
        summary = provider.get_market_history_summary(
            "2026-10-08", INDEX_CODES, TOTAL_TURNOVER_CODES
        )
        self.assertEqual(summary.turnover.current_cny, 3_000_000.0)  # 1000+2000 千元
        self.assertEqual([trend.code for trend in summary.indices], list(INDEX_CODES))

    def test_history_window_excludes_future_rows(self):
        index_rows = []
        amounts = {
            "000001.SH": {"20261005": 1000, "20261006": 1100, "20261007": 1200, "20261008": 1300, "20261009": 99999},
            "399001.SZ": {"20261005": 2000, "20261006": 2100, "20261007": 2200, "20261008": 2300, "20261009": 99999},
            "399006.SZ": {"20261005": 500, "20261006": 500, "20261007": 500, "20261008": 500, "20261009": 500},
        }
        for code, by_date in amounts.items():
            for trade_date, amount in by_date.items():
                index_rows.append(
                    {"ts_code": code, "trade_date": trade_date, "close": "100", "amount": str(amount)}
                )

        provider = TushareProvider(
            client=FakeClient(
                open_days={"20261005", "20261006", "20261007", "20261008", "20261009"},
                index_rows=index_rows,
            )
        )
        summary = provider.get_market_history_summary(
            "2026-10-08", INDEX_CODES, TOTAL_TURNOVER_CODES
        )
        # 元: 05=3.0M, 06=3.2M, 07=3.4M, 08=3.6M. The 20261009 row must be ignored.
        self.assertEqual(summary.turnover.current_cny, 3_600_000.0)
        self.assertEqual(summary.turnover.previous_cny, 3_400_000.0)
        self.assertEqual(summary.turnover.avg_5d_cny, 3_300_000.0)


if __name__ == "__main__":
    unittest.main()
