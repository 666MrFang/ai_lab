"""Stable version identity for Skill / Schema / Eval (content SHA256)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO / "skills" / "a-share-daily-review" / "SKILL.md"
SCHEMA_PATH = REPO / "schemas" / "review_schema.json"
EVAL_FILES: List[Path] = [
    REPO / "eval" / "evaluator.py",
    REPO / "eval" / "models.py",
    REPO / "eval" / "policies.py",
    REPO / "eval" / "contract.py",
    REPO / "eval" / "normalize.py",
]

SKILL_VERSION = "0.1.0"
SCHEMA_VERSION = "0.1.0"
EVAL_VERSION = "0.1.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_many(paths: List[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def identities() -> Dict[str, str]:
    return {
        "skill_version": SKILL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "eval_version": EVAL_VERSION,
        "skill_sha256": sha256_file(SKILL_PATH),
        "schema_sha256": sha256_file(SCHEMA_PATH),
        "eval_sha256": sha256_many(EVAL_FILES),
    }
