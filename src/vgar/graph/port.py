from __future__ import annotations

from typing import Protocol

from vgar.contracts.graph import (
    SearchSymbolsResult,
    SymbolRelationsResult,
)


class GraphService(Protocol):
    """
    Interface M1's graph implementation must satisfy.
    """

    def search_symbols(
        self,
        query: str,
        limit: int = 20,
    ) -> SearchSymbolsResult:
        ...

    def get_callers(
        self,
        symbol_id: str,
    ) -> SymbolRelationsResult:
        ...

    def get_callees(
        self,
        symbol_id: str,
    ) -> SymbolRelationsResult:
        ...