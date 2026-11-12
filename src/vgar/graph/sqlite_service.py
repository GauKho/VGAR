from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Any

from vgar.contracts.error import GraphNotReadyError, NodeNotFoundError
from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig, ranking_config_hash
from vgar.graph.task_overlay import TaskOverlayBuilder
from vgar.graph.test_selection import select_related_tests
from vgar.contracts.prompt_context import CONTEXT_FORMAT
from vgar.observability.graph_trace import GraphTrace

from vgar.contracts.graph import (
    GraphEdgeRef,
    GraphNodeRef,
    GraphNodeRepo,
    GraphSubgraphResult,
    RepositorySummaryResult,
    SearchSymbolsResult,
    SymbolRef,
    SymbolRelationsResult,
)
from vgar.graph.sqlite_store import (
    SQLiteGraphStore,
    StoredEdge,
    StoredNode,
    StoredSymbol,
)


logger = logging.getLogger(__name__)

_SYMBOL_OWNERS = frozenset({"Function", "Method", "Test"})
# Directed edges a dependency path may follow; a call is CONTAINS (owner -> CallSite) then CALLS.
_PATH_EDGES = frozenset({"CALLS", "MAY_CALL", "IMPORTS", "DEPENDS_ON", "CONTAINS", "HAS_METHOD", "HAS_CALLSITE"})


