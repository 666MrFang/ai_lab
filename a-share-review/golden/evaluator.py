"""Deterministic Golden constraints that do not require an LLM judge."""

from typing import Any, Dict, List


def _get(obj: Dict[str, Any], path: str):
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


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

    # Existing independent Eval/Schema/Contract own the complex must-not rules.
    # Golden records them as review criteria instead of duplicating semantics.
    return {
        "date": case["date"],
        "status": "PASS" if checks and all(x["passed"] is True for x in checks) else "FAIL",
        "checks": checks,
        "delegated_must_not": [x["id"] for x in case.get("must_not") or []],
        "human_score": case.get("human_score"),
    }
