"""Round 5B — offline tests for the Real Sector Provider (Industry V0.1)."""

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MARKET_MCP = Path(__file__).resolve().parents[1]
if str(MARKET_MCP) not in sys.path:
    sys.path.insert(0, str(MARKET_MCP))

from errors import ErrorCode, MarketError  # noqa: E402
from providers.akshare_provider import AkShareProvider  # noqa: E402

TODAY = dt.date(2026, 10, 6)
REVIEW = "2026-09-30"
SESSIONS = ["2026-09-%02d" % d for d in range(6, 31)]  # 25 sessions, ends 09-30

TAXONOMY = [("半导体", "881121"), ("房地产", "881153")]
SUMMARY = [
    {"板块": "半导体", "涨跌幅": 2.5, "总成交额": 1700.0, "上涨家数": 80, "下跌家数": 20, "领涨股": "中芯国际"},
    {"板块": "房地产", "涨跌幅": 0.79, "总成交额": 300.0, "上涨家数": 50, "下跌家数": 10, "领涨股": "陆家嘴"},
    {"板块": "未知板块", "涨跌幅": 9.9, "总成交额": 1.0, "上涨家数": 1, "下跌家数": 0, "领涨股": "X"},
]
SINA_MEMBERS = [
    {"code": "600663", "name": "陆家嘴", "changepercent": 2.0, "amount": 1.0e9,
     "turnoverratio": 1.5, "mktcap": 3.0e6},
    {"code": "000002", "name": "万科A", "changepercent": 0.5, "amount": 2.0e9,
     "turnoverratio": 2.0, "mktcap": 8.0e6},
]


def _taxonomy_frame():
    return pd.DataFrame(TAXONOMY, columns=["name", "code"])


def _summary_frame(rows=None):
    return pd.DataFrame(rows if rows is not None else SUMMARY,
                        columns=["板块", "涨跌幅", "总成交额", "上涨家数", "下跌家数", "领涨股"])


def _equal_weight_index(n=25):
    window = SESSIONS[-n:]
    rows = [{"日期": dt.date.fromisoformat(window[i]), "收盘价": 100.0 + i,
             "成交额": 1.0e10} for i in range(n)]
    return pd.DataFrame(rows, columns=["日期", "收盘价", "成交额"])


def _sina_frame(rows=None):
    return pd.DataFrame(rows if rows is not None else SINA_MEMBERS,
                        columns=["code", "name", "changepercent", "amount", "turnoverratio", "mktcap"])


class FakeSectorClient:
    def __init__(self, summary=None, index=None, sina=None, taxonomy=None, summary_error=None):
        self._summary = summary
        self._index = index
        self._sina = sina
        self._taxonomy = taxonomy
        self._summary_error = summary_error
        self.calls = []

    def tool_trade_date_hist_sina(self):
        return pd.DataFrame({"trade_date": [dt.date.fromisoformat(d) for d in SESSIONS]})

    def stock_board_industry_name_ths(self):
        return _taxonomy_frame() if self._taxonomy is None else self._taxonomy

    def stock_board_industry_summary_ths(self):
        if self._summary_error is not None:
            raise self._summary_error
        return _summary_frame() if self._summary is None else self._summary

    def stock_board_industry_index_ths(self, symbol=None, start_date=None, end_date=None):
        return _equal_weight_index() if self._index is None else self._index

    def stock_sector_detail(self, sector=None):
        return _sina_frame() if self._sina is None else self._sina


def provider(**kwargs):
    return AkShareProvider(client=FakeSectorClient(**kwargs), today=TODAY)


