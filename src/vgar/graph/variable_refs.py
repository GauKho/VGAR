"""Reads and writes of module globals and ``self``/``cls`` attributes per function (spec 2026-11-15 §2).

Globals come from ``symtable`` (so a parameter or local of the same name shadows the global); names a
module imports with ``from m import X`` are marked ``imported`` for the builder to resolve. Fields are
``<first parameter>.<name>`` inside a method of a class. Nested functions, lambdas and comprehensions
belong to their outer function. Aliasing (``x = self; x.a``) and inherited fields are out of scope.
"""
from __future__ import annotations

import ast
import symtable
from dataclasses import dataclass
from typing import Literal

_ANONYMOUS = {"lambda", "listcomp", "setcomp", "dictcomp", "genexpr"}


@dataclass(frozen=True)
class VariableAccess:
    function: str  # qualified name inside the module ("Class.method"); nested scopes give the outer one
    kind: Literal["global", "field", "imported"]
    owner: str  # "" for globals and imported names; class qualified name for fields
    name: str
    access: Literal["read", "write", "read_write"]


def _merge(found: dict[tuple[str, str, str, str], set[str]], key: tuple[str, str, str, str], access: str) -> None:
    found.setdefault(key, set()).add(access)


def _kind(table: symtable.SymbolTable) -> str:
    return str(table.get_type()).lower()


def _globals_in(table: symtable.SymbolTable, function: str, imported: set[str],
                found: dict[tuple[str, str, str, str], set[str]]) -> None:
    for symbol in table.get_symbols():
        if not symbol.is_global():
            continue
        name = symbol.get_name()
        kind = "imported" if name in imported else "global"
        if symbol.is_referenced():
            _merge(found, (function, kind, "", name), "read")
        if symbol.is_declared_global() and symbol.is_assigned():
            _merge(found, (function, kind, "", name), "write")
    for child in table.get_children():
        _globals_in(child, function, imported, found)


def _walk_tables(table: symtable.SymbolTable, prefix: str, imported: set[str],
                 found: dict[tuple[str, str, str, str], set[str]]) -> None:
    for child in table.get_children():
        name, kind = child.get_name(), _kind(child)
        if "class" in kind:
            _walk_tables(child, f"{prefix}{name}.", imported, found)
        elif "function" in kind and name not in _ANONYMOUS:
            _globals_in(child, f"{prefix}{name}", imported, found)


def _fields(body: list[ast.stmt], prefix: str, found: dict[tuple[str, str, str, str], set[str]]) -> None:
    for node in body:
        if isinstance(node, ast.ClassDef):
            owner = f"{prefix}{node.name}"
            for item in node.body:
                static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in getattr(item, "decorator_list", []))
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.args.args and not static:
                    receiver = item.args.args[0].arg
                    function = f"{owner}.{item.name}"
                    augmented = {id(n.target) for n in ast.walk(item) if isinstance(n, ast.AugAssign)}
                    for sub in ast.walk(item):
                        if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                                and sub.value.id == receiver):
                            if id(sub) in augmented:
                                access = "read_write"
                            elif isinstance(sub.ctx, ast.Store):
                                access = "write"
                            elif isinstance(sub.ctx, ast.Load):
                                access = "read"
                            else:
                                continue
                            _merge(found, (function, "field", owner, sub.attr), access)
            _fields(node.body, f"{owner}.", found)


def variable_accesses(source: bytes, filename: str = "<module>") -> list[VariableAccess]:
    """Every (function, variable) pair with its merged access; empty when the source does not parse.

    Args:
        source: Module source bytes.
        filename: Name used in parse errors.
    """
    try:
        text = source.decode("utf-8")
        tree = ast.parse(text, filename=filename)
        top = symtable.symtable(text, filename, "exec")
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return []
    imported = {alias.asname or alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                for alias in node.names if alias.name != "*"}
    found: dict[tuple[str, str, str, str], set[str]] = {}
    _walk_tables(top, "", imported, found)
    _fields(tree.body, "", found)
    out = []
    for (function, kind, owner, name), accesses in sorted(found.items()):
        access = "read_write" if "read_write" in accesses or accesses == {"read", "write"} else next(iter(accesses))
        out.append(VariableAccess(function, kind, owner, name, access))  # type: ignore[arg-type]
    return out
