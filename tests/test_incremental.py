"""Incremental graph update (M1-W11-1): every update must equal a full rebuild of the same source.

Design: docs/superpowers/specs/2026-11-01-m1-w11-incremental-design.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.incremental import IncrementalGraphBuilder

REPO_KEY, REVISION = "demo/incremental", "fixture-revision"


def _write(root: Path, files: dict[str, str | None]) -> None:
    for relative, text in files.items():
        path = root / relative
        if text is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


def _full(root: Path, **kwargs) -> dict:
    return PythonGraphBuilder(repo_key=REPO_KEY, repository_revision=REVISION, **kwargs).build(root)


def _normalized(document: dict) -> str:
    document = json.loads(json.dumps(document))
    document["statistics"].pop("build_time_ms", None)
    return json.dumps(document, sort_keys=True)


BASE = {
    "src/a.py": "from b import f\n\ndef caller():\n    return f()\n",
    "src/b.py": "def f():\n    return 1\n\ndef g():\n    return f()\n",
    "src/y.py": "def uses_helper():\n    return helper()\n",
    "src/z.py": "def helper():\n    return 0\n",
}

CHANGES = {
    "modify": {"src/b.py": "def f():\n    return 2\n\ndef g():\n    return f() + 1\n"},
    "add_file": {"src/c.py": "def h():\n    return 3\n", "src/a.py": "from c import h\n\ndef caller():\n    return h()\n"},
    "delete_file": {"src/y.py": None},
    "rename_function": {"src/b.py": "def f2():\n    return 1\n\ndef g():\n    return f2()\n",
                        "src/a.py": "from b import f2\n\ndef caller():\n    return f2()\n"},
    "move_import": {"src/c.py": "def f():\n    return 9\n", "src/a.py": "from c import f\n\ndef caller():\n    return f()\n"},
    # C1: z.helper was the unique `helper`; a second one makes y's fallback call unresolvable.
    "name_loses_uniqueness": {"src/x.py": "def helper():\n    return 5\n"},
    "rename_file": {"src/b.py": None, "src/b2.py": BASE["src/b.py"]},
}


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_incremental_equals_full_rebuild(tmp_path, change):
    _write(tmp_path, BASE)
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)

    _write(tmp_path, CHANGES[change])
    document, _ = builder.update(tmp_path)

    assert _normalized(document) == _normalized(_full(tmp_path))


def test_incremental_equals_full_rebuild_with_duplicate_module_names(tmp_path):
    roots = ("src", "lib")
    _write(tmp_path, {"src/a.py": "def f():\n    return 1\n", "lib/a.py": "def f():\n    return 2\n",
                      "src/use.py": "from a import f\n\ndef caller():\n    return f()\n"})
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION, source_roots=roots)
    builder.build(tmp_path)

    _write(tmp_path, {"lib/a.py": "def f():\n    return 3\n\ndef extra():\n    return 4\n"})
    document, _ = builder.update(tmp_path)

    assert _normalized(document) == _normalized(_full(tmp_path, source_roots=roots))


def test_two_consecutive_updates_do_not_leak_link_mutations_into_the_cache(tmp_path):
    # Review Focus 1: linking mutates node properties (method aliases, import status).
    _write(tmp_path, {"src/k.py": "class K:\n    def impl(self):\n        return 1\n    alias = impl\n",
                      "src/u.py": "from k import K\n\ndef use():\n    return K().alias()\n"})
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)

    _write(tmp_path, {"src/u.py": "from k import K\n\ndef use():\n    return K().impl()\n"})
    first, _ = builder.update(tmp_path)
    assert _normalized(first) == _normalized(_full(tmp_path))

    _write(tmp_path, {"src/v.py": "def other():\n    return 2\n"})
    second, _ = builder.update(tmp_path)
    assert _normalized(second) == _normalized(_full(tmp_path))


def test_unparseable_file_replayed_from_cache_matches_full_rebuild(tmp_path):
    # Review Focus 3
    _write(tmp_path, {**BASE, "src/broken.py": "def oops(:\n"})
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)

    _write(tmp_path, CHANGES["modify"])
    document, _ = builder.update(tmp_path)

    assert _normalized(document) == _normalized(_full(tmp_path))


def test_incremental_relinks_callers_when_callee_deleted(tmp_path):
    # G4
    _write(tmp_path, BASE)
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    before = builder.build(tmp_path)
    old_f = next(node["id"] for node in before["nodes"] if node["qualified_name"] == "b.f")

    _write(tmp_path, {"src/b.py": "def g():\n    return 0\n"})
    document, _ = builder.update(tmp_path)

    assert not [edge for edge in document["edges"] if edge["type"] == "CALLS" and edge["target_id"] == old_f]
    assert _normalized(document) == _normalized(_full(tmp_path))


def test_incremental_noop_keeps_version_and_hits_cache(tmp_path):
    # G5
    _write(tmp_path, BASE)
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    before = builder.build(tmp_path)

    document, summary = builder.update(tmp_path)

    assert document["graph_version"] == before["graph_version"]
    assert summary.cache_hits == summary.total_files == len(BASE)
    assert summary.changed_files == summary.added_files == summary.deleted_files == ()
    assert summary.affected_node_count == 0
    assert _normalized(document) == _normalized(before)


def test_incremental_rejects_scip_and_lsp():
    # G5b
    with pytest.raises(ValueError, match="static resolver only"):
        IncrementalGraphBuilder(REPO_KEY, REVISION, lsp=object())
    with pytest.raises(ValueError, match="static resolver only"):
        IncrementalGraphBuilder(REPO_KEY, REVISION, scip=object())


def test_summary_counts_files_and_cache_hits(tmp_path):
    # Task 4
    _write(tmp_path, {"src/a.py": "def a():\n    return 1\n", "src/b.py": "def b():\n    return 2\n",
                      "src/c.py": "def c():\n    return 3\n"})
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)

    _write(tmp_path, {"src/a.py": "def a():\n    return 10\n", "src/c.py": None, "src/d.py": "def d():\n    return 4\n"})
    _, summary = builder.update(tmp_path)

    assert (summary.changed_files, summary.added_files, summary.deleted_files) == (("src/a.py",), ("src/d.py",), ("src/c.py",))
    assert (summary.cache_hits, summary.total_files) == (1, 3)


def test_affected_nodes_cover_changed_function_and_its_caller(tmp_path):
    _write(tmp_path, BASE)
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)

    _write(tmp_path, CHANGES["rename_function"])
    _, summary = builder.update(tmp_path)

    assert summary.affected_node_count >= 3


def test_summary_timings_are_consistent(tmp_path):
    _write(tmp_path, BASE)
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)

    _write(tmp_path, CHANGES["modify"])
    _, summary = builder.update(tmp_path)

    assert 0 <= summary.extract_seconds <= summary.total_seconds
    assert 0 <= summary.validate_seconds <= summary.total_seconds


def test_unchanged_files_do_not_rerun_alias_analysis(tmp_path, monkeypatch):
    # Optimisation (01/11): per-file method-alias analysis is cached, not only the AST parse.
    import vgar.graph.builder as builder_module
    _write(tmp_path, {"src/k.py": "class K:\n    def impl(self):\n        return 1\n    alias = impl\n",
                      "src/m.py": "class M:\n    def run(self):\n        return 2\n    go = run\n"})
    builder = IncrementalGraphBuilder(REPO_KEY, REVISION)
    builder.build(tmp_path)
    seen: list[str] = []
    real = builder_module.file_alias_candidates
    monkeypatch.setattr(builder_module, "file_alias_candidates",
                        lambda tree, symbols: seen.append(symbols[0]["path"]) or real(tree, symbols))

    _write(tmp_path, {"src/m.py": "class M:\n    def run(self):\n        return 3\n    go = run\n"})
    document, _ = builder.update(tmp_path)

    assert seen == ["src/m.py"]
    assert _normalized(document) == _normalized(_full(tmp_path))
