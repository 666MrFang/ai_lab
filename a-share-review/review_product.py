"""One-command A-share daily review product.

Example:
    python review_product.py --date 2026-10-06 --mode live
"""

from __future__ import annotations

import argparse
from pathlib import Path

from product.pipeline import run_product_day
from runner.agent import ReferenceAgent
from runner.llm_agent import ExternalLLMAgent, AgentExecutionError

ROOT = Path(__file__).resolve().parent


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="A-share production review + memory + outlook")
    p.add_argument("--date", required=True)
    p.add_argument("--mode", choices=("auto", "live", "replay"), default="auto")
    p.add_argument("--overwrite-output", action="store_true")
    p.add_argument("--min-pattern-sample", type=int, default=8)
    p.add_argument("--agent", choices=("reference", "deepseek"), default="deepseek")
    p.add_argument("--model", choices=("deepseek-flash", "deepseek-v4-pro"),
                   default="deepseek-flash")
    p.add_argument("--agent-timeout", type=int, default=120)
    args = p.parse_args(argv)

    try:
        if args.agent == "reference":
            agent = ReferenceAgent()
        else:
            import os
            if not os.environ.get("DEEPSEEK_API_KEY"):
                print("AGENT_CONFIG_ERROR=DEEPSEEK_API_KEY_MISSING")
                return 2
            command = [
                os.environ.get("PYTHON", "python"),
                str(ROOT / "deepseek_agent.py"),
                "--model", args.model,
            ]
            agent = ExternalLLMAgent(command=command, timeout_seconds=args.agent_timeout)
    except AgentExecutionError as exc:
        print("AGENT_CONFIG_ERROR=%s" % exc.code)
        return 2

    result = run_product_day(
        date=args.date, mode=args.mode, overwrite_output=args.overwrite_output,
        agent=agent,
        min_pattern_sample=args.min_pattern_sample,
    )
    print("EXECUTION_STATUS=%s" % result.get("execution_status"))
    product = result.get("product") or {}
    if product:
        print("MEMORY_STATUS=%s" % product.get("memory_status"))
        print("CALIBRATED_PATTERNS=%s" % product.get("calibrated_pattern_count"))
        verification = product.get("d1_verification") or {}
        print("D1_VERIFICATION=PASS:%s FAIL:%s NOT_OBSERVABLE:%s" % (
            verification.get("pass", 0), verification.get("fail", 0),
            verification.get("not_observable", 0)))
        print("DASHBOARD=%s" % (ROOT / "output" / args.date / "dashboard.html"))
    return 0 if result.get("execution_status") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
