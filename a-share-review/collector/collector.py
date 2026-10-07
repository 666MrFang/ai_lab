"""Evidence collector: tool collection only (no Agent, no Eval, no review.md).

Collection != Analysis. This module only gathers Tool Evidence and classifies
collection completeness against the Production Capability Set.
"""

from __future__ import annotations
import time

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import capabilities as caps
from .normalize import extract_lineage, normalize_records

STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"


@dataclass
class RawRecord:
    tool: str
    arguments: Dict[str, Any]
    requested_at: str
    success: bool
    category: str  # required | optional | unimplemented
    kind: str      # current | baseline | optional | unimplemented
    provider: str
    runtime_identity: Dict[str, Any]
    result: Dict[str, Any]
    error_code: Optional[str] = None
    lineage: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "requested_at": self.requested_at,
            "success": self.success,
            "category": self.category,
            "kind": self.kind,
            "provider": self.provider,
            "error_code": self.error_code,
            "runtime_identity": self.runtime_identity,
            "lineage": self.lineage,
            "result": self.result,
        }


@dataclass
class Collection:
    date: str
    started_at: str
    finished_at: str
    runtime_identity: Dict[str, Any]
    status: str
    complete: bool
    records: List[RawRecord]
    tools_requested: List[str]
    tools_success: List[str]
    tools_failed: List[str]
    missing_capabilities: List[str]
    incomplete_evidence: List[str]
    missing_optional: List[str]
    temporal_quarantine: List[str] = field(default_factory=list)


def _signature(tool: str, arguments: Dict[str, Any]) -> str:
    return "%s(%s)" % (tool, ", ".join("%s=%s" % (k, arguments[k]) for k in sorted(arguments)))


def _is_incomplete_baseline(record: RawRecord) -> bool:
    if record.tool != "get_market_metric_baseline" or not record.success:
        return False
    baseline = (record.result or {}).get("baseline") or {}
    return baseline.get("complete") is not True


