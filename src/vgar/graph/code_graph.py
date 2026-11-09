"""Statements and variable names from tree-sitter, and the thin adapter over Joern's output (plan L3-1)."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

from tree_sitter import Node

logger = logging.getLogger(__name__)

_DEFINITIONS = frozenset({"function_definition", "class_definition", "decorated_definition"})
_ROW_WIDTH = {"METHOD": 5, "CFG": 11, "CDG": 11, "DDG": 12, "RAISE": 5, "END": 1}
_EXIT_LABEL = "METHOD_RETURN"
_PARAMETER_LABEL = "METHOD_PARAMETER_IN"
_NOT_STATEMENT_LABELS = frozenset({"METHOD", _EXIT_LABEL, _PARAMETER_LABEL, "METHOD_PARAMETER_OUT"})
_TRANSPARENT_LABELS = frozenset({"BLOCK", "JUMP_TARGET"})


@dataclass(frozen=True)
class StatementFact:
    """One statement of a function body."""

    node: Node
    kind: str
    n: int  # 1-based among statements of the same kind in the function
    parent: int | None  # index of the enclosing statement; None when directly in the function
    condition: str | None  # if, elif, while
    value: str | None  # return


@dataclass(frozen=True)
class IdentifierFact:
    """One occurrence of a variable name in a function body."""

    node: Node
    name: str
    n: int  # 1-based among occurrences of the same name in the function
    statement: int  # index of the smallest statement holding it
    type: str | None


@dataclass
class JoernMethod:
    """One method of the Joern export."""

    path: str
    line: int
    name: str
    nodes: dict[str, tuple[str, int]]  # node id -> (label, line)
    cfg: list[tuple[str, str]]
    data: list[tuple[str, str, str]]  # (where defined, where used, variable)
    raises: dict[str, bool]  # call id -> inside a try


@dataclass(frozen=True)
class MethodFlow:
    """Control and data flow of one method between its statements (indices into the statement list)."""

    cfg: frozenset[tuple[int, int]]  # source -> target
    control: frozenset[tuple[int, int]]  # dependent -> controlling statement
    data: dict[tuple[int, int | None], tuple[str, ...]]  # use -> definition; None is a parameter of the method
    raises_fixed: int
    cannot_reach_exit: int


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _body(function: Node) -> list[Node]:
    body = function.child_by_field_name("body")
    return [] if body is None else body.named_children


def _is_statement(node: Node) -> bool:
    return node.type.endswith("_statement") or node.type in _DEFINITIONS or node.type == "elif_clause"


def _kind(node: Node) -> str:
    if node.type == "elif_clause":
        return "elif"
    if node.type == "decorated_definition":
        node = node.child_by_field_name("definition") or node
    if node.type == "class_definition":
        return "class"
    if node.type in _DEFINITIONS:
        return "def"
    return node.type.removesuffix("_statement")


def _fact(node: Node, source: bytes, n: int, kind: str, parent: int | None) -> StatementFact:
    condition = node.child_by_field_name("condition") if kind in {"if", "elif", "while"} else None
    value = None
    if kind == "return":
        value = next((child for child in node.named_children if child.type != "comment"), None)
    return StatementFact(node, kind, n, parent, None if condition is None else _text(condition, source),
                         None if value is None else _text(value, source))


def function_statements(function: Node, source: bytes) -> list[StatementFact]:
    """Return the statements of one function in source order, without entering nested definitions."""
    facts: list[StatementFact] = []
    same_kind: Counter[str] = Counter()
    # An explicit stack: a long chain such as a + b + c ... nests deeper than Python's recursion limit.
    stack: list[tuple[Node, int | None]] = [(child, None) for child in reversed(_body(function))]
    while stack:
        node, parent = stack.pop()
        if _is_statement(node):
            kind = _kind(node)
            same_kind[kind] += 1
            facts.append(_fact(node, source, same_kind[kind], kind, parent))
            if node.type in _DEFINITIONS:
                continue
            parent = len(facts) - 1
        stack.extend((child, parent) for child in reversed(node.named_children))
    return facts


def function_identifiers(function: Node, source: bytes, statements: list[StatementFact]) -> list[IdentifierFact]:
    """Return every variable-name occurrence in the function body; field names are not variables."""
    index_of = {statement.node.id: index for index, statement in enumerate(statements)}
    facts: list[IdentifierFact] = []
    same_name: Counter[str] = Counter()
    declared: dict[int, str] = {}
    stack: list[tuple[Node, int | None]] = [(child, None) for child in reversed(_body(function))]
    while stack:
        node, statement = stack.pop()
        if node.type in _DEFINITIONS:
            continue
        statement = index_of.get(node.id, statement)
        if node.type == "identifier" and statement is not None:
            name = _text(node, source)
            same_name[name] += 1
            facts.append(IdentifierFact(node, name, same_name[name], statement, declared.get(node.id)))
        field = {"attribute": "attribute", "keyword_argument": "name"}.get(node.type)
        field_name = None if field is None else node.child_by_field_name(field)
        if node.type == "assignment":
            left, annotation = node.child_by_field_name("left"), node.child_by_field_name("type")
            if left is not None and annotation is not None and left.type == "identifier":
                declared[left.id] = _text(annotation, source)
        stack.extend((child, statement) for child in reversed(node.named_children)
                     if field_name is None or child.id != field_name.id)
    return facts


def statement_at(statements: list[StatementFact], line: int) -> int | None:
    """Return the statement a 1-based line belongs to: the first one starting on it, else the smallest covering it.

    Joern gives only a line. In `if c: raise E`, mapping the condition to the `raise` would draw a false edge out of the `raise`.
    """
    best: int | None = None
    best_size = 0
    for index, statement in enumerate(statements):
        node = statement.node
        if node.start_point.row + 1 == line:
            return index
        if node.start_point.row + 1 < line <= node.end_point.row + 1:
            size = node.end_byte - node.start_byte
            if best is None or size < best_size:
                best, best_size = index, size
    return best


def statement_covering(statements: list[StatementFact], start_byte: int, end_byte: int) -> int | None:
    """Return the index of the smallest statement holding a byte span."""
    holding = [index for index, statement in enumerate(statements)
               if statement.node.start_byte <= start_byte and end_byte <= statement.node.end_byte]
    return min(holding, key=lambda index: statements[index].node.end_byte - statements[index].node.start_byte, default=None)


def parse_export(text: str) -> list[JoernMethod]:
    """Read the rows of joern/export.sc, raising ValueError when a row has the wrong shape."""
    # split("\n"), not splitlines(): a code column may hold other line separators such as U+2028.
    rows = [line.split("\t") for line in text.split("\n") if line]
    for row in rows:
        if len(row) != _ROW_WIDTH.get(row[0]):
            raise ValueError(f"malformed Joern export row: {row[:4]}")
    methods = {(row[1], row[2]): JoernMethod(row[1], int(row[3]), row[4], {}, [], [], {}) for row in rows if row[0] == "METHOD"}
    for row in rows:
        method = None if row[0] == "END" else methods.get((row[1], row[2]))
        if method is None or row[0] in {"METHOD", "CDG"}:
            continue
        if row[0] == "RAISE":
            method.raises[row[3]] = row[4] == "true"
            continue
        source, target = row[3], row[7]
        method.nodes[source] = (row[4], int(row[5]))
        method.nodes[target] = (row[8], int(row[9]))
        if row[0] == "CFG":
            method.cfg.append((source, target))
        else:
            method.data.append((source, target, row[11]))
    return list(methods.values())


def _cut_raises(method: JoernMethod, exit_node: str | None) -> tuple[list[tuple[str, str]], set[str]]:
    """Joern lets a raise fall through to the next statement; outside a try it ends the function instead."""
    successors: defaultdict[str, list[str]] = defaultdict(list)
    for source, target in method.cfg:
        successors[source].append(target)
    wrong = {node for node, in_try in method.raises.items()
             if not in_try and any(method.nodes[target][0] != _EXIT_LABEL for target in successors.get(node, ()))}
    cfg = [edge for edge in method.cfg if edge[0] not in wrong]
    if exit_node is not None:
        cfg.extend((node, exit_node) for node in sorted(wrong))
    return cfg, wrong


def _control_dependence(cfg: list[tuple[str, str]], exit_node: str | None) -> tuple[list[tuple[str, str]], int]:
    """Ferrante-Ottenstein-Warren over the corrected CFG: (controlling node, dependent node) pairs."""
    import networkx as nx

    graph = nx.DiGraph(cfg)
    if exit_node is None or exit_node not in graph:
        logger.debug("method without a reachable exit: %d CFG edges", graph.number_of_edges())
        return [], graph.number_of_edges()
    # networkx 3.6 leaves the start node (the exit, on the reversed graph) out of the result.
    post_dominator = nx.immediate_dominators(graph.reverse(copy=False), exit_node)
    found: list[tuple[str, str]] = []
    cannot_reach = 0
    for source, target in graph.edges:
        if source not in post_dominator or (target not in post_dominator and target != exit_node):
            cannot_reach += 1
            continue
        walker = target
        while walker != post_dominator[source] and walker != exit_node:
            found.append((source, walker))
            following = post_dominator.get(walker)
            if following is None or following == walker:
                break
            walker = following
    return found, cannot_reach


def project_method(method: JoernMethod, statements: list[StatementFact]) -> MethodFlow:
    """Correct one Joern method and project its flow onto the statements of the function."""
    exit_node = next((node for node, (label, _) in method.nodes.items() if label == _EXIT_LABEL), None)
    cfg, cut = _cut_raises(method, exit_node)
    control, cannot_reach = _control_dependence(cfg, exit_node)
    by_line: dict[int, int | None] = {}

    def statement_of(node: str) -> int | None:
        label, line = method.nodes[node]
        if label in _NOT_STATEMENT_LABELS or label in _TRANSPARENT_LABELS:
            return None
        if line not in by_line:
            by_line[line] = statement_at(statements, line)
        return by_line[line]

    successors: defaultdict[str, list[str]] = defaultdict(list)
    for source, target in cfg:
        successors[source].append(target)
    next_pairs: set[tuple[int, int]] = set()
    for start, following in successors.items():
        origin = statement_of(start)
        if origin is None:
            continue
        stack, seen = list(following), set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            reached = statement_of(node)
            if reached is not None:
                if reached != origin:
                    next_pairs.add((origin, reached))
            elif method.nodes[node][0] != _EXIT_LABEL:
                stack.extend(successors.get(node, ()))  # a scope marker, or a node Joern gave no line

    control_pairs: set[tuple[int, int]] = set()
    for controlling, dependent in control:
        source_index, target_index = statement_of(dependent), statement_of(controlling)
        if source_index is not None and target_index is not None and source_index != target_index:
            control_pairs.add((source_index, target_index))

    raised = {statement_of(node) for node in cut}
    merged: defaultdict[tuple[int, int | None], set[str]] = defaultdict(set)
    for definition, use, variable in method.data:
        user = statement_of(use)
        if user is None:
            continue
        origin = None
        if method.nodes[definition][0] != _PARAMETER_LABEL:
            origin = statement_of(definition)
            if origin is None or origin == user or origin in raised:
                continue
        names = merged[user, origin]
        if variable.isidentifier():
            names.add(variable)
    return MethodFlow(frozenset(next_pairs), frozenset(control_pairs), {key: tuple(sorted(names)) for key, names in merged.items()},
                      len(cut), cannot_reach)
