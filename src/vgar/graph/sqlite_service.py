from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from vgar.contracts.error import GraphNotReadyError, InvalidLimitError, InvalidQueryError

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

    def __init__(self, store: SQLiteGraphStore, *, source_root=None, tokenizer_manifest=None,
                 count_tokens=None, counter_label=None, allow_fallback_counter=False) -> None:
        self.store = store
        self.source_root = Path(source_root).resolve() if source_root is not None else None
        self.tokenizer_manifest = tokenizer_manifest
        self.count_tokens, self.counter_label = count_tokens, counter_label
        self.allow_fallback_counter = allow_fallback_counter

    def find_task_anchors(self, issue_text: str, failing_tests: list[str] | None = None) -> dict:
        from vgar.graph.task_overlay import TaskOverlayBuilder
        if not isinstance(issue_text, str) or not issue_text.strip() or len(issue_text.encode("utf-8")) > 65536:
            raise InvalidQueryError("issue_text must be nonempty and at most 64 KiB")
        if failing_tests is not None and (not isinstance(failing_tests, list) or len(failing_tests) > 100
                or any(not isinstance(value, str) or not value or len(value.encode("utf-8")) > 8192 for value in failing_tests)):
            raise InvalidQueryError("failing_tests must contain at most 100 nonempty bounded reports")
        document = self.store.get_graph_document()
        task = {"graph_version": document["graph_version"], "issue_text": issue_text, "failing_tests": sorted(set(failing_tests or []))}
        digest = hashlib.sha256(json.dumps(task, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        handle = "vgar-task:" + digest
        overlay = TaskOverlayBuilder(document).build(handle, issue_text, task["failing_tests"])
        anchors = [a.node_id for a in overlay.grounding.anchors]
        task["anchor_ids"] = anchors
        self.store.put_task_context(handle, task)
        return {"task_handle": handle, "graph_version": document["graph_version"], "anchor_ids": anchors,
                **asdict(overlay.grounding)}

    def get_related_context(self, anchor_ids: list[str], budget_tokens: int, task_handle: str):
        from vgar.graph.retrieval import GraphContextRetriever
        from vgar.graph.task_overlay import TaskOverlayBuilder
        if not isinstance(task_handle, str) or not re.fullmatch(r"vgar-task:[0-9a-f]{64}", task_handle):
            raise InvalidQueryError("A task_handle returned by find_task_anchors is required")
        if not isinstance(anchor_ids, list) or any(not isinstance(item, str) for item in anchor_ids):
            raise InvalidQueryError("anchor_ids must be a list of node IDs")
        if isinstance(budget_tokens, bool) or not isinstance(budget_tokens, int) or budget_tokens < 1:
            raise InvalidLimitError("budget_tokens must be a positive integer")
        task = self.store.get_task_context(task_handle)
        core = {key: task[key] for key in ("graph_version", "issue_text", "failing_tests")}
        expected = "vgar-task:" + hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if task_handle != expected:
            raise InvalidQueryError("Task context integrity hash mismatch")
        document = self.store.get_graph_document()
        if task["graph_version"] != document["graph_version"]:
            raise GraphNotReadyError(task["graph_version"])
        overlay = TaskOverlayBuilder(document).build(task_handle, task["issue_text"], task["failing_tests"])
        if [anchor.node_id for anchor in overlay.grounding.anchors] != task["anchor_ids"]:
            raise InvalidQueryError("Task context anchor integrity mismatch")
        if set(anchor_ids) - set(task["anchor_ids"]):
            raise InvalidQueryError("Anchors must belong to the supplied task handle")
        if self.source_root is None:
            raise GraphNotReadyError(document["graph_version"] + ": host source root is not bound")
        counter, label = self.count_tokens, self.counter_label
        if counter is None and self.tokenizer_manifest is not None:
            from vgar.graph.token_counter import LocalTokenizerCounter
            counter = LocalTokenizerCounter(self.tokenizer_manifest)
            label = counter.counter_label
        if counter is None and self.allow_fallback_counter:
            from vgar.evaluation.retrieval.scoring import bytes_div4_counter, FALLBACK_COUNTER_LABEL
            counter, label = bytes_div4_counter, FALLBACK_COUNTER_LABEL
        if counter is None or label is None:
            raise GraphNotReadyError(document["graph_version"] + ": pinned tokenizer is not bound")
        return GraphContextRetriever(document, self.source_root, count_tokens=counter, counter_label=label).retrieve(
            anchor_ids, budget_tokens, issue_text=task["issue_text"], overlay=overlay)

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
