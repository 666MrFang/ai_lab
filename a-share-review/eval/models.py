"""Independent Eval Harness V0.1 — domain models.

This harness is independent of the generator. It consumes a *normalized,
structured* claim contract plus structured tool evidence, and applies explicit
deterministic rules. It never parses natural language, never calls an LLM and
never touches the network.

Normalized generator output contract (input to the evaluator):

    {
      "market_regime": {
        "state": "MAIN_UPTREND" | "ROTATION" | "LOSS_EFFECT" | "ICE_POINT" | "UNCERTAIN",
        "confidence": "HIGH" | "MEDIUM" | "LOW",
        "persistence_evidence_acknowledged": <bool>   # optional, default false
      },
      "metric_claims": [
        {
          "claim_id": "C001",
          "metric": "broken_limit_rate",
          "value": 18.75,
          "semantic_label": "high" | "low" | "strong" | "weak" | null,
          "evidence_refs": ["E001"],
          "forward_claim": <bool>
        }
      ]
    }

Structured evidence items (input to the evaluator):

    {
      "evidence_id": "E001",
      "type": "market_metric_baseline",
      "metric": "broken_limit_rate",
      "date": "2026-09-30",
      "window": 5,
      "current": 18.75,
      "percentile": 40.0,
      "complete": true,
      "sample_count": 5,
      "evidence_status": "COMPLETE"
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---- regime taxonomy (mirrors schemas/review_schema.json) ------------------
REGIME_MAIN_UPTREND = "MAIN_UPTREND"
REGIME_ROTATION = "ROTATION"
REGIME_LOSS_EFFECT = "LOSS_EFFECT"
REGIME_ICE_POINT = "ICE_POINT"
REGIME_UNCERTAIN = "UNCERTAIN"

CONFIRMED_REGIMES = frozenset(
    {REGIME_MAIN_UPTREND, REGIME_ROTATION, REGIME_LOSS_EFFECT, REGIME_ICE_POINT}
)
ALL_REGIMES = CONFIRMED_REGIMES | {REGIME_UNCERTAIN}

CONFIDENCE_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW"})

# ---- semantic labels -------------------------------------------------------
HIGH_LABELS = frozenset({"high", "strong"})
LOW_LABELS = frozenset({"low", "weak"})

# ---- result status ---------------------------------------------------------
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_OUT_OF_SCOPE = "OUT_OF_SCOPE"
STATUS_NOT_OBSERVABLE = "NOT_OBSERVABLE"

# ---- out-of-scope codes ----------------------------------------------------
OUT_OF_SCOPE_FORWARD_CLAIM = "OUT_OF_SCOPE_FORWARD_CLAIM"
OUT_OF_SCOPE_UNKNOWN_LABEL = "OUT_OF_SCOPE_UNKNOWN_SEMANTIC_LABEL"

# ---- not-observable codes --------------------------------------------------
# F002 can only be judged when the generator declares a structured metric-claim
# contract. Without it, a missing/None semantic label is NOT evidence that no
# semantic claim exists -> NOT_OBSERVABLE (never a vacuous PASS).
CLAIM_CONTRACT_METRIC_CLAIMS_V1 = "metric_claims/complete/v1"
NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS = "NOT_OBSERVABLE_NO_STRUCTURED_CLAIMS"

FAILURE_AGENT_F001 = "AGENT-F001"
FAILURE_AGENT_F002 = "AGENT-F002"

PERSISTENCE_BASELINE_TYPE = "market_metric_baseline"


@dataclass(frozen=True)
class Evidence:
    """A single structured evidence item provided to the evaluator."""

    evidence_id: str
    type: str
    metric: Optional[str] = None
    date: Optional[str] = None
    window: Optional[int] = None
    current: Optional[float] = None
    percentile: Optional[float] = None
    complete: Optional[bool] = None
    sample_count: Optional[int] = None
    evidence_status: Optional[str] = None

    @property
    def is_persistence_baseline(self) -> bool:
        return self.type == PERSISTENCE_BASELINE_TYPE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        return cls(
            evidence_id=data["evidence_id"],
            type=data["type"],
            metric=data.get("metric"),
            date=data.get("date"),
            window=data.get("window"),
            current=data.get("current"),
            percentile=data.get("percentile"),
            complete=data.get("complete"),
            sample_count=data.get("sample_count"),
            evidence_status=data.get("evidence_status"),
        )


@dataclass(frozen=True)
class Check:
    """A single rule evaluation.

    ``passed`` is ``None`` for checks that are not judged: ``out_of_scope``
    (recorded, not judged) or ``not_observable`` (the claim is not represented
    in structured output, so it cannot be judged).
    """

    rule: str
    passed: Optional[bool]
    reason: str
    evidence_refs: List[str] = field(default_factory=list)
    claim_refs: List[str] = field(default_factory=list)
    failure_code: Optional[str] = None
    out_of_scope_code: Optional[str] = None
    not_observable_code: Optional[str] = None


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    status: str
    failure_codes: List[str]
    out_of_scope: List[str]
    checks: List[Check]
    not_observable: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == STATUS_PASS

    def rule_status(self, rule: str) -> Optional[str]:
        """Aggregate the per-rule outcome (PASS/FAIL/NOT_OBSERVABLE/OUT_OF_SCOPE)."""

        checks = [check for check in self.checks if check.rule == rule]
        if not checks:
            return None
        if any(check.passed is False for check in checks):
            return STATUS_FAIL
        if any(check.not_observable_code for check in checks):
            return STATUS_NOT_OBSERVABLE
        if any(check.passed is None for check in checks):
            return STATUS_OUT_OF_SCOPE
        return STATUS_PASS


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    date: str
    failure_domain: str
    evidence: List[Evidence]
    generator_output: Dict[str, Any]
    expected_result: Dict[str, Any]
    semantic_policy: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalCase":
        return cls(
            case_id=data["case_id"],
            date=data["date"],
            failure_domain=data["failure_domain"],
            evidence=[Evidence.from_dict(item) for item in data.get("evidence", [])],
            generator_output=data.get("generator_output", {}),
            expected_result=data.get("expected_result", {}),
            semantic_policy=data.get("semantic_policy"),
        )
