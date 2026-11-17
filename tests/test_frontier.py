"""F*_approx and dependency_frontier_recall@B (plan 2026-11-17 Task 4; spec 2026-11-17 §2.4)."""
from __future__ import annotations

from vgar.evaluation.retrieval.frontier import dependency_frontier
from vgar.evaluation.retrieval.scoring import (
    CorpusIndex,
    RankItem,
    RankRecord,
    bytes_div4_counter,
    score_record,
)

PATCH = ("--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n"
         "+    return helper(len(x)) + Unique().get()\n")
A = "def f():\n    return 1\n"


def test_frontier_adds_unique_names_from_added_lines():
    corpus = CorpusIndex({"pkg/a.py": A, "pkg/b.py": "def helper():\n    pass\nclass Unique:\n    def get(self):\n        pass\n"})
    gold = {"gold_functions": ["pkg/a.py::pkg.a.f"]}
    assert dependency_frontier(PATCH, gold, corpus) == [
        "pkg/a.py::pkg.a.f", "pkg/b.py::pkg.b.Unique.get", "pkg/b.py::pkg.b.helper"]


def test_frontier_skips_names_with_several_definitions_and_builtins():
    corpus = CorpusIndex({"pkg/a.py": A, "pkg/b.py": "def helper():\n    pass\n", "pkg/c.py": "def helper():\n    pass\n",
                          "pkg/d.py": "def len(x):\n    pass\n"})
    gold = {"gold_functions": ["pkg/a.py::pkg.a.f"]}
    assert dependency_frontier(PATCH, gold, corpus) == ["pkg/a.py::pkg.a.f"]


def test_frontier_ignores_removed_and_header_lines():
    corpus = CorpusIndex({"pkg/a.py": A, "pkg/b.py": "def helper():\n    pass\n"})
    patch = "--- a/pkg/a.py\n+++ b/pkg/helper.py\n@@ -1,2 +1,2 @@\n def f():\n-    return helper()\n+    return 2\n"
    assert dependency_frontier(patch, {"gold_functions": ["pkg/a.py::pkg.a.f"]}, corpus) == ["pkg/a.py::pkg.a.f"]


def test_frontier_ignores_comments_strings_and_non_source_files():
    corpus = CorpusIndex({"pkg/a.py": A, "pkg/b.py": "def helper():\n    pass\ndef other():\n    pass\n"})
    patch = ("--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n"
             "+    return 'helper'  # other\n"
             "--- a/README.rst\n+++ b/README.rst\n@@ -1 +1 @@\n-x\n+Call helper() and other().\n"
             "--- a/tests/test_a.py\n+++ b/tests/test_a.py\n@@ -1 +1 @@\n-x\n+helper()\n")
    assert dependency_frontier(patch, {"gold_functions": ["pkg/a.py::pkg.a.f"]}, corpus) == ["pkg/a.py::pkg.a.f"]


def test_frontier_keeps_names_before_an_open_bracket():
    corpus = CorpusIndex({"pkg/a.py": A, "pkg/b.py": "def helper():\n    pass\n"})
    patch = "--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,2 +1,3 @@\n def f():\n-    return 1\n+    return helper(\n+        1)\n"
    assert dependency_frontier(patch, {"gold_functions": ["pkg/a.py::pkg.a.f"]}, corpus) == [
        "pkg/a.py::pkg.a.f", "pkg/b.py::pkg.b.helper"]


def test_frontier_equals_gold_when_patch_adds_no_names():
    corpus = CorpusIndex({"pkg/a.py": A})
    patch = "--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
    assert dependency_frontier(patch, {"gold_functions": ["pkg/a.py::pkg.a.f"]}, corpus) == ["pkg/a.py::pkg.a.f"]


def _record(function_ids):
    items = [RankItem(item_id=f, path=f.split("::")[0], kind="function", symbol=f.split("::")[1], start_line=1, end_line=2,
                      snippet="def f():\n    pass\n", function_id=f) for f in function_ids]
    return RankRecord("t", "x", items)


def test_score_record_reports_frontier_only_when_present():
    record = _record(["pkg/a.py::pkg.a.f", "pkg/b.py::pkg.b.helper"])
    base = {"gold_files": ["pkg/a.py"], "gold_functions": ["pkg/a.py::pkg.a.f"]}
    without = score_record(record, base, budget_tokens=12000, counter=bytes_div4_counter, counter_label="x")
    assert "frontier_in_context" not in without["packed"]["metrics"]
    with_frontier = score_record(record, {**base, "frontier_functions": ["pkg/a.py::pkg.a.f", "pkg/c.py::pkg.c.g"]},
                                 budget_tokens=12000, counter=bytes_div4_counter, counter_label="x")
    assert with_frontier["packed"]["metrics"]["frontier_in_context"] == 0.5


def _graph_task_gold(monkeypatch, complete):
    from vgar.evaluation.retrieval import graph_arm
    monkeypatch.setattr(graph_arm, "extract_gold", lambda patch, sources: {
        "gold_files": ["pkg/a.py"], "gold_functions": ["pkg/a.py::pkg.a.f"], "function_labels_complete": complete})
    task = {"instance_id": "t", "repo": "o/r", "base_commit": "a" * 40, "problem_statement": "x", "patch": PATCH}
    sources = {"pkg/a.py": A, "pkg/b.py": "def helper():\n    pass\n"}
    return graph_arm.evaluate_graph_task(task, sources, CorpusIndex(sources), {}, {}, budget_tokens=12000,
                                         counter=bytes_div4_counter, counter_label="x", frontier=True)["gold"]


def test_graph_task_frontier_only_with_complete_function_labels(monkeypatch):
    assert _graph_task_gold(monkeypatch, True)["frontier_functions"] == ["pkg/a.py::pkg.a.f", "pkg/b.py::pkg.b.helper"]
    assert "frontier_functions" not in _graph_task_gold(monkeypatch, False)
