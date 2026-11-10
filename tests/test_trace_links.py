"""TR-1: trace links from G_task to G_repo and G_arch.

Expected values are written by hand from the inputs.
Spec: docs/superpowers/specs/2026-11-10-tv2-tr-1-trace-links-design.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vgar.contracts.schema import (
    EDGE_ENDPOINTS,
    SCHEMA_VERSION,
    validate_graph_document,
)
from vgar.graph import grounding as grounding_module
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.grounding import (
    AnchorEvidence,
    AnchorResult,
    TaskAnchor,
    TaskAnchorFinder,
    is_absolute_path,
    resolve_absolute_frame,
)
from vgar.graph.task_overlay import TaskOverlay, TaskOverlayBuilder, _digest
from vgar.graph.trace_links import TraceLink, build_trace_links, rank_component_traces

FILES = {"requests/api.py", "src/flask/app.py", "lib/mpl/x.py", "requests/packages/urllib3/c.py", "test_requests.py", "a/b/m.py", "b/m.py"}


@pytest.mark.parametrize(("path", "expected"), [
    ("/L/site-packages/requests/api.py", "requests/api.py"),
    ("/L/dist-packages/flask/app.py", "src/flask/app.py"),
    ("/L/site-packages/mpl/x.py", "lib/mpl/x.py"),
    ("/L/site-packages/urllib3/c.py", None),
    ("/a/site-packages/x/site-packages/requests/api.py", "requests/api.py"),
    ("/usr/lib/python2.7/requests/api.py", None),
    ("C:/Python38/Lib/a/b/m.py", None),
    ("/Users/me/test_requests.py", None),
    ("/home/me/proj/a/b/m.py", "a/b/m.py"),
    ("C:/work/a/b/m.py", "a/b/m.py"),
    ("/home/me/../a/b/m.py", None),
])
def test_resolve_absolute_frame(path: str, expected: str | None) -> None:
    assert resolve_absolute_frame(path, FILES) == expected


def test_site_packages_needs_exactly_one_layout() -> None:
    assert resolve_absolute_frame("/L/site-packages/p/m.py", {"p/m.py", "src/p/m.py"}) is None


@pytest.mark.parametrize(("path", "expected"), [("/a/b.py", True), ("C:/a/b.py", True), ("c:/a.py", True), ("a/b.py", False), ("<stdin>", False)])
def test_is_absolute_path(path: str, expected: bool) -> None:
    assert is_absolute_path(path) is expected


def test_schema_declares_resolves_to() -> None:
    assert EDGE_ENDPOINTS["RESOLVES_TO"] == {
        ("StackTraceFrame", "File"), ("StackTraceFrame", "Class"), ("StackTraceFrame", "Function"), ("StackTraceFrame", "Method"),
        ("StackTraceFrame", "Test"), ("FailingTest", "Test"), ("ErrorMessage", "Class"),
    }
    assert EDGE_ENDPOINTS["TRACES_TO"] == {("Issue", "Component"), ("Requirement", "Component")}
    assert SCHEMA_VERSION == "vgar-schema-full-v5"


def _repo_document(tmp_path: Path) -> dict[str, Any]:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return PythonGraphBuilder(repo_key="t/trace", repository_revision="rev").build(tmp_path)


def _path_line_anchors(document: dict[str, Any], issue: str) -> list[tuple[str, float]]:
    result = TaskAnchorFinder(document).find_task_anchors(issue, None)
    return [(anchor.path, anchor.score) for anchor in result.anchors if any(item.kind == "path_line" for item in anchor.evidence)]


def test_absolute_traceback_becomes_path_line_anchor(tmp_path: Path) -> None:
    issue = 'Traceback (most recent call last):\n  File "/x/site-packages/pkg/m.py", line 1, in f\nValueError: bad\n'
    assert _path_line_anchors(_repo_document(tmp_path), issue) == [("pkg/m.py", 0.95)]


def test_absolute_traceback_outside_the_repo_is_unmatched(tmp_path: Path) -> None:
    location = 'File "/usr/lib/python3.8/json/decoder.py", line 1'
    result = TaskAnchorFinder(_repo_document(tmp_path)).find_task_anchors(f"{location}, in f\n", None)
    assert result.anchors == [] and location in result.unmatched_locations[0]


def test_absolute_path_in_prose_is_still_ignored(tmp_path: Path) -> None:
    document = _repo_document(tmp_path)
    result = TaskAnchorFinder(document).find_task_anchors("see /x/site-packages/pkg/m.py:1 please", None)
    assert not any(item.kind == "path_line" for anchor in result.anchors for item in anchor.evidence)
    assert "/x/site-packages/pkg/m.py:1" in result.unmatched_locations


def test_issue_without_absolute_traceback_keeps_anchors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(path: str, files: Any) -> None:
        raise AssertionError(path)

    monkeypatch.setattr(grounding_module, "resolve_absolute_frame", unexpected)
    assert _path_line_anchors(_repo_document(tmp_path), 'File "pkg/m.py", line 1, in f\n') == [("pkg/m.py", 0.95)]


def _range(start: int, end: int) -> dict[str, int]:
    return {"start_line": start, "start_col": 0, "end_line": end, "end_col": 1, "start_byte": start, "end_byte": end}


def _file(path: str) -> dict[str, Any]:
    return {"id": f"file:{path}", "type": "File", "name": path.rsplit("/", 1)[-1], "qualified_name": path, "path": path, "properties": {}}


def _symbol(kind: str, name: str, path: str = "a/m.py", start: int = 1, end: int = 5) -> dict[str, Any]:
    return {"id": f"{kind}:{path}:{name}:{start}", "type": kind, "name": name, "qualified_name": f"a.m.{name}", "path": path, "range": _range(start, end), "properties": {}}


def _class(name: str, bases: list[str], qualified_name: str | None = None, start: int = 1) -> dict[str, Any]:
    node = _symbol("Class", name, start=start)
    node["properties"]["bases"] = bases
    node["qualified_name"] = qualified_name or node["qualified_name"]
    return node


def _frame(file: str, line: int = 3, function: str | None = "f") -> dict[str, Any]:
    return {"id": "frame", "type": "StackTraceFrame", "properties": {"file": file, "line": line, "function": function, "order": 0}}


def _error(exception_type: str) -> dict[str, Any]:
    return {"id": "error", "type": "ErrorMessage", "properties": {"exception_type": exception_type, "message": "m", "occurrences": 1}}


def _links(task_nodes: list[dict[str, Any]], nodes: list[dict[str, Any]], anchors: list[TaskAnchor] | None = None) -> list[TraceLink]:
    return build_trace_links("issue", task_nodes, AnchorResult("v", anchors or [], [], []), nodes)


def _frame_target(frame: dict[str, Any], nodes: list[dict[str, Any]]) -> tuple[str, float] | None:
    links = _links([frame], nodes)
    assert len(links) <= 1
    return (links[0].target_id, links[0].confidence) if links else None


def test_frame_named_symbol_containing_line() -> None:
    function = _symbol("Function", "f")
    link = _links([_frame("a/m.py")], [_file("a/m.py"), function])[0]
    assert (link.edge_type, link.source_id, link.target_id, link.confidence, link.rule_id) == (
        "RESOLVES_TO", "frame", function["id"], 0.95, "task.resolves_to.frame.v1")


def test_frame_prefers_smallest_named_symbol() -> None:
    outer, inner = _symbol("Function", "f", start=1, end=9), _symbol("Function", "f", start=2, end=4)
    assert _frame_target(_frame("a/m.py"), [_file("a/m.py"), outer, inner]) == (inner["id"], 0.95)


def test_frame_line_drift_unique_name() -> None:
    function = _symbol("Method", "f")
    assert _frame_target(_frame("a/m.py", line=99), [_file("a/m.py"), function]) == (function["id"], 0.8)


@pytest.mark.parametrize("function", ["<module>", "<lambda>", None, ""])
def test_frame_module_goes_to_file(function: str | None) -> None:
    assert _frame_target(_frame("a/m.py", function=function), [_file("a/m.py"), _symbol("Function", "f")]) == ("file:a/m.py", 0.7)


def test_frame_unknown_function_goes_to_file() -> None:
    assert _frame_target(_frame("a/m.py", function="g"), [_file("a/m.py"), _symbol("Function", "f")]) == ("file:a/m.py", 0.6)


def test_frame_line_drift_with_two_named_symbols_goes_to_file() -> None:
    nodes = [_file("a/m.py"), _symbol("Method", "f", start=1, end=2), _symbol("Method", "f", start=4, end=5)]
    assert _frame_target(_frame("a/m.py", line=99), nodes) == ("file:a/m.py", 0.6)


def test_frame_evidence() -> None:
    assert _links([_frame("a/m.py")], [_file("a/m.py")])[0].evidence == [{"kind": "frame_location", "file": "a/m.py", "line": "3"}]


@pytest.mark.parametrize(("file", "paths", "expected"), [
    ("a/m.py", ["x/a/m.py"], "x/a/m.py"),
    ("a/m.py", ["a/m.py", "x/a/m.py"], "a/m.py"),
    ("a/m.py", ["x/a/m.py", "y/a/m.py"], None),
    ("./a/m.py", ["a/m.py"], "a/m.py"),
    ("m.py", ["m.py", "a/m.py"], "m.py"),
    ("m.py", ["a/m.py"], None),
    ("<stdin>", ["a/m.py"], None),
])
def test_relative_frame_rules(file: str, paths: list[str], expected: str | None) -> None:
    target = _frame_target(_frame(file, function=None), [_file(path) for path in paths])
    assert target == (None if expected is None else (f"file:{expected}", 0.7))


def test_relative_frame_with_parent_segment() -> None:
    assert _links([_frame("../a/m.py")], [_file("a/m.py")]) == []


def test_windows_backslash_frame() -> None:
    assert _frame_target(_frame(r"C:\work\a\b\m.py", function=None), [_file("a/b/m.py")]) == ("file:a/b/m.py", 0.7)


@pytest.mark.parametrize("file", ["/usr/lib/python3.8/a/m.py", "/Users/me/m.py"])
def test_stdlib_and_user_script_frames_have_no_edge(file: str) -> None:
    assert _links([_frame(file)], [_file("a/m.py"), _file("m.py")]) == []


def test_failing_test_links_use_anchor_score() -> None:
    task_node = {"id": "failing", "type": "FailingTest", "properties": {"selector": "t.py::x", "test_node_ids": ["test:1"]}}
    anchor = TaskAnchor("test:1", "t.py", "x", 1.0, [AnchorEvidence("pytest_selector", "t.py::x", "failing_test")])
    link = _links([task_node], [], [anchor])[0]
    assert (link.edge_type, link.source_id, link.target_id, link.confidence, link.rule_id, link.evidence) == (
        "RESOLVES_TO", "failing", "test:1", 1.0, "task.resolves_to.failing_test.v1", [{"kind": "test_selector", "selector": "t.py::x"}])


def test_error_qualified_name() -> None:
    target = _class("FooError", [], qualified_name="p.m.FooError")
    link = _links([_error("p.m.FooError")], [target])[0]
    assert (link.edge_type, link.source_id, link.target_id, link.confidence, link.rule_id, link.evidence) == (
        "RESOLVES_TO", "error", target["id"], 0.9, "task.resolves_to.error.v1", [{"kind": "exception_name", "name": "p.m.FooError"}])


def test_error_builtin_bare_name_has_no_edge() -> None:
    assert _links([_error("ConnectionError")], [_class("ConnectionError", ["Exception"])]) == []


def test_error_dotted_reexport_uses_last_part() -> None:
    target = _class("ConnectionError", ["IOError"], qualified_name="p.exceptions.ConnectionError")
    assert [(link.target_id, link.confidence) for link in _links([_error("p.ConnectionError")], [target])] == [(target["id"], 0.6)]


def test_error_bare_project_name() -> None:
    target = _class("FooError", ["ValueError"])
    assert [(link.target_id, link.confidence) for link in _links([_error("FooError")], [target])] == [(target["id"], 0.6)]


def test_error_requires_exception_class() -> None:
    assert _links([_error("FooError")], [_class("FooError", []), _class("Other", ["Exception"], start=9)]) == []


@pytest.mark.parametrize("base", ["B", "p.B"])
def test_error_inherited_chain(base: str) -> None:
    target = _class("C", [base])
    assert [link.target_id for link in _links([_error("C")], [target, _class("B", ["Exception"], start=9)])] == [target["id"]]


def test_error_inheritance_cycle() -> None:
    assert _links([_error("A")], [_class("A", ["B"]), _class("B", ["A"], start=9)]) == []


def test_error_odd_bases() -> None:
    target = _class("C", ["metaclass=ABCMeta", "Generic[T]", "Exception"])
    assert [link.confidence for link in _links([_error("C")], [target])] == [0.6]


def test_error_same_name_twice() -> None:
    assert _links([_error("C")], [_class("C", ["Exception"]), _class("C", ["Exception"], start=9)]) == []


def test_error_unknown_name() -> None:
    assert _links([_error("KeyError")], [_class("C", ["Exception"])]) == []


def test_rank_component_traces() -> None:
    def edge(target: str, confidence: float, count: int) -> dict[str, Any]:
        return {"target_id": target, "confidence": confidence, "properties": {"anchor_count": count}}

    edges = [edge("a", 0.8, 1), edge("b", 0.75, 9), edge("d", 0.8, 2), edge("c", 0.8, 2)]
    assert [item["target_id"] for item in rank_component_traces(edges)] == ["c", "d", "a", "b"]


CASES = Path(__file__).parent / "fixtures" / "vgar-arch-cases"
ISSUE = ('Login crashes\n\nTraceback (most recent call last):\n  File "app/service.py", line 8, in login\n'
         '    user = normalize(name)\nValueError: bad name\n')


def _multi_package(issue: str = ISSUE, tests: list[str] | None = None) -> tuple[dict[str, Any], TaskOverlay]:
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(CASES / "multi_package")
    return document, TaskOverlayBuilder(document).build("t1", issue, tests)


def test_weak_component_edge_is_kept(tmp_path: Path) -> None:
    for package in ("p", "q"):
        (tmp_path / package).mkdir()
        (tmp_path / package / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "p" / "m.py").write_text("def alpha_one():\n    return 1\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(tmp_path)
    edges = [edge for edge in TaskOverlayBuilder(document).build("t1", "alpha_one fails").edges if edge["type"] == "TRACES_TO"]
    assert len(edges) == 1 and edges[0]["confidence"] < 0.7


def test_overlay_has_resolves_to_and_new_profile() -> None:
    document, overlay = _multi_package()
    edges = [edge for edge in overlay.edges if edge["type"] == "RESOLVES_TO"]
    target = next(node for node in document["nodes"] if node["type"] == "Function" and node["name"] == "login")
    assert [(edge["target_id"], edge["confidence"], edge["provenance"]["rule_id"]) for edge in edges] == [(target["id"], 0.95, "task.resolves_to.frame.v1")]
    assert overlay.overlay_id == _digest({"graph_version": overlay.graph_version, "task_id": "t1", "issue_text": ISSUE, "failing_tests": [], "labels": [],
                                          "profile": "task-overlay-v11-trace-links"})


def test_overlay_failing_test_resolves_to_test() -> None:
    _, overlay = _multi_package("x", ["tests/test_service.py::test_login"])
    edge = next(item for item in overlay.edges if item["type"] == "RESOLVES_TO")
    assert edge["confidence"] == 1.0 and edge["provenance"]["rule_id"] == "task.resolves_to.failing_test.v1"


def test_overlay_edges_are_stable() -> None:
    document, overlay = _multi_package()
    again = TaskOverlayBuilder(document).build("t1", ISSUE)
    assert overlay.edges == again.edges
    keys = [(edge["type"], edge["source_id"], edge["target_id"]) for edge in overlay.edges]
    assert keys == sorted(keys)


def test_frame_edge_rejected_as_traces_to() -> None:
    document, overlay = _multi_package()
    edge = next(item for item in overlay.edges if item["type"] == "RESOLVES_TO")
    merged = {**document, "nodes": document["nodes"] + overlay.nodes, "edges": document["edges"] + [{**edge, "type": "TRACES_TO"}]}
    with pytest.raises(ValueError, match="TRACES_TO"):
        validate_graph_document(merged)


def test_resolves_to_rejects_wrong_endpoints() -> None:
    document, overlay = _multi_package()
    edge = next(item for item in overlay.edges if item["type"] == "RESOLVES_TO")
    merged = {**document, "nodes": document["nodes"] + overlay.nodes, "edges": document["edges"] + [{**edge, "source_id": overlay.nodes[0]["id"]}]}
    with pytest.raises(ValueError, match="RESOLVES_TO"):
        validate_graph_document(merged)
