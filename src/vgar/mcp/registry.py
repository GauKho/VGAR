from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class NamedTool(Protocol):
    """Only the public tool name is needed here, independent of any agent framework."""

    @property
    def name(self) -> str: ...


W3_W4_REQUIRED_GRAPH_TOOLS = {
    "graph_search_symbols",
    "graph_get_callers",
    "graph_get_callees",
}

W5_W6_REQUIRED_GRAPH_TOOLS = {"graph_find_task_anchors", "graph_get_related_context"}


def get_tool_names(
    tools: Iterable[NamedTool],
) -> set[str]:
    return {
        tool.name
        for tool in tools
    }


def validate_required_tools(
    tools: Iterable[NamedTool],
    required: set[str],
) -> None:
    names = get_tool_names(tools)

    missing = required - names

    if missing:
        formatted = ", ".join(sorted(missing))

        raise RuntimeError(
            "Missing required MCP tools: "
            f"{formatted}"
        )


# S9 (M3-W11-1): every tool an agent may see. A tool added to a server is refused until it is listed here,
# i.e. until someone has checked it takes no root/path/timeout chosen by the model and does not write files.
PUBLIC_TOOLS = frozenset({
    "graph_build_or_update_graph", "graph_explain_dependency_path", "graph_verify_patch_graph_constraints",
    "graph_rank_patch_candidates", "execution_run_relevant_tests",
    "graph_search_symbols", "graph_get_callers", "graph_get_callees", "graph_find_task_anchors",
    "graph_get_related_context", "graph_get_related_tests", "graph_analyze_patch_impact",
    "repository_health", "repository_read_file",
    "execution_health", "execution_run_pytest",
})


def validate_public_tools(tools: Iterable[NamedTool]) -> None:
    unknown = sorted(get_tool_names(tools) - PUBLIC_TOOLS)
    if unknown:
        raise RuntimeError("Unguarded MCP tool(s): " + ", ".join(unknown))
