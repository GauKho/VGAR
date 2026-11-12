"""Semantic full-build oracle and real incremental storage serving."""
import json
import sys
from pathlib import Path

import pytest
from test_graph_jobs import details, execute
from test_graph_jobs import jobs as jobs  # noqa: PLC0414 - explicitly re-export pytest fixture
from graph_fixture import real_graph_env


def read_document(controller, ctx, result):
    from vgar.graph.storage_capabilities import SnapshotGraphStore
    receipt = details(ctx, result)
    store = SnapshotGraphStore(ctx.output_root / receipt["manifest"], graph_version=result.result_snapshot_hash,
                               profiles=(controller.profile(),))
    return store.load_document(result.result_snapshot_hash)


def normalized(document):
    result = json.loads(json.dumps(document))
    result["statistics"].pop("build_time_ms", None)
    return result


def test_published_repository_metadata_refers_to_host_repo(jobs):
    from vgar.graph.storage_capabilities import SnapshotGraphStore
    _, controller, context, _, _ = jobs
    ctx = context()
    result = execute(controller, ctx)
    record = details(ctx, result)
    store = SnapshotGraphStore(ctx.output_root / record["manifest"], graph_version=result.result_snapshot_hash,
        profiles=(controller.profile(),))
    repository = next(n for n in store.load_document(result.result_snapshot_hash)["nodes"] if n["type"] == "Repository")
    assert repository["name"] == ctx.repo_root.name
    assert repository["properties"]["root_uri"] == ctx.repo_root.as_uri()


def test_effective_storage_profile_binds_config_and_implementation(jobs, monkeypatch):
    from dataclasses import replace
    m, controller, _, _, config = jobs
    old = controller.profile().profile_hash
    monkeypatch.setattr(m, "implementation_fingerprint", lambda: "sha256:" + "f" * 64)
    assert controller.profile().profile_hash != old
    different = m.GraphJobController(replace(config, config_hash="sha256:" + "e" * 64), storage_issuer=controller.storage_issuer)
    try:
        assert different.profile().profile_hash != controller.profile().profile_hash
    finally:
        different.close()


@pytest.mark.parametrize("change", ["modify", "add", "delete", "rename", "alias", "duplicate_name"])
def test_warm_update_equals_full_rebuild_on_bound_source(jobs, change):
    from vgar.graph.builder import PythonGraphBuilder
    _, controller, context, source, config = jobs
    other = source.with_name("b.py")
    other.write_text("from a import value\ndef caller():\n    return value()\n", encoding="utf-8")
    execute(controller, context())
    if change == "modify":
        source.write_text("def value():\n    return 2\n", encoding="utf-8")
    elif change == "add":
        source.with_name("c.py").write_text("def extra():\n    return 7\n", encoding="utf-8")
    elif change == "delete":
        other.unlink()
    elif change == "rename":
        other.rename(source.with_name("renamed.py"))
    elif change == "alias":
        source.write_text("class K:\n    def impl(self):\n        return 1\n    alias = impl\n", encoding="utf-8")
    else:
        source.with_name("c.py").write_text("def value():\n    return 7\n", encoding="utf-8")
    for iteration in range(2):
        ctx = context()
        result = execute(controller, ctx)
        actual = read_document(controller, ctx, result)
        full = PythonGraphBuilder(repo_key=config.repo_key, repository_revision=config.repository_revision,
                                  source_roots=config.source_roots).build(ctx.repo_root)
        assert normalized(actual) == normalized(full)
        if iteration == 0:
            # Subsequent update must not inherit link-phase mutations.
            source.write_text(source.read_text(encoding="utf-8") + "\n# another change\n", encoding="utf-8")


@pytest.mark.parametrize("server_python,mode", [
    (sys.executable, "2026-07-28"), (sys.executable, "legacy"),
    (str(Path(__file__).parents[2].parent / "environments/vgar-week78-cuda/Scripts/python.exe"), "legacy"),
], ids=["sdk2-modern", "sdk2-legacy", "sdk1-legacy"])
def test_real_build_update_and_snapshot_read_over_stdio(server_python, mode, tmp_path):
    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    from test_runtime_lifecycle import alive

    root = tmp_path / "fixture"
    repo = root / "repo"
    params = StdioServerParameters(command=server_python,
        args=["-B", str(Path(__file__).parents[1]/"fixtures/mcp_server/graph_jobs_fixture_server.py"), "--root", str(root)],
        env={"PYTHONPATH": str(Path(__file__).parents[2]/"src"), "PYTHONUTF8": "1",
             "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1", **real_graph_env()})
    rows = []
    async def run():
        with anyio.fail_after(60):
            async with Client(params, mode=mode) as client:
                assert len((await client.list_tools()).tools) == 11
                for iteration in range(3):
                    if iteration == 2:
                        path = repo / "src/a.py"
                        path.write_text(path.read_text(encoding="utf-8") + "\ndef added():\n    return value()\n", encoding="utf-8")
                    result = await client.call_tool("build_or_update_graph", {"repo_path": str(repo)})
                    assert not result.is_error
                    payload = json.loads(result.content[0].text)
                    assert payload["status"] == "PASS", payload
                    data = payload["data"]
                    assert data["published"] and data["capabilities"] == ["legacy_static_python"]
                    evidence = root / "output" / data["evidence"][0]["path"]
                    receipt = json.loads(evidence.read_bytes())
                    rows.append(receipt)
                    resource = await client.read_resource("vgar://repo/summary")
                    summary = json.loads(resource.contents[0].text)
                    assert summary["graph_version"] == data["result_snapshot_hash"]
                denied = await client.call_tool("build_or_update_graph", {"repo_path": str(root)})
                assert json.loads(denied.content[0].text)["status"] == "ERROR"
    anyio.run(run)
    assert [r["cache_mode"] for r in rows] == ["COLD_BUILD", "SNAPSHOT_REUSE", "WARM_UPDATE"]
    assert not alive(rows[-1]["worker_pid"])
    assert not list((root / "output").glob(".graph-worker-*"))
    (tmp_path / "graph-wire.json").write_text(json.dumps({"fixture_input": True, "provider": "real-static-builder",
        "server_python": server_python, "mode": mode, "receipts": rows}, indent=2), encoding="utf-8")
