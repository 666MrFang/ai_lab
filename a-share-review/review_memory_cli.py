"""CLI for review-memory ingestion, outcome settlement and historical outlook."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_memory.service import build_outlook, build_review_record, settle_record
from review_memory.store import ReviewMemoryStore

ROOT = Path(__file__).resolve().parent


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="A-share review memory")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--date", required=True)
    ingest.add_argument("--overwrite", action="store_true")

    settle = sub.add_parser("settle")
    settle.add_argument("--date", required=True)

    outlook = sub.add_parser("outlook")
    outlook.add_argument("--date", required=True)
    outlook.add_argument("--min-sample", type=int, default=8)

    args = parser.parse_args()
    memory = ReviewMemoryStore(ROOT / "data" / "review_history")

    if args.command == "ingest":
        review = _load(ROOT / "output" / args.date / "review.json")
        normalized = _load(
            ROOT / "data" / "market" / args.date / "normalized" / "market.json"
        )
        manifest_path = ROOT / "output" / args.date / "run_manifest.json"
        manifest = _load(manifest_path) if manifest_path.exists() else {}
        record = build_review_record(args.date, review, normalized, manifest)
        print(memory.save(args.date, record, overwrite=args.overwrite))
        return

    if args.command == "settle":
        record = memory.load(args.date)
        later = [
            d for d in memory.dates()
            if d > args.date
            and (ROOT / "data" / "market" / d / "normalized" / "market.json").exists()
        ][:5]
        evidence = [
            _load(ROOT / "data" / "market" / d / "normalized" / "market.json")
            for d in later
        ]
        settled = settle_record(record, evidence)
        memory.save(args.date, settled, overwrite=True)
        print(json.dumps(settled["settlement"], ensure_ascii=False, indent=2))
        return

    current = memory.load(args.date)
    result = build_outlook(
        args.date, current, memory.records_before(args.date), args.min_sample
    )
    target = ROOT / "output" / args.date / "outlook.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
