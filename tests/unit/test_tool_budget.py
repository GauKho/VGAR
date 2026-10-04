"""agent.max_tool_calls is enforced by the agent itself, not just reported."""
from __future__ import annotations

import asyncio
import itertools
from dataclasses import replace

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from vgar.agents.core import build_core_agent
from vgar.config.settings import Settings


class LoopingModel(GenericFakeChatModel):
    """Asks for the `ping` tool forever, so only a cap can stop it."""

    def bind_tools(self, tools, **kwargs):
        return self


def _ping_forever():
    for i in itertools.count():
        yield AIMessage(content="", tool_calls=[{"name": "ping", "args": {"x": str(i)}, "id": f"call-{i}"}])


def _agent(limit: int):
    executed: list[str] = []

    @tool
    def ping(x: str) -> str:
        """Record one real execution."""
        executed.append(x)
        return "pong"

    base = Settings()
    settings = replace(base, agent=replace(base.agent, max_tool_calls=limit))
    return build_core_agent(LoopingModel(messages=_ping_forever()), [ping], settings), executed


def _invoke(agent, messages):
    return asyncio.run(agent.ainvoke({"messages": messages}, config={"recursion_limit": 50}))


def test_tool_calls_stop_at_the_cap():
    agent, executed = _agent(limit=3)
    result = _invoke(agent, [HumanMessage("go")])
    assert len(executed) == 3  # the 4th requested call was blocked, never executed
    assert "limit" in str(result["messages"][-1].content).lower()


def test_cap_is_per_run_so_each_retry_gets_a_fresh_budget():
    agent, executed = _agent(limit=2)
    first = _invoke(agent, [HumanMessage("go")])
    _invoke(agent, [*first["messages"], HumanMessage("try again")])
    assert len(executed) == 4
