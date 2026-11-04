"""M3-W11-2: `vgar run` never reports success without verification (D9); `vgar chat --task` edits only
through the M2 engine and reports the engine verdict (D19).

Design: docs/superpowers/specs/2026-11-01-m3-w11-legacy-servers-design.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from vgar import cli

REPO = Path(__file__).resolve().parents[1]
TASK = REPO / "examples/m2/tasks/single_file_login.json"
REF = (REPO / "tests/fixtures/m2/reference_patches/single_file_login.diff").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------- vgar run (D9)
class _FakeAgent:
    async def ainvoke(self, payload, config=None):  # noqa: ARG002
        return {"messages": [*payload["messages"], AIMessage(content="done")]}


@pytest.fixture
def run_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text(
        "def test_ok():\n    assert True\n\ndef test_bad():\n    assert False\n", encoding="utf-8")
    seen: dict[str, Any] = {}

    async def fake_build_agent(settings, *, run_id=None, servers=None, extra_env=None, **kwargs):  # noqa: ARG001
        seen.update(servers=servers, extra_env=extra_env)
        return _FakeAgent()

    monkeypatch.setattr(cli, "build_agent", fake_build_agent)
    return repo, seen


def _run(repo: Path, selector: str | None) -> int:
    return asyncio.run(cli.cmd_run(argparse.Namespace(query="fix it", repo=str(repo), selector=selector, keep=False)))


def test_run_without_selector_is_unverified(run_repo, capsys):
    repo, _ = run_repo
    assert _run(repo, None) == 2
    assert "UNVERIFIED" in capsys.readouterr().out


def test_run_passes_lease_and_allowed_selector(run_repo):
    repo, seen = run_repo
    assert _run(repo, "tests/test_app.py::test_ok") == 0
    lease = Path(seen["extra_env"]["VGAR_LEASE_ROOT"])
    assert lease.resolve() != repo.resolve()
    assert json.loads(seen["extra_env"]["VGAR_ALLOWED_SELECTORS"]) == ["tests/test_app.py::test_ok"]
    assert "repair" not in seen["servers"]


def test_run_with_failing_selector_returns_1(run_repo):
    # Review Focus 5
    repo, _ = run_repo
    assert _run(repo, "tests/test_app.py::test_bad") == 1


# --------------------------------------------------------------------------------- vgar chat (D19)
class ChatScript(BaseChatModel):
    """Reads `Run directory: <path>` from the first human message, then calls the scripted tools in order."""
    steps: list[tuple[str, dict[str, Any]]]

    @property
    def _llm_type(self) -> str:
        return "test-chat-script"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ChatScript":  # noqa: ARG002
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ARG002
        first = next(m for m in messages if isinstance(m, HumanMessage))
        run_dir = re.search(r"Run directory: (\S+)", first.content).group(1)
        turn = sum(isinstance(m, ToolMessage) for m in messages)
        if turn >= len(self.steps):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="done"))])
        name, args = self.steps[turn]
        call = {"name": name, "args": {"run_dir": run_dir, **args}, "id": f"call_{turn}"}
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[call]))])


def _chat(tmp_path, steps):
    from vgar.agents.chat import run_chat
    from vgar.agents.runtime import Runtime
    runtime = Runtime(mode="fake", output_root=tmp_path / "runs")
    return asyncio.run(run_chat(TASK, runtime, ["Fix the login bug"], model=ChatScript(steps=steps)))


def test_chat_agent_patch_is_judged_by_engine(tmp_path):
    result = _chat(tmp_path, [("repair_apply_patch", {"diff": REF}), ("repair_run_relevant_tests", {}),
                              ("repair_verify_patch", {})])
    assert result["verdict"] == "PASS" and result["recommendation"] == "ACCEPT"
    assert result["verified_by"] == "agent"


def test_chat_host_verifies_when_agent_stops_early(tmp_path):
    # Review Focus 4: the printed outcome is the engine's, never the model's "done".
    result = _chat(tmp_path, [])
    assert result["verified_by"] == "host"
    record = json.loads((Path(result["run_dir"]) / "run_record.json").read_text(encoding="utf-8"))
    assert result["verdict"] == record["status"] != "PASS"


def test_chat_lease_is_the_run_worktree(tmp_path):
    result = _chat(tmp_path, [])
    task = json.loads(TASK.read_text(encoding="utf-8"))
    assert Path(result["lease_root"]).resolve() != (TASK.parent / task["source_repo"]).resolve()
    assert "tests/test_auth.py::test_login_rejects_whitespace" in result["allowed_selectors"]


def test_chat_hides_get_task_context_from_agent(tmp_path, monkeypatch):
    from vgar.agents import chat
    seen = {}
    real = chat.create_core_agent

    async def spy(settings=None, **kwargs):
        seen.update(kwargs)
        return await real(settings, **kwargs)

    monkeypatch.setattr(chat, "create_core_agent", spy)
    _chat(tmp_path, [])
    assert "repair_get_task_context" in seen["exclude_tools"]
    assert set(seen["servers"]) == {"graph", "repository", "execution", "repair"}


def test_system_prompt_routes_edits_through_repair():
    # Task 7
    text = (REPO / "src/vgar/agents/prompts/system.md").read_text(encoding="utf-8")
    assert "repair_apply_patch" in text and "repair_verify_patch" in text
    assert "Use MCP repository and graph tools before" not in text
    assert "untrusted" in text.lower()


# ------------------------------------------------------------- chat console (trace spec 2026-11-03 §6.3)
def test_chat_console_has_header_steps_and_result(tmp_path, capsys):
    _chat(tmp_path, [("repair_apply_patch", {"diff": REF}), ("repair_run_relevant_tests", {}),
                     ("repair_verify_patch", {})])
    lines = capsys.readouterr().out.strip().splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("== chat · single_file_login"))
    step = next(i for i, line in enumerate(lines) if "repair_verify_patch" in line and "agent" in line)
    result = next(i for i, line in enumerate(lines) if line.startswith("== RESULT PASS · class VERIFIED"))
    assert header < step < result
    assert any("model turn 1" in line for line in lines)
    assert any("followed NEXT n/a" in line for line in lines)
    assert lines[-1].startswith("[verdict] PASS")


def test_chat_console_shows_the_host_close(tmp_path, capsys):
    _chat(tmp_path, [])
    out = capsys.readouterr().out
    assert "verify_patch (close)" in out and "verified by host" in out
