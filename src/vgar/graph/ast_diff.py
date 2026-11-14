"""Compare Python declarations and bodies in the file versions from Git history.

Docstrings are compared apart from the rest of a body (``changed_parts`` ``"docstring"``), and
module-level assignments to plain names are reported as ``global`` symbols. A module docstring is
neither an entity nor a module statement, so editing only it gives no change.
"""
from __future__ import annotations

import ast
import stat
from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vgar.graph.history import CommitChange, FileVersion

DEFINITIONS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class DefinitionSpan:
    kind: Literal["class", "function", "async_function", "global"]
    start_line: int
    end_line: int


@dataclass(frozen=True)
class SymbolEdit:
    symbol: str
    change: Literal["ADDED", "REMOVED", "MODIFIED"]
    before: tuple[DefinitionSpan, ...]
    after: tuple[DefinitionSpan, ...]
    changed_parts: tuple[Literal["declaration", "body", "docstring"], ...] = ()


@dataclass(frozen=True)
class PythonAstDiff:
    edits: tuple[SymbolEdit, ...]
    module_statements_changed: bool


@dataclass(frozen=True)
class ParseError:
    side: Literal["before", "after"]
    message: str


@dataclass(frozen=True)
class PythonFileDiff:
    before: FileVersion | None
    after: FileVersion | None
    ast_diff: PythonAstDiff
    parse_error: ParseError | None = None


@dataclass(frozen=True)
class _Definition:
    span: DefinitionSpan
    declaration: str
    body: tuple[str, ...]
    class_order: tuple[tuple[str, str], ...] = ()
    docstring: str | None = None


def _split_docstring(body: list[ast.stmt]) -> tuple[str | None, list[ast.stmt]]:
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value.value, body[1:]
    return None, body


def _global_names(node: ast.stmt) -> list[str]:
    """Plain names a module-level assignment binds; empty for any other statement."""
    if isinstance(node, ast.Assign) and all(isinstance(target, ast.Name) for target in node.targets):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _statements(body: list[ast.stmt]) -> tuple[str, ...]:
    return tuple(ast.dump(node) for node in body if not isinstance(node, DEFINITIONS))


def _order(body: list[ast.stmt]) -> tuple[tuple[str, str], ...]:
    return tuple(("definition", node.name) if isinstance(node, DEFINITIONS) else ("statement", ast.dump(node))
                 for node in body)


def _order_changed(before: tuple[tuple[str, str], ...], after: tuple[tuple[str, str], ...]) -> bool:
    """Check relative order for statements with one unambiguous match on each side."""
    if before == after:
        return False
    left, right = Counter(before), Counter(after)
    shared = {key for key in left if left[key] == right[key] == 1}
    return tuple(key for key in before if key in shared) != tuple(key for key in after if key in shared)


def _definitions(body: list[ast.stmt], scope: str, result: dict[str, list[_Definition]]) -> None:
    for node in body:
        if not isinstance(node, DEFINITIONS):
            continue
        name = f"{scope}{node.name}"
        header = copy(node)
        header.body = []
        start = min((node.lineno, *(decorator.lineno for decorator in node.decorator_list)))
        kind: Literal["class", "function", "async_function"]
        docstring, rest = _split_docstring(node.body)
        if isinstance(node, ast.ClassDef):
            kind = "class"
            statements = _statements(rest)
            class_order = _order(rest)
            _definitions(node.body, f"{name}.", result)
        else:
            kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
            statements = tuple(ast.dump(statement) for statement in rest)
            class_order = ()
        span = DefinitionSpan(kind, start, node.end_lineno or node.lineno)
        result[name].append(_Definition(span, ast.dump(header), statements, class_order, docstring))


def _globals(body: list[ast.stmt], result: dict[str, list[_Definition]]) -> list[ast.stmt]:
    """Collect module-level plain-name assignments; return the other module statements."""
    rest = []
    for node in body:
        names = _global_names(node)
        if not names:
            rest.append(node)
            continue
        span = DefinitionSpan("global", node.lineno, node.end_lineno or node.lineno)
        for name in names:
            result[name].append(_Definition(span, "", (ast.dump(node),)))
    return rest


