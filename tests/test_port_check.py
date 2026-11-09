"""IM-1: lost-port check. Spec: docs/superpowers/specs/2026-11-09-tv2-im-1-impact-design.md"""
from __future__ import annotations

import ast
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from test_arch_lift import BOUNDARY_PORTS
from test_impact_arch import (
    _build_repo,
    _case,
    _diff,
    _edit,
    _features,
    _policy,
    _strip_arch,
)

from vgar.contracts.impact import ImpactReport, LostPort
from vgar.graph.arch_lift import read_dunder_all, select_ports
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.impact import _snapshot, analyze_patch_impact
from vgar.graph.port_check import check_lost_ports
from vgar.graph.tsg_extractor import TsgConfig
from vgar.mcp.servers import graph_server

CASES = Path(__file__).parent / "fixtures" / "vgar-arch-cases"


def _build(root: Path, **kwargs: Any) -> dict[str, Any]:
    return PythonGraphBuilder(repo_key="t/arch", repository_revision="rev", **kwargs).build(root)


def _sources(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.py")}


def test_select_ports_matches_lifted_ports() -> None:
    document = _build(CASES / "boundary_cases")
    exports = {path: read_dunder_all(data) for path, data in _sources(CASES / "boundary_cases").items() if b"__all__" in data}
    selected = select_ports(document["nodes"], document["edges"], exports)
    owned = {path for n in document["nodes"] if n["type"] == "Component" for path in n["properties"]["files"]}
    assert {node["qualified_name"] for node, _ in selected if node["path"] in owned} == BOUNDARY_PORTS  # written by hand
    names = {node["qualified_name"]: export for node, export in selected}
    assert names["services.pricing._internal"] == "dunder_all" and names["services.pricing.discount"] == "public_name"
    assert "services.pricing._secret" not in names and "services.pricing._Hidden.method" not in names


def test_select_ports_tolerates_missing_ancestor() -> None:
    nodes = [{"id": "f", "type": "Function", "name": "f", "path": "a.py"}]
    edges = [{"type": "CONTAINS", "source_id": "gone", "target_id": "f"}]
    assert [(n["id"], e) for n, e in select_ports(nodes, edges, {})] == [("f", "public_name")]


@pytest.mark.parametrize("relative", ["storage/sql.py", "storage/__init__.py"])
def test_extract_source_matches_extract_file(relative: str) -> None:
    root = CASES / "boundary_cases"
    from_file, from_bytes = (PythonGraphBuilder(repo_key="t/arch", repository_revision="rev") for _ in range(2))
    from_file.graph_version = from_bytes.graph_version = "v"
    from_file._extract_file(root, root / relative, "repo")
    from_bytes.extract_source(relative, (root / relative).read_bytes(), "repo")
    assert from_bytes.nodes == from_file.nodes and from_bytes.edges == from_file.edges
    assert {n["type"] for n in from_bytes.nodes} >= {"File", "Module"}


@pytest.mark.skipif(TsgConfig.from_env() is None, reason="needs VGAR_TSG_EXECUTABLE and VGAR_TSG_TREE_SITTER_DIR")
def test_route_graph_passes_source_snapshot() -> None:
    root = CASES / "web_app"
    document = _build(root, tsg=TsgConfig.from_env())
    assert any(n["type"] == "Route" for n in document["nodes"])
    _snapshot(document, root)  # checks every node with a path and range against its bytes; must not raise


# ---- lost ports (spec 5) --------------------------------------------------------------------------------------------

SQL = "storage/sql.py"
PRICING = "services/pricing.py"


def _text(root: Path, path: str) -> str:
    return (root / path).read_bytes().decode("utf-8")


def _without(text: str, name: str) -> str:
    """Source without the top-level function or class `name`."""
    node = next(n for n in ast.parse(text).body if getattr(n, "name", None) == name)
    lines = text.splitlines(keepends=True)
    del lines[node.lineno - 1:node.end_lineno]
    return "".join(lines)


def _patch(root: Path, doc: dict[str, Any], path: str, new_text: str) -> ImpactReport:
    return analyze_patch_impact(_diff(path, _text(root, path), new_text), doc, root, patch_policy=_policy(doc))


def _lost(report: ImpactReport) -> dict[str, LostPort]:
    return {port.qualified_name: port for port in report.port_check.lost}


def test_deleted_function_is_lost(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _patch(root, doc, SQL, _without(_text(root, SQL), "connect"))
    port = _lost(report)["storage.sql.connect"]
    assert (port.path, port.consumers, port.api_reason, port.export) == (SQL, [], "API_SYMBOL_REMOVED", "public_name")
    assert report.port_check.status == "COMPLETE" and report.port_check.checked_paths == [SQL]


def test_renamed_function_is_lost_with_consumers(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    port = _lost(_edit(root, doc, SQL, "def format_total", "def format_sum"))["storage.sql.format_total"]
    assert port.consumers == ["vgar:t/arch:python:component:services"]
    assert port.owner_component_id == "vgar:t/arch:python:component:storage"


def test_privatized_function_is_lost(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    assert "storage.sql.connect" in _lost(_edit(root, doc, SQL, "def connect", "def _connect"))


def test_removed_from_dunder_all_is_lost(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    assert _lost(_edit(root, doc, PRICING, ', "_internal"', ""))["services.pricing._internal"].export == "dunder_all"


def test_signature_change_is_not_lost(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    assert _edit(root, doc, PRICING, "def discount(value)", "def discount(value, extra=None)").port_check.lost == []


def test_line_shift_is_not_lost(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    check = _patch(root, doc, SQL, "# one\n# two\n# three\n" + _text(root, SQL)).port_check
    assert check.status == "COMPLETE" and check.lost == []


def test_duplicate_definition_loses_one(tmp_path: Path) -> None:
    head = "import sys\n\nif sys.platform == 'x':\n    def f():\n        return 1\n"
    doc = _build_repo(tmp_path, {"a.py": head + "else:\n    def f():\n        return 2\n"})
    lost = _patch(tmp_path, doc, "a.py", head).port_check.lost
    assert [port.port_id for port in lost] == ["vgar:t/arch:python:port:a.py:a.f@definition:7:4"]


def test_test_file_only_is_complete(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    path = "tests/test_handlers.py"
    check = _patch(root, doc, path, _text(root, path) + "# x\n").port_check
    assert check.status == "COMPLETE" and check.lost == [] and check.checked_paths == []


def test_other_source_roots_no_false_loss(tmp_path: Path) -> None:
    doc = _build_repo(tmp_path, {"lib/pkg/__init__.py": "", "lib/pkg/mod.py": "def f():\n    return 1\n",
                                 "lib/other/__init__.py": "", "lib/other/m.py": "def g():\n    return 2\n"}, source_roots=("lib",))
    check = _edit(tmp_path, doc, "lib/pkg/mod.py", "return 1", "return 3").port_check
    assert check.status == "COMPLETE" and check.lost == [] and check.checked_paths == ["lib/pkg/mod.py"]


def test_init_module_local_name(tmp_path: Path) -> None:
    doc = _build_repo(tmp_path, {"lib/pkg/__init__.py": "def f():\n    return 1\n", "lib/other/__init__.py": "def g():\n    return 2\n"},
                      source_roots=("lib",))
    check = _edit(tmp_path, doc, "lib/pkg/__init__.py", "return 1", "return 3").port_check
    assert check.status == "COMPLETE" and check.lost == [] and check.checked_paths == ["lib/pkg/__init__.py"]


@pytest.mark.parametrize("data", [pytest.param(b"def broken(:\n", id="syntax-error"), pytest.param(b"\xff\xfe", id="not-utf8"),
                                  pytest.param(b"# caf\xe9\ndef connect():\n    return 1\n", id="not-utf8-in-comment")])
def test_unparsable_after_is_partial(tmp_path: Path, data: bytes) -> None:
    _, doc = _case(tmp_path)
    check = check_lost_ports(doc, {SQL: data}, None)
    assert check.status == "PARTIAL" and check.lost == []
    assert [(item.path, item.reason) for item in check.unchecked] == [(SQL, "AFTER_PARSE_FAILED")]


def test_over_limit_is_partial(tmp_path: Path) -> None:
    _, doc = _case(tmp_path)
    check = check_lost_ports(doc, {SQL: b"#" * (5 * 1024 * 1024 + 1)}, None)
    assert check.status == "PARTIAL" and [item.reason for item in check.unchecked] == ["AFTER_TOO_LARGE"]


def test_class_removal_in_removed_api(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    path = "plugins/registry.py"
    report = _patch(root, doc, path, _without(_text(root, path), "Worker"))
    assert [(item.path, item.symbol) for item in report.port_check.removed_api] == [(path, "Worker")]
    assert "plugins.registry.Worker.process" in _lost(report)  # the method is a Port, so it is not repeated as API


def test_removed_test_function_is_not_public_api(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    path = "tests/test_handlers.py"
    name = next(n.name for n in ast.parse(_text(root, path)).body if isinstance(n, ast.FunctionDef))
    assert _patch(root, doc, path, _without(_text(root, path), name)).port_check.removed_api == []


def test_no_component_is_not_computed(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, _strip_arch(doc), SQL, "def connect", "def connect_mut")
    assert report.port_check.status == "NOT_COMPUTED" and _features(report)["ports_lost"].available is False


def test_two_files_one_broken_is_partial(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    after = {SQL: _without(_text(root, SQL), "connect").encode("utf-8"), PRICING: b"def broken(:\n"}
    check = check_lost_ports(doc, after, None)
    assert check.status == "PARTIAL" and [item.qualified_name for item in check.lost] == ["storage.sql.connect"]
    assert [(item.path, item.reason) for item in check.unchecked] == [(PRICING, "AFTER_PARSE_FAILED")]


def test_route_port_is_skipped(tmp_path: Path) -> None:
    doc = _build_repo(tmp_path, {"a.py": "def _handler():\n    return 1\n\n\ndef pub():\n    return 2\n"})
    port = next(n for n in doc["nodes"] if n["type"] == "Port")
    handler = next(n for n in doc["nodes"] if n["qualified_name"] == "a._handler")
    doc["nodes"].append({**port, "id": "route-port", "name": "_handler", "qualified_name": "a._handler",
                         "properties": {**port["properties"], "symbol_id": handler["id"], "export": "route"}})
    check = check_lost_ports(doc, {"a.py": b"def pub_renamed():\n    return 2\n"}, None)
    assert [item.qualified_name for item in check.lost] == ["a.pub"]
    assert check.status == "PARTIAL" and [item.reason for item in check.unchecked] == ["ROUTE_FACTS_UNAVAILABLE"]
    assert check.checked_paths == ["a.py"]  # the other Ports of the file were compared


def test_report_has_port_check_and_risk(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _patch(root, doc, SQL, _without(_text(root, SQL), "connect"))
    assert report.port_check.status == "COMPLETE" and _features(report)["ports_lost"].value == 1


def test_partial_check_leaves_ports_lost_unavailable(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    report = _edit(root, doc, SQL, "def connect():", "def connect(:")
    assert report.port_check.status == "PARTIAL" and report.port_check.removed_api == []
    assert (_features(report)["ports_lost"].available, _features(report)["ports_lost"].reason) == (False, "NOT_COMPUTED")


# ---- removed_api only claims what check_api could read after the patch ------------------------------------------------

CLASS_CONSTANT_FUNCTION = "class K:\n    pass\n\n\nX = 1\n\n\ndef f():\n    return 1\n"


@pytest.mark.parametrize("old,new", [
    pytest.param("class K:", "class K(:", id="syntax-error"),
    pytest.param("X = 1\n", "X = 1\n__all__ += ['z']\n", id="dynamic-exports"),
    pytest.param("class K:", "import functools\n\n\n@functools.total_ordering\nclass K:", id="decorated-class"),
])
def test_unreadable_after_is_not_removed_api(tmp_path: Path, old: str, new: str) -> None:
    doc = _build_repo(tmp_path, {"a.py": CLASS_CONSTANT_FUNCTION})
    assert _edit(tmp_path, doc, "a.py", old, new).port_check.removed_api == []


def test_port_that_still_exists_is_not_removed_api(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    check = _edit(root, doc, SQL, "def connect", "@cached\ndef connect").port_check
    assert check.lost == [] and check.removed_api == []


def test_two_files_one_broken_reports_only_real_removals(tmp_path: Path) -> None:
    root, doc = _case(tmp_path)
    raw = _diff(SQL, _text(root, SQL), _without(_text(root, SQL), "connect")) + _diff(PRICING, _text(root, PRICING), "def broken(:\n")
    check = analyze_patch_impact(raw, doc, root, patch_policy=_policy(doc)).port_check
    assert check.status == "PARTIAL" and [port.qualified_name for port in check.lost] == ["storage.sql.connect"]
    assert check.removed_api == []


def test_api_reason_is_none_when_after_is_unreadable(tmp_path: Path) -> None:
    doc = _build_repo(tmp_path, {"a.py": CLASS_CONSTANT_FUNCTION})
    report = _patch(tmp_path, doc, "a.py", CLASS_CONSTANT_FUNCTION.replace("def f", "def g") + "__all__ += ['z']\n")
    assert [(port.qualified_name, port.api_reason) for port in report.port_check.lost] == [("a.f", None)]


# ---- MCP build-server rules (spec 5.5) ------------------------------------------------------------------------------

def test_tool_description_mentions_ports_and_args() -> None:
    tool = next(t for t in asyncio.run(graph_server.mcp.list_tools()) if t.name == "analyze_patch_impact")
    assert "Port" in tool.description and "port_check" in tool.description
    for name in ("diff", "graph_version", "max_hops", "max_nodes"):
        assert name in tool.description and name in tool.inputSchema["properties"]


def test_check_writes_nothing_to_stdout(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    root, doc = _case(tmp_path)
    capfd.readouterr()
    _edit(root, doc, SQL, "def connect", "def connect_mut")
    assert capfd.readouterr().out == ""


def test_check_spawns_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, doc = _case(tmp_path)
    after = {SQL: _without(_text(root, SQL), "connect").encode("utf-8")}

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("check_lost_ports must stay in memory")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(tempfile, "mkdtemp", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    assert [port.qualified_name for port in check_lost_ports(doc, after, None).lost] == ["storage.sql.connect"]


def test_extract_error_keeps_impact_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    root, doc = _case(tmp_path)

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("boom")

    monkeypatch.setattr(PythonGraphBuilder, "extract_source", broken)
    with caplog.at_level(logging.WARNING, logger="vgar.graph.port_check"):
        report = _edit(root, doc, SQL, "def connect", "def connect_mut")
    assert report.impacted.status == "COMPLETE" and report.port_check.status == "PARTIAL"
    assert [item.reason for item in report.port_check.unchecked] == ["AFTER_EXTRACT_FAILED"] and "ValueError" in caplog.text
