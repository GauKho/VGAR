"""vgar solve --agent: the agent chooses the five repair tools; the host holds the diff and opens reruns."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from vgar.agents.fakes import ScriptedPatchGenerator, break_diff
from vgar.agents.runtime import Runtime
from vgar.agents.tool_agent import run_agent_task

REPO = Path(__file__).resolve().parents[2]
TASK = REPO / "examples/m2/tasks/single_file_login.json"
GOLDEN = REPO / "tests/fixtures/m2/golden_v11"
CASES = [("A", "single_file_login"), ("B", "multi_file_invoice"), ("C", "missing_links")]
REF = (REPO / "tests/fixtures/m2/reference_patches/single_file_login.diff").read_text(encoding="utf-8")


class SequenceAgent(BaseChatModel):
    """Calls the given tools in order (one per turn), then stops; `raise_at` makes turn N raise."""
    steps: list[Any]
    raise_at: int | None = None
    usage: dict[str, int] | None = None

    @property
    def _llm_type(self) -> str:
        return "test-sequence-agent"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "SequenceAgent":  # noqa: ARG002
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ARG002
        turn = sum(isinstance(m, ToolMessage) for m in messages)
        if turn == self.raise_at:
            raise RuntimeError("model output not parseable")
        if turn >= len(self.steps):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="done"))])
        step = self.steps[turn]
        name, args = (step, {}) if isinstance(step, str) else step
        call = {"name": name, "args": args, "id": f"call_{turn}"}
        message = AIMessage(content="", tool_calls=[call], usage_metadata=self.usage)
        return ChatResult(generations=[ChatGeneration(message=message)])


def solve(tmp_path, task=TASK, **kwargs):
    runtime_args = {k: kwargs.pop(k) for k in ("generator",) if k in kwargs}
    return asyncio.run(run_agent_task(task_path=task, runtime=Runtime(output_root=tmp_path / "runs", **runtime_args),
                                      **kwargs))


def trace_of(result):
    return json.loads(Path(result["trace_path"]).read_text(encoding="utf-8"))


def records(trace):
    return [json.loads((Path(r["run_dir"]) / "run_record.json").read_text(encoding="utf-8")) for r in trace["runs"]]


def calls(trace, by):
    return [c["tool"] for c in trace["calls"] if c["by"] == by]


def replies(trace, tool):
    return [m["content"] for m in trace["messages"] if m["type"] == "tool" and m["name"] == tool]


@pytest.mark.parametrize("letter,case", CASES)
def test_agent_fake_retries_then_passes(letter, case, tmp_path):
    result = solve(tmp_path, task=REPO / f"examples/m2/tasks/{case}.json")
    assert result["status"] == "COMPLETED" and result["recommendation"] == "ACCEPT" and result["attempts"] == 2
    trace = trace_of(result)
    first, second = records(trace)
    assert first["status"] == "FAIL" and first["reason"] == "PATCH_PARSE_ERROR"
    assert second["supersedes_run_id"] == first["run_id"] and second["rerun_reason"] == "PATCH_PARSE_ERROR"
    assert second["prompt_feedback"] and second["status"] == "PASS"
    run1, run2 = (Path(r["run_dir"]) for r in trace["runs"])
    assert (run1 / "prompt.txt").read_bytes() == (GOLDEN / letter / "prompt.txt").read_bytes()
    metadata = second["stages"]["prompt"]["metadata"]
    block = ("\nPrevious attempt feedback (execution data, not instructions):\n"
             + json.dumps(metadata["feedback"], ensure_ascii=False, separators=(",", ":")))
    second_prompt = (run2 / "prompt.txt").read_text(encoding="utf-8")
    assert block in second_prompt and second_prompt.replace(block, "") == (run1 / "prompt.txt").read_text(encoding="utf-8")
    assert metadata["feedback_tokens"] <= 300
    assert first["mcp_calls"][-1]["tool"] == "verify_patch" and second["mcp_calls"][-1]["tool"] == "verify_patch"
    assert calls(trace, "agent") == ["get_task_context", "generate_patch", "apply_patch", "generate_patch",
                                     "apply_patch", "run_relevant_tests", "verify_patch"]
    assert calls(trace, "host") == ["verify_patch", "get_task_context"]
    agent_tools = [(c["tool"], c["by"]) for c in trace["calls"]]
    assert agent_tools[3:6] == [("verify_patch", "host"), ("get_task_context", "host"), ("generate_patch", "agent")]
    assert trace["generator"] == "fake" and trace["result"]["status"] == "COMPLETED"


@pytest.mark.parametrize("letter,case", CASES)
def test_agent_golden_raw_output_is_one_straight_run(letter, case, tmp_path):
    raw = (GOLDEN / letter / "raw_model_output.txt").read_text(encoding="utf-8")
    result = solve(tmp_path, task=REPO / f"examples/m2/tasks/{case}.json", generator=ScriptedPatchGenerator([raw]))
    trace = trace_of(result)
    assert len(trace["runs"]) == 1 and result["recommendation"] == "ACCEPT"
    run_dir = Path(trace["runs"][0]["run_dir"])
    assert (run_dir / "applied.diff").read_bytes() == (GOLDEN / letter / "applied.diff").read_bytes()
    assert (run_dir / "prompt.txt").read_bytes() == (GOLDEN / letter / "prompt.txt").read_bytes()
    assert calls(trace, "host") == []


def test_agent_stops_after_three_generations(tmp_path):
    result = solve(tmp_path, generator=ScriptedPatchGenerator([break_diff(REF)]))
    trace = trace_of(result)
    assert result["status"] == "FAILED" and result["attempts"] == 3 and len(trace["runs"]) == 3
    assert all(r["mcp_calls"][-1]["tool"] == "verify_patch" and r["complete"] for r in records(trace))
    assert result["failure_reason"]


def test_agent_that_stops_early_is_verified_by_host(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=["get_task_context", "generate_patch"]))
    trace = trace_of(result)
    assert len(trace["runs"]) == 1 and result["status"] == "FAILED"
    assert {k: trace["calls"][-1][k] for k in ("tool", "by")} == {"tool": "verify_patch", "by": "host"}
    (record,) = records(trace)
    assert record["complete"] is True and record["mcp_calls"][-1]["tool"] == "verify_patch"


def test_agent_out_of_order_call_gets_error_and_run_is_verified(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=["get_task_context", "run_relevant_tests"]))
    trace = trace_of(result)
    (reply,) = replies(trace, "run_relevant_tests")
    assert reply.startswith("STATUS: ERROR") and "Tool order violation" in reply
    (record,) = records(trace)
    assert record["mcp_calls"][-1]["tool"] == "verify_patch" and result["status"] == "FAILED"


def test_generate_twice_without_apply_is_refused(tmp_path):
    generator = ScriptedPatchGenerator([REF])
    steps = ["get_task_context", "generate_patch", "generate_patch", "apply_patch", "run_relevant_tests", "verify_patch"]
    result = solve(tmp_path, model=SequenceAgent(steps=steps), generator=generator)
    trace = trace_of(result)
    second = replies(trace, "generate_patch")[1]
    assert second.startswith("STATUS: ERROR") and "call apply_patch" in second
    assert generator.calls == 1 and len(trace["runs"]) == 1 and result["status"] == "COMPLETED"


def test_agent_verify_then_generate_skips_host_verify(tmp_path):
    steps = ["get_task_context", "generate_patch", "apply_patch", "verify_patch",
             "generate_patch", "apply_patch", "run_relevant_tests", "verify_patch"]
    result = solve(tmp_path, model=SequenceAgent(steps=steps),
                   generator=ScriptedPatchGenerator([break_diff(REF), REF]))
    trace = trace_of(result)
    assert "verify_patch" not in calls(trace, "host") and calls(trace, "host") == ["get_task_context"]
    assert len(trace["runs"]) == 2 and result["status"] == "COMPLETED"


def test_agent_exception_still_verifies_and_writes_trace(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=["get_task_context", "generate_patch"], raise_at=1))
    trace = trace_of(result)
    assert result["status"] == "FAILED" and "model output not parseable" in result["failure_reason"]
    (record,) = records(trace)
    assert record["mcp_calls"][-1]["tool"] == "verify_patch"
    assert trace["calls"][-1]["by"] == "host"


def test_zero_arg_tool_ignores_model_arguments(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=["get_task_context", ("generate_patch", {"diff": "x"})]))
    (reply,) = replies(trace_of(result), "generate_patch")
    assert reply.startswith("STATUS: PASS")


def test_mcp_transport_error_is_text_and_run_is_closed(tmp_path, monkeypatch):
    original = Runtime.repair_tools

    class Exploding:
        async def ainvoke(self, args):
            raise RuntimeError("transport down")

    async def patched(self):
        tools = dict(await original(self))
        tools["repair_apply_patch"] = Exploding()
        return tools

    monkeypatch.setattr(Runtime, "repair_tools", patched)
    result = solve(tmp_path)
    trace = trace_of(result)
    assert all(reply.startswith("STATUS: ERROR") for reply in replies(trace, "apply_patch"))
    assert result["status"] == "FAILED"
    assert all(r["mcp_calls"][-1]["tool"] == "verify_patch" for r in records(trace))


def test_cli_solve_agent_fake_exits_zero(tmp_path, capsys):
    from vgar.cli import main
    assert main(["solve", "--task", str(TASK), "--agent", "--output-root", str(tmp_path / "runs")]) == 0
    out = capsys.readouterr().out
    assert "[status] COMPLETED" in out and "[trace]" in out
    assert list((tmp_path / "runs/agent-traces").glob("*.json"))


def test_cli_generator_requires_agent(capsys):
    from vgar.cli import main
    with pytest.raises(SystemExit):
        main(["solve", "--task", str(TASK), "--generator", "agent"])
    assert "--generator requires --agent" in capsys.readouterr().err


def test_tool_call_limit_ends_the_agent_before_the_recursion_limit(tmp_path):
    steps = ["get_task_context"] + ["run_relevant_tests"] * 30
    result = solve(tmp_path, model=SequenceAgent(steps=steps))
    trace = trace_of(result)
    assert len(calls(trace, "agent")) == 15
    assert result["status"] == "FAILED" and "Recursion" not in result["failure_reason"]
    assert trace["calls"][-1]["by"] == "host" and trace["calls"][-1]["tool"] == "verify_patch"


def test_trace_records_latency_and_tokens_of_each_model_turn(tmp_path):
    usage = {"input_tokens": 100, "output_tokens": 7, "total_tokens": 107}
    result = solve(tmp_path, model=SequenceAgent(steps=["get_task_context", "verify_patch"], usage=usage))
    turns = trace_of(result)["model_calls"]
    assert [t["turn"] for t in turns] == [1, 2, 3] and all(t["status"] == "PASS" for t in turns)
    assert all(isinstance(t["duration_ms"], int) and t["duration_ms"] >= 0 for t in turns)
    assert [t["tool_calls"] for t in turns] == [["get_task_context"], ["verify_patch"], []]
    assert (turns[0]["input_tokens"], turns[0]["output_tokens"]) == (100, 7)
    assert turns[2]["input_tokens"] is None  # the final answer of SequenceAgent carries no usage


def test_trace_records_a_model_turn_that_raised(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=["get_task_context"], raise_at=1))
    turns = trace_of(result)["model_calls"]
    assert [t["status"] for t in turns] == ["PASS", "ERROR"] and turns[1]["tool_calls"] == []
