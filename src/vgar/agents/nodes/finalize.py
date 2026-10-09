from __future__ import annotations

from pathlib import Path

from vgar.agents.state import VGARState
from vgar.observability.instrumentation import instrument_node
from vgar.repair.workspace import fingerprint_source


@instrument_node("finalize")
def finalize(state: VGARState) -> dict:
    """Success path still re-checks that the source repository was never touched."""
    source_hash = state.get("source_hash_before")
    if source_hash and fingerprint_source(Path(state["repo_path"])) != source_hash:
        return {
            "status": "FAILED",
            "failure_reason": "Source repository was modified during the run.",
        }
    return {
        "status": "COMPLETED",
        "failure_reason": None,
    }


@instrument_node("failed")
def finalize_failed(state: VGARState) -> dict:
    failure_reason = state.get("failure_reason") or (
        f"Not verified after {state.get('attempts', 0)} attempt(s): "
        f"{state.get('last_failure_class') or 'unknown'}"
    )

    return {
        "status": "FAILED",
        "failure_reason": failure_reason,
    }
