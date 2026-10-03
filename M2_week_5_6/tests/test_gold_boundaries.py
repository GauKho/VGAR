import unittest
from m2_retrieval.chunks import extract_chunks
from m2_retrieval.gold_labels import extract_gold, parse_patch


class GoldBoundaryTests(unittest.TestCase):
    def test_decorator_change_maps_decorated_function(self):
        source = "@cached\ndef f():\n    return 1\n"
        patch = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-@cached\n+@other\n"
        self.assertEqual(extract_gold(patch, {"a.py": source})["gold_functions"], ["a.py::a.f"])

    def test_nested_edit_labels_only_innermost_not_outer(self):
        source = "def outer():\n    def inner():\n        return 1\n    return inner()\n"
        patch = "--- a/a.py\n+++ b/a.py\n@@ -3 +3 @@\n-        return 1\n+        return 2\n"
        self.assertEqual(extract_gold(patch, {"a.py": source})["gold_functions"], ["a.py::a.outer.inner"])

    def test_added_only_function_is_explicitly_unretrievable(self):
        source = "def old():\n    return 1\n"
        patch = "--- a/a.py\n+++ b/a.py\n@@ -2,0 +3,3 @@\n+\n+def new():\n+    return 2\n"
        gold = extract_gold(patch, {"a.py": source})
        self.assertEqual(gold["gold_functions"], [])
        self.assertIn("new_function", [e["disposition"] for e in gold["mapping_events"]])

    def test_addition_inside_existing_function_is_retrievable(self):
        patch = "--- a/a.py\n+++ b/a.py\n@@ -1,0 +2 @@\n+    value = 2\n"
        self.assertEqual(extract_gold(patch, {"a.py": "def f():\n    return 1\n"})["gold_functions"], ["a.py::a.f"])

    def test_rename_and_delete_use_old_path(self):
        patch = "diff --git a/a.py b/renamed.py\nrename from a.py\nrename to renamed.py\n"
        self.assertEqual(extract_gold(patch, {"a.py": "x=1\n"})["gold_files"], ["a.py"])
        deleted = "--- a/a.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-def f():\n-    return 1\n"
        self.assertEqual(extract_gold(deleted, {"a.py": "def f():\n    return 1\n"})["gold_functions"], ["a.py::a.f"])

    def test_malformed_hunk_and_unsafe_path_do_not_generate_labels(self):
        for patch in ("--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n-x\n+y\n", "--- a/../evil.py\n+++ b/../evil.py\n"):
            with self.assertRaises(ValueError):
                parse_patch(patch)

    def test_long_functions_have_stable_parent_and_unique_windows(self):
        source = "def f():\n" + "    x = 1\n" * 10
        chunks, _ = extract_chunks({"a.py": source}, window_lines=4, overlap_lines=1)
        self.assertEqual(len({c["parent_id"] for c in chunks}), 1)
        self.assertEqual(len(chunks), 4)
        self.assertEqual(len({c["chunk_id"] for c in chunks}), 4)


if __name__ == "__main__":
    unittest.main()
