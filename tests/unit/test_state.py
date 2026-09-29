from vgar.agents.nodes.initialize import (
    initialize_task,
)


def test_initialize_task_sets_defaults():
    state = {
        "task_id": "task-001",
        "repo_path": "/repo",
        "issue_text": "Fix authentication.",
    }

    result = initialize_task(state)

    assert result["attempts"] == 0
    assert result["replan_count"] == 0
    assert result["needs_replan"] is False
    assert result["last_failure_class"] is None
    assert result["status"] == "RUNNING"
    assert result["failure_reason"] is None
    assert result["max_iterations"] == 5


def test_initialize_preserves_configured_iterations():
    result = initialize_task(
        {
            "task_id": "task-001",
            "repo_path": "/repo",
            "issue_text": "Fix issue.",
            "max_iterations": 3,
        }
    )

    assert result["max_iterations"] == 3