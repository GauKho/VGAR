"""F*_core v2: F*_approx plus names on removed lines (spec 2026-11-19 §9)."""
from baseline.frontier_v2 import changed_code_names, frontier_core_v2
from vgar.evaluation.retrieval.scoring import CorpusIndex


def _ids(corpus):
    return {d["symbol"].rsplit(".", 1)[-1]: d["parent_id"] for v in corpus.definitions.values() for d in v}


def test_removed_line_names_join_the_frontier():
    corpus = CorpusIndex({"src/a.py": "def old_helper():\n    return 1\n\n\ndef new_helper():\n    return 2\n",
                          "src/b.py": "def run():\n    return old_helper()\n"})
    ids = _ids(corpus)
    patch = "--- a/src/b.py\n+++ b/src/b.py\n@@ -2 +2 @@\n-    return old_helper()\n+    return new_helper()\n"
    assert frontier_core_v2(patch, {"gold_functions": [ids["run"]]}, corpus) == sorted(
        {ids["run"], ids["old_helper"], ids["new_helper"]})


def test_comments_strings_and_ambiguous_names_stay_out():
    corpus = CorpusIndex({"src/a.py": "def dup():\n    pass\n\n\ndef ghost():\n    pass\n",
                          "src/c.py": "def dup():\n    pass\n\n\ndef run():\n    pass\n"})
    ids = _ids(corpus)
    patch = ("--- a/src/c.py\n+++ b/src/c.py\n@@ -5 +5 @@\n-    pass  # ghost\n"
             "+    return dup() or 'ghost'\n")
    result = frontier_core_v2(patch, {"gold_functions": [ids["run"]]}, corpus)
    assert result == [ids["run"]]


def test_deleted_file_lines_count_and_tests_are_ignored():
    patch = ("--- a/src/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-value = compute_total()\n"
             "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1 +1 @@\n-assert test_only_name()\n+assert 1\n")
    names = changed_code_names(patch)
    assert "compute_total" in names and "test_only_name" not in names
