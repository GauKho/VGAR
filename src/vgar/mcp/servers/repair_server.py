"""MCP repair server: the M2 pipeline as four tools over one persisted run.

Order inside a run is strict: get_task_context -> apply_patch (once) -> run_relevant_tests (optional)
-> verify_patch. Each process may be a fresh server (the adapter opens a session per tool call), so
all state lives in the run directory. Tools only run on trusted fixtures and only write inside the
run's private worktree; every accepted call is appended to run_record.mcp_calls.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.observability.instrumentation import instrument_mcp_tool

mcp = FastMCP("vgar-repair")

# Phases a run must be in for each tool (verify_patch accepts any unfinished phase).
REQUIRED_PHASE = {"apply_patch": ("prepared",), "run_relevant_tests": ("applied",),
                  "verify_patch": ("prepared", "generated", "applied", "tested")}


def _entry(tool: str, inputs: dict[str, Any], started_utc: str, start: float, status: str) -> dict[str, Any]:
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {"tool": tool, "input_sha256": digest, "started_utc": started_utc,
            "duration_ms": round((time.monotonic() - start) * 1000), "status": status}


def _log(session, entry: dict[str, Any]) -> None:
    session.run.record["mcp_calls"].append(entry)
    session.run.save()


def _tool_error(error: BaseException) -> dict[str, Any]:
    return {"status": "ERROR", "reason": "TOOL_ERROR", "detail": f"{type(error).__name__}: {error}"}


def _load(tool: str, run_dir: str):
    from vgar.repair.session import RepairSession
    session = RepairSession.load(Path(run_dir))
    if session.phase not in REQUIRED_PHASE[tool]:
        raise ValueError(f"Tool order violation: {tool} needs phase {'/'.join(REQUIRED_PHASE[tool])}, "
                         f"run is {session.phase}")
    return session


def _tooling(session):
    from vgar.repair.pipeline import build_tokenizer
    output_root = session.run.directory.parent
    return build_tokenizer(session.state["mode"], session.policy, _profile(session), output_root)


def _profile(session):
    from vgar.repair.config import CONFIG_DIR, load_config
    return session.profile or load_config(session.state.get("config_path") or CONFIG_DIR / "demo.json")[1]


def _detail(record: dict[str, Any]) -> str | None:
    return (record.get("error_detail") or {}).get("message")


def _finish(session, tool, inputs, started_utc, start) -> dict[str, Any]:
    from vgar.repair.pipeline import recommendation_for
    from vgar.repair.session import finish
    run = finish(session, on_record=lambda status: session.run.record["mcp_calls"].append(
        _entry(tool, inputs, started_utc, start, status)))
    status, reason = run.record["status"], run.record.get("reason")
    bundle_path = run.directory / "evidence_bundle.json"
    evidence = json.loads(bundle_path.read_text(encoding="utf-8")) if bundle_path.is_file() else {}
    return {"status": status, "reason": reason, "detail": _detail(run.record),
            "recommendation": recommendation_for(status), "evidence": evidence,
            "run_dir": str(run.directory), "run_record_path": str(run.path)}


@mcp.tool()
@instrument_mcp_tool("get_task_context")
def get_task_context(task_path: str, mode: str, output_root: str, work_root: str,
                     config_path: str | None = None, keep_workspace: bool = False,
                     feedback: dict[str, Any] | None = None, supersedes_run_id: str | None = None,
                     rerun_reason: str | None = None) -> dict[str, Any]:
    """Start a run on a trusted fixture task: M1 context, private worktree, baseline and the V11 prompt.

    With feedback the run is a rerun: the feedback is appended to the V11 prompt and the run records
    which run it supersedes and why."""
    from vgar.repair.config import CONFIG_DIR, load_config, load_task
    from vgar.repair.executor import utc_now
    from vgar.repair.pipeline import build_tokenizer
    from vgar.repair.session import prepare, start_session
    inputs = {"task_path": task_path, "mode": mode, "output_root": output_root, "work_root": work_root,
              "config_path": config_path, "keep_workspace": keep_workspace}
    rerun = {"feedback": feedback, "supersedes_run_id": supersedes_run_id, "rerun_reason": rerun_reason}
    inputs.update({key: value for key, value in rerun.items() if value is not None})
    started_utc, start = utc_now(), time.monotonic()
    try:
        policy, profile = load_config(config_path or CONFIG_DIR / "demo.json")
        task = load_task(task_path)
        tokenizer, counter = build_tokenizer(mode, policy, profile, output_root)
        session = start_session(task, policy, mode, output_root, profile=profile if mode == "real" else None,
                                temp_root=Path(work_root), keep_workspace=keep_workspace, mcp_scope="repair_server",
                                **rerun)
        session.state["config_path"] = str(config_path or CONFIG_DIR / "demo.json")
        session.save()
    except Exception as error:
        return _tool_error(error)
    prompt = prepare(session, counter, tokenizer)
    if prompt is None:
        return _finish(session, "get_task_context", inputs, started_utc, start)
    _log(session, _entry("get_task_context", inputs, started_utc, start, "PASS"))
    return {"status": "PASS", "run_dir": str(session.run.directory), "run_id": session.run.record["run_id"],
            "worktree_id": session.state["lease"]["worktree_id"], "prompt": asdict(prompt),
            "failed_cases": session.state["baseline"].get("failed_cases", []),
            "context": session.run.record["stages"]["context"]["context"]}


@mcp.tool()
@instrument_mcp_tool("apply_patch")
def apply_patch(run_dir: str, diff: str, generation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record the client's generation, strictly parse the unified diff and git-apply it in the worktree."""
    from vgar.repair.executor import utc_now
    from vgar.repair.session import apply_candidate, record_generation
    inputs = {"run_dir": run_dir, "diff": diff, "generation": generation}
    started_utc, start = utc_now(), time.monotonic()
    try:
        session = _load("apply_patch", run_dir)
    except Exception as error:
        return _tool_error(error)
    meta = dict(generation or {"status": "PASS", "mode": "tool_input", "truncated": False})
    gen_started = meta.pop("started_utc", started_utc)
    gen_duration = meta.pop("duration_ms", 0)
    meta.setdefault("truncated", False)
    raw = record_generation(session, dict(meta, raw_text=diff), started_utc=gen_started, duration_ms=gen_duration)
    applied = apply_candidate(session, raw) if raw is not None else None
    status, reason = (applied.status, None) if applied is not None else tuple(session.outcome)
    _log(session, _entry("apply_patch", inputs, started_utc, start, status))
    return {"status": status, "reason": reason, "changed_files": list(applied.changed_files) if applied else []}


