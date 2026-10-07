from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from vgar.contracts.error import InvalidLimitError, NodeNotFoundError

from mcp.server.fastmcp import FastMCP

from vgar.graph.factory import create_graph_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.tooling import audit_resource, run_tool


mcp = FastMCP("vgar-graph")
graph_service = create_graph_service()
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))


def _tool(tool: str, call, audit_fields: dict[str, Any], summarize, metadata_fields=None) -> dict[str, Any]:
    # Module globals are looked up at call time so tests can swap the backend/logger.
    return run_tool(
        server="graph",
        tool=tool,
        backend=graph_service.backend_name,
        audit=_audit_logger,
        call=call,
        audit_fields=audit_fields,
        summarize=summarize,
        metadata_fields=metadata_fields,
    )


def _resource(resource: str, **fields: Any):
    return audit_resource(
        server="graph",
        resource=resource,
        backend=graph_service.backend_name,
        audit=_audit_logger,
        fields=fields,
    )


@mcp.tool()
def search_symbols(query: str, limit: int = 20) -> dict[str, Any]:
    """Search repository symbols. Returns the VGAR envelope; data = {query, limit, symbols}."""

    def call() -> dict[str, Any]:
        result = graph_service.search_symbols(query=query, limit=limit)
        return {
            "query": result.query,
            "limit": limit,
            "symbols": [symbol.model_dump() for symbol in result.symbols],
        }

    return _tool(
        "search_symbols", call,
        {"query": query, "limit": limit},
        lambda data: {"result_count": len(data["symbols"])},
    )


@mcp.tool()
def get_callers(symbol_id: str, depth: int = 1) -> dict[str, Any]:
    """Return direct callers; unsupported depths are rejected, never echoed as multi-hop."""

    def call() -> dict[str, Any]:
        if isinstance(depth, bool) or not isinstance(depth, int) or depth != 1:
            raise InvalidLimitError("Only depth=1 is implemented for callers")
        result = graph_service.get_callers(symbol_id)
        return {
            "symbol_id": symbol_id,
            "depth": depth,
            "callers": [symbol.model_dump() for symbol in result.symbols],
        }

    return _tool(
        "get_callers", call,
        {"symbol_id": symbol_id, "depth": depth},
        lambda data: {"result_count": len(data["callers"])},
    )


@mcp.tool()
def get_callees(symbol_id: str, depth: int = 1) -> dict[str, Any]:
    """Return direct callees; unsupported depths are rejected, never echoed as multi-hop."""

    def call() -> dict[str, Any]:
        if isinstance(depth, bool) or not isinstance(depth, int) or depth != 1:
            raise InvalidLimitError("Only depth=1 is implemented for callees")
        result = graph_service.get_callees(symbol_id)
        return {
            "symbol_id": symbol_id,
            "depth": depth,
            "callees": [symbol.model_dump() for symbol in result.symbols],
        }

    return _tool(
        "get_callees", call,
        {"symbol_id": symbol_id, "depth": depth},
        lambda data: {"result_count": len(data["callees"])},
    )


@mcp.tool()
def find_task_anchors(issue_text: str, failing_tests: list[str] | None = None) -> dict[str, Any]:
    """Ground an issue and return a task_handle for stateless related-context calls."""
    return _tool("find_task_anchors", lambda: graph_service.find_task_anchors(issue_text, failing_tests),
                 {"issue_length": len(issue_text) if isinstance(issue_text, str) else None,
                  "failing_test_count": len(failing_tests) if isinstance(failing_tests, list) else 0},
                 lambda data: {"anchor_count": len(data["anchor_ids"]), "task_handle": data["task_handle"]})


@mcp.tool()
def get_related_context(anchor_ids: list[str], budget_tokens: int, task_handle: str) -> dict[str, Any]:
    """Return the unchanged ContextPayload; task handle identifies the exact issue/overlay."""
    diagnostics = {}

    def call():
        result = graph_service.get_related_context(anchor_ids, budget_tokens, task_handle)
        diagnostics.update(task_handle=task_handle, overlay_id=result.overlay_id, counter_label=result.counter_label,
                           retrieval_diagnostics={"unavailable_features": result.unavailable_features,
                              "omissions": result.omissions, "traversal_limited": result.traversal_limited, "config": result.config})
        return result.context.model_dump(mode="json")

    return _tool("get_related_context", call, {"task_handle": task_handle, "budget_tokens": budget_tokens},
                 lambda data: {"item_count": len(data["items"]), "token_count": data["total_token_count"]},
                 metadata_fields=lambda: diagnostics)


def _resource_node(call, node_id, **kwargs):
    try:
        return call(node_id, **kwargs)
    except NodeNotFoundError:
        decoded = unquote(node_id)
        if decoded == node_id:
            raise
        return call(decoded, **kwargs)


@mcp.resource("vgar://repo/summary")
def repo_summary() -> str:
    with _resource("vgar://repo/summary"):
        result = graph_service.get_repository_summary()
        return result.model_dump_json(indent=2)


@mcp.resource("vgar://graph/node/{node_id}")
def graph_node(node_id: str) -> str:
    with _resource("vgar://graph/node/{node_id}", node_id=node_id):
        result = _resource_node(graph_service.get_node, node_id)
        return result.model_dump_json(indent=2)


@mcp.resource("vgar://graph/subgraph/{node_id}")
def graph_subgraph(node_id: str) -> str:
    with _resource("vgar://graph/subgraph/{node_id}", node_id=node_id, depth=2) as out:
        result = _resource_node(graph_service.get_subgraph, node_id, depth=2)
        out.update(node_count=len(result.nodes), edge_count=len(result.edges))
        return result.model_dump_json(indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
