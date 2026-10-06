"""Normalize a schema-compliant review.json into Independent Eval input.

Round 3E contract: ``review.json`` is the Claim Source of Truth. This module
reads ONLY structured fields (``metric_claims`` + ``evidence_registry``). It
never reads ``review.md`` and never performs NLP / regex extraction over
natural language.

Because ``review_schema.json`` requires ``metric_claims`` to exist, the schema
itself is the completeness contract, so ``claims_contract`` is set to
``metric_claims/complete/v1`` -- which makes F002 observable (PASS/FAIL),
never NOT_OBSERVABLE.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from models import CLAIM_CONTRACT_METRIC_CLAIMS_V1  # noqa: E402


def _evidence_entries(review: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for entry in review.get("evidence_registry") or []:
        complete = entry.get("complete")
        if entry.get("evidence_type") == "market_metric_baseline":
            if "evidence_status" in entry and entry["evidence_status"]:
                status = entry["evidence_status"]
            elif complete is True:
                status = "COMPLETE"
            elif complete is False:
                status = "INSUFFICIENT_HISTORY"
            else:
                status = None
        else:
            status = entry.get("evidence_status")
        entries.append(
            {
                "evidence_id": entry.get("evidence_id"),
                "type": entry.get("evidence_type"),
                "metric": entry.get("metric"),
                "date": entry.get("date"),
                "window": entry.get("window"),
                "current": entry.get("value"),
                "percentile": entry.get("percentile"),
                "complete": complete,
                "sample_count": entry.get("sample_count"),
                "evidence_status": status,
            }
        )
    return entries


def _claims(review: Dict[str, Any]) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    for claim in review.get("metric_claims") or []:
        claims.append(
            {
                "claim_id": claim.get("claim_id"),
                "metric": claim.get("metric"),
                "claim_type": claim.get("claim_type"),
                "current_value": claim.get("current_value"),
                "value": claim.get("current_value"),
                "unit": claim.get("unit"),
                "semantic_label": claim.get("semantic_label"),
                "baseline_refs": claim.get("baseline_refs") or [],
                "threshold_policy_ref": claim.get("threshold_policy_ref"),
                "evidence_refs": claim.get("evidence_refs") or [],
                "forward_claim": claim.get("forward_claim", False),
                "text_ref": claim.get("text_ref"),
            }
        )
    return claims


def normalize_review(
    review: Dict[str, Any],
    *,
    case_id: str,
    failure_domain: str = "F001+F002",
    semantic_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "date": review.get("date"),
        "failure_domain": failure_domain,
        "evidence": _evidence_entries(review),
        "generator_output": {
            "market_regime": review.get("market_regime", {}),
            "metric_claims": _claims(review),
            "claims_contract": CLAIM_CONTRACT_METRIC_CLAIMS_V1,
        },
        "semantic_policy": semantic_policy,
        "expected_result": {},
    }
