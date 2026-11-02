"""M1-W11-1 incremental graph update: re-extract only changed files, re-link the whole repository.

Each update's document equals ``PythonGraphBuilder.build`` on the same source (G3). Extraction results are cached
per file; every link phase runs over the whole repository exactly as in a full build, so name-index effects across
files (a name losing uniqueness, re-exports, aliases) need no dependency tracking. Complexity: parsing is O(changed
files), linking is O(repository). Static resolver only; the cache lives in memory.
Design: docs/superpowers/specs/2026-11-01-m1-w11-incremental-design.md
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vgar.contracts.schema import validate_graph_document
from vgar.graph.builder import RESOLVER_PROFILE, PythonGraphBuilder

_INDEXES = ("symbols_by_qualified_name", "scope_tables", "scope_parents", "unmodified_parameters", "typed_parameters")


@dataclass(frozen=True)
class UpdateSummary:
    changed_files: tuple[str, ...]
    added_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    cache_hits: int
    total_files: int
    extract_seconds: float
    validate_seconds: float
    total_seconds: float
    affected_node_count: int = 0


@dataclass
class _FileRecord:
    """Everything one ``_extract_file`` call contributed, taken before any link phase ran."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    calls: list[Any]
    classes: list[Any]
    index_writes: list[tuple[str, str, Any]]
    module: tuple[str, Any] | None
    overload_delta: int
    duplicate_delta: int
    failed_files: list[dict[str, str]] = field(default_factory=list)


def _copy(item: dict[str, Any]) -> dict[str, Any]:
    # Link phases mutate top-level ``properties`` keys (aliases, import status); keep cached items pristine.
    return {**item, "properties": dict(item["properties"])}


def affected_node_count(previous: dict[str, Any] | None, current: dict[str, Any]) -> int:
    """U1 "nodes affected": added/removed nodes plus endpoints of edges present in only one document.

    Edges are compared by (type, source_id, target_id). Reporting only; never drives the update.
    """
    if previous is None:
        return len(current["nodes"])
    before, after = ({node["id"] for node in doc["nodes"]} for doc in (previous, current))
    edges_before, edges_after = ({(e["type"], e["source_id"], e["target_id"]) for e in doc["edges"]}
                                 for doc in (previous, current))
    affected = before ^ after
    for _, source, target in edges_before ^ edges_after:
        affected.update((source, target))
    return len(affected)


