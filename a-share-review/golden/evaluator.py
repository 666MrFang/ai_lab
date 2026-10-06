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

    # Do not silently count delegated rules as PASS. They are explicitly
    # NOT_EVALUATED until a deterministic owner is wired for that rule.
    delegated = [
        {"id": x["id"], "status": "NOT_EVALUATED", "op": x.get("op")}
        for x in case.get("must_not") or []
    ]
    deterministic_pass = bool(checks) and all(x["passed"] is True for x in checks)
    return {
        "date": case["date"],
        "status": "PARTIAL_PASS" if deterministic_pass and delegated else (
            "PASS" if deterministic_pass else "FAIL"
        ),
        "checks": checks,
        "delegated_must_not": delegated,
        "human_score": case.get("human_score"),
    }
