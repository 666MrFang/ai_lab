"""Round 4A — offline EvidenceStore / collector tests (no network)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from collector import mcp_client  # noqa: E402
from collector.collector import (  # noqa: E402
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SUCCESS,
    collect,
    normalized_for,
)
from collector.replay import replay_market  # noqa: E402
from collector.store import (  # noqa: E402
    CollectionNotPublishable,
    EvidenceStore,
    OverwriteRefused,
    ReplayDataNotFound,
)

DATE = "2026-09-30"


def key(tool, **args):
    return (tool, tuple(sorted(args.items())))


def baseline(metric, window, complete):
    return {
        "success": True, "date": DATE,
        "baseline": {
            "metric": metric, "window": window, "complete": complete,
            "current": 18.75, "avg": 21.886, "median": 22.22,
            "percentile": 40 if complete else None, "sample_count": 5 if complete else 14,
            "unit": "percent",
            "definition": {"source": "eastmoney",
                           "endpoint": "stock_zt_pool_zbgc_em+stock_zt_pool_em"},
        },
    }


NOT_IMPL = {"success": False, "error_code": "REAL_PROVIDER_NOT_IMPLEMENTED", "error": "x"}


def base_responses(broken20=True, promotion20=True):
    resp = {
        key("get_index_performance", date=DATE): {
            "success": True, "date": DATE,
            "indices": [{"code": "000001.SH", "close": 3842.195,
                         "previous_close": 3830.451, "change_pct": 0.31,
                         "turnover": 680023000000.0}],
        },
        key("get_market_history_summary", date=DATE): {
            "success": True, "date": DATE,
            "turnover": {"current_cny": 1439356832918.04}, "indices": [],
        },
        key("get_market_breadth", date=DATE): {
            "success": True, "date": DATE,
            "limit_state": {"limit_up_count": 52, "limit_down_count": 9,
                            "broken_limit_count": 12, "broken_limit_rate": 18.75,
                            "first_limit_up_count": 40, "multi_limit_up_count": 12,
                            "max_limit_height": 7},
            "previous_limit_up": {"promotion_rate": 21.05},
            "breadth": {"rising_count": 2345, "falling_count": 2713, "flat_count": 155},
            "evidence": {"missing_reasons": {},
                         "definitions": {"limit_up_count": {"metric": "limit_up_count",
                                                            "source": "eastmoney",
                                                            "endpoint": "stock_zt_pool_em"}}},
        },
        key("get_market_metric_baseline", date=DATE, metric="broken_limit_rate", window=5): baseline("broken_limit_rate", 5, True),
        key("get_market_metric_baseline", date=DATE, metric="broken_limit_rate", window=20): baseline("broken_limit_rate", 20, broken20),
        key("get_market_metric_baseline", date=DATE, metric="promotion_rate", window=5): baseline("promotion_rate", 5, True),
        key("get_market_metric_baseline", date=DATE, metric="promotion_rate", window=20): baseline("promotion_rate", 20, promotion20),
        key("get_stock_detail", date=DATE, stock_code="600519.SH"): {
            "success": True, "date": DATE,
            "stock": {"code": "600519.SH", "name": "贵州茅台", "close": 1258.62,
                      "change_pct": 1.86},
        },
        key("get_sector_ranking", date=DATE, direction="top", limit=1000): {
            "success": True, "date": DATE, "direction": "top", "count": 2,
            "sectors": [
                {"sector_id": "881121", "sector_name": "半导体", "taxonomy": "industry",
                 "change_pct": 2.5, "turnover_cny": 1.7e11, "up_count": 80,
                 "down_count": 20, "flat_count": None, "constituent_count": None},
                {"sector_id": "881153", "sector_name": "房地产", "taxonomy": "industry",
                 "change_pct": 0.79, "turnover_cny": 3.0e10, "up_count": 50,
                 "down_count": 10, "flat_count": None, "constituent_count": None},
            ],
        },
        key("get_sector_detail", date=DATE, sector_name="半导体"): dict(NOT_IMPL),
        key("get_stock_news", date=DATE, stock_code="600519.SH"): dict(NOT_IMPL),
    }
    return resp


class FakeCaller:
    def __init__(self, responses):
        self.responses = responses
        self.runtime_identity = {"build": "test-build", "name": "A-Share Market MCP",
                                 "provider": "akshare", "data_mode": "real"}
        self.calls = []

    def call(self, tool, arguments):
        self.calls.append((tool, dict(arguments)))
        return self.responses.get(
            key(tool, **arguments),
            {"success": False, "error_code": "REAL_PROVIDER_NOT_IMPLEMENTED",
             "error": "missing fixture"},
        )


def collect_with(responses, date=DATE):
    return collect(FakeCaller(responses), date)


class EvidenceStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = EvidenceStore(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _save(self, responses, overwrite=False):
        collection = collect_with(responses)
        normalized = normalized_for(collection)
        self.store.save(DATE, collection, normalized, overwrite=overwrite)
        return collection, normalized

    # 1
    def test_01_save_load_round_trip(self):
        _, normalized = self._save(base_responses())
        data = self.store.load(DATE)
        self.assertEqual(data["date"], DATE)
        self.assertEqual(data["normalized"], normalized)
        self.assertIn("manifest", data)

    # 2
    def test_02_manifest_generated(self):
        self._save(base_responses())
        manifest = self.store.load(DATE)["manifest"]
        for field in ("date", "collection_started_at", "collection_finished_at",
                      "market_mcp_build", "provider", "data_mode", "tools_requested",
                      "tools_success", "tools_failed", "complete",
                      "missing_capabilities", "artifact_files"):
            self.assertIn(field, manifest)

    # 3
    def test_03_required_capability_success(self):
        collection = collect_with(base_responses(broken20=True, promotion20=True))
        self.assertEqual(collection.status, STATUS_SUCCESS)
        self.assertTrue(collection.complete)
        self.assertEqual(collection.incomplete_evidence, [])

    # 4
    def test_04_incomplete_baseline_partial(self):
        collection = collect_with(base_responses(broken20=False, promotion20=False))
        self.assertEqual(collection.status, STATUS_PARTIAL)
        self.assertFalse(collection.complete)
        self.assertTrue(collection.incomplete_evidence)

    # 5
    def test_05_insufficient_history_is_not_failure(self):
        collection = collect_with(base_responses(broken20=False, promotion20=False))
        self.assertNotEqual(collection.status, STATUS_FAILED)
        self.assertEqual(collection.tools_failed, [])

    # 6
    def test_06_network_error_required_tool_failed(self):
        responses = base_responses()
        responses[key("get_index_performance", date=DATE)] = {
            "success": False, "error_code": "NETWORK_ERROR", "error": "x"}
        collection = collect_with(responses)
        self.assertEqual(collection.status, STATUS_FAILED)
        normalized = normalized_for(collection)
        with self.assertRaises(CollectionNotPublishable):
            self.store.save(DATE, collection, normalized)
        self.assertFalse(self.store.exists(DATE))

    # 7
    def test_07_optional_failure_does_not_fail_collection(self):
        responses = base_responses()
        responses[key("get_stock_detail", date=DATE, stock_code="600519.SH")] = {
            "success": False, "error_code": "NETWORK_ERROR"}
        collection = collect_with(responses)
        self.assertNotEqual(collection.status, STATUS_FAILED)
        self.assertIn("get_stock_detail", collection.missing_optional)

    # 8
    def test_08_unimplemented_capability_recorded(self):
        collection = collect_with(base_responses())
        self.assertIn("get_stock_news", collection.missing_capabilities)
        self.assertNotIn("get_sector_ranking", collection.missing_capabilities)
        self.assertNotEqual(collection.status, STATUS_FAILED)

    # 9
    def test_09_exists(self):
        self.assertFalse(self.store.exists(DATE))
        self._save(base_responses())
        self.assertTrue(self.store.exists(DATE))

    # 10
    def test_10_duplicate_collection_refused(self):
        self._save(base_responses())
        with self.assertRaises(OverwriteRefused):
            self._save(base_responses())

    # 11
    def test_11_explicit_overwrite_works(self):
        self._save(base_responses())
        collection, normalized = self._save(base_responses(), overwrite=True)
        self.assertTrue(self.store.exists(DATE))
        self.assertEqual(self.store.load(DATE)["manifest"]["status"], collection.status)

    # 12
    def test_12_failed_collection_not_published(self):
        responses = base_responses()
        responses[key("get_market_breadth", date=DATE)] = {
            "success": False, "error_code": "UPSTREAM_SCHEMA_CHANGED"}
        collection = collect_with(responses)
        self.assertEqual(collection.status, STATUS_FAILED)
        with self.assertRaises(CollectionNotPublishable):
            self.store.save(DATE, collection, normalized_for(collection))
        self.assertFalse(self.store.exists(DATE))

    # 13
    def test_13_atomic_publish(self):
        collection = collect_with(base_responses())
        normalized = normalized_for(collection)
        with mock.patch("collector.store.os.rename", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                self.store.save(DATE, collection, normalized)
        self.assertFalse(self.store.exists(DATE))

    # 14
    def test_14_replay_uses_saved_data(self):
        _, normalized = self._save(base_responses())
        replayed = replay_market(self.store, DATE)
        self.assertEqual(replayed["normalized"], normalized)

    # 15
    def test_15_replay_missing_raises(self):
        with self.assertRaises(ReplayDataNotFound) as ctx:
            replay_market(self.store, "1999-01-01")
        self.assertEqual(ctx.exception.code, "REPLAY_DATA_NOT_FOUND")

    # 16
    def test_16_replay_does_not_access_network(self):
        self._save(base_responses())
        with mock.patch("collector.mcp_client.subprocess.Popen",
                        side_effect=AssertionError("network access in replay")):
            replayed = replay_market(self.store, DATE)
        self.assertEqual(replayed["date"], DATE)

    # 17
    def test_17_no_mock_fallback(self):
        responses = base_responses()
        del responses[key("get_index_performance", date=DATE)]
        collection = collect_with(responses)
        self.assertEqual(collection.status, STATUS_FAILED)
        normalized = normalized_for(collection)
        self.assertFalse(any(k.startswith("index_quote:") for k in normalized["evidence"]))

    # 18
    def test_18_runtime_identity_saved(self):
        self._save(base_responses())
        data = self.store.load(DATE)
        manifest = data["manifest"]
        self.assertEqual(manifest["market_mcp_build"], "test-build")
        self.assertEqual(manifest["provider"], "akshare")
        self.assertEqual(manifest["data_mode"], "real")
        raw_values = list(data["raw"].values())
        self.assertTrue(any(r.get("runtime_identity", {}).get("build") == "test-build"
                            for r in raw_values))

    # 19
    def test_19_source_endpoint_lineage_preserved(self):
        self._save(base_responses())
        data = self.store.load(DATE)
        baseline_records = [r for r in data["raw"].values()
                            if r["tool"] == "get_market_metric_baseline"]
        self.assertTrue(baseline_records)
        lineages = [entry for r in baseline_records for entry in r["lineage"]]
        self.assertIn({"source": "eastmoney",
                       "endpoint": "stock_zt_pool_zbgc_em+stock_zt_pool_em"}, lineages)
        entry = data["normalized"]["evidence"][
            "market_metric_baseline:broken_limit_rate:2026-09-30:5"]
        self.assertEqual(entry["source"], "eastmoney")

    # 20
    def test_20_deterministic_evidence_key(self):
        collection = collect_with(base_responses())
        norm1 = normalized_for(collection)
        norm2 = normalized_for(collection)
        self.assertEqual(norm1, norm2)
        self.assertIn("market_metric_baseline:broken_limit_rate:2026-09-30:5",
                      norm1["evidence"])
        self.assertIn("market_metric:broken_limit_rate:2026-09-30", norm1["evidence"])


if __name__ == "__main__":
    unittest.main()
