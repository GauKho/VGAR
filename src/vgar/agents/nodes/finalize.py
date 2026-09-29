from __future__ import annotations

from vgar.agents.state import VGARState


def finalize(state: VGARState) -> dict:
    return {
        "status": "COMPLETED",
        "failure_reason": None,
    }


def finalize_failed(state: VGARState) -> dict:
    failure_reason = state.get(
        "failure_reason",
        "Workflow failed.",
    )

    return {
        "status": "FAILED",
        "failure_reason": failure_reason,
    }