"""build_or_update_graph in build-server guide style: the agent builds, edits, rebuilds; read tools follow at once."""
from __future__ import annotations

import asyncio
import shutil

import pytest

from graph_fixture import FIXTURE_REPO
from vgar.graph.factory import create_graph_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server


@pytest.fixture
def served(tmp_path, monkeypatch):
    repo = tmp_path / FIXTURE_REPO.name
    shutil.copytree(FIXTURE_REPO, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "graphs" / "live.db"))
    monkeypatch.setenv("VGAR_REPOSITORY_ROOT", str(repo))
    monkeypatch.delenv("VGAR_GRAPH_VERSION", raising=False)
    monkeypatch.setattr(graph_server, "graph_service", create_graph_service())
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(graph_server, "_live_builder", None, raising=False)
    return repo


def build(path):
    return asyncio.run(graph_server.build_or_update_graph(str(path)))


def names(query):
    response = graph_server.search_symbols(query)
    return response, {row["name"] for row in (response["data"] or {}).get("symbols", [])}


def test_build_then_read_without_restart(served):
    before, _ = names("login")
    assert before["status"] == "ERROR" and before["error"]["code"] == "GRAPH_NOT_READY"
    assert "build_or_update_graph" in before["error"]["message"]
    built = build(served)
    assert built["status"] == "PASS", built
    assert built["data"]["mode"] == "cold" and built["data"]["nodes"] > 0
    after, found = names("login")
    assert after["status"] == "PASS" and "login" in found


def test_edit_then_rebuild_is_incremental_and_visible(served):
    build(served)
    target = next(p for p in sorted(served.rglob("*.py")) if "__pycache__" not in p.parts and p.stat().st_size > 0)
    target.write_text(target.read_text(encoding="utf-8") + "\n\ndef freshly_added_by_agent():\n    return 1\n",
                      encoding="utf-8")
    rebuilt = build(served)
    assert rebuilt["status"] == "PASS" and rebuilt["data"]["mode"] == "incremental"
    assert rebuilt["data"]["changed_files"] == [target.relative_to(served).as_posix()]
    _, found = names("freshly_added_by_agent")
    assert "freshly_added_by_agent" in found


def test_repo_path_must_resolve_to_the_configured_root(served, tmp_path, monkeypatch):
    other = tmp_path / "elsewhere"
    other.mkdir()
    refused = build(other)
    assert refused["status"] == "ERROR" and refused["error"]["code"] == "PATH_OUTSIDE_ROOT"
    monkeypatch.chdir(served.parent)
    assert build(served.name + "/")["status"] == "PASS"  # relative, trailing slash: same root
    assert build(str(served).upper())["status"] == "PASS"  # Windows paths are case-insensitive


def test_registered_build_provider_keeps_the_tv1_path(served, monkeypatch):
    calls = []

    async def respond_async(name, *args, **kwargs):
        calls.append(name)
        return {"status": "PASS", "data": {"tv1": True}}

    monkeypatch.setattr(graph_server, "_has_provider", lambda capability: capability == "build")
    monkeypatch.setattr(graph_server.core_tools, "respond_async", respond_async)
    assert build(served)["data"] == {"tv1": True} and calls == ["build_or_update_graph"]


def test_host_context_factory_keeps_the_tv1_path(served, monkeypatch):
    calls = []

    async def respond_async(name, *args, **kwargs):
        calls.append(name)
        return {"status": "PASS", "data": {"tv1": True}}

    monkeypatch.setattr(graph_server.core_tools, "context_factory", lambda operation, request: None)
    monkeypatch.setattr(graph_server.core_tools, "respond_async", respond_async)
    assert build(served)["data"] == {"tv1": True} and calls == ["build_or_update_graph"]
