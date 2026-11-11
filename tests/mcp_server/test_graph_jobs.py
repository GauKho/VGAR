"""Real static builder/storage on synthetic source; never model/target execution."""
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import anyio
import pytest

from vgar.mcp.proposal.context import bind_context, source_inventory_hash


def api():
    assert importlib.util.find_spec("vgar.mcp.proposal.graph_jobs"), "L6-6 controller missing"
    from vgar.mcp.proposal import graph_jobs
    return graph_jobs


@pytest.fixture
def jobs(bound):
    m = api()
    authority, original = bound
    source = original.repo_root / "src/a.py"
    source.parent.mkdir()
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    config = m.GraphJobConfig(repo_root=original.repo_root, output_root=original.output_root,
                              state_root=original.state_root, repo_key="demo/graph-job",
                              repository_revision="fixture-revision", config_hash=original.config_hash,
                              profile_hash=original.config_hash)

    def context(*, grant=True, task="task", limits=None):
        from vgar.mcp.proposal.contracts import BuildRequest
        ctx = bind_context(authority, repo_root=original.repo_root, lease_root=original.lease_root,
                           output_root=original.output_root, request_id="request-" + str(time.monotonic_ns()),
                           run_id="run", task_id=task, snapshot_hash=original.snapshot_hash,
                           source_hash=source_inventory_hash(original.repo_root), config_hash=config.config_hash,
                           deadline=time.time()+90, limits=limits)
        return authority.grant(ctx, "build_or_update_graph", BuildRequest(repo_path=str(ctx.repo_root)).input_hash()) if grant else ctx

    context.authority = authority  # Test bootstrap retains its original host authority.

    def issue(ctx, identity):
        storage = bind_context(authority, repo_root=ctx.repo_root, lease_root=ctx.lease_root,
                               output_root=ctx.output_root, request_id=ctx.request_id, run_id=ctx.run_id,
                               task_id=ctx.task_id, snapshot_hash=identity.snapshot_id,
                               source_hash=ctx.source_hash, config_hash=ctx.config_hash,
                               deadline=ctx.deadline, limits=ctx.limits)
        return authority.grant(storage, "storage_ingest", identity.snapshot_id)
    controller = m.GraphJobController(config, storage_issuer=issue)
    yield m, controller, context, source, config
    controller.close()


def execute(controller, ctx):
    from vgar.mcp.proposal.contracts import BuildRequest
    return anyio.run(controller.build_or_update, BuildRequest(repo_path=str(ctx.repo_root)), ctx)


def details(ctx, result):
    return json.loads((ctx.output_root / result.evidence[0].path).read_bytes())


def test_controller_exists():
    api()


def test_cold_unchanged_reuse_and_real_warm_update(jobs):
    _, controller, context, source, _ = jobs
    ctx = context()
    first = execute(controller, ctx)
    first_receipt = details(ctx, first)
    assert first_receipt["cache_mode"] == "COLD_BUILD"
    assert first.published and first.capabilities == ("legacy_static_python",)
    manifest = ctx.output_root / first_receipt["manifest"]
    database = manifest.parent / "graph.db"
    before = database.read_bytes()
    ctx2 = context(task="second-task")
    second = execute(controller, ctx2)
    assert details(ctx2, second)["cache_mode"] == "SNAPSHOT_REUSE"
    assert database.read_bytes() == before
    assert second.binding.task_id == "second-task"
    assert second.result_snapshot_hash == first.result_snapshot_hash
    source.write_text("def value():\n    return 2\n", encoding="utf-8")
    ctx3 = context()
    third = execute(controller, ctx3)
    receipt = details(ctx3, third)
    assert receipt["cache_mode"] == "WARM_UPDATE"
    assert third.result_snapshot_hash != first.result_snapshot_hash
    assert receipt["worker_pid"] == first_receipt["worker_pid"]
    assert receipt["changed_files"] == ["src/a.py"]


