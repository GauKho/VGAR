"""Agent-loop fixes after the OpenCode A/B runs on ShopFlow (spec 2026-11-23, batch 4 part A)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from vgar.contracts.error import GraphError, GraphNotReadyError, StaleGraphVersionError
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.factory import create_graph_service
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.snapshot_sources import read_graph_sources
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server
from vgar.repair import patch_evidence

SHOP = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n",
    "shop/checkout.py": "from shop.pricing import round_vnd\n\n\ndef total(lines):\n    return round_vnd(sum(lines))\n",
}
EDIT = "def round_vnd(amount):\n    return round(amount)\n"


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
    return root


def _build(tmp_path: Path, files: dict[str, str] = SHOP, *, with_sources: bool = True):
    root = _write(tmp_path / "repo", files)
    document = PythonGraphBuilder(repo_key="t/loop", repository_revision="rev").build(root)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document, sources=read_graph_sources(root, document) if with_sources else None)
    service = SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test")
    return service, document["graph_version"], root


def _anchor(service) -> list[str]:
    return [service.search_symbols("round_vnd").symbols[0].symbol_id]


# --- Task 1: retrieval reads the graph's stored source -----------------------------------------------

def test_related_context_after_an_edit_uses_the_graph_code(tmp_path):
    service, version, root = _build(tmp_path)
    stored = (root / "shop/pricing.py").read_bytes()
    (root / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    data = service.get_related_context(_anchor(service), 2000, graph_version=version, task_id="t", issue_text="round_vnd is wrong")
    snippets = [item["snippet"] for item in data["context"]["items"] if item["path"] == "shop/pricing.py"]
    assert snippets and all(snippet.encode() in stored for snippet in snippets)
    assert data["diagnostics"]["worktree_changes"] == ["shop/pricing.py"]
    assert "not in this context" in data["diagnostics"]["worktree_note"]


def test_related_context_ignores_a_scratch_file_and_a_deleted_file(tmp_path):
    service, version, root = _build(tmp_path)
    (root / "scratch.py").write_text("x = 1\n", encoding="utf-8")
    (root / "shop/checkout.py").unlink()
    data = service.get_related_context(_anchor(service), 2000, graph_version=version, task_id="t", issue_text="round_vnd")
    assert data["diagnostics"]["worktree_changes"] == ["scratch.py", "shop/checkout.py"]


def test_clean_tree_reports_no_worktree_changes(tmp_path):
    service, version, _ = _build(tmp_path)
    data = service.get_related_context(_anchor(service), 2000, graph_version=version, task_id="t", issue_text="round_vnd")
    assert data["diagnostics"]["worktree_changes"] == []
    assert "worktree_note" not in data["diagnostics"]


def test_find_task_anchors_with_a_labelled_error_line_after_an_edit(tmp_path):
    service, version, root = _build(tmp_path)
    (root / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    result = service.find_task_anchors("ValueError: something broke in round_vnd", graph_version=version, task_id="t")
    assert result["graph_version"] == version


def test_graph_without_stored_source_keeps_the_snapshot_check(tmp_path):
    service, version, root = _build(tmp_path, with_sources=False)
    (root / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    with pytest.raises(GraphError, match="Source content differs"):
        service.get_related_context(_anchor(service), 2000, graph_version=version, task_id="t", issue_text="round_vnd")


def test_clean_tree_ranks_the_same_with_and_without_stored_source(tmp_path):
    service, version, root = _build(tmp_path)
    document = service._document(version)
    kwargs = dict(count_tokens=len, counter_label="test")
    with_store = GraphContextRetriever(document, root, sources=service.snapshot_sources(version), **kwargs)
    without = GraphContextRetriever(document, root, **kwargs)
    a = with_store.retrieve(_anchor(service), 2000, issue_text="total uses round_vnd")
    b = without.retrieve(_anchor(service), 2000, issue_text="total uses round_vnd")
    assert a.candidates == b.candidates and a.context == b.context


def test_related_context_tool_keeps_worktree_changes(tmp_path, monkeypatch):
    service, version, root = _build(tmp_path)
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    (root / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    result = graph_server.get_related_context(_anchor(service), version, "t", issue_text="round_vnd")
    assert result["status"] == "PASS", result
    assert result["data"]["diagnostics"]["worktree_changes"] == ["shop/pricing.py"]


# --- Task 2: a pruned graph_version is refused --------------------------------------------------------

def _rebuild_with_edit(service, root) -> str:
    (root / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    document = PythonGraphBuilder(repo_key="t/loop", repository_revision="rev").build(root)
    service.store.ingest(document, sources=read_graph_sources(root, document))
    service.store.prune_other_versions(document["graph_version"], document["repo_key"])
    return document["graph_version"]


@pytest.mark.parametrize("call", [
    lambda s, v: s.find_task_anchors("round_vnd", graph_version=v, task_id="t"),
    lambda s, v: s.get_related_context([], 2000, graph_version=v, task_id="t", issue_text="round_vnd"),
    lambda s, v: s.get_related_tests([], graph_version=v),
    lambda s, v: s.analyze_patch_impact("", graph_version=v),
], ids=["anchors", "context", "tests", "impact"])
def test_a_pruned_version_is_refused_with_the_current_one(tmp_path, call):
    service, old, root = _build(tmp_path)
    service.find_task_anchors("round_vnd", graph_version=old, task_id="t")   # loads the old version into the cache
    new = _rebuild_with_edit(service, root)
    with pytest.raises(StaleGraphVersionError, match="no longer the graph") as error:
        call(service, old)
    assert error.value.code == "GRAPH_NOT_READY"
    assert error.value.details == {"reason": "stale_graph_version", "graph_version": old, "current_graph_version": new}


def test_forget_other_versions_drops_cached_documents(tmp_path):
    service, old, _ = _build(tmp_path)
    service.get_related_context(_anchor(service), 2000, graph_version=old, task_id="t", issue_text="round_vnd")
    service.forget_other_versions("sha256:other")
    assert old not in service._documents and not [key for key in service._retrievers if key[0] == old]


def test_empty_database_still_says_graph_not_ready(tmp_path):
    service = SQLiteGraphService(SQLiteGraphStore(tmp_path / "empty.db"), repository_root=tmp_path,
                                 count_tokens=len, counter_label="test")
    with pytest.raises(GraphNotReadyError):
        service.find_task_anchors("x", graph_version="sha256:none", task_id="t")


# --- Task 3: a build checks the changes nobody checked ---------------------------------------------------

@pytest.fixture
def live(tmp_path, monkeypatch) -> Path:
    root = _write(tmp_path / "repo", SHOP)
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "graphs" / "live.db"))
    monkeypatch.setenv("VGAR_REPOSITORY_ROOT", str(root))
    monkeypatch.delenv("VGAR_GRAPH_VERSION", raising=False)
    monkeypatch.setattr(graph_server, "graph_service", create_graph_service())
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(graph_server, "_live_builder", None, raising=False)
    monkeypatch.setattr(graph_server, "_verify_cache", {})
    monkeypatch.setattr(graph_server, "_impact_cache", {}, raising=False)
    return root


def build(root: Path) -> dict:
    result = asyncio.run(graph_server.build_or_update_graph(str(root)))
    assert result["status"] == "PASS", result
    return result["data"]


def test_first_build_runs_no_checks(live):
    assert build(live)["checks_before_update"] == {"status": "NOT_RUN", "reason": "first build"}


def test_clean_tree_build_reports_no_changes(live):
    build(live)
    assert build(live)["checks_before_update"] == {"status": "NO_CHANGES"}


def test_build_with_an_unchecked_edit_checks_it_first(live):
    build(live)
    (live / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    checks = build(live)["checks_before_update"]
    assert checks["status"] == "CHECKED", checks
    assert checks["checked_diff"]["files"] == ["shop/pricing.py"]
    assert checks["verify"]["status"] in {"PASS", "FAIL"} and checks["impact"]["changed_count"] >= 1
    assert checks["tests"] == "not run"


def test_build_reuses_the_checks_the_agent_already_ran(live, monkeypatch):
    build(live)
    (live / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    calls = {"verify": 0, "impact": 0}
    real_verify = patch_evidence.verify_patch
    real_impact = graph_server.graph_service.analyze_patch_impact

    def counted_verify(*args, **kwargs):
        calls["verify"] += 1
        return real_verify(*args, **kwargs)

    def counted_impact(*args, **kwargs):
        calls["impact"] += 1
        return real_impact(*args, **kwargs)

    monkeypatch.setattr(patch_evidence, "verify_patch", counted_verify)
    monkeypatch.setattr(graph_server.graph_service, "analyze_patch_impact", counted_impact)
    version = graph_server.graph_service.get_repository_summary().graph_version
    assert asyncio.run(graph_server.verify_patch_graph_constraints())["status"] == "PASS"
    assert graph_server.analyze_patch_impact(version)["status"] == "PASS"
    assert build(live)["checks_before_update"]["status"] == "CHECKED"
    assert calls == {"verify": 1, "impact": 1}


def test_a_new_file_only_is_not_run_and_the_build_still_runs(live):
    build(live)
    (live / "shop/extra.py").write_text("def extra():\n    return 1\n", encoding="utf-8")
    data = build(live)
    assert data["checks_before_update"]["status"] == "NOT_RUN"
    assert "shop/extra.py" in data["changed_files"]


def test_analyze_after_a_rebuild_points_to_checks_before_update(live):
    build(live)
    (live / "shop/pricing.py").write_text(EDIT, encoding="utf-8")
    version = build(live)["graph_version"]
    result = graph_server.analyze_patch_impact(version)
    assert result["status"] == "ERROR" and "checks_before_update" in result["error"]["message"]


# --- Task 4: search_symbols takes several names -------------------------------------------------------

ORDERS = {
    "shop/__init__.py": "",
    "shop/orders.py": ("class Order:\n    def transition_to(self, status):\n        return status\n\n\n"
                       "def cancel_order(order):\n    return order\n\n\ndef ship_order(order):\n    return order\n\n\n"
                       "def order_total(order):\n    return 0\n"),
}


# Captured on the code before this change (single-term queries keep their results and order).
SINGLE_TERM_BASELINE = ["Order", "orders", "transition_to", "cancel_order", "order_total", "ship_order"]


@pytest.fixture
def order_store(tmp_path) -> SQLiteGraphStore:
    root = _write(tmp_path / "orders", ORDERS)
    document = PythonGraphBuilder(repo_key="t/orders", repository_revision="rev").build(root)
    store = SQLiteGraphStore(tmp_path / "orders.db")
    store.ingest(document)
    return store


def _names(store, query, limit=20):
    return [symbol.name for symbol in store.search_symbols(query, limit)]


def test_three_names_return_three_symbols(order_store):
    assert set(_names(order_store, "cancel_order ship_order transition_to")) >= {"cancel_order", "ship_order",
                                                                                "transition_to"}


def test_single_term_is_unchanged(order_store):
    assert _names(order_store, "order") == SINGLE_TERM_BASELINE


def test_more_matched_terms_rank_first(order_store):
    assert _names(order_store, "order total")[0] == "order_total"


def test_short_terms_are_dropped_and_a_short_only_query_uses_the_whole_string(order_store):
    assert set(_names(order_store, "to ship_order")) == {"ship_order"}
    assert _names(order_store, "a b") == []


def test_limit_applies_after_ranking(order_store):
    assert _names(order_store, "order total", limit=1) == ["order_total"]   # cut before ranking would give "Order"
