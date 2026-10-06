"""Offline tests for market breadth and metric baselines (no network).

All upstream responses are fixture DataFrames that mirror the verified live
payload columns/units from the Round 2A probe.
"""

import datetime as dt
import unittest

import pandas as pd

from domain.metricdefs import SUPPORTED_BASELINE_METRICS
from errors import ErrorCode, MarketError
from providers.akshare_provider import (
    REASON_CURRENT_ONLY,
    REASON_EMPTY_UPSTREAM,
    REASON_OUT_OF_RETENTION,
    AkShareProvider,
)

TODAY = dt.date(2026, 10, 6)
REVIEW = "2026-09-30"
DATES = [
    "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21",
    "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28",
    "2026-09-29", "2026-09-30",
]
# Extra older trading days (mostly outside the 30-calendar-day retention).
EXTENDED_DATES = [
    "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
    "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
    "2026-09-07", "2026-09-08",
] + DATES


def compact(date: str) -> str:
    return date.replace("-", "")


def zt_boards(boards):
    rows = [
        {"代码": "%06d" % (600000 + i), "名称": "X", "涨跌幅": 10.0, "连板数": board}
        for i, board in enumerate(boards)
    ]
    return pd.DataFrame(rows, columns=["代码", "名称", "涨跌幅", "连板数"])


def zt_rows(rows):
    return pd.DataFrame(rows, columns=["代码", "名称", "涨跌幅", "连板数"])


def code_frame(codes, changes):
    rows = [{"代码": code, "名称": "X", "涨跌幅": ch} for code, ch in zip(codes, changes)]
    return pd.DataFrame(rows, columns=["代码", "名称", "涨跌幅"])


def legu_frame(as_of, up, down, flat):
    return pd.DataFrame(
        [["上涨", up], ["下跌", down], ["平盘", flat], ["统计日期", as_of]],
        columns=["item", "value"],
    )


class FakeClient:
    """Mirrors the AkShare namespace used by the breadth/baseline paths."""

    def __init__(self, trade_dates, pools, legu=None):
        self._trade_dates = list(trade_dates)
        self._pools = pools or {}
        self._legu = legu
        self.calls = []

    def tool_trade_date_hist_sina(self):
        return pd.DataFrame(
            {"trade_date": [dt.date.fromisoformat(d) for d in self._trade_dates]}
        )

    def _pool(self, endpoint, date):
        self.calls.append((endpoint, date))
        return self._pools.get((endpoint, date), pd.DataFrame())

    def stock_zt_pool_em(self, date=None):
        return self._pool("stock_zt_pool_em", date)

    def stock_zt_pool_dtgc_em(self, date=None):
        return self._pool("stock_zt_pool_dtgc_em", date)

    def stock_zt_pool_zbgc_em(self, date=None):
        return self._pool("stock_zt_pool_zbgc_em", date)

    def stock_zt_pool_previous_em(self, date=None):
        return self._pool("stock_zt_pool_previous_em", date)

    def stock_market_activity_legu(self):
        self.calls.append(("stock_market_activity_legu", None))
        return self._legu if self._legu is not None else pd.DataFrame(columns=["item", "value"])


def make_provider(pools=None, legu=None, trade_dates=DATES, today=TODAY):
    client = FakeClient(trade_dates, pools or {}, legu)
    return AkShareProvider(client=client, today=today), client


