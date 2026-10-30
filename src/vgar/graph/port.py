from __future__ import annotations

from typing import Protocol, Any

from vgar.contracts.graph import (
    GraphNodeRef,
    GraphSubgraphResult,
    RepositorySummaryResult,
    SearchSymbolsResult,
    SymbolRelationsResult,
)


class GraphService(Protocol):
    """Storage-agnostic graph API exposed to the MCP layer."""

    @property
    def backend_name(self) -> str:
        ...

    def search_symbols(
        self,
        query: str,
        limit: int = 20,
    ) -> SearchSymbolsResult:
        ...

    def find_task_anchors(self, issue_text: str, failing_tests: list[str] | None = None, *,
                          graph_version: str, task_id: str) -> dict[str, Any]:
        ...

    def get_related_context(self, anchor_ids: list[str], budget_tokens: int, *, graph_version: str,
                            task_id: str, issue_text: str = "", failing_tests: list[str] | None = None) -> dict[str, Any]:
        ...

    def get_callers(
        self,
        symbol_id: str,
    ) -> SymbolRelationsResult:
        ...

    def get_related_tests(self, symbol_ids: list[str], *, graph_version: str,
                          changed_paths: list[str] | None = None, failing_tests: list[str] | None = None,
                          selected_tests: list[str] | None = None, max_hops: int = 2, limit: int = 50) -> dict[str, Any]:
        ...

    def get_callees(
        self,
        symbol_id: str,
    ) -> SymbolRelationsResult:
        ...

    def analyze_patch_impact(self, diff: str, *, graph_version: str, max_hops: int = 2,
                             max_nodes: int = 200) -> dict[str, Any]:
        ...

    def get_repository_summary(self) -> RepositorySummaryResult:
        ...

    def get_node(self, node_id: str) -> GraphNodeRef:
        ...

    def get_subgraph(
        self,
        node_id: str,
        *,
        depth: int = 2,
        limit: int = 200,
    ) -> GraphSubgraphResult:
        ...
