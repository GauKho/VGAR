from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from vgar.contracts.schema import validate_graph_document
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.task_overlay import TaskOverlayBuilder


ROOT = Path(__file__).resolve().parents[1]


class TaskOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = PythonGraphBuilder(
            repo_key="demo/overlay", repository_revision="fixture", use_jedi=False,
        ).build(ROOT / "tests" / "fixtures" / "sample_repo")

    def test_issue_mentions_and_reported_failure_use_existing_endpoints(self) -> None:
        overlay = TaskOverlayBuilder(self.document).build(
            "task-login", "login fails at src/auth/service.py:2",
            ["tests/test_auth.py::test_login[param]"],
        )
        issue = overlay.nodes[0]
        nodes = {node["id"]: node for node in self.document["nodes"] + overlay.nodes}
        self.assertEqual(issue["type"], "Issue")
        self.assertIsNone(issue["path"])
        self.assertIsNone(issue["range"])
        self.assertEqual(overlay.graph_version, self.document["graph_version"])
        mentions = [edge for edge in overlay.edges if edge["type"] == "MENTIONS"]
        reproduces = [edge for edge in overlay.edges if edge["type"] == "REPRODUCES"]
        self.assertEqual(len(mentions), 2)
        self.assertEqual(len(reproduces), 1)
        self.assertTrue(all(edge["source_id"] == issue["id"] for edge in mentions))
        self.assertEqual(nodes[reproduces[0]["source_id"]]["type"], "Test")
        self.assertEqual(reproduces[0]["target_id"], issue["id"])
        self.assertFalse(reproduces[0]["properties"]["execution_verified"])
        self.assertTrue(reproduces[0]["provenance"]["evidence"])
        validate_graph_document({
            **self.document, "nodes": self.document["nodes"] + overlay.nodes,
            "edges": self.document["edges"] + overlay.edges,
        })

    def test_mentioned_test_is_not_automatically_reported_as_failing(self) -> None:
        overlay = TaskOverlayBuilder(self.document).build("task", "test_login fails")
        self.assertEqual([edge["type"] for edge in overlay.edges], ["MENTIONS"])

    def test_failing_location_must_resolve_to_test_not_file_or_function(self) -> None:
        for reports in (["tests/test_auth.py"], ["src/auth/service.py:2"], ["missing.py::test_login"]):
            with self.subTest(reports=reports):
                overlay = TaskOverlayBuilder(self.document).build("task", "", reports)
                self.assertFalse(any(edge["type"] == "REPRODUCES" for edge in overlay.edges))

    def test_ambiguous_failure_retains_candidates_without_reproduces(self) -> None:
        graph = self._ambiguous_graph()
        overlay = TaskOverlayBuilder(graph).build("task", "", ["test_same"])
        self.assertEqual(len(overlay.grounding.ambiguous_matches), 1)
        self.assertEqual(len(overlay.edges), 2)
        self.assertTrue(all(edge["type"] == "MENTIONS" for edge in overlay.edges))
        self.assertTrue(all(edge["properties"]["has_ambiguous_evidence"] for edge in overlay.edges))
        self.assertTrue(all(edge["confidence"] == 0.5 for edge in overlay.edges))

    def test_independent_selector_confirms_only_one_ambiguous_test(self) -> None:
        graph = self._ambiguous_graph()
        overlay = TaskOverlayBuilder(graph).build(
            "task", "", ["test_same", "tests/test_one.py::test_same"],
        )
        reproduces = [edge for edge in overlay.edges if edge["type"] == "REPRODUCES"]
        self.assertEqual(len(reproduces), 1)
        node = next(node for node in graph["nodes"] if node["id"] == reproduces[0]["source_id"])
        self.assertEqual(node["path"], "tests/test_one.py")
        self.assertEqual([item["kind"] for item in reproduces[0]["provenance"]["evidence"]], ["pytest_selector"])

    def test_issue_confirmation_does_not_resolve_ambiguous_failing_input(self) -> None:
        graph = self._ambiguous_graph()
        overlay = TaskOverlayBuilder(graph).build(
            "task", "tests/test_one.py::test_same", ["test_same"],
        )
        self.assertEqual(overlay.grounding.anchors[0].score, 1.0)
        self.assertFalse(any(edge["type"] == "REPRODUCES" for edge in overlay.edges))

    def test_base_snapshot_and_other_task_are_not_mutated(self) -> None:
        graph = copy.deepcopy(self.document)
        before = copy.deepcopy(graph)
        builder = TaskOverlayBuilder(graph)
        first = builder.build("first", "login")
        first_json = asdict(first)
        builder.build("second", "test_login", ["test_login"])
        self.assertEqual(graph, before)
        self.assertEqual(asdict(first), first_json)
        graph["nodes"].clear()
        self.assertEqual(asdict(builder.build("first", "login")), first_json)

    def test_equivalent_reports_deduplicate_and_task_or_input_changes_identity(self) -> None:
        builder = TaskOverlayBuilder(self.document)
        reports = ["test_login", "tests/test_auth.py::test_login"]
        first = builder.build("task", "login", reports)
        second = builder.build("task", "login", list(reversed(reports)) + reports)
        self.assertEqual(asdict(first), asdict(second))
        self.assertEqual(len({edge["id"] for edge in first.edges}), len(first.edges))
        self.assertNotEqual(first.overlay_id, builder.build("other", "login", reports).overlay_id)
        changed = builder.build("task", "different issue", reports)
        self.assertNotEqual(first.overlay_id, changed.overlay_id)
        self.assertEqual(first.nodes[0]["id"], changed.nodes[0]["id"])

    def test_empty_and_unmatched_tasks_have_no_invented_trace_edges(self) -> None:
        for text in ("", "unknown prose", "missing.py:9"):
            with self.subTest(text=text):
                overlay = TaskOverlayBuilder(self.document).build("task", text)
                self.assertEqual(len(overlay.nodes), 1)
                self.assertEqual(overlay.edges, [])

    def test_invalid_inputs_and_issue_collision_fail_explicitly(self) -> None:
        builder = TaskOverlayBuilder(self.document)
        with self.assertRaises(ValueError):
            builder.build(" ", "login")
        with self.assertRaises(TypeError):
            builder.build("task", "login", "test_login")
        with self.assertRaises(TypeError):
            builder.build("task", None)
        overlay = builder.build("task", "login")
        combined = {**self.document, "nodes": self.document["nodes"] + overlay.nodes,
                    "edges": self.document["edges"] + overlay.edges}
        with self.assertRaises(ValueError):
            TaskOverlayBuilder(combined).build("task", "login")

    def test_cli_exports_sidecar_without_writing_base_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph = Path(directory) / "graph.json"
            issue = Path(directory) / "issue.txt"
            graph.write_text(json.dumps(self.document), encoding="utf-8")
            issue.write_text("login fails", encoding="utf-8")
            before = graph.read_bytes()
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_task_overlay.py"),
                 str(graph), "--task-id", "cli-task", "--issue-file", str(issue),
                 "--failing-test", "tests/test_auth.py::test_login"],
                capture_output=True, text=True, encoding="utf-8", check=True,
            )
            overlay = json.loads(result.stdout)
            self.assertEqual(overlay["task_id"], "cli-task")
            self.assertEqual(overlay["graph_version"], self.document["graph_version"])
            self.assertEqual(len(overlay["nodes"]), 1)
            self.assertEqual(graph.read_bytes(), before)
            self.assertEqual(len([edge for edge in overlay["edges"] if edge["type"] == "REPRODUCES"]), 1)

    @staticmethod
    def _ambiguous_graph() -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            for filename in ("test_one.py", "test_two.py"):
                (root / "tests" / filename).write_text("def test_same():\n    pass\n", encoding="utf-8")
            return PythonGraphBuilder(
                repo_key="demo/ambiguous-tests", repository_revision="fixture", use_jedi=False,
            ).build(root)


if __name__ == "__main__":
    unittest.main()
