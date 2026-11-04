"""Spec 2026-11-03-m3-w12-trace §3.2 + E1: agent trace calls carry attempt/run_id/metrics/NEXT; model turns
record whether the agent followed the host's NEXT hint."""
from __future__ import annotations

import pytest

from vgar.agents.tool_agent import hint_tools

from test_agent_solve import SequenceAgent, solve, trace_of


@pytest.fixture(scope="module")
def fake_agent_trace(tmp_path_factory):
    return trace_of(solve(tmp_path_factory.mktemp("v2")))


def test_hint_tools():
    assert hint_tools("generate_patch to retry with feedback, or verify_patch to finish") == {"generate_patch",
                                                                                            "verify_patch"}
    assert hint_tools("stop") == frozenset() and hint_tools(None) == frozenset()


def test_trace_calls_have_v2_fields(fake_agent_trace):
    call = next(c for c in fake_agent_trace["calls"] if c["tool"] == "get_task_context")
    assert call["attempt"] == 0 and call["run_id"] and call["transport_status"] == "OK" and call["t"].endswith("Z")
    assert {"input_tokens", "input_cap", "failing_tests"} <= set(call["metrics"]) and call["next_hint"]
    generated = next(c for c in fake_agent_trace["calls"] if c["tool"] == "generate_patch")
    assert generated["attempt"] == 1


def test_model_calls_record_followed(fake_agent_trace):
    first = fake_agent_trace["model_calls"][0]
    assert first["next_hint"] == "get_task_context" and first["followed"] is True
    assert fake_agent_trace["model_calls"][-1]["followed"] is None  # last turn ends without a tool call


def test_refused_call_keeps_hint_and_is_logged(tmp_path):
    trace = trace_of(solve(tmp_path, model=SequenceAgent(steps=["apply_patch", "get_task_context"])))
    refused = trace["calls"][0]
    assert refused["tool"] == "apply_patch" and refused["reason"] == "HOST_REFUSED"
    assert refused["next_hint"] == "get_task_context"
    assert trace["model_calls"][0]["followed"] is False


def test_on_event_errors_never_break_the_run(tmp_path):
    seen = []

    def on_event(kind, payload):
        seen.append(kind)
        raise RuntimeError("console broke")

    result = solve(tmp_path, on_event=on_event)
    assert result["status"] == "COMPLETED" and {"start", "end", "turn"} <= set(seen)


def test_retry_generation_time_excludes_the_host_close_and_reopen(fake_agent_trace):
    # The host's verify (close) and reopen are logged as their own calls; counting them again inside
    # generate_patch would double count in the time breakdown (E4) and the M1 latency table.
    calls = fake_agent_trace["calls"]
    reopen = next(i for i, c in enumerate(calls) if c["tool"] == "get_task_context" and c["by"] == "host")
    retry = next(c for c in calls[reopen:] if c["tool"] == "generate_patch")
    assert retry["t"] >= calls[reopen]["t"]
    assert fake_agent_trace["time_breakdown"]["overlap_ms"] == 0
