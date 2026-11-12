"""The agent builds and updates the graph through MCP (proposal §10.3, §10.5, §11; plan L6-6).

Spec: docs/superpowers/specs/2026-11-12-agent-builds-graph-design.md
"""
from __future__ import annotations

import pytest

from graph_fixture import FIXTURE_REPO
from vgar.contracts.error import GraphNotReadyError
from vgar.graph.factory import create_graph_service


# ------------------------------------------------------------------ Task 1: server starts without a graph
def test_server_starts_without_a_database_when_the_repo_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "g" / "graph.db"))
    monkeypatch.setenv("VGAR_REPOSITORY_ROOT", str(FIXTURE_REPO))
    monkeypatch.delenv("VGAR_GRAPH_VERSION", raising=False)
    service = create_graph_service()
    with pytest.raises(GraphNotReadyError, match="build_or_update_graph"):
        service.get_repository_summary()


def test_missing_database_without_repo_root_still_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "missing.db"))
    monkeypatch.delenv("VGAR_REPOSITORY_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="Graph database not found"):
        create_graph_service()


# ------------------------------------------------------------------ Task 2: LiveGraphBuilder
import shutil  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from vgar.graph.indexing import index_repo  # noqa: E402
from vgar.graph.sqlite_store import SQLiteGraphStore  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    target = tmp_path / FIXTURE_REPO.name
    shutil.copytree(FIXTURE_REPO, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return target


def _python_file(root):
    return next(p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts and p.stat().st_size > 0)


def _index_version(repo, tmp_path, name):
    database = tmp_path / f"{name}.db"
    index_repo(repo, database)
    return SQLiteGraphStore(database).resolve_graph_version()


def test_cold_build_matches_vgar_index(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    result = LiveGraphBuilder(repo, tmp_path / "live.db").run()
    assert result["mode"] == "cold" and result["previous_graph_version"] is None and result["nodes"] > 0
    assert result["graph_version"] == _index_version(repo, tmp_path, "index")
    assert SQLiteGraphStore(tmp_path / "live.db").resolve_graph_version() == result["graph_version"]


def test_edit_gives_incremental_update_equal_to_a_rebuild(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    live = LiveGraphBuilder(repo, tmp_path / "live.db")
    first = live.run()
    target = _python_file(repo)
    target.write_text(target.read_text(encoding="utf-8") + "\n\ndef added_by_agent():\n    return 1\n", encoding="utf-8")
    second = live.run()
    assert second["mode"] == "incremental" and second["unchanged"] is False
    assert second["changed_files"] == [target.relative_to(repo).as_posix()]
    assert second["previous_graph_version"] == first["graph_version"]
    assert second["graph_version"] == _index_version(repo, tmp_path, "rebuilt")


def test_second_run_without_changes_is_unchanged(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    live = LiveGraphBuilder(repo, tmp_path / "live.db")
    first, second = live.run(), live.run()
    assert second["unchanged"] is True and second["changed_files"] == []
    assert second["graph_version"] == first["graph_version"]


def test_concurrent_runs_are_serialized(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    live, results, errors = LiveGraphBuilder(repo, tmp_path / "live.db"), [], []
    active, overlap = [0], [False]
    original = live._compute

    def watched(*args, **kwargs):
        active[0] += 1
        overlap[0] = overlap[0] or active[0] > 1
        try:
            time.sleep(0.2)
            return original(*args, **kwargs)
        finally:
            active[0] -= 1

    live._compute = watched

    def call():
        try:
            results.append(live.run())
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=call) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    assert errors == [] and len(results) == 2 and not overlap[0]
    assert len({r["graph_version"] for r in results}) == 1


def test_syntax_error_file_does_not_kill_the_server(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    live = LiveGraphBuilder(repo, tmp_path / "live.db")
    live.run()
    (repo / "broken_by_agent.py").write_text("def broken(:\n", encoding="utf-8")
    try:
        live.run()
    except Exception as error:  # noqa: BLE001 - an error is acceptable, a dead builder is not
        assert str(error)
    (repo / "broken_by_agent.py").unlink()
    assert live.run()["graph_version"] == _index_version(repo, tmp_path, "after")


def test_deleted_database_triggers_a_cold_rebuild(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    live = LiveGraphBuilder(repo, tmp_path / "live.db")
    first = live.run()
    (tmp_path / "live.db").unlink()
    again = live.run()
    assert again["mode"] == "cold" and again["graph_version"] == first["graph_version"]
    assert SQLiteGraphStore(tmp_path / "live.db").resolve_graph_version() == first["graph_version"]


def test_timeout_releases_the_lock(repo, tmp_path):
    from vgar.graph.live_build import LiveGraphBuilder

    live = LiveGraphBuilder(repo, tmp_path / "live.db", timeout_seconds=0.2)
    original = live._compute
    live._compute = lambda *a, **k: (time.sleep(1.0), original(*a, **k))[1]
    from vgar.mcp.schemas import CodedToolError
    with pytest.raises(CodedToolError):
        live.run()
    live._compute, live.timeout_seconds = original, 120
    assert live.run()["mode"] == "cold"


# ------------------------------------------------------------------ Task 4: host configuration examples
import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _load(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonc":
        text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
        text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def test_host_examples_declare_three_servers_with_absolute_paths():
    examples = {"claude-desktop.example.json": ("mcpServers", "command", "args", "env"),
                "mcp.example.json": ("mcpServers", "command", "args", "env"),
                "opencode.example.jsonc": ("servers", "command", None, "environment")}
    for name, (key, command_key, args_key, env_key) in examples.items():
        data = _load(ROOT / "configs/mcp_server" / name)
        servers = data["mcp"][key] if name.startswith("opencode") else data[key]
        assert set(servers) == {"vgar-graph", "vgar-execution", "vgar-repository"}, name
        for server_name, server in servers.items():
            command = server[command_key][0] if args_key is None else server[command_key]
            assert command.startswith("<ABSOLUTE"), (name, server_name)
            module_args = server[command_key][1:] if args_key is None else server[args_key]
            assert module_args == ["-m", f"vgar.mcp.servers.{server_name.removeprefix('vgar-')}_server"], (name, server_name)
            env = server[env_key]
            # Absolute audit path: the default logs/ is relative to the host's working directory (the user's repo).
            assert env.get("VGAR_MCP_AUDIT_LOG", "").startswith("<ABSOLUTE"), (name, server_name)
            if server_name != "vgar-repository":
                assert {"VGAR_GRAPH_BACKEND", "VGAR_GRAPH_DATABASE", "VGAR_REPOSITORY_ROOT"} <= set(env), (name, server_name)
            else:
                assert "VGAR_LEASE_ROOT" in env, name


# ------------------------------------------------------------------ final review fixes
def test_reverting_an_edit_serves_the_reverted_graph(repo, tmp_path):
    # C1: going back to earlier content must not leave read tools on the edited graph.
    from vgar.graph.live_build import LiveGraphBuilder

    database = tmp_path / "live.db"
    live = LiveGraphBuilder(repo, database)
    original = live.run()["graph_version"]
    target = _python_file(repo)
    original_bytes = target.read_bytes()  # bytes: write_text would turn LF into CRLF on Windows
    target.write_bytes(original_bytes + b"\n\ndef reverted_later():\n    return 1\n")
    live.run()
    target.write_bytes(original_bytes)
    back = live.run()
    store = SQLiteGraphStore(database)
    assert back["graph_version"] == original == store.resolve_graph_version()
    assert not store.search_symbols("reverted_later", 10)


def test_only_the_current_snapshot_is_kept(repo, tmp_path):
    # I4: every edit used to add a full snapshot forever.
    import sqlite3

    from vgar.graph.live_build import LiveGraphBuilder

    database = tmp_path / "live.db"
    live = LiveGraphBuilder(repo, database)
    live.run()
    target = _python_file(repo)
    for number in range(3):
        target.write_text(target.read_text(encoding="utf-8") + f"\n\ndef edit_{number}():\n    return {number}\n",
                          encoding="utf-8")
        current = live.run()["graph_version"]
    with sqlite3.connect(database) as connection:
        versions = [row[0] for row in connection.execute("SELECT graph_version FROM graph_metadata")]
        orphans = connection.execute("SELECT COUNT(*) FROM nodes WHERE graph_version != ?", (current,)).fetchone()[0]
    assert versions == [current] and orphans == 0


def test_timeout_is_a_coded_tool_error_and_the_late_result_is_reused(repo, tmp_path):
    # I1: TIMEOUT, not INTERNAL_ERROR. I2: the worker keeps the lock; the next call waits for and reuses its result.
    from vgar.graph.live_build import LiveGraphBuilder
    from vgar.mcp.schemas import TIMEOUT, CodedToolError

    live = LiveGraphBuilder(repo, tmp_path / "live.db", timeout_seconds=0.3)
    computed = []
    original = live._compute

    def slow(*args, **kwargs):
        time.sleep(1.0)
        computed.append(1)
        return original(*args, **kwargs)

    live._compute = slow
    with pytest.raises(CodedToolError) as raised:
        live.run()
    assert raised.value.code == TIMEOUT
    live.timeout_seconds = 30
    result = live.run()
    assert result["mode"] == "cold" and len(computed) == 1  # no second full build