class MarketBreadthTest(unittest.TestCase):
    def _provider(self):
        pools = {
            ("stock_zt_pool_em", compact(REVIEW)): zt_rows([
                {"代码": "600001", "名称": "A", "涨跌幅": 10.0, "连板数": 1},
                {"代码": "600002", "名称": "B", "涨跌幅": 10.0, "连板数": 1},
                {"代码": "600003", "名称": "C", "涨跌幅": 10.0, "连板数": 2},
                {"代码": "600004", "名称": "D", "涨跌幅": 10.0, "连板数": 3},
            ]),
            ("stock_zt_pool_dtgc_em", compact(REVIEW)): code_frame(["000001"], [-10.0]),
            ("stock_zt_pool_zbgc_em", compact(REVIEW)): code_frame(
                ["300001", "300002"], [5.0, 3.0]
            ),
            ("stock_zt_pool_previous_em", compact(REVIEW)): code_frame(
                ["600001", "600005", "600006", "600007"], [5.0, -3.0, 0.0, 8.0]
            ),
        }
        legu = legu_frame("2026-09-30 15:00:00", 3000, 1800, 120)
        return make_provider(pools, legu)

    def test_limit_ecology_counts_and_rate(self):
        breadth = self._provider()[0].get_market_breadth(REVIEW)
        self.assertEqual(breadth.limit.limit_up_count, 4)
        self.assertEqual(breadth.limit.limit_down_count, 1)
        self.assertEqual(breadth.limit.broken_limit_count, 2)
        self.assertEqual(breadth.limit.broken_limit_rate, round(2 / 6 * 100, 2))
        self.assertEqual(breadth.limit.first_limit_up_count, 2)
        self.assertEqual(breadth.limit.multi_limit_up_count, 2)
        self.assertEqual(breadth.limit.max_consecutive_limit_up, 3)

    def test_first_multi_max_board(self):
        breadth = self._provider()[0].get_market_breadth(REVIEW)
        self.assertEqual(breadth.limit.first_limit_up_count, 2)
        self.assertEqual(breadth.limit.multi_limit_up_count, 2)
        self.assertEqual(breadth.limit.max_consecutive_limit_up, 3)

    def test_previous_limit_up_metrics(self):
        breadth = self._provider()[0].get_market_breadth(REVIEW)
        self.assertEqual(breadth.limit.previous_sample_size, 4)
        self.assertEqual(breadth.limit.previous_average_change_pct, 2.5)
        self.assertEqual(breadth.limit.previous_median_change_pct, 2.5)
        self.assertEqual(breadth.limit.previous_positive_rate, 50.0)  # >0 strict, 0 excluded
        self.assertEqual(breadth.limit.previous_promotion_rate, 25.0)

    def test_breadth_tool_dict_contract(self):
        payload = self._provider()[0].get_market_breadth(REVIEW).to_tool_dict()
        self.assertEqual(payload["limit_state"]["max_limit_height"], 3)
        self.assertEqual(payload["breadth"]["rising_count"], 3000)
        self.assertEqual(payload["breadth"]["falling_count"], 1800)
        self.assertEqual(payload["breadth"]["flat_count"], 120)
        self.assertIsNone(payload["extreme_move"]["large_rise_count"])
        self.assertIn("evidence", payload)

    def test_not_trading_day(self):
        with self.assertRaises(MarketError) as ctx:
            self._provider()[0].get_market_breadth("2026-10-01")
        self.assertEqual(ctx.exception.error_code, ErrorCode.NOT_TRADING_DAY)


class EmptyVsZeroTest(unittest.TestCase):
    def test_empty_pool_is_not_zero(self):
        # zt empty -> limit_up_count unknown (NOT zero).
        pools = {
            ("stock_zt_pool_zbgc_em", compact(REVIEW)): code_frame(["300001"], [5.0]),
        }
        breadth = make_provider(pools)[0].get_market_breadth(REVIEW)
        self.assertIsNone(breadth.limit.limit_up_count)
        self.assertIsNone(breadth.limit.broken_limit_rate)
        self.assertEqual(
            breadth.missing_reasons["limit_up_count"], REASON_EMPTY_UPSTREAM
        )

    def test_both_empty_rate_is_none_not_zero(self):
        breadth = make_provider({})[0].get_market_breadth(REVIEW)
        self.assertIsNone(breadth.limit.broken_limit_rate)
        self.assertIsNone(breadth.limit.limit_up_count)

    def test_out_of_retention_is_not_zero(self):
        old = "2026-08-20"
        provider, client = make_provider({}, trade_dates=[old] + DATES)
        breadth = provider.get_market_breadth(old)
        self.assertIsNone(breadth.limit.limit_up_count)
        self.assertEqual(
            breadth.missing_reasons["limit_up_count"], REASON_OUT_OF_RETENTION
        )
        # No pool endpoint was queried at all for an out-of-retention date.
        self.assertEqual(client.calls, [])