def collect(caller: Any, date: str, clock: Optional[Callable[[], str]] = None) -> Collection:
    now = clock or (lambda: dt.datetime.now().isoformat(timespec="seconds"))
    runtime_identity = dict(getattr(caller, "runtime_identity", {}) or {})
    provider = runtime_identity.get("provider", "akshare")
    started = now()

    plan = (
        [(t, a, "required", k) for t, a, k in caps.required_requests(date)]
        + [(t, a, "optional", k) for t, a, k in caps.optional_requests(date)]
        + [(t, a, "unimplemented", k) for t, a, k in caps.unimplemented_requests(date)]
    )

    records: List[RawRecord] = []

    def call_and_record(tool, arguments, category, kind):
        requested_at = now()
        result = caller.call(tool, arguments)
        # Live public-data endpoints occasionally fail transiently. Retry only
        # transport/network failures, never semantic/data errors, and only for
        # REQUIRED evidence so optional enrichment cannot amplify traffic.
        if category == "required" and result.get("error_code") == "NETWORK_ERROR":
            for retry_no in range(1, 3):
                print("COLLECT_RETRY|%s|%d/2|NETWORK_ERROR" % (tool, retry_no), flush=True)
                time.sleep(0.5 * retry_no)
                result = caller.call(tool, arguments)
                if result.get("success") or result.get("error_code") != "NETWORK_ERROR":
                    break
        success = bool(result.get("success"))
        error_code = result.get("error_code")
        record = RawRecord(
            tool=tool, arguments=arguments, requested_at=requested_at,
            success=success, category=category, kind=kind, provider=provider,
            runtime_identity=runtime_identity, result=result, error_code=error_code,
            lineage=extract_lineage(result),
        )
        records.append(record)
        # Production CLI progress must distinguish a slow upstream from a dead
        # process and expose the exact failing capability without leaking data.
        print(
            "COLLECT|%s|%s|%s%s" % (
                tool,
                "PASS" if success else "FAIL",
                category.upper(),
                "" if success else "|%s" % (error_code or "UNKNOWN_ERROR"),
            ),
            flush=True,
        )
        return record

    for tool, arguments, category, kind in plan:
        call_and_record(tool, arguments, category, kind)

    # Product V1.1: enrich the strongest three industries with current
    # membership when (and only when) a VERIFIED THS->Sina mapping exists.
    # These calls are OPTIONAL: missing mappings are explicit evidence gaps,
    # never a reason to fail the day's market collection.
    ranking_record = next(
        (r for r in records if r.tool == "get_sector_ranking" and r.success), None
    )
    if ranking_record is not None:
        for sector in ((ranking_record.result or {}).get("sectors") or [])[:3]:
            name = sector.get("sector_name")
            if name:
                # THS history is the same evidence family as THS ranking and
                # gives the pattern engine real 5d/20d persistence context.
                call_and_record(
                    "get_sector_history_summary",
                    {"date": date, "sector_name": name},
                    "optional",
                    "sector_history",
                )
                membership_record = call_and_record(
                    "get_sector_membership",
                    {"sector_name": name},
                    "optional",
                    "sector_membership",
                )
                if membership_record.success:
                    members = list((membership_record.result or {}).get("stocks") or [])
                    members.sort(
                        key=lambda item: item.get("change_pct")
                        if item.get("change_pct") is not None else float("-inf"),
                        reverse=True,
                    )
                    selected = []
                    for rank, member in enumerate(members, start=1):
                        market_cap = member.get("market_cap_cny")
                        circulating_cap = member.get("circulating_market_cap_cny")
                        if rank <= 3 or (
                            market_cap is not None and float(market_cap) >= 50_000_000_000
                        ) or (
                            circulating_cap is not None
                            and float(circulating_cap) >= 50_000_000_000
                        ):
                            code = member.get("stock_code")
                            if code and code not in selected:
                                selected.append(code)
                        if len(selected) >= 5:
                            break
                    # Bound enrichment to the actionable candidate set.
                    # Querying every constituent caused hundreds of serial calls
                    # and many INVALID_STOCK_CODE errors from stale/delisted
                    # current-membership rows. The candidate set already
                    # contains today's top movers plus capacity candidates.
                    for code in selected:
                        call_and_record(
                            "get_stock_history_summary",
                            {"date": date, "stock_code": code},
                            "optional",
                            "stock_history",
                        )
                    for code in selected:
                        call_and_record(
                            "get_stock_news",
                            {"date": date, "stock_code": code, "limit": 10},
                            "optional",
                            "stock_news",
                        )
                        call_and_record(
                            "get_stock_disclosures",
                            {"date": date, "stock_code": code, "limit": 10},
                            "optional",
                            "stock_disclosures",
                        )

    # --- classify ---------------------------------------------------------
    required = [r for r in records if r.category == "required"]
    # Sector ranking is CURRENT_ONLY upstream. For an explicitly historical
    # live backfill, HISTORICAL_RANKING_UNAVAILABLE is an expected evidence gap,
    # not a failure of the independently historical market/index evidence.
    # Any other sector-ranking failure (including network/schema errors) remains
    # a hard required failure.
    historical_ranking_gaps = [
        r for r in required
        if r.tool == "get_sector_ranking"
        and not r.success
        and r.error_code == "HISTORICAL_RANKING_UNAVAILABLE"
    ]
    required_failed = [
        r for r in required
        if not r.success and r not in historical_ranking_gaps
    ]
    incomplete = [
        caps.baseline_key(
            (r.result.get("baseline") or {}).get("metric"),
            date,
            (r.result.get("baseline") or {}).get("window"),
        )
        for r in required
        if _is_incomplete_baseline(r)
    ]

    unimplemented = [r.tool for r in records if r.category == "unimplemented"]
    missing_optional = [r.tool for r in records if r.category == "optional" and not r.success]
    missing_optional.extend("get_sector_ranking:HISTORICAL_RANKING_UNAVAILABLE"
                            for _ in historical_ranking_gaps)
    missing_capabilities = sorted(set(unimplemented))

    # CURRENT_ONLY evidence is only temporally valid when its observed session
    # is the requested review date. A historical path/name must never retrofit
    # today's constituents into the past.
    temporal_quarantine = []
    for r in records:
        if not r.success:
            continue
        result = r.result or {}
        temporal_semantics = result.get("temporal_semantics")
        observed_date = result.get("observed_session_date") or result.get("date")
        if temporal_semantics == "CURRENT_ONLY" and observed_date != date:
            temporal_quarantine.append(_signature(r.tool, r.arguments))

    if required_failed:
        status, complete = STATUS_FAILED, False
    elif incomplete:
        status, complete = STATUS_PARTIAL, False
    else:
        status, complete = STATUS_SUCCESS, True

    return Collection(
        date=date,
        started_at=started,
        finished_at=now(),
        runtime_identity=runtime_identity,
        status=status,
        complete=complete,
        records=records,
        tools_requested=[_signature(r.tool, r.arguments) for r in records],
        tools_success=[_signature(r.tool, r.arguments) for r in records if r.success],
        tools_failed=[_signature(r.tool, r.arguments) for r in records
                      if not r.success and r.category != "unimplemented"],
        missing_capabilities=missing_capabilities,
        incomplete_evidence=sorted(set(incomplete)),
        missing_optional=sorted(set(missing_optional)),
        temporal_quarantine=sorted(set(temporal_quarantine)),
    )


def normalized_for(collection: Collection) -> Dict[str, Any]:
    return normalize_records(collection.records, collection.date)
