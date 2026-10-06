"""Deterministic MetricClaim contract validator (Round 3E).

Complements JSON Schema with cross-reference and semantic checks that JSON
Schema cannot express. Pure stdlib. No NLP, no regex over natural language --
the only patterns used match the machine evidence-id format (``^E[0-9]+$``).
"""

from __future__ import annotations

from typing import Any, Dict, List

CLAIM_TYPES = ("FACT", "RELATIVE_NUMERIC", "SEMANTIC", "FORWARD")
SEMANTIC_LABELS = ("high", "low", "strong", "weak")
BASELINE_TYPE = "market_metric_baseline"


def _registry_map(review: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    registry = review.get("evidence_registry") or []
    return {
        entry.get("evidence_id"): entry
        for entry in registry
        if isinstance(entry, dict) and entry.get("evidence_id")
    }


def validate_review_contract(review: Dict[str, Any]) -> List[str]:
    """Return a list of contract errors (empty means valid)."""

    errors: List[str] = []
    registry = _registry_map(review)

    seen: set = set()
    for claim in review.get("metric_claims") or []:
        if not isinstance(claim, dict):
            errors.append("metric_claim is not an object")
            continue

        cid = claim.get("claim_id", "?")
        if cid in seen:
            errors.append("duplicate claim_id: %s" % cid)
        seen.add(cid)

        ctype = claim.get("claim_type")
        if ctype not in CLAIM_TYPES:
            errors.append("%s: unknown claim_type %r" % (cid, ctype))

        for ref in claim.get("evidence_refs") or []:
            if ref not in registry:
                errors.append("%s: unknown evidence_ref %s" % (cid, ref))

        for ref in claim.get("baseline_refs") or []:
            if ref not in registry:
                errors.append("%s: unknown baseline_ref %s" % (cid, ref))
                continue
            entry = registry[ref]
            if entry.get("evidence_type") != BASELINE_TYPE:
                errors.append("%s: baseline_ref %s is not a baseline" % (cid, ref))
            if entry.get("metric") and claim.get("metric") and entry["metric"] != claim["metric"]:
                errors.append(
                    "%s: baseline metric %s != claim metric %s"
                    % (cid, entry["metric"], claim["metric"])
                )

        if ctype == "SEMANTIC":
            if not claim.get("baseline_refs"):
                errors.append("%s: SEMANTIC requires baseline_refs" % cid)
            if not claim.get("threshold_policy_ref"):
                errors.append("%s: SEMANTIC requires threshold_policy_ref" % cid)
            if claim.get("semantic_label") not in SEMANTIC_LABELS:
                errors.append(
                    "%s: SEMANTIC requires semantic_label in %s" % (cid, SEMANTIC_LABELS)
                )
        elif claim.get("semantic_label") is not None:
            errors.append("%s: non-SEMANTIC claim must have semantic_label=null" % cid)

        if ctype == "FORWARD":
            if claim.get("forward_claim") is not True:
                errors.append("%s: FORWARD requires forward_claim=true" % cid)
        elif claim.get("forward_claim") is True:
            errors.append("%s: non-FORWARD claim must have forward_claim=false" % cid)

    return errors