def test_restart_reuses_snapshot_but_changed_source_builds_cold(jobs):
    m, controller, context, source, config = jobs
    ctx = context()
    first = execute(controller, ctx)
    controller.close()
    replacement = m.GraphJobController(config, storage_issuer=controller.storage_issuer)
    try:
        second_ctx = context()
        second = execute(replacement, second_ctx)
        assert details(second_ctx, second)["cache_mode"] == "SNAPSHOT_REUSE"
        assert second.result_snapshot_hash == first.result_snapshot_hash
        source.write_text("def value():\n    return 3\n", encoding="utf-8")
        third_ctx = context()
        third = execute(replacement, third_ctx)
        assert details(third_ctx, third)["cache_mode"] == "COLD_BUILD"
    finally:
        replacement.close()


def test_denied_or_replayed_grant_has_no_spawn_or_operation_output(jobs):
    _, controller, context, _, _ = jobs
    ctx = context(grant=False)
    with pytest.raises(ValueError, match="grant"):
        execute(controller, ctx)
    assert not list(ctx.output_root.iterdir())
    allowed = context()
    execute(controller, allowed)
    before = {p.relative_to(ctx.output_root).as_posix(): p.read_bytes() for p in ctx.output_root.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="used"):
        execute(controller, allowed)
    assert {p.relative_to(ctx.output_root).as_posix(): p.read_bytes() for p in ctx.output_root.rglob("*") if p.is_file()} == before


