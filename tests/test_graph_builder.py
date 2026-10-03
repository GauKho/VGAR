from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.contracts.schema import validate_graph_document


SAMPLE_REPOSITORY = Path(__file__).parent / "fixtures" / "sample_repo"
JEDI_REPOSITORY = Path(__file__).parent / "fixtures" / "jedi_repo"


class PythonGraphBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = PythonGraphBuilder(
            repo_key="demo/vgar-fixture",
            repository_revision="fixture-revision",
        ).build(SAMPLE_REPOSITORY)

    def test_output_satisfies_graph_schema(self) -> None:
        validate_graph_document(self.document)
        self.assertNotIn("schema_version", self.document)

    def test_extracts_repository_files_modules_and_functions(self) -> None:
        node_types = [node["type"] for node in self.document["nodes"]]

        self.assertEqual(node_types.count("Repository"), 1)
        self.assertEqual(node_types.count("File"), 8)
        self.assertEqual(node_types.count("Module"), 8)
        self.assertEqual(node_types.count("Function"), 3)
        self.assertEqual(node_types.count("Class"), 4)
        self.assertEqual(node_types.count("Method"), 3)
        self.assertEqual(node_types.count("Test"), 1)
        self.assertEqual(node_types.count("CallSite"), 7)

    def test_resolves_import_and_direct_call(self) -> None:
        edge_types = [edge["type"] for edge in self.document["edges"]]

        self.assertEqual(edge_types.count("IMPORTS"), 5)
        self.assertEqual(edge_types.count("CALLS"), 5)
        self.assertEqual(edge_types.count("INHERITS"), 2)
        self.assertEqual(edge_types.count("TESTS"), 1)

        call_edge = next(
            edge
            for edge in self.document["edges"]
            if edge["type"] == "CALLS"
            and self._node(edge["target_id"])["qualified_name"]
            == "auth.service.login"
        )
        target = self._node(call_edge["target_id"])
        self.assertEqual(target["qualified_name"], "auth.service.login")

    def test_extracts_method_and_resolves_self_call(self) -> None:
        method_names = {
            node["qualified_name"]
            for node in self.document["nodes"]
            if node["type"] == "Method"
        }
        self.assertEqual(
            method_names,
            {
                "relative_pkg.service.RelativeService.create",
                "users.service.UserService.normalize",
                "users.service.UserService.find_user",
            },
        )

        self_call = next(
            edge
            for edge in self.document["edges"]
            if edge["type"] == "CALLS"
            and edge["properties"]["binding_kind"] == "self_method"
        )
        self.assertEqual(
            self._node(self_call["target_id"])["qualified_name"],
            "users.service.UserService.normalize",
        )

    def test_statistics_report_unresolved_calls(self) -> None:
        statistics = self.document["statistics"]

        self.assertEqual(statistics["callsite_count"], 7)
        self.assertEqual(statistics["unresolved_call_count"], 2)
        self.assertEqual(statistics["partial_file_count"], 0)
        self.assertGreaterEqual(statistics["build_time_ms"], 0)

    def test_relative_import_and_constructor_resolution(self) -> None:
        relative_import = next(
            edge
            for edge in self.document["edges"]
            if edge["type"] == "IMPORTS"
            and self._node(edge["target_id"])["qualified_name"]
            == "relative_pkg.base"
        )
        self.assertEqual(
            self._node(relative_import["source_id"])["properties"]["resolution_status"],
            "resolved",
        )

        constructors = [
            edge
            for edge in self.document["edges"]
            if edge["type"] == "CALLS"
            and edge["properties"]["binding_kind"] == "constructor"
        ]
        constructor_targets = {
            self._node(edge["target_id"])["qualified_name"]
            for edge in constructors
        }
        self.assertEqual(
            constructor_targets,
            {
                "relative_pkg.service.RelativeService",
                "users.service.UserService",
            },
        )

    def test_unique_repository_symbol_is_low_confidence_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text(
                "def unique_helper():\n    return 1\n",
                encoding="utf-8",
            )
            (root / "src" / "b.py").write_text(
                "from wrong.module import unique_helper\n\n"
                "def caller():\n    return unique_helper()\n",
                encoding="utf-8",
            )
            document = PythonGraphBuilder(
                repo_key="demo/heuristic",
                repository_revision="fixture-revision",
            ).build(root)

        call_edge = next(
            edge for edge in document["edges"] if edge["type"] == "CALLS"
        )
        self.assertEqual(call_edge["properties"]["binding_kind"], "heuristic")
        self.assertEqual(call_edge["confidence"], 0.60)

    def test_jedi_resolves_typed_receiver_method(self) -> None:
        document = PythonGraphBuilder(
            repo_key="demo/jedi",
            repository_revision="fixture-revision",
        ).build(JEDI_REPOSITORY)

        jedi_edge = next(
            edge
            for edge in document["edges"]
            if edge["type"] == "CALLS"
            and edge["properties"]["binding_kind"] == "jedi"
        )
        self.assertEqual(
            next(
                node["qualified_name"]
                for node in document["nodes"]
                if node["id"] == jedi_edge["target_id"]
            ),
            "service.Worker.execute",
        )
        self.assertEqual(jedi_edge["confidence"], 0.85)

    def test_jedi_can_be_disabled(self) -> None:
        without_jedi = PythonGraphBuilder(
            repo_key="demo/vgar-fixture",
            repository_revision="fixture-revision",
            use_jedi=False,
        ).build(SAMPLE_REPOSITORY)

        self.assertFalse(
            any(
                edge["properties"].get("binding_kind", "").startswith("jedi")
                for edge in without_jedi["edges"]
            )
        )

    def test_graph_version_is_deterministic(self) -> None:
        second_document = PythonGraphBuilder(
            repo_key="demo/vgar-fixture",
            repository_revision="fixture-revision",
        ).build(SAMPLE_REPOSITORY)

        self.assertEqual(
            self.document["graph_version"],
            second_document["graph_version"],
        )

    def _node(self, node_id: str) -> dict:
        return next(
            node for node in self.document["nodes"] if node["id"] == node_id
        )


