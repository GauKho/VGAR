"""Outer LangGraph workflow around the M2 repair pipeline (one generation).

    START -> initialize -> repair_run -+-> finalize -> END
                                       +-> failed   -> END

`repair_run` calls vgar.repair.pipeline.run_repair exactly once: prompt,
unified diff, private worktree, tests/mypy/Ruff and the evidence bundle all
come from M2 code, so verification never depends on what the model claims.
"""
from __future__ import annotations

from pathlib import Path
import time
import uuid

from langgraph.graph import END, START, StateGraph

from vgar.agents.nodes import finalize, finalize_failed, initialize_task, repair_run
from vgar.agents.routes import route_after_repair_run
from vgar.agents.runtime import Runtime, cleanup_work_dir, new_work_dir
from vgar.agents.state import VGARState
from vgar.observability.instrumentation import emit, trace_run


def build_workflow(runtime: Runtime | None = None):
    runtime = runtime or Runtime()

    def _repair_run(state: VGARState) -> dict:
        return repair_run(state, runtime)

    workflow = StateGraph(VGARState)
    workflow.add_node("initialize", initialize_task)
    workflow.add_node("repair_run", _repair_run)
    workflow.add_node("finalize", finalize)
    workflow.add_node("failed", finalize_failed)

    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "repair_run")
    workflow.add_conditional_edges("repair_run", route_after_repair_run, {"finalize": "finalize", "failed": "failed"})
    workflow.add_edge("finalize", END)
    workflow.add_edge("failed", END)

    return workflow.compile()


async def run_task(*, task_path: Path, runtime: Runtime | None = None) -> VGARState:
    """Run one M2 task file end to end. Owns the temp dir so cleanup also happens on errors."""
    from vgar.repair.config import load_task
    from vgar.repair.workspace import fingerprint_source

    runtime = runtime or Runtime()
    task_path = Path(task_path).resolve()
    task = load_task(task_path)
    work_dir = new_work_dir()
    run_id = uuid.uuid4().hex
    started = time.perf_counter()
    initial_state = {
        "task_id": task.task_id,
        "task_path": str(task_path),
        "repo_path": str(task.source_repo),
        "issue_text": task.issue_text,
        "failing_tests": list(task.failing_selectors),
        "max_iterations": 1,
        "work_dir": str(work_dir),
        "source_hash_before": fingerprint_source(task.source_repo),
    }
    emit(
        "WORKFLOW_START",
        run_id=run_id,
        task_id=task.task_id,
        repo_path=str(task.source_repo),
        failing_tests=list(task.failing_selectors),
        max_iterations=1,
        initial_state=initial_state,
    )
    try:
        with trace_run(run_id):
            result = await build_workflow(runtime).ainvoke(initial_state, config={"recursion_limit": 8})
        emit(
            "WORKFLOW_END",
            run_id=run_id,
            duration_ms=round((time.perf_counter() - started) * 1000),
            status=result.get("status"),
            attempts=result.get("attempts"),
            run_record_path=result.get("run_record_path"),
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