class CurrentOnlyBreadthTest(unittest.TestCase):
    def test_current_snapshot_available_for_latest_session(self):
        legu = legu_frame("2026-09-30 15:00:00", 3000, 1800, 120)
        breadth = make_provider({}, legu)[0].get_market_breadth(REVIEW)
        self.assertEqual(breadth.advance_count, 3000)
        self.assertEqual(breadth.decline_count, 1800)
        self.assertEqual(breadth.flat_count, 120)
        self.assertEqual(breadth.breadth_as_of, REVIEW)

    def test_historical_date_cannot_use_current_snapshot(self):
        old = "2026-09-29"
        pools = {
            ("stock_zt_pool_em", compact(old)): zt_boards([1, 2, 3]),
        }
        provider, client = make_provider(
            pools, legu_frame("2026-09-30 15:00:00", 1, 1, 1)
        )
        breadth = provider.get_market_breadth(old)
        self.assertEqual(breadth.limit.limit_up_count, 3)  # real history
        self.assertIsNone(breadth.advance_count)
        self.assertEqual(breadth.missing_reasons["advance_count"], REASON_CURRENT_ONLY)
        self.assertNotIn(("stock_market_activity_legu", None), client.calls)

    def test_snapshot_lag_is_current_only(self):
        legu = legu_frame("2026-09-29 15:00:00", 3000, 1800, 120)
        breadth = make_provider({}, legu)[0].get_market_breadth(REVIEW)
        self.assertIsNone(breadth.advance_count)
        self.assertEqual(breadth.breadth_as_of, "2026-09-29")
        self.assertEqual(breadth.missing_reasons["advance_count"], REASON_CURRENT_ONLY)


class BaselineTest(unittest.TestCase):
    BOARDS = {
        "2026-09-15": 5, "2026-09-16": 6, "2026-09-17": 7, "2026-09-18": 8,
        "2026-09-21": 9, "2026-09-22": 10, "2026-09-23": 11, "2026-09-24": 12,
        "2026-09-25": 13, "2026-09-28": 14, "2026-09-29": 15, "2026-09-30": 16,
    }

    def _provider(self, trade_dates=DATES, boards=None):
        boards = boards or self.BOARDS
        pools = {
            ("stock_zt_pool_em", compact(day)): zt_boards(list(range(count)))
            for day, count in boards.items()
        }
        return make_provider(pools, trade_dates=trade_dates)

    def test_baseline_excludes_current(self):
        provider, _ = self._provider()
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 3)
        self.assertEqual(baseline.current, 16)
        self.assertEqual(baseline.sample_end, "2026-09-29")
        self.assertTrue(baseline.sample_end < REVIEW)
        self.assertEqual(baseline.avg, 14.0)  # (13+14+15)/3, current excluded

    def test_five_day_complete_baseline(self):
        provider, _ = self._provider()
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 5)
        self.assertTrue(baseline.complete)
        self.assertEqual(baseline.sample_count, 5)
        self.assertEqual(baseline.avg, 13.0)  # (11..15)/5
        self.assertEqual(baseline.median, 13.0)
        self.assertEqual(baseline.percentile, 100.0)  # current 16 >= all
        self.assertEqual(baseline.missing_dates, ())

    def test_twenty_day_incomplete_baseline(self):
        provider, _ = self._provider()
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 20)
        self.assertFalse(baseline.complete)
        self.assertEqual(baseline.window, 20)
        self.assertEqual(baseline.sample_count, 11)
        self.assertIsNone(baseline.avg)
        self.assertIsNone(baseline.median)
        self.assertIsNone(baseline.percentile)

    def test_missing_dates_recorded(self):
        # Extended calendar; only the recent 5 days have pool data.
        boards = {
            "2026-09-24": 12, "2026-09-25": 13, "2026-09-28": 14,
            "2026-09-29": 15, "2026-09-30": 16,
        }
        provider, _ = self._provider(trade_dates=EXTENDED_DATES, boards=boards)
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 20)
        self.assertFalse(baseline.complete)
        self.assertEqual(baseline.sample_count, 4)  # prior days with data (excl current)
        self.assertTrue(baseline.missing_dates)
        self.assertTrue(all(day < REVIEW for day in baseline.missing_dates))
        self.assertEqual(
            baseline.missing_dates, tuple(baseline.missing_dates)
        )

    def test_percentile_includes_ties(self):
        boards = {
            "2026-09-23": 5, "2026-09-24": 10, "2026-09-25": 10,
            "2026-09-28": 15, "2026-09-29": 20, "2026-09-30": 10,
        }
        provider, _ = self._provider(boards=boards)
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 5)
        self.assertTrue(baseline.complete)
        self.assertEqual(baseline.current, 10)
        self.assertEqual(baseline.percentile, 60.0)  # <= 10 -> {5,10,10} = 3/5

    def test_no_future_leakage(self):
        boards = dict(self.BOARDS)
        boards["2026-10-08"] = 999
        provider, _ = self._provider(
            trade_dates=DATES + ["2026-10-08"], boards=boards
        )
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 2)
        self.assertLess(baseline.sample_end, REVIEW)
        self.assertEqual(baseline.avg, 14.5)  # (14+15)/2, future 999 ignored

    def test_unsupported_metric(self):
        provider, _ = self._provider()
        with self.assertRaises(MarketError) as ctx:
            provider.get_market_metric_baseline(REVIEW, "advance_count", 5)
        self.assertEqual(ctx.exception.error_code, ErrorCode.UNSUPPORTED_METRIC)

    def test_invalid_window(self):
        provider, _ = self._provider()
        for window in (0, -1, True):
            with self.assertRaises(MarketError) as ctx:
                provider.get_market_metric_baseline(REVIEW, "limit_up_count", window)
            self.assertEqual(ctx.exception.error_code, ErrorCode.INVALID_WINDOW)

    def test_metric_value_dict(self):
        provider, _ = self._provider()
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 5)
        payload = baseline.to_tool_dict()
        self.assertEqual(payload["evidence_status"], "COMPLETE")
        self.assertEqual(payload["definition"]["source"], "eastmoney")
        self.assertEqual(payload["definition"]["endpoint"], "stock_zt_pool_em")


