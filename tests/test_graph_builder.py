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


if __name__ == "__main__":
    unittest.main()
