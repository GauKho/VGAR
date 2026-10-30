"""M3-W10-3: the agent's analyze_patch_impact tool reaches the graph MCP server over stdio."""
from __future__ import annotations

import asyncio

from vgar.agents.runtime import impact_graph_tool
from vgar.config.settings import get_settings
from vgar.mcp.result_parser import parse_mcp_json_result

from test_agent_solve import REPO, WRONG


def test_impact_graph_tool_answers_over_stdio(tmp_path):
    repo = REPO / "examples/m2/snapshots/single_file_login"
    tool, version = asyncio.run(impact_graph_tool(get_settings(), repo, tmp_path / "g.db"))
    wrong = (WRONG / "single_file_login.diff").read_text(encoding="utf-8")
    result = parse_mcp_json_result(asyncio.run(tool.ainvoke({"diff": wrong, "graph_version": version})))
    assert result["status"] == "PASS" and version.startswith("sha256:")
    assert [n["path"] for n in result["data"]["changed"]] == ["auth.py"]
    assert result["data"]["impacted"]["status"] in ("COMPLETE", "PARTIAL")


from vgar.agents import tool_agent
from vgar.agents.fakes import ScriptedPatchGenerator, break_diff
from vgar.agents.runtime import Runtime
from vgar.agents.tool_agent import AgentRepairHost, NoArgs

from test_agent_solve import REF, TASK, SequenceAgent, records, replies, solve, trace_of

WRONG_LOGIN = (WRONG / "single_file_login.diff").read_text(encoding="utf-8")
IMPACT_LINE = "Static graph impact of the previous patch"
FAIL_THEN_IMPACT = ["get_task_context", "generate_patch", "apply_patch", "run_relevant_tests",
                    "analyze_patch_impact", "generate_patch", "apply_patch", "run_relevant_tests", "verify_patch"]


def impact_calls(trace):
    return [(c["by"], c["status"], c["reason"]) for c in trace["calls"] if c["tool"] == "analyze_patch_impact"]


def count_graph_builds(monkeypatch):
    builds = []
    real = tool_agent.impact_graph_tool

    async def counting(*args):
        builds.append(args)
        return await real(*args)
    monkeypatch.setattr(tool_agent, "impact_graph_tool", counting)
    return builds


def test_impact_reply_and_feedback(tmp_path):
    result = solve(tmp_path, model=SequenceAgent(steps=FAIL_THEN_IMPACT),
                   generator=ScriptedPatchGenerator([WRONG_LOGIN, REF]))
    trace = trace_of(result)
    assert impact_calls(trace) == [("agent", "PASS", None)]
    assert replies(trace, "analyze_patch_impact")[0].startswith(f"STATUS: PASS\nIMPACT: {IMPACT_LINE}")
    assert IMPACT_LINE in records(trace)[1]["prompt_feedback"]["message"]
    assert result["status"] == "COMPLETED"


def test_impact_refused_before_task(tmp_path, monkeypatch):
    builds = count_graph_builds(monkeypatch)
    result = solve(tmp_path, model=SequenceAgent(steps=["analyze_patch_impact"]))
    trace = trace_of(result)
    assert impact_calls(trace) == [("agent", "ERROR", "HOST_REFUSED")] and builds == []
    assert "No task yet" in replies(trace, "analyze_patch_impact")[0]


def test_impact_refused_before_failure(tmp_path, monkeypatch):
    builds = count_graph_builds(monkeypatch)
    steps = ["get_task_context", "generate_patch", "apply_patch", "analyze_patch_impact", "run_relevant_tests",
             "verify_patch"]
    result = solve(tmp_path, model=SequenceAgent(steps=steps), generator=ScriptedPatchGenerator([REF]))
    trace = trace_of(result)
    assert "Impact needs an applied patch" in replies(trace, "analyze_patch_impact")[0] and builds == []
    assert result["status"] == "COMPLETED"


def test_impact_refused_after_parse_error(tmp_path, monkeypatch):
    builds = count_graph_builds(monkeypatch)
    steps = ["get_task_context", "generate_patch", "apply_patch", "analyze_patch_impact", "generate_patch",
             "apply_patch", "run_relevant_tests", "verify_patch"]
    result = solve(tmp_path, model=SequenceAgent(steps=steps), generator=ScriptedPatchGenerator([break_diff(REF), REF]))
    trace = trace_of(result)
    assert impact_calls(trace) == [("agent", "ERROR", "HOST_REFUSED")] and builds == []
    assert IMPACT_LINE not in records(trace)[1]["prompt_feedback"]["message"]


def test_impact_refused_twice_in_one_run(tmp_path, monkeypatch):
    builds = count_graph_builds(monkeypatch)
    steps = FAIL_THEN_IMPACT[:5] + ["analyze_patch_impact"] + FAIL_THEN_IMPACT[5:]
    result = solve(tmp_path, model=SequenceAgent(steps=steps), generator=ScriptedPatchGenerator([WRONG_LOGIN, REF]))
    trace = trace_of(result)
    assert impact_calls(trace) == [("agent", "PASS", None), ("agent", "ERROR", "HOST_REFUSED")] and len(builds) == 1
    assert "already analyzed" in replies(trace, "analyze_patch_impact")[1]


