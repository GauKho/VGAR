from __future__ import annotations

from vgar.contracts.graph import (
    GraphEdgeRef,
    GraphNodeRef,
    GraphSubgraphResult,
    RepositorySummaryResult,
    SearchSymbolsResult,
    SymbolRef,
    SymbolRelationsResult,
)


class DemoGraphService:
    """Deterministic fallback backend used for transport smoke tests."""

    backend_name = "demo"

    def __init__(self) -> None:
        self._symbols = [
            SymbolRef(symbol_id="function:auth.login", name="login", kind="function", path="src/auth/service.py"),
            SymbolRef(symbol_id="function:web.login_handler", name="login_handler", kind="function", path="src/web/routes.py"),
            SymbolRef(symbol_id="function:auth.validate_token", name="validate_token", kind="function", path="src/auth/token.py"),
        ]
        self._calls = {
            "function:web.login_handler": ["function:auth.login"],
        }

    def search_symbols(self, query: str, limit: int = 20) -> SearchSymbolsResult:
        normalized = query.lower().strip()
        matches = [s for s in self._symbols if normalized in s.name.lower() or normalized in s.symbol_id.lower() or normalized in s.path.lower()]
        return SearchSymbolsResult(query=query, symbols=matches[:limit])

    def get_callers(self, symbol_id: str) -> SymbolRelationsResult:
        caller_ids = [caller for caller, callees in self._calls.items() if symbol_id in callees]
        return SymbolRelationsResult(symbol_id=symbol_id, symbols=[self._find(item) for item in caller_ids])

    def get_callees(self, symbol_id: str) -> SymbolRelationsResult:
        return SymbolRelationsResult(symbol_id=symbol_id, symbols=[self._find(item) for item in self._calls.get(symbol_id, [])])

    def get_repository_summary(self) -> RepositorySummaryResult:
        return RepositorySummaryResult(
            graph_version="demo-v1", repo_key="demo", repository_revision="demo",
            node_count=len(self._symbols), edge_count=sum(len(v) for v in self._calls.values()),
            node_counts_by_type={"Function": len(self._symbols)},
            edge_counts_by_type={"CALLS": sum(len(v) for v in self._calls.values())},
            statistics={"backend": "demo"},
        )

    def get_node(self, node_id: str) -> GraphNodeRef:
        symbol = self._find(node_id)
        return GraphNodeRef(
            node_id=symbol.symbol_id, node_type="Function", repo_key="demo",
            name=symbol.name, qualified_name=symbol.symbol_id, path=symbol.path,
            properties={},
        )

    def get_subgraph(self, node_id: str, *, depth: int = 2, limit: int = 200) -> GraphSubgraphResult:
        self._find(node_id)
        visited = {node_id}
        frontier = {node_id}
        edge_refs: list[GraphEdgeRef] = []
        for hop in range(depth):
            next_frontier: set[str] = set()
            for caller, callees in self._calls.items():
                for callee in callees:
                    if caller in frontier or callee in frontier:
                        edge_refs.append(GraphEdgeRef(
                            edge_id=f"demo:call:{caller}->{callee}", edge_type="CALLS",
                            source_id=caller, target_id=callee, confidence=1.0, resolution="demo",
                        ))
                        for endpoint in (caller, callee):
                            if endpoint not in visited and len(visited) < limit:
                                visited.add(endpoint); next_frontier.add(endpoint)
            frontier = next_frontier
            if not frontier:
                break
        nodes = [self.get_node(item) for item in sorted(visited)]
        unique_edges = {edge.edge_id: edge for edge in edge_refs}
        return GraphSubgraphResult(anchor_id=node_id, depth=depth, nodes=nodes, edges=list(unique_edges.values()))

    def _find(self, symbol_id: str) -> SymbolRef:
        for symbol in self._symbols:
            if symbol.symbol_id == symbol_id:
                return symbol
        raise KeyError(f"Unknown symbol: {symbol_id}")
