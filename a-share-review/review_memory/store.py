"""Filesystem store for review -> outcome learning records."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict


class ReviewRecordExists(RuntimeError):
    pass


class ReviewRecordNotFound(RuntimeError):
    pass


class ReviewMemoryStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def record_path(self, date: str) -> Path:
        return self.root / date / "record.json"

    def exists(self, date: str) -> bool:
        return self.record_path(date).is_file()

    def load(self, date: str) -> Dict[str, Any]:
        path = self.record_path(date)
        if not path.is_file():
            raise ReviewRecordNotFound(date)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, date: str, record: Dict[str, Any], overwrite: bool = False) -> Path:
        final = self.root / date
        if final.exists() and not overwrite:
            raise ReviewRecordExists(date)
        self.root.mkdir(parents=True, exist_ok=True)
        stage = self.root / (".tmp-%s-%s" % (date, uuid.uuid4().hex[:8]))
        stage.mkdir(parents=True)
        try:
            (stage / "record.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            if final.exists():
                backup = self.root / (".bak-%s-%s" % (date, uuid.uuid4().hex[:8]))
                os.rename(final, backup)
                try:
                    os.rename(stage, final)
                except Exception:
                    os.rename(backup, final)
                    raise
                shutil.rmtree(backup, ignore_errors=True)
            else:
                os.rename(stage, final)
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        return final

    def dates(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            p.name for p in self.root.iterdir()
            if p.is_dir() and not p.name.startswith(".") and (p / "record.json").is_file()
        )

    def records_before(self, as_of_date: str) -> list[Dict[str, Any]]:
        return [self.load(d) for d in self.dates() if d < as_of_date]
