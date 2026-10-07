"""Production Runner V0.1: Evidence -> Agent -> Validation -> Eval -> Artifacts."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from jsonschema import Draft202012Validator

from .agent import ReferenceAgent
from .identity import EVAL_FILES, SCHEMA_PATH, SKILL_PATH, identities
from .integrity import validate_integrity

REPO = Path(__file__).resolve().parents[1]
EVAL_DIR = REPO / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import contract as eval_contract  # noqa: E402
import evaluator as eval_evaluator  # noqa: E402
import normalize as eval_normalize  # noqa: E402
from models import EvalCase  # noqa: E402

from collector.collector import STATUS_FAILED, collect, normalized_for  # noqa: E402
from collector.mcp_client import McpStdioToolCaller  # noqa: E402
from collector.replay import replay_market  # noqa: E402
from collector.store import EvidenceStore, ReplayDataNotFound  # noqa: E402

PENDING, RUNNING, PASS, FAIL, SKIPPED = "PENDING", "RUNNING", "PASS", "FAIL", "SKIPPED"

_EXEC_STAGES = (
    "resolve_evidence",
    "run_agent",
    "schema_validation",
    "contract_validation",
    "evidence_integrity",
    "publish",
)


class OutputExists(Exception):
    pass


def _outcome(result: Any) -> Dict[str, Any]:
    return {
        "status": result.status,
        "failure_codes": result.failure_codes,
        "out_of_scope": result.out_of_scope,
        "not_observable": result.not_observable,
        "rule_status": {"F001": result.rule_status("F001"), "F002": result.rule_status("F002")},
        "checks": [
            {"rule": c.rule, "passed": c.passed, "failure_code": c.failure_code,
             "not_observable_code": c.not_observable_code, "evidence_refs": c.evidence_refs,
             "claim_refs": c.claim_refs, "reason": c.reason}
            for c in result.checks
        ],
    }


def run_review(
    *,
    date: str,
    mode: str = "auto",
    data_root: Optional[str] = None,
    output_root: Optional[str] = None,
    failed_root: Optional[str] = None,
    overwrite_output: bool = False,
    agent: Any = None,
    tool_caller_factory: Any = None,
    clock: Optional[Callable[[], str]] = None,
) -> Dict[str, Any]:
    data_root = Path(data_root) if data_root else REPO / "data" / "market"
    output_root = Path(output_root) if output_root else REPO / "output"
    failed_root = Path(failed_root) if failed_root else REPO / "failed_runs"
    now = clock or (lambda: dt.datetime.now().isoformat(timespec="seconds"))
    run_id = uuid.uuid4().hex[:12]
    started = now()
    agent = agent or ReferenceAgent()
    store = EvidenceStore(str(data_root))

    stages: List[Dict[str, str]] = []
    errors: List[str] = []
    schema_errors: List[str] = []
    contract_errors: List[str] = []
    integrity_errors: List[str] = []

    def add_stage(name: str, status: str, message: str = "") -> None:
        stages.append({"name": name, "status": status, "timestamp": now(), "message": message})
        print("STAGE|%s|%s|%s" % (name, status, message))

    def skip_rest(after: str) -> None:
        names = ["resolve_evidence", "run_agent", "schema_validation",
                 "contract_validation", "evidence_integrity", "independent_eval", "publish"]
        started_skipping = False
        for name in names:
            if name == after:
                started_skipping = True
                continue
            if started_skipping:
                add_stage(name, SKIPPED, "upstream %s failed" % after)

    review: Optional[Dict[str, Any]] = None
    review_md: Optional[str] = None
    normalized: Optional[Dict[str, Any]] = None
    manifest: Optional[Dict[str, Any]] = None
    evidence_mode_used = None
    evidence_manifest_path = None
    collection_status = None
    eval_payload: Optional[Dict[str, Any]] = None
    review_quality_status = SKIPPED
    agent_execution: Dict[str, Any] = {}

    # --- Stage 1: resolve evidence ------------------------------------
    try:
        if mode == "replay" or (mode == "auto" and store.exists(date)):
            evidence_mode_used = "replay"
            data = replay_market(store, date)
            manifest = data["manifest"]
            normalized = data["normalized"]
            evidence_manifest_path = str(store.date_dir(date) / "manifest.json")
            collection_status = manifest.get("status")
            add_stage("resolve_evidence", PASS, "replay (no Market MCP)")
        elif mode in ("live", "auto"):
            evidence_mode_used = "live"
            factory = tool_caller_factory or McpStdioToolCaller
            with factory() as caller:
                collection = collect(caller, date)
                normalized = normalized_for(collection)
            if collection.status == STATUS_FAILED:
                failed = "; ".join(collection.tools_failed) or "unknown required tool"
                add_stage("resolve_evidence", FAIL, "live collection FAILED: %s" % failed)
                errors.append("live collection FAILED: %s" % failed)
                for record in collection.records:
                    if record.category == "required" and not record.success:
                        print(
                            "COLLECTION_FAILURE|tool=%s|error_code=%s|args=%s" % (
                                record.tool, record.error_code or "UNKNOWN_ERROR",
                                json.dumps(record.arguments, ensure_ascii=False, sort_keys=True),
                            ),
                            flush=True,
                        )
            else:
                target = store.save(date, collection, normalized)
                data = store.load(date)
                manifest = data["manifest"]
                normalized = data["normalized"]
                evidence_manifest_path = str(target / "manifest.json")
                collection_status = collection.status
                add_stage("resolve_evidence", PASS, "live collect (%s)" % collection.status)
        else:
            add_stage("resolve_evidence", FAIL, "unknown mode %r" % mode)
            errors.append("unknown mode")
    except ReplayDataNotFound:
        add_stage("resolve_evidence", FAIL, "REPLAY_DATA_NOT_FOUND")
        errors.append("REPLAY_DATA_NOT_FOUND")
    except Exception as exc:  # noqa: BLE001
        add_stage("resolve_evidence", FAIL, type(exc).__name__)
        errors.append("resolve failed: %s" % type(exc).__name__)

    if stages[-1]["status"] != PASS:
        skip_rest("resolve_evidence")
        return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                         evidence_manifest_path, collection_status, stages, errors,
                         review, review_md, normalized, eval_payload,
                         execution="FAIL", quality=SKIPPED,
                         output_root=output_root, failed_root=failed_root,
                         overwrite_output=overwrite_output,
                         extra_partials={})

    # CURRENT_ONLY optional evidence is quarantined by the collector and
    # excluded from the normalized reasoning view. It remains in raw evidence
    # and the manifest for auditability, but must not kill an otherwise valid
    # historical review. Required temporal violations are still fatal.
    quarantined = list((manifest or {}).get("temporal_quarantine") or [])
    if quarantined:
        required_sigs = {
            item for item in quarantined
            if any(item.startswith(tool + "(") for tool in (
                "get_index_performance", "get_market_history_summary",
                "get_market_breadth", "get_sector_ranking",
                "get_market_metric_baseline",
            ))
        }
        if required_sigs:
            add_stage("temporal_integrity", FAIL, "required CURRENT_ONLY evidence date mismatch")
            errors.append("required temporal evidence quarantined")
            skip_rest("resolve_evidence")
            return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                             evidence_manifest_path, collection_status, stages, errors,
                             review, review_md, normalized, eval_payload,
                             execution="FAIL", quality=SKIPPED,
                             output_root=output_root, failed_root=failed_root,
                             overwrite_output=overwrite_output,
                             extra_partials={"temporal_quarantine.json": json.dumps(
                                 quarantined, ensure_ascii=False, indent=2)})
        print("TEMPORAL_QUARANTINE|OPTIONAL|count=%d" % len(quarantined))

    # --- Stage 2: run agent -------------------------------------------
    agent_input = {"date": date, "manifest": manifest, "normalized": normalized,
                   "skill_path": str(SKILL_PATH), "schema_path": str(SCHEMA_PATH)}
    try:
        agent_result = agent(agent_input)
        review = agent_result.get("review")
        review_md = agent_result.get("review_md")
        agent_execution = dict(agent_result.get("execution") or {})
        if not isinstance(review, dict):
            raise ValueError("agent did not return a review object")
        add_stage("run_agent", PASS, getattr(agent, "name", "agent"))
    except Exception as exc:  # noqa: BLE001
        error_code = getattr(exc, "code", type(exc).__name__)
        agent_execution = dict(getattr(agent, "last_execution", {}) or {})
        if agent_execution:
            agent_execution.setdefault("error_code", error_code)
        add_stage("run_agent", FAIL, str(error_code))
        errors.append("agent failed: %s" % error_code)
        stderr = str(agent_execution.get("stderr") or "").strip()
        if stderr:
            # Provider adapters must never print credentials. Keep the terminal
            # diagnostic bounded so API error details are visible without log spam.
            diagnostic = " ".join(stderr.split())[:500]
            print("AGENT_DIAGNOSTIC|%s" % diagnostic)
        skip_rest("run_agent")
        return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                         evidence_manifest_path, collection_status, stages, errors,
                         review, review_md, normalized, eval_payload,
                         execution="FAIL", quality=SKIPPED,
                         output_root=output_root, failed_root=failed_root,
                         overwrite_output=overwrite_output,
                         extra_partials={
                             "agent_execution.json": json.dumps(agent_execution, ensure_ascii=False, indent=2)
                         } if agent_execution else {})

    # --- Stage 3: schema validation -----------------------------------
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_errors = [
        "%s: %s" % (list(e.path), e.message)
        for e in sorted(Draft202012Validator(schema).iter_errors(review), key=lambda e: list(e.path))
    ]
    if schema_errors:
        add_stage("schema_validation", FAIL, "%d error(s)" % len(schema_errors))
        errors.append("schema validation failed")
        skip_rest("schema_validation")
        return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                         evidence_manifest_path, collection_status, stages, errors,
                         review, review_md, normalized, eval_payload,
                         execution="FAIL", quality=SKIPPED,
                         output_root=output_root, failed_root=failed_root,
                         overwrite_output=overwrite_output,
                         extra_partials={"schema_errors.json": json.dumps(schema_errors, ensure_ascii=False, indent=2)})
    add_stage("schema_validation", PASS, "schema valid")

    # --- Stage 4: contract validation ---------------------------------
    contract_errors = eval_contract.validate_review_contract(review)
    if contract_errors:
        add_stage("contract_validation", FAIL, "%d error(s)" % len(contract_errors))
        errors.append("contract validation failed")
        skip_rest("contract_validation")
        return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                         evidence_manifest_path, collection_status, stages, errors,
                         review, review_md, normalized, eval_payload,
                         execution="FAIL", quality=SKIPPED,
                         output_root=output_root, failed_root=failed_root,
                         overwrite_output=overwrite_output,
                         extra_partials={"contract_errors.json": json.dumps(contract_errors, ensure_ascii=False, indent=2)})
    add_stage("contract_validation", PASS, "contract valid")

    # --- Stage 5: evidence integrity ----------------------------------
    integrity_errors = validate_integrity(review, normalized)
    if integrity_errors:
        add_stage("evidence_integrity", FAIL, "%d error(s)" % len(integrity_errors))
        errors.append("evidence integrity failed")
        skip_rest("evidence_integrity")
        return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                         evidence_manifest_path, collection_status, stages, errors,
                         review, review_md, normalized, eval_payload,
                         execution="FAIL", quality=SKIPPED,
                         output_root=output_root, failed_root=failed_root,
                         overwrite_output=overwrite_output,
                         extra_partials={"integrity_errors.json": json.dumps(integrity_errors, ensure_ascii=False, indent=2)})
    add_stage("evidence_integrity", PASS, "review evidence matches store")

    # --- Stage 6: independent eval ------------------------------------
    eval_input = eval_normalize.normalize_review(
        review, case_id="RUN-%s-%s" % (date, run_id), failure_domain="F001+F002"
    )
    result = eval_evaluator.evaluate_case(EvalCase.from_dict(eval_input))
    eval_payload = _outcome(result)
    review_quality_status = result.status
    add_stage("independent_eval", PASS if result.status == "PASS" else FAIL,
              "F001=%s F002=%s" % (result.rule_status("F001"), result.rule_status("F002")))

    # --- Stage 7: publish ---------------------------------------------
    files = {
        "review.json": json.dumps(review, ensure_ascii=False, indent=2),
        "review.md": review_md or "",
        "eval_input.json": json.dumps(eval_input, ensure_ascii=False, indent=2),
        "eval.json": json.dumps(eval_payload, ensure_ascii=False, indent=2),
    }
    return _finalize(run_id, date, started, now(), mode, evidence_mode_used,
                     evidence_manifest_path, collection_status, stages, errors,
                     review, review_md, normalized, eval_payload,
                     execution="SUCCESS", quality=review_quality_status,
                     output_root=output_root, failed_root=failed_root,
                     overwrite_output=overwrite_output, extra_partials={},
                     ready_files=files,
                     agent_execution=agent_execution)


def _build_manifest(run_id, date, started, finished, mode, evidence_mode_used,
                    evidence_manifest_path, collection_status, stages, errors,
                    execution, quality, artifacts):
    identity = identities()
    manifest = {
        "run_id": run_id,
        "date": date,
        "started_at": started,
        "finished_at": finished,
        "mode_requested": mode,
        "evidence_mode_used": evidence_mode_used,
        "evidence_manifest_path": evidence_manifest_path,
        "evidence_collection_status": collection_status,
        "market_mcp_build": None,
        "skill_version": identity["skill_version"],
        "schema_version": identity["schema_version"],
        "eval_version": identity["eval_version"],
        "skill_sha256": identity["skill_sha256"],
        "schema_sha256": identity["schema_sha256"],
        "eval_sha256": identity["eval_sha256"],
        "stages": stages,
        "execution_status": execution,
        "review_quality_status": quality,
        "artifacts": artifacts,
        "errors": errors,
    }
    return manifest


def _finalize(run_id, date, started, finished, mode, evidence_mode_used,
              evidence_manifest_path, collection_status, stages, errors,
              review, review_md, normalized, eval_payload,
              *, execution, quality, output_root, failed_root, overwrite_output,
              extra_partials, ready_files=None, agent_execution=None):
    # attach market_mcp_build from evidence manifest if available
    build = None
    try:
        if evidence_manifest_path:
            build = json.loads(Path(evidence_manifest_path).read_text(encoding="utf-8")).get("market_mcp_build")
    except Exception:
        build = None

    if execution == "SUCCESS" and ready_files is not None:
        stages = stages + [{"name": "publish", "status": PASS,
                            "timestamp": finished, "message": "atomic publish"}]
        files = dict(ready_files)
        if agent_execution:
            files["agent_execution.json"] = json.dumps(agent_execution, ensure_ascii=False, indent=2)
        manifest = _build_manifest(run_id, date, started, finished, mode, evidence_mode_used,
                                   evidence_manifest_path, collection_status, stages, errors,
                                   execution, quality, list(files) + ["run_manifest.json"])
        manifest["market_mcp_build"] = build
        _attach_eval(manifest, eval_payload)
        files["run_manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)
        try:
            _publish(output_root, date, run_id, files, overwrite_output)
            print("PUBLISHED|%s" % (Path(output_root) / date))
        except OutputExists:
            errors = errors + ["output exists: %s" % date]
            _demote_publish(stages, finished, "output exists")
            manifest = _build_manifest(run_id, date, started, finished, mode, evidence_mode_used,
                                       evidence_manifest_path, collection_status, stages, errors,
                                       "FAIL", quality, [])
            manifest["market_mcp_build"] = build
            _attach_eval(manifest, eval_payload)
            _write_failure(failed_root, run_id, manifest, "OUTPUT_EXISTS", extra_partials)
        except Exception as exc:  # noqa: BLE001
            errors = errors + ["publish failed: %s" % type(exc).__name__]
            _demote_publish(stages, finished, type(exc).__name__)
            manifest = _build_manifest(run_id, date, started, finished, mode, evidence_mode_used,
                                       evidence_manifest_path, collection_status, stages, errors,
                                       "FAIL", quality, [])
            manifest["market_mcp_build"] = build
            _attach_eval(manifest, eval_payload)
            _write_failure(failed_root, run_id, manifest, "PUBLISH_FAILED", extra_partials)
        return manifest

    # failure path
    if not any(stage["name"] == "publish" for stage in stages):
        stages = stages + [{"name": "publish", "status": SKIPPED,
                            "timestamp": finished, "message": "not published"}]
    partials = dict(extra_partials)
    if review is not None:
        partials["review.json"] = json.dumps(review, ensure_ascii=False, indent=2)
    if review_md:
        partials["review.md"] = review_md
    manifest = _build_manifest(run_id, date, started, finished, mode, evidence_mode_used,
                               evidence_manifest_path, collection_status, stages, errors,
                               execution, quality, [])
    manifest["market_mcp_build"] = build
    _attach_eval(manifest, eval_payload)
    _write_failure(failed_root, run_id, manifest, "PIPELINE_FAILED", partials)
    return manifest


def _attach_eval(manifest, eval_payload):
    payload = eval_payload or {}
    manifest["eval_status"] = payload.get("status")
    manifest["eval_rule_status"] = payload.get("rule_status")


def _demote_publish(stages, finished, message):
    for index in range(len(stages) - 1, -1, -1):
        if stages[index]["name"] == "publish":
            stages[index] = {"name": "publish", "status": FAIL,
                             "timestamp": finished, "message": message}
            return


def _publish(output_root, date, run_id, files, overwrite):
    output_root = Path(output_root)
    target = output_root / date
    if target.exists() and not overwrite:
        raise OutputExists(str(target))
    output_root.mkdir(parents=True, exist_ok=True)
    tmp = output_root / (".tmp-%s-%s" % (date, run_id))
    tmp.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (tmp / name).write_text(content, encoding="utf-8")
    if target.exists():
        shutil.rmtree(target)
    os.rename(tmp, target)


def _write_failure(failed_root, run_id, manifest, error_code, partials):
    directory = Path(failed_root) / run_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "error.json").write_text(
        json.dumps({"error_code": error_code, "errors": manifest.get("errors", [])},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    for name, content in (partials or {}).items():
        (directory / name).write_text(content, encoding="utf-8")
    print("FAILED_RUN|%s|%s" % (error_code, directory))
