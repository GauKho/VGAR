"""GT-1: the G_task layer extracted from issue text and reported failing tests.

Expected values are written by hand from the inputs.
Spec: docs/superpowers/specs/2026-11-09-tv2-gt-1-g-task-design.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vgar.contracts.schema import (
    EDGE_ENDPOINTS,
    G_ARCH_EDGE_TYPES,
    NODE_TYPES,
    SCHEMA_VERSION,
)
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_graph import (
    CriterionFact,
    ErrorFact,
    FrameFact,
    TaskFacts,
    extract_task_facts,
)
from vgar.graph.task_overlay import TaskOverlay, TaskOverlayBuilder
from vgar.graph.tsg_extractor import TsgConfig


def test_schema_declares_g_task() -> None:
    assert {"BugReport", "Requirement", "UserStory", "AcceptanceCriterion", "FailingTest", "ErrorMessage",
            "StackTraceFrame", "Constraint", "Actor"} <= NODE_TYPES
    for target in ("StackTraceFrame", "ErrorMessage", "AcceptanceCriterion", "BugReport", "Route"):
        assert ("Issue", target) in EDGE_ENDPOINTS["MENTIONS"]
    assert EDGE_ENDPOINTS["TRACES_TO"] == {("Issue", "Component"), ("Requirement", "Component")}
    assert ("FailingTest", "BugReport") in EDGE_ENDPOINTS["REPRODUCES"] and ("Test", "Issue") in EDGE_ENDPOINTS["REPRODUCES"]
    assert ("Requirement", "Requirement") in EDGE_ENDPOINTS["DEPENDS_ON"]
    assert EDGE_ENDPOINTS["CONFLICTS_WITH"] == {("Requirement", "Requirement")}
    assert ("Test", "Requirement") in EDGE_ENDPOINTS["TESTS"]
    assert SCHEMA_VERSION == "vgar-schema-full-v5"


TRACE = ('Traceback (most recent call last):\n  File "a/b.py", line 8, in login\n    x()\n'
         "  File '<stdin>', line 1, in <module>\n  File \"c.py\", line 2\nValueError: bad name\n")


def test_frames() -> None:
    assert extract_task_facts(TRACE).frames == (
        FrameFact("a/b.py", 8, "login", 0), FrameFact("<stdin>", 1, "<module>", 1), FrameFact("c.py", 2, None, 2))


def test_two_tracebacks_keep_duplicate_frames() -> None:
    assert [frame.order for frame in extract_task_facts('File "a.py", line 1\nFile "a.py", line 1\n').frames] == [0, 1]


def test_errors_merge_duplicates_and_keep_module() -> None:
    text = "requests.exceptions.ConnectionError: x\nrequests.exceptions.ConnectionError: x\nKeyError: 'k'\n"
    assert extract_task_facts(text).errors == (ErrorFact("requests.exceptions.ConnectionError", "x", 2), ErrorFact("KeyError", "'k'", 1))


@pytest.mark.parametrize("line", ["except ValueError:", "ValueError:", "Warning: x", 'raise ValueError("x")', "class FooError(Exception):"])
def test_not_error_lines(line: str) -> None:
    assert extract_task_facts(line + "\n").errors == ()


@pytest.mark.parametrize("heading", ["## Acceptance Criteria", "**Acceptance criteria:**", "Definition of done", "> acceptance tests"])
def test_criteria_under_heading(heading: str) -> None:
    text = f"{heading}\n- first\n\n* [x] second\n3) third\nNot a bullet\n- outside\n"
    assert extract_task_facts(text).criteria == (CriterionFact("first", None), CriterionFact("second", True), CriterionFact("third", None))


def test_unchecked_box() -> None:
    assert extract_task_facts("## Acceptance criteria\n- [ ] a\n").criteria == (CriterionFact("a", False),)


def test_bullets_elsewhere_are_not_criteria() -> None:
    assert extract_task_facts("## Steps\n- first\n").criteria == ()


def test_heading_inside_code_block_is_ignored() -> None:
    assert extract_task_facts("```\n## Acceptance criteria\n- first\n```\n").criteria == ()


@pytest.mark.parametrize(("kwargs", "text", "signals"), [
    ({}, 'File "a.py", line 1\n', ("stack_frame",)), ({}, "KeyError: 'k'\n", ("error_message",)),
    ({"failing_tests": ["t.py::a"]}, "x", ("failing_test",)), ({"labels": ["BUG"]}, "x", ("label",)),
])
def test_bug_signals(kwargs: dict[str, list[str]], text: str, signals: tuple[str, ...]) -> None:
    assert extract_task_facts(text, **kwargs).bug_signals == signals


def test_word_bug_is_not_a_signal() -> None:
    assert extract_task_facts("This is a bug and it fails with an error.").bug_signals == ()


def test_other_label_is_not_a_signal() -> None:
    assert extract_task_facts("x", labels=["performance"]).bug_signals == ()


def test_blank_inputs_are_dropped() -> None:
    facts = extract_task_facts("x", failing_tests=["", "  ", "b", "a", "a"], labels=[" ", "Bug ", "bug"])
    assert facts.failing_tests == ("a", "b") and facts.labels == ("bug",)


def test_crlf_text() -> None:
    facts = extract_task_facts("KeyError: boom\r\n## Acceptance criteria\r\n- first\r\n")
    assert facts.errors[0].message == "boom" and facts.criteria[0].text == "first"


def test_windows_frame_path() -> None:
    assert extract_task_facts('File "C:\\x\\y.py", line 3, in f\n').frames[0].file == "C:\\x\\y.py"


@pytest.mark.parametrize("text", ["", "\x00\x01\x02", "a" * 2_000_000, "File \"" * 20_000, "- " * 50_000],
                         ids=["empty", "control-chars", "long-line", "repeated-file", "repeated-bullets"])
def test_odd_text_does_not_fail(text: str) -> None:
    assert isinstance(extract_task_facts(text), TaskFacts)


ISSUE = ('Login crashes\n\nTraceback (most recent call last):\n  File "app/service.py", line 8, in login\n'
         '    user = normalize(name)\nValueError: bad name\n')
CASES = Path(__file__).parent / "fixtures" / "vgar-arch-cases"


def _graph(repo: str, tsg: TsgConfig | None = None) -> dict[str, Any]:
    return PythonGraphBuilder(repo_key="t/arch", repository_revision="rev", tsg=tsg).build(CASES / repo)


def _overlay(repo: str, text: str, tests: list[str] | None = None, *, labels: list[str] | None = None,
             tsg: TsgConfig | None = None) -> TaskOverlay:
    return TaskOverlayBuilder(_graph(repo, tsg)).build("t1", text, tests, labels=labels)


def _of(overlay: TaskOverlay, kind: str) -> list[dict[str, Any]]:
    return [node for node in overlay.nodes if node["type"] == kind]


def _type(overlay: TaskOverlay, node_id: str) -> str | None:
    return next((node["type"] for node in overlay.nodes if node["id"] == node_id), None)


def test_overlay_frames_errors_and_bug_report() -> None:
    overlay = _overlay("multi_package", ISSUE)
    assert overlay.nodes[0]["type"] == "Issue" and overlay.nodes[0]["properties"]["labels"] == []
    frame = _of(overlay, "StackTraceFrame")[0]
    assert frame["properties"] == {"file": "app/service.py", "line": 8, "function": "login", "order": 0}
    assert frame["name"] == "app/service.py:8" and frame["qualified_name"] == "t1::stack_frame:0" and frame["path"] is None
    assert frame["id"].endswith(":task:" + overlay.nodes[0]["id"].split(":issue:")[1] + ":stack_frame:0")
    error = _of(overlay, "ErrorMessage")[0]
    assert error["name"] == "ValueError"
    assert error["properties"] == {"exception_type": "ValueError", "message": "bad name", "occurrences": 1}
    assert _of(overlay, "BugReport")[0]["properties"]["signals"] == ["error_message", "stack_frame"]
    confidence = {_type(overlay, edge["target_id"]): edge["confidence"] for edge in overlay.edges if edge["type"] == "MENTIONS"}
    assert confidence["StackTraceFrame"] == 0.95 and confidence["ErrorMessage"] == 0.9 and confidence["BugReport"] == 0.7
    rules = {edge["provenance"]["rule_id"] for edge in overlay.edges}
    assert "task.mentions.v1" in rules


def test_error_name_drops_module() -> None:
    overlay = _overlay("multi_package", "requests.exceptions.ConnectionError: x\n")
    assert _of(overlay, "ErrorMessage")[0]["name"] == "ConnectionError"


def test_overlay_acceptance_edge() -> None:
    overlay = _overlay("multi_package", "## Acceptance criteria\n- first\n")
    assert _of(overlay, "AcceptanceCriterion")[0]["properties"] == {"text": "first", "checked": None}
    assert {edge["confidence"] for edge in overlay.edges} == {0.7}
    assert _of(overlay, "BugReport") == []


def test_failing_tests_reproduce_bug_report() -> None:
    overlay = _overlay("multi_package", ISSUE, ["tests/test_service.py::test_login", "tests/test_service.py::test_missing"])
    failing = {node["name"]: node for node in _of(overlay, "FailingTest")}
    test_id = next(anchor.node_id for anchor in overlay.grounding.anchors if anchor.symbol == "tests.test_service.test_login")
    assert failing["tests/test_service.py::test_login"]["properties"] == {"selector": "tests/test_service.py::test_login", "test_node_ids": [test_id]}
    assert failing["tests/test_service.py::test_missing"]["properties"]["test_node_ids"] == []
    bug = _of(overlay, "BugReport")[0]["id"]
    edges = [edge for edge in overlay.edges if edge["type"] == "REPRODUCES" and edge["target_id"] == bug]
    assert len(edges) == 2 and {edge["confidence"] for edge in edges} == {0.8}
    assert all(edge["properties"]["input_reported_failure"] and not edge["properties"]["execution_verified"] for edge in edges)
    issue = overlay.nodes[0]["id"]
    assert any(edge["type"] == "REPRODUCES" and edge["source_id"] == test_id and edge["target_id"] == issue for edge in overlay.edges)


def test_label_bug_creates_bug_report_and_normalizes() -> None:
    overlay = _overlay("multi_package", "nothing", labels=[" Bug", "security"])
    assert overlay.nodes[0]["properties"]["labels"] == ["bug", "security"] and len(_of(overlay, "BugReport")) == 1
    assert _of(_overlay("multi_package", "nothing", labels=["security"]), "BugReport") == []


def test_labels_change_identity() -> None:
    plain, labelled = _overlay("multi_package", "x"), _overlay("multi_package", "x", labels=["security"])
    assert plain.overlay_id != labelled.overlay_id
    assert plain.nodes[0]["content_hash"] != labelled.nodes[0]["content_hash"]


def test_plain_issue_adds_nothing() -> None:
    overlay = _overlay("multi_package", "Nothing here mentions any code.\n")
    assert len(overlay.nodes) == 1 and overlay.edges == []


def test_retrieval_ignores_failing_test_nodes() -> None:
    root = CASES / "multi_package"
    document = _graph("multi_package")
    overlay = TaskOverlayBuilder(document).build("t1", ISSUE, ["tests/test_service.py::test_login"])
    retriever = GraphContextRetriever(document, root, count_tokens=lambda text: len(text.split()), counter_label="words")
    anchors = [anchor.node_id for anchor in overlay.grounding.anchors]
    result = retriever.retrieve(anchors, 500, issue_text=ISSUE, overlay=overlay)
    failing_ids = {node["id"] for node in _of(overlay, "FailingTest")}
    assert failing_ids
    assert not failing_ids & {item.node_id for item in result.context.items}


def test_traces_to_component() -> None:
    overlay = _overlay("multi_package", ISSUE)
    edges = [edge for edge in overlay.edges if edge["type"] == "TRACES_TO"]
    assert len(edges) == 1
    assert edges[0]["target_id"] == "vgar:t/arch:python:component:app"
    assert edges[0]["confidence"] == 0.95 and edges[0]["properties"]["anchor_count"] == 2
    assert edges[0]["provenance"]["rule_id"] == "task.traces_to.v1"
    evidence = edges[0]["provenance"]["evidence"]
    assert [item["kind"] for item in evidence] == ["anchor", "anchor"]
    assert [item["node_id"] for item in evidence] == sorted(item["node_id"] for item in evidence)


def test_test_anchors_do_not_trace() -> None:
    overlay = _overlay("multi_package", "x", ["tests/test_service.py::test_login"])
    assert not [edge for edge in overlay.edges if edge["type"] == "TRACES_TO"]


def test_ambiguous_anchors_do_not_trace() -> None:
    overlay = _overlay("boundary_cases", "format_total returns the wrong value\n")
    assert len([edge for edge in overlay.edges if edge["type"] == "MENTIONS"]) == 2
    assert not [edge for edge in overlay.edges if edge["type"] == "TRACES_TO"]


def test_evidence_is_capped_at_five(tmp_path: Path) -> None:
    names = ["alpha_one", "beta_two", "gamma_three", "delta_four", "epsilon_five", "zeta_six"]
    (tmp_path / "p").mkdir()
    (tmp_path / "q").mkdir()
    (tmp_path / "p" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "q" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "p" / "m.py").write_text("".join(f"def {name}():\n    return 1\n\n\n" for name in names), encoding="utf-8")
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(tmp_path)
    overlay = TaskOverlayBuilder(document).build("t1", " ".join(names))
    edge = next(item for item in overlay.edges if item["type"] == "TRACES_TO")
    assert edge["properties"]["anchor_count"] == 6 and len(edge["provenance"]["evidence"]) == 5


def test_graph_without_components() -> None:
    document = _graph("multi_package")
    removed_nodes = {"Component", "Port", "Service", "DeploymentUnit"}
    document = {**document, "nodes": [node for node in document["nodes"] if node["type"] not in removed_nodes],
                "edges": [edge for edge in document["edges"] if edge["type"] not in G_ARCH_EDGE_TYPES]}
    overlay = TaskOverlayBuilder(document).build("t1", ISSUE)
    assert not [edge for edge in overlay.edges if edge["type"] == "TRACES_TO"]


@pytest.mark.skipif(TsgConfig.from_env() is None, reason="needs VGAR_TSG_EXECUTABLE and VGAR_TSG_TREE_SITTER_DIR")
@pytest.mark.parametrize(("text", "confidence"), [("GET /items fails", 0.8), ("/items fails", 0.6), ("POST /items fails", None)])
def test_route_mentions_with_real_cli(text: str, confidence: float | None) -> None:
    overlay = _overlay("web_app", text, tsg=TsgConfig.from_env())
    found = [edge["confidence"] for edge in overlay.edges if edge["type"] == "MENTIONS" and edge["target_id"].split(":")[3:4] == ["route"]]
    assert found == ([confidence] if confidence is not None else [])


def test_huge_line_number_is_not_fatal() -> None:
    text = 'File "a.py", line ' + "9" * 5000 + "\n"
    assert extract_task_facts(text).frames == ()
    assert _of(_overlay("multi_package", text), "StackTraceFrame") == []


@pytest.mark.parametrize("text", [
    "## Definition of done\n- Code reviewed\n- Acceptance tests pass on CI\n- Docs updated\n",
])
def test_bullet_starting_like_a_heading_stays_a_criterion(text: str) -> None:
    assert [item.text for item in extract_task_facts(text).criteria] == ["Code reviewed", "Acceptance tests pass on CI", "Docs updated"]


@pytest.mark.parametrize("text", [
    "Acceptance tests are failing on main, steps:\n- open page\n- click\n",
    "- acceptance tests are flaky\n- unrelated note\n",
])
def test_prose_is_not_a_criteria_heading(text: str) -> None:
    assert extract_task_facts(text).criteria == ()


def test_failing_test_links_do_not_match_prefix_siblings(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_login():\n    pass\n\n\ndef test_login_two():\n    pass\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(tmp_path)
    overlay = TaskOverlayBuilder(document).build("t1", "x", ["tests/test_a.py::test_login", "tests/test_a.py::test_login_two"])
    symbols = {anchor.node_id: anchor.symbol for anchor in overlay.grounding.anchors}
    linked = {node["name"]: [symbols[item] for item in node["properties"]["test_node_ids"]] for node in _of(overlay, "FailingTest")}
    assert linked == {"tests/test_a.py::test_login": ["tests.test_a.test_login"], "tests/test_a.py::test_login_two": ["tests.test_a.test_login_two"]}


def test_bare_slash_needs_a_method_to_mention_a_route() -> None:
    builder = TaskOverlayBuilder(_graph("multi_package"))
    builder._document["nodes"].append({"id": "root", "type": "Route", "properties": {"route_path": "/", "methods": ["GET"]}})
    assert builder._mentioned_routes("use a / b and / or c") == {}
    assert builder._mentioned_routes("GET / fails") == {"root": 0.8}
