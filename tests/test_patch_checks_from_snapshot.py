"""Patch checks run on the source the graph was built from, stored in the database (spec 2026-11-22, batch 3)."""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import anyio
import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.indexing import index_repo
from vgar.graph.live_build import LiveGraphBuilder
from vgar.graph.snapshot_sources import materialize_snapshot, read_graph_sources
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff
from vgar.repair.patch_evidence import run_patch_tests, verify_patch
from vgar.repair.worktree_diff import worktree_diff
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import execution_server, graph_server

SHOP = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n",
    "shop/checkout.py": "from shop.pricing import round_vnd\n\n\ndef total(lines):\n    return round_vnd(sum(lines))\n",
}


def _write(root: Path, files: dict[str, str | bytes]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="")
    return root


def _doc(tmp_path: Path, files: dict[str, str | bytes] = SHOP) -> tuple[Path, dict]:
    root = _write(tmp_path / "repo", files)
    return root, PythonGraphBuilder(repo_key="t/snap", repository_revision="rev").build(root)


def _files(root: Path, document: dict) -> dict[str, bytes]:
    return {node["path"]: (root / node["path"]).read_bytes() for node in document["nodes"] if node["type"] == "File"}


# --- Task 1: the sources table -------------------------------------------------------------------

def test_ingest_keeps_the_sources_of_its_version(tmp_path):
    root, document = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(document, sources=_files(root, document))
    assert store.get_sources(document["graph_version"]) == {p: t.encode() for p, t in SHOP.items()}


def test_ingest_without_sources_stores_none(tmp_path):
    root, document = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(document)
    assert store.get_sources(document["graph_version"]) == {}


def test_put_sources_rejects_bytes_that_differ_from_the_graph(tmp_path):
    root, document = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(document)
    sources = {**_files(root, document), "shop/pricing.py": b"x = 1\n"}
    with pytest.raises(ValueError, match="shop/pricing.py"):
        store.put_sources(document["graph_version"], sources)


def test_put_sources_rejects_a_missing_file(tmp_path):
    root, document = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(document)
    sources = _files(root, document)
    del sources["shop/checkout.py"]
    with pytest.raises(ValueError, match="shop/checkout.py"):
        store.put_sources(document["graph_version"], sources)


def test_pruning_a_version_removes_its_sources(tmp_path):
    root, first = _doc(tmp_path)
    store = SQLiteGraphStore(tmp_path / "g.db")
    store.ingest(first, sources=_files(root, first))
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return 0\n", encoding="utf-8", newline="")
    second = PythonGraphBuilder(repo_key="t/snap", repository_revision="rev").build(root)
    store.ingest(second, sources=_files(root, second))
    store.prune_other_versions(second["graph_version"], "t/snap")
    assert store.get_sources(first["graph_version"]) == {}
    assert store.get_sources(second["graph_version"])["shop/pricing.py"] == b"def round_vnd(amount):\n    return 0\n"


# --- Task 2: builds store the sources -------------------------------------------------------------

def test_read_graph_sources_rejects_a_file_changed_after_the_build(tmp_path):
    root, document = _doc(tmp_path)
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return 0\n", encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="changed during the build: shop/pricing.py"):
        read_graph_sources(root, document)


def test_live_build_stores_the_source_of_every_file(tmp_path):
    root = _write(tmp_path / "repo", SHOP)
    version = LiveGraphBuilder(root, tmp_path / "g.db").run()["graph_version"]
    assert SQLiteGraphStore(tmp_path / "g.db").get_sources(version) == {p: t.encode() for p, t in SHOP.items()}


def test_live_build_backfills_the_sources_of_an_unchanged_older_graph(tmp_path):
    root = _write(tmp_path / "repo", SHOP)
    db = tmp_path / "g.db"
    builder = LiveGraphBuilder(root, db)
    version = builder.run()["graph_version"]
    with sqlite3.connect(db) as connection:
        connection.execute("DELETE FROM sources")           # a graph built before sources were stored
    assert builder.run()["unchanged"] is True
    assert SQLiteGraphStore(db).get_sources(version)["shop/pricing.py"] == SHOP["shop/pricing.py"].encode()


def test_vgar_index_stores_the_sources(tmp_path):
    root = _write(tmp_path / "repo", SHOP)
    index_repo(root, tmp_path / "g.db")
    store = SQLiteGraphStore(tmp_path / "g.db")
    assert set(store.get_sources(store.resolve_graph_version())) == set(SHOP)


# --- Task 3: analyze_patch_impact on the stored source --------------------------------------------

