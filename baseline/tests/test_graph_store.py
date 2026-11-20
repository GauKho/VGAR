"""One SQLite graph per (task, build), shared by T1 and T2 (spec 2026-11-19 §7)."""
from baseline.graph_store import graph_db_path, load_or_build
from vgar.graph.layer_config import LayerConfigs

ROW = {"instance_id": "o__r-1", "repo": "o/r", "base_commit": "c" * 40}


def _tree(tmp_path):
    tree = tmp_path / "tree"
    (tree / "pkg").mkdir(parents=True)
    (tree / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tree / "pkg" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tree / "pkg" / "b.py").write_text("from pkg.a import f\n\n\ndef g():\n    return f()\n", encoding="utf-8")
    return tree


def _load(tmp_path, tree, builder_hash="h1"):
    return load_or_build(tmp_path, ROW, tree, build="base", layers=LayerConfigs(), graphs_dir=tmp_path / "graphs",
                         builder_hash=builder_hash)


def test_second_call_reads_the_same_graph_from_sqlite(tmp_path):
    tree = _tree(tmp_path)
    first_doc, first = _load(tmp_path, tree)
    second_doc, second = _load(tmp_path, tree)
    assert not first["from_cache"] and second["from_cache"] and first["db"].exists()
    assert second_doc["graph_version"] == first_doc["graph_version"]
    assert len(second_doc["nodes"]) == len(first_doc["nodes"]) and second["build_seconds"] == first["build_seconds"]


def test_new_builder_hash_rebuilds(tmp_path):
    tree = _tree(tmp_path)
    _load(tmp_path, tree)
    _, again = _load(tmp_path, tree, builder_hash="h2")
    assert not again["from_cache"] and again["builder_hash"] == "h2"


def test_builds_use_separate_databases(tmp_path):
    assert graph_db_path(tmp_path, "base", "x") != graph_db_path(tmp_path, "scip", "x")
