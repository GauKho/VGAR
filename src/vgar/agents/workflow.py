"""Outer LangGraph workflow.

Interim state while M2 W7-W8 moves into src/vgar: only `initialize` runs.
The M2 pipeline node is wired in by the next migration step.
"""
from __future__ import annotations

from pathlib import Path
import time
import uuid

from langgraph.graph import END, START, StateGraph

from vgar.agents.nodes import initialize_task
from vgar.agents.runtime import Runtime, cleanup_work_dir, new_work_dir
from vgar.agents.state import VGARState
from vgar.observability.instrumentation import emit, trace_run


def build_workflow(runtime: Runtime | None = None):
    workflow = StateGraph(VGARState)
    workflow.add_node("initialize", initialize_task)
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", END)
    return workflow.compile()


async def run_task(
    *,
    repo: Path,
    issue_text: str,
    selectors: list[str],
    runtime: Runtime | None = None,
    task_id: str = "task-001",
) -> VGARState:
    """Run one task end to end. Owns the temp dir so cleanup also happens on errors."""
    runtime = runtime or Runtime()
    max_iterations = runtime.base_settings().agent.max_iterations
    work_dir = new_work_dir()
    run_id = uuid.uuid4().hex
    started = time.perf_counter()
    initial_state = {
        "task_id": task_id,
        "repo_path": str(Path(repo).resolve()),
        "issue_text": issue_text,
        "failing_tests": list(selectors),
        "max_iterations": max_iterations,
        "work_dir": str(work_dir),
    }
    emit(
        "WORKFLOW_START",
        run_id=run_id,
        task_id=task_id,
        repo_path=str(Path(repo).resolve()),
        failing_tests=list(selectors),
        max_iterations=max_iterations,
        initial_state=initial_state,
    )
    try:
        with trace_run(run_id):
            result = await build_workflow(runtime).ainvoke(
                initial_state,
                config={"recursion_limit": 6 + 2 * max_iterations},
            )
        emit(
            "WORKFLOW_END",
            run_id=run_id,
            duration_ms=round((time.perf_counter() - started) * 1000),
            status=result.get("status"),
            attempts=result.get("attempts"),
            tool_call_count=result.get("tool_call_count"),
            evidence=result.get("evidence"),
            failure_reason=result.get("failure_reason"),
        )
        return result
    except Exception as exc:
        emit(
            "WORKFLOW_ERROR",
            run_id=run_id,
            duration_ms=round((time.perf_counter() - started) * 1000),
            exception=type(exc).__name__,
            message=str(exc),
        )
        raise
    finally:
        emit("WORKFLOW_CLEANUP_START", run_id=run_id, work_dir=str(work_dir), keep=runtime.keep_workspace)
        cleanup_work_dir(work_dir, runtime.keep_workspace)
        emit("WORKFLOW_CLEANUP_END", run_id=run_id, duration_ms=round((time.perf_counter() - started) * 1000))


app = build_workflow()
