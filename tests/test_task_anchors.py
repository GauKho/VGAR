from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.grounding import TaskAnchorFinder, issue_symbol_text, issue_topic_text


class TaskAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = TaskAnchorFinder(PythonGraphBuilder(
            repo_key="demo/anchors", repository_revision="fixture",
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

    def test_module_suffix_symbol_and_unknown_receiver(self) -> None:
        result = self.finder.find_task_anchors("service.login fails")
        self.assertEqual([item.symbol for item in result.anchors], ["auth.service.login"])
        self.assertEqual(result.anchors[0].score, 0.8)
        self.assertEqual(self.finder.find_task_anchors("unknown.login").anchors, [])

    def test_class_method_suffix_preserves_ambiguity_and_exact_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("first", "second"):
                (root / f"{name}.py").write_text(
                    "class Header:\n    def fromstring(self):\n        pass\n",
                    encoding="utf-8",
                )
            finder = TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/suffix", repository_revision="fixture",
            ).build(root))
        result = finder.find_task_anchors("Header.fromstring fails")
        self.assertEqual([item.symbol for item in result.anchors],
                         ["first.Header.fromstring", "second.Header.fromstring"])
        self.assertEqual(len(result.ambiguous_matches), 1)
        self.assertTrue(all(item.score == 0.5 for item in result.anchors))
        result = finder.find_task_anchors("first.Header.fromstring fails")
        self.assertEqual([item.symbol for item in result.anchors], ["first.Header.fromstring"])
        self.assertEqual(result.ambiguous_matches, [])

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
                repo_key="demo/ranges", repository_revision="fixture",
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
                repo_key="demo/spaces", repository_revision="fixture",
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

    def test_common_prose_does_not_dilute_an_explicit_symbol(self) -> None:
        finder = self._prose_finder()
        result = finder.find_task_anchors("Please read and search; use the default. `login` fails.")
        self.assertEqual([item.symbol for item in result.anchors], ["app.login"])
        self.assertEqual(result.anchors[0].score, 0.75)

    def test_source_link_keeps_file_evidence_without_historical_line_guess(self) -> None:
        result = self.finder.find_task_anchors(
            "https://github.com/demo/repo/blob/stable/1.x/src/auth/service.py#L999")
        self.assertEqual([item.symbol for item in result.anchors], ["src/auth/service.py"])
        self.assertEqual(result.anchors[0].evidence[0].kind, "source_link")
        self.assertEqual(self.finder.find_task_anchors(
            "<!-- https://github.com/demo/repo/blob/main/src/auth/service.py -->").anchors, [])
        self.assertEqual(self.finder.find_task_anchors(
            "https://example.com/src/auth/service.py").anchors, [])

    def test_unknown_receiver_call_is_a_weak_hint_with_all_member_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class First:\n    def process(self): pass\n"
                "class Second:\n    def process(self): pass\n", encoding="utf-8")
            finder = TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/member", repository_revision="fixture").build(root))
        result = finder.find_task_anchors("obj.process() fails")
        self.assertEqual([a.symbol for a in result.anchors], ["app.First.process", "app.Second.process"])
        self.assertEqual(len(result.ambiguous_matches), 1)
        self.assertTrue(all(a.score == 0.45 and a.evidence[0].kind == "receiver_member"
                            for a in result.anchors))
        self.assertEqual(finder.find_task_anchors("obj.process fails").anchors, [])
        exact = finder.find_task_anchors("First.process() fails")
        self.assertEqual([a.symbol for a in exact.anchors], ["app.First.process"])
        self.assertEqual(exact.anchors[0].score, 0.8)

    def test_common_names_remain_valid_in_code_and_narrative_fallback(self) -> None:
        finder = self._prose_finder()
        for text in ("`read` fails", "``read`` fails", "read() fails",
                     "```python\nread()\n```", "~~~python\nread()\n~~~"):
            with self.subTest(text=text):
                result = finder.find_task_anchors(text)
                self.assertEqual([item.symbol for item in result.anchors], ["app.read"])
                self.assertEqual(result.anchors[0].score, 0.75)
        fallback = finder.find_task_anchors("read fails")
        self.assertEqual([item.symbol for item in fallback.anchors], ["app.read"])
        self.assertLess(fallback.anchors[0].score, 0.4)

    def test_comments_and_links_do_not_supply_issue_symbols(self) -> None:
        finder = self._prose_finder()
        result = finder.find_task_anchors(
            "<!-- app.search read() --> https://example.com/app.default `login` fails",
        )
        self.assertEqual([item.symbol for item in result.anchors], ["app.login"])

    def test_explicit_ambiguous_symbol_retains_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("first", "second"):
                (root / f"{name}.py").write_text("def search(): pass\n", encoding="utf-8")
            finder = TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/prose-ambiguity", repository_revision="fixture",
            ).build(root))
        result = finder.find_task_anchors("`search` fails")
        self.assertEqual(len(result.anchors), 2)
        self.assertEqual(len(result.ambiguous_matches), 1)
        self.assertTrue(all(item.score == 0.5 for item in result.anchors))
        result = finder.find_task_anchors("", ["search"])
        self.assertEqual(len(result.anchors), 2)
        self.assertEqual(len(result.ambiguous_matches), 1)

    def test_plain_ambiguous_mentions_have_lower_priority_than_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("first", "second"):
                (root / f"{name}.py").write_text("def process(): pass\n", encoding="utf-8")
            finder = TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/prose-priority", repository_revision="fixture",
            ).build(root))
        plain = finder.find_task_anchors("process fails")
        explicit = finder.find_task_anchors("`process` fails")
        self.assertEqual(len(plain.anchors), 2)
        self.assertLess(plain.anchors[0].score, explicit.anchors[0].score)

    @staticmethod
    def _prose_finder() -> TaskAnchorFinder:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def read(): pass\ndef search(): pass\ndef default(): pass\ndef login(): pass\n",
                encoding="utf-8",
            )
            return TaskAnchorFinder(PythonGraphBuilder(
                repo_key="demo/prose", repository_revision="fixture",
            ).build(root))

    def test_reproduction_variables_are_not_repository_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def x(): pass\ndef y(): pass\ndef mode(): pass\ndef process(): pass\n", encoding="utf-8")
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key="demo/locals", repository_revision="fixture").build(root))
        result = finder.find_task_anchors("```python\nx = 1\ny = x\nfor mode in ('fast',):\n    obj.process(x, y)\n```")
        self.assertEqual([a.symbol for a in result.anchors], ["app.process"])
        # Explicit repository function calls and identifiers outside the snippet remain usable.
        self.assertEqual([a.symbol for a in finder.find_task_anchors("`x()` fails").anchors], ["app.x"])
        self.assertEqual([a.symbol for a in finder.find_task_anchors("```python\nx = 1\n```\napp.x fails").anchors], ["app.x"])

    def test_import_alias_resolves_module_and_external_import_does_not_guess_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "api.py").write_text("def process(): pass\n", encoding="utf-8")
            (root / "other.py").write_text("def process(): pass\n", encoding="utf-8")
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key="demo/imports", repository_revision="fixture").build(root))
        for snippet in ("import api as a\na.process()", "from api import process as p\np()"):
            result = finder.find_task_anchors("```python\n" + snippet + "\n```")
            self.assertEqual([a.symbol for a in result.anchors], ["api.process"])
            self.assertEqual(result.ambiguous_matches, [])
        result = finder.find_task_anchors("```python\nimport external as a\na.process()\n```")
        self.assertEqual(result.anchors, [])

    def test_invalid_reproduction_keeps_lexical_fallback(self) -> None:
        result = self._prose_finder().find_task_anchors("```python\nif ???\nobj.login()\n```")
        self.assertEqual([a.symbol for a in result.anchors], ["app.login"])

    def test_topic_excludes_reproduction_syntax_and_preserves_literal_names(self) -> None:
        issue = 'Timeout handling\n```python\nclass Demo:\n    def method(self):\n        return None\n```'
        visible = issue_symbol_text(issue)
        self.assertEqual(len(visible), len(issue))
        self.assertNotIn('Demo', visible)
        self.assertNotIn('method', visible)
        self.assertIn('None', visible)
        self.assertEqual(issue_topic_text(issue), 'Timeout handling')
        self.assertEqual(issue_topic_text('```python\nclass Demo: pass\n```\n`fetch()` fails'), '`fetch()` fails')

    def test_narrative_help_does_not_override_explicit_code_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app.py').write_text('def help(): pass\ndef handle(): pass\n', encoding='utf-8')
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key='demo/help-prose', repository_revision='fixture').build(root))
        self.assertEqual([a.symbol for a in finder.find_task_anchors('`handle()` does not help').anchors], ['app.handle'])
        for issue in ('help fails', '`help()` fails'):
            self.assertEqual([a.symbol for a in finder.find_task_anchors(issue).anchors], ['app.help'])

    def test_reproduction_definitions_and_arguments_do_not_seed_repository_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('class Example:\n    def __init__(self): pass\ndef value(): pass\ndef external(): pass\n', encoding='utf-8')
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key='demo/definitions', repository_revision='fixture').build(root))
        issue = '```python\nclass Example:\n    def __init__(self, value):\n        external()\n        self.value = value\n```'
        result = finder.find_task_anchors(issue)
        self.assertEqual([a.symbol for a in result.anchors], ['app.external'])
        result = finder.find_task_anchors(issue + '\n`Example.__init__()` fails')
        self.assertIn('app.Example.__init__', [a.symbol for a in result.anchors])

    def test_environment_versions_and_language_prose_do_not_seed_setup_classes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app.py').write_text('class Python: pass\nclass Widget: pass\ndef repair_target(): pass\n', encoding='utf-8')
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key='demo/metadata', repository_revision='fixture').build(root))
            issue = 'repair_target fails\n**Widget version**\r\r\n * Widget version: 1.0\r\r\n * Python version: 3.11\nPython was installed locally.'
            self.assertEqual([a.symbol for a in finder.find_task_anchors(issue).anchors], ['app.repair_target'])
            self.assertEqual([a.symbol for a in finder.find_task_anchors('`Python()` fails').anchors], ['app.Python'])

    def test_version_report_section_is_not_bug_evidence_and_preserves_next_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app.py').write_text('def repair_target(): pass\ndef show_versions(): pass\ndef another_failure(): pass\n', encoding='utf-8')
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key='demo/report-sections', repository_revision='fixture').build(root))
            for heading, report in (
                ('#### Output of ``pkg.show_versions()``', '<details>\n# Paste show_versions() here\nshow_versions()\n</details>'),
                ('#### Installed versions', 'show_versions: 1.0'),
                ('#### Output of `tool --version`', 'show_versions: 1.0'),
                ('#### tool --version output', 'show_versions: 1.0'),
            ):
                issue = f'`repair_target()` fails\n{heading}\n{report}\n#### Actual failure\n`another_failure()` fails\n'
                with self.subTest(heading=heading):
                    self.assertEqual({a.symbol for a in finder.find_task_anchors(issue).anchors},
                                     {'app.repair_target', 'app.another_failure'})
                    normalized = issue_symbol_text(issue)
                    self.assertNotIn('show_versions', normalized)
                    self.assertEqual(len(normalized), len(issue))
                    self.assertEqual(normalized.index('another_failure'), issue.index('another_failure'))

    def test_diagnostic_function_as_the_reported_bug_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app.py').write_text('def show_versions(): pass\n', encoding='utf-8')
            finder = TaskAnchorFinder(PythonGraphBuilder(repo_key='demo/diagnostic-bug', repository_revision='fixture').build(root))
            for issue in ('`show_versions()` returns the wrong output',
                          '#### Output of `show_versions()` is wrong\n`show_versions()` fails',
                          '```python\n# Output of show_versions()\nshow_versions()\n```'):
                with self.subTest(issue=issue):
                    self.assertEqual([a.symbol for a in finder.find_task_anchors(issue).anchors], ['app.show_versions'])

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
                repo_key="demo/routes", repository_revision="fixture",
            ).build(root))


if __name__ == "__main__":
    unittest.main()
