from __future__ import annotations

import hashlib
import os
from contextlib import nullcontext
from pathlib import Path
from types import MappingProxyType
from typing import Any

from vgar.graph.factory import create_graph_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal import contracts as proposal_contracts
from vgar.mcp.proposal.context import current_context, request_scope
from vgar.mcp.proposal.ports import ProviderRegistry
from vgar.mcp.proposal.prompts import (
    PROMPT_NAME,
    PromptRenderer,
    audit_protocol_reject,
    serve_prompt,
)
from vgar.mcp.proposal.resources import ResourceReader
from vgar.mcp.proposal.tools import CoreTools, legacy_binding
from vgar.mcp.server_factory import create_resource_server
from vgar.mcp.tooling import audit_resource, run_tool
from vgar.observability.instrumentation import instrument_mcp_tool

mcp = create_resource_server("vgar-graph", lambda uri: _read_resource(uri), log_level="WARNING",
                             prompt_reader=lambda name, arguments: _get_prompt(name, arguments),
                             protocol_reject=lambda: audit_protocol_reject(_audit_logger))
graph_service = create_graph_service()
core_tools = CoreTools(ProviderRegistry())  # Trusted bootstrap may replace before serving; never a tool argument.
prompt_renderer = PromptRenderer()  # Host may configure lower limits/redaction before serving.
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))


def _tool(tool: str, call, audit_fields: dict[str, Any], summarize) -> dict[str, Any]:
    # Module globals are looked up at call time so tests can swap the backend/logger.
    def guarded_call():
        ctx = legacy_binding()
        store = getattr(graph_service, "store", None)
        if ctx is not None and store is not None and store.requested_graph_version != ctx.snapshot_hash:
            raise ValueError("Bound legacy store must explicitly pin the snapshot; latest is not allowed")
        if ctx is not None and graph_service.get_repository_summary().graph_version != ctx.snapshot_hash:
            raise ValueError("Legacy backend snapshot does not match host binding")
        value = call()
        legacy_binding()
        return value
    kwargs = {
        "server": "graph", "tool": tool, "backend": graph_service.backend_name, "audit": _audit_logger,
        "call": guarded_call, "audit_fields": audit_fields, "summarize": summarize,
        "untrusted": True,  # S12: names, paths and snippets come from the repository
    }
    try:
        ctx = current_context()
        if ctx is None and core_tools.context_factory is not None:
            ctx = core_tools._context(tool, MappingProxyType(dict(audit_fields)))
    except Exception as exc:  # noqa: BLE001 - preserve terminal envelope/audit on bootstrap failure
        def fail(error=exc): raise error
        kwargs["call"] = fail
        return run_tool(**kwargs)
    with request_scope(ctx) if ctx is not None else nullcontext():
        return run_tool(**kwargs)


def _resource(resource: str, **fields: Any):
    return audit_resource(
        server="graph",
        resource=resource,
        backend=graph_service.backend_name,
        audit=_audit_logger,
        fields=fields,
    )


def _read_resource(uri: str) -> str:
    # Resolve globals at call time for trusted bootstrap and isolated tests.
    return ResourceReader(core_tools, graph_service, _audit_logger).read(uri)


@mcp.tool()
@instrument_mcp_tool("search_symbols")
def search_symbols(query: str, limit: int = 20) -> dict[str, Any]:
    """Search repository symbols. Returns the VGAR envelope; data = {query, limit, symbols}."""

    def call() -> dict[str, Any]:
        legacy_binding()
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
    """Return direct callers; multi-hop requires a host-bound traversal provider."""

    if type(depth) is int and depth > 1:
        return _multihop(symbol_id, depth, "callers")
    def call() -> dict[str, Any]:
        legacy_binding()
        if type(depth) is not int or depth < 1:
            raise ValueError("Depth must be a positive integer")
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
    """Return direct callees; multi-hop requires a host-bound traversal provider."""

    if type(depth) is int and depth > 1:
        return _multihop(symbol_id, depth, "callees")
    def call() -> dict[str, Any]:
        legacy_binding()
        if type(depth) is not int or depth < 1:
            raise ValueError("Depth must be a positive integer")
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
    return _read_resource("vgar://repo/summary")


