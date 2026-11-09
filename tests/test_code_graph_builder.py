"""L3-1: G_code inside the builder, with a recorded Joern run instead of Docker."""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from vgar.contracts.schema import G_CODE_EDGE_TYPES, validate_graph_document
from vgar.graph import joern_runner
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.code_graph import JoernMethod, parse_export
from vgar.graph.joern_runner import JoernConfig, JoernResult
from vgar.graph.sqlite_store import SQLiteGraphStore

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "joern"
BUILD_GRAPH = Path(__file__).parent.parent / "scripts" / "build_graph.py"
SOURCE = (FIXTURE_DIR / "flow_cases.py").read_bytes().replace(b"\r\n", b"\n")
METHODS = tuple(parse_export((FIXTURE_DIR / "flow_cases.edges.tsv").read_text(encoding="utf-8")))
READY = JoernResult("ready", methods=METHODS)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "flow_cases.py").write_bytes(SOURCE)
    return root


def _builder(joern: JoernConfig | None = None) -> PythonGraphBuilder:
    return PythonGraphBuilder(repo_key="demo/flow", repository_revision="base", source_roots=(".",), joern=joern)


def _build(repo: Path, monkeypatch: pytest.MonkeyPatch, result: JoernResult = READY) -> dict[str, Any]:
    monkeypatch.setattr(joern_runner, "run_joern", lambda root, files, config: result)
    return _builder(JoernConfig()).build(repo)


def _statement(document: dict[str, Any], suffix: str) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] == "Statement" and node["id"].endswith(suffix))


def _function(document: dict[str, Any], name: str) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] in {"Function", "Method"} and node["qualified_name"].endswith(f".{name}"))


def _children(document: dict[str, Any], parent_id: str) -> list[dict[str, Any]]:
    edges = sorted((edge for edge in document["edges"] if edge["type"] == "AST_CHILD" and edge["source_id"] == parent_id),
                   key=lambda edge: edge["properties"]["ordinal"])
    assert [edge["properties"]["ordinal"] for edge in edges] == list(range(len(edges)))
    by_id = {node["id"]: node for node in document["nodes"]}
    return [by_id[edge["target_id"]] for edge in edges]


def _edges(document: dict[str, Any], edge_type: str, source_id: str | None = None) -> list[dict[str, Any]]:
    return [edge for edge in document["edges"] if edge["type"] == edge_type and source_id in (None, edge["source_id"])]


def _g_code_ids(document: dict[str, Any]) -> set[str]:
    return {node["id"] for node in document["nodes"] if node["type"] == "Statement" or node["properties"].get("extractor") == "code-graph"}


def _shifted(methods: tuple[JoernMethod, ...], by: int) -> tuple[JoernMethod, ...]:
    def line(value: int) -> int:
        return value + by if value > 0 else value

    return tuple(dataclasses.replace(method, line=line(method.line),
                                     nodes={key: (label, line(number)) for key, (label, number) in method.nodes.items()})
                 for method in methods)


def test_off_by_default_changes_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_run(*args: object) -> JoernResult:
        raise AssertionError("Joern must not run when the option is off")

    monkeypatch.setattr(joern_runner, "run_joern", must_not_run)
    document = _builder().build(repo)
    assert not any(node["type"] == "Statement" for node in document["nodes"])
    assert not any(edge["type"] in G_CODE_EDGE_TYPES for edge in document["edges"])
    assert "code_graph" not in document["statistics"]


