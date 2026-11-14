"""Context budget of get_related_context and the token counter of the MCP servers.

Spec: docs/superpowers/specs/2026-11-14-context-budget-and-token-counter-design.md (D1-D5).
"""
from __future__ import annotations

import json

import anyio
import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.factory import create_graph_service
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.token_counter import FALLBACK_COUNTER_LABEL, bytes_div4_counter
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server


def _ingest(repo, database):
    document = PythonGraphBuilder(repo_key="demo/budget", repository_revision="fixture").build(repo)
    SQLiteGraphStore(database).ingest(document)
    return document


@pytest.fixture
def repo_env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text('def login():\n    return "café"\n', encoding="utf-8")
    database = tmp_path / "graph.db"
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_REPOSITORY_ROOT", str(repo))
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(database))
    monkeypatch.delenv("VGAR_GRAPH_VERSION", raising=False)
    return repo, _ingest(repo, database)


def test_factory_counts_bytes_without_tokenizer(repo_env, monkeypatch):
    monkeypatch.delenv("VGAR_TOKENIZER_MANIFEST", raising=False)
    service = create_graph_service()
    assert service.count_tokens is bytes_div4_counter
    assert service.counter_label == "FALLBACK:utf8_bytes_ceil_div4"
    repo, document = repo_env
    anchor = next(n["id"] for n in document["nodes"] if n["type"] == "Function")
    result = service.get_related_context([anchor], 1000, graph_version=document["graph_version"], task_id="t")
    assert result["context"]["items"] and result["counter_label"] == "FALLBACK:utf8_bytes_ceil_div4"


def test_factory_ignores_a_stale_tokenizer_variable(repo_env, monkeypatch):
    monkeypatch.setenv("VGAR_TOKENIZER_MANIFEST", str(repo_env[0] / "missing_manifest.json"))
    service = create_graph_service()
    assert service.counter_label == "FALLBACK:utf8_bytes_ceil_div4"


# --------------------------------------------------------------------------- default and ceiling of the tool
@pytest.fixture
def big_server(tmp_path, monkeypatch):
    """20 functions of about 4000 bytes each: well above 12000 bytes/4 tokens in total."""
    repo = tmp_path / "repo"
    repo.mkdir()
    body = "".join(f'def f{i}():\n    """{"x" * 4000}"""\n    return {i}\n\n\n' for i in range(20))
    (repo / "app.py").write_text(body, encoding="utf-8")
    database = tmp_path / "graph.db"
    document = _ingest(repo, database)
    service = SQLiteGraphService(SQLiteGraphStore(database), repository_root=repo,
                                 count_tokens=bytes_div4_counter, counter_label=FALLBACK_COUNTER_LABEL)
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(audit))
    anchors = [n["id"] for n in document["nodes"] if n["type"] == "Function"]
    return anchors, document["graph_version"], audit


def _budget(response):
    assert response["status"] == "PASS", response
    return response["data"]["diagnostics"]["budget"], response["data"]["context"]["total_token_count"]


def test_budget_defaults_to_12000(big_server):
    anchors, version, _ = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t"))
    assert budget == {"requested": 12000, "effective": 12000, "ceiling": 12000, "clamped": False}
    assert 0 < total <= 12000


def test_budget_above_ceiling_is_clamped_and_audited(big_server):
    anchors, version, audit = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t",
                                                             budget_tokens=50000))
    assert budget == {"requested": 50000, "effective": 12000, "ceiling": 12000, "clamped": True}
    assert total <= 12000
    record = [json.loads(line)["payload"] for line in audit.read_text(encoding="utf-8").splitlines()][-1]
    assert record["tool"] == "get_related_context"
    assert record["budget_tokens"] == 50000 and record["effective_budget_tokens"] == 12000


def test_budget_below_ceiling_is_kept(big_server):
    anchors, version, _ = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t",
                                                             budget_tokens=4000))
    assert budget["effective"] == 4000 and budget["clamped"] is False and total <= 4000


def test_budget_at_ceiling_is_not_clamped(big_server):
    anchors, version, _ = big_server
    budget, _ = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t",
                                                         budget_tokens=12000))
    assert budget["clamped"] is False


@pytest.mark.parametrize("bad", [0, -1, True])
def test_invalid_budget_is_rejected(big_server, bad):
    anchors, version, _ = big_server
    response = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=bad)
    assert response["error"]["code"] == "INVALID_LIMIT"


def test_schema_makes_budget_optional_with_default():
    async def schema():
        tools = await graph_server.mcp.list_tools()
        return next(t for t in tools if t.name == "get_related_context").input_schema

    found = anyio.run(schema)
    assert found["properties"]["budget_tokens"]["default"] == 12000
    assert "budget_tokens" not in found.get("required", [])


@pytest.mark.parametrize("bad", [True, "5000", 5000.5])
def test_mcp_call_rejects_a_non_integer_budget(big_server, bad):
    """Through the SDK, lax validation would turn true into 1 and "5000" into 5000 (final review, Important #1)."""
    anchors, version, _ = big_server

    async def call():
        return await graph_server.mcp.call_tool("get_related_context", {
            "anchor_ids": anchors, "graph_version": version, "task_id": "t", "budget_tokens": bad})

    try:
        result = anyio.run(call)
    except Exception:  # noqa: BLE001 - the SDK may raise its validation error
        return
    assert getattr(result, "is_error", False) or getattr(result, "isError", False), result