PRICING_FIX = """diff --git a/shop/pricing.py b/shop/pricing.py
--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -1,2 +1,2 @@
 def round_vnd(amount):
-    return amount
+    return round(amount, -3)
"""


def _build(tmp_path: Path, files: dict[str, str | bytes] = SHOP, *, with_sources: bool = True):
    root, document = _doc(tmp_path, files)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document, sources=read_graph_sources(root, document) if with_sources else None)
    service = SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test")
    return service, document["graph_version"], root


def _edit_pricing(root: Path) -> None:
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return round(amount, -3)\n", encoding="utf-8",
                                          newline="")


def test_patch_impact_checks_a_diff_on_the_graph_code_while_the_file_is_edited(tmp_path):
    service, version, root = _build(tmp_path)
    _edit_pricing(root)
    changed = service.analyze_patch_impact(PRICING_FIX, graph_version=version)["changed"]
    assert [item["path"] for item in changed] == ["shop/pricing.py"]


def test_graph_without_a_source_copy_keeps_the_old_check_and_hints_a_rebuild(tmp_path):
    service, version, root = _build(tmp_path, with_sources=False)
    _edit_pricing(root)
    with pytest.raises(ValueError) as error:
        service.analyze_patch_impact(PRICING_FIX, graph_version=version)
    assert "shop/pricing.py" in str(error.value) and "build_or_update_graph" in str(error.value)


def test_a_tampered_source_copy_is_refused(tmp_path):
    service, version, _ = _build(tmp_path)
    with sqlite3.connect(tmp_path / "graph.db") as connection:
        connection.execute("UPDATE sources SET content = ? WHERE path = ?", (b"x = 1\n", "shop/pricing.py"))
    with pytest.raises(ValueError, match="shop/pricing.py"):
        service.snapshot_sources(version)


def test_materialized_snapshot_holds_the_graph_code_and_the_other_worktree_files(tmp_path):
    sources = {"pkg/a.py": b"A = 1\n", "pkg/gone.py": b"G = 1\n"}
    worktree = _write(tmp_path / "wt", {"pkg/a.py": "A = 2\n", "scratch.py": "x = 1\n", "data.json": "{}",
                                        ".venv/lib/site.py": "s = 1\n"})
    target = materialize_snapshot(sources, tmp_path / "copy", worktree=worktree)
    assert (target / "pkg/a.py").read_bytes() == b"A = 1\n" and (target / "pkg/gone.py").read_bytes() == b"G = 1\n"
    assert not (target / "scratch.py").exists() and (target / "data.json").read_text() == "{}"
    assert (target / ".venv/lib/site.py").exists()          # folders the builder ignores are left alone


# --- Task 4: verify_patch and run_patch_tests on the stored source --------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOGIN_REPO = FIXTURES / "w7_w8_handoff" / "single_file_login" / "repo"
REF = (FIXTURES / "m2" / "reference_patches" / "single_file_login.diff").read_text(encoding="utf-8")
FAILING = ["tests/test_auth.py::test_login_rejects_whitespace"]


def _build_from(tmp_path: Path, repo: Path):
    root = tmp_path / "repo"
    shutil.copytree(repo, root, ignore=shutil.ignore_patterns("__pycache__"))
    document = PythonGraphBuilder(repo_key="t/login", repository_revision="rev").build(root)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document, sources=read_graph_sources(root, document))
    return SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test"), document["graph_version"], root


def _apply_in_place(root: Path, diff: str) -> None:
    # Test setup: write the patched files into the working tree, as a coding agent does.
    paths = tuple(sorted({line[6:] for line in diff.splitlines() if line.startswith("+++ b/")}))
    for path, content in _bind(parse_unified_diff(diff, PatchPolicy(paths, ())), root)[0].items():
        (root / path).write_bytes(content)


def test_verify_passes_a_diff_while_the_file_is_edited(tmp_path):
    service, version, root = _build(tmp_path)
    _edit_pricing(root)
    assert verify_patch(service, PRICING_FIX, graph_version=version)["status"] == "PASS"


