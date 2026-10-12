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
                                       ).build(SAMPLE)

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
        self.assertEqual(login["raw_failing_test_proximity"], 0.5)
        self.assertEqual(login["features"]["failing_test_proximity"], 0.5 * login['direct_task_similarity'])
        self.assertTrue(any(step.startswith(('CALLS:', 'TESTS:')) for step in login['failing_test_rationale']))
        self.assertEqual(result.overlay_id, overlay.overlay_id)
        self.assertNotIn("failing_test_proximity", result.unavailable_features)

    def test_include_filters_items_but_not_traversal_or_failing_test_proximity(self) -> None:
        overlay = TaskOverlayBuilder(self.graph).build("login-task", "login fails", ["tests/test_auth.py::test_login"])
        login = self.node_id("login")
        retriever = self.retriever()
        plain = retriever.retrieve([login], 1000, overlay=overlay)
        filtered = retriever.retrieve([login], 1000, overlay=overlay, include=lambda node: node["type"] != "Test")
        types = lambda result: {retriever.nodes[c["node_id"]]["type"] for c in result.candidates}
        self.assertIn("Test", types(plain))
        self.assertNotIn("Test", types(filtered))
        self.assertFalse(any(item.symbol.startswith("tests.") for item in filtered.context.items))
        self.assertGreater(filtered.config["filtered_by_include"], 0)
        self.assertEqual(plain.config["filtered_by_include"], 0)
        # Test nodes still serve failing_test_proximity of the remaining candidates.
        kept = next(c for c in filtered.candidates if c["node_id"] == login)
        self.assertEqual(kept["raw_failing_test_proximity"], 0.5)
        self.assertEqual(kept["features"]["failing_test_proximity"], 0.5 * kept['direct_task_similarity'])
        # include=None keeps the legacy behaviour exactly.
        self.assertEqual([c["node_id"] for c in plain.candidates],
                         [c["node_id"] for c in retriever.retrieve([login], 1000, overlay=overlay).candidates])

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

    def test_test_bonus_discriminates_issue_code_from_cleanup_and_file_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'test_app.py').write_text('''def repair_target(): return 1
def cleanup(): return None
def same_file_only(): return None
def test_repair():
    repair_target()
    cleanup()
''', encoding='utf-8')
            graph = PythonGraphBuilder(repo_key='demo/test-evidence', repository_revision='fixture').build(root)
            target = self.node_id('repair_target', graph=graph)
            overlay = TaskOverlayBuilder(graph).build('repair', 'repair_target fails', ['test_app.py::test_repair'])
            retriever = self.retriever(graph, root)
            result = retriever.retrieve([target], 1000, overlay=overlay)
            candidates = {c['symbol']:c for c in result.candidates}
            repair, cleanup = candidates['test_app.repair_target'], candidates['test_app.cleanup']
            self.assertEqual(repair['raw_failing_test_proximity'], .5)
            self.assertEqual(cleanup['raw_failing_test_proximity'], .5)
            self.assertGreater(repair['features']['failing_test_proximity'], 0)
            self.assertEqual(cleanup['features']['failing_test_proximity'], 0)
            self.assertEqual(candidates['test_app.same_file_only']['raw_failing_test_proximity'], 0)
            self.assertEqual(candidates['test_app.test_repair']['features']['failing_test_proximity'], 1)
            # Failing-test-only fallback and explicit ablation retain raw evidence.
            empty = TaskOverlayBuilder(graph).build('no-issue', '', ['test_app.py::test_repair'])
            for config, task in ((RetrievalConfig(), empty),
                                 (RetrievalConfig(gate_failing_test_evidence=False), overlay)):
                ungated = self.retriever(graph, root, config=config).retrieve([target], 1000, overlay=task)
                c = next(c for c in ungated.candidates if c['symbol']=='test_app.cleanup')
                self.assertEqual(c['features']['failing_test_proximity'], .5)

    def test_evidence_configuration_flags_require_booleans(self) -> None:
        for flag in ('use_source_evidence', 'prefer_relevant_paths', 'gate_failing_test_evidence'):
            with self.subTest(flag=flag), self.assertRaises(InvalidQueryError):
                RetrievalConfig(**{flag: 1})

    def test_task_similarity_can_rank_a_related_symbol_above_the_anchor(self) -> None:
        weights = {name: float(name == "task_similarity") for name in RetrievalConfig().weights}
        result = self.retriever(config=RetrievalConfig(weights=weights)).retrieve(
            [self.node_id("login")], 1000, issue_text="login_handler")
        self.assertEqual(result.candidates[0]["node_id"], self.node_id("login_handler"))

    def test_dependency_can_inherit_issue_relevance_but_file_membership_cannot(self) -> None:
        result = self.retriever(config=RetrievalConfig(max_hops=1, use_source_evidence=False)).retrieve(
            [self.node_id("login")], 1000, issue_text="login")
        caller = next(c for c in result.candidates if c['symbol'] == 'web.routes.login_handler')
        self.assertGreater(caller['features']['task_similarity'], caller['direct_task_similarity'])
        file = next(c for c in result.candidates if c['path'] == 'src/auth/service.py' and c['node_id'] != self.node_id('login'))
        self.assertEqual(file['features']['task_similarity'], file['direct_task_similarity'])

    def test_same_hop_dependency_evidence_is_not_hidden_by_containment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app.py').write_text('class Container:\n    def helper(self): return 1\ndef repair_entry(): Container.helper(None)\n', encoding='utf-8')
            graph = PythonGraphBuilder(repo_key='demo/paths', repository_revision='fixture').build(root)
            entry = self.node_id('repair_entry', graph=graph)
            container = self.node_id('Container', kind='Class', graph=graph)
            helper = self.node_id('helper', kind='Method', graph=graph)
            retriever = self.retriever(graph, root, config=RetrievalConfig(max_hops=1, use_source_evidence=False))
            states, _ = retriever._walk([container, entry], {container:.9, entry:.45}, task_words={'repair', 'entry'})
            self.assertEqual(states[helper][0], 1)
            self.assertEqual(states[helper][1], .45)
            self.assertTrue(any(step.startswith('CALLS:') for step in states[helper][2]))
            plain, _ = retriever._walk([container, entry], {container:.9, entry:.45})
            self.assertEqual(plain[helper][1], .9)

    def test_executable_evidence_discriminates_same_api_without_docstring_noise(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app.py').write_text('''class Actual:
    def handle(self, client):
        return client.timeout
class Noise:
    def handle(self, client):
        """timeout timeout timeout"""
        # timeout
        return None
''', encoding='utf-8')
            graph = PythonGraphBuilder(repo_key='demo/source', repository_revision='fixture').build(root)
            ids = [self.node_id(name, kind='Method', graph=graph) for name in ('app.Actual.handle', 'app.Noise.handle')]
            retriever = self.retriever(graph, root, config=RetrievalConfig(max_hops=0))
            result = retriever.retrieve(ids, 1000, issue_text='handle timeout')
            self.assertEqual(result.candidates[0]['symbol'], 'app.Actual.handle')
            self.assertGreater(result.candidates[0]['source_task_similarity'], 0)
            self.assertEqual(result.candidates[1]['source_task_similarity'], 0)
            self.assertEqual(asdict(result), asdict(retriever.retrieve(list(reversed(ids)), 1000, issue_text='handle timeout')))

    def test_popular_api_cannot_win_by_caller_count_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def helper(): pass\ndef repair_target(): pass\n"
                + "".join(f"def caller_{i}(): helper()\n" for i in range(12)), encoding="utf-8")
            graph = PythonGraphBuilder(repo_key="demo/popularity", repository_revision="fixture").build(root)
            ids = [self.node_id(name, graph=graph) for name in ("helper", "repair_target")]
            retriever = self.retriever(graph, root, config=RetrievalConfig(max_hops=0))
            result = retriever.retrieve(ids, 1000, issue_text="repair_target fails")
            self.assertEqual(result.candidates[0]["symbol"], "app.repair_target")
            self.assertEqual(result.config["normalized_weights"]["public_api_risk"], 0)
            popular = next(c for c in result.candidates if c["symbol"] == "app.helper")
            self.assertGreater(popular["features"]["public_api_risk"], 0.5)

    def test_global_frontier_leaves_room_for_relevant_callee_from_later_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def a_generic():\n" + "".join(f"    noise_{i}()\n" for i in range(10))
                + "def z_entry(): repair_target()\ndef repair_target(): pass\n"
                + "".join(f"def noise_{i}(): pass\n" for i in range(10)), encoding="utf-8")
            graph = PythonGraphBuilder(repo_key="demo/frontier", repository_revision="fixture").build(root)
            ids = [self.node_id(name, graph=graph) for name in ("a_generic", "z_entry")]
            retriever = self.retriever(graph, root, config=RetrievalConfig(max_hops=1, max_candidates=4))
            result = retriever.retrieve(ids, 1000, issue_text="repair_target", include=lambda n: n["type"] == "Function")
            self.assertIn("app.repair_target", [c["symbol"] for c in result.candidates])
            self.assertLessEqual(len(result.candidates), 4)
            self.assertTrue(result.traversal_limited)
            self.assertEqual(asdict(result), asdict(retriever.retrieve(list(reversed(ids)), 1000,
                issue_text="repair_target", include=lambda n: n["type"] == "Function")))

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
            graph = PythonGraphBuilder(repo_key="demo/cycle", repository_revision="fixture").build(root)
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

    def test_many_anchors_leave_room_for_a_callee(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text(
                "def a(): return z_target()\ndef z_target(): return 1\n"
                + "".join(f"def noise_{i}(): pass\n" for i in range(8)), encoding="utf-8",
            )
            graph = PythonGraphBuilder(repo_key="demo/quota", repository_revision="fixture").build(root)
            starts = [node["id"] for node in graph["nodes"] if node["type"] == "Function"
                      and node["name"] != "z_target"]
            retriever = self.retriever(graph, root, config=RetrievalConfig(max_candidates=4, max_hops=1))
            include = lambda node: node["type"] == "Function"
            result = retriever.retrieve(starts, 1000, include=include)
            target = next(item for item in result.candidates if item["symbol"] == "demo.z_target")
            self.assertEqual(target["graph_distance"], 1)
            self.assertTrue(any("CALLS:" in reason for reason in target["graph_rationale"]))
            self.assertLessEqual(len(result.candidates), 4)
            self.assertTrue(result.traversal_limited)
            reverse = retriever.retrieve(list(reversed(starts)), 1000, include=include)
            self.assertEqual(asdict(result), asdict(reverse))

    def test_file_anchor_reaches_class_methods_in_one_semantic_hop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Service:\n    def convert_date(self): return 1\n", encoding="utf-8")
            graph = PythonGraphBuilder(repo_key="demo/file-scope", repository_revision="fixture").build(root)
            file_id = self.node_id("app.py", "File", graph)
            result = self.retriever(graph, root, config=RetrievalConfig(max_hops=1)).retrieve(
                [file_id], 1000, include=lambda node: node["type"] == "Method")
            self.assertEqual([c["symbol"] for c in result.candidates], ["app.Service.convert_date"])
            self.assertEqual(result.candidates[0]["graph_distance"], 1)
            self.assertTrue(any("SOURCE_CONTAINS:" in r for r in result.candidates[0]["graph_rationale"]))

    def test_weak_anchor_distance_credit_and_issue_template_invariance(self) -> None:
        overlay = TaskOverlayBuilder(self.graph).build("weak", "login fails")
        result = self.retriever().retrieve([self.node_id("login")], 1000, overlay=overlay)
        login = next(c for c in result.candidates if c["node_id"] == self.node_id("login"))
        self.assertEqual(login["features"]["graph_distance"], 0.4)
        first = self.retriever().retrieve([self.node_id("login")], 1000, issue_text="login")
        second = self.retriever().retrieve([self.node_id("login")], 1000,
            issue_text="login <!-- unrelated narrative template --> https://example.com/login_handler")
        self.assertEqual(first.candidates, second.candidates)

    def test_filtered_test_anchor_does_not_consume_the_only_candidate_slot(self) -> None:
        retriever = self.retriever(config=RetrievalConfig(max_candidates=1, max_hops=1))
        result = retriever.retrieve([self.node_id("test_login", "Test")], 1000,
                                   include=lambda node: node["type"] == "Function")
        self.assertEqual([item["node_id"] for item in result.candidates], [self.node_id("login")])
        self.assertEqual(result.candidates[0]["graph_distance"], 1)
        self.assertEqual(result.context.items[0].symbol, "auth.service.login")

    def test_test_namespace_filter_also_applies_to_seed_quota(self) -> None:
        retriever = self.retriever(config=RetrievalConfig(max_candidates=1, max_hops=1))
        result = retriever.retrieve([self.node_id("test_login", "Test")], 1000, include=lambda node: True)
        self.assertEqual([item["node_id"] for item in result.candidates], [self.node_id("login")])

    def test_zero_hops_uses_full_quota_for_anchors(self) -> None:
        starts = [self.node_id("login"), self.node_id("login_handler")]
        result = self.retriever(config=RetrievalConfig(max_candidates=2, max_hops=0)).retrieve(starts, 1000)
        self.assertEqual({item["node_id"] for item in result.candidates}, set(starts))
        self.assertFalse(result.traversal_limited)

    def test_excluded_bridge_nodes_still_have_a_hard_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("".join(f"def f_{i}(): pass\n" for i in range(20)), encoding="utf-8")
            graph = PythonGraphBuilder(repo_key="demo/bridges", repository_revision="fixture").build(root)
            starts = [node["id"] for node in graph["nodes"] if node["type"] == "Function"]
            retriever = self.retriever(graph, root, config=RetrievalConfig(max_candidates=1))
            states, limited = retriever._walk(starts, {}, include=lambda node: False)
            self.assertLessEqual(len(states), 4)
            self.assertTrue(limited)
            self.assertEqual(retriever.retrieve(starts, 1000, include=lambda node: False).context.items, [])

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
            graph = PythonGraphBuilder(repo_key="demo/unicode", repository_revision="fixture").build(root)
            result = self.retriever(graph, root, config=RetrievalConfig(max_hops=0)).retrieve([self.node_id("café", graph=graph)], 1000)
            item = result.context.items[0]
            node = next(node for node in graph["nodes"] if node["id"] == item.node_id)
            self.assertEqual(item.snippet.encode("utf-8"), data[node["range"]["start_byte"]:node["range"]["end_byte"]])

    def test_file_and_module_ranges_cover_leading_whitespace_and_full_hash(self) -> None:
        for data in (b"\n\ndef login(): return 1\n", "\r\n\r\ndef café(): return 1\r\n".encode(), b"\n\n", b""):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "app.py").write_bytes(data)
                graph = PythonGraphBuilder(repo_key="demo/full-file", repository_revision="fixture").build(root)
                retriever = self.retriever(graph, root, config=RetrievalConfig(max_hops=0))
                for node in graph["nodes"]:
                    if node["type"] not in {"File", "Module"}:
                        continue
                    self.assertEqual(node["range"]["start_byte"], 0)
                    self.assertEqual(node["range"]["end_byte"], len(data))
                    result = retriever.retrieve([node["id"]], 1000)
                    self.assertEqual(result.context.items[0].snippet.encode("utf-8"), data)

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
        for issue in ('', 'login'):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                shutil.copytree(SAMPLE, root)
                def mutate(text):
                    (root / "new.py").write_text("# added during retrieval\n", encoding="utf-8")
                    return counter(text)
                with self.assertRaises(GraphError):
                    self.retriever(root=root, count_tokens=mutate).retrieve([self.node_id("login")], 1000, issue_text=issue)

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