class SQLiteGraphService:
    """M1 graph backend compatible with VGAR's GraphService Protocol."""

    backend_name = "sqlite"

    def __init__(self, store: SQLiteGraphStore, *, repository_root: str | Path | None = None,
                 count_tokens: Callable[[str], int] | None = None, counter_label: str = "") -> None:
        self.store = store
        self.repository_root = Path(repository_root).resolve() if repository_root else None
        self.count_tokens = count_tokens
        self.counter_label = counter_label
        self._documents: dict[str, dict[str, Any]] = {}
        self._retrievers: dict[tuple[str, str], GraphContextRetriever] = {}
        self._tasks: dict[str, dict[str, Any]] = {}

    def _document(self, graph_version: str) -> dict[str, Any]:
        """The stored graph of ``graph_version``, loaded from SQLite once and reused (read-only).

        Args:
            graph_version: Stored graph snapshot to read.
        """
        if graph_version not in self._documents:
            self._documents[graph_version] = self.store.load_document(graph_version)
        return self._documents[graph_version]

    def get_related_tests(self, symbol_ids: list[str], *, graph_version: str,
                          changed_paths: list[str] | None = None, failing_tests: list[str] | None = None,
                          selected_tests: list[str] | None = None, max_hops: int = 2, limit: int = 50) -> dict[str, Any]:
        return select_related_tests(self._document(graph_version), symbol_ids, changed_paths=changed_paths,
                                    failing_tests=failing_tests, selected_tests=selected_tests, max_hops=max_hops, limit=limit)

    def find_task_anchors(self, issue_text: str, failing_tests: list[str] | None = None, *,
                          graph_version: str, task_id: str) -> dict[str, Any]:
        document = self._document(graph_version)
        overlay = TaskOverlayBuilder(document).build(task_id, issue_text, failing_tests)
        result = {**asdict(overlay.grounding), "task_id": task_id, "overlay_id": overlay.overlay_id,
                  "trace_nodes": overlay.nodes, "trace_edges": overlay.edges}
        self._tasks[task_id] = result
        return result

    def get_related_context(self, anchor_ids: list[str], budget_tokens: int, *, graph_version: str,
                            task_id: str, issue_text: str = "", failing_tests: list[str] | None = None,
                            config: RetrievalConfig | None = None, use_history: bool = False,
                            history_commits: int = 50) -> dict[str, Any]:
        """Pack source-verified context around anchors for one task.

        Args:
            anchor_ids: Graph node ids to start from.
            budget_tokens: Token budget for the packed context.
            graph_version: Stored graph snapshot to read.
            task_id: Task identifier used for the task overlay.
            issue_text: Issue text used for grounding and ranking.
            failing_tests: Optional failing test selectors.
            config: Optional ranking config; None keeps the default ``RetrievalConfig()``.
            use_history: Add the commit-history signal (``recent_change_frequency``) read from the
                graph's own revision backwards; off by default so results stay unchanged.
            history_commits: Number of first-parent commits in the history window.
        """
        if self.repository_root is None or self.count_tokens is None or not self.counter_label:
            raise GraphNotReadyError("W5 retrieval requires repository root and a verified tokenizer")
        document = self._document(graph_version)
        overlay = TaskOverlayBuilder(document).build(task_id, issue_text, failing_tests)
        history = self._history(document, history_commits) if use_history else None
        label = history["label"] if history and history["available"] else None
        key = (graph_version, ranking_config_hash(config or RetrievalConfig()), label or "")
        retriever = self._retrievers.get(key)
        if retriever is None:
            retriever = GraphContextRetriever(document, self.repository_root, count_tokens=self.count_tokens,
                                              counter_label=self.counter_label, config=config,
                                              change_counts=history["counts"] if label else None, history_label=label)
            self._retrievers[key] = retriever
        try:
            result = retriever.retrieve(anchor_ids, budget_tokens, issue_text=issue_text, overlay=overlay)
        except Exception as error:
            retriever.trace.emit("retrieval_error", graph_version=graph_version, task_id=task_id,
                                 error_type=type(error).__name__, reason=str(error))
            raise
        return {"graph_version": graph_version, "task_id": task_id, "overlay_id": overlay.overlay_id,
                "context_format": CONTEXT_FORMAT, "repository_revision": document["repository_revision"],
                "source_metadata": {item.node_id: {"content_hash": retriever.nodes[item.node_id]["content_hash"],
                                                    "range_encoding": "utf-8-bytes"} for item in result.context.items},
                "context": result.context.model_dump(mode="json"), "counter_label": result.counter_label,
                "diagnostics": {"config": result.config, "omissions": result.omissions,
                                "unavailable_features": result.unavailable_features,
                                "candidates": result.candidates, "traversal_limited": result.traversal_limited,
                                **({"history": {key: value for key, value in history.items() if key != "counts"}}
                                   if history is not None else {})}}

    def _history(self, document: dict[str, Any], max_commits: int) -> dict[str, Any]:
        """Commit-history window ending at the graph's own revision; never reads commits after the snapshot."""
        revision = document["repository_revision"]
        try:
            from vgar.graph.history import read_commit_history
            window = read_commit_history(self.repository_root, revision=revision, max_commits=max_commits)
        except Exception as error:  # noqa: BLE001 - missing dulwich, non-SHA revision or missing objects
            logger.warning("Commit history unavailable for %s: %s", revision, type(error).__name__)
            return {"available": False, "label": None, "paths": [], "counts": None, "reason": type(error).__name__}
        counts = window.change_counts
        return {"available": True, "label": window.history_label, "paths": sorted(counts), "counts": counts}

    def traverse(self, symbol_id: str, direction: str, depth: int, max_nodes: int = 200) -> dict[str, Any]:
        """Callers or callees up to ``depth`` hops; MAY_CALL targets are listed apart from CALLS results.

        Each hop uses the same query as ``get_callers``/``get_callees``, so hop 1 equals the direct result.

        Args:
            symbol_id: Graph node id of a function, method, class or test.
            direction: ``"callers"`` or ``"callees"``.
            depth: Number of hops to follow, at least 1.
            max_nodes: Maximum symbols returned; stopping early sets ``truncated``.
        """
        if direction not in {"callers", "callees"}:
            raise ValueError("direction must be 'callers' or 'callees'")
        if type(depth) is not int or depth < 1 or type(max_nodes) is not int or max_nodes < 1:
            raise ValueError("depth and max_nodes must be positive integers")
        step = self.store.get_callers if direction == "callers" else self.store.get_callees
        may_call = self._may_call_index(self.store.resolve_graph_version())[direction]
        seen, frontier = {symbol_id}, [symbol_id]
        symbols: list[dict[str, Any]] = []
        possible: list[dict[str, Any]] = []
        possible_seen: set[str] = set()
        examined, truncated = 0, False
        for hop in range(1, depth + 1):
            following = []
            for current in frontier:
                for symbol in step(current):
                    examined += 1
                    if symbol.symbol_id in seen:
                        continue
                    if len(symbols) >= max_nodes:
                        truncated = True
                        break
                    seen.add(symbol.symbol_id)
                    following.append(symbol.symbol_id)
                    symbols.append({"symbol_id": symbol.symbol_id, "name": symbol.name, "kind": symbol.kind,
                                    "path": symbol.path, "hop": hop, "via": current})
                for target, confidence in may_call.get(current, ()):
                    if target not in seen and target not in possible_seen:
                        possible_seen.add(target)
                        possible.append({"symbol_id": target, "hop": hop, "via": current, "confidence": confidence})
                if truncated:
                    break
            frontier = following
            if truncated or not frontier:
                break
        possible = [item for item in possible if item["symbol_id"] not in seen]
        return {"symbol_id": symbol_id, "direction": direction, "depth": depth, "symbols": symbols,
                "may_call": possible, "truncated": truncated, "examined": examined}

    def _may_call_index(self, graph_version: str) -> dict[str, dict[str, list[tuple[str, float]]]]:
        document = self._document(graph_version)
        kinds = {node["id"]: node["type"] for node in document["nodes"]}
        owner = {edge["target_id"]: edge["source_id"] for edge in document["edges"]
                 if edge["type"] == "CONTAINS" and kinds.get(edge["source_id"]) in _SYMBOL_OWNERS}
        index: dict[str, dict[str, list[tuple[str, float]]]] = {"callees": {}, "callers": {}}
        for edge in sorted(document["edges"], key=lambda item: item["id"]):
            caller = owner.get(edge["source_id"])
            if edge["type"] != "MAY_CALL" or caller is None:
                continue
            index["callees"].setdefault(caller, []).append((edge["target_id"], edge["confidence"]))
            index["callers"].setdefault(edge["target_id"], []).append((caller, edge["confidence"]))
        return index

    def explain_dependency_path(self, source_id: str, target_id: str, max_hops: int = 6,
                                max_nodes: int = 200) -> dict[str, Any]:
        """Shortest directed path between two graph nodes over typed dependency edges.

        Args:
            source_id: Graph node id where the path starts.
            target_id: Graph node id where the path ends.
            max_hops: Maximum number of edges on the path (one call is CONTAINS then CALLS).
            max_nodes: Maximum nodes visited before giving up; giving up sets ``truncated``.
        """
        if type(max_hops) is not int or max_hops < 1 or type(max_nodes) is not int or max_nodes < 1:
            raise ValueError("max_hops and max_nodes must be positive integers")
        document = self._document(self.store.resolve_graph_version())
        known = {node["id"] for node in document["nodes"]}
        for node_id in (source_id, target_id):
            if node_id not in known:
                raise NodeNotFoundError(node_id)
        outgoing: dict[str, list[dict[str, Any]]] = {}
        for edge in document["edges"]:
            if edge["type"] in _PATH_EDGES:
                outgoing.setdefault(edge["source_id"], []).append(edge)
        for edges in outgoing.values():
            edges.sort(key=lambda item: (item["type"], item["target_id"], item["id"]))
        previous: dict[str, dict[str, Any] | None] = {source_id: None}
        queue, examined, truncated = deque([(source_id, 0)]), 0, False
        while queue and target_id not in previous:
            node_id, hops = queue.popleft()
            if hops == max_hops:
                truncated = truncated or bool(outgoing.get(node_id))
                continue
            for edge in outgoing.get(node_id, ()):
                examined += 1
                if edge["target_id"] in previous:
                    continue
                if len(previous) >= max_nodes:
                    truncated = True
                    queue.clear()
                    break
                previous[edge["target_id"]] = edge
                queue.append((edge["target_id"], hops + 1))
        if target_id not in previous:
            return {"source_id": source_id, "target_id": target_id, "found": False, "nodes": [], "edges": [],
                    "examined_edges": examined, "truncated": truncated}
        path, node_id = [], target_id
        while previous[node_id] is not None:
            edge = previous[node_id]
            path.append({"edge_id": edge["id"], "edge_type": edge["type"], "source_id": edge["source_id"],
                         "target_id": edge["target_id"], "confidence": edge["confidence"]})
            node_id = edge["source_id"]
        path.reverse()
        return {"source_id": source_id, "target_id": target_id, "found": True,
                "nodes": [source_id] + [edge["target_id"] for edge in path], "edges": path,
                "examined_edges": examined, "truncated": False}

    def get_schema(self) -> dict[str, Any]:
        """The schema S (SC-1) as plain data, for ``vgar://repo/schema``."""
        from vgar.contracts.schema import schema_description
        return schema_description()

    def get_component(self, component_id: str) -> dict[str, Any]:
        """One G_arch component with the fields of the proposal's ``vgar://component/Auth`` example.

        Args:
            component_id: Component node id, or the component's name when that name is unique.
        """
        document = self._document(self.store.resolve_graph_version())
        by_id = {node["id"]: node for node in document["nodes"]}
        components = [node for node in document["nodes"] if node["type"] == "Component"]
        component = by_id.get(component_id)
        if component is None or component["type"] != "Component":
            named = [node for node in components if node["name"] == component_id]
            if len(named) != 1:
                raise NodeNotFoundError(component_id, entity="component")
            component = named[0]
        own = component["id"]
        ports, dependencies, dependents = [], set(), set()
        for edge in document["edges"]:
            if edge["type"] == "EXPOSES_PORT" and edge["source_id"] == own:
                ports.append(by_id[edge["target_id"]]["qualified_name"])
            elif edge["type"] == "DEPENDS_ON" and edge["source_id"] == own:
                dependencies.add(by_id[edge["target_id"]]["name"])
            elif edge["type"] == "DEPENDS_ON" and edge["target_id"] == own:
                dependents.add(by_id[edge["source_id"]]["name"])
        properties = component.get("properties", {})
        coupling = properties.get("coupling")
        risk = ("high_fanin" if len(dependents) >= 3
                else "high_coupling" if isinstance(coupling, (int, float)) and coupling >= 1.0 else None)
        return {"component": component["name"], "files": list(properties.get("files", [])),
                "public_ports": sorted(ports), "dependencies": sorted(dependencies), "dependents": sorted(dependents),
                "tests": list(properties.get("tests", [])), "risk": risk}

    def get_task(self, task_id: str) -> dict[str, Any]:
        """The task graph built by the last ``find_task_anchors`` call for ``task_id``.

        Args:
            task_id: Task identifier passed to ``find_task_anchors``.
        """
        if task_id not in self._tasks:
            raise GraphNotReadyError("Call find_task_anchors for this task first")
        return self._tasks[task_id]

    def get_baseline(self) -> dict[str, Any]:
        """Graph part of the baseline evidence; test and invariant evidence belong to layer 5 and are not run here."""
        from collections import Counter

        from vgar.contracts.schema import SCHEMA_VERSION
        graph_version = self.store.resolve_graph_version()
        document = self._document(graph_version)
        return {"graph_version": graph_version, "schema_version": SCHEMA_VERSION,
                "node_counts": dict(sorted(Counter(node["type"] for node in document["nodes"]).items())),
                "edge_counts": dict(sorted(Counter(edge["type"] for edge in document["edges"]).items())),
                "tests": "NOT_RUN", "invariants": "NOT_RUN"}

    def search_symbols(self, query: str, limit: int = 20) -> SearchSymbolsResult:
        symbols = self.store.search_symbols(query, limit)
        return SearchSymbolsResult(query=query, symbols=[_to_symbol_contract(s) for s in symbols])

    def get_callers(self, symbol_id: str) -> SymbolRelationsResult:
        symbols = self.store.get_callers(symbol_id)
        return SymbolRelationsResult(symbol_id=symbol_id, symbols=[_to_symbol_contract(s) for s in symbols])

    def get_callees(self, symbol_id: str) -> SymbolRelationsResult:
        symbols = self.store.get_callees(symbol_id)
        return SymbolRelationsResult(symbol_id=symbol_id, symbols=[_to_symbol_contract(s) for s in symbols])

    def get_repository_summary(self) -> RepositorySummaryResult:
        return RepositorySummaryResult.model_validate(self.store.get_repository_summary())

    def get_node(self, node_id: str) -> GraphNodeRef:
        return _to_node_contract(self.store.get_node(node_id))

    def get_subgraph(self, node_id: str, *, depth: int = 2, limit: int = 200) -> GraphSubgraphResult:
        nodes, edges = self.store.get_subgraph(node_id, depth=depth, limit=limit)
        return GraphSubgraphResult(
            anchor_id=node_id,
            depth=depth,
            nodes=[_to_node_contract(node) for node in nodes],
            edges=[_to_edge_contract(edge) for edge in edges],
        )

    def get_importers(self, module_id: str) -> SymbolRelationsResult:
        symbols = self.store.get_importers(module_id)
        return SymbolRelationsResult(symbol_id=module_id, symbols=[_to_symbol_contract(s) for s in symbols])

    def analyze_patch_impact(self, diff: str, *, graph_version: str, max_hops: int = 2,
                             max_nodes: int = 200) -> dict[str, Any]:
        """ImpactReport (canonical JSON object) of a unified diff against the snapshot's baseline source."""
        if self.repository_root is None:
            raise GraphNotReadyError("Patch impact requires the repository root of the snapshot")
        from vgar.graph.impact import analyze_patch_impact
        from vgar.repair.patch import PatchPolicy
        document = self._document(graph_version)
        paths = tuple(sorted(node["path"] for node in document["nodes"] if node["type"] == "File"))
        report = analyze_patch_impact(diff, document, self.repository_root, patch_policy=PatchPolicy(paths, ()),
                                      max_hops=max_hops, max_nodes=max_nodes)
        return json.loads(report.canonical_json())

    def get_reverse_edges(self, node_ids: list[str], edge_types: list[str]) -> list[GraphEdgeRef]:
        return [_to_edge_contract(edge) for edge in self.store.get_reverse_edges(node_ids, edge_types)]

    def find_nodes_at(self, path: str, line: int) -> list[GraphNodeRef]:
        return [_to_node_contract(node) for node in self.store.find_nodes_at(path, line)]


