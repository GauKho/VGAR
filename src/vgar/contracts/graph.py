from __future__ import annotations

from typing import Any

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


class GraphRange(BaseModel):
    start_line: int | None = None
    start_col: int | None = None
    end_line: int | None = None
    end_col: int | None = None


class GraphNodeRef(BaseModel):
    node_id: str
    node_type: str
    repo_key: str
    name: str
    qualified_name: str
    path: str | None = None
    source_range: GraphRange | None = None
    content_hash: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeRef(BaseModel):
    edge_id: str
    edge_type: str
    source_id: str
    target_id: str
    confidence: float
    resolution: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class RepositorySummaryResult(BaseModel):
    graph_version: str
    repo_key: str
    repository_revision: str
    node_count: int
    edge_count: int
    node_counts_by_type: dict[str, int] = Field(default_factory=dict)
    edge_counts_by_type: dict[str, int] = Field(default_factory=dict)
    statistics: dict[str, Any] = Field(default_factory=dict)


class GraphSubgraphResult(BaseModel):
    anchor_id: str
    depth: int
    nodes: list[GraphNodeRef] = Field(default_factory=list)
    edges: list[GraphEdgeRef] = Field(default_factory=list)
