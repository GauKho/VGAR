"""Outer LangGraph workflow: a fixed repair flow whose repair steps are MCP tool calls.

    START -> initialize -> retrieve -+-> generate -> apply -+-> test -> verify -+-> finalize -> END
                                     |                      +---------> verify  +-> failed   -> END
                                     +-> failed -> END

retrieve/apply/test/verify call the MCP `repair` server (repair_get_task_context,
repair_apply_patch, repair_run_relevant_tests, repair_verify_patch); generate is the only
model call. verify is the single finalizer of a started run, so the worktree is always cleaned.
"""
from __future__ import annotations

from pathlib import Path
import time
import uuid

from langgraph.graph import END, START, StateGraph

from vgar.agents.nodes import apply, finalize, finalize_failed, generate, initialize_task, retrieve, test, verify
from vgar.agents.routes import route_after_apply, route_after_retrieve, route_after_verify
from vgar.agents.runtime import Runtime, cleanup_work_dir, new_work_dir
from vgar.agents.state import VGARState
from vgar.observability.instrumentation import emit, trace_run


def build_workflow(runtime: Runtime | None = None):
    runtime = runtime or Runtime()

    def bind(node):
        async def run(state: VGARState) -> dict:
            return await node(state, runtime)
        return run

    workflow = StateGraph(VGARState)
    workflow.add_node("initialize", initialize_task)
    for name, node in (("retrieve", retrieve), ("generate", generate), ("apply", apply), ("test", test),
                       ("verify", verify)):
        workflow.add_node(name, bind(node))
    workflow.add_node("finalize", finalize)
    workflow.add_node("failed", finalize_failed)

    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "retrieve")
    workflow.add_conditional_edges("retrieve", route_after_retrieve, {"generate": "generate", "failed": "failed"})
    workflow.add_edge("generate", "apply")
    workflow.add_conditional_edges("apply", route_after_apply, {"test": "test", "verify": "verify"})
    workflow.add_edge("test", "verify")
    workflow.add_conditional_edges("verify", route_after_verify, {"finalize": "finalize", "failed": "failed"})
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
            result = await build_workflow(runtime).ainvoke(initial_state, config={"recursion_limit": 12})
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