@mcp.tool()
@instrument_mcp_tool("run_relevant_tests")
def run_relevant_tests(run_dir: str) -> dict[str, Any]:
    """Select the relevant tests for the changed files and run them in the worktree."""
    from vgar.repair.executor import utc_now
    from vgar.repair.pipeline import _test_groups, test_vector
    from vgar.repair.session import run_selected_tests
    inputs = {"run_dir": run_dir}
    started_utc, start = utc_now(), time.monotonic()
    try:
        session = _load("run_relevant_tests", run_dir)
        _, counter = _tooling(session)
    except Exception as error:
        return _tool_error(error)
    partial = run_selected_tests(session, counter)
    if partial is None or partial["status"] != "TESTED":
        status = "ERROR"
        result = {"status": status, "reason": (session.outcome or (None, partial and partial.get("reason")))[1]}
    else:
        failing, relevant = _test_groups(test_vector(partial["tests"]), session.state["baseline"])
        status = "PASS" if failing.status == relevant.status == "PASS" or (
            failing.status == "PASS" and relevant.status == "NOT_RUN") else "FAIL"
        result = {"status": status, "failing_tests": failing.model_dump(mode="json"),
                  "relevant_tests": relevant.model_dump(mode="json")}
    _log(session, _entry("run_relevant_tests", inputs, started_utc, start, status))
    return result


@mcp.tool()
@instrument_mcp_tool("verify_patch")
def verify_patch(run_dir: str) -> dict[str, Any]:
    """Static checks and final assessment, clean the worktree and publish the evidence bundle."""
    from vgar.repair.executor import utc_now
    inputs = {"run_dir": run_dir}
    started_utc, start = utc_now(), time.monotonic()
    try:
        session = _load("verify_patch", run_dir)
    except Exception as error:
        return _tool_error(error)
    return _finish(session, "verify_patch", inputs, started_utc, start)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
