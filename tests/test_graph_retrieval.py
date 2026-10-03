from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from vgar.contracts.context import ContextPayload
from vgar.contracts.error import GraphError, InvalidLimitError, InvalidQueryError, NodeNotFoundError
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
from vgar.graph.task_overlay import TaskOverlayBuilder


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "sample_repo"


def counter(text: str) -> int:
    return len(re.findall(r"\S+", text))


class GraphRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = PythonGraphBuilder(repo_key="demo/retrieval", repository_revision="fixture",
                                       use_jedi=False).build(SAMPLE)

    def retriever(self, graph=None, root=SAMPLE, **kwargs):
        return GraphContextRetriever(graph or self.graph, root,
            count_tokens=kwargs.pop("count_tokens", counter), counter_label="test-whitespace:not-model-tokens", **kwargs)

    def node_id(self, name, kind="Function", graph=None):
        return next(node["id"] for node in (graph or self.graph)["nodes"]
                    if name in (node["name"], node["qualified_name"]) and node["type"] == kind)

    def test_callers_callees_are_one_semantic_hop_not_callsite_hops(self) -> None:
        result = self.retriever(config=RetrievalConfig(max_hops=1)).retrieve([self.node_id("login")], 1000)
        candidates = {item["symbol"]: item for item in result.candidates}
        self.assertEqual(candidates["web.routes.login_handler"]["graph_distance"], 1)
        self.assertEqual(candidates["tests.test_auth.test_login"]["graph_distance"], 1)
        self.assertTrue(any("CALLERS:" in reason for reason in candidates["web.routes.login_handler"]["graph_rationale"]))
        result = self.retriever(config=RetrievalConfig(max_hops=1)).retrieve([self.node_id("login_handler")], 1000)
        login = next(item for item in result.candidates if item["node_id"] == self.node_id("login"))
        self.assertEqual(login["graph_distance"], 1)
        self.assertTrue(any("CALLS:" in reason for reason in login["graph_rationale"]))

    def test_import_edges_fold_import_node_and_keep_reverse_dependents(self) -> None:
        module = self.node_id("auth.service", "Module")
        result = self.retriever(config=RetrievalConfig(max_hops=1)).retrieve([module], 1000)
        web = next(item for item in result.candidates if item["symbol"] == "web.routes")
        self.assertEqual(web["graph_distance"], 1)
        self.assertTrue(any("IMPORTED_BY:" in reason for reason in web["graph_rationale"]))

    def test_failing_test_proximity_uses_confirmed_overlay_links(self) -> None:
        overlay = TaskOverlayBuilder(self.graph).build("login-task", "login fails", ["tests/test_auth.py::test_login"])
        result = self.retriever().retrieve([self.node_id("login")], 1000, overlay=overlay)
        test = next(item for item in result.candidates if item["symbol"] == "tests.test_auth.test_login")
        login = next(item for item in result.candidates if item["node_id"] == self.node_id("login"))
        self.assertEqual(test["features"]["failing_test_proximity"], 1)
        self.assertEqual(login["features"]["failing_test_proximity"], 0.5)
        self.assertEqual(result.overlay_id, overlay.overlay_id)
        self.assertNotIn("failing_test_proximity", result.unavailable_features)

    def test_missing_features_are_explicit_and_history_needs_provenance(self) -> None:
        result = self.retriever().retrieve([self.node_id("login")], 1000, issue_text="login")
        self.assertIn("recent_change_frequency", result.unavailable_features)
        self.assertIn("architecture_dependencies", result.unavailable_features)
        self.assertIn("failing_test_proximity", result.unavailable_features)
        self.assertIsNone(result.candidates[0]["features"]["recent_change_frequency"])
        with self.assertRaises(InvalidQueryError):
            self.retriever(change_counts={"src/auth/service.py": 2})
        result = self.retriever(change_counts={"src/auth/service.py": 2}, history_label="test-only:2 commits").retrieve(
            [self.node_id("login")], 1000)
        login = next(item for item in result.candidates if item["node_id"] == self.node_id("login"))
        self.assertEqual(login["features"]["recent_change_frequency"], 1)
        self.assertEqual(result.history_label, "test-only:2 commits")

    def test_task_similarity_can_rank_a_related_symbol_above_the_anchor(self) -> None:
        weights = {name: float(name == "task_similarity") for name in RetrievalConfig().weights}
        result = self.retriever(config=RetrievalConfig(weights=weights)).retrieve(
            [self.node_id("login")], 1000, issue_text="login_handler")
        self.assertEqual(result.candidates[0]["node_id"], self.node_id("login_handler"))

    def test_supplied_history_affects_ranking_without_being_invented(self) -> None:
        test_id = self.node_id("test_login", "Test")
        weights = {name: float(name == "recent_change_frequency") for name in RetrievalConfig().weights}
        result = self.retriever(config=RetrievalConfig(weights=weights), change_counts={test_id: 3},
                                history_label="synthetic test history").retrieve([self.node_id("login")], 1000)
        self.assertEqual(result.candidates[0]["node_id"], test_id)
        self.assertEqual(result.candidates[0]["features"]["recent_change_frequency"], 1)

    def test_confidence_is_bottleneck_and_public_api_feature_is_a_proxy(self) -> None:
        graph = copy.deepcopy(self.graph)
        call = next(edge for edge in graph["edges"] if edge["type"] == "CALLS"
                    and edge["target_id"] == self.node_id("login")
                    and next(node for node in graph["nodes"] if node["id"] == edge["source_id"])["path"] == "src/web/routes.py")
        call["confidence"] = 0.7
        result = self.retriever(graph, config=RetrievalConfig(max_hops=1)).retrieve([self.node_id("login_handler")], 1000)
        login = next(item for item in result.candidates if item["node_id"] == self.node_id("login"))
        self.assertEqual(login["confidence"], 0.7)
        self.assertGreater(login["features"]["public_api_risk"], 0.5)

    def test_bfs_cycles_confidence_filter_and_depth_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text(
                "def a():\n    b()\n\ndef b():\n    c()\n\ndef c():\n    a()\n", encoding="utf-8")
            graph = PythonGraphBuilder(repo_key="demo/cycle", repository_revision="fixture", use_jedi=False).build(root)
            result = self.retriever(graph, root, config=RetrievalConfig(max_hops=1)).retrieve([self.node_id("a", graph=graph)], 1000)
            self.assertEqual(len({item["node_id"] for item in result.candidates}), len(result.candidates))
            self.assertTrue(all(item["graph_distance"] <= 1 for item in result.candidates))
            call = next(edge for edge in graph["edges"] if edge["type"] == "CALLS"
                        and edge["target_id"] == self.node_id("b", graph=graph))
            call["confidence"] = 0.3
            result = self.retriever(graph, root, config=RetrievalConfig(max_hops=1)).retrieve([self.node_id("a", graph=graph)], 1000)
            self.assertFalse(any(item["node_id"] == self.node_id("b", graph=graph) for item in result.candidates))

    def test_deterministic_ranking_input_dedup_and_candidate_limit(self) -> None:
        anchors = [self.node_id("login"), self.node_id("login_handler")]
        retriever = self.retriever()
        first = retriever.retrieve(anchors, 1000, issue_text="login password")
        second = retriever.retrieve(list(reversed(anchors)) + anchors, 1000, issue_text="login password")
        self.assertEqual(asdict(first), asdict(second))
        limited = self.retriever(config=RetrievalConfig(max_candidates=1)).retrieve([anchors[0]], 1000)
        self.assertEqual(len(limited.candidates), 1)
        self.assertTrue(limited.context.truncated)
        self.assertTrue(limited.traversal_limited)

    def test_budget_is_exact_and_whole_snippets_skip_without_clipping(self) -> None:
        anchor = self.node_id("login")
        retriever = self.retriever(config=RetrievalConfig(max_hops=0))
        full = retriever.get_related_context([anchor], 1000)
        size = full.items[0].token_count
        exact = retriever.get_related_context([anchor], size)
        self.assertFalse(exact.truncated)
        self.assertEqual(exact.total_token_count, size)
        small = retriever.get_related_context([anchor], size - 1)
        self.assertEqual(small.items, [])
        self.assertTrue(small.truncated)
        self.assertEqual(exact.items[0].snippet, full.items[0].snippet)
        ContextPayload.model_validate_json(exact.model_dump_json())

    def test_oversized_candidate_does_not_block_later_smaller_candidate(self) -> None:
        result = self.retriever(count_tokens=lambda text: 10000 if "return bool(username" in text else 1).retrieve(
            [self.node_id("login")], 2)
        self.assertTrue(result.context.items)
        self.assertLessEqual(result.context.total_token_count, 2)
        self.assertTrue(result.context.truncated)
        self.assertTrue(any(item["reason"] == "token_budget" for item in result.omissions))

    def test_overlapping_ranges_do_not_duplicate_source_text(self) -> None:
        result = self.retriever().retrieve([self.node_id("login")], 1000)
        ranges = [(item.path, self.retriever().nodes[item.node_id]["range"]) for item in result.context.items]
        for index, (path, first) in enumerate(ranges):
            for other_path, second in ranges[index + 1:]:
                if path == other_path:
                    self.assertFalse(first["start_byte"] < second["end_byte"] and second["start_byte"] < first["end_byte"])
        self.assertTrue(any(item["reason"] == "overlapping_selected_range" for item in result.omissions))

    def test_utf8_and_crlf_snippet_ranges_match_actual_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = 'def café():\r\n    return "xin chào 👋"\r\n'.encode("utf-8")
            (root / "unicode.py").write_bytes(data)
            graph = PythonGraphBuilder(repo_key="demo/unicode", repository_revision="fixture", use_jedi=False).build(root)
            result = self.retriever(graph, root, config=RetrievalConfig(max_hops=0)).retrieve([self.node_id("café", graph=graph)], 1000)
            item = result.context.items[0]
            node = next(node for node in graph["nodes"] if node["id"] == item.node_id)
            self.assertEqual(item.snippet.encode("utf-8"), data[node["range"]["start_byte"]:node["range"]["end_byte"]])

    def test_changed_deleted_and_added_sources_require_snapshot_refresh(self) -> None:
        for change in ("edit", "delete", "add"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                shutil.copytree(SAMPLE, root)
                retriever = self.retriever(root=root)
                file = root / "src" / "auth" / "service.py"
                if change == "edit":
                    file.write_text("# changed\n" + file.read_text(encoding="utf-8"), encoding="utf-8")
                elif change == "delete":
                    file.unlink()
                else:
                    (root / "new.py").write_text("def new(): pass\n", encoding="utf-8")
                with self.assertRaises(GraphError) as error:
                    retriever.retrieve([self.node_id("login")], 1000)
                self.assertEqual(error.exception.code, "GRAPH_ERROR")

    def test_source_changed_during_token_counting_is_not_returned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            shutil.copytree(SAMPLE, root)
            def mutate(text):
                (root / "new.py").write_text("# added during retrieval\n", encoding="utf-8")
                return counter(text)
            with self.assertRaises(GraphError):
                self.retriever(root=root, count_tokens=mutate).retrieve([self.node_id("login")], 1000)

    def test_invalid_node_hash_and_inconsistent_byte_range_fail_closed(self) -> None:
        for change in ("hash", "range", "path"):
            with self.subTest(change=change):
                graph = copy.deepcopy(self.graph)
                node = next(node for node in graph["nodes"] if node["id"] == self.node_id("login"))
                if change == "hash":
                    node["content_hash"] = "sha256:wrong"
                elif change == "range":
                    node["range"]["start_col"] += 1
                else:
                    node["path"] = "../outside.py"
                with self.assertRaises(GraphError):
                    self.retriever(graph).retrieve([node["id"]], 1000)

    def test_unknown_non_source_and_wrong_snapshot_inputs_are_rejected(self) -> None:
        retriever = self.retriever()
        with self.assertRaises(NodeNotFoundError):
            retriever.retrieve(["missing"], 1000)
        repository = next(node["id"] for node in self.graph["nodes"] if node["type"] == "Repository")
        with self.assertRaises(InvalidQueryError):
            retriever.retrieve([repository], 1000)
        overlay = TaskOverlayBuilder(self.graph).build("task", "login")
        overlay.graph_version = "different-snapshot"
        with self.assertRaises(InvalidQueryError):
            retriever.retrieve([self.node_id("login")], 1000, overlay=overlay)

    def test_empty_anchors_and_invalid_limits_or_counter(self) -> None:
        result = self.retriever().retrieve([], 1000)
        self.assertEqual(result.context.items, [])
        self.assertFalse(result.context.truncated)
        for limit in (0, -1, True):
            with self.subTest(limit=limit), self.assertRaises(InvalidLimitError):
                self.retriever().retrieve([], limit)
        with self.assertRaises(InvalidLimitError):
            RetrievalConfig(max_hops=-1)
        for value in (-1, True, 0.5):
            with self.subTest(counter=value), self.assertRaises(InvalidQueryError):
                self.retriever(count_tokens=lambda text: value).retrieve([self.node_id("login")], 1000)

    def test_cli_issue_to_context_keeps_base_graph_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            path.write_text(json.dumps(self.graph), encoding="utf-8")
            before = path.read_bytes()
            process = subprocess.run([sys.executable, str(ROOT / "scripts/get_related_context.py"),
                str(path), str(SAMPLE), "--budget-tokens", "1000", "--demo-counter", "--explain",
                "--issue-text", "login fails", "--failing-test", "tests/test_auth.py::test_login"],
                capture_output=True, text=True, encoding="utf-8", check=True)
            result = json.loads(process.stdout)
            payload = ContextPayload.model_validate(result["context"])
            self.assertTrue(payload.items)
            self.assertIn("not-model-tokens", result["counter_label"])
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
