import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner.llm_agent import AgentExecutionError, ExternalLLMAgent


def _input(tmp_path):
    skill = tmp_path / "SKILL.md"
    schema = tmp_path / "schema.json"
    skill.write_text("NO EVIDENCE -> GAP", encoding="utf-8")
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    return {
        "date": "2026-09-30", "manifest": {"status": "PARTIAL"},
        "normalized": {"evidence": {"x": {"value": 1}}},
        "skill_path": str(skill), "schema_path": str(schema),
    }


def test_request_is_evidence_only_and_has_no_tool_handle(tmp_path, monkeypatch):
    seen = {}
    def fake_run(command, **kwargs):
        seen["request"] = json.loads(kwargs["input"])
        assert kwargs["shell"] is False
        return subprocess.CompletedProcess(command, 0, json.dumps({"date": "2026-09-30"}), "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ExternalLLMAgent(["fake"])(_input(tmp_path))
    req = seen["request"]
    assert req["rules"]["no_market_mcp"] is True
    assert req["rules"]["evidence_only"] is True
    assert req["normalized_evidence"]["evidence"]["x"]["value"] == 1
    assert result["review"]["date"] == "2026-09-30"
    assert result["execution"]["prompt_sha256"]


def test_invalid_json_is_explicit_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess(a[0], 0, "not-json", ""))
    with pytest.raises(AgentExecutionError) as exc:
        ExternalLLMAgent(["fake"])(_input(tmp_path))
    assert exc.value.code == "AGENT_OUTPUT_INVALID_JSON"


def test_nonzero_exit_is_explicit_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess(a[0], 7, "", "boom"))
    with pytest.raises(AgentExecutionError) as exc:
        ExternalLLMAgent(["fake"])(_input(tmp_path))
    assert exc.value.code == "AGENT_EXIT_NONZERO"


def test_timeout_is_explicit_failure(tmp_path, monkeypatch):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="fake", timeout=1)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(AgentExecutionError) as exc:
        ExternalLLMAgent(["fake"], timeout_seconds=1)(_input(tmp_path))
    assert exc.value.code == "AGENT_TIMEOUT"


def test_environment_is_whitelisted(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_THAT_MUST_NOT_LEAK", "secret")
    seen = {}
    def fake_run(command, **kwargs):
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, "{}", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    ExternalLLMAgent(["fake"])(_input(tmp_path))
    assert "SECRET_THAT_MUST_NOT_LEAK" not in seen["env"]
