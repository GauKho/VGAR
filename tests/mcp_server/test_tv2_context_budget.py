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
from vgar.mcp.agent_output import agent_context, compact_json
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
def _serve_repo(tmp_path, monkeypatch, source: str):
    """Serve ``source`` as app.py; returns the Function anchors, the graph version and the audit path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(source, encoding="utf-8")
    database = tmp_path / "graph.db"
    document = _ingest(repo, database)
    service = SQLiteGraphService(SQLiteGraphStore(database), repository_root=repo,
                                 count_tokens=bytes_div4_counter, counter_label=FALLBACK_COUNTER_LABEL)
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(audit))
    anchors = [n["id"] for n in document["nodes"] if n["type"] == "Function"]
    return anchors, document["graph_version"], audit


@pytest.fixture
def big_server(tmp_path, monkeypatch):
    """20 functions of about 4000 bytes each: well above 12000 bytes/4 tokens in total."""
    body = "".join(f'def f{i}():\n    """{"x" * 4000}"""\n    return {i}\n\n\n' for i in range(20))
    return _serve_repo(tmp_path, monkeypatch, body)


def _budget(response):
    assert response["status"] == "PASS", response
    return response["data"]["diagnostics"]["budget"], response["data"]["context"]["total_token_count"]


def test_budget_defaults_to_4000(big_server):
    anchors, version, _ = big_server
    budget, total = _budget(graph_server.get_related_context(anchors, graph_version=version, task_id="t"))
    assert budget == {"requested": 4000, "effective": 4000, "ceiling": 12000, "clamped": False}
    assert 0 < total <= 4000


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
    assert found["properties"]["budget_tokens"]["default"] == 4000
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


# --------------------------------------------------------------------------- agent shape and 32 KiB limit (spec 2026-11-24 §4.2)
def _size(value) -> int:
    return len(compact_json(value).encode("utf-8"))


def test_items_have_the_agent_fields(big_server):
    anchors, version, _ = big_server
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t")["data"]
    assert data["context_format"] == "vgar.context.agent.v1" and "source_metadata" not in data
    for item in data["context"]["items"]:
        assert list(item) == ["node_id", "path", "lines", "score", "distance", "why", "snippet"]
        assert item["lines"][0] <= item["lines"][1] and item["score"] == round(item["score"], 3)


def test_why_names_relations_by_qualified_name(tmp_path, monkeypatch):
    anchors, version, _ = _serve_repo(tmp_path, monkeypatch, "def a():\n    return b()\n\n\ndef b():\n    return 1\n")
    a = next(n for n in anchors if n.endswith(":app.a"))
    items = graph_server.get_related_context([a], graph_version=version, task_id="t")["data"]["context"]["items"]
    assert next(i["why"] for i in items if i["node_id"].endswith(":app.b")) == ["TASK_ANCHOR", "CALLS app.a -> app.b"]


def test_response_is_capped_at_32_kib_by_dropping_the_lowest_ranked_items(big_server):
    anchors, version, audit = big_server
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=12000)["data"]
    full = graph_server.graph_service.get_related_context(anchors, 12000, graph_version=version,
                                                          task_id="t")["context"]["items"]
    kept, limit = data["context"]["items"], data["diagnostics"]["response_limit"]
    assert _size(data) <= 32768
    assert [i["node_id"] for i in kept] == [i["node_id"] for i in full[:len(kept)]]
    assert limit["limit_bytes"] == 32768 and limit["dropped_items"] == len(full) - len(kept) > 0
    assert limit["over_limit"] is False
    assert data["context"]["truncated"] is True
    assert data["context"]["total_token_count"] == sum(i["token_count"] for i in full[:len(kept)])
    payload = [json.loads(line)["payload"] for line in audit.read_text(encoding="utf-8").splitlines()][-1]
    assert payload["response_bytes"] == _size(data) and payload["dropped_items"] == limit["dropped_items"]


def test_budget_truncation_adds_a_hint(big_server):
    anchors, version, _ = big_server
    diagnostics = graph_server.get_related_context(anchors, graph_version=version, task_id="t")["data"]["diagnostics"]
    assert "budget_tokens can go up to 12000" in diagnostics["budget_hint"] and "response_limit" not in diagnostics


def test_a_budget_smaller_than_any_snippet_returns_no_items_and_a_hint(big_server):
    anchors, version, _ = big_server
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=1)["data"]
    assert data["context"]["items"] == [] and data["context"]["truncated"] is True
    assert "budget_hint" in data["diagnostics"] and "response_limit" not in data["diagnostics"]


def test_one_item_larger_than_the_limit_is_returned_whole(tmp_path, monkeypatch):
    anchors, version, _ = _serve_repo(tmp_path, monkeypatch, f'def huge():\n    """{"x" * 40000}"""\n')
    data = graph_server.get_related_context(anchors, graph_version=version, task_id="t", budget_tokens=12000)["data"]
    assert len(data["context"]["items"]) == 1
    assert data["diagnostics"]["response_limit"]["over_limit"] is True
    assert data["diagnostics"]["response_limit"]["dropped_items"] == 0


def test_why_shows_the_qualified_name_of_a_renamed_duplicate():
    duplicate = "vgar:r:python:function:a.py:a.f@definition:3:0"
    item = {"node_id": duplicate, "path": "a.py", "symbol": "a.f", "snippet": "def f(): ...",
            "range": {"start_line": 3, "start_col": 0, "end_line": 4, "end_col": 9}, "relevance_score": 0.12345,
            "graph_distance": 1, "confidence": 1.0, "token_count": 3,
            "graph_rationale": ["TASK_ANCHOR", f"CALLS:vgar:r:python:function:b.py:b.g->{duplicate}"]}
    data = {"context_format": "vgar.context.v1", "source_metadata": {}, "diagnostics": {},
            "context": {"anchor_ids": [], "items": [item], "total_token_count": 3, "token_budget": 4000, "truncated": False}}
    assert agent_context(data)["context"]["items"][0] == {
        "node_id": duplicate, "path": "a.py", "lines": [3, 4], "score": 0.123, "distance": 1,
        "why": ["TASK_ANCHOR", "CALLS b.g -> a.f"], "snippet": "def f(): ..."}


def test_a_too_large_top_item_after_drops_gets_the_over_limit_hint():
    """Final review: dropping items first then finding the top one too large must not say "kept under 32 KiB"."""
    def item(name, snippet):
        return {"node_id": f"vgar:r:python:function:a.py:a.{name}", "path": "a.py", "symbol": f"a.{name}",
                "snippet": snippet, "range": {"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 0},
                "relevance_score": 0.5, "graph_distance": 0, "confidence": 1.0, "token_count": len(snippet) // 4,
                "graph_rationale": ["TASK_ANCHOR"]}
    data = {"context_format": "vgar.context.v1", "source_metadata": {}, "diagnostics": {},
            "context": {"anchor_ids": [], "items": [item("big", "x" * 40000), item("small", "y")],
                        "total_token_count": 10000, "token_budget": 12000, "truncated": False}}
    limit = agent_context(data)["diagnostics"]["response_limit"]
    assert limit["over_limit"] is True and limit["dropped_items"] == 1
    assert limit["hint"] == "the top-ranked item alone is larger than 32 KiB; it is returned whole"
