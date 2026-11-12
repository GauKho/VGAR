from __future__ import annotations

import hashlib
import logging
import threading

import anyio
import os
from contextlib import nullcontext
from pathlib import Path
from types import MappingProxyType
from typing import Any

from vgar.contracts.error import GraphError
from vgar.graph.factory import create_graph_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal import contracts as proposal_contracts
from vgar.mcp.proposal.context import current_context, request_scope
from vgar.mcp.proposal.locking import no_links
from vgar.mcp.proposal.ports import ProviderRegistry
from vgar.mcp.proposal.prompts import (
    PROMPT_NAME,
    PromptRenderer,
    audit_protocol_reject,
    serve_prompt,
)
from vgar.mcp.proposal.resources import ResourceReader
from vgar.mcp.proposal.tools import CoreTools, legacy_binding
from vgar.mcp.logging_setup import configure_server_logging, server_log_level
from vgar.mcp.schemas import PATH_OUTSIDE_ROOT, ROOT_NOT_LEASED, CodedToolError
from vgar.mcp.server_factory import create_resource_server
from vgar.mcp.tooling import PYTEST_OUTPUT_CAP, PYTEST_TIMEOUT_SECONDS, audit_resource, run_tool
from vgar.observability.instrumentation import instrument_mcp_tool

# Run as `python -m`, __name__ is "__main__"; keep the module name so the vgar log handler applies.
logger = logging.getLogger("vgar.mcp.servers.graph_server" if __name__ == "__main__" else __name__)

mcp = create_resource_server("vgar-graph", lambda uri: _read_resource(uri), log_level=server_log_level(),
                             prompt_reader=lambda name, arguments: _get_prompt(name, arguments),
                             protocol_reject=lambda: audit_protocol_reject(_audit_logger))
try:
    graph_service = create_graph_service()
except Exception as error:
    configure_server_logging()  # the error must reach the host's log before the process exits
    logger.error("vgar-graph cannot start: %s", error, exc_info=True)
    raise
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
    """Return the functions that call a symbol, following up to ``depth`` caller hops.

    Args:
        symbol_id: Graph node id of the function, method, class or test.
        depth: Number of caller hops; 1 returns direct callers. Possible callers through
            unresolved calls (MAY_CALL) are listed separately in ``may_call`` when depth > 1.
    """

    if type(depth) is int and depth > 1:
        return _multihop(symbol_id, depth, "callers") if _has_provider("traversal") else _traverse(symbol_id, depth, "callers")
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
    """Return the functions a symbol calls, following up to ``depth`` callee hops.

    Args:
        symbol_id: Graph node id of the function, method, class or test.
        depth: Number of callee hops; 1 returns direct callees. Possible callees through
            unresolved calls (MAY_CALL) are listed separately in ``may_call`` when depth > 1.
    """

    if type(depth) is int and depth > 1:
        return _multihop(symbol_id, depth, "callees") if _has_provider("traversal") else _traverse(symbol_id, depth, "callees")
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


def _diff_hash(diff: str) -> str:
    return "sha256:" + hashlib.sha256(diff.encode("utf-8")).hexdigest()


_verify_cache: dict[str, dict[str, Any]] = {}
_test_cache: dict[str, dict[str, Any]] = {}


def _cache_key(diff: str) -> tuple[str, str]:
    return graph_service.get_repository_summary().graph_version, _diff_hash(diff)


def _verified(diff: str) -> dict[str, Any]:
    """verify_patch result for ``diff`` on the served snapshot, computed once per (snapshot, diff)."""
    from vgar.repair.patch_evidence import verify_patch
    version, key = _cache_key(diff)
    if (version, key) not in _verify_cache:
        _verify_cache[(version, key)] = verify_patch(graph_service, diff, graph_version=version)
    return _verify_cache[(version, key)]


def _tested(diff: str) -> dict[str, Any]:
    """run_patch_tests result for ``diff`` on the served snapshot, computed once per (snapshot, diff)."""
    from vgar.repair.patch_evidence import run_patch_tests
    version, key = _cache_key(diff)
    if (version, key) not in _test_cache:
        _test_cache[(version, key)] = run_patch_tests(graph_service, diff, graph_version=version,
                                                      timeout_seconds=PYTEST_TIMEOUT_SECONDS, output_cap=PYTEST_OUTPUT_CAP)
    return _test_cache[(version, key)]