class SectorTest(unittest.TestCase):
    # 1
    def test_01_ths_taxonomy_normalization(self):
        tax = provider()._ths_industry_taxonomy()
        self.assertEqual(tax, {"半导体": "881121", "房地产": "881153"})

    # 2
    def test_02_sector_name_to_id(self):
        summary = provider().get_sector_history_summary(REVIEW, "半导体")
        self.assertEqual(summary.sector_id, "881121")

    # 3
    def test_03_unresolved_id(self):
        with self.assertRaises(MarketError) as ctx:
            provider().get_sector_history_summary(REVIEW, "不存在板块")
        self.assertEqual(ctx.exception.error_code, ErrorCode.SECTOR_ID_UNRESOLVED)

    # 4
    def test_04_ranking_top(self):
        rows = provider().get_sector_ranking(REVIEW, "top", 10)
        self.assertEqual([r.sector_name for r in rows], ["半导体", "房地产"])  # 未知板块 skipped

    # 5
    def test_05_ranking_bottom(self):
        rows = provider().get_sector_ranking(REVIEW, "bottom", 10)
        self.assertEqual([r.sector_name for r in rows], ["房地产", "半导体"])

    # 6
    def test_06_turnover_yi_to_cny(self):
        row = provider().get_sector_ranking(REVIEW, "top", 10)[0]
        self.assertEqual(row.turnover_cny, 1700.0 * 1e8)

    # 7
    def test_07_breadth_up_down(self):
        row = provider().get_sector_ranking(REVIEW, "top", 10)[0]
        self.assertEqual((row.up_count, row.down_count), (80, 20))

    # 8
    def test_08_flat_count_null(self):
        self.assertIsNone(provider().get_sector_ranking(REVIEW, "top", 10)[0].flat_count)

    # 9
    def test_09_current_date_allowed(self):
        rows = provider().get_sector_ranking(REVIEW, "top", 5)
        self.assertTrue(rows)
        self.assertEqual(rows[0].date_semantics, "CURRENT_ONLY")

    # 10
    def test_10_historical_current_endpoint_rejected(self):
        with self.assertRaises(MarketError) as ctx:
            provider().get_sector_ranking("2026-09-29", "top", 5)
        self.assertEqual(ctx.exception.error_code, ErrorCode.HISTORICAL_RANKING_UNAVAILABLE)

    # 11 + 13
    def test_11_5d_return_formula(self):
        summary = provider().get_sector_history_summary(REVIEW, "半导体")
        # closes 100..124, close[-1]=124 close[-5]=120 -> 3.33
        self.assertEqual(summary.change_pct_5d, round((124 / 120 - 1) * 100, 2))
        self.assertTrue(summary.history_5d_complete)
        self.assertEqual(summary.sample_count_5d, 5)

    # 12 + 14
    def test_12_20d_return_formula(self):
        summary = provider().get_sector_history_summary(REVIEW, "半导体")
        self.assertEqual(summary.change_pct_20d, round((124 / 105 - 1) * 100, 2))
        self.assertTrue(summary.history_20d_complete)
        self.assertEqual(summary.sample_count_20d, 20)

    # 15
    def test_15_turnover_avg5(self):
        self.assertEqual(
            provider().get_sector_history_summary(REVIEW, "半导体").turnover_avg_5d_cny, 1.0e10
        )

    # 16
    def test_16_turnover_avg20(self):
        self.assertEqual(
            provider().get_sector_history_summary(REVIEW, "半导体").turnover_avg_20d_cny, 1.0e10
        )

    # 17
    def test_17_incomplete_5d(self):
        summary = provider(index=_equal_weight_index(3)).get_sector_history_summary(REVIEW, "半导体")
        self.assertFalse(summary.history_5d_complete)
        self.assertIsNone(summary.change_pct_5d)
        self.assertIsNone(summary.turnover_avg_5d_cny)
        self.assertEqual(summary.sample_count_5d, 3)

    # 18
    def test_18_incomplete_20d(self):
        summary = provider(index=_equal_weight_index(10)).get_sector_history_summary(REVIEW, "半导体")
        self.assertFalse(summary.history_20d_complete)
        self.assertIsNone(summary.change_pct_20d)
        self.assertIsNone(summary.turnover_avg_20d_cny)

    # 19
    def test_19_sina_membership_unit_normalization(self):
        membership = provider().get_sector_membership("房地产")
        member = membership.stocks[0]
        self.assertEqual(member.stock_code, "600663")
        self.assertEqual(member.change_pct, 2.0)  # percent
        self.assertEqual(member.turnover_cny, 1.0e9)  # 元
        self.assertEqual(member.turnover_rate_pct, 1.5)  # percent
        self.assertEqual(member.market_cap_cny, 3.0e6 * 1e4)  # 万元 -> CNY

    # 20
    def test_20_current_membership_only(self):
        membership = provider().get_sector_membership("房地产")
        self.assertEqual(membership.membership_semantics, "CURRENT_MEMBERSHIP_ONLY")

    # 21 + 23
    def test_21_23_no_mapping_unavailable(self):
        with self.assertRaises(MarketError) as ctx:
            provider().get_sector_membership("半导体")
        self.assertEqual(ctx.exception.error_code, ErrorCode.SECTOR_MEMBERSHIP_UNAVAILABLE)

    # 22
    def test_22_verified_mapping_works(self):
        membership = provider().get_sector_membership("房地产")
        self.assertEqual(membership.sector_id, "881153")
        self.assertEqual(membership.source_family, "sina")
        self.assertEqual([s.stock_code for s in membership.stocks], ["600663", "000002"])

    # 24
    def test_24_families_kept_separate(self):
        ranking = provider().get_sector_ranking(REVIEW, "top", 5)[0]
        membership = provider().get_sector_membership("房地产")
        self.assertEqual(ranking.source_family, "ths")
        self.assertEqual(membership.source_family, "sina")

    # 25
    def test_25_no_cross_family_breadth(self):
        membership = provider().get_sector_membership("房地产")
        for member in membership.stocks:
            self.assertFalse(hasattr(member, "up_count"))
        # breadth only exists on the THS ranking snapshot
        self.assertIsNotNone(provider().get_sector_ranking(REVIEW, "top", 1)[0].up_count)

    # 26
    def test_26_no_cross_family_leader(self):
        # membership exposes no leader/contribution; only per-stock facts
        member = provider().get_sector_membership("房地产").stocks[0]
        self.assertFalse(hasattr(member, "is_leader"))
        self.assertFalse(hasattr(member, "contribution_pct"))

    # 27
    def test_27_evidence_lineage(self):
        snapshot = provider().get_sector_ranking(REVIEW, "top", 1)[0]
        self.assertEqual(snapshot.lineage.source, "ths")
        self.assertEqual(snapshot.lineage.endpoint, "stock_board_industry_summary_ths")
        membership = provider().get_sector_membership("房地产")
        self.assertEqual(membership.lineage.source, "sina")
        summary = provider().get_sector_history_summary(REVIEW, "半导体")
        self.assertEqual(summary.lineage.endpoint, "stock_board_industry_index_ths")

    # 28
    def test_28_current_ranking_full_snapshot_stored(self):
        from collector.normalize import normalize_records

        class Rec:
            tool = "get_sector_ranking"
            success = True
            result = {
                "success": True,
                "sectors": [
                    {"sector_id": "881121", "sector_name": "半导体", "change_pct": 2.5,
                     "turnover_cny": 1.7e11, "up_count": 80, "down_count": 20},
                    {"sector_id": "881153", "sector_name": "房地产", "change_pct": 0.79,
                     "turnover_cny": 3.0e10, "up_count": 50, "down_count": 10},
                ],
            }

        normalized = normalize_records([Rec()], REVIEW)
        stored = normalized["sector_ranking"]
        self.assertEqual(stored["date_semantics"], "CURRENT_ONLY")
        self.assertEqual(len(stored["sectors"]), 2)

    # 29 + 30
    def test_29_30_replay_ranking_and_missing(self):
        from collector.store import EvidenceStore, ReplayDataNotFound

        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            with self.assertRaises(ReplayDataNotFound):
                store.load(REVIEW)
            normalized = {"date": REVIEW, "evidence": {},
                          "sector_ranking": {"date": REVIEW, "sectors": [
                              {"sector_id": "881121", "sector_name": "半导体"}]}}

            class FakeCollection:
                date = REVIEW
                started_at = finished_at = "t"
                runtime_identity = {"build": "test", "provider": "akshare", "data_mode": "real"}
                status = "SUCCESS"
                complete = True
                records: list = []
                tools_requested = tools_success = tools_failed = []
                missing_capabilities = missing_optional = incomplete_evidence = []
                temporal_quarantine = []

            store.save(REVIEW, FakeCollection(), normalized)
            loaded = store.load(REVIEW)
            self.assertEqual(loaded["normalized"]["sector_ranking"]["sectors"][0]["sector_name"], "半导体")

    # 31
    def test_31_network_error_propagation(self):
        with self.assertRaises(MarketError) as ctx:
            provider(summary_error=ConnectionError("Max retries exceeded")).get_sector_ranking(
                REVIEW, "top", 5)
        self.assertEqual(ctx.exception.error_code, ErrorCode.NETWORK_ERROR)

    # 32
    def test_32_empty_not_zero(self):
        with self.assertRaises(MarketError) as ctx:
            provider(summary=_summary_frame(rows=[])).get_sector_ranking(REVIEW, "top", 5)
        self.assertEqual(ctx.exception.error_code, ErrorCode.EMPTY_UPSTREAM_RESPONSE)

    # 33
    def test_33_no_mock_fallback(self):
        # Empty taxonomy -> SECTOR_ID_UNRESOLVED (never fabricated ids / mock rows).
        empty_tax = pd.DataFrame(columns=["name", "code"])
        with self.assertRaises(MarketError) as ctx:
            provider(taxonomy=empty_tax).get_sector_ranking(REVIEW, "top", 5)
        self.assertEqual(ctx.exception.error_code, ErrorCode.DATA_NOT_AVAILABLE)

    # 34
    def test_34_market_regression_placeholder(self):
        # Full Market suite runs separately; here we assert market tools still import.
        self.assertTrue(hasattr(AkShareProvider, "get_index_performance"))

    # 35
    def test_35_collector_regression_placeholder(self):
        from collector.capabilities import required_requests
        tools = [t for t, _, _ in required_requests(REVIEW)]
        self.assertIn("get_sector_ranking", tools)


if __name__ == "__main__":
    unittest.main()
