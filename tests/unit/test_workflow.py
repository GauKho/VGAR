"""Outer workflow with a scripted fake agent (no model, no MCP servers)."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from vgar.agents.runtime import Runtime
from vgar.agents.workflow import run_task
from vgar.config.settings import AgentSettings, Settings
from dataclasses import replace

BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "calc.py").write_text(BUGGY)
    (root / "tests" / "test_calc.py").write_text(TEST)
    (root / "conftest.py").write_text("import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))\n")
    return root


class ScriptedAgent:
    """Attempt i runs actions[i-1](workspace); records every prompt it receives."""

    def __init__(self, actions):
        self.actions = actions
        self.prompts: list[str] = []

    async def ainvoke(self, payload, config=None):
        messages = payload["messages"]
        self.prompts.append(messages[-1].content)
        text = messages[0].content
        workspace = Path(re.search(r"\): (.+)", text).group(1).strip())
        self.actions[len(self.prompts) - 1](workspace)
        return {"messages": [*messages, AIMessage(content="done")]}


def solve(**kwargs):
    return asyncio.run(run_task(**kwargs))


def runtime_for(agent: ScriptedAgent, max_iterations: int = 3) -> Runtime:
    base = Settings()
    settings = replace(base, agent=replace(base.agent, max_iterations=max_iterations))

    async def factory(_settings):
        return agent

    return Runtime(settings=settings, agent_factory=factory, test_timeout=60)


def nothing(_ws: Path) -> None:
    pass


def fix(ws: Path) -> None:
    (ws / "src" / "calc.py").write_text(FIXED)


def test_retry_then_pass_and_source_untouched(repo: Path):
    agent = ScriptedAgent([nothing, fix])
    result = solve(repo=repo, issue_text="add() is wrong", selectors=["tests/test_calc.py::test_add"],
                            runtime=runtime_for(agent))
    assert result["status"] == "COMPLETED"
    assert result["attempts"] == 2
    assert result["evidence"]["passed"] is True
    assert "No file in the workspace was changed" in agent.prompts[1]  # feedback reached the agent
    assert (repo / "src" / "calc.py").read_text() == BUGGY  # source repo untouched


def test_gives_up_after_max_iterations(repo: Path):
    agent = ScriptedAgent([nothing, nothing])
    result = solve(repo=repo, issue_text="x", selectors=["tests/test_calc.py::test_add"],
                            runtime=runtime_for(agent, max_iterations=2))
    assert result["status"] == "FAILED"
    assert result["attempts"] == 2
    assert result["last_failure_class"] in {"TEST_FAILED", "NO_PATCH"}


def test_agent_error_is_not_retried(repo: Path):
    class Boom:
        async def ainvoke(self, *_a, **_k):
            raise RuntimeError("model unavailable")

    async def factory(_s):
        return Boom()

    rt = Runtime(settings=Settings(), agent_factory=factory)
    result = solve(repo=repo, issue_text="x", selectors=["tests/test_calc.py::test_add"], runtime=rt)
    assert result["status"] == "FAILED"
    assert result["attempts"] == 1
    assert "model unavailable" in result["failure_reason"]


def test_requires_selectors(repo: Path):
    with pytest.raises(ValueError, match="failing_tests"):
        solve(repo=repo, issue_text="x", selectors=[], runtime=runtime_for(ScriptedAgent([nothing])))