class ErrorPropagationTest(unittest.TestCase):
    def test_network_error_propagates(self):
        class Boom(FakeClient):
            def stock_zt_pool_em(self, date=None):
                raise ConnectionError("Max retries exceeded with url /api/qt")

        provider = AkShareProvider(client=Boom(DATES, {}), today=TODAY)
        with self.assertRaises(MarketError) as ctx:
            provider.get_market_breadth(REVIEW)
        self.assertEqual(ctx.exception.error_code, ErrorCode.NETWORK_ERROR)

    def test_schema_change_propagates(self):
        bad = pd.DataFrame([{"代码": "600001"}], columns=["代码"])
        pools = {("stock_zt_pool_em", compact(REVIEW)): bad}
        provider, _ = make_provider(pools)
        with self.assertRaises(MarketError) as ctx:
            provider.get_market_breadth(REVIEW)
        self.assertEqual(ctx.exception.error_code, ErrorCode.UPSTREAM_SCHEMA_CHANGED)

    def test_baseline_current_unavailable_is_data_not_available(self):
        # current metric (limit_up_count) empty -> DATA_NOT_AVAILABLE, not zero.
        provider, _ = make_provider({})
        with self.assertRaises(MarketError) as ctx:
            provider.get_market_metric_baseline(REVIEW, "limit_up_count", 5)
        self.assertEqual(ctx.exception.error_code, ErrorCode.DATA_NOT_AVAILABLE)


class DefinitionConsistencyTest(unittest.TestCase):
    def test_limit_metrics_are_eastmoney_only(self):
        provider, _ = make_provider({
            ("stock_zt_pool_em", compact(REVIEW)): zt_boards([1, 2]),
        })
        breadth = provider.get_market_breadth(REVIEW)
        for name in (
            "limit_up_count", "limit_down_count", "broken_limit_count",
            "broken_limit_rate", "first_limit_up_count", "multi_limit_up_count",
            "max_consecutive_limit_up", "previous_limit_up_positive_rate",
            "promotion_rate",
        ):
            self.assertEqual(breadth.definitions[name].source, "eastmoney")
        for name in ("advance_count", "decline_count", "flat_count"):
            self.assertEqual(breadth.definitions[name].source, "legulegu")

    def test_baseline_definition_matches_registry(self):
        provider, _ = make_provider({
            ("stock_zt_pool_em", compact(REVIEW)): zt_boards([1, 2, 3]),
            ("stock_zt_pool_em", compact("2026-09-29")): zt_boards([1, 2]),
            ("stock_zt_pool_em", compact("2026-09-28")): zt_boards([1]),
        })
        baseline = provider.get_market_metric_baseline(REVIEW, "limit_up_count", 2)
        self.assertEqual(baseline.definition.metric, "limit_up_count")
        self.assertEqual(baseline.definition.source, "eastmoney")
        self.assertEqual(baseline.unit, "count")
        self.assertIn("limit_up_count", SUPPORTED_BASELINE_METRICS)


if __name__ == "__main__":
    unittest.main()
