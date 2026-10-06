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
    assert result["status"] == "PASS"
    assert result["delegated_must_not"] == ["G9"]
