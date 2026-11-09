"""Host-only immutable SQLite snapshots. No latest lookup, migration on read, or MCP tool.

The normalized SQL projection remains the legacy schema. A future schema provider
must supply a compatible storage projection as well as validation; registering a
validator alone cannot make Component/Port documents fit legacy tables.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from vgar.contracts import schema
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.proposal.context import (
    BoundContext,
    authorize_write,
    check_context,
    check_source,
    request_commit_guard,
)
from vgar.mcp.proposal.locking import locked, no_links
from vgar.mcp.proposal.security import resolve_read_path
from vgar.mcp.proposal.state import repo_guard


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _hash(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("Pinned SHA-256 required")


@dataclass(frozen=True)
class StorageIdentity:
    graph_version: str
    source_inventory_hash: str
    schema_hash: str
    resolver_hash: str
    profile_hash: str
    canonical_document_hash: str

    def __post_init__(self):
        if not isinstance(self.graph_version, str) or not self.graph_version.strip():
            raise ValueError("Explicit graph version required")
        for field, value in asdict(self).items():
            if field != "graph_version":
                _hash(value)

    @property
    def snapshot_id(self) -> str:
        return digest(canonical_bytes(asdict(self)))


@dataclass(frozen=True)
class StorageProfile:
    """Trusted bootstrap registration, never populated from model/manifest arguments.

    Validators may narrow the legacy projection, not replace its invariant checks.
    A richer SQL projection is deliberately not implemented in L6-7.
    """
    name: str
    schema_hash: str
    resolver_hash: str
    profile_hash: str
    validator: Callable[[Mapping[str, Any]], None]

    def __post_init__(self):
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.name):
            raise ValueError("Invalid storage profile name")
        for value in (self.schema_hash, self.resolver_hash, self.profile_hash):
            _hash(value)
        if not callable(self.validator):
            raise TypeError("Profile validator required")


def legacy_profile(*, resolver_hash: str, profile_hash: str) -> StorageProfile:
    return StorageProfile("legacy", digest(Path(schema.__file__).read_bytes()),
                          resolver_hash, profile_hash, schema.validate_graph_document)


class SnapshotStorage(Protocol):
    def ingest(self, document: Mapping[str, Any], *, context: BoundContext,
               profile: str = "legacy", cancel_event=None,
               request_context: BoundContext | None = None, operation_deadline: float | None = None) -> Path: ...


def _gate(context, identity, cancel_event=None):
    check_source(context)
    if context.snapshot_hash != identity.snapshot_id or context.source_hash != identity.source_inventory_hash:
        raise ValueError("Storage context/identity binding mismatch")
    if cancel_event is not None and cancel_event.is_set():
        raise ValueError("Storage request cancelled")


class _SnapshotWriter(SQLiteGraphStore):
    def __init__(self, path, identity, document_bytes, gate, context):
        super().__init__(path, graph_version=identity.graph_version)
        self.identity = identity
        self.document_bytes = document_bytes
        self.gate = gate
        self.context = context

    def _before_ready(self, connection, document):
        connection.execute("CREATE TABLE snapshot_binding (identity_json TEXT NOT NULL, document_json TEXT NOT NULL)")
        connection.execute("INSERT INTO snapshot_binding VALUES (?, ?)",
                           (canonical_bytes(asdict(self.identity)).decode(), self.document_bytes.decode()))
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Snapshot foreign key integrity failed")
        _verify_projection(connection, document)
        self.gate()

    @contextmanager
    def _connect(self):
        # New private DB only. READY and full metadata commit under the same
        # cancellation guard; publication later has its own guard.
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.set_progress_handler(lambda: _progress(self.gate), 1000)
        try:
            yield connection
            with request_commit_guard(self.context):
                self.gate()
                connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def _progress(gate):
    try:
        gate()
    except (ValueError, TimeoutError):
        return 1
    return 0


def _verify_projection(connection, document):
    """Prove that SQL facts used by queries match the preserved canonical JSON.

    Compare scalar ranges AND range_json; comparing only legacy load_document
    would miss scalar corruption. Extensions remain in the raw document only.
    This is an ingest/bind integrity scan, never a substitute for a SQL query.
    """
    connection.row_factory = sqlite3.Row
    version = document["graph_version"]
    node_columns = ("graph_version", "id", "type", "repo_key", "name", "qualified_name", "path",
                    "start_line", "start_col", "end_line", "end_col", "content_hash",
                    "properties_json", "language", "range_json")
    expected_nodes = []
    for node in document["nodes"]:
        source_range = node.get("range") or {}
        expected_nodes.append((version, node["id"], node["type"], node["repo_key"], node["name"],
                               node["qualified_name"], node.get("path"),
                               *(source_range.get(k) for k in ("start_line", "start_col", "end_line", "end_col")),
                               node.get("content_hash"), node["properties"], node.get("language"), node.get("range")))
    edge_columns = ("graph_version", "id", "type", "source_id", "target_id", "confidence",
                    "resolution", "provenance_json", "properties_json")
    expected_edges = [
        (version, e["id"], e["type"], e["source_id"], e["target_id"], e["confidence"],
         e["resolution"], e["provenance"], e["properties"]) for e in document["edges"]
    ]
    for table, columns, expected in (("nodes", node_columns, expected_nodes), ("edges", edge_columns, expected_edges)):
        rows = connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        actual = [tuple(json.loads(row[c]) if c.endswith("_json") else row[c] for c in columns) for row in rows]
        if actual != expected:
            raise ValueError("Snapshot SQL projection/document mismatch")
    rows = connection.execute("SELECT * FROM graph_metadata").fetchall()
    expected_metadata = {k: v for k, v in document.items() if k not in {"nodes", "edges"}}
    if (len(rows) != 1 or rows[0]["graph_version"] != version
            or rows[0]["repo_key"] != document["repo_key"]
            or rows[0]["repository_revision"] != document["repository_revision"]
            or json.loads(rows[0]["metadata_json"]) != expected_metadata):
        raise ValueError("Snapshot SQL metadata projection/document mismatch")


def _verify_roundtrip(database: Path, identity: StorageIdentity, raw: bytes) -> None:
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Snapshot integrity check failed")
        row = connection.execute("SELECT identity_json, document_json FROM snapshot_binding").fetchone()
        ready = connection.execute("SELECT graph_version, status FROM graph_metadata").fetchall()
        if (row is None or row[0].encode() != canonical_bytes(asdict(identity))
                or row[1].encode() != raw or ready != [(identity.graph_version, "ready")]):
            raise ValueError("Snapshot round-trip/binding/READY mismatch")
        if digest(raw) != identity.canonical_document_hash:
            raise ValueError("Snapshot canonical document mismatch")
        _verify_projection(connection, json.loads(raw))


class SQLiteSnapshotStorage:
    """Output root must preexist, be host-selected, and lie within context.output_root.

    storage_ingest grant input_hash = identity.snapshot_id, which hashes all six
    identity fields including the exact canonical document hash. The storage
    context snapshot_hash is this snapshot_id; legacy graph_version stays intact.
    """
    def __init__(self, root: str | Path, *, profiles: tuple[StorageProfile, ...]):
        self.root = no_links(root).resolve(strict=True)
        if not self.root.is_dir() or not profiles or any(type(p) is not StorageProfile for p in profiles):
            raise ValueError("Existing storage root and trusted profiles required")
        if len({p.name for p in profiles}) != len(profiles):
            raise ValueError("Duplicate storage profile")
        self._profiles = tuple(profiles)

    def _profile(self, name):
        result = next((p for p in self._profiles if p.name == name), None)
        if result is None:
            raise ValueError("Unsupported storage profile; validator/provider required")
        return result

    def identity(self, document, *, source_inventory_hash, profile="legacy") -> StorageIdentity:
        selected = self._profile(profile)
        # Copy JSON bytes first: mutation of caller's dictionaries cannot affect ingest.
        raw = canonical_bytes(document)
        frozen = json.loads(raw)
        selected.validator(frozen)
        schema.validate_graph_document(frozen)
        return StorageIdentity(frozen["graph_version"], source_inventory_hash,
                               selected.schema_hash, selected.resolver_hash,
                               selected.profile_hash, digest(raw))

    def ingest(self, document, *, context, profile="legacy", cancel_event=None,
               request_context: BoundContext | None = None, operation_deadline: float | None = None) -> Path:
        check_context(context)
        coordinator = request_context if request_context is not None else context
        check_context(coordinator)
        fields = ("authority_id", "repo_root", "lease_root", "output_root", "state_root", "request_id",
                  "run_id", "task_id", "source_hash", "config_hash", "deadline", "limits")
        if any(getattr(coordinator, key) != getattr(context, key) for key in fields):
            raise ValueError("Storage/request context binding mismatch")
        operation_end = coordinator.deadline if operation_deadline is None else operation_deadline
        if (isinstance(operation_end, bool) or not isinstance(operation_end, (int, float))
                or not math.isfinite(operation_end) or operation_end > coordinator.deadline):
            raise ValueError("Storage operation deadline must narrow request deadline")
        root = no_links(self.root).resolve(strict=True)
        if not root.is_relative_to(context.output_root) or not root.is_dir():
            raise ValueError("Storage root outside trusted output")
        raw = canonical_bytes(document)
        frozen = json.loads(raw)
        identity = self.identity(frozen, source_inventory_hash=context.source_hash, profile=profile)
        def gate():
            # Preserve the legacy expired-context ValueError; the new narrower
            # controller deadline has its own TimeoutError when context is live.
            check_context(coordinator)
            if time.time() >= operation_end:
                raise TimeoutError("Storage operation deadline exhausted")
            _gate(context, identity, cancel_event)
            check_context(coordinator)
            if time.time() >= operation_end:
                raise TimeoutError("Storage operation deadline exhausted after source validation")
        gate()
        name = identity.snapshot_id.removeprefix("sha256:")
        destination = resolve_read_path(root, name)
        with repo_guard(context, cancel_event=cancel_event), locked(
            context.state_root / "locks" / ("snapshot-" + name + ".lock"),
            timeout=context.limits.lock_seconds, deadline=context.deadline, cancel_event=cancel_event,
        ):
            gate()
            if destination.exists():
                raise ValueError("Snapshot target already exists; no overwrite or automatic orphan recovery")
            authorize_write(context, "storage_ingest", identity.snapshot_id)
            # Only this operation owns this private stage, never a historical DB.
            stage = root / (".staging-" + uuid4().hex)
            stage.mkdir(exist_ok=False)
            try:
                database = stage / "graph.db"
                writer = _SnapshotWriter(database, identity, raw, gate, coordinator)
                writer.ingest(frozen)
                gate()
                _verify_roundtrip(database, identity, raw)
                record = {"format": "vgar-sqlite-snapshot-v1", "status": "READY",
                          "snapshot_id": identity.snapshot_id, "identity": asdict(identity),
                          "profile": profile, "database": "graph.db",
                          "database_hash": digest(database.read_bytes()),
                          "binding": {"run_id": context.run_id, "task_id": context.task_id,
                                      "config_hash": context.config_hash}}
                with (stage / "manifest.json").open("xb") as stream:
                    stream.write(canonical_bytes(record)); stream.flush(); os.fsync(stream.fileno())
                with request_commit_guard(coordinator):
                    gate()
                    no_links(root)
                    no_links(destination)
                    if destination.exists():
                        raise ValueError("Snapshot target already exists")
                    # Same-volume directory rename publishes DB + manifest together.
                    # rename (not replace) refuses an existing nonempty snapshot.
                    stage.rename(destination)
                return destination / "manifest.json"
            finally:
                if stage.exists():
                    no_links(stage)
                    if stage.parent != root or not stage.name.startswith(".staging-"):
                        raise ValueError("Refusing unsafe staging cleanup")
                    # A linked descendant is an integrity failure, never traverse it.
                    for path in stage.rglob("*"):
                        no_links(path)
                    shutil.rmtree(stage)

    def unpublished_staging(self) -> tuple[Path, ...]:
        """Operator inspection only. No automatic adoption, repair, or deletion."""
        return tuple(sorted(no_links(p) for p in self.root.glob(".staging-*")))


def _file_stamp(path):
    no_links(path)
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1:
        raise ValueError("Snapshot files must be regular, unlinked files")
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _read_operation(method):
    @wraps(method)
    def read(self, *args, **kwargs):
        with self.read_transaction():
            return method(self, *args, **kwargs)
    return read


class SnapshotGraphStore(SQLiteGraphStore):
    """Pinned, read-only SQL service. Per-operation connection, reused only nested
    within that operation on the same thread. No SQLite immutable URI optimization.
    A changed file/manifest/sidecar invalidates this binding instead of rebinding.
    """
    def __init__(self, manifest: str | Path, *, graph_version: str,
                 profiles: tuple[StorageProfile, ...] | None = None):
        if not isinstance(graph_version, str) or not graph_version.strip():
            raise ValueError("Explicit graph_version required")
        try:
            self.manifest_path = no_links(manifest).resolve(strict=True)
        except FileNotFoundError:
            raise ValueError("Published snapshot manifest missing; no recovery or latest fallback") from None
        self._manifest_stamp = _file_stamp(self.manifest_path)
        record = json.loads(self.manifest_path.read_bytes())
        if record.get("format") != "vgar-sqlite-snapshot-v1" or record.get("status") != "READY":
            raise ValueError("Published READY snapshot manifest required")
        self.identity = StorageIdentity(**record["identity"])
        if not profiles or any(type(p) is not StorageProfile for p in profiles):
            raise ValueError("Reader requires trusted profiles from host bootstrap")
        if len({p.name for p in profiles}) != len(profiles):
            raise ValueError("Duplicate trusted profile")
        selected = next((p for p in profiles if p.name == record.get("profile")), None)
        if (selected is None or type(selected) is not StorageProfile
                or (selected.schema_hash, selected.resolver_hash, selected.profile_hash) != (
                    self.identity.schema_hash, self.identity.resolver_hash, self.identity.profile_hash)):
            raise ValueError("Snapshot schema/profile fingerprint unsupported or mismatched")
        if record.get("snapshot_id") != self.identity.snapshot_id or graph_version != self.identity.graph_version:
            raise ValueError("Manifest identity/version mismatch")
        if self.manifest_path.parent.name != self.identity.snapshot_id.removeprefix("sha256:"):
            raise ValueError("Unpublished or mismatched snapshot directory")
        if record.get("database") != "graph.db":
            raise ValueError("Invalid snapshot DB reference")
        database = no_links(self.manifest_path.parent / "graph.db")
        self._db_stamp = _file_stamp(database)
        _hash(record["database_hash"])
        if digest(database.read_bytes()) != record["database_hash"]:
            raise ValueError("Snapshot DB hash mismatch")
        super().__init__(database, graph_version=graph_version)
        self._local = threading.local()
        with self.read_transaction() as connection:
            row = connection.execute("SELECT identity_json, document_json FROM snapshot_binding").fetchone()
            if row is None or row[0].encode() != canonical_bytes(asdict(self.identity)):
                raise ValueError("Snapshot metadata identity mismatch")
            raw = row[1].encode()
            if digest(raw) != self.identity.canonical_document_hash:
                raise ValueError("Snapshot document hash mismatch")
            selected.validator(json.loads(raw))
            schema.validate_graph_document(json.loads(raw))
            _verify_projection(connection, json.loads(raw))

    def _unchanged(self):
        if (_file_stamp(self.manifest_path) != self._manifest_stamp
                or _file_stamp(self.database_path) != self._db_stamp):
            raise ValueError("Snapshot file identity changed; explicit rebind required")
        for suffix in ("-wal", "-shm", "-journal"):
            path = no_links(Path(str(self.database_path) + suffix))
            if path.exists():
                raise ValueError("Mutable SQLite sidecar found; snapshot is not sealed")

    @contextmanager
    def read_transaction(self):
        self._unchanged()
        current = getattr(self._local, "connection", None)
        if current is not None:
            yield current
            self._unchanged()
            return
        connection = sqlite3.connect(self.database_path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            rows = connection.execute("SELECT graph_version, status FROM graph_metadata").fetchall()
            if len(rows) != 1 or tuple(rows[0]) != (self.identity.graph_version, "ready"):
                raise ValueError("Snapshot version is not uniquely READY")
            self._local.connection = connection
            yield connection
            self._unchanged()
        finally:
            self._local.connection = None
            connection.close()

    @contextmanager
    def _connect(self):
        with self.read_transaction() as connection:
            yield connection

    def initialize(self):
        raise ValueError("Snapshot reader cannot initialize or migrate")

    def ingest(self, document):
        raise ValueError("Snapshot reader cannot write")

    def resolve_graph_version(self):
        with self.read_transaction():
            if self.requested_graph_version != self.identity.graph_version:
                raise ValueError("Pinned version mismatch")
            return self.identity.graph_version

    def load_document(self, graph_version):
        if graph_version != self.identity.graph_version:
            raise ValueError("Pinned version mismatch")
        with self.read_transaction() as connection:
            row = connection.execute("SELECT document_json FROM snapshot_binding").fetchone()
            return json.loads(row[0])

    search_symbols = _read_operation(SQLiteGraphStore.search_symbols)
    get_callers = _read_operation(SQLiteGraphStore.get_callers)
    get_callees = _read_operation(SQLiteGraphStore.get_callees)
    get_node = _read_operation(SQLiteGraphStore.get_node)
    get_repository_summary = _read_operation(SQLiteGraphStore.get_repository_summary)
    get_subgraph = _read_operation(SQLiteGraphStore.get_subgraph)
    get_importers = _read_operation(SQLiteGraphStore.get_importers)
    get_reverse_edges = _read_operation(SQLiteGraphStore.get_reverse_edges)
    find_nodes_at = _read_operation(SQLiteGraphStore.find_nodes_at)
