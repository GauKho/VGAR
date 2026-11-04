"""Spec 2026-11-03-m3-w12-trace §4 E2–E4: attempt funnel, failure class and time breakdown from a trace."""
from __future__ import annotations

import json

import pytest

from vgar.agents.trace_report import attempt_funnel, failure_class, time_breakdown

from test_agent_solve import solve, trace_of

RUNS = ("R1", "R2", "R3")


def _call(tool, by, status, reason, run_id, attempt, ms, **metrics):
    return {"tool": tool, "by": by, "status": status, "reason": reason, "run_id": run_id, "attempt": attempt,
            "duration_ms": ms, "metrics": metrics, "t": "2026-11-03T12:54:16Z"}


def _seaborn_calls():
    """03/11 seaborn run: every generation hit the 900 s timeout; the host closed and reopened each attempt."""
    calls = [_call("get_task_context", "agent", "PASS", None, "R1", 0, 36_700, input_tokens=3903)]
    for n, run in enumerate(RUNS, start=1):
        calls.append(_call("generate_patch", "agent", "ERROR", "GENERATION_TIMEOUT", run, n, 950_400))
        calls.append(_call("verify_patch", "host", "ERROR", "VERIFICATION_INCOMPLETE", run, n, 700))
        if n < 3:
            calls.append(_call("get_task_context", "host", "PASS", None, RUNS[n], n, 46_700))
    return calls


CALLS_SEABORN = _seaborn_calls()
RECORDS_SEABORN = {run: {"status": "ERROR", "reason": "VERIFICATION_INCOMPLETE",
                         "stages": {"workspace": {"duration_ms": 2_000}, "baseline": {"duration_ms": 30_000},
                                    "generation": {"duration_ms": 950_000}, "verification": {"duration_ms": 500}}}
                   for run in RUNS}
MODEL_CALLS = [{"turn": i, "duration_ms": 8_000} for i in range(1, 10)]


def test_seaborn_like_run_is_model_generation_timeout():
    assert failure_class(CALLS_SEABORN, RECORDS_SEABORN, {"status": "FAILED"}) == {"class": "MODEL",
                                                                                   "code": "GENERATION_TIMEOUT"}


def test_funnel_marks_failed_generation():
    rows = attempt_funnel(CALLS_SEABORN, RECORDS_SEABORN)
    assert [r["run_id"] for r in rows] == list(RUNS)
    assert rows[0]["generated"] == "✗" and rows[0]["generation_reason"] == "GENERATION_TIMEOUT"
    assert rows[0]["applied"] == "–" and rows[0]["tests"] == "–" and rows[0]["verdict"] == "REJECT"


def test_funnel_of_an_applied_passing_attempt():
    calls = [_call("get_task_context", "agent", "PASS", None, "R1", 0, 10),
             _call("generate_patch", "agent", "PASS", None, "R1", 1, 10, files=["a.py"]),
             _call("apply_patch", "agent", "PASS", None, "R1", 1, 10, files=["a.py"]),
             _call("run_relevant_tests", "agent", "PASS", None, "R1", 1, 10, passed=2, failed=0),
             _call("verify_patch", "agent", "PASS", None, "R1", 1, 10, recommendation="ACCEPT")]
    record = {"status": "PASS", "reason": None, "stages": {"verification": {"policy_checks": {
        "tests": {"status": "PASS"}, "ruff": {"status": "PASS"}, "mypy": {"status": "PASS"}}}}}
    row = attempt_funnel(calls, {"R1": record})[0]
    assert (row["generated"], row["applied"], row["tests"], row["static"], row["verdict"]) == ("✓", "✓", "2/2", "✓",
                                                                                              "ACCEPT")
    assert failure_class(calls, {"R1": record}, {"status": "COMPLETED"})["class"] == "VERIFIED"


def test_over_cap_is_protocol():
    calls = [_call("get_task_context", "agent", "ERROR", "INTERNAL_ERROR", "R1", 0, 221_567)]
    records = {"R1": {"status": "ERROR", "reason": "INTERNAL_ERROR",
                      "error_detail": {"message": "Tokenizer worker failed: Full prompt exceeds model input budget"}}}
    assert failure_class(calls, records, {"status": "FAILED"}) == {"class": "PROTOCOL", "code": "INTERNAL_ERROR"}


def test_docker_failure_is_infra():
    records = {"R1": {"status": "ERROR", "reason": "INTERNAL_ERROR",
                      "error_detail": {"message": "Docker operation incomplete: ['info', '--format'] "}}}
    calls = [_call("get_task_context", "agent", "ERROR", "INTERNAL_ERROR", "R1", 0, 122_967)]
    assert failure_class(calls, records, {"status": "FAILED"})["class"] == "INFRA"


def test_no_run_opened_uses_the_result_reason():
    assert failure_class([], {}, {"status": "FAILED", "failure_reason": "Agent made no tool call"})["class"] == \
        "UNCLASSIFIED"


def test_time_breakdown_sums_to_total():
    t = time_breakdown(3_240_000, CALLS_SEABORN, MODEL_CALLS, RECORDS_SEABORN)
    assert t["generation_ms"] == 3 * 950_400 and t["agent_turns_ms"] == 72_000 and t["docker_ms"] == 3 * 32_500
    assert t["generation_ms"] + t["agent_turns_ms"] + t["docker_ms"] + t["other_ms"] - t["overlap_ms"] == 3_240_000


def test_time_breakdown_overlap_is_reported_not_negative():
    t = time_breakdown(1_000, CALLS_SEABORN, MODEL_CALLS, RECORDS_SEABORN)
    assert t["other_ms"] == 0 and t["overlap_ms"] > 0


class TimeoutGenerator:
    mode = "fake"

    def generate(self, prompt, profile, timeout_seconds):  # noqa: ARG002
        return {"status": "ERROR", "timed_out": True, "reason": "worker exceeded 900 s", "raw_text": "",
                "truncated": False}


@pytest.fixture(scope="module")
def timeout_trace(tmp_path_factory):
    return trace_of(solve(tmp_path_factory.mktemp("timeout"), generator=TimeoutGenerator()))


def test_generation_timeout_is_a_code_in_the_trace(timeout_trace):
    call = next(c for c in timeout_trace["calls"] if c["tool"] == "generate_patch")
    assert call["reason"] == "GENERATION_TIMEOUT" and call["metrics"]["detail"] == "worker exceeded 900 s"
    assert timeout_trace["failure_class"] == {"class": "MODEL", "code": "GENERATION_TIMEOUT"}


def test_written_trace_has_v2_keys_and_keeps_v1_keys(timeout_trace):
    assert timeout_trace["schema"] == "vgar-agent-trace-v2"
    assert {"calls", "model_calls", "runs", "messages", "result", "duration_ms", "header", "attempts",
            "failure_class", "time_breakdown"} <= set(timeout_trace)
    header = timeout_trace["header"]
    assert header["task_id"] == "single_file_login" and header["input_cap"] > 0 and "machine" in header
    assert "\"inventory\":" not in json.dumps(header)  # hashes only, never the file inventory
