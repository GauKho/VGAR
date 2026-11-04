"""Spec 2026-11-03-m3-w12-trace §3.1: the solve --agent console (header, one line per step and model turn,
result block); the old [status]/[run]/[trace] lines stay last."""
from __future__ import annotations

from vgar.agents.trace_report import render_header, render_result, render_step, render_turn

from test_agent_solve import TASK
from test_trace_report import CALLS_SEABORN, MODEL_CALLS, RECORDS_SEABORN

T = "2026-11-03T12:54:52Z"
HEADER = {"task_id": "mwaskom__seaborn-3069", "variant": "A2", "arm": "graph", "experiment_id": "d12a97b9097bcac7",
          "model": "Qwen/Qwen3-4B-Instruct-2507@cdbee75f", "generator": "worker", "input_cap": 6000,
          "output_cap": 1536, "generation_timeout": 900.0, "admission_hash": "sha256:68964899d21c9ac2",
          "inventory_hash": "sha256:97af0c2d", "bundle_hash": "sha256:6d719d1d47aa",
          "code": {"head": "eded53cb5cff38a9437274c69c1b9119c81cf154",
                   "dirty": [{"path": f"f{i}.py", "sha256_12": "0" * 12} for i in range(4)]},
          "machine": {"gpu": "NVIDIA GeForce RTX 3050", "vram_mib": 6141, "ram_gib": 7.6,
                      "placement": {"gpu_pct": 71.0, "offload_pct": 29.0}}, "mode": "real"}


def test_header_shows_caps_code_and_machine():
    lines = render_header(HEADER)
    assert "commit eded53c + dirty 4 files" in lines[0] and "A2 (graph)" in lines[0]
    assert "cap in 6000 / out 1536 tok" in lines[1] and "gen timeout 900 s" in lines[1]
    assert "RTX 3050" in lines[2] and "GPU 71.0% / offload 29.0%" in lines[2]
    assert "68964899" in lines[3] and lines[-1].split()[:3] == ["time", "try", "by"]


def test_header_with_missing_fields_prints_dashes():
    lines = render_header({"task_id": "t"})
    assert "commit unknown" in lines[0] and "—" in lines[2]


def test_step_start_and_end_lines():
    start = render_step("start", {"tool": "generate_patch", "attempt": 0, "by": "agent", "t": T}, 3)
    assert "running" in start and "12:54:52" in start and "1/3" in start
    end = render_step("end", {"tool": "generate_patch", "status": "ERROR", "reason": "GENERATION_TIMEOUT",
                              "duration_ms": 950400, "attempt": 1, "by": "agent", "t": T, "metrics": {}}, 3)
    assert "1/3" in end and "950.4 s" in end and "GENERATION_TIMEOUT" in end
    context = render_step("end", {"tool": "get_task_context", "status": "PASS", "reason": None, "duration_ms": 36700,
                                  "attempt": 0, "by": "agent", "t": T, "run_id": "20261103T125416597686Z-ef3e99a9",
                                  "metrics": {"input_tokens": 3903, "input_cap": 6000, "context_items": 5,
                                              "truncated": True, "failing_tests": 2}}, 3)
    assert "prompt 3903/6000 tok" in context and "5 items (truncated)" in context and "2 failing tests" in context
    host = render_step("end", {"tool": "verify_patch", "status": "ERROR", "reason": "VERIFICATION_INCOMPLETE",
                               "duration_ms": 700, "attempt": 1, "by": "host", "t": T, "metrics": {}}, 3)
    assert "host" in host and "verify_patch (close)" in host


def test_turn_line_shows_followed():
    line = render_turn({"turn": 2, "duration_ms": 23100, "input_tokens": 825, "output_tokens": 16,
                        "tool_calls": ["generate_patch"], "next_hint": "generate_patch", "followed": True})
    assert "model turn 2" in line and "→generate_patch" in line and "in 825 / out 16 tok" in line
    assert line.endswith("· followed")
    ended = render_turn({"turn": 9, "duration_ms": 100, "tool_calls": [], "next_hint": "stop", "followed": None})
    assert ended.endswith("· ended")


def test_result_block_reports_class_and_followed_rate():
    from vgar.agents.trace_report import attempt_funnel, failure_class, time_breakdown
    turns = [dict(t, followed=True, tool_calls=["x"]) for t in MODEL_CALLS]
    trace = {"result": {"status": "FAILED", "attempts": 3}, "calls": CALLS_SEABORN, "model_calls": turns,
             "attempts": attempt_funnel(CALLS_SEABORN, RECORDS_SEABORN),
             "failure_class": failure_class(CALLS_SEABORN, RECORDS_SEABORN, {"status": "FAILED"}),
             "time_breakdown": time_breakdown(3_240_000, CALLS_SEABORN, turns, RECORDS_SEABORN)}
    text = "\n".join(render_result(trace))
    assert "== RESULT FAILED · class MODEL (GENERATION_TIMEOUT) · 3/3 attempts" in text
    assert "run 1/3: generated ✗ GENERATION_TIMEOUT → applied – → tests – → static – → verdict REJECT" in text
    assert "followed NEXT 9/9" in text and "time 54.0 min = generation 47.5 (88%)" in text


def test_result_block_of_a_v1_trace_does_not_crash():
    assert render_result({"result": {"status": "FAILED", "attempts": 0}, "calls": [], "model_calls": []})[0].startswith(
        "== RESULT FAILED")


def test_cli_prints_console_then_keeps_status_lines(tmp_path, capsys):
    from vgar.cli import main
    assert main(["solve", "--task", str(TASK), "--agent", "--output-root", str(tmp_path / "runs")]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith("== solve --agent · single_file_login")
    assert any("model turn 1" in line for line in lines) and any("running" in line for line in lines)
    assert any(line.startswith("== RESULT COMPLETED · class VERIFIED") for line in lines)
    assert [line.split()[0] for line in lines[-3:]] == ["[status]", "[run]", "[trace]"]


def test_chat_turn_with_a_tool_and_no_hint_is_not_called_ended():
    line = render_turn({"turn": 1, "duration_ms": 10, "tool_calls": ["repair_apply_patch"], "next_hint": None,
                        "followed": None})
    assert line.endswith("· n/a")
