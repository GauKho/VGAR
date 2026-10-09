from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from vgar.agents.runtime import Runtime
from vgar.agents.state import VGARState
from vgar.observability.instrumentation import instrument_node


def _first_prompt(state: VGARState) -> str:
    lines = [
        state["issue_text"],
        "",
        "Repository working copy (use this exact value as `repo_path` in "
        f"repository_* and execution_* tools): {state['workspace_path']}",
        "Test selectors: " + ", ".join(state["failing_tests"]),
        "Never claim success without execution_run_pytest evidence.",
    ]
    return "\n".join(lines)


def _retry_prompt(state: VGARState) -> str:
    evidence = state.get("evidence") or {}
    tests = evidence.get("tests") or {}
    lines = [
        f"Independent verification of attempt {state['attempts']} FAILED "
        f"({state.get('last_failure_class')}).",
    ]
    if not evidence.get("patch_applied"):
        lines.append("No file in the workspace was changed. Apply a fix with repository_apply_patch.")
    if tests.get("failed_cases"):
        lines.append("Failing tests: " + ", ".join(tests["failed_cases"]))
    if tests.get("output_tail"):
        lines += ["Pytest output (tail):", tests["output_tail"]]
    lines.append("Fix the remaining problem. The workspace keeps your earlier edits.")
    return "\n".join(lines)


def _count_tool_calls(messages: list) -> int:
    return sum(len(m.tool_calls or []) for m in messages if isinstance(m, AIMessage))


@instrument_node("repair")
async def repair(state: VGARState, runtime: Runtime) -> dict:
    """The only LLM node: one agent run (possibly several tool calls)."""
    attempt = state.get("attempts", 0) + 1
    history = list(state.get("agent_messages") or [])
    prompt = _retry_prompt(state) if history else _first_prompt(state)

    try:
        agent = await runtime.make_agent()
        result = await agent.ainvoke(
            {"messages": [*history, HumanMessage(content=prompt)]},
            config={"recursion_limit": runtime.sandboxed.agent.recursion_limit},
        )
    except Exception as exc:  # model/MCP/recursion errors end the run, they are not retried
        return {
            "attempts": attempt,
            "last_failure_class": "AGENT_ERROR",
            "failure_reason": f"Agent error on attempt {attempt}: {type(exc).__name__}: {exc}",
        }

    messages = result["messages"]
    new_calls = _count_tool_calls(messages[len(history) + 1:])
    return {
        "attempts": attempt,
        "agent_messages": messages,
        "tool_call_count": state.get("tool_call_count", 0) + new_calls,
        "failure_reason": None,
    }
