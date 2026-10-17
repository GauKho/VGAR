from __future__ import annotations

from vgar.agents.state import VGARState
from vgar.observability.instrumentation import emit


def route_after_repair_run(state: VGARState) -> str:
    target = "finalize" if state.get("repair_status") == "PASS" else "failed"
    emit(
        "ROUTE_DECISION",
        router="route_after_repair_run",
        condition="repair_status == PASS",
        observed=state.get("repair_status"),
        target=target,
        state={"failure_reason": state.get("failure_reason"), "attempts": state.get("attempts")},
    )
    return target
