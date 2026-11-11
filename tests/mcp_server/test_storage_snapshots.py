"""Independent synthetic graph oracle; no tracked DB is opened for writing."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parents[1] / "fixtures/graph_contract_fixture.json"
HASH = "sha256:" + "b" * 64


def trusted_profiles(m):
    return (m.legacy_profile(resolver_hash=HASH, profile_hash="sha256:" + "a" * 64),)


def api():
    assert importlib.util.find_spec("vgar.graph.storage_capabilities"), "L6-7 snapshot capability missing"
    from vgar.graph import storage_capabilities
    return storage_capabilities


@pytest.fixture
def storage(bound):
    from vgar.mcp.proposal.context import bind_context
    m = api()
    authority, ctx = bound
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["extension"] = {"unicode": "đồ thị", "nested": [1, None]}
    document["nodes"][0]["extension"] = {"preserve": True}
    profile = m.legacy_profile(resolver_hash=HASH, profile_hash=ctx.config_hash)
    capability = m.SQLiteSnapshotStorage(ctx.output_root, profiles=(profile,))
    identity = capability.identity(document, source_inventory_hash=ctx.source_hash)
    ctx = bind_context(authority, repo_root=ctx.repo_root, lease_root=ctx.lease_root,
                       output_root=ctx.output_root, request_id=ctx.request_id,
                       run_id=ctx.run_id, task_id=ctx.task_id,
                       snapshot_hash=identity.snapshot_id, source_hash=ctx.source_hash,
                       config_hash=ctx.config_hash, deadline=ctx.deadline)
    ctx = authority.grant(ctx, "storage_ingest", identity.snapshot_id)
    return m, authority, ctx, document, capability, identity


def test_storage_module_is_available():
    api()


def test_roundtrip_preserves_all_fields_and_queries_sql(storage):
    m, _, ctx, doc, cap, identity = storage
    manifest = cap.ingest(doc, context=ctx)
    store = m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    assert store.identity == identity
    assert store.load_document(doc["graph_version"]) == doc
    assert store.resolve_graph_version() == doc["graph_version"]
    assert store.get_node(doc["nodes"][0]["id"]).name == doc["nodes"][0]["name"]
    before = store.database_path.read_bytes()
    with store._connect() as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(Exception, match="readonly"):
            connection.execute("DELETE FROM nodes")
    store.get_repository_summary()
    assert store.database_path.read_bytes() == before


def test_identity_changes_for_every_fingerprint(storage):
    _, _, _, _, _, identity = storage
    for field in ("source_inventory_hash", "schema_hash", "resolver_hash", "profile_hash", "canonical_document_hash"):
        assert replace(identity, **{field: "sha256:" + "c" * 64}).snapshot_id != identity.snapshot_id


@pytest.mark.parametrize("fault", ["missing_grant", "wrong_snapshot", "wrong_source", "wrong_hash"])
def test_unauthorized_has_no_operation_output(storage, fault):
    _, authority, ctx, doc, cap, _ = storage
    if fault in ("missing_grant", "wrong_hash"):
        ctx = authority._sign(replace(ctx, grants=()))
        if fault == "wrong_hash":
            ctx = authority.grant(ctx, "storage_ingest", HASH)
    elif fault == "wrong_snapshot":
        ctx = authority._sign(replace(ctx, snapshot_hash=HASH))
    else:
        (ctx.repo_root / "changed.py").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError):
        cap.ingest(doc, context=ctx)
    assert list(ctx.output_root.iterdir()) == []


def test_replay_and_existing_target_never_overwrite(storage):
    _, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    before = {p.name: p.read_bytes() for p in manifest.parent.iterdir()}
    with pytest.raises(ValueError):
        cap.ingest(doc, context=ctx)
    assert {p.name: p.read_bytes() for p in manifest.parent.iterdir()} == before


@pytest.mark.parametrize("fault", ["duplicate", "endpoint", "profile"])
def test_invalid_document_or_profile_before_write(storage, fault):
    _, _, ctx, doc, cap, _ = storage
    if fault == "duplicate":
        doc["nodes"].append(copy.deepcopy(doc["nodes"][0]))
    elif fault == "endpoint":
        doc["edges"][0]["target_id"] = "missing"
    with pytest.raises(ValueError):
        cap.ingest(doc, context=ctx, profile="unknown" if fault == "profile" else "legacy")
    assert list(ctx.output_root.iterdir()) == []


def test_reader_requires_explicit_manifest_version_and_ready(storage):
    m, _, ctx, doc, cap, _ = storage
    missing = ctx.output_root / "missing/manifest.json"
    with pytest.raises(ValueError):
        m.SnapshotGraphStore(missing, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    assert not missing.parent.exists()
    manifest = cap.ingest(doc, context=ctx)
    for version in (None, "", "wrong-version"):
        with pytest.raises(ValueError):
            m.SnapshotGraphStore(manifest, graph_version=version, profiles=trusted_profiles(m))
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["status"] = "building"
    manifest.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))


def test_reader_detects_db_or_manifest_mutation(storage):
    m, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    store = m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    with store.database_path.open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError):
        store.get_repository_summary()
    with pytest.raises(ValueError):
        m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))


def test_worker_thread_reads_each_use_own_connection(storage):
    m, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    store = m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    before = hashlib.sha256(store.database_path.read_bytes()).hexdigest()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: store.get_repository_summary(), range(12)))
    assert all(item == results[0] for item in results)
    assert hashlib.sha256(store.database_path.read_bytes()).hexdigest() == before


def test_publication_cancellation_removes_owned_staging(storage, monkeypatch):
    m, _, ctx, doc, cap, _ = storage
    from vgar.mcp.proposal.context import cancel_request
    original = m._verify_roundtrip
    def cancel_after_commit(*args):
        result = original(*args)
        cancel_request(ctx)
        return result
    monkeypatch.setattr(m, "_verify_roundtrip", cancel_after_commit)
    with pytest.raises(ValueError, match="cancel"):
        cap.ingest(doc, context=ctx)
    assert list(ctx.output_root.iterdir()) == []


def test_factory_snapshot_mode_requires_operator_manifest(storage, monkeypatch):
    _, _, ctx, doc, cap, _ = storage
    from vgar.graph.factory import create_graph_service
    manifest = cap.ingest(doc, context=ctx)
    monkeypatch.setenv("VGAR_GRAPH_RESOLVER_HASH", HASH)
    monkeypatch.setenv("VGAR_GRAPH_PROFILE_HASH", ctx.config_hash)
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "snapshot")
    monkeypatch.setenv("VGAR_GRAPH_SNAPSHOT_MANIFEST", str(manifest))
    monkeypatch.setenv("VGAR_GRAPH_VERSION", doc["graph_version"])
    service = create_graph_service()
    assert service.store.load_document(doc["graph_version"]) == doc


@pytest.mark.parametrize("field", ["profile", "schema_hash", "resolver_hash", "profile_hash", "document_hash"])
def test_manifest_fingerprints_cannot_claim_an_unregistered_profile(storage, field):
    m, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    record = json.loads(manifest.read_bytes())
    if field == "profile":
        record["profile"] = "rich-unavailable"
    else:
        key = "canonical_document_hash" if field == "document_hash" else field
        record["identity"][key] = "sha256:" + "c" * 64
        record["snapshot_id"] = m.StorageIdentity(**record["identity"]).snapshot_id
    manifest.write_bytes(m.canonical_bytes(record))
    with pytest.raises(ValueError):
        m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))


def test_two_snapshots_same_ids_different_facts_are_isolated(storage):
    m, authority, ctx, doc, cap, _ = storage
    manifest1 = cap.ingest(doc, context=ctx)
    changed = copy.deepcopy(doc)
    changed["nodes"][0]["name"] = "second-repository"
    identity2 = cap.identity(changed, source_inventory_hash=ctx.source_hash)
    ctx2 = authority._sign(replace(ctx, snapshot_hash=identity2.snapshot_id, grants=()))
    ctx2 = authority.grant(ctx2, "storage_ingest", identity2.snapshot_id)
    manifest2 = cap.ingest(changed, context=ctx2)
    left = m.SnapshotGraphStore(manifest1, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    right = m.SnapshotGraphStore(manifest2, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    node_id = doc["nodes"][0]["id"]
    assert left.database_path != right.database_path
    assert left.get_node(node_id).name == doc["nodes"][0]["name"]
    assert right.get_node(node_id).name == "second-repository"


def test_in_transaction_exception_rolls_back_rows_and_ready(storage, monkeypatch):
    m, _, ctx, doc, cap, _ = storage
    receipts = []
    original = m._SnapshotWriter._before_ready
    def fail(writer, connection, document):
        original(writer, connection, document)
        receipts.append(connection.execute("SELECT status FROM graph_metadata").fetchone()[0])
        raise RuntimeError("synthetic crash before READY")
    monkeypatch.setattr(m._SnapshotWriter, "_before_ready", fail)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        cap.ingest(doc, context=ctx)
    assert receipts == ["building"]
    assert list(ctx.output_root.iterdir()) == []


def test_keyboard_interrupt_before_publish_never_exposes_ready(storage, monkeypatch):
    m, _, ctx, doc, cap, _ = storage
    def interrupt(*_):
        raise KeyboardInterrupt()
    monkeypatch.setattr(m, "_verify_roundtrip", interrupt)
    with pytest.raises(KeyboardInterrupt):
        cap.ingest(doc, context=ctx)
    assert not cap.unpublished_staging()
    assert list(ctx.output_root.iterdir()) == []


@pytest.mark.parametrize("crash_point", ["db_committed", "manifest_written"])
def test_dead_process_leaves_only_unpublished_orphan(storage, tmp_path, crash_point):
    m, _, _, doc, _, _ = storage
    # Native child exits without finally/GC after SQL commit. Host creates its
    # own authority/context; no private grant/key is exported into results.
    root = tmp_path / "child"
    root.mkdir()
    code = '''
import json, os, sys, time
from pathlib import Path
from vgar.graph import storage_capabilities as m
from vgar.mcp.proposal.context import ContextAuthority, bind_context, source_inventory_hash
root=Path(sys.argv[1])
for name in ("repo","lease","output","state"): (root/name).mkdir()
a=ContextAuthority(root/"state")
p=m.legacy_profile(resolver_hash="sha256:"+"b"*64,profile_hash="sha256:"+"a"*64)
cap=m.SQLiteSnapshotStorage(root/"output",profiles=(p,))
doc=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
source=source_inventory_hash(root/"repo")
i=cap.identity(doc,source_inventory_hash=source)
c=bind_context(a,repo_root=root/"repo",lease_root=root/"lease",output_root=root/"output",request_id="child",run_id="run",task_id="task",snapshot_hash=i.snapshot_id,source_hash=source,config_hash=p.profile_hash,deadline=time.time()+60)
c=a.grant(c,"storage_ingest",i.snapshot_id)
if sys.argv[3]=="db_committed":
    m._verify_roundtrip=lambda *args: os._exit(23)
else:
    Path.rename=lambda *args: os._exit(23)
cap.ingest(doc,context=c)
'''
    result = subprocess.run([sys.executable, "-B", "-c", code, str(root), str(FIXTURE), crash_point],
                            capture_output=True, timeout=30, check=False)
    assert result.returncode == 23, result.stderr.decode(errors="replace")
    output = root / "output"
    assert not [p for p in output.glob("*/manifest.json") if not p.parent.name.startswith(".")]
    orphans = list(output.glob(".staging-*"))
    assert len(orphans) == 1 and (orphans[0] / "graph.db").is_file()
    with pytest.raises(ValueError):
        m.SnapshotGraphStore(orphans[0] / "manifest.json", graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    assert (orphans[0] / "manifest.json").exists() == (crash_point == "manifest_written")


def test_concurrent_writer_grant_replay_and_reader_visibility(storage):
    m, _, ctx, doc, cap, _ = storage
    import threading
    barrier = threading.Barrier(2)
    def write():
        barrier.wait(timeout=10)
        try:
            return cap.ingest(doc, context=ctx)
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: write(), range(2)))
    assert sum(r is not None for r in results) == 1
    manifest = next(r for r in results if r is not None)
    assert m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m)).load_document(doc["graph_version"]) == doc


@pytest.mark.parametrize("fault", ["db_missing", "not_ready", "metadata_mismatch", "wal", "version_mutation"])
def test_read_failures_do_not_create_or_migrate(storage, fault):
    m, _, ctx, doc, cap, _ = storage
    import sqlite3
    manifest = cap.ingest(doc, context=ctx)
    store = m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    database = store.database_path
    if fault == "db_missing":
        database.unlink()
    elif fault == "wal":
        Path(str(database) + "-wal").write_bytes(b"invalid")
    elif fault == "version_mutation":
        store.requested_graph_version = "different"
    else:
        from contextlib import closing
        with closing(sqlite3.connect(database)) as connection:
            if fault == "not_ready":
                connection.execute("UPDATE graph_metadata SET status='building'")
            else:
                connection.execute("UPDATE snapshot_binding SET identity_json='{}'")
            connection.commit()
    before = {p.name: p.read_bytes() for p in manifest.parent.iterdir()}
    with pytest.raises((ValueError, FileNotFoundError)):
        store.get_repository_summary()
    assert {p.name: p.read_bytes() for p in manifest.parent.iterdir()} == before


def test_optimized_python_denies_untrusted_context(storage):
    _, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    code = '''
import sys
from vgar.graph.storage_capabilities import SnapshotGraphStore,legacy_profile
s=SnapshotGraphStore(sys.argv[1],graph_version=sys.argv[2],profiles=(legacy_profile(resolver_hash="sha256:"+"b"*64,profile_hash="sha256:"+"a"*64),))
try: s.initialize()
except ValueError: pass
else: raise RuntimeError("reader wrote under -O")
'''
    result = subprocess.run([sys.executable, "-O", "-B", "-c", code, str(manifest), doc["graph_version"]],
                            capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def storage_process(context, document, go, queue):
    from vgar.graph import storage_capabilities as m
    from vgar.mcp.proposal.context import ContextAuthority
    ContextAuthority(context.state_root)
    profile = m.legacy_profile(resolver_hash=HASH, profile_hash=context.config_hash)
    cap = m.SQLiteSnapshotStorage(context.output_root, profiles=(profile,))
    if not go.wait(15):
        raise RuntimeError("Synthetic process barrier timed out")
    try:
        manifest = cap.ingest(document, context=context)
        queue.put(("PUBLISHED", str(manifest)))
    except ValueError:
        queue.put(("REJECTED", None))


def test_two_native_process_writers_serialize_same_identity(storage):
    m, _, ctx, doc, _, _ = storage
    import multiprocessing as mp
    spawn = mp.get_context("spawn")
    go, queue = spawn.Event(), spawn.Queue()
    processes = [spawn.Process(target=storage_process, args=(ctx, doc, go, queue)) for _ in range(2)]
    for process in processes:
        process.start()
    go.set()
    try:
        values = [queue.get(timeout=25) for _ in processes]
        for process in processes:
            process.join(15)
        assert sorted(row[0] for row in values) == ["PUBLISHED", "REJECTED"]
        assert all(p.exitcode == 0 for p in processes)
        manifest = next(row[1] for row in values if row[1])
        assert m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m)).load_document(doc["graph_version"]) == doc
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        queue.close()


def test_reader_cannot_bypass_profile_hash_with_registry(storage):
    m, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    wrong = m.legacy_profile(resolver_hash="sha256:" + "d" * 64, profile_hash=ctx.config_hash)
    with pytest.raises(ValueError, match="profile"):
        m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=(wrong,))


def test_invalid_profile_fingerprint_or_new_schema_is_not_admitted(storage):
    m, _, ctx, doc, _, _ = storage
    with pytest.raises(ValueError, match="SHA-256"):
        m.StorageProfile("rich", "missing", HASH, HASH, lambda _: None)
    # A host validator alone cannot widen the SQL legacy schema.
    profile = m.StorageProfile("rich", HASH, HASH, HASH, lambda _: None)
    unsupported = m.SQLiteSnapshotStorage(ctx.output_root, profiles=(profile,))
    doc["nodes"][0]["type"] = "Component"
    with pytest.raises(ValueError):
        unsupported.ingest(doc, context=ctx, profile="rich")
    assert list(ctx.output_root.iterdir()) == []


def test_reader_sees_nothing_before_atomic_publication(storage, monkeypatch):
    m, _, ctx, doc, cap, _ = storage
    import threading
    ready, release = threading.Event(), threading.Event()
    original = m._verify_roundtrip
    def pause(*args):
        original(*args)
        ready.set()
        if not release.wait(15):
            raise RuntimeError("Synthetic publish barrier timed out")
    monkeypatch.setattr(m, "_verify_roundtrip", pause)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(cap.ingest, doc, context=ctx)
        try:
            assert ready.wait(10)
            assert not list(ctx.output_root.glob("*/manifest.json"))
            assert len(cap.unpublished_staging()) == 1
        finally:
            release.set()
        manifest = future.result(timeout=20)
    assert not cap.unpublished_staging()
    assert m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m)).load_document(doc["graph_version"]) == doc


def test_linked_output_root_rejected_without_touching_target(storage, tmp_path):
    m, _, ctx, _, _, _ = storage
    import os
    alias = ctx.output_root / "alias"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(ctx.lease_root)],
                                capture_output=True, check=False, timeout=10)
        assert result.returncode == 0, result.stderr
    else:
        alias.symlink_to(ctx.lease_root, target_is_directory=True)
    profile = m.legacy_profile(resolver_hash=HASH, profile_hash=ctx.config_hash)
    with pytest.raises(ValueError, match="Linked/reparse"):
        m.SQLiteSnapshotStorage(alias, profiles=(profile,))
    assert list(ctx.lease_root.iterdir()) == []


def test_sdk2_sync_tool_queries_sqlite_on_worker_threads(storage):
    m, _, ctx, doc, cap, _ = storage
    import threading

    import anyio

    from vgar.mcp.server_factory import create_server

    manifest = cap.ingest(doc, context=ctx)
    store = m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"], profiles=trusted_profiles(m))
    server = create_server("synthetic-storage-thread-proof")
    main_thread = threading.get_ident()
    observed = []

    @server.tool()
    def snapshot_summary() -> str:
        observed.append(threading.get_ident())
        return json.dumps(store.get_repository_summary())

    async def run():
        # Public SDK method performs sync tool dispatch in AnyIO worker threads.
        async with anyio.create_task_group() as tasks:
            for _ in range(6):
                tasks.start_soon(server.call_tool, "snapshot_summary", {})
    anyio.run(run)
    assert len(observed) == 6
    assert all(thread != main_thread for thread in observed)


def test_manifest_cannot_register_its_own_profile(storage):
    m, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    with pytest.raises(ValueError, match="trusted profile"):
        m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"])


@pytest.mark.parametrize("sql", [
    "UPDATE nodes SET name='forged' WHERE rowid=1",
    "UPDATE nodes SET start_line=100 WHERE rowid=2",
    "UPDATE edges SET confidence=0.01 WHERE rowid=1",
    "UPDATE edges SET provenance_json='{}' WHERE rowid=1",
    "UPDATE graph_metadata SET repo_key='wrong'",
    "DELETE FROM edges WHERE rowid=1",
])
def test_sql_projection_must_match_document_even_if_db_hash_is_refreshed(storage, sql):
    import sqlite3
    from contextlib import closing
    m, _, ctx, doc, cap, identity = storage
    manifest = cap.ingest(doc, context=ctx)
    database = manifest.parent / "graph.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(sql)
        connection.commit()
    record = json.loads(manifest.read_bytes())
    record["database_hash"] = m.digest(database.read_bytes())
    manifest.write_bytes(m.canonical_bytes(record))
    with pytest.raises(ValueError, match="projection"):
        m._verify_roundtrip(database, identity, m.canonical_bytes(doc))
    with pytest.raises(ValueError, match="projection"):
        m.SnapshotGraphStore(manifest, graph_version=doc["graph_version"],
                             profiles=(m.legacy_profile(resolver_hash=HASH, profile_hash=ctx.config_hash),))


@pytest.mark.parametrize("fault", ["source", "deadline", "cancel_event"])
def test_insert_guard_failure_rolls_back_and_consumes_grant(storage, monkeypatch, fault):
    import threading
    import time

    m, _, ctx, doc, cap, _ = storage
    event = threading.Event()
    original = m._SnapshotWriter._before_ready
    def disrupt(writer, connection, document):
        if fault == "source":
            (ctx.repo_root / "new.py").write_text("# synthetic changed source\n", encoding="utf-8")
        if fault == "cancel_event":
            event.set()
        if fault == "deadline":
            with monkeypatch.context() as scoped:
                scoped.setattr(time, "time", lambda: ctx.deadline + 1)
                original(writer, connection, document)
        else:
            original(writer, connection, document)
    monkeypatch.setattr(m._SnapshotWriter, "_before_ready", disrupt)
    with pytest.raises(ValueError):
        cap.ingest(doc, context=ctx, cancel_event=event)
    assert list(ctx.output_root.iterdir()) == []
    assert (ctx.state_root / "used" / ctx.grants[-1].grant_id).is_file()


def test_coordinated_manifest_and_sql_binding_cannot_change_trusted_profile(storage):
    import sqlite3
    from contextlib import closing
    m, _, ctx, doc, cap, identity = storage
    manifest = cap.ingest(doc, context=ctx)
    forged = replace(identity, resolver_hash="sha256:" + "f" * 64)
    with closing(sqlite3.connect(manifest.parent / "graph.db")) as connection:
        connection.execute("UPDATE snapshot_binding SET identity_json=?", (m.canonical_bytes(m.asdict(forged)).decode(),))
        connection.commit()
    record = json.loads(manifest.read_bytes())
    record["identity"] = m.asdict(forged)
    record["snapshot_id"] = forged.snapshot_id
    record["database_hash"] = m.digest((manifest.parent / "graph.db").read_bytes())
    manifest.write_bytes(m.canonical_bytes(record))
    destination = manifest.parent.with_name(forged.snapshot_id.removeprefix("sha256:"))
    manifest.parent.rename(destination)
    with pytest.raises(ValueError, match="profile"):
        m.SnapshotGraphStore(destination / "manifest.json", graph_version=doc["graph_version"], profiles=trusted_profiles(m))


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
def test_snapshot_factory_through_real_sdk2_stdio(storage, mode):
    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    _, _, ctx, doc, cap, _ = storage
    manifest = cap.ingest(doc, context=ctx)
    database = manifest.parent / "graph.db"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    source_before = ctx.source_hash
    from vgar.mcp.proposal.context import source_inventory_hash
    env = {"PYTHONPATH": str(Path(__file__).parents[2] / "src"), "PYTHONUTF8": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1",
           "VGAR_GRAPH_BACKEND": "snapshot", "VGAR_GRAPH_SNAPSHOT_MANIFEST": str(manifest),
           "VGAR_GRAPH_VERSION": doc["graph_version"], "VGAR_GRAPH_RESOLVER_HASH": HASH,
           "VGAR_GRAPH_PROFILE_HASH": ctx.config_hash,
           "VGAR_MCP_AUDIT_LOG": str(ctx.output_root / "wire-audit.jsonl")}
    params = StdioServerParameters(command=sys.executable,
                                  args=["-B", "-m", "vgar.mcp.servers.graph_server"], env=env)
    async def run():
        with anyio.fail_after(30):
            async with Client(params, mode=mode) as client:
                resources = await client.read_resource("vgar://repo/summary")
                summary = json.loads(resources.contents[0].text)
                assert summary["graph_version"] == doc["graph_version"]
                assert len((await client.list_tools()).tools) == 11
                result = await client.call_tool("search_symbols", {"query": "login", "limit": 20})
                assert not result.is_error
                assert "login" in result.content[0].text
    anyio.run(run)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert source_inventory_hash(ctx.repo_root) == source_before
