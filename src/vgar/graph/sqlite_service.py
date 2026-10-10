from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Callable, Any

from vgar.contracts.error import GraphNotReadyError
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder

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


class SQLiteGraphService:
    """M1 graph backend compatible with VGAR's GraphService Protocol."""

    backend_name = "sqlite"

    def __init__(self, store: SQLiteGraphStore, *, repository_root: str | Path | None = None,
                 count_tokens: Callable[[str], int] | None = None, counter_label: str = "") -> None:
        self.store = store
        self.repository_root = Path(repository_root).resolve() if repository_root else None
        self.count_tokens = count_tokens
        self.counter_label = counter_label

    def find_task_anchors(self, issue_text: str, failing_tests: list[str] | None = None, *,
                          graph_version: str, task_id: str) -> dict[str, Any]:
        document = self.store.load_document(graph_version)
        overlay = TaskOverlayBuilder(document).build(task_id, issue_text, failing_tests)
        return {**asdict(overlay.grounding), "task_id": task_id, "overlay_id": overlay.overlay_id,
                "trace_nodes": overlay.nodes, "trace_edges": overlay.edges}

    def get_related_context(self, anchor_ids: list[str], budget_tokens: int, *, graph_version: str,
                            task_id: str, issue_text: str = "", failing_tests: list[str] | None = None) -> dict[str, Any]:
        if self.repository_root is None or self.count_tokens is None or not self.counter_label:
            raise GraphNotReadyError("W5 retrieval requires repository root and a verified tokenizer")
        document = self.store.load_document(graph_version)
        overlay = TaskOverlayBuilder(document).build(task_id, issue_text, failing_tests)
        retriever = GraphContextRetriever(document, self.repository_root, count_tokens=self.count_tokens,
                                          counter_label=self.counter_label)
        result = retriever.retrieve(anchor_ids, budget_tokens, issue_text=issue_text, overlay=overlay)
        return {"graph_version": graph_version, "task_id": task_id, "overlay_id": overlay.overlay_id,
                "context": result.context.model_dump(mode="json"), "counter_label": result.counter_label,
                "diagnostics": {"config": result.config, "omissions": result.omissions,
                                "unavailable_features": result.unavailable_features}}

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