def test_stale_context_does_not_consume_grant_or_write(jobs):
    _, controller, context, source, _ = jobs
    ctx = context()
    source.write_text("# changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        execute(controller, ctx)
    assert not list(ctx.output_root.iterdir())
    assert not (ctx.state_root / "used" / ctx.grants[-1].grant_id).exists()


def test_core_tools_uses_controller_without_nested_thread_lock_deadlock(jobs):
    from vgar.mcp.proposal.contracts import BuildRequest
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    _, controller, context, _, _ = jobs
    tools = CoreTools(ProviderRegistry(), graph_jobs=controller)
    async def run():
        ctx = context()
        with anyio.fail_after(15):
            result = await tools.build(BuildRequest(repo_path=str(ctx.repo_root)), ctx)
        assert result.published
    anyio.run(run)


def test_unsupported_layers_fail_before_authorization_or_spawn(jobs):
    m, controller, context, _, config = jobs
    other = m.GraphJobController(replace(config, required_capabilities=("G_arch",)), storage_issuer=controller.storage_issuer)
    ctx = context()
    try:
        with pytest.raises(ValueError, match="capability"):
            execute(other, ctx)
        assert not list(ctx.output_root.iterdir())
    finally:
        other.close()


def test_cache_hash_corruption_is_not_a_cache_miss(jobs):
    _, controller, context, _, _ = jobs
    ctx = context()
    result = execute(controller, ctx)
    record = details(ctx, result)
    manifest = ctx.output_root / record["manifest"]
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash"):
        execute(controller, context())


def test_storage_issuer_cannot_substitute_context(jobs):
    m, controller, context, _, config = jobs
    original = controller.storage_issuer
    def wrong(ctx, identity):
        return original(ctx, identity).__class__(**{**original(ctx, identity).__dict__, "task_id": "forged"})
    other = m.GraphJobController(config, storage_issuer=wrong)
    ctx = context()
    try:
        with pytest.raises(ValueError):
            execute(other, ctx)
        assert not list(ctx.output_root.glob("snapshots/*/manifest.json"))
    finally:
        other.close()


def test_parent_request_cancellation_blocks_derived_storage_publication(jobs, monkeypatch):
    from vgar.graph import storage_capabilities as s
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.mcp.proposal.context import cancel_request
    m, controller, context, _, config = jobs
    parent = context()
    document = PythonGraphBuilder(repo_key=config.repo_key, repository_revision=config.repository_revision).build(config.repo_root)
    profile = s.legacy_profile(resolver_hash=m.resolver_fingerprint(), profile_hash=config.profile_hash)
    cap = s.SQLiteSnapshotStorage(parent.output_root, profiles=(profile,))
    identity = cap.identity(document, source_inventory_hash=parent.source_hash)
    storage = controller.storage_issuer(parent, identity)
    original = s._verify_roundtrip
    def cancel(*args):
        original(*args)
        cancel_request(parent)
    monkeypatch.setattr(s, "_verify_roundtrip", cancel)
    with pytest.raises(ValueError, match="cancel"):
        cap.ingest(document, context=storage, request_context=parent)
    assert not list(parent.output_root.iterdir())


def test_missing_worker_ack_never_publishes(jobs, monkeypatch):
    _, controller, context, _, _ = jobs
    exchange = controller._exchange
    def fail(message, *args):
        if message["action"] == "ack":
            return {"status": "ERROR"}
        return exchange(message, *args)
    monkeypatch.setattr(controller, "_exchange", fail)
    ctx = context()
    with pytest.raises(ValueError, match="acknowledged"):
        execute(controller, ctx)
    assert not list(ctx.output_root.glob("snapshots/*/manifest.json"))


def test_cache_requires_original_publication_receipt(jobs):
    _, controller, context, _, _ = jobs
    ctx = context()
    result = execute(controller, ctx)
    (ctx.output_root / result.evidence[0].path).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        execute(controller, context())


def test_implementation_drift_restarts_worker(jobs, monkeypatch):
    m, controller, context, source, _ = jobs
    ctx = context()
    before = details(ctx, execute(controller, ctx))
    monkeypatch.setattr(m, "implementation_fingerprint", lambda: "sha256:" + "f" * 64)
    source.write_text("def value():\n    return 9\n", encoding="utf-8")
    after_ctx = context()
    after = details(after_ctx, execute(controller, after_ctx))
    assert after["cache_mode"] == "COLD_BUILD"
    assert after["worker_pid"] != before["worker_pid"]


def test_readiness_reports_bound_controller(jobs):
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    _, controller, _, _, _ = jobs
    assert CoreTools(ProviderRegistry(), graph_jobs=controller).readiness()["build"] == "BOUND_UNVERIFIED"


def test_worker_deadline_applies_before_storage_publication(jobs):
    import threading

    from vgar.mcp.proposal.context import SecurityLimits
    m, controller, context, _, config = jobs
    original = controller.storage_issuer
    def delayed(ctx, identity):
        # Exercise the controller's short deadline, not the longer context TTL.
        threading.Event().wait(2.1)
        return original(ctx, identity)
    other = m.GraphJobController(config, storage_issuer=delayed)
    ctx = context(limits=SecurityLimits(worker_seconds=2))
    try:
        with pytest.raises(TimeoutError):
            execute(other, ctx)
        assert not list(ctx.output_root.glob("snapshots/*/manifest.json"))
    finally:
        other.close()


def test_returning_to_cached_source_resets_divergent_worker_baseline(jobs):
    _, controller, context, source, _ = jobs
    original = source.read_bytes()
    execute(controller, context())
    source.write_text("def value():\n    return 2\n", encoding="utf-8")
    execute(controller, context())
    source.write_bytes(original)
    ctx = context()
    assert details(ctx, execute(controller, ctx))["cache_mode"] == "SNAPSHOT_REUSE"
    source.with_name("c.py").write_text("def extra():\n    return 3\n", encoding="utf-8")
    ctx2 = context()
    record = details(ctx2, execute(controller, ctx2))
    assert record["cache_mode"] == "COLD_BUILD"
    assert record["changes_baseline_snapshot_hash"] is None


def test_malformed_worker_summary_is_rejected_before_publication(jobs, monkeypatch):
    _, controller, context, _, _ = jobs
    from vgar.graph.storage_capabilities import canonical_bytes, digest
    exchange = controller._exchange
    def corrupt(message, *args):
        result = exchange(message, *args)
        if message["action"] == "build":
            summary = Path(message["stage"]) / "summary.json"
            value = json.loads(summary.read_bytes())
            value["cache_hits"] = True
            summary.write_bytes(canonical_bytes(value))
            result["summary_hash"] = digest(summary.read_bytes())
        return result
    monkeypatch.setattr(controller, "_exchange", corrupt)
    ctx = context()
    with pytest.raises(ValueError, match="summary"):
        execute(controller, ctx)
    assert not list(ctx.output_root.glob("snapshots/*/manifest.json"))


def native_job(config, ctx, go, queue, crash=False):
    from vgar.mcp.proposal.context import ContextAuthority
    from vgar.mcp.proposal.graph_jobs import GraphJobController
    authority = ContextAuthority(ctx.state_root)
    def issue(parent, identity):
        new = bind_context(authority, repo_root=parent.repo_root, lease_root=parent.lease_root,
            output_root=parent.output_root, request_id=parent.request_id, run_id=parent.run_id,
            task_id=parent.task_id, snapshot_hash=identity.snapshot_id, source_hash=parent.source_hash,
            config_hash=parent.config_hash, deadline=parent.deadline, limits=parent.limits)
        return authority.grant(new, "storage_ingest", identity.snapshot_id)
    controller = GraphJobController(config, storage_issuer=issue)
    if crash:
        from vgar.graph import storage_capabilities
        storage_capabilities._verify_roundtrip = lambda *_: os._exit(29)
    if not go.wait(15):
        raise RuntimeError("Native graph job barrier timeout")
    try:
        result = execute(controller, ctx)
        queue.put(details(ctx, result)["cache_mode"])
    finally:
        controller.close()


def test_two_native_clients_serialize_without_overwriting(jobs):
    import multiprocessing as mp
    _, _, context, _, config = jobs
    spawn = mp.get_context("spawn")
    go, queue = spawn.Event(), spawn.Queue()
    contexts = [context(task="client-"+str(i)) for i in range(2)]
    processes = [spawn.Process(target=native_job, args=(config, ctx, go, queue)) for ctx in contexts]
    for process in processes:
        process.start()
    go.set()
    try:
        values = [queue.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(10)
        assert sorted(values) == ["COLD_BUILD", "SNAPSHOT_REUSE"]
        assert all(p.exitcode == 0 for p in processes)
        assert len(list(config.output_root.glob("snapshots/*/manifest.json"))) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        queue.close()


def test_native_controller_crash_cannot_publish_private_ready_db(jobs):
    import multiprocessing as mp
    _, _, context, _, config = jobs
    spawn = mp.get_context("spawn")
    go, queue = spawn.Event(), spawn.Queue()
    process = spawn.Process(target=native_job, args=(config, context(), go, queue, True))
    process.start()
    go.set()
    try:
        process.join(25)
        assert process.exitcode == 29
        assert not list(config.output_root.glob("snapshots/*/manifest.json"))
        assert len(list(config.output_root.glob("snapshots/.staging-*/graph.db"))) == 1
        assert not list(config.output_root.glob("graph-cache/*.json"))
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        queue.close()


def test_async_cancellation_kills_worker_and_descendant(jobs, tmp_path, monkeypatch):
    from test_runtime_lifecycle import alive
    m, controller, context, _, _ = jobs
    marker = tmp_path / "pids.json"
    fake = tmp_path / "worker.py"
    fake.write_text("import os,sys,json,subprocess,threading\nfrom pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-B','-c','import threading;threading.Event().wait(60)'])\n"
        f"Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid]))\n"
        "threading.Event().wait(60)\n", encoding="utf-8")
    original = subprocess.Popen
    def start(argv, **kwargs):
        if any(str(arg).endswith("_graph_worker.py") for arg in argv):
            argv = [sys.executable, "-B", str(fake)]
        return original(argv, **kwargs)
    monkeypatch.setattr(m.subprocess, "Popen", start)
    ctx = context()
    async def run():
        async with anyio.create_task_group() as group:
            group.start_soon(controller.build_or_update, m.BuildRequest(repo_path=str(ctx.repo_root)), ctx)
            with anyio.fail_after(10):
                while not marker.exists():
                    await anyio.sleep(.02)
            group.cancel_scope.cancel()
    anyio.run(run)
    pids = json.loads(marker.read_bytes())
    assert all(not alive(pid) for pid in pids)
    assert controller._process is None
    assert not list(ctx.output_root.glob(".graph-job-*"))
    assert not list(ctx.output_root.glob(".graph-worker-*"))
    assert not list(ctx.output_root.glob("snapshots/*/manifest.json"))
    records = [json.loads(p.read_bytes()) for p in ctx.output_root.glob("graph-jobs/*.json")]
    assert len(records) == 1 and records[0]["status"] == "ERROR" and records[0]["cleanup"] == "PASS"


@pytest.mark.parametrize("barrier", ["copy", "ingest"])
def test_parent_cancellation_at_write_barriers_never_publishes(jobs, monkeypatch, barrier):
    from vgar.graph import storage_capabilities
    from vgar.mcp.proposal.context import cancel_request
    m, controller, context, _, _ = jobs
    ctx = context()
    if barrier == "copy":
        original = m.read_lease_bytes
        def cancel(root, *args):
            result = original(root, *args)
            if root == ctx.repo_root:
                cancel_request(ctx)
            return result
        monkeypatch.setattr(m, "read_lease_bytes", cancel)
    else:
        original = storage_capabilities._verify_roundtrip
        def cancel(*args):
            original(*args)
            cancel_request(ctx)
        monkeypatch.setattr(storage_capabilities, "_verify_roundtrip", cancel)
    with pytest.raises(ValueError, match="cancel"):
        execute(controller, ctx)
    assert not list(ctx.output_root.glob("snapshots/*/manifest.json"))
    assert not list(ctx.output_root.glob(".graph-job-*"))


def test_controller_fails_closed_under_optimized_python(jobs):
    _, _, _, _, config = jobs
    code = '''
import sys,anyio
from pathlib import Path
from vgar.mcp.proposal.graph_jobs import GraphJobConfig,GraphJobController
from vgar.mcp.proposal.contracts import BuildRequest
c=GraphJobConfig(repo_root=Path(sys.argv[1]),output_root=Path(sys.argv[2]),state_root=Path(sys.argv[3]),repo_key="demo",repository_revision="revision",config_hash="sha256:"+"a"*64,profile_hash="sha256:"+"a"*64)
j=GraphJobController(c,storage_issuer=lambda *args:None)
try:
    try: anyio.run(j.build_or_update,BuildRequest(repo_path=str(c.repo_root)),{})
    except ValueError: pass
    else: raise RuntimeError("untrusted context accepted under -O")
finally: j.close()
'''
    result = subprocess.run([sys.executable, "-O", "-B", "-c", code, str(config.repo_root), str(config.output_root), str(config.state_root)],
                            check=False, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert list(config.output_root.iterdir()) == []


def test_storage_rechecks_deadline_after_final_source_scan(jobs, monkeypatch):
    from vgar.graph import storage_capabilities as storage
    from vgar.graph.builder import PythonGraphBuilder
    _, controller, context, _, config = jobs
    ctx = context()
    document = PythonGraphBuilder(repo_key=config.repo_key, repository_revision=config.repository_revision).build(ctx.repo_root)
    cap = storage.SQLiteSnapshotStorage(ctx.output_root, profiles=(controller.profile(),))
    identity = cap.identity(document, source_inventory_hash=ctx.source_hash)
    derived = controller.storage_issuer(ctx, identity)
    deadline = time.time()+5
    clock = [time.time()]
    original = storage._gate
    def cross_deadline(*args):
        original(*args)
        if list(ctx.output_root.glob(".staging-*/manifest.json")):
            clock[0] = deadline+1
    monkeypatch.setattr(storage, "_gate", cross_deadline)
    monkeypatch.setattr(storage.time, "time", lambda: clock[0])
    with pytest.raises(TimeoutError):
        cap.ingest(document, context=derived, request_context=ctx, operation_deadline=deadline)
    assert not list(ctx.output_root.glob("*/manifest.json"))


def test_disappearing_source_cannot_skip_worker_cleanup(jobs, monkeypatch):
    import shutil
    _, controller, context, _, _ = jobs
    ctx = context()
    original = controller._exchange
    def remove(message, *args):
        response = original(message, *args)
        if message["action"] == "build":
            # Explicit test-owned source root; never the VGAR checkout.
            assert ctx.repo_root.parent.name.startswith("test_")
            shutil.rmtree(ctx.repo_root)
        return response
    monkeypatch.setattr(controller, "_exchange", remove)
    with pytest.raises(ValueError):
        execute(controller, ctx)
    assert controller._process is None
    assert not list(ctx.output_root.glob(".graph-worker-*"))


@pytest.mark.parametrize("change", ["repo_root", "repo_key", "revision", "roots", "profile", "config", "resolver", "schema"])
def test_changed_build_bindings_do_not_reuse_previous_snapshot(jobs, monkeypatch, change):
    m, controller, context, _, config = jobs
    before_ctx = context()
    before = details(before_ctx, execute(controller, before_ctx))
    updated = config
    pin = "sha256:" + "d" * 64
    if change == "repo_root":
        new_root = config.repo_root.with_name("repo-new")
        (new_root / "src").mkdir(parents=True)
        (new_root / "src/a.py").write_bytes((config.repo_root / "src/a.py").read_bytes())
        updated = replace(config, repo_root=new_root)
    elif change == "repo_key":
        updated = replace(config, repo_key="demo/other")
    elif change == "revision":
        updated = replace(config, repository_revision="fixture-revision-next")
    elif change == "roots":
        updated = replace(config, source_roots=("src", "tests"))
    elif change == "profile":
        updated = replace(config, profile_hash=pin)
    elif change == "config":
        updated = replace(config, config_hash=pin)
    elif change == "resolver":
        monkeypatch.setattr(m, "resolver_fingerprint", lambda: pin)
    else:
        original = m.legacy_profile
        # Synthetic fingerprint invalidation only; never claims rich-schema support.
        monkeypatch.setattr(m, "legacy_profile", lambda **kwargs: replace(original(**kwargs), schema_hash=pin))
    authority = context.authority
    parent = bind_context(authority, repo_root=updated.repo_root, lease_root=before_ctx.lease_root,
        output_root=config.output_root, request_id="changed-"+change, run_id="run", task_id="task",
        snapshot_hash=before_ctx.snapshot_hash, source_hash=source_inventory_hash(updated.repo_root),
        config_hash=updated.config_hash, deadline=time.time()+90)
    parent = authority.grant(parent, "build_or_update_graph", m.BuildRequest(repo_path=str(updated.repo_root)).input_hash())
    next_controller = m.GraphJobController(updated, storage_issuer=controller.storage_issuer)
    try:
        after = details(parent, execute(next_controller, parent))
        assert after["cache_mode"] == "COLD_BUILD"
        assert after["storage_snapshot_id"] != before["storage_snapshot_id"]
    finally:
        next_controller.close()


def test_non_python_source_change_gets_new_identity_without_fake_code_delta(jobs):
    _, controller, context, _, config = jobs
    ctx = context()
    before = details(ctx, execute(controller, ctx))
    (config.repo_root / "README.md").write_text("auxiliary source changed\n", encoding="utf-8")
    next_ctx = context()
    after = details(next_ctx, execute(controller, next_ctx))
    assert after["storage_snapshot_id"] != before["storage_snapshot_id"]
    assert after["graph_version"] == before["graph_version"]
    assert after["cache_mode"] == "WARM_UPDATE"
    assert after["cache_hits"] == 1
    assert not after["changed_files"] and not after["added_files"] and not after["deleted_files"]