def _has_provider(capability: str) -> bool:
    """True when the host registered a provider for ``capability``; otherwise the guide-style path serves it."""
    return core_tools.registry.get(capability) is not None


def _traverse(symbol_id, depth, direction):
    def call() -> dict[str, Any]:
        legacy_binding()
        result = graph_service.traverse(symbol_id, direction, depth, max_nodes=core_tools.limits.max_nodes)
        return {"symbol_id": symbol_id, "depth": depth, direction: result["symbols"],
                "may_call": result["may_call"], "truncated": result["truncated"]}

    return _tool("get_" + direction, call, {"symbol_id": symbol_id, "depth": depth},
                 lambda data: {"result_count": len(data[direction]), "truncated": data["truncated"]})


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
    """Build the graph of the configured repository, or update it after edits. This tool WRITES the graph.

    Call it once before the other tools on a new repository, and again after changing code: later calls
    re-extract only the changed files (incremental update), and every read tool sees the new graph at once.

    Args:
        repo_path: The repository root this server is configured for (VGAR_REPOSITORY_ROOT); any other path is refused.
    """
    if _trusted_build_host():  # host with a trusted build provider, job controller or bound context (TV1, L6-6)
        return await core_tools.respond_async("build_or_update_graph",
                                              lambda: proposal_contracts.BuildRequest(repo_path=repo_path),
                                              server="graph", audit=_audit_logger, invoke=core_tools.build)

    def call() -> dict[str, Any]:
        return _live().run()

    def checked() -> dict[str, Any]:
        _same_repository(repo_path)
        return call()

    # Building can take minutes on a large repository: run it off the event loop (build-server guide).
    return await anyio.to_thread.run_sync(lambda: _tool(
        "build_or_update_graph", checked, {"repo_path_sha256": _diff_hash(repo_path)},
        lambda data: {"mode": data["mode"], "graph_version": data["graph_version"],
                      "changed_files": len(data["changed_files"])}))


def _trusted_build_host() -> bool:
    """True when TV1's trusted path owns builds: a registered build provider, a graph job controller or a host context."""
    return (_has_provider("build") or core_tools.graph_jobs is not None
            or core_tools.context_factory is not None or current_context() is not None)


_live_builder = None
_live_lock = threading.Lock()


def _live():
    """The process-wide LiveGraphBuilder for the configured repository and database (created on first use)."""
    global _live_builder
    with _live_lock:
        if _live_builder is None:
            from vgar.graph.live_build import LiveGraphBuilder
            root, database = os.getenv("VGAR_REPOSITORY_ROOT", "").strip(), os.getenv("VGAR_GRAPH_DATABASE", "").strip()
            if not root or not database:
                raise CodedToolError(ROOT_NOT_LEASED, "VGAR_REPOSITORY_ROOT and VGAR_GRAPH_DATABASE must be configured")
            _live_builder = LiveGraphBuilder(Path(root), Path(database),
                                             timeout_seconds=float(os.getenv("VGAR_GRAPH_BUILD_TIMEOUT_SECONDS", "900")))
        return _live_builder


def _same_repository(repo_path: str) -> None:
    """Path jail (proposal §10.5): only the configured repository may be built; links are refused."""
    configured = os.getenv("VGAR_REPOSITORY_ROOT", "").strip()
    if not configured:
        raise CodedToolError(ROOT_NOT_LEASED, "VGAR_REPOSITORY_ROOT is not configured")
    try:
        requested = no_links(Path(repo_path)).resolve(strict=True)
        root = no_links(Path(configured)).resolve(strict=True)
    except (OSError, ValueError):
        raise CodedToolError(PATH_OUTSIDE_ROOT, "repo_path is not the configured repository") from None
    if os.path.normcase(str(requested)) != os.path.normcase(str(root)):
        raise CodedToolError(PATH_OUTSIDE_ROOT, "repo_path is not the configured repository")


