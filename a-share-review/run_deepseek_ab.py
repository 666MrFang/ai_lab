"""One-command ReferenceAgent vs DeepSeek replay experiment."""

import argparse
import json
import os
import sys
from pathlib import Path

from experiments.ab import run_ab
from runner.llm_agent import ExternalLLMAgent

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--model", choices=("deepseek-chat", "deepseek-reasoner"),
                   default="deepseek-chat")
    p.add_argument("--data-root", default=str(ROOT / "data" / "market"))
    p.add_argument("--work-root", default=None)
    p.add_argument("--timeout", type=int, default=180)
    args = p.parse_args(argv)

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY is not configured; set it in your shell, never in Git.")
        return 2

    env = {"DEEPSEEK_MODEL": args.model}
    agent = ExternalLLMAgent(
        [sys.executable, str(ROOT / "deepseek_agent.py")],
        timeout_seconds=args.timeout,
        env=env,
    )
    work = args.work_root or str(
        ROOT / "experiments" / "runs" / ("%s-%s" % (args.date, args.model))
    )
    result = run_ab(
        date=args.date, data_root=args.data_root, work_root=work,
        candidate_agent=agent,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["candidate"]["execution_status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
