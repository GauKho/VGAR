import math
import tempfile
import unittest
from pathlib import Path

from m2_retrieval.bm25 import BM25, tokenize, pack_context
from m2_retrieval.chunks import extract_chunks
from m2_retrieval.gold_labels import extract_gold
from m2_retrieval.metrics import evaluate_ranking


SOURCE = """def decorate(f):
    return f

@decorate
def login(user_name):
    return user_name.strip()

class Auth:
    def validate(self, token):
        def normalize(value):
            return value.lower()
        return normalize(token)

SETTING = 1
"""


class CoreTests(unittest.TestCase):
    def test_tokenizer_splits_snake_camel_and_paths(self):
        terms = tokenize("TokenService auth/token.py user_name HTTPServer")
        for expected in ("tokenservice", "token", "service", "auth", "py", "user", "name", "http", "server"):
            self.assertIn(expected, terms)

    def test_chunks_preserve_decorator_nested_names_and_module(self):
        chunks, issues = extract_chunks({"auth/core.py": SOURCE})
        self.assertEqual(issues, [])
        by_name = {c["symbol"]: c for c in chunks}
        self.assertEqual(by_name["auth.core.login"]["start_line"], 4)
        self.assertIn("auth.core.Auth.validate.normalize", by_name)
        self.assertEqual(by_name["auth.core.Auth.validate"]["kind"], "method")
        self.assertIn("auth.core::<module>", by_name)
        self.assertIn("SETTING = 1", by_name["auth.core::<module>"]["snippet"])

    def test_parse_failure_is_recorded_not_silently_skipped(self):
        chunks, issues = extract_chunks({"bad.py": "def broken(:\n"})
        self.assertFalse(chunks)
        self.assertEqual(issues[0]["path"], "bad.py")

    def test_bm25_matches_hand_calculated_score(self):
        engine = BM25([{"chunk_id": "a", "text": "apple apple"}, {"chunk_id": "b", "text": "pear"}])
        result = engine.search("apple")
        expected = math.log(2) * (2 * 2.2) / (2 + 1.2 * (0.25 + 0.75 * 2 / 1.5))
        self.assertAlmostEqual(result[0]["score"], expected)
        self.assertEqual([r["chunk_id"] for r in result], ["a"])
        self.assertEqual(engine.search("unknown"), [])
        self.assertEqual(engine.search(""), [])

    def test_packing_never_exceeds_budget_and_reports_skips(self):
        packed = pack_context([{"chunk_id": "a", "snippet": "x" * 40}, {"chunk_id": "b", "snippet": "ok"}], 5)
        self.assertEqual([x["chunk_id"] for x in packed["items"]], ["b"])
        self.assertLessEqual(packed["total_token_count"], 5)
        self.assertTrue(packed["truncated"])

    def test_gold_changed_function_and_module_boundary(self):
        patch = "--- a/auth/core.py\n+++ b/auth/core.py\n@@ -6,1 +6,1 @@\n-    return user_name.strip()\n+    return user_name.lower()\n@@ -14,1 +14,1 @@\n-SETTING = 1\n+SETTING = 2\n"
        gold = extract_gold(patch, {"auth/core.py": SOURCE})
        self.assertEqual(gold["gold_files"], ["auth/core.py"])
        self.assertEqual(gold["gold_functions"], ["auth/core.py::auth.core.login"])
        self.assertIn("module_edit", [x["disposition"] for x in gold["mapping_events"]])

    def test_new_file_cannot_be_retrieved_from_base(self):
        patch = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+def new():\n+    return 1\n"
        gold = extract_gold(patch, {})
        self.assertEqual(gold["gold_files"], [])
        self.assertEqual(gold["unretrievable_files"], ["new.py"])

    def test_function_metrics_dedup_windows_before_k(self):
        ranked = [{"path": "a.py", "parent_id": "a.py::a.f"}, {"path": "a.py", "parent_id": "a.py::a.f"}, {"path": "b.py", "parent_id": "b.py::b.g"}]
        metrics = evaluate_ranking(ranked, {"gold_files": ["b.py"], "gold_functions": ["b.py::b.g"]}, ks=(1, 2))
        self.assertEqual(metrics["file_recall@2"], 1)
        self.assertEqual(metrics["function_recall@2"], 1)
        self.assertEqual(metrics["file_mrr"], 0.5)

    def test_empty_gold_is_ineligible_not_perfect_or_zero(self):
        metrics = evaluate_ranking([], {"gold_files": [], "gold_functions": []})
        self.assertIsNone(metrics["function_recall@3"])


if __name__ == "__main__":
    unittest.main()
