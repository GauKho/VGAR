from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgar.contracts.error import (
    GraphNotReadyError,
    InvalidLimitError,
    InvalidQueryError,
    NodeNotFoundError,
)
from vgar.contracts.schema import validate_graph_document


SYMBOL_NODE_TYPES = ("Module", "Class", "Function", "Method", "Test")


@dataclass(frozen=True)
class StoredSymbol:
    symbol_id: str
    name: str
    kind: str
    path: str
    qualified_name: str


@dataclass(frozen=True)
class StoredNode:
    node_id: str
    node_type: str
    repo_key: str
    name: str
    qualified_name: str
    path: str | None
    start_line: int | None
    start_col: int | None
    end_line: int | None
    end_col: int | None
    content_hash: str | None
    properties: dict[str, Any]


@dataclass(frozen=True)
class StoredEdge:
    edge_id: str
    edge_type: str
    source_id: str
    target_id: str
    confidence: float
    resolution: str
    provenance: dict[str, Any]
    properties: dict[str, Any]


class SQLiteGraphStore:
    """SQLite persistence and read queries for the frozen graph contract."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        graph_version: str | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.requested_graph_version = graph_version

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_metadata (
                    graph_version TEXT PRIMARY KEY,
                    repo_key TEXT NOT NULL,
                    repository_revision TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('building', 'ready', 'failed')),
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    graph_version TEXT NOT NULL,
                    id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    repo_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    qualified_name TEXT NOT NULL,
                    path TEXT,
                    start_line INTEGER,
                    start_col INTEGER,
                    end_line INTEGER,
                    end_col INTEGER,
                    content_hash TEXT,
                    properties_json TEXT NOT NULL,
                    PRIMARY KEY (graph_version, id),
                    FOREIGN KEY (graph_version)
                        REFERENCES graph_metadata(graph_version)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS edges (
                    graph_version TEXT NOT NULL,
                    id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    resolution TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    PRIMARY KEY (graph_version, id),
                    FOREIGN KEY (graph_version)
                        REFERENCES graph_metadata(graph_version)
                        ON DELETE CASCADE,
                    FOREIGN KEY (graph_version, source_id)
                        REFERENCES nodes(graph_version, id),
                    FOREIGN KEY (graph_version, target_id)
                        REFERENCES nodes(graph_version, id)
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_type
                    ON nodes(graph_version, type);
                CREATE INDEX IF NOT EXISTS idx_nodes_path
                    ON nodes(graph_version, path);
                CREATE INDEX IF NOT EXISTS idx_nodes_qualified_name
                    ON nodes(graph_version, qualified_name);
                CREATE INDEX IF NOT EXISTS idx_nodes_name
                    ON nodes(graph_version, name);
                CREATE INDEX IF NOT EXISTS idx_edges_source_type
                    ON edges(graph_version, source_id, type);
                CREATE INDEX IF NOT EXISTS idx_edges_target_type
                    ON edges(graph_version, target_id, type);
                """
            )

    def ingest(self, document: Mapping[str, Any]) -> None:
        validate_graph_document(document)
        self.initialize()

        graph_version = str(document["graph_version"])
        nodes = document["nodes"]
        edges = document["edges"]

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM graph_metadata WHERE graph_version = ?",
                (graph_version,),
            ).fetchone()
            if existing is not None:
                raise ValueError(f"graph version already exists: {graph_version}")

            connection.execute(
                """
                INSERT INTO graph_metadata (
                    graph_version,
                    repo_key,
                    repository_revision,
                    status,
                    metadata_json
                ) VALUES (?, ?, ?, 'building', ?)
                """,
                (
                    graph_version,
                    document["repo_key"],
                    document["repository_revision"],
                    json.dumps(
                        {
                            key: value
                            for key, value in document.items()
                            if key not in {"nodes", "edges"}
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )

            for node in nodes:
                source_range = node.get("range") or {}
                connection.execute(
                    """
                    INSERT INTO nodes (
                        graph_version, id, type, repo_key, name,
                        qualified_name, path, start_line, start_col,
                        end_line, end_col, content_hash, properties_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        graph_version,
                        node["id"],
                        node["type"],
                        node["repo_key"],
                        node["name"],
                        node["qualified_name"],
                        node.get("path"),
                        source_range.get("start_line"),
                        source_range.get("start_col"),
                        source_range.get("end_line"),
                        source_range.get("end_col"),
                        node.get("content_hash"),
                        json.dumps(
                            node["properties"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )

            for edge in edges:
                connection.execute(
                    """
                    INSERT INTO edges (
                        graph_version, id, type, source_id, target_id,
                        confidence, resolution, provenance_json,
                        properties_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        graph_version,
                        edge["id"],
                        edge["type"],
                        edge["source_id"],
                        edge["target_id"],
                        edge["confidence"],
                        edge["resolution"],
                        json.dumps(
                            edge["provenance"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        json.dumps(
                            edge["properties"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )

            connection.execute(
                """
                UPDATE graph_metadata
                SET status = 'ready'
                WHERE graph_version = ?
                """,
                (graph_version,),
            )

    def search_symbols(self, query: str, limit: int) -> list[StoredSymbol]:
        normalized_query = query.strip()
        if not normalized_query:
            raise InvalidQueryError("query must not be empty")
        if not 1 <= limit <= 100:
            raise InvalidLimitError("limit must be within [1, 100]")

        graph_version = self.resolve_graph_version()
        pattern = f"%{_escape_like(normalized_query)}%"
        placeholders = ", ".join("?" for _ in SYMBOL_NODE_TYPES)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, name, type, path, qualified_name
                FROM nodes
                WHERE graph_version = ?
                  AND type IN ({placeholders})
                  AND (
                      name LIKE ? ESCAPE '\\' COLLATE NOCASE
                      OR qualified_name LIKE ? ESCAPE '\\' COLLATE NOCASE
                      OR path LIKE ? ESCAPE '\\' COLLATE NOCASE
                  )
                ORDER BY
                    CASE
                        WHEN name = ? COLLATE NOCASE THEN 0
                        WHEN qualified_name = ? COLLATE NOCASE THEN 1
                        ELSE 2
                    END,
                    qualified_name,
                    id
                LIMIT ?
                """,
                (
                    graph_version,
                    *SYMBOL_NODE_TYPES,
                    pattern,
                    pattern,
                    pattern,
                    normalized_query,
                    normalized_query,
                    limit,
                ),
            ).fetchall()

        return [_row_to_symbol(row) for row in rows]

    def get_callers(
        self,
        symbol_id: str,
        *,
        min_confidence: float = 0.60,
    ) -> list[StoredSymbol]:
        _validate_confidence_threshold(min_confidence)
        graph_version = self.resolve_graph_version()
        self._require_symbol(graph_version, symbol_id)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT caller.id, caller.name, caller.type,
                       caller.path, caller.qualified_name
                FROM edges AS call_edge
                JOIN edges AS contains_edge
                  ON contains_edge.graph_version = call_edge.graph_version
                 AND contains_edge.type = 'CONTAINS'
                 AND contains_edge.target_id = call_edge.source_id
                JOIN nodes AS caller
                  ON caller.graph_version = contains_edge.graph_version
                 AND caller.id = contains_edge.source_id
                WHERE call_edge.graph_version = ?
                  AND call_edge.type = 'CALLS'
                  AND call_edge.target_id = ?
                  AND call_edge.confidence >= ?
                  AND caller.type IN ('Function', 'Method', 'Test')
                ORDER BY caller.qualified_name, caller.id
                """,
                (graph_version, symbol_id, min_confidence),
            ).fetchall()

        return [_row_to_symbol(row) for row in rows]

    def get_callees(
        self,
        symbol_id: str,
        *,
        min_confidence: float = 0.60,
    ) -> list[StoredSymbol]:
        _validate_confidence_threshold(min_confidence)
        graph_version = self.resolve_graph_version()
        self._require_symbol(graph_version, symbol_id)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT callee.id, callee.name, callee.type,
                       callee.path, callee.qualified_name
                FROM edges AS contains_edge
                JOIN edges AS call_edge
                  ON call_edge.graph_version = contains_edge.graph_version
                 AND call_edge.type = 'CALLS'
                 AND call_edge.source_id = contains_edge.target_id
                JOIN nodes AS callee
                  ON callee.graph_version = call_edge.graph_version
                 AND callee.id = call_edge.target_id
                WHERE contains_edge.graph_version = ?
                  AND contains_edge.type = 'CONTAINS'
                  AND contains_edge.source_id = ?
                  AND call_edge.confidence >= ?
                  AND callee.type IN ('Class', 'Function', 'Method')
                ORDER BY callee.qualified_name, callee.id
                """,
                (graph_version, symbol_id, min_confidence),
            ).fetchall()

        return [_row_to_symbol(row) for row in rows]

    def get_node(self, node_id: str) -> StoredNode:
        graph_version = self.resolve_graph_version()
        if not node_id:
            raise ValueError("node_id must not be empty")

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, type, repo_key, name, qualified_name, path,
                       start_line, start_col, end_line, end_col,
                       content_hash, properties_json
                FROM nodes
                WHERE graph_version = ? AND id = ?
                """,
                (graph_version, node_id),
            ).fetchone()

        if row is None:
            raise NodeNotFoundError(node_id, entity="node")
        return StoredNode(
            node_id=str(row["id"]),
            node_type=str(row["type"]),
            repo_key=str(row["repo_key"]),
            name=str(row["name"]),
            qualified_name=str(row["qualified_name"]),
            path=str(row["path"]).replace("\\", "/") if row["path"] else None,
            start_line=row["start_line"],
            start_col=row["start_col"],
            end_line=row["end_line"],
            end_col=row["end_col"],
            content_hash=row["content_hash"],
            properties=json.loads(row["properties_json"]),
        )

    def get_repository_summary(self) -> dict[str, Any]:
        graph_version = self.resolve_graph_version()
        with self._connect() as connection:
            metadata_row = connection.execute(
                """
                SELECT repo_key, repository_revision, metadata_json
                FROM graph_metadata
                WHERE graph_version = ? AND status = 'ready'
                """,
                (graph_version,),
            ).fetchone()
            if metadata_row is None:
                raise GraphNotReadyError(graph_version)

            node_rows = connection.execute(
                """
                SELECT type, COUNT(*) AS count
                FROM nodes
                WHERE graph_version = ?
                GROUP BY type
                ORDER BY type
                """,
                (graph_version,),
            ).fetchall()
            edge_rows = connection.execute(
                """
                SELECT type, COUNT(*) AS count
                FROM edges
                WHERE graph_version = ?
                GROUP BY type
                ORDER BY type
                """,
                (graph_version,),
            ).fetchall()

        metadata = json.loads(metadata_row["metadata_json"])
        node_counts = {str(row["type"]): int(row["count"]) for row in node_rows}
        edge_counts = {str(row["type"]): int(row["count"]) for row in edge_rows}
        statistics = dict(metadata.get("statistics") or {})
        return {
            "graph_version": graph_version,
            "repo_key": str(metadata_row["repo_key"]),
            "repository_revision": str(metadata_row["repository_revision"]),
            "node_count": sum(node_counts.values()),
            "edge_count": sum(edge_counts.values()),
            "node_counts_by_type": node_counts,
            "edge_counts_by_type": edge_counts,
            "statistics": statistics,
        }

    def get_subgraph(
        self,
        node_id: str,
        *,
        depth: int = 2,
        limit: int = 200,
    ) -> tuple[list[StoredNode], list[StoredEdge]]:
        if depth < 0 or depth > 5:
            raise ValueError("depth must be within [0, 5]")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be within [1, 1000]")

        graph_version = self.resolve_graph_version()
        self.get_node(node_id)

        visited: set[str] = {node_id}
        frontier: set[str] = {node_id}
        edge_rows_by_id: dict[str, sqlite3.Row] = {}

        with self._connect() as connection:
            for _ in range(depth):
                if not frontier or len(visited) >= limit:
                    break
                placeholders = ", ".join("?" for _ in frontier)
                params = (graph_version, *sorted(frontier), *sorted(frontier))
                rows = connection.execute(
                    f"""
                    SELECT id, type, source_id, target_id, confidence,
                           resolution, provenance_json, properties_json
                    FROM edges
                    WHERE graph_version = ?
                      AND (
                          source_id IN ({placeholders})
                          OR target_id IN ({placeholders})
                      )
                    ORDER BY id
                    """,
                    params,
                ).fetchall()

                next_frontier: set[str] = set()
                for row in rows:
                    edge_rows_by_id[str(row["id"])] = row
                    for endpoint in (str(row["source_id"]), str(row["target_id"])):
                        if endpoint not in visited and len(visited) < limit:
                            visited.add(endpoint)
                            next_frontier.add(endpoint)
                frontier = next_frontier

            placeholders = ", ".join("?" for _ in visited)
            node_rows = connection.execute(
                f"""
                SELECT id, type, repo_key, name, qualified_name, path,
                       start_line, start_col, end_line, end_col,
                       content_hash, properties_json
                FROM nodes
                WHERE graph_version = ? AND id IN ({placeholders})
                ORDER BY id
                """,
                (graph_version, *sorted(visited)),
            ).fetchall()

        nodes = [_row_to_node(row) for row in node_rows]
        edges = [_row_to_edge(row) for row in edge_rows_by_id.values()]
        edges = [edge for edge in edges if edge.source_id in visited and edge.target_id in visited]
        edges.sort(key=lambda item: item.edge_id)
        return nodes, edges

    def get_importers(self, module_id: str) -> list[StoredSymbol]:
        graph_version = self.resolve_graph_version()
        module = self.get_node(module_id)
        if module.node_type != "Module":
            raise ValueError("get_importers requires a Module node_id")

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT source_module.id, source_module.name,
                       source_module.type, source_module.path,
                       source_module.qualified_name
                FROM edges AS import_edge
                JOIN edges AS contains_edge
                  ON contains_edge.graph_version = import_edge.graph_version
                 AND contains_edge.type = 'CONTAINS'
                 AND contains_edge.target_id = import_edge.source_id
                JOIN nodes AS source_module
                  ON source_module.graph_version = contains_edge.graph_version
                 AND source_module.id = contains_edge.source_id
                WHERE import_edge.graph_version = ?
                  AND import_edge.type = 'IMPORTS'
                  AND import_edge.target_id = ?
                  AND source_module.type = 'Module'
                ORDER BY source_module.qualified_name, source_module.id
                """,
                (graph_version, module_id),
            ).fetchall()

        return [_row_to_symbol(row) for row in rows]

    def resolve_graph_version(self) -> str:
        self.initialize()
        with self._connect() as connection:
            if self.requested_graph_version:
                row = connection.execute(
                    """
                    SELECT graph_version
                    FROM graph_metadata
                    WHERE graph_version = ? AND status = 'ready'
                    """,
                    (self.requested_graph_version,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT graph_version
                    FROM graph_metadata
                    WHERE status = 'ready'
                    ORDER BY rowid DESC
                    LIMIT 1
                    """
                ).fetchone()

        if row is None:
            requested = self.requested_graph_version or "latest-ready"
            raise GraphNotReadyError(requested)
        return str(row["graph_version"])

    def _require_symbol(self, graph_version: str, symbol_id: str) -> None:
        if not symbol_id:
            raise ValueError("symbol_id must not be empty")

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM nodes
                WHERE graph_version = ? AND id = ?
                """,
                (graph_version, symbol_id),
            ).fetchone()

        if row is None:
            raise NodeNotFoundError(symbol_id, entity="symbol")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def load_graph_document(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        document = json.load(file)
    if not isinstance(document, dict):
        raise ValueError("graph document root must be an object")
    return document


def _row_to_node(row: sqlite3.Row) -> StoredNode:
    return StoredNode(
        node_id=str(row["id"]),
        node_type=str(row["type"]),
        repo_key=str(row["repo_key"]),
        name=str(row["name"]),
        qualified_name=str(row["qualified_name"]),
        path=str(row["path"]).replace("\\", "/") if row["path"] else None,
        start_line=row["start_line"],
        start_col=row["start_col"],
        end_line=row["end_line"],
        end_col=row["end_col"],
        content_hash=row["content_hash"],
        properties=json.loads(row["properties_json"]),
    )


def _row_to_edge(row: sqlite3.Row) -> StoredEdge:
    return StoredEdge(
        edge_id=str(row["id"]),
        edge_type=str(row["type"]),
        source_id=str(row["source_id"]),
        target_id=str(row["target_id"]),
        confidence=float(row["confidence"]),
        resolution=str(row["resolution"]),
        provenance=json.loads(row["provenance_json"]),
        properties=json.loads(row["properties_json"]),
    )


def _row_to_symbol(row: sqlite3.Row) -> StoredSymbol:
    path = row["path"]
    if not isinstance(path, str) or not path:
        raise ValueError(f"symbol has no repository-relative path: {row['id']}")
    return StoredSymbol(
        symbol_id=str(row["id"]),
        name=str(row["name"]),
        kind=str(row["type"]).lower(),
        path=path.replace("\\", "/"),
        qualified_name=str(row["qualified_name"]),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _validate_confidence_threshold(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("min_confidence must be a number")
    if not 0.0 <= value <= 1.0:
        raise ValueError("min_confidence must be within [0, 1]")
