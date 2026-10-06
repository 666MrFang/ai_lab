"""One-command A-share daily review product.

Example:
    python review_product.py --date 2026-10-06 --mode live
"""

from __future__ import annotations

import argparse
from pathlib import Path

from product.pipeline import run_product_day

ROOT = Path(__file__).resolve().parent


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="A-share production review + memory + outlook")
    p.add_argument("--date", required=True)
    p.add_argument("--mode", choices=("auto", "live", "replay"), default="auto")
    p.add_argument("--overwrite-output", action="store_true")
    p.add_argument("--min-pattern-sample", type=int, default=8)
    args = p.parse_args(argv)

    result = run_product_day(
        date=args.date, mode=args.mode, overwrite_output=args.overwrite_output,
        min_pattern_sample=args.min_pattern_sample,
    )
    print("EXECUTION_STATUS=%s" % result.get("execution_status"))
    product = result.get("product") or {}
    if product:
        print("MEMORY_STATUS=%s" % product.get("memory_status"))
        print("CALIBRATED_PATTERNS=%s" % product.get("calibrated_pattern_count"))
        print("DASHBOARD=%s" % (ROOT / "output" / args.date / "dashboard.html"))
    return 0 if result.get("execution_status") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
