from __future__ import annotations

from collections.abc import Iterable

from langchain_core.tools import BaseTool


W3_W4_REQUIRED_GRAPH_TOOLS = {
    "graph_search_symbols",
    "graph_get_callers",
    "graph_get_callees",
}

W5_W6_REQUIRED_GRAPH_TOOLS = {"graph_find_task_anchors", "graph_get_related_context"}


def get_tool_names(
    tools: Iterable[BaseTool],
) -> set[str]:
    return {
        tool.name
        for tool in tools
    }


def validate_required_tools(
    tools: Iterable[BaseTool],
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