@mcp.tool()
@instrument_mcp_tool("find_task_anchors")
def find_task_anchors(issue_text: str, graph_version: str, task_id: str,
                      failing_tests: list[str] | None = None) -> dict[str, Any]:
    """Ground an issue and reported failing tests on one explicit repository snapshot."""
    def call():
        legacy_binding(graph_version=graph_version, task_id=task_id)
        return graph_service.find_task_anchors(issue_text, failing_tests, graph_version=graph_version, task_id=task_id)
    return _tool("find_task_anchors", call,
        {"graph_version": graph_version, "task_id": task_id},
        lambda data: {"anchor_count": len(data["anchors"])})


@mcp.tool()
@instrument_mcp_tool("get_related_context")
def get_related_context(anchor_ids: list[str], budget_tokens: int, graph_version: str,
                        task_id: str, issue_text: str = "", failing_tests: list[str] | None = None) -> dict[str, Any]:
    """Retrieve and pack graph context under a verified token budget; task inputs are request-local."""
    def call():
        legacy_binding(graph_version=graph_version, task_id=task_id)
        return graph_service.get_related_context(anchor_ids, budget_tokens, graph_version=graph_version,
                                                task_id=task_id, issue_text=issue_text, failing_tests=failing_tests)
    return _tool("get_related_context", call,
        {"graph_version": graph_version, "task_id": task_id, "budget_tokens": budget_tokens},
        lambda data: {"item_count": len(data["context"]["items"]),
                      "total_token_count": data["context"]["total_token_count"]})


@mcp.resource("vgar://graph/node/{node_id}")
def graph_node(node_id: str) -> str:
    return _read_resource("vgar://graph/node/" + node_id)


@mcp.tool()
@instrument_mcp_tool("get_related_tests")
def get_related_tests(symbol_ids: list[str], graph_version: str, changed_paths: list[str] | None = None,
                      failing_tests: list[str] | None = None, selected_tests: list[str] | None = None,
                      max_hops: int = 2, limit: int = 50) -> dict[str, Any]:
    """Select static test candidates; keep failing tests, fall back to supplied tests when links are absent."""
    return _tool("get_related_tests", lambda: graph_service.get_related_tests(
        symbol_ids, graph_version=graph_version, changed_paths=changed_paths, failing_tests=failing_tests,
        selected_tests=selected_tests, max_hops=max_hops, limit=limit),
        {"graph_version": graph_version, "symbol_ids": symbol_ids, "max_hops": max_hops, "limit": limit},
        lambda data: {"test_count": len(data["tests"]), "selection_mode": data["selection_mode"]})


@mcp.tool()
@instrument_mcp_tool("analyze_patch_impact")
def analyze_patch_impact(diff: str, graph_version: str, max_hops: int = 2, max_nodes: int = 200) -> dict[str, Any]:
    """Report what a unified diff changes and what depends on it.

    Walks callers, importers, subclasses and tests backwards, adds the affected Port and
    Component nodes, and reports Ports and public API removed by the patch in port_check.

    Args:
        diff: Unified diff against the snapshot's baseline source.
        graph_version: Snapshot to analyze.
        max_hops: Traversal depth, 1 to 5.
        max_nodes: Maximum impacted nodes, 1 to 1000.
    """
    patch_sha256 = "sha256:" + hashlib.sha256(diff.encode("utf-8")).hexdigest()
    def call():
        legacy_binding(graph_version=graph_version)
        return graph_service.analyze_patch_impact(diff, graph_version=graph_version, max_hops=max_hops, max_nodes=max_nodes)
    return _tool("analyze_patch_impact", call,
        {"graph_version": graph_version, "patch_sha256": patch_sha256, "max_hops": max_hops, "max_nodes": max_nodes},
        lambda data: {"changed_count": len(data["changed"]), "impacted_count": len(data["impacted"]["items"]),
                      "impacted_status": data["impacted"]["status"]})


@mcp.resource("vgar://graph/subgraph/{node_id}")
def graph_subgraph(node_id: str) -> str:
    return _read_resource("vgar://graph/subgraph/" + node_id)


