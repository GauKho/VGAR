import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from m2_retrieval.evaluation import evaluate_manifest, evaluate_task
from m2_retrieval.evidence import sha256, write_json
from m2_retrieval.m1_adapter import adapt_context, compare_run


def inputs():
    row = {"instance_id": "sample-1", "repo": "demo/demo", "base_commit": "a" * 40,
           "problem_statement": "login validates token", "patch": "--- a/auth.py\n+++ b/auth.py\n@@ -2 +2 @@\n-    return True\n+    return False\n"}
    result = evaluate_task(row, {"auth.py": "def login(token):\n    return True\n"}, budget_tokens=512)
    export = {k: result[k] for k in ("instance_id", "repository", "base_commit", "query_hash", "corpus_hash")}
    export["context"] = {"graph_version": "real-version", "anchor_ids": [], "token_budget": 512, "total_token_count": 20,
                         "truncated": False, "items": [{"node_id": "fn-1", "path": "auth.py", "symbol": "auth.login",
                         "range": {"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 15}, "snippet": "def login(token):\n    return True",
                         "relevance_score": 0.7, "confidence": 0.9, "graph_distance": 1, "graph_rationale": ["call relation"], "token_count": 20}]}
    return row, result, export


class HandoffTests(unittest.TestCase):
    def test_adapter_rejects_fabricated_snippet_even_with_valid_metadata(self):
        _, result, export = inputs()
        export["context"]["items"][0]["snippet"] = "def login(token):\n    return False"
        with self.assertRaisesRegex(ValueError, "snippet"):
            adapt_context(export, result)

    def test_adapter_rejects_inconsistent_tokens_and_path(self):
        _, result, original = inputs()
        for mutation in ("tokens", "path", "columns"):
            export = copy.deepcopy(original)
            if mutation == "tokens":
                export["context"]["total_token_count"] = 10
            elif mutation == "path":
                export["context"]["items"][0]["path"] = "../auth.py"
            else:
                export["context"]["items"][0]["range"]["end_col"] = 999
            with self.assertRaises(ValueError):
                adapt_context(export, result)

    def test_unknown_function_labels_are_not_scored_as_complete(self):
        row, _, _ = inputs()
        row["patch"] = row["patch"].replace("return True", "return WrongBase")
        result = evaluate_task(row, {"auth.py": "def login(token):\n    return True\n"})
        self.assertIsNone(result["metrics"]["function_recall@3"])
        self.assertFalse(result["gold"]["function_labels_complete"])

    def test_comparison_marks_missing_m1_not_a_fake_zero(self):
        _, result, _ = inputs()
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            write_json(run / "result.json", {"task_results": [{"instance_id": "sample-1", "status": "SUCCEEDED"}]})
            write_json(run / "tasks" / "sample-1.json", result)
            output = compare_run(run, Path(temporary) / "exports", Path(temporary) / "results")
            self.assertEqual(output[1]["status"], "AWAITING_M1")
            self.assertEqual(output[1]["paired_tasks"], 0)

    def test_comparison_uses_same_budget_context_not_unbounded_bm25(self):
        _, result, exported = inputs()
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            exports = Path(temporary) / "exports"
            write_json(run / "result.json", {"task_results": [{"instance_id": "sample-1", "status": "SUCCEEDED"}]})
            write_json(run / "tasks" / "sample-1.json", result)
            write_json(exports / "sample-1.json", exported)
            _, report = compare_run(run, exports, Path(temporary) / "results")
            self.assertEqual(report["paired_tasks"], 1)
            self.assertEqual(report["status"], "SUCCEEDED")
            self.assertEqual(report["pairs"][0]["graph_metrics"]["function_recall@3"], 1)


if __name__ == "__main__":
    unittest.main()