class _CachingGraphBuilder(PythonGraphBuilder):
    """A single-use full builder whose extraction and alias parsing read from / fill a shared cache."""

    def __init__(self, files: dict[tuple[str, str, str], _FileRecord], aliases: dict[tuple[str, str], list[tuple[str, str, dict]]],
                 digests: dict[str, str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._files, self._aliases, self._digests = files, aliases, digests
        self._capture: list[tuple[str, str, Any]] | None = None
        self.trusted_ids: set[str] = set()
        self.cache_hits = 0
        self.extract_seconds = 0.0
        self.validate_seconds = 0.0

    def _set_index(self, index: dict, key: str, value: Any) -> None:
        if self._capture is not None:
            name = next(name for name in _INDEXES if getattr(self, name) is index)
            self._capture.append((name, key, value))
        super()._set_index(index, key, value)

    def _extract_file(self, root: Path, file_path: Path, repository_id: str) -> None:
        started = time.perf_counter()
        relative = file_path.relative_to(root).as_posix()
        key = (relative, self._digests[relative], RESOLVER_PROFILE)
        record = self._files.get(key)
        if record is None:
            record = self._extract_and_record(root, file_path, repository_id, relative)
            self._files[key] = record
        else:
            self.cache_hits += 1
            self._replay(record)
        self.extract_seconds += time.perf_counter() - started

    def _extract_and_record(self, root: Path, file_path: Path, repository_id: str, relative: str) -> _FileRecord:
        sizes = (len(self.nodes), len(self.edges), len(self.calls), len(self.classes), len(self.skipped_failed_files))
        counters = (self.skipped_overload_count, self.renamed_duplicate_count)
        module_name = self._module_name(relative)
        module_before = self.modules.get(module_name)
        self._capture = []
        try:
            super()._extract_file(root, file_path, repository_id)
        finally:
            writes, self._capture = self._capture, None
        module_after = self.modules.get(module_name)
        return _FileRecord(
            nodes=[_copy(node) for node in self.nodes[sizes[0]:]],
            edges=list(self.edges[sizes[1]:]),  # link phases never mutate extraction edges
            calls=self.calls[sizes[2]:], classes=self.classes[sizes[3]:], index_writes=writes,
            module=(module_name, module_after) if module_after is not module_before else None,
            overload_delta=self.skipped_overload_count - counters[0],
            duplicate_delta=self.renamed_duplicate_count - counters[1],
            failed_files=[dict(entry) for entry in self.skipped_failed_files[sizes[4]:]])

    def _replay(self, record: _FileRecord) -> None:
        # The only cross-file read during extraction: the Repository->File edge ordinal is len(self.modules)
        # at the moment the file is reached (builder.py, rule repository.file.v1). Recompute it here.
        file_ordinal = len(self.modules)
        version = self.graph_version
        for node in record.nodes:
            copied = _copy(node)
            copied["graph_version"] = version
            self.nodes.append(copied)
            self.trusted_ids.add(copied["id"])
        for edge in record.edges:
            copied = {**edge, "graph_version": version}
            if edge["provenance"]["rule_id"] == "repository.file.v1":
                copied["properties"] = {**edge["properties"], "ordinal": file_ordinal}
            self.edges.append(copied)
            self.trusted_ids.add(copied["id"])
        for node in self.nodes[len(self.nodes) - len(record.nodes):]:
            self.nodes_by_id[node["id"]] = node
        self.calls.extend(record.calls)
        self.classes.extend(record.classes)
        for name, key, value in record.index_writes:
            getattr(self, name)[key] = value
        if record.module is not None:
            self.modules[record.module[0]] = record.module[1]
        self.skipped_overload_count += record.overload_delta
        self.renamed_duplicate_count += record.duplicate_delta
        self.skipped_failed_files.extend(dict(entry) for entry in record.failed_files)

    def _alias_candidates(self, root: Path, path: str, symbols: list[dict[str, Any]]) -> list[tuple[str, str, dict]]:
        key = (path, self._digests[path])
        if key not in self._aliases:
            self._aliases[key] = super()._alias_candidates(root, path, symbols)
        return self._aliases[key]

    def _validate(self, document: dict[str, Any]) -> None:
        started = time.perf_counter()
        validate_graph_document(document, trusted_ids=frozenset(self.trusted_ids))
        self.validate_seconds = time.perf_counter() - started


class IncrementalGraphBuilder:
    """Keeps per-file extraction results across updates of one repository snapshot lineage."""

    def __init__(self, repo_key: str, repository_revision: str, *, source_roots: tuple[str, ...] = ("src",),
                 scip: Any = None, lsp: Any = None) -> None:
        if scip is not None or lsp is not None:
            raise ValueError("incremental update supports the static resolver only; run a full build")
        self._options = {"repo_key": repo_key, "repository_revision": repository_revision, "source_roots": source_roots}
        self._files: dict[tuple[str, str, str], _FileRecord] = {}
        self._aliases: dict[tuple[str, str], list[tuple[str, str, dict]]] = {}
        self._digests: dict[str, str] = {}
        self._document: dict[str, Any] | None = None

    def build(self, root: str | Path) -> dict[str, Any]:
        """First build (or rebuild from an empty cache)."""
        self._files.clear()
        self._aliases.clear()
        self._digests, self._document = {}, None
        return self.update(root)[0]

    def update(self, root: str | Path) -> tuple[dict[str, Any], UpdateSummary]:
        started = time.perf_counter()
        root = Path(root).resolve()
        builder = _CachingGraphBuilder(self._files, self._aliases, {}, **self._options)
        paths = [path.relative_to(root).as_posix() for path in builder._discover_python_files(root)]
        digests = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
        builder._digests = digests
        previous = self._digests
        changed = tuple(sorted(path for path in digests if path in previous and previous[path] != digests[path]))
        added = tuple(sorted(set(digests) - set(previous)))
        deleted = tuple(sorted(set(previous) - set(digests)))
        live = {(path, digest, RESOLVER_PROFILE) for path, digest in digests.items()}
        for key in [key for key in self._files if key not in live]:
            del self._files[key]
        for key in [key for key in self._aliases if (key[0], key[1], RESOLVER_PROFILE) not in live]:
            del self._aliases[key]
        document = builder.build(root)
        total = time.perf_counter() - started
        summary = UpdateSummary(changed_files=changed, added_files=added, deleted_files=deleted,
                                cache_hits=builder.cache_hits, total_files=len(paths),
                                extract_seconds=builder.extract_seconds, validate_seconds=builder.validate_seconds,
                                total_seconds=total,
                                affected_node_count=affected_node_count(self._document, document))
        self._digests, self._document = digests, document
        return document, summary
