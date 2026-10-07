"""Round 4B — offline Production Runner tests (no network, no LLM)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from collector.collector import collect, normalized_for  # noqa: E402
from collector.store import EvidenceStore  # noqa: E402
from collector.tests.test_evidence_store import (  # noqa: E402
    DATE,
    FakeCaller,
    base_responses,
)
from runner.agent import ReferenceAgent  # noqa: E402
from runner.identity import identities  # noqa: E402
from runner.runner import run_review  # noqa: E402


class FakeFactory:
    def __init__(self, responses):
        self.responses = responses

    def __call__(self):
        return FakeCallerCtx(self.responses)


class FakeCallerCtx:
    def __init__(self, responses):
        self._caller = FakeCaller(responses)
        self.runtime_identity = self._caller.runtime_identity

    def __enter__(self):
        return self._caller

    def __exit__(self, *exc):
        return False


class FailingAgent:
    name = "failing-agent"

    def __call__(self, agent_input):
        raise RuntimeError("agent boom")


class SpyAgent:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.inputs = []
        self.name = "spy-agent"

    def __call__(self, agent_input):
        self.calls += 1
        self.inputs.append(agent_input)
        return self.inner(agent_input)


class SchemaBadAgent:
    name = "schema-bad-agent"

    def __call__(self, agent_input):
        result = ReferenceAgent()(agent_input)
        del result["review"]["metric_claims"]
        return result


class ContractBadAgent:
    name = "contract-bad-agent"

    def __call__(self, agent_input):
        result = ReferenceAgent()(agent_input)
        result["review"]["metric_claims"][0]["evidence_refs"] = ["E999"]
        return result


class TamperAgent:
    name = "tamper-agent"

    def __call__(self, agent_input):
        result = ReferenceAgent()(agent_input)
        for entry in result["review"]["evidence_registry"]:
            if entry["evidence_type"] == "market_metric" and entry["metric"] == "broken_limit_rate":
                entry["value"] = (entry["value"] or 0) + 1000
        return result


class UnknownEvidenceAgent:
    name = "unknown-evidence-agent"

    def __call__(self, agent_input):
        result = ReferenceAgent()(agent_input)
        result["review"]["evidence_registry"].append({
            "evidence_id": "E900", "evidence_type": "market_metric",
            "metric": "ghost_metric", "date": agent_input["date"], "window": None,
            "value": 1.0, "avg": None, "median": None, "percentile": None,
            "sample_count": None, "complete": None, "unit": "count", "source": "x",
        })
        return result


class EvalFailAgent:
    name = "eval-fail-agent"

    def __call__(self, agent_input):
        result = ReferenceAgent()(agent_input)
        registry = result["review"]["evidence_registry"]
        metric_id = next(e["evidence_id"] for e in registry
                         if e["evidence_type"] == "market_metric" and e["metric"] == "broken_limit_rate")
        baseline_id = next(e["evidence_id"] for e in registry
                           if e["evidence_type"] == "market_metric_baseline"
                           and e["metric"] == "broken_limit_rate" and e["window"] == 20)
        result["review"]["metric_claims"].append({
            "claim_id": "C900", "metric": "broken_limit_rate", "claim_type": "SEMANTIC",
            "current_value": 18.75, "unit": "percent", "semantic_label": "low",
            "baseline_refs": [baseline_id], "threshold_policy_ref": "policy/low-v1",
            "evidence_refs": [metric_id, baseline_id], "forward_claim": False, "text_ref": None,
        })
        return result


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.data = str(root / "data")
        self.out = str(root / "out")
        self.failed = str(root / "failed")
        self.clock = lambda: "2026-10-01T00:00:00"

    def tearDown(self):
        self._tmp.cleanup()

    def save_evidence(self, responses=None, date=DATE):
        responses = responses or base_responses(broken20=False, promotion20=False)
        caller = FakeCaller(responses)
        collection = collect(caller, date)
        EvidenceStore(self.data).save(date, collection, normalized_for(collection))
        return collection

    def execute(self, date=DATE, mode="replay", agent=None, factory=None, overwrite=False):
        return run_review(date=date, mode=mode, data_root=self.data, output_root=self.out,
                          failed_root=self.failed, overwrite_output=overwrite,
                          agent=agent, tool_caller_factory=factory, clock=self.clock)

    def stage(self, manifest, name):
        return next(s["status"] for s in manifest["stages"] if s["name"] == name)

    # 1
    def test_01_auto_replay_when_evidence_exists(self):
        self.save_evidence()
        manifest = self.execute(mode="auto")
        self.assertEqual(manifest["evidence_mode_used"], "replay")
        self.assertEqual(self.stage(manifest, "resolve_evidence"), "PASS")

    # 2
    def test_02_auto_live_when_no_evidence(self):
        manifest = self.execute(mode="auto", factory=FakeFactory(base_responses()))
        self.assertEqual(manifest["evidence_mode_used"], "live")
        self.assertTrue(EvidenceStore(self.data).exists(DATE))

    def test_live_overwrite_replaces_existing_evidence(self):
        self.save_evidence()
        manifest = self.execute(
            mode="live", factory=FakeFactory(base_responses()), overwrite=True
        )
        self.assertEqual(self.stage(manifest, "resolve_evidence"), "PASS")
        self.assertEqual(manifest["evidence_mode_used"], "live")
        self.assertTrue(EvidenceStore(self.data).exists(DATE))

    # 3
    def test_03_replay_missing_fails(self):
        manifest = self.execute(mode="replay")
        self.assertEqual(manifest["execution_status"], "FAIL")
        self.assertEqual(self.stage(manifest, "resolve_evidence"), "FAIL")
        self.assertIn("REPLAY_DATA_NOT_FOUND", manifest["errors"])

    # 4
    def test_04_live_failed_stops(self):
        responses = base_responses()
        responses[("get_index_performance", (("date", DATE),))] = {
            "success": False, "error_code": "NETWORK_ERROR"}
        manifest = self.execute(mode="live", factory=FakeFactory(responses))
        self.assertEqual(manifest["execution_status"], "FAIL")
        self.assertEqual(self.stage(manifest, "resolve_evidence"), "FAIL")
        self.assertEqual(self.stage(manifest, "run_agent"), "SKIPPED")

    # 5
    def test_05_partial_evidence_allowed(self):
        self.save_evidence()
        manifest = self.execute(mode="replay")
        self.assertEqual(manifest["evidence_collection_status"], "PARTIAL")
        self.assertEqual(self.stage(manifest, "resolve_evidence"), "PASS")

    # 6
    def test_06_agent_failure_skips_downstream(self):
        self.save_evidence()
        manifest = self.execute(agent=FailingAgent())
        self.assertEqual(self.stage(manifest, "run_agent"), "FAIL")
        self.assertEqual(self.stage(manifest, "schema_validation"), "SKIPPED")
        self.assertEqual(manifest["execution_status"], "FAIL")

    def test_reference_agent_output_matches_frozen_schema(self):
        self.save_evidence()
        manifest = self.execute()
        self.assertEqual(self.stage(manifest, "schema_validation"), "PASS")
        self.assertEqual(manifest["execution_status"], "SUCCESS")

    # 7
    def test_07_invalid_output_fails_schema_stage(self):
        self.save_evidence()
        manifest = self.execute(agent=SchemaBadAgent())
        self.assertEqual(self.stage(manifest, "schema_validation"), "FAIL")

    # 8
    def test_08_schema_failure_skips_contract_and_eval(self):
        self.save_evidence()
        manifest = self.execute(agent=SchemaBadAgent())
        self.assertEqual(self.stage(manifest, "contract_validation"), "SKIPPED")
        self.assertEqual(self.stage(manifest, "independent_eval"), "SKIPPED")

    # 9
    def test_09_contract_failure_skips_eval(self):
        self.save_evidence()
        manifest = self.execute(agent=ContractBadAgent())
        self.assertEqual(self.stage(manifest, "contract_validation"), "FAIL")
        self.assertEqual(self.stage(manifest, "independent_eval"), "SKIPPED")

    # 10
    def test_10_evidence_integrity_pass(self):
        self.save_evidence()
        manifest = self.execute()
        self.assertEqual(self.stage(manifest, "evidence_integrity"), "PASS")

    # 11
    def test_11_modified_evidence_value_fails_integrity(self):
        self.save_evidence()
        manifest = self.execute(agent=TamperAgent())
        self.assertEqual(self.stage(manifest, "evidence_integrity"), "FAIL")
        self.assertEqual(self.stage(manifest, "independent_eval"), "SKIPPED")

    # 12
    def test_12_unknown_evidence_fails_integrity(self):
        self.save_evidence()
        manifest = self.execute(agent=UnknownEvidenceAgent())
        self.assertEqual(self.stage(manifest, "evidence_integrity"), "FAIL")

    # 13
    def test_13_eval_pass(self):
        self.save_evidence()
        manifest = self.execute()
        self.assertEqual(self.stage(manifest, "independent_eval"), "PASS")
        self.assertEqual(manifest["review_quality_status"], "PASS")

    # 14
    def test_14_eval_fail_but_execution_success(self):
        self.save_evidence()
        manifest = self.execute(agent=EvalFailAgent())
        self.assertEqual(self.stage(manifest, "independent_eval"), "FAIL")
        self.assertEqual(manifest["execution_status"], "SUCCESS")
        self.assertEqual(manifest["review_quality_status"], "FAIL")

    # 15
    def test_15_run_manifest_generated(self):
        self.save_evidence()
        manifest = self.execute()
        path = Path(self.out) / DATE / "run_manifest.json"
        self.assertTrue(path.is_file())
        for field in ("run_id", "date", "started_at", "finished_at", "mode_requested",
                      "evidence_mode_used", "evidence_manifest_path",
                      "evidence_collection_status", "market_mcp_build", "skill_version",
                      "schema_version", "eval_version", "skill_sha256", "schema_sha256",
                      "eval_sha256", "stages", "execution_status",
                      "review_quality_status", "artifacts", "errors"):
            self.assertIn(field, manifest)

    # 16
    def test_16_sha256_identities_stable(self):
        first = identities()
        second = identities()
        self.assertEqual(first, second)
        self.assertEqual(len(first["skill_sha256"]), 64)
        self.assertEqual(len(first["eval_sha256"]), 64)
        self.assertEqual(len(first["schema_sha256"]), 64)

    # 17
    def test_17_duplicate_output_refused(self):
        self.save_evidence()
        self.execute()
        manifest = self.execute()
        self.assertEqual(manifest["execution_status"], "FAIL")
        self.assertEqual(self.stage(manifest, "publish"), "FAIL")

    # 18
    def test_18_overwrite_output_works(self):
        self.save_evidence()
        self.execute()
        manifest = self.execute(overwrite=True)
        self.assertEqual(manifest["execution_status"], "SUCCESS")

    # 19
    def test_19_failed_run_artifact_saved(self):
        self.save_evidence()
        manifest = self.execute(agent=FailingAgent())
        run_dir = Path(self.failed) / manifest["run_id"]
        self.assertTrue((run_dir / "run_manifest.json").is_file())
        self.assertTrue((run_dir / "error.json").is_file())

    # 20
    def test_20_atomic_publish(self):
        self.save_evidence()
        with mock.patch("runner.runner.os.rename", side_effect=OSError("boom")):
            manifest = self.execute()
        self.assertEqual(manifest["execution_status"], "FAIL")
        self.assertFalse((Path(self.out) / DATE).exists())

    # 21
    def test_21_replay_does_not_call_market_mcp(self):
        self.save_evidence()
        with mock.patch("runner.runner.McpStdioToolCaller",
                        side_effect=AssertionError("market MCP in replay")):
            manifest = self.execute(mode="replay")
        self.assertEqual(manifest["execution_status"], "SUCCESS")

    # 22
    def test_22_agent_evidence_comes_only_from_store(self):
        self.save_evidence()
        spy = SpyAgent(ReferenceAgent())
        self.execute(agent=spy)
        stored = EvidenceStore(self.data).load(DATE)["normalized"]
        self.assertEqual(spy.inputs[0]["normalized"], stored)
        self.assertIn("manifest", spy.inputs[0])

    # 23
    def test_23_no_automatic_agent_retry(self):
        self.save_evidence()
        spy = SpyAgent(FailingAgent())
        self.execute(agent=spy)
        self.assertEqual(spy.calls, 1)

    # 24
    def test_24_no_mock_fallback(self):
        manifest = self.execute(mode="replay")  # no evidence saved
        self.assertEqual(manifest["execution_status"], "FAIL")
        self.assertFalse((Path(self.out) / DATE).exists())

    # 25
    def test_25_deterministic_evidence_validation(self):
        self.save_evidence()
        m1 = self.execute()
        out2 = str(Path(self._tmp.name) / "out2")
        m2 = run_review(date=DATE, mode="replay", data_root=self.data, output_root=out2,
                        failed_root=self.failed, clock=self.clock)
        review1 = json.loads((Path(self.out) / DATE / "review.json").read_text(encoding="utf-8"))
        review2 = json.loads((Path(out2) / DATE / "review.json").read_text(encoding="utf-8"))
        self.assertEqual(review1["evidence_registry"], review2["evidence_registry"])
        self.assertEqual([c["current_value"] for c in review1["metric_claims"]],
                         [c["current_value"] for c in review2["metric_claims"]])
        self.assertEqual(m1["execution_status"], "SUCCESS")
        self.assertEqual(m2["execution_status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
