"""Task-isolated W6 MCP boundary over real persisted M1 snapshots."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

from vgar.contracts.context import ContextPayload
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server


@pytest.fixture
def graph(tmp_path, monkeypatch):
    source = tmp_path / "repo"
    (source / "src").mkdir(parents=True)
    (source / "src/demo.py").write_text("def answer():\n    return 0\n\ndef other():\n    return 1\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="fixture", repository_revision="base", use_jedi=False).build(source)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    # Reopen so no process-local M1 builder/document state can make this pass.
    monkeypatch.setattr(graph_server, "graph_service", SQLiteGraphService(SQLiteGraphStore(store.database_path)))
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    return source, document, store, tmp_path / "audit.jsonl"


@pytest.mark.parametrize("tool", ["get_callers", "get_callees"])
@pytest.mark.parametrize("depth", [0, 2, -1, True])
def test_relation_depth_is_not_echoed_without_real_traversal(graph, tool, depth):
    iid = next(n["id"] for n in graph[1]["nodes"] if n["name"] == "answer" and n["type"] == "Function")
    response = getattr(graph_server, tool)(iid, depth=depth)
    assert response["status"] == "ERROR" and response["error"]["code"] == "INVALID_LIMIT"


@pytest.mark.parametrize("resource", ["graph_node", "graph_subgraph"])
def test_resource_decodes_percent_encoded_real_graph_node(graph, resource):
    iid = next(n["id"] for n in graph[1]["nodes"] if n["name"] == "answer" and n["type"] == "Function")
    value = json.loads(getattr(graph_server, resource)(quote(iid, safe="")))
    assert value["repo"]["node_id"] == iid if resource == "graph_node" else value["anchor_id"] == iid


def service(graph):
    source, _, store, _ = graph
    return SQLiteGraphService(SQLiteGraphStore(store.database_path), source_root=source,
                              count_tokens=lambda text: len(text.split()), counter_label="fixture-words")


def test_sqlite_roundtrip_preserves_full_snapshot_source_ranges_and_language(graph):
    store = SQLiteGraphStore(graph[2].database_path)
    assert store.get_graph_document() == graph[1]


def test_task_handles_survive_service_recreation_and_do_not_mix_issues(graph):
    first = service(graph)
    a = first.find_task_anchors("demo.answer returns wrong value")
    b = first.find_task_anchors("demo.answer must return a different value")
    assert a["task_handle"] != b["task_handle"] and a["anchor_ids"] == b["anchor_ids"]
    second = service(graph)
    one = second.get_related_context(a["anchor_ids"], 1000, a["task_handle"])
    two = second.get_related_context(b["anchor_ids"], 1000, b["task_handle"])
    assert one.context.graph_version == two.context.graph_version == graph[1]["graph_version"]
    assert one.overlay_id != two.overlay_id
    assert one.context.total_token_count <= 1000 and one.context.items
    assert graph[2].get_graph_document() == graph[1], "task overlays must not change repository graph"


def test_mcp_tools_return_frozen_context_and_task_diagnostics_in_metadata(graph, monkeypatch):
    monkeypatch.setattr(graph_server, "graph_service", service(graph))
    found = graph_server.find_task_anchors("demo.answer wrong value")
    assert found["status"] == "PASS" and found["data"]["graph_version"] == graph[1]["graph_version"]
    response = graph_server.get_related_context(found["data"]["anchor_ids"], 1000, found["data"]["task_handle"])
    payload = ContextPayload.model_validate(response["data"])
    assert response["status"] == "PASS" and payload.items
    assert response["metadata"]["task_handle"] == found["data"]["task_handle"]
    assert response["metadata"]["counter_label"] == "fixture-words"
    events = [json.loads(line)["payload"] for line in graph[3].read_text().splitlines()]
    assert {e["tool"] for e in events} == {"find_task_anchors", "get_related_context"}


def test_unknown_handle_bad_anchors_budget_and_stale_source_fail_closed(graph):
    from vgar.contracts.error import GraphError
    s = service(graph)
    found = s.find_task_anchors("demo.answer wrong value")
    for anchors, budget, handle in [(found["anchor_ids"], 100, "unknown"), (["unknown"], 100, found["task_handle"]),
                                  (found["anchor_ids"], 0, found["task_handle"])]:
        with pytest.raises((GraphError, ValueError)):
            s.get_related_context(anchors, budget, handle)
    (graph[0] / "src/demo.py").write_text("def answer(): return 42\n", encoding="utf-8")
    with pytest.raises(GraphError):
        s.get_related_context(found["anchor_ids"], 1000, found["task_handle"])


def test_handle_from_prior_graph_version_is_rejected_not_rebound(graph):
    from vgar.contracts.error import GraphError
    old = service(graph).find_task_anchors("demo.answer wrong value")
    (graph[0] / "src/demo.py").write_text("def answer(): return 42\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="fixture", repository_revision="next", use_jedi=False).build(graph[0])
    graph[2].ingest(document)
    with pytest.raises(GraphError):
        service(graph).get_related_context(old["anchor_ids"], 1000, old["task_handle"])


def test_no_anchor_is_empty_context_with_diagnostics_not_fake_match(graph):
    s = service(graph)
    found = s.find_task_anchors("missing_file.py:20")
    assert found["anchor_ids"] == [] and found["unmatched_locations"]
    assert s.get_related_context([], 1000, found["task_handle"]).context.items == []


@pytest.mark.parametrize("mutation", ["issue_text", "anchor_ids"])
def test_persisted_task_context_tamper_is_rejected(graph, mutation):
    from vgar.contracts.error import GraphError
    s = service(graph)
    found = s.find_task_anchors("demo.answer wrong value")
    with graph[2]._connect() as connection:
        row = connection.execute("SELECT context_json FROM task_contexts WHERE task_handle=?", (found["task_handle"],)).fetchone()
        data = json.loads(row["context_json"])
        data[mutation] = "different issue" if mutation == "issue_text" else []
        connection.execute("UPDATE task_contexts SET context_json=? WHERE task_handle=?", (json.dumps(data), found["task_handle"]))
    with pytest.raises(GraphError, match="integrity"):
        s.get_related_context(found["anchor_ids"], 1000, found["task_handle"])


def test_demo_backend_reports_retrieval_unavailable_not_fake_evidence(tmp_path, monkeypatch):
    from vgar.graph.demo_service import DemoGraphService
    monkeypatch.setattr(graph_server, "graph_service", DemoGraphService())
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    result = graph_server.find_task_anchors("login fails")
    assert result["status"] == "ERROR" and result["error"]["code"] == "GRAPH_NOT_READY"


def test_real_stateless_stdio_and_langchain_context_display(tmp_path):
    from vgar.evaluation.retrieval.evidence import new_run, write_json, utc_now
    root = Path(__file__).resolve().parents[1]
    directory, record = new_run(root / "artifacts/fixes/w3-w6", "milestone-6-stdio-wrapper")
    argv = [sys.executable, "-B", str(root / "scripts/smoke_w5_w6.py"), "--allow-fallback-counter",
            "--output-root", str(directory / "transport")]
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    completed = subprocess.run(argv, cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=110)
    record.update(command_argv=argv, stdout=completed.stdout, stderr=completed.stderr,
                  exit_code=completed.returncode, status="PASS" if completed.returncode == 0 else "ERROR",
                  complete=True, ended_utc=utc_now(), inference="NOT_RUN")
    write_json(directory / "result.json", record)
    assert completed.returncode == 0, f"{directory}: {completed.stdout}\n{completed.stderr}"
    run = next((directory / "transport").iterdir())
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS" and result["source_hash_before"] == result["source_hash_after"]
    assert result["inference"] == "NOT_RUN" and result["counter_is_fallback"]
    assert (run / "CONTEXT.md").is_file() and (run / "context.json").is_file()
    calls = result["calls"]
    assert len(calls) == 6 and calls[-1]["response"]["status"] == "ERROR"
    assert calls[2]["response"]["data"] == calls[4]["response"]["data"]
