from __future__ import annotations

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from vgar.agents.nodes import (
    finalize,
    finalize_failed,
    initialize_task,
)
from vgar.agents.routes import (
    route_after_core_agent,
)
from vgar.agents.state import VGARState


async def infrastructure_probe(
    state: VGARState,
) -> dict:
    """
    W3-W4 placeholder node.

    This node will be replaced by the real task-grounding /
    retrieval path during W5-W6.

    It intentionally performs no repair.
    """

    return {
        "status": "INFRASTRUCTURE_READY",
    }


def build_workflow():
    workflow = StateGraph(VGARState)

    workflow.add_node(
        "initialize",
        initialize_task,
    )

    workflow.add_node(
        "infrastructure_probe",
        infrastructure_probe,
    )

    workflow.add_node(
        "finalize",
        finalize,
    )

    workflow.add_node(
        "failed",
        finalize_failed,
    )

    workflow.add_edge(
        START,
        "initialize",
    )

    workflow.add_edge(
        "initialize",
        "infrastructure_probe",
    )

    workflow.add_conditional_edges(
        "infrastructure_probe",
        route_after_core_agent,
        {
            "finalize": "finalize",
            "failed": "failed",
        },
    )

    workflow.add_edge(
        "finalize",
        END,
    )

    workflow.add_edge(
        "failed",
        END,
    )

    return workflow.compile()


app = build_workflow()