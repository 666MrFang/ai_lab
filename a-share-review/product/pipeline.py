"""End-to-end product lifecycle built on the frozen Production Runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from review_memory.service import build_outlook, build_review_record, settle_record
from review_memory.store import ReviewMemoryStore
from review_memory.verification import verify_conditions
from runner.runner import run_review
from .dashboard import render_dashboard


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _settle_prior_records(
    memory: ReviewMemoryStore,
    market_root: Path,
    current_date: str,
) -> int:
    changed = 0
    # Evidence Store may contain dates that have never been ingested as
    # review-memory records. Settlement must use market snapshots, not the
    # memory index, otherwise an older record can never reach T+5 unless every
    # intermediate day was separately ingested first.
    available = (
        sorted(
            p.name for p in market_root.iterdir()
            if p.is_dir()
            and p.name <= current_date
            and (p / "normalized" / "market.json").is_file()
        )
        if market_root.exists()
        else []
    )
    for date in memory.dates():
        if date >= current_date:
            continue
        record = memory.load(date)
        future_dates = [d for d in available if d > date][:5]
        evidence = [
            _load(market_root / d / "normalized" / "market.json")
            for d in future_dates
        ]
        settled = settle_record(record, evidence)
        if evidence:
            conditions = (
                (settled.get("review_snapshot") or {}).get("tomorrow_watch_conditions") or []
            )
            machine_conditions = [
                item for item in conditions
                if item.get("horizon_sessions") == 1 and item.get("condition_id")
            ]
            if machine_conditions:
                settled["d1_verification"] = verify_conditions(
                    machine_conditions, evidence[0]
                )
        if settled != record:
            memory.save(date, settled, overwrite=True)
            changed += 1
    return changed


def run_product_day(
    *,
    date: str,
    mode: str = "auto",
    data_root: Optional[str] = None,
    output_root: Optional[str] = None,
    failed_root: Optional[str] = None,
    memory_root: Optional[str] = None,
    overwrite_output: bool = False,
    agent: Any = None,
    tool_caller_factory: Any = None,
    clock: Any = None,
    min_pattern_sample: int = 8,
) -> Dict[str, Any]:
    repo = Path(__file__).resolve().parents[1]
    market_root = Path(data_root) if data_root else repo / "data" / "market"
    out_root = Path(output_root) if output_root else repo / "output"
    mem_root = Path(memory_root) if memory_root else repo / "data" / "review_history"

    manifest = run_review(
        date=date, mode=mode, data_root=str(market_root),
        output_root=str(out_root), failed_root=failed_root,
        overwrite_output=overwrite_output, agent=agent,
        tool_caller_factory=tool_caller_factory, clock=clock,
    )
    if manifest.get("execution_status") != "SUCCESS":
        return manifest

    day_dir = out_root / date
    review = _load(day_dir / "review.json")
    normalized = _load(market_root / date / "normalized" / "market.json")
    memory = ReviewMemoryStore(mem_root)

    record = build_review_record(date, review, normalized, manifest)
    memory.save(date, record, overwrite=True)
    settled_count = _settle_prior_records(memory, market_root, date)

    # Reload in case this date had previously existed and was overwritten.
    current = memory.load(date)
    outlook = build_outlook(
        date, current, memory.records_before(date), min_pattern_sample
    )
    (day_dir / "outlook.json").write_text(
        json.dumps(outlook, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dashboard = render_dashboard(review, outlook, current)
    (day_dir / "dashboard.html").write_text(dashboard, encoding="utf-8")

    product_manifest = {
        "version": "a-share-review-product/v1",
        "date": date,
        "runner_execution_status": manifest.get("execution_status"),
        "review_quality_status": manifest.get("review_quality_status"),
        "memory_status": current.get("status"),
        "prior_records_updated": settled_count,
        "calibrated_pattern_count": outlook.get("calibrated_pattern_count"),
        "artifacts": [
            "review.json", "review.md", "eval.json", "run_manifest.json",
            "outlook.json", "dashboard.html",
        ],
    }
    (day_dir / "product_manifest.json").write_text(
        json.dumps(product_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**manifest, "product": product_manifest}
