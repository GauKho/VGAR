"""Cross-check GlobalVariable/Field from compare.py's report.json against Python's ast.

Usage: python spikes/tree_sitter_graph/ast_check.py <repo> <out>/report.json

Same definitions as python.tsg:
- GlobalVariable: module-level Assign (outermost target only) / AnnAssign whose target is a Name;
- Field: AnnAssign with a Name target directly in a class body, or `self.x = ...` / `self.x: T = ...`
  inside a method of that class (not inside nested defs, classes or lambdas).
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def first_target(stmt: ast.stmt) -> ast.expr | None:
    if isinstance(stmt, ast.Assign):
        return stmt.targets[0]
    if isinstance(stmt, ast.AnnAssign):
        return stmt.target
    return None


def self_fields(node: ast.AST, rel: str, out: set) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        target = first_target(child) if isinstance(child, ast.stmt) else None
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
            out.add((rel, target.attr, child.lineno))
        self_fields(child, rel, out)


def main() -> None:
    repo = Path(sys.argv[1])
    report = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    globals_, fields = set(), set()
    for file in sorted(repo.rglob("*.py")):
        if ".git" in file.parts:
            continue
        rel = file.relative_to(repo).as_posix()
        module = ast.parse(file.read_bytes())
        for stmt in module.body:
            target = first_target(stmt)
            if isinstance(target, ast.Name):
                globals_.add((rel, target.id, stmt.lineno))
        for cls in (n for n in ast.walk(module) if isinstance(n, ast.ClassDef)):
            for stmt in cls.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.add((rel, stmt.target.id, stmt.lineno))
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self_fields(stmt, rel, fields)
    for label, expected in (("GlobalVariable", globals_), ("Field", fields)):
        got = {tuple(x[1:]) for x in report[label]}
        print(f"{label}: ast={len(expected)} tsg={len(got)} match={len(expected & got)} "
              f"only_ast={sorted(expected - got)[:6]} only_tsg={sorted(got - expected)[:6]}")


if __name__ == "__main__":
    main()
