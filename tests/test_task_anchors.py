from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.grounding import TaskAnchorFinder


class TaskAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = TaskAnchorFinder(PythonGraphBuilder(
            repo_key="demo/anchors", repository_revision="fixture", use_jedi=False,
        ).build(Path(__file__).parent / "fixtures" / "sample_repo"))

    def test_exact_path_is_file_anchor(self) -> None:
        result = self.finder.find_task_anchors("Failure in src/auth/service.py")
        self.assertEqual([item.symbol for item in result.anchors], ["src/auth/service.py"])
        self.assertEqual(result.anchors[0].evidence[0].kind, "path")

    def test_path_line_selects_containing_function(self) -> None:
        result = self.finder.find_task_anchors("src/auth/service.py:2")
        self.assertEqual([item.symbol for item in result.anchors], ["auth.service.login"])

    def test_traceback_line_overrides_file_only_match(self) -> None:
        result = self.finder.find_task_anchors('File "src/web/routes.py", line 5, in login_handler')
        self.assertEqual([item.symbol for item in result.anchors], ["web.routes.login_handler"])
        self.assertEqual(result.anchors[0].score, 0.95)

    def test_pytest_selector_with_parameter_id(self) -> None:
        result = self.finder.find_task_anchors("", ["tests/test_auth.py::test_login[login_handler]"])
        self.assertEqual([item.symbol for item in result.anchors], ["tests.test_auth.test_login"])
        self.assertEqual(result.anchors[0].evidence[0].source, "failing_test")

    def test_selector_line_must_be_inside_the_selected_test(self) -> None:
        text = "tests/test_auth.py::test_login:999"
        result = self.finder.find_task_anchors("", [text])
        self.assertEqual(result.anchors, [])
        self.assertEqual(result.unmatched_locations, [text])

    def test_qualified_symbol_and_short_name(self) -> None:
        for text in ("auth.service.login fails", "login fails"):
            with self.subTest(text=text):
                result = self.finder.find_task_anchors(text)
                self.assertEqual([item.symbol for item in result.anchors], ["auth.service.login"])

    def test_ambiguous_basename_preserves_all_candidates(self) -> None:
        result = self.finder.find_task_anchors("service.py")
        self.assertEqual(len(result.anchors), 3)
        self.assertEqual(len(result.ambiguous_matches), 1)
        self.assertEqual(len(result.ambiguous_matches[0].candidate_ids), 3)
        self.assertTrue(all(item.score == 0.5 for item in result.anchors))

    def test_unknown_invalid_line_and_traversal_do_not_create_nodes(self) -> None:
        for text in (
            "unknown.py:5", "src/auth/service.py:999", "src/auth/service.py:0",
            "src/auth/service.py:-1", 'File "src/auth/service.py", line -1, in login',
            "../src/auth/service.py", "C:\\src\\auth\\service.py",
        ):
            with self.subTest(text=text):
                result = self.finder.find_task_anchors(text)
                self.assertEqual(result.anchors, [])
                self.assertEqual(result.unmatched_locations, [text])
        self.assertEqual(self.finder.find_task_anchors("unknown prose").anchors, [])

    def test_windows_relative_path_and_deterministic_deduplication(self) -> None:
        first = self.finder.find_task_anchors("src\\auth\\service.py:2 login login")
        second = self.finder.find_task_anchors("src\\auth\\service.py:2 login login")
        self.assertEqual(asdict(first), asdict(second))
        self.assertEqual(len(first.anchors), 1)
        self.assertEqual(len(first.anchors[0].evidence), 2)

    def test_invalid_traceback_does_not_fall_back_to_frame_symbol(self) -> None:
        text = 'File "missing.py", line 5, in login'
        result = self.finder.find_task_anchors(text)
        self.assertEqual(result.anchors, [])
        self.assertEqual(result.unmatched_locations, [text])

    def test_exclusive_end_line_does_not_belong_to_previous_symbol_or_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("def before():\n    pass\n\n", encoding="utf-8")
            graph = PythonGraphBuilder(
                repo_key="demo/ranges", repository_revision="fixture", use_jedi=False,
            ).build(root)
        # Exercise an end at column zero, as emitted for files and multiline ranges.
        function = next(node for node in graph["nodes"] if node["type"] == "Function")
        function["range"]["end_line"] = 3
        function["range"]["end_col"] = 0
        finder = TaskAnchorFinder(graph)
        result = finder.find_task_anchors("demo.py:3")
        self.assertEqual([anchor.symbol for anchor in result.anchors], ["demo.py"])
        self.assertEqual(finder.find_task_anchors("demo.py:4").anchors, [])

    def test_quoted_and_traceback_paths_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "src" / "my package"
            folder.mkdir(parents=True)
            (folder / "service.py").write_text("def unique_handler():\n    pass\n", encoding="utf-8")
            finder = TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/spaces", repository_revision="fixture", use_jedi=False,
            ).build(root))
        for text in ('"src/my package/service.py":2', 'File "src/my package/service.py", line 2, in unique_handler'):
            with self.subTest(text=text):
                result = finder.find_task_anchors(text)
                self.assertEqual(len(result.anchors), 1)
                self.assertEqual(result.anchors[0].path, "src/my package/service.py")
                self.assertEqual(result.anchors[0].evidence[0].kind, "path_line")

    def test_route_method_disambiguates_literal_decorators(self) -> None:
        finder = self._route_finder()
        result = finder.find_task_anchors("POST /login returns 500")
        self.assertEqual([item.symbol for item in result.anchors], ["routes.post_login"])
        self.assertEqual(result.anchors[0].evidence[0].kind, "route")
        result = finder.find_task_anchors("/login fails")
        self.assertEqual(len(result.anchors), 2)
        self.assertEqual(len(result.ambiguous_matches), 1)
        self.assertTrue(all(item.score == 0.5 for item in result.anchors))
        result = finder.find_task_anchors("GET /users/{user_id}")
        self.assertEqual([item.symbol for item in result.anchors], ["routes.get_user"])

    def test_route_mismatch_and_dynamic_route_do_not_guess_handler(self) -> None:
        finder = self._route_finder()
        for text in ("DELETE /login", "GET /dynamic", "/post_login", "GET /users/123"):
            with self.subTest(text=text):
                result = finder.find_task_anchors(text)
                self.assertEqual(result.anchors, [])
                self.assertEqual(result.unmatched_locations, [text])

    def test_failing_test_evidence_order_is_canonical(self) -> None:
        reports = ["tests/test_auth.py::test_login", "test_login"]
        first = self.finder.find_task_anchors("login", reports)
        second = self.finder.find_task_anchors("login", list(reversed(reports)) + reports)
        self.assertEqual(asdict(first), asdict(second))

    @staticmethod
    def _route_finder() -> TaskAnchorFinder:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "routes.py").write_text(
                '@app.get("/login")\ndef get_login():\n    pass\n\n'
                '@app.route(rule="/login", methods=["POST"])\ndef post_login():\n    pass\n\n'
                '@router.api_route(path="/users/{user_id}")\ndef get_user():\n    pass\n\n'
                '@app.get(make_route())\ndef dynamic_handler():\n    pass\n',
                encoding="utf-8",
            )
            return TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/routes", repository_revision="fixture", use_jedi=False,
            ).build(root))


if __name__ == "__main__":
    unittest.main()