def test_verify_ignores_a_scratch_file_added_after_the_build(tmp_path):
    service, version, root = _build(tmp_path)
    _edit_pricing(root)
    (root / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    assert verify_patch(service, PRICING_FIX, graph_version=version)["status"] == "PASS"


def test_verify_without_a_source_copy_hints_a_rebuild(tmp_path):
    service, version, root = _build(tmp_path, with_sources=False)
    _edit_pricing(root)
    reason = verify_patch(service, PRICING_FIX, graph_version=version)["reasons"][0]
    assert reason.startswith("SOURCE_DIFFERS_FROM_SNAPSHOT") and "build_or_update_graph" in reason


def test_patch_tests_run_on_the_graph_code_while_the_fix_is_in_the_worktree(tmp_path):
    service, version, root = _build_from(tmp_path, LOGIN_REPO)
    _apply_in_place(root, REF)
    result = run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING)
    assert result["status"] == "PASS", result
    assert result["baseline"][FAILING[0]] == "FAIL" and result["candidate"][FAILING[0]] == "PASS"


# --- Task 5: the diff of the working tree against the stored source ------------------------------

def _round_trip(tmp_path: Path, stored: dict[str, bytes], worktree: dict[str, bytes]) -> dict[str, bytes]:
    base, wt = _write(tmp_path / "base", stored), _write(tmp_path / "wt", worktree)
    wd = worktree_diff(stored, wt)
    return _bind(parse_unified_diff(wd.diff, PatchPolicy(tuple(stored), ())), base)[0]


@pytest.mark.parametrize("old, new", [
    (b"a\nb\nc\n", b"a\nB\nc\n"),           # edit a middle line
    (b"a\nb", b"a\nb\nc\n"),                # file without final newline grows
    (b"a\nb\n", b"a\nb"),                   # final newline removed
    (b"a\r\nb\r\n", b"a\r\nX\r\n"),         # CRLF on both sides
])
def test_worktree_diff_applies_back_to_the_worktree_bytes(tmp_path, old, new):
    assert _round_trip(tmp_path, {"m.py": old}, {"m.py": new}) == {"m.py": new}


def test_worktree_diff_handles_paths_with_spaces(tmp_path):
    assert _round_trip(tmp_path, {"my pkg/m.py": b"a\n"}, {"my pkg/m.py": b"b\n"}) == {"my pkg/m.py": b"b\n"}


def test_worktree_diff_counts_changed_lines(tmp_path):
    root = _write(tmp_path / "wt", {"m.py": b"a\nB\n"})
    assert worktree_diff({"m.py": b"a\nb\n"}, root).changed_lines == 2


def test_line_endings_alone_are_not_a_change(tmp_path):
    wd = worktree_diff({"m.py": b"a\nb\n"}, _write(tmp_path / "wt", {"m.py": b"a\r\nb\r\n"}))
    assert wd.diff == "" and wd.not_checked == ("line endings only: m.py",)


def test_new_deleted_and_non_utf8_files_are_listed_not_diffed(tmp_path):
    root = _write(tmp_path / "wt", {"a.py": b"A\n", "new.py": b"N\n", "bin.py": b"\xff\n"})
    wd = worktree_diff({"a.py": b"A\n", "gone.py": b"G\n", "bin.py": b"x\n"}, root)
    assert wd.diff == "" and wd.files == ()
    assert wd.not_checked == ("deleted file: gone.py", "new file: new.py", "not UTF-8: bin.py")


def test_no_change_gives_an_empty_diff(tmp_path):
    wd = worktree_diff({"a.py": b"A\n"}, _write(tmp_path / "wt", {"a.py": b"A\n"}))
    assert (wd.diff, wd.files, wd.not_checked, wd.changed_lines) == ("", (), (), 0)


# --- Task 6: the tools need no diff ---------------------------------------------------------------

def _serve(tmp_path: Path, monkeypatch, service) -> None:
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(graph_server, "_verify_cache", {})


@pytest.fixture
def served(tmp_path, monkeypatch) -> tuple[str, Path]:
    service, version, root = _build(tmp_path)
    _serve(tmp_path, monkeypatch, service)
    return version, root


def verify() -> dict:
    return anyio.run(graph_server.verify_patch_graph_constraints)


def test_analyze_without_a_diff_checks_the_worktree_changes(served):
    version, root = served
    _edit_pricing(root)
    data = graph_server.analyze_patch_impact(graph_version=version)["data"]
    assert [item["path"] for item in data["changed"]] == ["shop/pricing.py"]
    assert data["checked_diff"]["source"] == "worktree" and data["checked_diff"]["files"] == ["shop/pricing.py"]


