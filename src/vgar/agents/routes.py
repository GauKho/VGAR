from __future__ import annotations

from vgar.agents.state import VGARState
from vgar.observability.instrumentation import emit


def _route(router: str, condition: str, observed, target: str, state: VGARState) -> str:
    emit(
        "ROUTE_DECISION",
        router=router,
        condition=condition,
        observed=observed,
        target=target,
        state={"failure_reason": state.get("failure_reason"), "attempts": state.get("attempts")},
    )
    return target


def route_after_retrieve(state: VGARState) -> str:
    ready = bool(state.get("run_dir") and state.get("prompt"))
    return _route("route_after_retrieve", "run_dir and prompt returned", ready, "generate" if ready else "failed", state)


def route_after_apply(state: VGARState) -> str:
    status = state.get("apply_status")
    return _route("route_after_apply", "apply_status == PASS", status, "test" if status == "PASS" else "verify", state)


def route_after_verify(state: VGARState) -> str:
    recommendation = state.get("recommendation")
    return _route("route_after_verify", "recommendation == ACCEPT", recommendation,
                  "finalize" if recommendation == "ACCEPT" else "failed", state)
