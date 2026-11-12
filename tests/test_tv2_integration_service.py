"""SQLiteGraphService functions that the guide-style MCP tools call (spec §7.1, §7.4).

Expected call facts are written by hand from tests/fixtures/vgar-arch-cases/multi_package:
app/service.py login -> normalize, _audit, load_user; _audit -> save_user;
db/store.py load_user -> Store, Store.put; Store.put -> normalize.
"""
from __future__ import annotations

import pytest

from graph_fixture import fixture_service


def _service(tmp_path, **kwargs):
    service = fixture_service(tmp_path / "graph")
    for key, value in kwargs.items():
        setattr(service, key, value)
    return service, service.get_repository_summary().graph_version


def test_document_is_loaded_once_per_version(tmp_path, monkeypatch):
    service, version = _service(tmp_path)
    calls = []
    original = service.store.load_document
    monkeypatch.setattr(service.store, "load_document", lambda value: calls.append(value) or original(value))
    service.find_task_anchors("app/service.py login fails", graph_version=version, task_id="t1")
    service.find_task_anchors("app/service.py login fails", graph_version=version, task_id="t2")
    service.get_related_tests([], graph_version=version, changed_paths=["app/service.py"])
    assert calls == [version]


def test_cache_never_serves_another_version(tmp_path):
    service, version = _service(tmp_path)
    service._document(version)
    with pytest.raises(Exception):
        service._document("sha256:" + "0" * 64)


def test_related_context_output_is_unchanged_by_the_cache(tmp_path):
    service, version = _service(tmp_path, count_tokens=len, counter_label="test:characters")
    anchors = service.find_task_anchors("login in app/service.py", graph_version=version, task_id="t")["anchors"]
    anchor_ids = [anchor["node_id"] for anchor in anchors][:3]
    first = service.get_related_context(anchor_ids, 2000, graph_version=version, task_id="t", issue_text="login")
    second = service.get_related_context(anchor_ids, 2000, graph_version=version, task_id="t", issue_text="login")
    fresh, _ = _service(tmp_path / "fresh", count_tokens=len, counter_label="test:characters")
    third = fresh.get_related_context(anchor_ids, 2000, graph_version=version, task_id="t", issue_text="login")
    assert first["context"] == second["context"] == third["context"]


# --- Task 3: traverse and explain_dependency_path -------------------------------------------------

def _ids(service, version):
    return {node["qualified_name"]: node["id"] for node in service._document(version)["nodes"]
            if node["type"] in {"Function", "Method", "Class", "Test"}}


def test_traverse_hop_one_matches_direct_callers(tmp_path):
    service, version = _service(tmp_path)
    ids = _ids(service, version)
    target = ids["app.parser.normalize"]
    direct = [symbol.symbol_id for symbol in service.get_callers(target).symbols]
    result = service.traverse(target, "callers", depth=1)
    assert [item["symbol_id"] for item in result["symbols"] if item["hop"] == 1] == direct
    assert set(direct) == {ids["app.service.login"], ids["db.store.Store.put"]}


def test_traverse_depth_two_reaches_callers_of_callers(tmp_path):
    service, version = _service(tmp_path)
    ids = _ids(service, version)
    result = service.traverse(ids["app.parser.normalize"], "callers", depth=2)
    hop_two = {item["symbol_id"]: item["via"] for item in result["symbols"] if item["hop"] == 2}
    assert hop_two == {ids["tests.test_service.test_login"]: ids["app.service.login"]}
    assert result["truncated"] is False


