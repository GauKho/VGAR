from vgar.agents.routes import (
    route_after_core_agent,
)


def test_route_success_to_finalize():
    state = {
        "status": "RUNNING",
        "failure_reason": None,
    }

    assert (
        route_after_core_agent(state)
        == "finalize"
    )


def test_route_failure_to_failed():
    state = {
        "failure_reason": "Infrastructure failure",
    }

    assert (
        route_after_core_agent(state)
        == "failed"
    )