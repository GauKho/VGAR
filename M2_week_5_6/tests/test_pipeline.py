import json
import sys
import tempfile
import unittest
from pathlib import Path

from m2_retrieval.dataset import select_tasks, validate_task
from m2_retrieval.evidence import record_command
from m2_retrieval.evaluation import evaluate_task
from m2_retrieval.m1_adapter import adapt_context


def task(identity="demo-1"):
    return {"instance_id": identity, "repo": "demo/demo", "base_commit": "a" * 40,
            "problem_statement": "login accepts bad token", "patch": "--- a/auth.py\n+++ b/auth.py\n@@ -2,1 +2,1 @@\n-    return True\n+    return False\n"}


class PipelineTests(unittest.TestCase):
    def test_evaluation_retrieves_gold_and_does_not_mutate_source(self):
        sources = {"auth.py": "def login(token):\n    return True\n", "math.py": "def square(x):\n    return x*x\n"}
        before = dict(sources)
        record = evaluate_task(task(), sources, budget_tokens=512)
        self.assertEqual(record["status"], "SUCCEEDED")
        self.assertEqual(record["metrics"]["function_recall@3"], 1)
        self.assertEqual(sources, before)
        self.assertNotIn("return False", json.dumps(record["context"]))

    def test_ranking_does_not_change_when_gold_patch_changes(self):
        sources = {"auth.py": "def login(token):\n    return True\n", "math.py": "def square(x):\n    return x*x\n"}
        a = task()
        b = dict(a, patch="--- a/math.py\n+++ b/math.py\n@@ -2,1 +2,1 @@\n-    return x*x\n+    return x**2\n")
        self.assertEqual(evaluate_task(a, sources)["ranked"], evaluate_task(b, sources)["ranked"])

    def test_selection_is_deterministic_stratified_and_excludes_single_file(self):
        rows = []
        for repo in ("a/a", "b/b"):
            for i in range(3):
                row = task(f"{repo.replace('/', '__')}-{i}")
                row["repo"] = repo
                row["patch"] += "--- a/other.py\n+++ b/other.py\n@@ -1 +1 @@\n-x=1\n+x=2\n"
                rows.append(row)
        rows.append(task("single"))
        selected, audit = select_tasks(rows, 4)
        reversed_selected, _ = select_tasks(list(reversed(rows)), 4)
        self.assertEqual([r["instance_id"] for r in selected], [r["instance_id"] for r in reversed_selected])
        self.assertEqual([r["repo"] for r in selected], ["a/a", "b/b", "a/a", "b/b"])
        self.assertEqual(audit["eligible_count"], 6)

    def test_path_traversal_repo_or_non_hash_revision_is_rejected(self):
        for overrides in ({"repo": "../evil"}, {"base_commit": "main"}, {"instance_id": "../outside"}):
            with self.assertRaises(ValueError):
                validate_task(dict(task(), **overrides))

    def test_recorder_keeps_full_output_and_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, record = record_command([sys.executable, "-c", "import sys; print('hello'); print('problem', file=sys.stderr); sys.exit(2)"], temporary, Path(temporary) / "results")
            self.assertEqual(record["exit_code"], 2)
            self.assertIn("hello", record["stdout"])
            self.assertIn("problem", record["stderr"])
            self.assertTrue(path.exists())
            _, timed = record_command([sys.executable, "-c", "import time; time.sleep(2)"], temporary, Path(temporary) / "results", timeout=0.1)
            self.assertEqual(timed["status"], "TIMEOUT")

    def test_m1_rejects_wrong_commit_and_unsafe_context(self):
        result = evaluate_task(task(), {"auth.py": "def login(token):\n    return True\n"})
        exported = {"instance_id": "demo-1", "repository": "demo/demo", "base_commit": "b" * 40,
                    "query_hash": result["query_hash"], "corpus_hash": result["corpus_hash"], "context": {}}
        with self.assertRaises(ValueError):
            adapt_context(exported, result)

    def test_m1_valid_context_maps_span_to_function_without_fabricating_graph_fields(self):
        result = evaluate_task(task(), {"auth.py": "def login(token):\n    return True\n"}, budget_tokens=512)
        exported = {"instance_id": "demo-1", "repository": "demo/demo", "base_commit": "a" * 40,
                    "query_hash": result["query_hash"], "corpus_hash": result["corpus_hash"], "context": {
                        "graph_version": "snapshot-1", "anchor_ids": ["issue:1"], "token_budget": 512,
                        "total_token_count": 10, "truncated": False, "items": [{
                            "node_id": "real-m1-id", "path": "auth.py", "symbol": "auth.login",
                            "range": {"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 15},
                            "snippet": "def login(token):\n    return True", "relevance_score": 0.8, "graph_distance": 1,
                            "graph_rationale": ["symbol mention"], "confidence": 0.9, "token_count": 10}]}}
        adapted = adapt_context(exported, result)
        self.assertEqual(adapted["items"][0]["parent_id"], "auth.py::auth.login")
        self.assertEqual(adapted["items"][0]["node_id"], "real-m1-id")


if __name__ == "__main__":
    unittest.main()
