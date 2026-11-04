"""Fixes from the official M3-X2b run of 03/11 (results/m3/w12/agent/20261103T151652Z), see docs/status/m3.md."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

TRUNCATED = {"status": "ERROR", "reason": "VERIFICATION_INCOMPLETE",
             "stages": {"generation": {"status": "PASS", "truncated": True, "output_tokens": 1536}}}
TIMED_OUT = {"status": "ERROR", "reason": "VERIFICATION_INCOMPLETE",
             "stages": {"baseline": {"status": "ERROR", "reason": "BASELINE_NOT_QUALIFIED",
                                     "static": {"mypy": {"timed_out": True, "exit_code": -9,
                                                         "timeout_seconds": 60}}}}}


# ---- 1. VERIFICATION_INCOMPLETE split into a model cause and an infrastructure cause ---------------------------

def test_truncated_output_is_a_model_failure():
    from vgar.evaluation.failure_class import classify, refine_code
    code, evidence = refine_code("VERIFICATION_INCOMPLETE", TRUNCATED)
    assert code == "OUTPUT_TRUNCATED" and evidence == "generation: output cut at 1536 tokens"
    assert classify("ERROR", code) == "MODEL"


def test_a_killed_tool_is_an_infra_failure():
    from vgar.evaluation.failure_class import classify, refine_code
    code, evidence = refine_code("VERIFICATION_INCOMPLETE", TIMED_OUT)
    assert code == "TOOL_TIMEOUT" and evidence == "baseline.static.mypy timed out after 60 s"
    assert classify("ERROR", code) == "INFRA"


def test_other_codes_and_records_without_cause_are_unchanged():
    from vgar.evaluation.failure_class import refine_code
    assert refine_code("TEST_FAILED", TIMED_OUT) == ("TEST_FAILED", None)
    assert refine_code("VERIFICATION_INCOMPLETE", {"stages": {}}) == ("VERIFICATION_INCOMPLETE", None)
    assert refine_code("VERIFICATION_INCOMPLETE", None) == ("VERIFICATION_INCOMPLETE", None)


def _call(tool, status, run_id, reason=None, by="agent", **metrics):
    return {"tool": tool, "by": by, "status": status, "reason": reason, "run_id": run_id, "attempt": 1,
            "duration_ms": 1000, "metrics": metrics}


def test_trace_class_reads_the_cause_from_the_run_record():
    from vgar.agents.trace_report import failure_class
    calls = [_call("get_task_context", "ERROR", "r2", "VERIFICATION_INCOMPLETE", by="host")]
    assert failure_class(calls, {"r2": TIMED_OUT}, {"status": "FAILED"}) == {
        "class": "INFRA", "code": "TOOL_TIMEOUT", "evidence": "baseline.static.mypy timed out after 60 s"}
    calls = [_call("apply_patch", "ERROR", "r1", "VERIFICATION_INCOMPLETE")]
    assert failure_class(calls, {"r1": TRUNCATED}, {"status": "FAILED"})["class"] == "MODEL"


# ---- 2. the experiment id reaches the header ----------------------------------------------------------------------

def test_header_takes_the_experiment_id_from_the_runtime():
    from vgar.agents.trace_report import trace_header
    host = SimpleNamespace(run_args={}, task=SimpleNamespace(task_id="t"), generator=SimpleNamespace(mode="fake"),
                           profile=SimpleNamespace(model_id="m", revision="r"),
                           policy=SimpleNamespace(input_cap=1, output_cap=2, generation_timeout=3))
    runtime = SimpleNamespace(mode="fake", experiment_id="d11f8b7c6792f780")
    assert trace_header(host, runtime, None)["experiment_id"] == "d11f8b7c6792f780"


# ---- 3, 4, 8. result block: per-task audit, one attempt count, invalid calls counted like table M1 ----------------

def _trace(**extra):
    return {"result": {"status": "FAILED", "attempts": 1}, "failure_class": {"class": "INFRA", "code": "TOOL_TIMEOUT"},
            "attempts": [{"run_id": "r1", "generated": "✓", "applied": "✗", "tests": "–", "static": "–", "verdict": "REJECT"},
                         {"run_id": "r2", "generated": "✗", "generation_reason": "TOOL_TIMEOUT", "applied": "–", "tests": "–",
                              "static": "–", "verdict": "REJECT"}],
            "calls": [_call("analyze_patch_impact", "ERROR", "r1", "INVALID_ARGUMENT"),
                      _call("apply_patch", "FAIL", "r1", "NO_OP")],
            "model_calls": [], **extra}


def test_result_block_counts_runs_and_attempts_without_contradiction():
    from vgar.agents.trace_report import render_result
    lines = render_result(_trace())
    assert lines[0] == "== RESULT FAILED · class INFRA (TOOL_TIMEOUT) · 1/3 attempts · 2 runs"
    assert lines[1].startswith("   run 1/2: generated ✓") and lines[2].startswith("   run 2/2: generated ✗ TOOL_TIMEOUT")


def test_result_block_shows_the_evidence_of_the_class():
    from vgar.agents.trace_report import render_result
    trace = _trace(failure_class={"class": "INFRA", "code": "TOOL_TIMEOUT", "evidence": "baseline.static.mypy timed out after 60 s"})
    assert "   cause baseline.static.mypy timed out after 60 s" in render_result(trace)


def test_result_block_counts_invalid_calls_like_table_m1_and_shows_audit():
    from vgar.agents.trace_report import render_result
    assert render_result(_trace())[-1] == "   agent: 2 calls · invalid 1 · followed NEXT n/a · audit —"
    line = render_result(_trace(), audit={"expected": 2, "matched": 2, "missing": []})[-1]
    assert line.endswith("· audit 2/2")


def test_cli_reads_the_audit_log_for_the_result_block(tmp_path, monkeypatch):
    from vgar.cli import _task_audit
    stamp = "20261103T153523274990Z"
    trace_path = tmp_path / f"{stamp}-t.json"
    trace_path.write_text(json.dumps({"duration_ms": 10_000, "calls": [_call("apply_patch", "FAIL", "r1", "NO_OP")]}),
                          encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    audit.write_text(json.dumps({"timestamp": "2026-11-03T15:35:20+00:00", "event_type": "tool_call",
                                 "payload": {"server": "repair", "tool": "apply_patch"}}) + "\n", encoding="utf-8")
    monkeypatch.setenv("VGAR_MCP_AUDIT_LOG", str(audit))
    assert _task_audit(trace_path) == {"expected": 1, "matched": 1, "missing": []}
    monkeypatch.setenv("VGAR_MCP_AUDIT_LOG", str(tmp_path / "absent.jsonl"))
    assert _task_audit(trace_path) is None


# ---- 5. generation_timeout is enforced by the agent generator ---------------------------------------------------

def test_agent_generator_enforces_the_generation_timeout(monkeypatch):
    pytest.importorskip("torch")
    from test_agent_model_generator import POLICY, PROFILE, PROMPT, fake_model

    from vgar.agents import agent_generator
    model, hf = fake_model()
    result = agent_generator.AgentModelGenerator(model, PROFILE, POLICY).generate(PROMPT, PROFILE, 900)
    assert hf.calls[0]["max_time"] == 900 and result["status"] == "PASS"
    clock = iter([0.0, 901.0])
    monkeypatch.setattr(agent_generator.time, "monotonic", lambda: next(clock))
    hf.generate = lambda inputs, generation_config=None, **kw: __import__("torch").cat(
        [inputs, __import__("torch").tensor([[7, 8]])], dim=-1)  # cut by max_time: no EOS, below the cap
    result = agent_generator.AgentModelGenerator(model, PROFILE, POLICY).generate(PROMPT, PROFILE, 900)
    assert result["status"] == "ERROR" and result["timed_out"] is True and result["raw_text"] == ""


# ---- 6. files listed once; truncation visible on the generate_patch line -----------------------------------------

def test_diff_files_are_listed_once():
    from vgar.agents.tool_agent import _diff_files
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n--- a/x.py\n+++ b/x.py\n@@ -5 +5 @@\n-c\n+d\n"
    assert _diff_files(diff) == "x.py"


def test_generate_patch_line_says_the_output_was_cut():
    from vgar.agents.trace_report import render_step
    call = _call("generate_patch", "PASS", "r1", files=["x.py"], output_truncated=True)
    call["t"] = "2026-11-03T16:47:44Z"
    assert render_step("end", call, 3).endswith("x.py · output cut at output cap")


# ---- 7. why analyze_patch_impact refused the call --------------------------------------------------------------

def test_audit_keeps_the_message_of_an_invalid_argument(tmp_path):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.tooling import run_tool

    def call():
        raise ValueError("diff touches no file of the graph")
    log = tmp_path / "audit.jsonl"
    run_tool(server="graph", tool="analyze_patch_impact", backend="sqlite", audit=AuditLogger(log), call=call)
    payload = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["payload"]
    assert payload["error_code"] == "INVALID_ARGUMENT"
    assert payload["error_message"] == "diff touches no file of the graph"