def test_callees_list_may_call_separately(tmp_path):
    service, version = _service(tmp_path)
    ids = _ids(service, version)
    result = service.traverse(ids["app.service.login"], "callees", depth=2)
    by_hop = {}
    for item in result["symbols"]:
        by_hop.setdefault(item["hop"], set()).add(item["symbol_id"])
    assert by_hop[1] == {ids["app.parser.normalize"], ids["app.service._audit"], ids["db.store.load_user"]}
    assert by_hop[2] == {ids["db.store.save_user"], ids["db.store.Store"]}
    assert [(item["symbol_id"], item["via"], item["hop"]) for item in result["may_call"]] == [
        (ids["db.store.Store.put"], ids["db.store.load_user"], 2)]
    assert 0 < result["may_call"][0]["confidence"] < 1
    assert ids["db.store.Store.put"] not in {item["symbol_id"] for item in result["symbols"]}


def test_traverse_reports_truncation(tmp_path):
    service, version = _service(tmp_path)
    result = service.traverse(_ids(service, version)["app.service.login"], "callees", depth=5, max_nodes=1)
    assert result["truncated"] is True and len(result["symbols"]) == 1


def test_traverse_unknown_symbol_is_not_found(tmp_path):
    from vgar.contracts.error import NodeNotFoundError
    service, _ = _service(tmp_path)
    with pytest.raises(NodeNotFoundError):
        service.traverse("missing:symbol", "callers", depth=2)


def test_path_follows_typed_edges(tmp_path):
    service, version = _service(tmp_path)
    ids = _ids(service, version)
    result = service.explain_dependency_path(ids["app.service.login"], ids["db.store.save_user"])
    assert result["found"] is True
    assert result["nodes"][0] == ids["app.service.login"] and result["nodes"][-1] == ids["db.store.save_user"]
    assert [edge["edge_type"] for edge in result["edges"]] == ["CONTAINS", "CALLS", "CONTAINS", "CALLS"]
    assert all(edge["source_id"] == result["nodes"][index] and edge["target_id"] == result["nodes"][index + 1]
               for index, edge in enumerate(result["edges"]))


def test_path_absent_returns_found_false(tmp_path):
    service, version = _service(tmp_path)
    ids = _ids(service, version)
    result = service.explain_dependency_path(ids["db.store.save_user"], ids["app.service.login"])
    assert result["found"] is False and result["nodes"] == [] and result["edges"] == []


def test_path_respects_the_hop_limit(tmp_path):
    service, version = _service(tmp_path)
    ids = _ids(service, version)
    result = service.explain_dependency_path(ids["app.service.login"], ids["db.store.save_user"], max_hops=2)
    assert result["found"] is False and result["truncated"] is True


def test_path_unknown_endpoint_is_not_found(tmp_path):
    from vgar.contracts.error import NodeNotFoundError
    service, version = _service(tmp_path)
    with pytest.raises(NodeNotFoundError):
        service.explain_dependency_path("missing:a", _ids(service, version)["app.service.login"])


# --- Task 4: schema, component, task and baseline resources --------------------------------------

def test_schema_resource_is_the_sc1_description(tmp_path):
    from vgar.contracts.schema import schema_description
    service, _ = _service(tmp_path)
    assert service.get_schema() == schema_description()


def test_component_has_the_proposal_keys_and_real_values(tmp_path):
    service, _ = _service(tmp_path)
    data = service.get_component("vgar:fixture/multi_package:python:component:app")
    assert set(data) == {"component", "files", "public_ports", "dependencies", "dependents", "tests", "risk"}
    assert data == {
        "component": "app",
        "files": ["app/__init__.py", "app/parser.py", "app/service.py"],
        "public_ports": ["app.parser.normalize", "app.service._audit", "app.service.login"],
        "dependencies": ["db"], "dependents": ["db"],
        "tests": ["tests/test_service.py"],
        "risk": "high_coupling",
    }


def test_component_can_be_named_by_its_unique_name(tmp_path):
    service, _ = _service(tmp_path)
    assert service.get_component("db")["public_ports"] == ["db.store.Store.put", "db.store.load_user", "db.store.save_user"]


def test_unknown_component_is_not_found(tmp_path):
    from vgar.contracts.error import NodeNotFoundError
    service, _ = _service(tmp_path)
    with pytest.raises(NodeNotFoundError):
        service.get_component("missing")