class GraphBuilderRegressionTests(unittest.TestCase):
    def _build(self, source: str, *, use_jedi: bool = False) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(source, encoding="utf-8")
            return PythonGraphBuilder(
                repo_key="demo/regression",
                repository_revision="regression",
                use_jedi=use_jedi,
            ).build(root)

    def _targets(self, document: dict) -> list[str]:
        nodes = {node["id"]: node for node in document["nodes"]}
        return [
            nodes[edge["target_id"]]["qualified_name"]
            for edge in document["edges"] if edge["type"] == "CALLS"
        ]

    def test_repeated_test_calls_keep_callsites_and_one_tests_relation(self) -> None:
        document = self._build(
            "def helper():\n    return 1\n\n"
            "def test_helper():\n    helper()\n    helper()\n"
        )
        self.assertEqual(self._targets(document), ["app.helper", "app.helper"])
        self.assertEqual(sum(edge["type"] == "TESTS" for edge in document["edges"]), 1)
        self.assertEqual(len({edge["id"] for edge in document["edges"]}), len(document["edges"]))

    def test_test_can_contain_nested_function_and_class(self) -> None:
        document = self._build(
            "def test_outer():\n"
            "    def test_helper():\n        return 1\n"
            "    class Worker:\n        pass\n"
            "    test_helper()\n    Worker()\n"
        )
        self.assertEqual(set(self._targets(document)), {"app.test_outer.test_helper", "app.test_outer.Worker"})
        self.assertEqual(sum(node["type"] == "Test" for node in document["nodes"]), 1)

    def test_nested_function_shadows_module_function(self) -> None:
        for use_jedi in (False, True):
            with self.subTest(use_jedi=use_jedi):
                document = self._build(
                    "def helper():\n    return 1\n\n"
                    "def caller():\n"
                    "    def helper():\n        return 2\n"
                    "    return helper()\n", use_jedi=use_jedi,
                )
                self.assertEqual(self._targets(document), ["app.caller.helper"])

    def test_parameter_and_assignment_shadow_module_function(self) -> None:
        for use_jedi in (False, True):
            for caller in (
                "def caller(helper):\n    return helper()\n",
                "def caller():\n    helper = lambda: 2\n    return helper()\n",
            ):
                with self.subTest(use_jedi=use_jedi, caller=caller):
                    document = self._build(
                        "def helper():\n    return 1\n\n" + caller, use_jedi=use_jedi,
                    )
                    self.assertEqual(self._targets(document), [])
                    self.assertEqual(document["statistics"]["unresolved_call_count"], 1)

    def test_closure_resolves_enclosing_function_binding(self) -> None:
        document = self._build(
            "def helper():\n    return 1\n\n"
            "def outer():\n"
            "    def helper():\n        return 2\n"
            "    def inner():\n        return helper()\n"
            "    return inner()\n"
        )
        self.assertEqual(set(self._targets(document)), {"app.outer.helper", "app.outer.inner"})

    def test_method_does_not_use_class_namespace_for_bare_call(self) -> None:
        document = self._build(
            "def helper():\n    return 1\n\n"
            "class Worker:\n"
            "    def helper(self):\n        return 2\n"
            "    def caller(self):\n        return helper()\n"
        )
        self.assertEqual(self._targets(document), ["app.helper"])

    def test_nested_class_does_not_overwrite_module_definition(self) -> None:
        document = self._build(
            "class Worker:\n    pass\n\n"
            "def outer():\n    class Worker:\n        pass\n\n"
            "def caller():\n    return Worker()\n"
        )
        self.assertEqual(self._targets(document), ["app.Worker"])

    def test_nested_symbol_is_not_repository_global_fallback(self) -> None:
        document = self._build(
            "def outer():\n    def helper():\n        return 1\n\n"
            "def caller():\n    return helper()\n"
        )
        self.assertEqual(self._targets(document), [])

    def test_local_import_shadows_module_symbol(self) -> None:
        for use_jedi in (False, True):
            with self.subTest(use_jedi=use_jedi), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "app.py").write_text(
                    "def helper():\n    return 1\n\n"
                    "def caller():\n    from other import helper as helper\n    return helper()\n",
                    encoding="utf-8",
                )
                (root / "other.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
                document = PythonGraphBuilder(
                    repo_key="demo/local-import", repository_revision="fixture", use_jedi=use_jedi,
                ).build(root)
                self.assertEqual(self._targets(document), ["other.helper"] if use_jedi else [])


if __name__ == "__main__":
    unittest.main()