def _to_symbol_contract(symbol: StoredSymbol) -> SymbolRef:
    return SymbolRef(symbol_id=symbol.symbol_id, name=symbol.name, kind=symbol.kind, path=symbol.path)


def _to_node_contract(node: StoredNode) -> GraphNodeRef:
    # Keep M1's builder/SQLite schema unchanged and adapt only at the frozen
    # VGAR boundary. Source-backed nodes are syntactically extracted by
    # tree-sitter; SQLite is persistence, not provenance.
    provenance = "tree-sitter" if node.path is not None else "graph-builder"
    return GraphNodeRef(
        repo=GraphNodeRepo(
            node_id=node.node_id,
            type=node.node_type,
            path=node.path,
            start_line=node.start_line,
            start_col=node.start_col,
            end_line=node.end_line,
            end_col=node.end_col,
            confidence=1.0,
            provenance=provenance,
            metadata={
                "repo_key": node.repo_key,
                "name": node.name,
                "qualified_name": node.qualified_name,
                "content_hash": node.content_hash,
                "properties": node.properties,
            },
        )
    )


def _to_edge_contract(edge: StoredEdge) -> GraphEdgeRef:
    return GraphEdgeRef(
        edge_id=edge.edge_id, edge_type=edge.edge_type, source_id=edge.source_id,
        target_id=edge.target_id, confidence=edge.confidence, resolution=edge.resolution,
        provenance=edge.provenance, properties=edge.properties,
    )
