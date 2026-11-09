"""L3-1: G_code schema, statements from tree-sitter and the adapter over Joern's output."""
from __future__ import annotations

import ast
import copy
from collections.abc import Iterator
from pathlib import Path

import networkx as nx
import pytest
import tree_sitter_python
from tree_sitter import Language, Node, Parser

from vgar.contracts.schema import (
    EDGE_ENDPOINTS,
    G_CODE_EDGE_TYPES,
    NODE_TYPES,
    SCHEMA_VERSION,
    SOURCE_BACKED_NODE_TYPES,
    GraphValidationError,
    validate_graph_document,
)
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.code_graph import (
    JoernMethod,
    MethodFlow,
    StatementFact,
    function_identifiers,
    function_statements,
    parse_export,
    project_method,
    statement_at,
)

REPOSITORY = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
PARSER = Parser(Language(tree_sitter_python.language()))


def test_schema_declares_g_code() -> None:
    assert "Statement" in NODE_TYPES and "Statement" not in SOURCE_BACKED_NODE_TYPES
    assert G_CODE_EDGE_TYPES == {"AST_CHILD", "CFG_NEXT", "DATA_DEPENDS_ON", "CONTROL_DEPENDS_ON"}
    assert EDGE_ENDPOINTS["AST_CHILD"] == {("Function", "Statement"), ("Method", "Statement"), ("Statement", "Statement"),
                                           ("Statement", "CallSite"), ("Statement", "Identifier")}
    assert EDGE_ENDPOINTS["CFG_NEXT"] == EDGE_ENDPOINTS["CONTROL_DEPENDS_ON"] == {("Statement", "Statement")}
    assert EDGE_ENDPOINTS["DATA_DEPENDS_ON"] == {("Statement", "Statement"), ("Statement", "Function"), ("Statement", "Method")}
    assert SCHEMA_VERSION == "vgar-schema-full-v4"


