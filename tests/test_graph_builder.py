from __future__ import annotations

import unittest
from unittest import mock
import tempfile
from pathlib import Path

from vgar.graph.builder import GRAPH_VERSION_RESOLVER_LABEL, RESOLVER_PROFILE, PythonGraphBuilder
from vgar.contracts.schema import validate_graph_document


SAMPLE_REPOSITORY = Path(__file__).parent / "fixtures" / "sample_repo"
TYPED_REPOSITORY = Path(__file__).parent / "fixtures" / "typed_repo"


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

    @staticmethod
    def _build_files(files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return PythonGraphBuilder(
                repo_key="demo/heuristic",
                repository_revision="fixture-revision",
            ).build(root)

    @staticmethod
    def _call_targets(document: dict) -> set[str]:
        names = {node["id"]: node["qualified_name"] for node in document["nodes"]}
        return {names[edge["target_id"]] for edge in document["edges"] if edge["type"] == "CALLS"}

    def test_explicit_external_import_not_bound_to_internal_unique_name(self) -> None:
        # G1 (B10): an explicit import from a module outside the repo must not
        # be rebound to a same-named repository function.
        document = self._build_files({
            "src/a.py": "def unique_helper():\n    return 1\n",
            "src/b.py": "from wrong.module import unique_helper\n\n"
                        "def caller():\n    return unique_helper()\n",
        })

        self.assertNotIn("a.unique_helper", self._call_targets(document))
        self.assertEqual(document["statistics"]["unresolved_call_count"], 1)

    def test_unique_name_fallback_without_import_still_resolves(self) -> None:
        # G2: with no import of the name, the unique-name fallback is unchanged.
        document = self._build_files({
            "src/a.py": "def unique_helper():\n    return 1\n",
            "src/b.py": "def caller():\n    return unique_helper()\n",
        })

        call_edge = next(edge for edge in document["edges"] if edge["type"] == "CALLS")
        self.assertEqual(self._call_targets(document), {"a.unique_helper"})
        self.assertEqual(call_edge["properties"]["binding_kind"], "heuristic")
        self.assertEqual(call_edge["confidence"], 0.60)

    def test_reexport_from_repository_package_still_resolves(self) -> None:
        # G2b: `from pkg import helper` where pkg is in the repo but only
        # re-exports helper keeps resolving to the real definition.
        document = self._build_files({
            "src/pkg/__init__.py": "from .impl import helper\n",
            "src/pkg/impl.py": "def helper():\n    return 1\n",
            "src/c.py": "from pkg import helper\n\n"
                        "def caller():\n    return helper()\n",
        })

        self.assertIn("pkg.impl.helper", self._call_targets(document))

    def test_relative_import_inside_repository_package_still_resolves(self) -> None:
        # G2c: a relative import inside a repository package keeps resolving.
        document = self._build_files({
            "src/pkg/__init__.py": "",
            "src/pkg/impl.py": "def helper():\n    return 1\n",
            "src/pkg/user.py": "from .impl import helper\n\n"
                               "def caller():\n    return helper()\n",
        })

        self.assertIn("pkg.impl.helper", self._call_targets(document))

    def test_b10_keeps_graph_version_and_records_resolver_profile(self) -> None:
        # G7 under E5 option (iii): the W10 graph_version (printed in every W10 prompt) must not change with the
        # resolver; the resolver change is carried by statistics.resolver.profile and checked at handoff.
        # Since the 08/11 schema profiles, that frozen identity is statistics.legacy_graph_version; the full
        # graph_version does depend on the resolver profile.
        # Checkout-independent (no pinned hash: CRLF/LF checkouts hash different source bytes).
        self.assertEqual(GRAPH_VERSION_RESOLVER_LABEL, "tree-sitter+python-static-v3-method-aliases")
        with mock.patch("vgar.graph.builder.RESOLVER_PROFILE", "another-resolver-profile"):
            other = PythonGraphBuilder(repo_key="demo/vgar-fixture",
                                       repository_revision="fixture-revision").build(SAMPLE_REPOSITORY)
        self.assertEqual(other["statistics"]["legacy_graph_version"], self.document["statistics"]["legacy_graph_version"])
        self.assertNotEqual(other["graph_version"], self.document["graph_version"])
        self.assertEqual(other["statistics"]["resolver"]["profile"], "another-resolver-profile")
        self.assertEqual(self.document["statistics"]["resolver"]["profile"], RESOLVER_PROFILE)
        self.assertIn("-v4-", RESOLVER_PROFILE)

    def test_build_uses_overridable_hooks(self) -> None:
        # Incremental Task 2: validation and alias AST parsing go through methods a subclass can override.
        calls: dict[str, list] = {"validate": [], "parse": []}

        class Recording(PythonGraphBuilder):
            def _validate(self, document):
                calls["validate"].append(document["graph_version"])
                super()._validate(document)

            def _parse_python_ast(self, root, path):
                calls["parse"].append(path)
                return super()._parse_python_ast(root, path)

        document = Recording(repo_key="demo/static", repository_revision="fixture-revision").build(TYPED_REPOSITORY)

        class_paths = {node["path"] for node in document["nodes"] if node["type"] in {"Class", "Method"}}
        self.assertEqual(calls["validate"], [document["graph_version"]])
        self.assertEqual(set(calls["parse"]), class_paths)

    def test_static_resolver_resolves_typed_receiver_method(self) -> None:
        document = PythonGraphBuilder(
            repo_key="demo/static",
            repository_revision="fixture-revision",
        ).build(TYPED_REPOSITORY)

        typed_edge = next(
            edge
            for edge in document["edges"]
            if edge["type"] == "CALLS"
            and edge["properties"]["binding_kind"] == "typed_parameter"
        )
        self.assertEqual(
            next(
                node["qualified_name"]
                for node in document["nodes"]
                if node["id"] == typed_edge["target_id"]
            ),
            "service.Worker.execute",
        )
        self.assertEqual(typed_edge["confidence"], 0.85)

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
    def _build(self, source: str, *, path: str = "app.py") -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
            return PythonGraphBuilder(
                repo_key="demo/regression",
                repository_revision="regression",
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
            "def test_helper():\n    helper()\n    helper()\n",
            path="tests/test_app.py",
        )
        self.assertEqual(self._targets(document), ["tests.test_app.helper", "tests.test_app.helper"])
        self.assertEqual(sum(edge["type"] == "TESTS" for edge in document["edges"]), 1)
        self.assertEqual(len({edge["id"] for edge in document["edges"]}), len(document["edges"]))

    def test_test_can_contain_nested_function_and_class(self) -> None:
        document = self._build(
            "def test_outer():\n"
            "    def test_helper():\n        return 1\n"
            "    class Worker:\n        pass\n"
            "    test_helper()\n    Worker()\n",
            path="tests/test_app.py",
        )
        self.assertEqual(set(self._targets(document)), {"tests.test_app.test_outer.test_helper", "tests.test_app.test_outer.Worker"})
        self.assertEqual(sum(node["type"] == "Test" for node in document["nodes"]), 1)

    def test_nested_function_shadows_module_function(self) -> None:
        document = self._build(
            "def helper():\n    return 1\n\n"
            "def caller():\n"
            "    def helper():\n        return 2\n"
            "    return helper()\n",
        )
        self.assertEqual(self._targets(document), ["app.caller.helper"])

    def test_parameter_and_assignment_shadow_module_function(self) -> None:
        for caller in (
            "def caller(helper):\n    return helper()\n",
            "def caller():\n    helper = lambda: 2\n    return helper()\n",
        ):
            with self.subTest(caller=caller):
                document = self._build("def helper():\n    return 1\n\n" + caller)
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def helper():\n    return 1\n\n"
                "def caller():\n    from other import helper as helper\n    return helper()\n",
                encoding="utf-8",
            )
            (root / "other.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
            document = PythonGraphBuilder(repo_key="demo/local-import", repository_revision="fixture").build(root)
            # Function-local imports are deliberately unresolved by this profile.
            self.assertEqual(self._targets(document), [])


if __name__ == "__main__":
    unittest.main()
