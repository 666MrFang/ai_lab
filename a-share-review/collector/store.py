"""Filesystem EvidenceStore: atomic publish, overwrite guard, offline replay."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .collector import Collection, STATUS_FAILED


class OverwriteRefused(Exception):
    """Raised when a date already exists and overwrite was not requested."""


class CollectionNotPublishable(Exception):
    """Raised when a FAILED collection must not be published."""


class ReplayDataNotFound(Exception):
    code = "REPLAY_DATA_NOT_FOUND"

    def __init__(self, date: str):
        super().__init__("REPLAY_DATA_NOT_FOUND: no stored evidence for %s" % date)
        self.date = date


class EvidenceStore:
    def __init__(self, root: str):
        self.root = Path(root)

    def date_dir(self, date: str) -> Path:
        return self.root / date

    def exists(self, date: str) -> bool:
        return (self.date_dir(date) / "manifest.json").is_file()

    # ------------------------------------------------------------------
    def save(
        self,
        date: str,
        collection: Collection,
        normalized: Dict[str, Any],
        overwrite: bool = False,
    ) -> Path:
        target = self.date_dir(date)
        if self.exists(date) and not overwrite:
            raise OverwriteRefused("evidence for %s already exists (use --overwrite)" % date)
        if collection.status == STATUS_FAILED:
            raise CollectionNotPublishable(
                "REFUSE_PUBLISH: collection for %s is FAILED" % date
            )

        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / (".tmp-%s-%s" % (date, uuid.uuid4().hex))
        (tmp / "raw").mkdir(parents=True)
        (tmp / "normalized").mkdir()

        artifacts: List[str] = []
        for index, record in enumerate(collection.records, start=1):
            rel = "raw/%03d_%s.json" % (index, record.tool)
            (tmp / rel).write_text(
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            artifacts.append(rel)

        (tmp / "normalized" / "market.json").write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        artifacts.append("normalized/market.json")

        identity = collection.runtime_identity or {}
        manifest = {
            "date": collection.date,
            "collection_started_at": collection.started_at,
            "collection_finished_at": collection.finished_at,
            "market_mcp_build": identity.get("build"),
            "provider": identity.get("provider"),
            "data_mode": identity.get("data_mode"),
            "status": collection.status,
            "complete": collection.complete,
            "tools_requested": collection.tools_requested,
            "tools_success": collection.tools_success,
            "tools_failed": collection.tools_failed,
            "missing_capabilities": collection.missing_capabilities,
            "missing_optional": collection.missing_optional,
            "incomplete_evidence": collection.incomplete_evidence,
            "normalized_evidence_count": len(normalized.get("evidence", {})),
            "artifact_files": artifacts + ["manifest.json"],
        }
        (tmp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Publish atomically: the final directory only appears after every file
        # (including manifest) is fully written under a temp directory.
        if target.exists():
            shutil.rmtree(target)
        os.rename(tmp, target)
        return target

    # ------------------------------------------------------------------
    def load(self, date: str) -> Dict[str, Any]:
        """Offline replay. Reads only stored files; never touches the network."""

        target = self.date_dir(date)
        manifest_path = target / "manifest.json"
        if not manifest_path.is_file():
            raise ReplayDataNotFound(date)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw: Dict[str, Any] = {}
        raw_dir = target / "raw"
        if raw_dir.is_dir():
            for path in sorted(raw_dir.glob("*.json")):
                raw[path.name] = json.loads(path.read_text(encoding="utf-8"))
        normalized = json.loads(
            (target / "normalized" / "market.json").read_text(encoding="utf-8")
        )
        return {"date": date, "manifest": manifest, "raw": raw, "normalized": normalized}
