"""Round 3E — structured MetricClaim contract tests (offline, deterministic)."""

import json
import sys
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = EVAL_DIR.parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from jsonschema import Draft202012Validator  # noqa: E402

from contract import validate_review_contract  # noqa: E402
from evaluator import evaluate_case  # noqa: E402
from models import EvalCase, STATUS_NOT_OBSERVABLE  # noqa: E402
from normalize import normalize_review  # noqa: E402

SCHEMA = json.loads(
    (REPO_DIR / "schemas" / "review_schema.json").read_text(encoding="utf-8")
)
_VALIDATOR = Draft202012Validator(SCHEMA)


def schema_errors(review):
    return list(_VALIDATOR.iter_errors(review))


def entry(eid, etype, metric=None, value=None, window=None, complete=None,
          avg=None, median=None, percentile=None, sample_count=None, unit=None):
    return {
        "evidence_id": eid, "evidence_type": etype, "metric": metric,
        "date": "2026-09-30", "window": window, "value": value, "avg": avg,
        "median": median, "percentile": percentile, "sample_count": sample_count,
        "complete": complete, "unit": unit, "source": "market MCP",
    }


def claim(cid, metric, ctype, current_value=18.75, unit="percent",
          semantic_label=None, baseline_refs=None, threshold_policy_ref=None,
          evidence_refs=None, forward_claim=False, text_ref=None):
    return {
        "claim_id": cid, "metric": metric, "claim_type": ctype,
        "current_value": current_value, "unit": unit,
        "semantic_label": semantic_label,
        "baseline_refs": baseline_refs if baseline_refs is not None else [],
        "threshold_policy_ref": threshold_policy_ref,
        "evidence_refs": evidence_refs if evidence_refs is not None else [],
        "forward_claim": forward_claim, "text_ref": text_ref,
    }


def review(metric_claims, evidence_registry):
    return {
        "date": "2026-09-30",
        "market": {"facts": [], "inferences": []},
        "market_regime": {"state": "UNCERTAIN", "confidence": "LOW",
                          "evidence": [], "counter_evidence": [], "evidence_gaps": []},
        "sectors": {"top_gainers": [], "top_losers": [], "main_theme_candidates": []},
        "stocks": [],
        "profit_effect": {"summary": "x", "confidence": "LOW", "evidence": [],
                          "evidence_gaps": []},
        "loss_effect": {"summary": "x", "confidence": "LOW", "evidence": [],
                        "evidence_gaps": []},
        "evidence_gaps": [],
        "tomorrow_watch_conditions": [],
        "metric_claims": metric_claims,
        "evidence_registry": evidence_registry,
    }


REGISTRY = [
    entry("E001", "market_metric", "broken_limit_rate", value=18.75, unit="percent"),
    entry("E002", "market_metric_baseline", "broken_limit_rate", window=5,
          complete=True, avg=21.886, median=22.22, percentile=40, sample_count=5),
    entry("E003", "market_metric_baseline", "broken_limit_rate", window=20,
          complete=False, sample_count=14),
]

FACT = claim("C001", "broken_limit_rate", "FACT", evidence_refs=["E001"])
RELATIVE = claim("C002", "broken_limit_rate", "RELATIVE_NUMERIC",
                 baseline_refs=["E002"], evidence_refs=["E001", "E002"])
SEMANTIC = claim("C003", "broken_limit_rate", "SEMANTIC", semantic_label="high",
                 baseline_refs=["E002"], threshold_policy_ref="policy/high-v1",
                 evidence_refs=["E001", "E002"])
FORWARD = claim("C004", "broken_limit_rate", "FORWARD", forward_claim=True,
                evidence_refs=["E001"])


