"""Controlled external LLM adapter.

The model process receives one JSON request on stdin and must emit one JSON
object on stdout. It has no Market MCP handle: all market facts come from the
stored Evidence payload embedded in the request.

Command configuration is a JSON array in REVIEW_AGENT_COMMAND, e.g.
["python","my_agent.py"]. No shell expansion is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class AgentExecutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ExternalLLMAgent:
    name = "external-llm-agent-v1"

    def __init__(self, command=None, timeout_seconds: int = 120, env: Optional[Dict[str, str]] = None):
        if command is None:
            raw = os.environ.get("REVIEW_AGENT_COMMAND", "")
            try:
                command = json.loads(raw) if raw else None
            except json.JSONDecodeError as exc:
                raise AgentExecutionError("AGENT_CONFIG_INVALID", "REVIEW_AGENT_COMMAND must be a JSON array") from exc
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise AgentExecutionError("AGENT_CONFIG_MISSING", "external agent command is not configured")
        self.command = list(command)
        self.timeout_seconds = int(timeout_seconds)
        self.extra_env = dict(env or {})
        self.last_execution: Dict[str, Any] = {}

    @staticmethod
    def _request(agent_input: Dict[str, Any]) -> Dict[str, Any]:
        skill = Path(agent_input["skill_path"]).read_text(encoding="utf-8")
        schema = json.loads(Path(agent_input["schema_path"]).read_text(encoding="utf-8"))
        return {
            "protocol": "a-share-review-agent/v1",
            "task": "Generate one daily A-share review. Return JSON only.",
            "date": agent_input["date"],
            "rules": {
                "evidence_only": True,
                "no_market_mcp": True,
                "no_mock_fallback": True,
                "no_retry": True,
                "news_is_not_causality": True,
                "forward_output_is_verification_conditions_not_prediction": True,
            },
            "skill": skill,
            "schema": schema,
            "evidence_manifest": agent_input.get("manifest") or {},
            "normalized_evidence": agent_input.get("normalized") or {},
        }

    def __call__(self, agent_input: Dict[str, Any]) -> Dict[str, Any]:
        request = self._request(agent_input)
        payload = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        prompt_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "HOME": os.environ.get("HOME", ""),
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
            **self.extra_env,
        }
        try:
            completed = subprocess.run(
                self.command,
                input=payload,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                env={k: v for k, v in env.items() if v},
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            self.last_execution = {"prompt_sha256": prompt_hash, "error_code": "AGENT_TIMEOUT"}
            raise AgentExecutionError("AGENT_TIMEOUT", "external agent timed out") from exc
        except OSError as exc:
            self.last_execution = {"prompt_sha256": prompt_hash, "error_code": "AGENT_START_FAILED"}
            raise AgentExecutionError("AGENT_START_FAILED", type(exc).__name__) from exc

        self.last_execution = {
            "prompt_sha256": prompt_hash,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            raise AgentExecutionError("AGENT_EXIT_NONZERO", "external agent returned non-zero")
        if not completed.stdout.strip():
            raise AgentExecutionError("AGENT_OUTPUT_MISSING", "external agent produced no stdout")
        try:
            obj = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise AgentExecutionError("AGENT_OUTPUT_INVALID_JSON", "stdout is not valid JSON") from exc

        review = obj.get("review") if isinstance(obj, dict) and "review" in obj else obj
        if not isinstance(review, dict):
            raise AgentExecutionError("AGENT_OUTPUT_INVALID_JSON", "review must be a JSON object")
        return {
            "review": review,
            "review_md": obj.get("review_md", "") if isinstance(obj, dict) else "",
            "raw": completed.stdout,
            "execution": dict(self.last_execution),
        }
