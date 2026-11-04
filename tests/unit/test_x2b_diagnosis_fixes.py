"""Fixes from the X2b diagnosis of 04/11 (docs/status/m3_x2b_diagnosis_2026-11-04.md, "Lỗi code" 1–4)."""
from __future__ import annotations

from pathlib import Path

from test_agent_impact_tool import FAIL_THEN_IMPACT, WRONG_LOGIN
from test_agent_solve import REF, SequenceAgent, solve, trace_of

from vgar.agents import tool_agent
from vgar.agents.fakes import ScriptedPatchGenerator

# ---- 1. analyze_patch_impact gets the diff the engine applied, not the raw model text -----------------------------

def test_impact_receives_the_engine_applied_diff(tmp_path, monkeypatch):
    sent = []

    class Tool:
        async def ainvoke(self, args):
            sent.append(args["diff"])
            return '{"status": "ERROR", "reason": "INVALID_ARGUMENT"}'

    async def fake_graph(*args):
        return Tool(), "sha256:x"
    monkeypatch.setattr(tool_agent, "impact_graph_tool", fake_graph)
    trace = trace_of(solve(tmp_path, model=SequenceAgent(steps=FAIL_THEN_IMPACT),
                           generator=ScriptedPatchGenerator([WRONG_LOGIN, REF])))
    applied = (Path(trace["runs"][0]["run_dir"]) / "applied.diff").read_text(encoding="utf-8")
    assert sent == [applied] and applied != WRONG_LOGIN


# ---- 2. the retry feedback carries the parse stage error of a normalized run -----------------------------------

def test_feedback_reads_the_parse_stage_error():
    from vgar.agents.feedback import build_feedback
    record = {"task_id": "t", "run_id": "r1", "status": "FAIL", "reason": "NO_OP",
              "stages": {"parse_patch": {"status": "FAIL", "error": {
                  "code": "NO_OP", "message": "Every hunk is a no-op or leaves its file unchanged"}}}}
    assert build_feedback(record)["message"] == "Every hunk is a no-op or leaves its file unchanged"


# ---- 3. a static tool that cannot run on the testbed is not a static failure -----------------------------------

def _record(**checks):
    return {"stages": {"verification": {"policy_checks": {"tests": {"status": "FAIL"}, **checks}}}}


def test_unavailable_static_tool_is_not_a_failure():
    from vgar.agents.trace_report import _static
    django = _record(syntax={"status": "PASS"}, mypy={"status": "UNAVAILABLE"}, ruff={"status": "PASS"})
    assert _static(django) == "✓ (mypy n/a)"
    assert _static(_record(syntax={"status": "PASS"}, ruff={"status": "FAIL"})) == "✗"
    assert _static(_record(syntax={"status": "PASS"}, ruff={"status": "PASS"})) == "✓"


# ---- 4. the optional analyze_patch_impact after failed tests counts as following NEXT -------------------------

def test_optional_impact_call_counts_as_followed(tmp_path):
    trace = trace_of(solve(tmp_path, model=SequenceAgent(steps=FAIL_THEN_IMPACT),
                           generator=ScriptedPatchGenerator([WRONG_LOGIN, REF])))
    turn = next(m for m in trace["model_calls"] if m["tool_calls"] == ["analyze_patch_impact"])
    assert turn["followed"] is True


def test_impact_call_when_not_allowed_is_not_followed(tmp_path):
    steps = ["get_task_context", "analyze_patch_impact", "generate_patch", "apply_patch", "run_relevant_tests",
             "verify_patch"]
    trace = trace_of(solve(tmp_path, model=SequenceAgent(steps=steps), generator=ScriptedPatchGenerator([REF])))
    turn = next(m for m in trace["model_calls"] if m["tool_calls"] == ["analyze_patch_impact"])
    assert turn["followed"] is False