class MetricClaimContractTest(unittest.TestCase):
    def _ok(self, r):
        self.assertEqual(schema_errors(r), [], "unexpected schema errors")
        self.assertEqual(validate_review_contract(r), [], "unexpected contract errors")

    def test_01_fact_valid(self):
        self._ok(review([FACT], REGISTRY))

    def test_02_relative_numeric_valid(self):
        self._ok(review([RELATIVE], REGISTRY))

    def test_03_semantic_with_evidence_and_policy_valid(self):
        self._ok(review([SEMANTIC], REGISTRY))

    def test_04_semantic_without_baseline_invalid(self):
        bad = claim("C003", "broken_limit_rate", "SEMANTIC", semantic_label="high",
                    baseline_refs=[], threshold_policy_ref="policy/high-v1",
                    evidence_refs=["E001"])
        r = review([bad], REGISTRY)
        self.assertTrue(schema_errors(r))
        self.assertTrue(validate_review_contract(r))

    def test_05_semantic_without_policy_invalid(self):
        bad = claim("C003", "broken_limit_rate", "SEMANTIC", semantic_label="high",
                    baseline_refs=["E002"], threshold_policy_ref=None,
                    evidence_refs=["E001", "E002"])
        r = review([bad], REGISTRY)
        self.assertTrue(schema_errors(r))
        self.assertTrue(validate_review_contract(r))

    def test_06_forward_structured_valid(self):
        self._ok(review([FORWARD], REGISTRY))

    def test_07_missing_evidence_refs_invalid(self):
        bad = claim("C001", "broken_limit_rate", "FACT", evidence_refs=[])
        self.assertTrue(schema_errors(review([bad], REGISTRY)))

    def test_08_duplicate_claim_id_invalid(self):
        dup = claim("C001", "broken_limit_rate", "FACT", evidence_refs=["E001"])
        errors = validate_review_contract(review([FACT, dup], REGISTRY))
        self.assertTrue(any("duplicate claim_id" in e for e in errors))

    def test_09_unknown_claim_type_invalid(self):
        bad = claim("C001", "broken_limit_rate", "WEIRD", evidence_refs=["E001"])
        self.assertTrue(schema_errors(review([bad], REGISTRY)))

    def test_10_semantic_label_on_fact_invalid(self):
        bad = claim("C001", "broken_limit_rate", "FACT", semantic_label="high",
                    evidence_refs=["E001"])
        self.assertTrue(schema_errors(review([bad], REGISTRY)))

    def test_11_semantic_label_on_relative_invalid(self):
        bad = claim("C001", "broken_limit_rate", "RELATIVE_NUMERIC",
                    semantic_label="low", baseline_refs=["E002"],
                    evidence_refs=["E001", "E002"])
        self.assertTrue(schema_errors(review([bad], REGISTRY)))

    def test_12_forward_false_invalid(self):
        bad = claim("C004", "broken_limit_rate", "FORWARD", forward_claim=False,
                    evidence_refs=["E001"])
        self.assertTrue(schema_errors(review([bad], REGISTRY)))

    def test_13_unknown_evidence_ref_invalid(self):
        bad = claim("C001", "broken_limit_rate", "FACT", evidence_refs=["E999"])
        errors = validate_review_contract(review([bad], REGISTRY))
        self.assertTrue(any("unknown evidence_ref" in e for e in errors))

    def test_14_unknown_baseline_ref_invalid(self):
        bad = claim("C001", "broken_limit_rate", "RELATIVE_NUMERIC",
                    baseline_refs=["E999"], evidence_refs=["E001"])
        errors = validate_review_contract(review([bad], REGISTRY))
        self.assertTrue(any("unknown baseline_ref" in e for e in errors))

    def test_15_baseline_metric_mismatch_invalid(self):
        bad = claim("C001", "promotion_rate", "RELATIVE_NUMERIC",
                    baseline_refs=["E002"], evidence_refs=["E001"])
        errors = validate_review_contract(review([bad], REGISTRY))
        self.assertTrue(any("baseline metric" in e for e in errors))

    def test_16_schema_requires_metric_claims_and_registry(self):
        r = review([FACT], REGISTRY)
        del r["metric_claims"]
        self.assertTrue(schema_errors(r))
        r2 = review([FACT], REGISTRY)
        del r2["evidence_registry"]
        self.assertTrue(schema_errors(r2))

    def test_17_empty_metric_claims_valid(self):
        self._ok(review([], REGISTRY))

    def test_18_normalization_reads_structured_claims(self):
        out = normalize_review(review([FACT, RELATIVE], REGISTRY), case_id="T18")
        claims = out["generator_output"]["metric_claims"]
        self.assertEqual([c["claim_id"] for c in claims], ["C001", "C002"])
        self.assertEqual(out["generator_output"]["claims_contract"],
                         "metric_claims/complete/v1")
        self.assertEqual([e["evidence_id"] for e in out["evidence"]],
                         ["E001", "E002", "E003"])

    def test_19_no_text_scan(self):
        r = review([], REGISTRY)
        r["market"]["inferences"] = [{
            "claim": "炸板率较高，市场分歧明显",
            "confidence": "LOW",
            "evidence": [],
            "counter_evidence": [],
            "evidence_gaps": [],
        }]
        out = normalize_review(r, case_id="T19")
        # A phrase in free text must NOT be extracted into structured claims.
        self.assertEqual(out["generator_output"]["metric_claims"], [])

    def test_20_f002_observable_when_contract_exists(self):
        out = normalize_review(review([FACT, RELATIVE], REGISTRY), case_id="T20")
        result = evaluate_case(EvalCase.from_dict(out))
        self.assertNotEqual(result.rule_status("F002"), STATUS_NOT_OBSERVABLE)
        self.assertEqual(result.rule_status("F002"), "PASS")


if __name__ == "__main__":
    unittest.main()
