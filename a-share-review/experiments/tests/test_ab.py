import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ab import compare_reviews
from golden.evaluator import evaluate_golden


def test_ab_comparison_does_not_require_exact_prose_equality():
    ref = {"market_regime": {"state": "UNCERTAIN"}, "metric_claims": [{"claim_id": "C1"}],
           "stocks": [{"code": "A", "roles": ["STRONG_STOCK"]}]}
    cand = {"market_regime": {"state": "UNCERTAIN"}, "metric_claims": [{"claim_id": "X1"}],
            "stocks": [{"code": "A", "roles": ["STRONG_STOCK"]}]}
    result = compare_reviews(ref, cand)
    assert result["regime_equal"] is True
    assert result["stock_roles_equal"] is True


def test_golden_is_constraint_based_not_exact_answer():
    case = {
        "date": "2026-09-30",
        "must": [
            {"id": "G1", "path": "market_regime.state", "op": "eq",
             "value": "UNCERTAIN", "reason": "persistence"},
            {"id": "G2", "path": "tomorrow_watch_conditions", "op": "nonempty",
             "reason": "verification"}
        ],
        "must_not": [{"id": "G9"}],
        "human_score": {"status": "UNSCORED"},
    }
    review = {
        "market_regime": {"state": "UNCERTAIN"},
        "tomorrow_watch_conditions": [{"target": "x"}],
        "arbitrary_prose": "models may word this differently",
    }
    result = evaluate_golden(review, case)
    assert result["status"] == "PARTIAL_PASS"
    assert result["must_not_checks"][0]["status"] == "NOT_EVALUATED"


def test_golden_delegated_rules_are_not_silently_passed():
    case = {
        "date": "2026-09-30",
        "must": [{"id": "G1", "path": "market_regime.state", "op": "eq",
                  "value": "UNCERTAIN", "reason": "gate"}],
        "must_not": [{"id": "G2", "op": "news_as_cause_without_causal_evidence"}],
        "human_score": {"status": "UNSCORED"},
    }
    review = {"market_regime": {"state": "UNCERTAIN"}}
    result = evaluate_golden(review, case)
    assert result["status"] == "PASS"
    assert result["must_not_checks"][0]["status"] == "PASS"


def test_golden_rejects_semantic_claim_with_incomplete_baseline():
    case = {"date": "2026-09-30", "must": [
        {"id": "G1", "path": "market_regime.state", "op": "eq",
         "value": "UNCERTAIN", "reason": "gate"}],
        "must_not": [{"id": "G101", "op": "semantic_claim_without_complete_baseline"}]}
    review = {
        "market_regime": {"state": "UNCERTAIN"},
        "metric_claims": [{"claim_type": "SEMANTIC", "baseline_refs": ["E1"]}],
        "evidence_registry": [{"evidence_id": "E1", "complete": False}],
    }
    result = evaluate_golden(review, case)
    assert result["status"] == "FAIL"
    assert result["must_not_checks"][0]["status"] == "FAIL"


def test_golden_rejects_strong_stock_without_historical_sample():
    case = {"date": "2026-09-30", "must": [
        {"id": "G1", "path": "market_regime.state", "op": "eq",
         "value": "UNCERTAIN", "reason": "gate"}],
        "must_not": [{"id": "G104", "op": "strong_stock_from_single_day_rank"}]}
    review = {"market_regime": {"state": "UNCERTAIN"}, "metric_claims": [],
              "evidence_registry": [], "stocks": [
                  {"roles": ["STRONG_STOCK"], "historical_behavior": None}]}
    assert evaluate_golden(review, case)["status"] == "FAIL"