def test_validate_rejects_wrong_g_code_endpoint(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    document = PythonGraphBuilder(repo_key="r", repository_revision="base", source_roots=(".",)).build(tmp_path)
    function = next(node for node in document["nodes"] if node["type"] == "Function")
    file_node = next(node for node in document["nodes"] if node["type"] == "File")
    edge = copy.deepcopy(document["edges"][0])
    edge.update(id="bad-edge", type="CFG_NEXT", source_id=function["id"], target_id=file_node["id"])
    document["edges"].append(edge)
    with pytest.raises(GraphValidationError, match="invalid endpoints for CFG_NEXT"):
        validate_graph_document(document)


def _function_nodes(root: Node) -> Iterator[Node]:
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            yield node
        stack.extend(reversed(node.named_children))


def _function(source: bytes) -> Node:
    return next(_function_nodes(PARSER.parse(source).root_node))


SAMPLE = b"""def f(a):
    if a:
        x: int = g(k=a)
    elif a.b:
        pass
    else:
        for i in a:
            print(i)
    try:
        y = 1
    except E:
        y = 2
    def inner():
        z = 1
    h = lambda q: q
    return y
"""


def test_statement_kinds_and_nesting() -> None:
    facts = function_statements(_function(SAMPLE), SAMPLE)
    assert [s.kind for s in facts] == ["if", "expression", "elif", "pass", "for", "expression", "try", "expression",
                                       "expression", "def", "expression", "return"]
    assert facts[0].condition == "a" and facts[2].condition == "a.b" and facts[-1].value == "y"
    assert facts[1].parent == 0 and facts[0].parent is None and facts[9].parent is None
    assert [s.n for s in facts if s.kind == "expression"] == [1, 2, 3, 4, 5]


def test_identifiers_skip_attribute_and_keyword_names() -> None:
    function = _function(SAMPLE)
    facts = function_identifiers(function, SAMPLE, function_statements(function, SAMPLE))
    names = [f.name for f in facts]
    assert "b" not in names and "k" not in names and "z" not in names
    assert names.count("a") >= 3 and "q" in names
    assert next(f for f in facts if f.name == "x").type == "int"
    assert [f.n for f in facts if f.name == "y"] == [1, 2, 3]


def test_identifier_belongs_to_the_smallest_statement() -> None:
    function = _function(SAMPLE)
    statements = function_statements(function, SAMPLE)
    facts = function_identifiers(function, SAMPLE, statements)
    assert statements[next(f for f in facts if f.name == "x").statement].kind == "expression"
    assert statements[next(f for f in facts if f.name == "a").statement].kind == "if"
    assert statements[[f for f in facts if f.name == "y"][-1].statement].kind == "return"


def test_decorated_definition_uses_inner_kind() -> None:
    source = b"def f():\n    @d\n    class C:\n        x = 1\n    @d\n    def g():\n        y = 1\n"
    assert [s.kind for s in function_statements(_function(source), source)] == ["class", "def"]


def test_one_line_and_async_functions() -> None:
    one_line = b"def f(x): return x\n"
    assert [s.kind for s in function_statements(_function(one_line), one_line)] == ["return"]
    coroutine = b"async def f(items):\n    async for item in items:\n        await item\n    async with items as held:\n        pass\n"
    assert [s.kind for s in function_statements(_function(coroutine), coroutine)] == ["for", "expression", "with", "pass"]


def test_match_statement_and_case_bodies() -> None:
    source = b"def f(v):\n    match v:\n        case 1:\n            a = 1\n        case _:\n            a = 2\n    return a\n"
    facts = function_statements(_function(source), source)
    assert [s.kind for s in facts] == ["match", "expression", "expression", "return"]
    assert facts[1].parent == 0 and facts[2].parent == 0


def test_statement_at_returns_the_smallest() -> None:
    source = b"def f(a):\n    if a:\n        b = (\n            1)\n    return a\n"
    statements = function_statements(_function(source), source)

    def kind(line: int) -> str:
        return statements[statement_at(statements, line)].kind

    assert statement_at(statements, 1) is None and statement_at(statements, 99) is None
    assert kind(2) == "if" and kind(3) == kind(4) == "expression" and kind(5) == "return"


def test_statement_at_prefers_the_statement_starting_on_the_line() -> None:
    source = b"def f(a):\n    if a: raise E\n    return 1\n"
    statements = function_statements(_function(source), source)
    assert statements[statement_at(statements, 2)].kind == "if"


def _ast_statements(body: list[ast.stmt]) -> Iterator[ast.stmt]:
    for statement in body:
        yield statement
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            inner = getattr(statement, field, None)
            if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                yield from _ast_statements(inner)
        for handler in getattr(statement, "handlers", []):
            yield from _ast_statements(handler.body)
        for case in getattr(statement, "cases", []):
            yield from _ast_statements(case.body)


def _name(node: Node, data: bytes) -> str:
    name = node.child_by_field_name("name")
    return data[name.start_byte:name.end_byte].decode()


@pytest.mark.parametrize("repo", [REPOSITORY / "src" / "vgar", FIXTURES / "sample_repo", FIXTURES / "vgar-arch-cases",
                                  FIXTURES / "vgar-callgraph-cases"], ids=lambda path: path.name)
def test_statement_count_matches_python_ast(repo: Path) -> None:
    compared = 0
    for path in sorted(repo.rglob("*.py")):
        data = path.read_bytes()
        try:
            tree = ast.parse(data)
        except (SyntaxError, ValueError):
            continue
        expected = {(node.lineno, node.name): sum(1 for _ in _ast_statements(node.body))
                    for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        counted = {(node.start_point.row + 1, _name(node, data)): len(function_statements(node, data))
                   for node in _function_nodes(PARSER.parse(data).root_node)}
        assert counted == expected, path
        compared += len(expected)
    assert compared > 0


def test_deeply_nested_expression_does_not_overflow() -> None:
    source = b"def f():\n    return " + b" + ".join([b"1"] * 5000) + b"\n"
    function = _function(source)
    statements = function_statements(function, source)
    assert [s.kind for s in statements] == ["return"]
    assert function_identifiers(function, source, statements) == []


# Line numbers of tests/fixtures/joern/flow_cases.py, written by hand from its source.
EXPECTED = {
    "login": ({(2, 3), (3, 4), (3, 5), (5, 6)}, {(4, 3), (5, 3), (6, 3)}),
    "guarded": ({(11, 13), (11, 16), (13, 14), (14, 16), (16, 17)}, {(13, 11), (14, 11)}),
    "managed": ({(21, 22), (22, 21), (21, 23)}, set()),
    "checked": ({(27, 28), (27, 29), (29, 30)}, {(28, 27), (29, 27), (30, 27)}),
    "looped": ({(34, 35), (35, 36), (35, 39), (36, 37), (36, 38), (37, 39), (38, 35)}, {(36, 35), (37, 36), (38, 36), (35, 36)}),
    "matched": ({(43, 45), (43, 47), (45, 48), (47, 48)}, {(45, 43), (47, 43)}),
    "one_line_guard": ({(67, 68)}, {(68, 67)}),
}
DATA = {
    "login": [(3, 2), (5, 2), (6, 5), (2, None)],
    "checked": [(27, None), (28, None), (29, None), (30, 29)],
    "looped": [(38, 34), (39, 34), (36, 35), (38, 35), (39, 38)],
    "matched": [(48, 45), (48, 47)],
}
FLOW_TEXT = (FIXTURES / "joern" / "flow_cases.edges.tsv").read_text(encoding="utf-8")
FLOW_SOURCE = (FIXTURES / "joern" / "flow_cases.py").read_bytes()
FLOW_METHODS = [method for method in parse_export(FLOW_TEXT) if method.path == "flow_cases.py"]


def _statements_of(name: str, line: int | None) -> list[StatementFact]:
    function = next(node for node in _function_nodes(PARSER.parse(FLOW_SOURCE).root_node)
                    if _name(node, FLOW_SOURCE) == name and line in (None, node.start_point.row + 1))
    return function_statements(function, FLOW_SOURCE)


def _flow(name: str, line: int | None = None) -> tuple[MethodFlow, list[int]]:
    statements = _statements_of(name, line)
    method = next(item for item in FLOW_METHODS if item.name == name and line in (None, item.line))
    return project_method(method, statements), [statement.node.start_point.row + 1 for statement in statements]


def _by_line(flow: MethodFlow, lines: list[int]) -> dict[tuple[int, int | None], tuple[str, ...]]:
    return {(lines[use], None if definition is None else lines[definition]): names for (use, definition), names in flow.data.items()}


def _method(nodes: dict[str, tuple[str, int]], cfg=(), data=(), raises=None) -> JoernMethod:
    return JoernMethod(path="m.py", line=1, name="f", nodes=nodes, cfg=list(cfg), data=list(data), raises=raises or {})


@pytest.mark.parametrize("name", EXPECTED)
def test_cfg_and_control_match_hand_answers(name: str) -> None:
    flow, lines = _flow(name)
    assert {(lines[a], lines[b]) for a, b in flow.cfg} == EXPECTED[name][0]
    assert {(lines[a], lines[b]) for a, b in flow.control} == EXPECTED[name][1]


@pytest.mark.parametrize("name", DATA)
def test_data_has_a_path(name: str) -> None:
    flow, lines = _flow(name)
    graph = nx.DiGraph([(use, definition or 0) for use, definition in _by_line(flow, lines)])  # 0 stands for the parameters
    for use, definition in DATA[name]:
        assert use in graph and (definition or 0) in graph and nx.has_path(graph, use, definition or 0), (use, definition)


@pytest.mark.xfail(strict=True, reason="Joern has no REACHING_DEF into a bare name that is the whole condition of if, while or match")
def test_bare_match_subject_depends_on_the_parameter() -> None:
    flow, lines = _flow("matched")
    assert (43, None) in _by_line(flow, lines)


def test_data_lists_only_simple_variable_names() -> None:
    flow, lines = _flow("login")
    by_line = _by_line(flow, lines)
    assert by_line[6, 5] == ("session",)
    assert all(name.isidentifier() for names in by_line.values() for name in names)


def test_unpacked_assignment_reports_only_the_used_name() -> None:
    flow, lines = _flow("unpacked")
    assert _by_line(flow, lines)[53, 52] == ("x",)


def test_several_variables_merge_into_one_edge() -> None:
    source = b"def f():\n    a, b = g()\n    h(a, b)\n"
    statements = function_statements(_function(source), source)
    nodes = {"d": ("IDENTIFIER", 2), "u": ("IDENTIFIER", 3)}
    flow = project_method(_method(nodes, data=[("d", "u", "b"), ("d", "u", "a"), ("d", "u", "a + 1")]), statements)
    assert flow.data == {(1, 0): ("a", "b")}


def test_pair_without_a_simple_name_keeps_the_edge() -> None:
    source = b"def f(s):\n    s.x = 1\n    g(s.x)\n"
    statements = function_statements(_function(source), source)
    nodes = {"d": ("CALL", 2), "u": ("CALL", 3)}
    assert project_method(_method(nodes, data=[("d", "u", "s.x")]), statements).data == {(1, 0): ()}


def test_parameter_of_a_one_line_function_targets_the_function() -> None:
    source = b"def f(x): return x\n"
    statements = function_statements(_function(source), source)
    nodes = {"p": ("METHOD_PARAMETER_IN", 1), "u": ("IDENTIFIER", 1)}
    assert project_method(_method(nodes, data=[("p", "u", "x")]), statements).data == {(0, None): ("x",)}


def test_raise_in_try_is_left_alone() -> None:
    flow, lines = _flow("guarded")
    assert flow.raises_fixed == 0 and (14, 16) in {(lines[a], lines[b]) for a, b in flow.cfg}


def test_raise_outside_try_is_cut() -> None:
    flow, lines = _flow("checked")
    assert flow.raises_fixed == 1 and (28, 29) not in {(lines[a], lines[b]) for a, b in flow.cfg}


def test_raise_already_exit_is_not_counted() -> None:
    source = b"def f():\n    raise E\n"
    statements = function_statements(_function(source), source)
    nodes = {"r": ("CALL", 2), "x": ("METHOD_RETURN", 1)}
    assert project_method(_method(nodes, cfg=[("r", "x")], raises={"r": False}), statements).raises_fixed == 0


def test_multi_line_raise_drops_dataflow_from_all_its_lines() -> None:
    source = b"def f(a, b):\n    if a:\n        raise E(\n            b)\n    return b\n"
    statements = function_statements(_function(source), source)
    nodes = {"r": ("CALL", 3), "arg": ("IDENTIFIER", 4), "use": ("IDENTIFIER", 5), "x": ("METHOD_RETURN", 1)}
    flow = project_method(_method(nodes, cfg=[("r", "use"), ("use", "x")], data=[("arg", "use", "b")], raises={"r": False}), statements)
    assert flow.raises_fixed == 1 and flow.data == {} and flow.cfg == frozenset()


def test_one_line_guard_has_no_false_fall_through() -> None:
    source = b"def f(a):\n    if a: raise E\n    return 1\n"
    statements = function_statements(_function(source), source)
    nodes = {"c": ("IDENTIFIER", 2), "r": ("CALL", 2), "n": ("RETURN", 3), "x": ("METHOD_RETURN", 1)}
    cfg = [("c", "r"), ("c", "n"), ("r", "n"), ("n", "x")]
    flow = project_method(_method(nodes, cfg=cfg, raises={"r": False}), statements)
    assert flow.raises_fixed == 1 and flow.cfg == {(0, 2)} and flow.control == {(2, 0)}


def test_node_without_path_to_exit_does_not_fail() -> None:
    source = b"def f():\n    a()\n    b()\n    c()\n    d()\n"
    statements = function_statements(_function(source), source)
    nodes = {"a": ("CALL", 2), "b": ("CALL", 3), "c": ("CALL", 4), "d": ("CALL", 5), "x": ("METHOD_RETURN", 1)}
    flow = project_method(_method(nodes, cfg=[("a", "c"), ("c", "x"), ("a", "b"), ("b", "d"), ("d", "b")]), statements)
    assert flow.cannot_reach_exit == 3


def test_method_without_exit_has_no_control_edges() -> None:
    source = b"def f():\n    a()\n    b()\n"
    statements = function_statements(_function(source), source)
    flow = project_method(_method({"a": ("CALL", 2), "b": ("CALL", 3)}, cfg=[("a", "b"), ("b", "a")]), statements)
    assert flow.control == frozenset() and flow.cannot_reach_exit == 2 and flow.cfg == {(0, 1), (1, 0)}


def test_node_without_a_line_is_followed() -> None:
    source = b"def f():\n    a = 1\n    b = 2\n"
    statements = function_statements(_function(source), source)
    nodes = {"a": ("IDENTIFIER", 2), "l": ("LITERAL", -1), "b": ("IDENTIFIER", 3)}
    assert project_method(_method(nodes, cfg=[("a", "l"), ("l", "b")]), statements).cfg == {(0, 1)}


def test_property_getter_and_setter_stay_apart() -> None:
    assert sorted(item.line for item in FLOW_METHODS if item.name == "size") == [58, 62]
    getter, getter_lines = _flow("size", 58)
    setter, setter_lines = _flow("size", 62)
    assert getter_lines == [59] and setter_lines == [63]
    assert (59, None) in _by_line(getter, getter_lines) and "value" in _by_line(setter, setter_lines)[63, None]


def test_parse_export_rejects_short_row() -> None:
    with pytest.raises(ValueError, match="malformed"):
        parse_export("CFG\tx")


def test_parse_export_rejects_unknown_row() -> None:
    with pytest.raises(ValueError, match="malformed"):
        parse_export("WHAT\ta\tb\tc\td")


def test_parse_export_splits_rows_only_on_newline() -> None:
    row = "METHOD\tm.py\tm.f\t1\tf\nCFG\tm.py\tm.f\t1\tCALL\t2\ta\rb\u2028c\t2\tCALL\t3\td\n"
    assert parse_export(row)[0].cfg == [("1", "2")]


def test_parse_export_accepts_the_end_marker() -> None:
    assert [method.name for method in parse_export("METHOD\tm.py\tm.f\t1\tf\nEND\n")] == ["f"]


def test_parse_export_ignores_rows_of_an_unknown_method() -> None:
    assert parse_export("CFG\t?\t?\t1\tCALL\t2\ta\t2\tCALL\t3\tb\n") == []


def test_parse_export_keeps_helper_methods_apart() -> None:
    assert {"<module>", "login"} <= {item.name for item in FLOW_METHODS}
    assert next(item for item in FLOW_METHODS if item.name == "login").line == 1
    assert "<operator>.assignment" in {item.name for item in parse_export(FLOW_TEXT)}
