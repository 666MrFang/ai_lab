"""Independent Eval Harness V0.1 — evaluator.

Deterministic, offline, LLM-free. Same (evidence, generator output, policy)
always yields the same EvalResult.

Scope: AGENT-F001 (forced regime classification under insufficient persistence
evidence) and AGENT-F002 (uncalibrated metric semantic interpretation) only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from models import (
    CLAIM_CONTRACT_METRIC_CLAIMS_V1,
    CONFIRMED_REGIMES,
    FAILURE_AGENT_F001,
    FAILURE_AGENT_F002,
    HIGH_LABELS,
    LOW_LABELS,
    NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS,
    OUT_OF_SCOPE_FORWARD_CLAIM,
    OUT_OF_SCOPE_UNKNOWN_LABEL,
    STATUS_FAIL,
    STATUS_NOT_OBSERVABLE,
    STATUS_OUT_OF_SCOPE,
    STATUS_PASS,
    Check,
    EvalCase,
    EvalResult,
    Evidence,
)
from policies import SemanticCalibrationPolicy

RULE_F001 = "F001"
RULE_F002 = "F002"


# ---------------------------------------------------------------------------
# F001 — Forced Regime Classification Under Insufficient Persistence Evidence
# ---------------------------------------------------------------------------
def _check_f001(case: EvalCase) -> Optional[Check]:
    regime = case.generator_output.get("market_regime")
    if not isinstance(regime, dict):
        return None  # not a regime claim; F001 not applicable

    state = regime.get("state")
    acknowledged = bool(regime.get("persistence_evidence_acknowledged", False))

    # Persistence is insufficient if ANY provided persistence baseline is not
    # proven complete (complete is not True). Unknown counts as insufficient.
    incomplete = [
        ev
        for ev in case.evidence
        if ev.is_persistence_baseline and ev.complete is not True
    ]
    incomplete_refs = [ev.evidence_id for ev in incomplete]

    if state not in CONFIRMED_REGIMES:
        return Check(
            rule=RULE_F001,
            passed=True,
            reason=(
                f"state={state!r} is not a confirmed regime claim; "
                "insufficient-persistence classification is allowed"
            ),
            claim_refs=["market_regime.state"],
        )

    if not incomplete:
        return Check(
            rule=RULE_F001,
            passed=True,
            reason=(
                f"state={state!r} with complete persistence evidence; "
                "F001 does not fire (this does not validate the regime itself)"
            ),
            evidence_refs=[ev.evidence_id for ev in case.evidence if ev.is_persistence_baseline],
            claim_refs=["market_regime.state"],
        )

    if acknowledged:
        return Check(
            rule=RULE_F001,
            passed=True,
            reason=(
                "confirmed regime claim with explicit acknowledgment that "
                "persistence evidence is insufficient"
            ),
            evidence_refs=incomplete_refs,
            claim_refs=["market_regime.state"],
        )

    return Check(
        rule=RULE_F001,
        passed=False,
        failure_code=FAILURE_AGENT_F001,
        reason=(
            f"confirmed regime {state!r} asserted while persistence evidence is "
            "incomplete and not acknowledged"
        ),
        evidence_refs=incomplete_refs,
        claim_refs=["market_regime.state"],
    )


# ---------------------------------------------------------------------------
# F002 — Uncalibrated Metric Semantic Interpretation
# ---------------------------------------------------------------------------
def _find_baseline(case: EvalCase, claim: Dict[str, Any]) -> Optional[Evidence]:
    refs = claim.get("evidence_refs") or []
    for evidence in case.evidence:
        if evidence.evidence_id in refs and evidence.is_persistence_baseline:
            return evidence
    metric = claim.get("metric")
    for evidence in case.evidence:
        if evidence.is_persistence_baseline and evidence.metric == metric:
            return evidence
    return None


def _check_f002(case: EvalCase) -> List[Check]:
    output = case.generator_output
    claims = output.get("metric_claims")
    contract = output.get("claims_contract")

    # F002 is only observable when the generator declares a structured metric
    # claim contract guaranteeing that every numeric semantic claim is present
    # in ``metric_claims``. Otherwise a missing/None ``semantic_label`` is NOT
    # evidence of "no semantic claim" -> NOT_OBSERVABLE (never a vacuous PASS).
    if claims is None or contract != CLAIM_CONTRACT_METRIC_CLAIMS_V1:
        return [
            Check(
                rule=RULE_F002,
                passed=None,
                not_observable_code=NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS,
                reason=(
                    "semantic claims are not represented in structured generator "
                    "output (no metric_claims contract); F002 cannot be judged"
                ),
                claim_refs=[],
            )
        ]

    policy = SemanticCalibrationPolicy.from_dict(case.semantic_policy)
    checks: List[Check] = []

    for claim in claims:
        claim_id = claim.get("claim_id", "?")
        metric = claim.get("metric")
        label = claim.get("semantic_label")

        if claim.get("forward_claim"):
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=None,
                    out_of_scope_code=OUT_OF_SCOPE_FORWARD_CLAIM,
                    reason=(
                        "forward-looking claim; out of scope for F002 "
                        "(future eval rule candidate)"
                    ),
                    claim_refs=[claim_id],
                )
            )
            continue

        if label is None:
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=True,
                    reason="numeric fact only; no semantic label to calibrate",
                    claim_refs=[claim_id],
                )
            )
            continue

        baseline = _find_baseline(case, claim)

        if baseline is None:
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=False,
                    failure_code=FAILURE_AGENT_F002,
                    reason=(
                        f"semantic label {label!r} for {metric!r} without any "
                        "baseline/threshold evidence"
                    ),
                    claim_refs=[claim_id],
                )
            )
            continue

        if baseline.complete is not True:
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=False,
                    failure_code=FAILURE_AGENT_F002,
                    reason=(
                        f"semantic label {label!r} for {metric!r} with an "
                        "incomplete baseline (evidence_status="
                        f"{baseline.evidence_status!r})"
                    ),
                    evidence_refs=[baseline.evidence_id],
                    claim_refs=[claim_id],
                )
            )
            continue

        supported = policy.label_supported(label, baseline.percentile)

        if supported is None:
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=None,
                    out_of_scope_code=OUT_OF_SCOPE_UNKNOWN_LABEL,
                    reason=(
                        f"semantic label {label!r} cannot be judged by the "
                        "provided policy (unknown label or missing threshold)"
                    ),
                    evidence_refs=[baseline.evidence_id],
                    claim_refs=[claim_id],
                )
            )
        elif supported:
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=True,
                    reason=(
                        f"semantic label {label!r} supported by baseline "
                        f"percentile={baseline.percentile}"
                    ),
                    evidence_refs=[baseline.evidence_id],
                    claim_refs=[claim_id],
                )
            )
        else:
            checks.append(
                Check(
                    rule=RULE_F002,
                    passed=False,
                    failure_code=FAILURE_AGENT_F002,
                    reason=(
                        f"semantic label {label!r} contradicts calibration: "
                        f"percentile={baseline.percentile} does not satisfy policy"
                    ),
                    evidence_refs=[baseline.evidence_id],
                    claim_refs=[claim_id],
                )
            )

    return checks


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def evaluate_case(case: EvalCase) -> EvalResult:
    domain = (case.failure_domain or "").upper()
    run_f001 = "F001" in domain
    run_f002 = "F002" in domain
    if not run_f001 and not run_f002:
        run_f001 = run_f002 = True

    checks: List[Check] = []
    if run_f001:
        f001 = _check_f001(case)
        if f001 is not None:
            checks.append(f001)
    if run_f002:
        checks.extend(_check_f002(case))

    evaluated = [check for check in checks if check.passed is not None]
    failures = [check for check in evaluated if check.passed is False]
    not_observable = [check for check in checks if check.not_observable_code]
    out_of_scope = [
        check
        for check in checks
        if check.passed is None and not check.not_observable_code
    ]

    if failures:
        status = STATUS_FAIL
    elif not_observable:
        status = STATUS_NOT_OBSERVABLE
    elif out_of_scope:
        status = STATUS_OUT_OF_SCOPE
    else:
        status = STATUS_PASS

    failure_codes = sorted(
        {check.failure_code for check in failures if check.failure_code}
    )
    out_of_scope_codes = sorted(
        {check.out_of_scope_code for check in out_of_scope if check.out_of_scope_code}
    )
    not_observable_codes = sorted(
        {
            check.not_observable_code
            for check in not_observable
            if check.not_observable_code
        }
    )

    return EvalResult(
        case_id=case.case_id,
        status=status,
        failure_codes=failure_codes,
        out_of_scope=out_of_scope_codes,
        checks=checks,
        not_observable=not_observable_codes,
    )


def evaluate_cases(cases: Sequence[EvalCase]) -> List[EvalResult]:
    return [evaluate_case(case) for case in cases]


def load_cases(path: str) -> List[EvalCase]:
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase.from_dict(item) for item in data]
