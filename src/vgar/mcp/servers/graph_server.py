from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.observability.instrumentation import instrument_mcp_tool

from vgar.graph.factory import create_graph_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.tooling import audit_resource, run_tool


mcp = FastMCP("vgar-graph")
graph_service = create_graph_service()
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))


def _tool(tool: str, call, audit_fields: dict[str, Any], summarize) -> dict[str, Any]:
    # Module globals are looked up at call time so tests can swap the backend/logger.
    return run_tool(
        server="graph",
        tool=tool,
        backend=graph_service.backend_name,
        audit=_audit_logger,
        call=call,
        audit_fields=audit_fields,
        summarize=summarize,
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
@instrument_mcp_tool("search_symbols")
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
@instrument_mcp_tool("get_callers")
def get_callers(symbol_id: str, depth: int = 1) -> dict[str, Any]:
    """Return direct callers of a symbol. depth is reserved for W5-W6 traversal (only 1 is applied)."""

    def call() -> dict[str, Any]:
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
@instrument_mcp_tool("get_callees")
def get_callees(symbol_id: str, depth: int = 1) -> dict[str, Any]:
    """Return direct callees of a symbol. depth is reserved for W5-W6 traversal (only 1 is applied)."""

    def call() -> dict[str, Any]:
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


@mcp.resource("vgar://repo/summary")
def repo_summary() -> str:
    with _resource("vgar://repo/summary"):
        result = graph_service.get_repository_summary()
        return result.model_dump_json(indent=2)


@mcp.resource("vgar://graph/node/{node_id}")
def graph_node(node_id: str) -> str:
    with _resource("vgar://graph/node/{node_id}", node_id=node_id):
        result = graph_service.get_node(node_id)
        return result.model_dump_json(indent=2)


@mcp.resource("vgar://graph/subgraph/{node_id}")
def graph_subgraph(node_id: str) -> str:
    with _resource("vgar://graph/subgraph/{node_id}", node_id=node_id, depth=2) as out:
        result = graph_service.get_subgraph(node_id, depth=2)
        out.update(node_count=len(result.nodes), edge_count=len(result.edges))
        return result.model_dump_json(indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
