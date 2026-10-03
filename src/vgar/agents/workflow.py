"""Outer LangGraph workflow: deterministic pipeline around one LLM node.

    START -> initialize -> prepare_workspace -> repair -> verify -+-> finalize -> END
                                                  ^               |
                                                  +---- retry ----+-> failed   -> END
                                                       (attempts < max_iterations)

Only `repair` calls a model. Everything else is plain code, so verification
never depends on what the agent claims.
"""
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from vgar.agents.nodes import (
    finalize,
    finalize_failed,
    initialize_task,
    prepare_workspace,
    repair,
    verify,
)
from vgar.agents.routes import route_after_repair, route_after_verify
from vgar.agents.runtime import Runtime, cleanup_work_dir, new_work_dir
from vgar.agents.state import VGARState


def build_workflow(runtime: Runtime | None = None):
    runtime = runtime or Runtime()

    # Nodes need the per-run Runtime, so bind it with small closures.
    def _prepare(state: VGARState) -> dict:
        return prepare_workspace(state, runtime)

    async def _repair(state: VGARState) -> dict:
        return await repair(state, runtime)

    def _verify(state: VGARState) -> dict:
        return verify(state, runtime)

    workflow = StateGraph(VGARState)
    workflow.add_node("initialize", initialize_task)
    workflow.add_node("prepare_workspace", _prepare)
    workflow.add_node("repair", _repair)
    workflow.add_node("verify", _verify)
    workflow.add_node("finalize", finalize)
    workflow.add_node("failed", finalize_failed)

    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "prepare_workspace")
    workflow.add_edge("prepare_workspace", "repair")
    workflow.add_conditional_edges("repair", route_after_repair, {"verify": "verify", "failed": "failed"})
    workflow.add_conditional_edges(
        "verify",
        route_after_verify,
        {"finalize": "finalize", "repair": "repair", "failed": "failed"},
    )
    workflow.add_edge("finalize", END)
    workflow.add_edge("failed", END)

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
    try:
        return await build_workflow(runtime).ainvoke(
            {
                "task_id": task_id,
                "repo_path": str(Path(repo).resolve()),
                "issue_text": issue_text,
                "failing_tests": list(selectors),
                "max_iterations": max_iterations,
                "work_dir": str(work_dir),
            },
            # initialize + prepare + (repair + verify) * N + final, with headroom
            config={"recursion_limit": 6 + 2 * max_iterations},
        )
    finally:
        cleanup_work_dir(work_dir, runtime.keep_workspace)


app = build_workflow()