def test_verify_without_a_diff_passes_and_lists_a_scratch_file(served):
    version, root = served
    _edit_pricing(root)
    (root / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    data = verify()["data"]
    assert data["status"] == "PASS" and data["checked_diff"]["not_checked"] == ["new file: scratch.py"]
    assert "NOT_CHECKED: new file: scratch.py" in data["reasons"]


def test_verify_without_changes_is_not_run(served):
    data = verify()["data"]
    assert data["status"] == "NOT_RUN" and data["reasons"] == ["NO_CHANGES"]


def test_analyze_without_changes_says_check_before_rebuilding(served):
    response = graph_server.analyze_patch_impact(graph_version=served[0])
    assert response["status"] == "ERROR" and "before rebuilding" in response["error"]["message"]


def test_verify_follows_new_edits_between_calls(served):
    version, root = served
    _edit_pricing(root)
    first = verify()["data"]["status"]
    (root / "shop/pricing.py").write_text("def round_vnd(amount):\n    return (\n", encoding="utf-8", newline="")
    second = verify()["data"]
    assert first == "PASS" and second["status"] == "FAIL" and "CANDIDATE_SYNTAX_ERROR" in second["reasons"]


def test_not_checked_entries_do_not_leak_between_calls(served):
    version, root = served
    _edit_pricing(root)
    (root / "a_scratch.py").write_text("x = 1\n", encoding="utf-8")
    verify()
    (root / "a_scratch.py").unlink()
    data = verify()["data"]
    assert data["checked_diff"]["not_checked"] == [] and not any(r.startswith("NOT_CHECKED") for r in data["reasons"])


def test_graph_without_a_source_copy_needs_a_diff(tmp_path, monkeypatch):
    service, version, root = _build(tmp_path, with_sources=False)
    _serve(tmp_path, monkeypatch, service)
    _edit_pricing(root)
    response = verify()
    assert response["status"] == "ERROR" and "build_or_update_graph" in response["error"]["message"]


def test_too_many_changed_files_ask_to_rebuild_after_each_fix(tmp_path, monkeypatch):
    service, version, root = _build(tmp_path, {f"m{i}.py": "X = 0\n" for i in range(6)})
    _serve(tmp_path, monkeypatch, service)
    for i in range(6):
        (root / f"m{i}.py").write_text("X = 1\n", encoding="utf-8", newline="")
    response = graph_server.analyze_patch_impact(graph_version=version)
    assert response["status"] == "ERROR" and "rebuild the graph after each fix" in response["error"]["message"]


def test_a_host_provider_still_requires_a_diff(served, monkeypatch):
    monkeypatch.setattr(graph_server, "_has_provider", lambda capability: True)
    response = verify()
    assert response["status"] == "ERROR" and "diff is required" in json.dumps(response)


def test_run_relevant_tests_without_a_diff(tmp_path, monkeypatch):
    service, version, root = _build_from(tmp_path, LOGIN_REPO)
    _apply_in_place(root, REF)
    monkeypatch.setattr(execution_server, "_graph_service", service)
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "x.jsonl"))
    data = anyio.run(execution_server.run_relevant_tests)["data"]
    assert data["candidate"][FAILING[0]] == "PASS" and data["checked_diff"]["files"] == ["auth.py"]


# --- Final review fixes ---------------------------------------------------------------------------

def test_verify_with_only_a_new_file_reports_it_as_not_checked(served):
    version, root = served
    (root / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    data = verify()["data"]
    assert data["status"] == "NOT_RUN" and data["reasons"] == ["NO_CHANGES", "NOT_CHECKED: new file: scratch.py"]


def test_analyze_with_only_a_new_file_names_it_instead_of_blaming_a_rebuild(served):
    version, root = served
    (root / "scratch.py").write_text("print(1)\n", encoding="utf-8")
    message = graph_server.analyze_patch_impact(graph_version=version)["error"]["message"]
    assert "new file: scratch.py" in message and "already in it" not in message


def test_a_form_feed_line_is_listed_instead_of_breaking_the_diff(tmp_path):
    wd = worktree_diff({"m.py": b"a\n\x0c\nb\n"}, _write(tmp_path / "wt", {"m.py": b"a\n\x0c\nB\n"}))
    assert wd.diff == "" and wd.not_checked == ("unsupported line separator: m.py",)


def test_verify_with_a_stored_source_does_not_claim_the_copy_is_missing(tmp_path, monkeypatch):
    from vgar.repair import patch_evidence
    service, version, root = _build(tmp_path)
    _edit_pricing(root)
    monkeypatch.setattr(patch_evidence.PythonGraphBuilder, "_calculate_graph_version", lambda self, *a: "sha256:other")
    assert verify_patch(service, PRICING_FIX, graph_version=version)["reasons"] == ["BUILDER_OPTIONS_OR_SOURCE_DIFFER_FROM_SNAPSHOT"]
