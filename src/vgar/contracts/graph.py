from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolRef(BaseModel):
    """A stable reference to one repository symbol."""

    symbol_id: str
    name: str
    kind: str
    path: str


class SearchSymbolsResult(BaseModel):
    query: str

    symbols: list[SymbolRef] = Field(
        default_factory=list
    )


class SymbolRelationsResult(BaseModel):
    symbol_id: str

    symbols: list[SymbolRef] = Field(
        default_factory=list
    )