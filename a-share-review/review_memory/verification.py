"""Machine-verifiable forward conditions and D+1 settlement."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def metric_value(normalized: Dict[str, Any], metric: str) -> Optional[float]:
    date = normalized.get("date")
    key = "market_metric:%s:%s" % (metric, date)
    entry = (normalized.get("evidence") or {}).get(key) or {}
    value = entry.get("value")
    return float(value) if value is not None else None


def verify_conditions(
    conditions: List[Dict[str, Any]], normalized: Dict[str, Any]
) -> Dict[str, Any]:
    results = []
    for condition in conditions or []:
        metric = condition.get("metric")
        operator = condition.get("operator")
        expected = condition.get("expected_value")
        actual = metric_value(normalized, metric) if metric else None
        if actual is None or expected is None or operator not in {"gt", "gte", "lt", "lte", "eq"}:
            status = "NOT_OBSERVABLE"
        else:
            expected = float(expected)
            passed = {
                "gt": actual > expected, "gte": actual >= expected,
                "lt": actual < expected, "lte": actual <= expected,
                "eq": abs(actual - expected) <= 1e-9,
            }[operator]
            status = "OBSERVED_PASS" if passed else "OBSERVED_FAIL"
        results.append({
            "condition_id": condition.get("condition_id"),
            "metric": metric, "operator": operator,
            "expected_value": condition.get("expected_value"),
            "actual_value": actual, "status": status,
            "observed_date": normalized.get("date"),
        })
    return {
        "version": "verification-result/v1",
        "observed_date": normalized.get("date"),
        "results": results,
        "summary": {
            "pass": sum(x["status"] == "OBSERVED_PASS" for x in results),
            "fail": sum(x["status"] == "OBSERVED_FAIL" for x in results),
            "not_observable": sum(x["status"] == "NOT_OBSERVABLE" for x in results),
        },
    }
