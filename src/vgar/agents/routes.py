from __future__ import annotations

from vgar.agents.state import VGARState


def route_after_repair(state: VGARState) -> str:
    return "failed" if state.get("failure_reason") else "verify"


def route_after_verify(state: VGARState) -> str:
    if (state.get("evidence") or {}).get("passed"):
        return "finalize"

    if state.get("attempts", 0) < state.get("max_iterations", 1):
        return "repair"

    return "failed"
