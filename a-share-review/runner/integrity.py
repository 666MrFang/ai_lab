"""Evidence Integrity Check: the review must not tamper with stored evidence."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

_FLOAT_FIELDS = ("value", "avg", "median", "percentile")
_EXACT_FIELDS = ("window", "sample_count", "complete", "unit")


def _close(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return a == b


def _store_index(stored_evidence: Dict[str, Any]) -> Dict[Tuple, Dict[str, Any]]:
    index: Dict[Tuple, Dict[str, Any]] = {}
    for entry in stored_evidence.values():
        etype = entry.get("evidence_type")
        if etype == "market_metric":
            ident = ("market_metric", entry.get("metric"), entry.get("date"), None)
        elif etype == "market_metric_baseline":
            ident = ("market_metric_baseline", entry.get("metric"), entry.get("date"),
                     entry.get("window"))
        else:
            continue
        index[ident] = entry
    return index


def validate_integrity(review: Dict[str, Any], stored_normalized: Dict[str, Any]) -> List[str]:
    """Return integrity errors (empty == review evidence matches the store)."""

    errors: List[str] = []
    index = _store_index(stored_normalized.get("evidence", {}))

    for entry in review.get("evidence_registry") or []:
        etype = entry.get("evidence_type")
        if etype not in ("market_metric", "market_metric_baseline"):
            errors.append("unsupported evidence_type: %s" % etype)
            continue
        ident = (etype, entry.get("metric"), entry.get("date"),
                 entry.get("window") if etype == "market_metric_baseline" else None)
        stored = index.get(ident)
        if stored is None:
            errors.append("evidence not found in store: %s" % (ident,))
            continue

        if etype == "market_metric":
            if not _close(entry.get("value"), stored.get("value")):
                errors.append("evidence value mismatch for %s: review=%s store=%s"
                              % (ident, entry.get("value"), stored.get("value")))
            if entry.get("unit") != stored.get("unit"):
                errors.append("evidence unit mismatch for %s" % (ident,))
        else:
            # review stores baseline "value" == stored "current"
            if not _close(entry.get("value"), stored.get("current")):
                errors.append("baseline current mismatch for %s" % (ident,))
            for field in ("avg", "median", "percentile"):
                if not _close(entry.get(field), stored.get(field)):
                    errors.append("baseline %s mismatch for %s" % (field, ident))
            for field in ("window", "sample_count", "complete", "unit"):
                if entry.get(field) != stored.get(field):
                    errors.append("baseline %s mismatch for %s" % (field, ident))

    return errors
