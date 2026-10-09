from __future__ import annotations

from vgar.agents.state import VGARState
from vgar.observability.instrumentation import emit


def route_after_repair(state: VGARState) -> str:
    target = "failed" if state.get("failure_reason") else "verify"
    emit(
        "ROUTE_DECISION",
        router="route_after_repair",
        condition="failure_reason is truthy",
        observed=bool(state.get("failure_reason")),
        target=target,
        state={"failure_reason": state.get("failure_reason"), "attempts": state.get("attempts")},
    )
    return target


def route_after_verify(state: VGARState) -> str:
    passed = bool((state.get("evidence") or {}).get("passed"))
    if passed:
        target, reason = "finalize", "evidence.passed"
    elif state.get("attempts", 0) < state.get("max_iterations", 1):
        target, reason = "repair", "attempts < max_iterations"
    else:
        target, reason = "failed", "max_iterations exhausted"

    emit(
        "ROUTE_DECISION",
        router="route_after_verify",
        condition=reason,
        target=target,
        state={
            "evidence_passed": passed,
            "attempts": state.get("attempts", 0),
            "max_iterations": state.get("max_iterations", 1),
            "last_failure_class": state.get("last_failure_class"),
        },
    )
    return target
