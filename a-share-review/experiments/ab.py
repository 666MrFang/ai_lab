"""Replay A/B experiment: deterministic reference vs candidate Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from runner.agent import ReferenceAgent
from runner.runner import run_review
from golden.evaluator import evaluate_golden

REPO = Path(__file__).resolve().parents[1]


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_reviews(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    ref_claims = reference.get("metric_claims") or []
    cand_claims = candidate.get("metric_claims") or []
    ref_roles = {(s.get("code"), tuple(sorted(s.get("roles") or [])))
                 for s in reference.get("stocks") or []}
    cand_roles = {(s.get("code"), tuple(sorted(s.get("roles") or [])))
                  for s in candidate.get("stocks") or []}
    return {
        "regime_equal": reference.get("market_regime", {}).get("state")
                        == candidate.get("market_regime", {}).get("state"),
        "reference_regime": reference.get("market_regime", {}).get("state"),
        "candidate_regime": candidate.get("market_regime", {}).get("state"),
        "reference_claim_count": len(ref_claims),
        "candidate_claim_count": len(cand_claims),
        "reference_stock_roles": sorted([list(x) for x in ref_roles]),
        "candidate_stock_roles": sorted([list(x) for x in cand_roles]),
        "stock_roles_equal": ref_roles == cand_roles,
    }


def run_ab(*, date: str, data_root: str, work_root: str, candidate_agent: Any,
           clock=None) -> Dict[str, Any]:
    root = Path(work_root)
    ref_out, cand_out = root / "reference", root / "candidate"
    failed = root / "failed"
    common = dict(
        date=date, mode="replay", data_root=data_root, failed_root=str(failed),
        overwrite_output=True, clock=clock,
    )
    ref_manifest = run_review(
        **common, output_root=str(ref_out), agent=ReferenceAgent()
    )
    cand_manifest = run_review(
        **common, output_root=str(cand_out), agent=candidate_agent
    )
    result = {
        "protocol": "a-share-review-ab/v1",
        "date": date,
        "same_evidence": (
            ref_manifest.get("evidence_manifest_path")
            == cand_manifest.get("evidence_manifest_path")
        ),
        "reference": {
            "execution_status": ref_manifest.get("execution_status"),
            "review_quality_status": ref_manifest.get("review_quality_status"),
            "eval_rule_status": ref_manifest.get("eval_rule_status"),
        },
        "candidate": {
            "execution_status": cand_manifest.get("execution_status"),
            "review_quality_status": cand_manifest.get("review_quality_status"),
            "eval_rule_status": cand_manifest.get("eval_rule_status"),
        },
        "comparison": None,
        "golden": None,
    }
    if (ref_manifest.get("execution_status") == "SUCCESS"
            and cand_manifest.get("execution_status") == "SUCCESS"):
        reference_review = _load(ref_out / date / "review.json")
        candidate_review = _load(cand_out / date / "review.json")
        result["comparison"] = compare_reviews(reference_review, candidate_review)
        case_path = REPO / "golden" / "cases" / ("%s.json" % date)
        if case_path.exists():
            case = _load(case_path)
            result["golden"] = {
                "case_version": case.get("version"),
                "reference": evaluate_golden(reference_review, case),
                "candidate": evaluate_golden(candidate_review, case),
            }
            # Golden is a publication-quality gate for experiments. A hard
            # deterministic violation is never hidden by pipeline PASS.
            result["golden_gate"] = {
                "reference": result["golden"]["reference"]["status"],
                "candidate": result["golden"]["candidate"]["status"],
                "candidate_blocked": result["golden"]["candidate"]["status"] == "FAIL",
            }
    root.mkdir(parents=True, exist_ok=True)
    (root / "ab_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
