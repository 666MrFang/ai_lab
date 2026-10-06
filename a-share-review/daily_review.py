"""CLI: run the production daily review pipeline.

    python daily_review.py --date 2026-09-30
    python daily_review.py --date 2026-09-30 --mode replay
    python daily_review.py --date 2026-09-30 --mode live

Stages: Evidence -> Agent -> Schema -> Contract -> Integrity -> Eval -> Artifacts.
No Sector / News. No automatic Agent retry. No mock fallback.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from runner.runner import run_review  # noqa: E402
from runner.agent import ReferenceAgent  # noqa: E402
from runner.llm_agent import ExternalLLMAgent, AgentExecutionError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Production daily review runner.")
    parser.add_argument("--date", required=True, help="Trading date, YYYY-MM-DD.")
    parser.add_argument("--mode", choices=("auto", "live", "replay"), default="auto")
    parser.add_argument("--data-root", default=str(REPO_ROOT / "data" / "market"))
    parser.add_argument("--output-root", default=str(REPO_ROOT / "output"))
    parser.add_argument("--failed-root", default=str(REPO_ROOT / "failed_runs"))
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--agent", choices=("reference", "external"), default="reference",
                        help="reference=deterministic; external=REVIEW_AGENT_COMMAND JSON-array command")
    parser.add_argument("--agent-timeout", type=int, default=120)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        agent = ReferenceAgent() if args.agent == "reference" else ExternalLLMAgent(timeout_seconds=args.agent_timeout)
    except AgentExecutionError as exc:
        print("AGENT_CONFIG_ERROR=%s" % exc.code)
        return 2
    manifest = run_review(
        date=args.date,
        mode=args.mode,
        data_root=args.data_root,
        output_root=args.output_root,
        failed_root=args.failed_root,
        overwrite_output=args.overwrite_output,
        agent=agent,
    )
    print("RUN_ID=%s" % manifest.get("run_id"))
    print("EVIDENCE_MODE=%s" % manifest.get("evidence_mode_used"))
    print("EXECUTION_STATUS=%s" % manifest.get("execution_status"))
    print("REVIEW_QUALITY_STATUS=%s" % manifest.get("review_quality_status"))
    print("EVAL_RULE_STATUS=%s" % (manifest.get("eval_rule_status") or {}))
    return 0 if manifest.get("execution_status") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