def test_task_exists_only_after_find_task_anchors(tmp_path):
    from vgar.contracts.error import GraphNotReadyError
    service, version = _service(tmp_path)
    with pytest.raises(GraphNotReadyError):
        service.get_task("t1")
    anchors = service.find_task_anchors("app/service.py login fails", graph_version=version, task_id="t1")
    assert service.get_task("t1") == anchors and service.get_task("t1")["task_id"] == "t1"


def test_baseline_marks_tests_and_invariants_not_run(tmp_path):
    from vgar.contracts.schema import SCHEMA_VERSION
    service, version = _service(tmp_path)
    data = service.get_baseline()
    assert data["graph_version"] == version and data["schema_version"] == SCHEMA_VERSION
    assert data["node_counts"]["Component"] == 2 and data["edge_counts"]["CALLS"] == 8
    assert data["tests"] == "NOT_RUN" and data["invariants"] == "NOT_RUN"


# --- Task 8: commit history signal for related context -------------------------------------------

def _git(cwd, *args):
    import subprocess
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


def _history_repo(tmp_path):
    """Git repo checked out at commit A (graph built here); a later commit B adds pkg/b.py."""
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "a.py").write_text("def alpha(x):\n    return x + 1\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "A")
    sha_a = _git(repo, "rev-parse", "HEAD")
    document = PythonGraphBuilder(repo_key="t/history", repository_revision=sha_a, source_roots=(".",)).build(repo)
    database = tmp_path / "graph.db"
    SQLiteGraphStore(database).ingest(document)
    (repo / "pkg" / "b.py").write_text("def beta(x):\n    return x - 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "B")
    _git(repo, "checkout", "-q", sha_a)  # work at the graph's base commit; commit B stays in the object store
    store = SQLiteGraphStore(database, graph_version=document["graph_version"])
    store.resolve_graph_version()
    service = SQLiteGraphService(store, repository_root=repo, count_tokens=len, counter_label="test:characters")
    anchor = next(node["id"] for node in document["nodes"] if node.get("qualified_name") == "pkg.a.alpha")
    return service, document["graph_version"], anchor


def test_history_is_off_by_default_and_output_is_unchanged(tmp_path):
    service, version, anchor = _history_repo(tmp_path)
    plain = service.get_related_context([anchor], 2000, graph_version=version, task_id="t", issue_text="alpha")
    again = service.get_related_context([anchor], 2000, graph_version=version, task_id="t", issue_text="alpha",
                                        use_history=False)
    assert plain["context"] == again["context"]
    assert "recent_change_frequency" in plain["diagnostics"]["unavailable_features"]
    assert "history" not in plain["diagnostics"]


def test_history_window_stops_at_the_graph_revision(tmp_path):
    service, version, anchor = _history_repo(tmp_path)
    result = service.get_related_context([anchor], 2000, graph_version=version, task_id="t", issue_text="alpha",
                                         use_history=True)
    history = result["diagnostics"]["history"]
    assert "pkg/a.py" in history["paths"] and "pkg/b.py" not in history["paths"]
    assert history["label"].startswith("git:first-parent:v1:")
    assert "recent_change_frequency" not in result["diagnostics"]["unavailable_features"]


def test_missing_history_is_reported_not_hidden(tmp_path):
    service, version = _service(tmp_path, count_tokens=len, counter_label="test:characters")
    anchors = service.find_task_anchors("login in app/service.py", graph_version=version, task_id="t")["anchors"]
    result = service.get_related_context([anchors[0]["node_id"]], 2000, graph_version=version, task_id="t",
                                         issue_text="login", use_history=True)   # revision "fixture" is not a SHA
    assert "recent_change_frequency" in result["diagnostics"]["unavailable_features"]
    assert result["diagnostics"]["history"]["available"] is False