@mcp.tool()
@instrument_mcp_tool("explain_dependency_path")
def explain_dependency_path(source_id: str, target_id: str) -> dict[str, Any]:
    """Explain how one symbol depends on another: the shortest typed edge path between them.

    Args:
        source_id: Graph node id where the path starts.
        target_id: Graph node id where the path ends.
    """
    if not _has_provider("path"):
        def call() -> dict[str, Any]:
            legacy_binding()
            return graph_service.explain_dependency_path(source_id, target_id, max_nodes=core_tools.limits.max_nodes)

        return _tool("explain_dependency_path", call, {"source_id": source_id, "target_id": target_id},
                     lambda data: {"found": data["found"], "edge_count": len(data["edges"])})
    return core_tools.respond("explain_dependency_path", lambda: proposal_contracts.PathRequest(
        source_id=source_id, target_id=target_id, max_hops=core_tools.limits.max_hops,
        max_nodes=core_tools.limits.max_nodes, max_examined_edges=core_tools.limits.max_examined_edges),
        server="graph", audit=_audit_logger, invoke=core_tools.path)


@mcp.tool()
@instrument_mcp_tool("verify_patch_graph_constraints")
async def verify_patch_graph_constraints(diff: str) -> dict[str, Any]:
    """Check a proposed patch against the graph: schema, structure, public API, import cycles and lost Ports.

    The repository is never modified; the patch is checked on a temporary copy.

    Args:
        diff: Unified diff against the served snapshot's source.
    """
    if not _has_provider("verification"):
        def call() -> dict[str, Any]:
            legacy_binding()
            return _verified(diff)

        # Building the candidate graph is slow: run it off the event loop (build-server guide: stay responsive).
        return await anyio.to_thread.run_sync(lambda: _tool(
            "verify_patch_graph_constraints", call, {"diff_sha256": _diff_hash(diff)},
            lambda data: {"verdict": data["status"], "reason_count": len(data["reasons"])}))
    return core_tools.respond("verify_patch_graph_constraints", lambda: proposal_contracts.DiffRequest.from_diff(diff),
                              server="graph", audit=_audit_logger, invoke=core_tools.verify)


@mcp.tool()
@instrument_mcp_tool("rank_patch_candidates")
async def rank_patch_candidates(candidates: list[proposal_contracts.Candidate]) -> dict[str, Any]:
    """Rank candidate patches by their evidence: eligible patches first, then score(patch).

    A high score never lifts a patch whose required check failed. Patches not yet verified or
    tested are checked first (on temporary copies; the repository is never modified).

    Args:
        candidates: Candidate patches, each with ``candidate_id``, ``diff`` and ``diff_hash``.
    """
    if not _has_provider("ranking"):
        def call() -> dict[str, Any]:
            legacy_binding()
            from vgar.repair.patch_evidence import load_ranking_weights, rank_candidates
            items = [{"candidate_id": item.candidate_id, "diff": item.diff} for item in candidates]
            verify = {_diff_hash(item["diff"]): _verified(item["diff"]) for item in items}
            tests = {_diff_hash(item["diff"]): _tested(item["diff"]) for item in items}
            return rank_candidates(items, verify_results=verify, test_results=tests, weights=load_ranking_weights())

        # Ranking may verify and test each candidate: run it off the event loop.
        return await anyio.to_thread.run_sync(lambda: _tool(
            "rank_patch_candidates", call, {"candidate_count": len(candidates)},
            lambda data: {"ranked": len(data["ranking"]), "eligible": sum(row["eligible"] for row in data["ranking"])}))
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
    configure_server_logging()
    if logger.isEnabledFor(logging.INFO):
        from importlib.metadata import version
        try:
            graph_version = graph_service.get_repository_summary().graph_version
        except GraphError:  # no graph yet: the agent builds it with build_or_update_graph
            graph_version = "not built"
        logger.info("server=vgar-graph mcp=%s backend=%s database=%s graph_version=%s repository_root=%s",
                    version("mcp"), os.getenv("VGAR_GRAPH_BACKEND", "sqlite"), os.getenv("VGAR_GRAPH_DATABASE"),
                    graph_version, os.getenv("VGAR_REPOSITORY_ROOT"))
    try:
        mcp.run(transport="stdio")
    finally:
        if core_tools.graph_jobs is not None:
            core_tools.graph_jobs.close()


if __name__ == "__main__":
    main()
