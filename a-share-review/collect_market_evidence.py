"""CLI: collect market evidence for a date and persist it (production workflow).

    python collect_market_evidence.py --date 2026-09-30
    python collect_market_evidence.py --date 2026-09-30 --overwrite
    python collect_market_evidence.py --date 2026-09-30 --replay

Collection only. Does not run the Agent, Eval, or produce review.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from collector.collector import collect, normalized_for  # noqa: E402
from collector.mcp_client import McpStdioToolCaller  # noqa: E402
from collector.store import EvidenceStore  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect market evidence (production).")
    parser.add_argument("--date", required=True, help="Trading date, YYYY-MM-DD.")
    parser.add_argument(
        "--data-root",
        default=str(REPO_ROOT / "data" / "market"),
        help="Evidence store root (default: <repo>/data/market).",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow re-collection.")
    parser.add_argument("--replay", action="store_true", help="Load stored evidence offline.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    store = EvidenceStore(args.data_root)

    if args.replay:
        data = store.load(args.date)
        print(json.dumps(data["manifest"], ensure_ascii=False, indent=2))
        return 0

    with McpStdioToolCaller() as caller:
        collection = collect(caller, args.date)
        normalized = normalized_for(collection)
        print("RUNTIME_IDENTITY=%s" % json.dumps(caller.runtime_identity, ensure_ascii=False))

    target = store.save(args.date, collection, normalized, overwrite=args.overwrite)
    print("STATUS=%s COMPLETE=%s" % (collection.status, collection.complete))
    print("MISSING_CAPABILITIES=%s" % collection.missing_capabilities)
    print("INCOMPLETE_EVIDENCE=%s" % collection.incomplete_evidence)
    print("SAVED=%s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