def test_impact_is_not_carried_to_a_later_retry(tmp_path):
    steps = FAIL_THEN_IMPACT[:8] + ["generate_patch", "apply_patch", "run_relevant_tests", "verify_patch"]
    result = solve(tmp_path, model=SequenceAgent(steps=steps),
                   generator=ScriptedPatchGenerator([WRONG_LOGIN, WRONG_LOGIN, REF]))
    first, second, third = records(trace_of(result))
    assert IMPACT_LINE in second["prompt_feedback"]["message"]
    assert IMPACT_LINE not in third["prompt_feedback"]["message"]
    assert result["status"] == "COMPLETED"


def test_impact_error_keeps_retry_going(tmp_path, monkeypatch):
    async def broken(*args):
        raise RuntimeError("graph server did not start")
    monkeypatch.setattr(tool_agent, "impact_graph_tool", broken)
    result = solve(tmp_path, model=SequenceAgent(steps=FAIL_THEN_IMPACT),
                   generator=ScriptedPatchGenerator([WRONG_LOGIN, REF]))
    trace = trace_of(result)
    reply = replies(trace, "analyze_patch_impact")[0]
    assert reply.startswith("STATUS: ERROR\nREASON: TOOL_ERROR") and "graph server did not start" in reply
    assert len(trace["runs"]) == 2 and IMPACT_LINE not in records(trace)[1]["prompt_feedback"]["message"]
    assert result["status"] == "COMPLETED"


def test_agent_has_six_tools(tmp_path):
    host = AgentRepairHost(Runtime(), TASK, tmp_path, ScriptedPatchGenerator([REF]))
    tools = host.langchain_tools()
    assert [t.name for t in tools] == ["get_task_context", "generate_patch", "apply_patch", "run_relevant_tests",
                                       "verify_patch", "analyze_patch_impact"]
    assert all(t.args_schema is NoArgs for t in tools)


import pytest

from test_agent_solve import CASES, calls


@pytest.mark.parametrize("letter,case", CASES)
def test_scripted_agent_calls_impact_after_test_failure(letter, case, tmp_path):
    wrong = (WRONG / f"{case}.diff").read_text(encoding="utf-8")
    ref = (REPO / f"tests/fixtures/m2/reference_patches/{case}.diff").read_text(encoding="utf-8")
    result = solve(tmp_path, task=REPO / f"examples/m2/tasks/{case}.json",
                   generator=ScriptedPatchGenerator([wrong, ref]))
    trace = trace_of(result)
    assert calls(trace, "agent") == ["get_task_context", "generate_patch", "apply_patch", "run_relevant_tests",
                                     "analyze_patch_impact", "generate_patch", "apply_patch",
                                     "run_relevant_tests", "verify_patch"]
    assert IMPACT_LINE in records(trace)[1]["prompt_feedback"]["message"]
    assert result["status"] == "COMPLETED" and result["recommendation"] == "ACCEPT"


def test_summarize_reads_a_fake_trace(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_real", REPO / "scripts/check_agent_impact_real.py")
    check_real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_real)
    result = solve(tmp_path, generator=ScriptedPatchGenerator([WRONG_LOGIN, REF]))
    row = check_real.summarize(trace_of(result))
    assert row["task"] == "single_file_login" and row["recommendation"] == "ACCEPT"
    assert row["impact_called"] is True and row["impact_status"] == "PASS" and row["feedback_has_impact"] is True
    assert row["tool_calls"] == 9 and check_real.gate([row]) is True
    assert check_real.gate([{**row, "impact_called": False}]) is False


def test_impact_graph_tool_reuses_an_indexed_database(tmp_path):
    repo, db = REPO / "examples/m2/snapshots/single_file_login", tmp_path / "g.db"
    _, first = asyncio.run(impact_graph_tool(get_settings(), repo, db))
    _, second = asyncio.run(impact_graph_tool(get_settings(), repo, db))  # a retry after a failed first call
    assert first == second


def test_impact_refused_when_no_attempts_are_left(tmp_path, monkeypatch):
    builds = count_graph_builds(monkeypatch)
    attempt = ["generate_patch", "apply_patch", "run_relevant_tests"]
    steps = ["get_task_context"] + attempt * 3 + ["analyze_patch_impact", "verify_patch"]
    result = solve(tmp_path, model=SequenceAgent(steps=steps), generator=ScriptedPatchGenerator([WRONG_LOGIN]))
    trace = trace_of(result)
    assert impact_calls(trace) == [("agent", "ERROR", "HOST_REFUSED")] and builds == []
    assert "No attempts left" in replies(trace, "analyze_patch_impact")[0]


def test_impact_without_computed_dependents_still_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_agent, "impact_message", lambda data: None)  # e.g. a NOT_COMPUTED report
    result = solve(tmp_path, model=SequenceAgent(steps=FAIL_THEN_IMPACT),
                   generator=ScriptedPatchGenerator([WRONG_LOGIN, REF]))
    reply = replies(trace_of(result), "analyze_patch_impact")[0]
    assert reply.startswith("STATUS: PASS\nIMPACT: No dependent code was computed for this patch.")
