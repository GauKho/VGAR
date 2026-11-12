"""Spec 2026-11-03-m3-w12-trace §3.3/§5: [VGAR_TRACE] lines only in debug mode, with the run id; library noise filtered."""
import json

from vgar.observability.instrumentation import emit, instrument_mcp_tool

RUN = "20261103T125416597686Z-ef3e99a9eb7c"


def _rows(err):
    return [json.loads(line.split(" ", 1)[1]) for line in err.splitlines() if line.startswith("[VGAR_TRACE]")]


def test_emit_is_silent_by_default(monkeypatch, capsys):
    monkeypatch.delenv("VGAR_TRACE", raising=False)
    emit("X", a=1)
    assert "[VGAR_TRACE]" not in capsys.readouterr().err


def test_emit_prints_in_debug(monkeypatch, capsys):
    monkeypatch.setenv("VGAR_TRACE", "debug")
    emit("X", a=1)
    assert [r["event"] for r in _rows(capsys.readouterr().err)] == ["X"]


def test_mcp_tool_events_carry_run_id_from_run_dir(monkeypatch, capsys):
    monkeypatch.setenv("VGAR_TRACE", "debug")

    @instrument_mcp_tool("verify_patch")
    def tool(run_dir):
        return {"status": "PASS"}

    tool(run_dir=f"/x/results/{RUN}")
    rows = _rows(capsys.readouterr().err)
    assert len(rows) == 3 and {r["run_id"] for r in rows} == {RUN}


def test_mcp_output_run_id_from_result(monkeypatch, capsys):
    # get_task_context has no run_dir argument; the run id is in its result.
    monkeypatch.setenv("VGAR_TRACE", "debug")
    monkeypatch.delenv("VGAR_TRACE_RUN_ID", raising=False)

    @instrument_mcp_tool("get_task_context")
    def tool(task_path):
        return {"status": "PASS", "run_id": "R1"}

    tool(task_path="t.json")
    rows = {r["event"]: r["run_id"] for r in _rows(capsys.readouterr().err)}
    assert rows["MCP_TOOL_OUTPUT"] == "R1" and rows["MCP_TOOL_END"] == "R1"


def test_mcp_wrapper_never_breaks_a_tool_whose_data_is_not_a_dict(monkeypatch):
    # Final review: observability must never change a tool's result (spec §2), whatever shape the result has.
    for mode in ("debug", ""):
        monkeypatch.setenv("VGAR_TRACE", mode)

        @instrument_mcp_tool("list_tool")
        def tool():
            return {"status": "PASS", "data": ["a", "b"]}

        assert tool() == {"status": "PASS", "data": ["a", "b"]}