def test_on_adds_four_edge_types_and_validates(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    validate_graph_document(document)
    assert {edge["type"] for edge in document["edges"]} >= G_CODE_EDGE_TYPES
    types = {node["type"] for node in document["nodes"]}
    assert {"Function", "Statement", "CallSite", "Identifier"} <= types
    assert any(node["type"] == "Statement" and node["properties"]["kind"] == "if" for node in document["nodes"])
    report = document["statistics"]["code_graph"]
    assert report["status"] == "ready" and report["reason"] is None and report["image"] == JoernConfig().image
    assert report["statements"] == sum(node["type"] == "Statement" for node in document["nodes"]) > 0
    assert report["identifiers"] > 0 and set(report["edges"]) == G_CODE_EDGE_TYPES
    assert report["methods_matched"] == 10 and report["methods_unmatched"] == 0 and report["raises_fixed"] == 2


def test_statement_node_fields(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    owner = _function(document, "login")
    node = _statement(document, ".login::if#1")
    assert node["id"] == f"{owner['id']}::if#1" and node["qualified_name"] == f"{owner['qualified_name']}::if#1"
    assert node["name"] == "if" and node["path"] == "flow_cases.py"
    assert node["properties"] == {"kind": "if", "owner_id": owner["id"], "condition": "user is None"}
    assert node["range"]["start_line"] == 3 and node["range"]["end_line"] == 4
    assert node["content_hash"] == PythonGraphBuilder._hash_bytes(b"if user is None:\n        return None")
    assert _statement(document, ".login::return#2")["properties"]["value"] == "session"


def test_ast_child_shape_and_ordinal(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    owner = _function(document, "login")
    assert [node["range"]["start_line"] for node in _children(document, owner["id"])] == [2, 3, 5, 6]
    assign = _statement(document, ".login::expression#1")
    assert [(node["type"], node["name"]) for node in _children(document, assign["id"])] == [
        ("Identifier", "user"), ("CallSite", "db.find"), ("Identifier", "db"), ("Identifier", "username")]
    branch = _statement(document, ".login::if#1")
    assert [(node["type"], node["name"]) for node in _children(document, branch["id"])] == [("Identifier", "user"), ("Statement", "return")]


def test_identifier_has_contains_and_ast_child(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    owner = _function(document, "login")
    identifier = next(node for node in document["nodes"] if node["id"] == f"{owner['id']}::identifier:user#1")
    assert identifier["type"] == "Identifier" and identifier["properties"] == {"extractor": "code-graph"}
    contains = [edge for edge in _edges(document, "CONTAINS", owner["id"]) if edge["target_id"] == identifier["id"]]
    assert len(contains) == 1 and contains[0]["properties"] == {"extractor": "code-graph"}
    assert identifier in _children(document, _statement(document, ".login::expression#1")["id"])


def test_identifier_records_a_declared_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.py").write_text("def f():\n    x: int = 1\n    return x\n", encoding="utf-8")
    document = _build(tmp_path, monkeypatch, JoernResult("ready", methods=tuple(parse_export("METHOD\ta.py\ta.f\t1\tf\n"))))
    identifier = next(node for node in document["nodes"] if node["id"].endswith("::identifier:x#1"))
    assert identifier["properties"] == {"extractor": "code-graph", "type": "int"}


def test_parameter_data_edge_targets_the_function(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    owner = _function(document, "login")
    edges = _edges(document, "DATA_DEPENDS_ON", _statement(document, ".login::expression#1")["id"])
    assert [(edge["target_id"], edge["properties"]) for edge in edges] == [(owner["id"], {"variables": ["username"]})]


def test_control_edge_goes_from_dependent_to_controller(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    dependent = _statement(document, ".login::return#1")
    assert [edge["target_id"] for edge in _edges(document, "CONTROL_DEPENDS_ON", dependent["id"])] == [_statement(document, ".login::if#1")["id"]]


@pytest.mark.parametrize("edge_type,confidence,resolution,tool,rule", [
    ("AST_CHILD", 1.0, "exact", "vgar-python-graph-builder", "python.code.ast_child.v1"),
    ("CFG_NEXT", 0.9, "heuristic", "joern-pysrc2cpg", "python.code.cfg_next.v1"),
    ("DATA_DEPENDS_ON", 0.8, "heuristic", "joern-pysrc2cpg", "python.code.data_depends_on.v1"),
    ("CONTROL_DEPENDS_ON", 0.9, "heuristic", "joern-pysrc2cpg", "python.code.control_depends_on.v1"),
])
def test_edge_provenance_values(repo: Path, monkeypatch: pytest.MonkeyPatch, edge_type: str, confidence: float, resolution: str, tool: str, rule: str) -> None:
    edges = _edges(_build(repo, monkeypatch), edge_type)
    assert edges and all(edge["confidence"] == confidence and edge["resolution"] == resolution for edge in edges)
    assert all(edge["provenance"]["source_tool"] == tool and edge["provenance"]["rule_id"] == rule for edge in edges)


def test_ids_survive_edit_of_other_function(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _g_code_ids(_build(repo, monkeypatch))
    (repo / "flow_cases.py").write_bytes(SOURCE.replace(b"result = value + 1", b"result = value + 2"))
    assert _g_code_ids(_build(repo, monkeypatch)) == before


def test_ids_survive_line_added_above(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _g_code_ids(_build(repo, monkeypatch))
    (repo / "flow_cases.py").write_bytes(b"import os\n" + SOURCE)
    assert _g_code_ids(_build(repo, monkeypatch, JoernResult("ready", methods=_shifted(METHODS, 1)))) == before


def test_unmatched_function_gets_no_g_code(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = JoernResult("ready", methods=tuple(method for method in METHODS if method.name != "login"))
    document = _build(repo, monkeypatch, result)
    assert document["statistics"]["code_graph"]["methods_unmatched"] == 1
    assert not any(node["type"] == "Statement" and ".login::" in node["id"] for node in document["nodes"])
    assert any(node["type"] == "Statement" and ".checked::" in node["id"] for node in document["nodes"])


def test_two_joern_methods_with_one_key_are_not_matched(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    login = next(method for method in METHODS if method.name == "login")
    document = _build(repo, monkeypatch, JoernResult("ready", methods=(*METHODS, login)))
    assert document["statistics"]["code_graph"]["methods_unmatched"] == 1
    assert not any(node["type"] == "Statement" and ".login::" in node["id"] for node in document["nodes"])


def test_property_getter_and_setter_both_get_statements(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    statements = [node["id"] for node in document["nodes"] if node["type"] == "Statement" and ".size" in node["id"]]
    assert len(statements) == 2 and any(".size.setter::" in item for item in statements)


def test_test_code_gets_no_g_code(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    seen: list[list[Path]] = []

    def run(root: Path, files: list[Path], config: JoernConfig) -> JoernResult:
        seen.append(files)
        return READY

    monkeypatch.setattr(joern_runner, "run_joern", run)
    document = _builder(JoernConfig()).build(repo)
    assert [path.name for path in seen[0]] == ["flow_cases.py"]
    assert not any(node["type"] == "Statement" and node["path"].startswith("tests/") for node in document["nodes"])
    assert document["statistics"]["code_graph"]["methods_unmatched"] == 0


@pytest.mark.parametrize("status", ["unavailable", "failed", "timeout"])
def test_joern_failure_still_builds(repo: Path, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    document = _build(repo, monkeypatch, JoernResult(status, "because"))
    validate_graph_document(document)
    assert not any(node["type"] == "Statement" for node in document["nodes"])
    report = document["statistics"]["code_graph"]
    assert report["status"] == status and report["reason"] == "because" and report["statements"] == 0


def test_graph_version_differs_on_and_off(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    off = _builder().build(repo)["graph_version"]
    ready = _build(repo, monkeypatch)["graph_version"]
    failed = _build(repo, monkeypatch, JoernResult("failed", "x"))["graph_version"]
    assert len({off, ready, failed}) == 3


def test_get_subgraph_excludes_g_code(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.initialize()
    store.ingest(document)
    nodes, edges = store.get_subgraph(_function(document, "login")["id"], depth=3, limit=1000)
    assert edges and not any(edge.edge_type in G_CODE_EDGE_TYPES for edge in edges)
    assert not any(node.node_type == "Statement" or node.properties.get("extractor") == "code-graph" for node in nodes)
    assert any(node.node_type == "CallSite" for node in nodes)


def _build_graph_module() -> Any:
    spec = importlib.util.spec_from_file_location("build_graph_script", BUILD_GRAPH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cli_arguments(repo: Path, output: Path, *extra: str) -> list[str]:
    return ["build_graph.py", str(repo), str(output), "--repo-key", "demo/flow", "--revision", "base", *extra]


def test_cli_warns_when_joern_is_not_ready(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(joern_runner, "run_joern", lambda root, files, config: JoernResult("failed", "boom"))
    monkeypatch.setattr(sys, "argv", _cli_arguments(repo, tmp_path / "graph.json", "--joern"))
    _build_graph_module().main()
    assert "WARNING: Joern failed: boom" in capsys.readouterr().err
    assert (tmp_path / "graph.json").exists()


def test_cli_passes_image_and_timeout(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[JoernConfig] = []

    def run(root: Path, files: list[Path], config: JoernConfig) -> JoernResult:
        seen.append(config)
        return READY

    monkeypatch.setattr(joern_runner, "run_joern", run)
    monkeypatch.setattr(sys, "argv", _cli_arguments(repo, tmp_path / "graph.json", "--joern", "--joern-image", "joern:test", "--joern-timeout", "12.5"))
    _build_graph_module().main()
    assert seen == [JoernConfig(image="joern:test", timeout_seconds=12.5)]


def test_cli_does_not_run_joern_without_the_flag(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_run(*args: object) -> JoernResult:
        raise AssertionError("Joern must not run without --joern")

    monkeypatch.setattr(joern_runner, "run_joern", must_not_run)
    monkeypatch.setattr(sys, "argv", _cli_arguments(repo, tmp_path / "graph.json"))
    _build_graph_module().main()
    assert (tmp_path / "graph.json").exists()
