from __future__ import annotations

from vgar.agents.state import VGARState


def route_after_core_agent(
    state: VGARState,
) -> str:
    if state.get("failure_reason"):
        return "failed"

    return "finalize"