from __future__ import annotations

from vgar.agents.state import VGARState


def initialize_task(state: VGARState) -> dict:
    task_id = state.get("task_id")
    repo_path = state.get("repo_path")
    issue_text = state.get("issue_text")

    if not task_id:
        raise ValueError("task_id is required")

    if not repo_path:
        raise ValueError("repo_path is required")

    if not issue_text:
        raise ValueError("issue_text is required")

    max_iterations = state.get("max_iterations", 5)

    if max_iterations <= 0:
        raise ValueError(
            "max_iterations must be greater than zero"
        )

    return {
        "failing_tests": list(
            state.get("failing_tests") or []
        ),
        "attempts": 0,
        "replan_count": 0,
        "needs_replan": False,
        "last_failure_class": None,
        "status": "RUNNING",
        "failure_reason": None,
        "max_iterations": max_iterations,
    }