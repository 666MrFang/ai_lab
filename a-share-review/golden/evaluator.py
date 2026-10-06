"""Deterministic Golden constraints. No LLM judge and no prose heuristics."""

from typing import Any, Dict, List


def _get(obj: Dict[str, Any], path: str):
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _must_not(review: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
    op = rule.get("op")
    violated = False
    observable = True

    if op == "semantic_claim_without_complete_baseline":
        registry = {x.get("evidence_id"): x for x in review.get("evidence_registry") or []}
        for claim in review.get("metric_claims") or []:
            if claim.get("claim_type") != "SEMANTIC":
                continue
            refs = claim.get("baseline_refs") or []
            if not refs or any((registry.get(r) or {}).get("complete") is not True for r in refs):
                violated = True
                break
    elif op == "confirmed_regime_with_incomplete_persistence":
        state = (review.get("market_regime") or {}).get("state")
        gaps = " ".join((review.get("market_regime") or {}).get("evidence_gaps") or []).lower()
        incomplete = "20d" in gaps and ("incomplete" in gaps or "不足" in gaps or "缺" in gaps)
        violated = state != "UNCERTAIN" and incomplete
    elif op == "news_as_cause_without_causal_evidence":
        # Causal assertions are not represented by a structured causal contract yet.
        # Refuse to infer them from prose.
        observable = False
    elif op == "strong_stock_from_single_day_rank":
        # STRONG_STOCK must carry historical_behavior with a positive sample.
        for stock in review.get("stocks") or []:
            if "STRONG_STOCK" in (stock.get("roles") or []):
                hist = stock.get("historical_behavior")
                if not isinstance(hist, dict) or int(hist.get("sample_size") or 0) <= 0:
                    violated = True
                    break
    elif op == "capacity_candidate_as_confirmed_leader":
        # Schema intentionally has no LEADER role. Guard against role expansion.
        for stock in review.get("stocks") or []:
            roles = set(stock.get("roles") or [])
            if "CAPACITY_CORE_CANDIDATE" in roles and (
                "LEADER" in roles or "CONFIRMED_LEADER" in roles
            ):
                violated = True
                break
    else:
        observable = False

    return {
        "id": rule["id"],
        "op": op,
        "status": ("NOT_EVALUATED" if not observable else
                   ("FAIL" if violated else "PASS")),
    }


def evaluate_golden(review: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for rule in case.get("must") or []:
        value = _get(review, rule.get("path", ""))
        op = rule["op"]
        if op == "eq":
            passed = value == rule.get("value")
        elif op == "nonempty":
            passed = bool(value)
        elif op == "structured_complete_contract":
            passed = (
                isinstance(value, list)
                and all(isinstance(x, dict) and x.get("claim_id") for x in value)
            )
        else:
            passed = None
        checks.append({"id": rule["id"], "passed": passed, "reason": rule["reason"]})

    must_not = [_must_not(review, x) for x in case.get("must_not") or []]
    deterministic_pass = bool(checks) and all(x["passed"] is True for x in checks)
    hard_fail = any(x["status"] == "FAIL" for x in must_not)
    incomplete = any(x["status"] == "NOT_EVALUATED" for x in must_not)
    status = "FAIL" if (not deterministic_pass or hard_fail) else (
        "PARTIAL_PASS" if incomplete else "PASS"
    )
    return {
        "date": case["date"], "status": status, "checks": checks,
        "must_not_checks": must_not,
        "human_score": case.get("human_score"),
    }
