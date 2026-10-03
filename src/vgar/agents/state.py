from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class VGARState(TypedDict, total=False):
    # ---------------------------------------------------------
    # Identity
    # ---------------------------------------------------------

    task_id: str
    repo_path: str

    # ---------------------------------------------------------
    # Sandbox (created by prepare_workspace)
    # ---------------------------------------------------------

    work_dir: str
    workspace_path: str
    worktree_id: str
    source_hash_before: str
    graph_db: str
    graph_node_count: int

    # ---------------------------------------------------------
    # Original task
    # ---------------------------------------------------------

    issue_text: str
    failing_tests: list[str]

    # ---------------------------------------------------------
    # Graph/task grounding
    # W5-W6
    # ---------------------------------------------------------

    anchors: list[dict[str, Any]]
    context: dict[str, Any]

    # ---------------------------------------------------------
    # Planning
    # W5-W6
    # ---------------------------------------------------------

    repair_plan: dict[str, Any]

    # ---------------------------------------------------------
    # Core LangChain agent
    # ---------------------------------------------------------

    agent_messages: list[Any]
    tool_call_count: int

    # ---------------------------------------------------------
    # Repair artifacts
    # W7-W8
    # ---------------------------------------------------------

    patch_diff: str
    changed_files: list[str]
    worktree_id: str

    # ---------------------------------------------------------
    # Verification
    # W7+
    # ---------------------------------------------------------

    evidence: dict[str, Any]
    impact_report: dict[str, Any]

    # ---------------------------------------------------------
    # Loop control
    # ---------------------------------------------------------

    attempts: int
    max_iterations: int
    replan_count: int

    # ---------------------------------------------------------
    # Verification-driven routing
    # ---------------------------------------------------------

    last_failure_class: str | None
    needs_replan: bool

    # ---------------------------------------------------------
    # Terminal state
    # ---------------------------------------------------------

    status: str
    failure_reason: str | None