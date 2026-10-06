"""Run ReferenceAgent vs configured external model on identical replay evidence."""

import argparse
import json
import os
from pathlib import Path

from experiments.ab import run_ab
from runner.llm_agent import AgentExecutionError, ExternalLLMAgent

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--data-root", default=str(ROOT / "data" / "market"))
    p.add_argument("--work-root", default=None)
    p.add_argument("--agent-timeout", type=int, default=120)
    args = p.parse_args(argv)
    work = args.work_root or str(ROOT / "experiments" / "runs" / args.date)
    try:
        agent = ExternalLLMAgent(timeout_seconds=args.agent_timeout)
    except AgentExecutionError as exc:
        print("AGENT_CONFIG_ERROR=%s" % exc.code)
        print('Set REVIEW_AGENT_COMMAND to a JSON argv array, e.g. ["python","adapter.py"].')
        return 2
    result = run_ab(
        date=args.date, data_root=args.data_root, work_root=work,
        candidate_agent=agent,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["candidate"]["execution_status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
