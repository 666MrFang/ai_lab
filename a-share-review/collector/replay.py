"""Replay: load previously saved evidence. Never touches the network."""

from __future__ import annotations

from typing import Any, Dict

from .normalize import normalize_records
from .collector import RawRecord, _signature
from .store import EvidenceStore


def replay_market(store: EvidenceStore, date: str) -> Dict[str, Any]:
    """Return stored evidence for ``date`` or raise ``ReplayDataNotFound``.

    There is deliberately NO fallback to LIVE collection: a missing replay is
    an explicit error, never a silent re-fetch from the upstream API.
    """

    data = store.load(date)
    quarantined = set((data.get("manifest") or {}).get("temporal_quarantine") or [])
    if not quarantined:
        return data

    # Compatibility safety for snapshots written before normalized_for()
    # filtered quarantined optional records. Rebuild the reasoning view from
    # immutable raw evidence rather than trusting a potentially stale
    # normalized/market.json.
    records = []
    for raw in (data.get("raw") or {}).values():
        record = RawRecord(
            tool=raw.get("tool"),
            arguments=dict(raw.get("arguments") or {}),
            requested_at=raw.get("requested_at") or "",
            success=bool(raw.get("success")),
            category=raw.get("category") or "optional",
            kind=raw.get("kind") or "optional",
            provider=raw.get("provider") or "",
            runtime_identity=dict(raw.get("runtime_identity") or {}),
            result=dict(raw.get("result") or {}),
            error_code=raw.get("error_code"),
            lineage=list(raw.get("lineage") or []),
        )
        if _signature(record.tool, record.arguments) not in quarantined:
            records.append(record)
    data["normalized"] = normalize_records(records, date)
    return data