@mcp.resource("vgar://graph/subgraph/{node_id}?k=2")
def graph_subgraph_canonical(node_id: str) -> str:
    return _read_resource("vgar://graph/subgraph/" + node_id + "?k=2")


@mcp.resource("vgar://repo/schema")
def repo_schema() -> str:
    return _read_resource("vgar://repo/schema")


@mcp.resource("vgar://component/{component_id}")
def component_resource(component_id: str) -> str:
    return _read_resource("vgar://component/" + component_id)


@mcp.resource("vgar://task/{task_id}")
def task_resource(task_id: str) -> str:
    return _read_resource("vgar://task/" + task_id)


@mcp.resource("vgar://evidence/baseline")
def baseline_resource() -> str:
    return _read_resource("vgar://evidence/baseline")


@mcp.resource("vgar://audit/log")
def audit_log_resource() -> str:
    return _read_resource("vgar://audit/log")


def _multihop(symbol_id, depth, direction):
    return core_tools.respond("get_" + direction, lambda: proposal_contracts.TraversalRequest(
        symbol_id=symbol_id, direction=direction, depth=depth, max_nodes=core_tools.limits.max_nodes,
        max_examined_edges=core_tools.limits.max_examined_edges), server="graph", audit=_audit_logger,
        invoke=core_tools.traverse, serialize=lambda result: {
            "symbol_id": symbol_id, "depth": depth, direction: [s.model_dump(exclude={"hop"}) for s in result.symbols],
            "traversal": result.model_dump(mode="json")})


@mcp.tool()
@instrument_mcp_tool("build_or_update_graph")
async def build_or_update_graph(repo_path: str) -> dict[str, Any]:
    """Request a graph build for exactly the host-bound repository; requires a write grant."""
    return await core_tools.respond_async("build_or_update_graph", lambda: proposal_contracts.BuildRequest(repo_path=repo_path),
                                          server="graph", audit=_audit_logger, invoke=core_tools.build)


@mcp.tool()
@instrument_mcp_tool("explain_dependency_path")
def explain_dependency_path(source_id: str, target_id: str) -> dict[str, Any]:
    """Explain a bounded typed path in the host-bound snapshot; requires a path provider."""
    return core_tools.respond("explain_dependency_path", lambda: proposal_contracts.PathRequest(
        source_id=source_id, target_id=target_id, max_hops=core_tools.limits.max_hops,
        max_nodes=core_tools.limits.max_nodes, max_examined_edges=core_tools.limits.max_examined_edges),
        server="graph", audit=_audit_logger, invoke=core_tools.path)


@mcp.tool()
@instrument_mcp_tool("verify_patch_graph_constraints")
def verify_patch_graph_constraints(diff: str) -> dict[str, Any]:
    """Return graph constraint evidence without applying/finalizing a legacy repair run."""
    return core_tools.respond("verify_patch_graph_constraints", lambda: proposal_contracts.DiffRequest.from_diff(diff),
                              server="graph", audit=_audit_logger, invoke=core_tools.verify)


@mcp.tool()
@instrument_mcp_tool("rank_patch_candidates")
def rank_patch_candidates(candidates: list[proposal_contracts.Candidate]) -> dict[str, Any]:
    """Rank bound candidates; scores never override required check failures or unknowns."""
    return core_tools.respond("rank_patch_candidates", lambda: proposal_contracts.RankRequest(candidates=tuple(candidates)),
                              server="graph", audit=_audit_logger, invoke=core_tools.rank)


@mcp.prompt()
def repair_with_graph_context(issue_text: str, failing_tests: str, context_budget: str) -> list[dict[str, Any]]:
    """Seven-step repair workflow. failing_tests is a JSON string array; context_budget is positive decimal text."""
    return _get_prompt(PROMPT_NAME, {"issue_text": issue_text, "failing_tests": failing_tests, "context_budget": context_budget})


def _get_prompt(name, arguments):
    return serve_prompt(prompt_renderer, name, arguments, _audit_logger)


def main() -> None:
    if core_tools.registry.test_only:
        raise ValueError("Synthetic registry is forbidden in production entrypoint")
    try:
        mcp.run(transport="stdio")
    finally:
        if core_tools.graph_jobs is not None:
            core_tools.graph_jobs.close()


if __name__ == "__main__":
    main()
