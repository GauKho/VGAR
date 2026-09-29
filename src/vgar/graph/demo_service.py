from __future__ import annotations

from vgar.contracts.graph import (
    SearchSymbolsResult,
    SymbolRef,
    SymbolRelationsResult,
)


class DemoGraphService:
    """
    Temporary deterministic implementation.

    Only used to validate:
        GraphService -> MCP -> LangChain

    Replace with M1's real GraphService later.
    """

    def __init__(self) -> None:
        self._symbols = [
            SymbolRef(
                symbol_id="function:auth.login",
                name="login",
                kind="function",
                path="src/auth/service.py",
            ),
            SymbolRef(
                symbol_id="function:web.login_handler",
                name="login_handler",
                kind="function",
                path="src/web/routes.py",
            ),
            SymbolRef(
                symbol_id="function:auth.validate_token",
                name="validate_token",
                kind="function",
                path="src/auth/token.py",
            ),
        ]

    def search_symbols(
        self,
        query: str,
        limit: int = 20,
    ) -> SearchSymbolsResult:
        query_normalized = query.lower().strip()

        matches = [
            symbol
            for symbol in self._symbols
            if (
                query_normalized in symbol.name.lower()
                or query_normalized in symbol.symbol_id.lower()
                or query_normalized in symbol.path.lower()
            )
        ]

        return SearchSymbolsResult(
            query=query,
            symbols=matches[:limit],
        )

    def get_callers(
        self,
        symbol_id: str,
    ) -> SymbolRelationsResult:
        callers: list[SymbolRef] = []

        if symbol_id == "function:auth.login":
            callers.append(
                self._find(
                    "function:web.login_handler"
                )
            )

        return SymbolRelationsResult(
            symbol_id=symbol_id,
            symbols=callers,
        )

    def get_callees(
        self,
        symbol_id: str,
    ) -> SymbolRelationsResult:
        callees: list[SymbolRef] = []

        if symbol_id == "function:web.login_handler":
            callees.append(
                self._find(
                    "function:auth.login"
                )
            )

        return SymbolRelationsResult(
            symbol_id=symbol_id,
            symbols=callees,
        )

    def _find(
        self,
        symbol_id: str,
    ) -> SymbolRef:
        for symbol in self._symbols:
            if symbol.symbol_id == symbol_id:
                return symbol

        raise KeyError(
            f"Unknown symbol: {symbol_id}"
        )