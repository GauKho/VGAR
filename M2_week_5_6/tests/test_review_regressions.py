import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from m2_retrieval.chunks import extract_chunks, is_source
from m2_retrieval.evaluation import evaluate_manifest, evaluate_task
from m2_retrieval.evidence import write_json
from m2_retrieval.gold_labels import extract_gold
from m2_retrieval.m1_adapter import compare_run
from m2_retrieval.metrics import evaluate_ranking
from test_handoff_and_failure import inputs
import test_resume as resume_fixtures


class ReviewRegressions(unittest.TestCase):
    def test_pytest_testing_directory_is_not_production_corpus(self):
        self.assertFalse(is_source("testing/python/collect.py"))
        self.assertTrue(is_source("src/_pytest/config/__init__.py"))

    def test_formfeed_does_not_shift_ast_diff_or_chunk_lines(self):
        source = "INTRO=1\n\f\ndef f():\n    return 1\n"
        patch = "--- a/a.py\n+++ b/a.py\n@@ -4 +4 @@\n-    return 1\n+    return 2\n"
        chunks, _ = extract_chunks({"a.py": source})
        function = next(c for c in chunks if c["kind"] == "function")
        self.assertIn("return 1", function["snippet"])
        self.assertEqual(extract_gold(patch, {"a.py": source})["gold_functions"], ["a.py::a.f"])

    def test_module_only_change_does_not_exclude_other_gold_function(self):
        patch = "--- a/constants.py\n+++ b/constants.py\n@@ -1 +1 @@\n-VALUE=1\n+VALUE=2\n--- a/a.py\n+++ b/a.py\n@@ -2 +2 @@\n-    return 1\n+    return 2\n"
        gold = extract_gold(patch, {"constants.py": "VALUE=1\n", "a.py": "def f():\n    return 1\n"})
        self.assertTrue(gold["function_labels_complete"])
        self.assertEqual(gold["gold_functions"], ["a.py::a.f"])

    def test_exact_unique_context_relocation_reports_offset_and_maps_actual_line(self):
        source = "# two extra lines\n# at base\ndef f():\n    return 1\n"
        patch = "--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
        gold = extract_gold(patch, {"a.py": source})
        self.assertEqual(gold["gold_functions"], ["a.py::a.f"])
        relocated = [e for e in gold["mapping_events"] if e["disposition"] == "hunk_relocated"]
        self.assertEqual(relocated[0]["offset_lines"], 2)

    def test_duplicate_qualified_definition_is_not_a_false_gold_hit(self):
        source = '@register("first")\ndef handler():\n    return 1\n\n@register("second")\ndef handler():\n    return 2\n'
        patch = "--- a/a.py\n+++ b/a.py\n@@ -3 +3 @@\n-    return 1\n+    return 9\n"
        chunks, _ = extract_chunks({"a.py": source})
        functions = [c for c in chunks if c["kind"] == "function"]
        self.assertEqual(len({c["parent_id"] for c in functions}), 2)
        gold = extract_gold(patch, {"a.py": source})
        metrics = evaluate_ranking([functions[1]], gold)
        self.assertEqual(metrics["function_recall@3"], 0)

    def test_malformed_m1_root_does_not_abort_comparison_evidence(self):
        _, result, _ = inputs()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "run/result.json", {"task_results": [{"instance_id": "sample-1", "status": "SUCCEEDED"}]})
            write_json(root / "run/tasks/sample-1.json", result)
            write_json(root / "exports/sample-1.json", [])
            directory, record = compare_run(root / "run", root / "exports", root / "results")
            self.assertTrue(record["complete"])
            self.assertEqual(len(record["invalid_exports"]), 1)
            self.assertNotEqual(record["status"], "RUNNING")

    def test_tampered_resume_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = resume_fixtures.ResumeTests().prepare(root)
            run, _ = evaluate_manifest(root, manifest, offline=True)
            file = run / "tasks/demo-1.json"
            artifact = json.loads(file.read_text(encoding="utf-8"))
            artifact["metrics"]["function_recall@3"] = 0.123
            write_json(file, artifact)
            with self.assertRaisesRegex(ValueError, "hash|integrity"):
                evaluate_manifest(root, manifest, offline=True, resume=run)

    def test_complete_rank_identity_trace_replays_tail_mrr(self):
        sources = {f"a_{i:03d}.py": "def f():\n    return marker\n" for i in range(101)}
        row, _, _ = inputs()
        row["problem_statement"] = "marker"
        row["patch"] = "--- a/a_100.py\n+++ b/a_100.py\n@@ -2 +2 @@\n-    return marker\n+    return 1\n"
        result = evaluate_task(row, sources)
        self.assertAlmostEqual(result["metrics"]["function_mrr"], 1 / 101)
        self.assertEqual(result["ranked_identity_order"]["functions"][-1], "a_100.py::a_100.f")

    def test_bm25_scores_are_identical_across_python_hash_seeds(self):
        program = "from m2_retrieval.bm25 import BM25; import json; words=['alpha','beta','gamma','delta','epsilon','theta','sigma','omega','rho','psi']; docs=[{'chunk_id':str(i),'text':' '.join(words[:i+1]* (i+1))} for i in range(10)]; print(json.dumps(BM25(docs).search(' '.join(words)),sort_keys=True))"
        outputs = [subprocess.check_output([sys.executable, "-c", program], env=dict(os.environ, PYTHONHASHSEED=str(seed)), text=True) for seed in (1, 2, 3)]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