def diff_python_ast(before: bytes | None, after: bytes | None, *,
                    before_path: str = "<before>", after_path: str = "<after>") -> PythonAstDiff:
    """Compare by lexical name. Missing files have an empty AST.

    Spans do not affect equality. Repeated definitions with one name are
    compared in source order. Nested local functions belong to the outer
    function body, and conditional definitions remain in the containing statement.
    """
    old = ast.parse(before if before is not None else b"", filename=before_path, type_comments=True)
    new = ast.parse(after if after is not None else b"", filename=after_path, type_comments=True)
    left: dict[str, list[_Definition]] = defaultdict(list)
    right: dict[str, list[_Definition]] = defaultdict(list)
    _definitions(old.body, "", left)
    _definitions(new.body, "", right)
    old_rest = _globals(_split_docstring(old.body)[1], left)
    new_rest = _globals(_split_docstring(new.body)[1], right)
    edits = []
    for name in sorted(left.keys() | right.keys()):
        previous = left.get(name, [])
        current = right.get(name, [])
        old_spans = tuple(item.span for item in previous)
        new_spans = tuple(item.span for item in current)
        if not previous:
            edits.append(SymbolEdit(name, "ADDED", (), new_spans))
        elif not current:
            edits.append(SymbolEdit(name, "REMOVED", old_spans, ()))
        else:
            parts: list[Literal["declaration", "body", "docstring"]] = []
            if [item.declaration for item in previous] != [item.declaration for item in current]:
                parts.append("declaration")
            if ([item.body for item in previous] != [item.body for item in current]
                    or any(_order_changed(a.class_order, b.class_order) for a, b in zip(previous, current, strict=True))):
                parts.append("body")
            elif [item.docstring for item in previous] != [item.docstring for item in current]:
                parts.append("docstring")
            if parts:
                edits.append(SymbolEdit(name, "MODIFIED", old_spans, new_spans, tuple(parts)))
    module_changed = (
        _statements(old_rest) != _statements(new_rest)
        # Order keeps the global assignments: moving one across code changes execution order.
        or _order_changed(_order(_split_docstring(old.body)[1]), _order(_split_docstring(new.body)[1]))
        or [item.tag for item in old.type_ignores] != [item.tag for item in new.type_ignores]
    )
    return PythonAstDiff(tuple(edits), module_changed)


def _python_version(version: FileVersion | None) -> FileVersion | None:
    return version if version and stat.S_ISREG(version.mode) and version.path.endswith(".py") else None


def _python_files(repo_root: str | Path, commit: CommitChange
                  ) -> list[tuple[FileVersion | None, FileVersion | None, bytes | None, bytes | None]]:
    from dulwich.objects import Blob, ObjectID
    from dulwich.repo import Repo

    def read(repo: Repo, version: FileVersion | None) -> bytes | None:
        if version is None:
            return None
        try:
            blob = repo.get_object(ObjectID(version.object_id.encode("ascii")))
        except KeyError as exc:
            raise ValueError(f"Git blob missing for {version.path}") from exc
        if not isinstance(blob, Blob):
            raise TypeError(f"Git object for {version.path} is not a blob")
        return blob.data

    files = []
    with Repo(str(Path(repo_root).resolve(strict=True))) as repo:
        for change in commit.files:
            before = _python_version(change.before)
            after = _python_version(change.after)
            if before is not None or after is not None:
                files.append((before, after, read(repo, before), read(repo, after)))
    return files


def read_python_blobs(repo_root: str | Path, commit: CommitChange) -> dict[str, tuple[bytes | None, bytes | None]]:
    """Before/after bytes of each regular .py file the commit changes.

    Args:
        repo_root: Local Git repository.
        commit: L4-1 commit record.

    Returns:
        Map keyed by the after path (the before path for removals).
    """
    result: dict[str, tuple[bytes | None, bytes | None]] = {}
    for before, after, old, new in _python_files(repo_root, commit):
        version = after or before
        assert version is not None
        result[version.path] = (old, new)
    return result


def diff_python_commit(repo_root: str | Path, commit: CommitChange) -> tuple[PythonFileDiff, ...]:
    """Diff regular .py blobs from an L4-1 commit record without using the worktree.

    A file that does not parse on either side is returned with ``parse_error`` and no edits;
    the other files of the commit still diff.
    """
    results = []
    for before, after, old, new in _python_files(repo_root, commit):
        try:
            diff = diff_python_ast(old, new, before_path=before.path if before else "<absent>",
                                   after_path=after.path if after else "<absent>")
            results.append(PythonFileDiff(before, after, diff))
        except (SyntaxError, ValueError) as error:
            side: Literal["before", "after"] = "after"
            try:
                ast.parse(old if old is not None else b"")
            except (SyntaxError, ValueError):
                side = "before"
            results.append(PythonFileDiff(before, after, PythonAstDiff((), False),
                                          ParseError(side, f"{type(error).__name__}: {error}")))
    return tuple(results)
