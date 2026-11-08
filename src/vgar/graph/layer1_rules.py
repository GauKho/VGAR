"""Layer 1 facts computed from the builder's own data (plan task L1-3; spec 2026-11-08 §4.3-4.5).

Pure rules over decorator/base strings and import records; ``PythonGraphBuilder._derive_layer1_facts``
applies them to the graph. Nothing here imports or executes repository code.
"""
from __future__ import annotations

import ast
from typing import Any, NamedTuple

from vgar.graph.grounding import _static_route


class RouteSpec(NamedTuple):
    name: str
    methods: list[str]
    route_path: str
    decorator: str
    receiver: str


def route_specs(decorators: list[str]) -> list[RouteSpec]:
    """Routes declared by a handler's literal decorators, one per distinct ``"{METHODS} {path}"`` name."""
    specs: dict[str, RouteSpec] = {}
    for decorator in decorators:
        route = _static_route(decorator)
        if route is None:
            continue
        path, methods = route
        name = f"{','.join(sorted(methods))} {path}"
        if name not in specs:
            # _static_route only accepts a Call on an Attribute, so this parse cannot fail.
            receiver = ast.unparse(ast.parse(decorator.lstrip("@").strip(), mode="eval").body.func.value)
            specs[name] = RouteSpec(name, sorted(methods), path, decorator, receiver)
    return list(specs.values())


def import_table(imports: list[dict[str, Any]]) -> dict[str, str]:
    """Local name -> dotted origin, from the ``properties`` of one module's Import nodes.

    ``from dataclasses import dataclass as dc`` gives ``dc -> dataclasses.dataclass``;
    ``import typing as t`` gives ``t -> typing``; ``import os.path`` binds ``os -> os``.
    """
    table: dict[str, str] = {}
    for item in imports:
        module, name, alias = item["imported_module"], item["imported_name"], item["alias"]
        if name is None:
            table[alias or module.split(".", 1)[0]] = module if alias else module.split(".", 1)[0]
        elif name != "*":
            table[alias or name] = f"{module}.{name}"
    return table


def resolve(expression: str, table: dict[str, str]) -> str | None:
    """Dotted origin of a decorator/base expression, or None when its first name is not imported.

    Drops a leading ``@``, call arguments ``(...)``, type parameters ``[...]`` (``Protocol[T]``) and a
    ``metaclass=`` prefix.
    """
    text = expression.strip().lstrip("@").split("(", 1)[0].split("[", 1)[0].strip()
    text = text.removeprefix("metaclass=").strip()
    head, _, rest = text.partition(".")
    origin = table.get(head)
    if origin is None:
        return None
    return f"{origin}.{rest}" if rest else origin


_SCHEMA_DECORATORS = {"dataclasses.dataclass": "dataclass"}
_SCHEMA_BASES = {"pydantic.BaseModel": "pydantic", "typing.TypedDict": "typed_dict",
                 "typing_extensions.TypedDict": "typed_dict"}


def schema_kind(decorators: list[str], bases: list[str], table: dict[str, str]) -> tuple[str, str] | None:
    """(schema_kind, evidence) for spec §4.4 cases (a) decorator and (b)/(c) base; None otherwise."""
    for decorator in decorators:
        kind = _SCHEMA_DECORATORS.get(resolve(decorator, table) or "")
        if kind:
            return kind, "decorator"
    for base in bases:
        kind = _SCHEMA_BASES.get(resolve(base, table) or "")
        if kind:
            return kind, "base"
    return None


_INTERFACE_BASES = {"abc.ABC": "abc", "abc.ABCMeta": "abc", "typing.Protocol": "protocol",
                    "typing_extensions.Protocol": "protocol"}


def interface_kind(bases: list[str], table: dict[str, str]) -> str | None:
    """"abc" or "protocol" when a class is an interface by its own bases (spec §4.5), else None."""
    for base in bases:
        kind = _INTERFACE_BASES.get(resolve(base, table) or "")
        if kind:
            return kind
    return None


_ENV_ORIGINS = {"getenv": "os.getenv", "environ_get": "os.environ.get", "environ_subscript": "os.environ"}


def env_read(access: str, callee: str, table: dict[str, str]) -> bool:
    """True when ``callee`` (``o.getenv``, ``environ``, ...) resolves through the imports to os (spec §4.2)."""
    return resolve(callee, table) == _ENV_ORIGINS[access]
