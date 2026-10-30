"""Fake mode for `vgar solve --agent`: a broken first diff, a scripted generator and a scripted agent.

They prove the host plumbing and the regenerate-with-feedback branch, not a real model's choices.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def break_diff(diff: str) -> str:
    """Drop the '-' of the first removed line (the spike's failure): the hunk counts stop matching."""
    lines = diff.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("-") and not line.startswith("---"):
            lines[index] = line[1:]
            break
    return "".join(lines)


class ScriptedPatchGenerator:
    """Returns the given diffs in order, then keeps returning the last one."""
    mode = "fake"

    def __init__(self, diffs: list[str]):
        self.diffs = list(diffs)
        self.calls = 0

    def generate(self, prompt, profile, timeout_seconds):
        raw = self.diffs[min(self.calls, len(self.diffs) - 1)]
        self.calls += 1
        return dict(status="PASS", mode="fake", raw_text=raw, finish_reason="fixture", truncated=False,
                    input_tokens=prompt.input_tokens, output_tokens=None, token_measurement="unit-test-only",
                    duration_ms=0)


def _field(text: str, name: str) -> str | None:
    match = re.search(rf"^{name}: (.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


class ScriptedRepairAgent(BaseChatModel):
    """Chooses the next tool from the last tool reply, like the agent prompt describes."""

    @property
    def _llm_type(self) -> str:
        return "vgar-scripted-repair-agent"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedRepairAgent":  # noqa: ARG002
        return self

    def next_tool(self, name: str, text: str) -> str | None:
        status = _field(text, "STATUS")
        if name == "verify_patch":
            return None
        if name == "analyze_patch_impact":
            return "generate_patch"
        if status == "PASS":
            return {"get_task_context": "generate_patch", "generate_patch": "apply_patch",
                    "apply_patch": "run_relevant_tests", "run_relevant_tests": "verify_patch"}[name]
        if name in ("apply_patch", "run_relevant_tests") and int(_field(text, "ATTEMPTS LEFT") or 0) > 0:
            return "analyze_patch_impact" if name == "run_relevant_tests" else "generate_patch"
        return "verify_patch"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ARG002
        last = next((m for m in reversed(messages) if isinstance(m, ToolMessage)), None)
        tool = "get_task_context" if last is None else self.next_tool(last.name, str(last.content))
        if tool is None:
            message = AIMessage(content=str(last.content))
        else:
            message = AIMessage(content="", tool_calls=[{"name": tool, "args": {}, "id": f"call_{uuid.uuid4().hex[:8]}"}])
        return ChatResult(generations=[ChatGeneration(message=message)])
