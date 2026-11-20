"""SPIKE (throwaway): pytest plugin that records entry/exit values of functions in one package.

Enable with ``-p tracer`` (this folder on PYTHONPATH) and the environment variables:
  INV_PACKAGE  package prefix to trace (e.g. ``shop``)
  INV_OUT      output folder; writes ``trace.jsonl`` (approach B) and ``trace.dtrace`` (approach A, Daikon)
Values are flattened to primitives: int, float, str, bool, None; objects give ``x.field`` (one level);
containers give ``x.__len__``. Exceptional exits are recorded as kind ``raise`` (not sent to Daikon).
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

PACKAGE = os.environ.get("INV_PACKAGE", "shop")
OUT = Path(os.environ.get("INV_OUT", "inv_out"))
RECORDS: list[dict] = []
_stack: dict[int, dict] = {}
_nonce = [0]


def _primitive(value):
    return value is None or isinstance(value, (bool, int, float, str))


def flatten(name: str, value, out: dict) -> None:
    if _primitive(value):
        out[name] = value
        return
    if isinstance(value, (list, tuple, set, dict, frozenset)):
        out[f"{name}.__len__"] = len(value)
        return
    out[name] = {"__object__": type(value).__name__, "__id__": id(value)}
    fields = ({f.name: getattr(value, f.name) for f in dataclasses.fields(value)} if dataclasses.is_dataclass(value)
              else dict(getattr(value, "__dict__", {})))
    for field, item in fields.items():
        if _primitive(item):
            out[f"{name}.{field}"] = item
        elif isinstance(item, (list, tuple, set, dict, frozenset)):
            out[f"{name}.{field}.__len__"] = len(item)


def _ppt(frame) -> str | None:
    module = frame.f_globals.get("__name__", "")
    code = frame.f_code
    if not module.startswith(PACKAGE) or code.co_name.startswith("<") or "site-packages" in code.co_filename:
        return None
    if not code.co_filename.replace("\\", "/").split("/")[-2:-1] or code.co_filename.startswith("<"):
        return None  # dataclass-generated methods live in "<string>"
    qualname = getattr(code, "co_qualname", code.co_name)
    args = code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]
    return f"{module}.{qualname}({', '.join(args)})"


def _arguments(frame) -> dict:
    code = frame.f_code
    out: dict = {}
    for index, arg in enumerate(code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]):
        name = "this" if index == 0 and arg == "self" else arg
        flatten(name, frame.f_locals.get(arg), out)
    return out


def _local(frame, event, arg):
    state = _stack.get(id(frame))
    if state is None:
        return None
    if event == "exception":
        state["raised"] = True
    elif event == "line":
        state["raised"] = False  # the exception was handled inside the function
    elif event == "return":
        _stack.pop(id(frame), None)
        if state["raised"] and arg is None:
            RECORDS.append({"ppt": state["ppt"], "kind": "raise", "nonce": state["nonce"], "vars": state["enter"]})
        else:
            values = dict(state["enter"])
            flatten("return", arg, values)
            RECORDS.append({"ppt": state["ppt"], "kind": "exit", "nonce": state["nonce"], "vars": values,
                            "test": state["test"]})
    return _local


CURRENT_TEST = [""]


def _global(frame, event, arg):
    if event != "call":
        return None
    ppt = _ppt(frame)
    if ppt is None:
        return None
    _nonce[0] += 1
    enter = _arguments(frame)
    _stack[id(frame)] = {"ppt": ppt, "nonce": _nonce[0], "enter": enter, "raised": False, "test": CURRENT_TEST[0]}
    RECORDS.append({"ppt": ppt, "kind": "enter", "nonce": _nonce[0], "vars": enter, "test": CURRENT_TEST[0]})
    return _local


def pytest_runtest_call(item):
    CURRENT_TEST[0] = item.nodeid
    sys.settrace(_global)


def pytest_runtest_teardown(item):
    sys.settrace(None)


# ---------------------------------------------------------------- Daikon output (approach A)
def _kind(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "java.lang.String"
    return "hashcode"


def _variable_types(records: list[dict]) -> dict[str, dict[str, str]]:
    """Per program point, one Daikon type per variable; variables with mixed types are dropped."""
    seen: dict[str, dict[str, set]] = {}
    for record in records:
        if record["kind"] == "raise":
            continue
        point = seen.setdefault(record["ppt"], {})
        for name, value in record["vars"].items():
            point.setdefault(name, set())
            kind = _kind(value)
            if kind:
                point[name].add(kind)
    types = {}
    for ppt, variables in seen.items():
        enter_vars = {k: v.pop() for k, v in variables.items() if len(v) == 1}
        types[ppt] = enter_vars
    return types


def _value(kind: str, value) -> tuple[str, int]:
    if value is None:
        return ("null", 1) if kind in ("java.lang.String", "hashcode") else ("nonsensical", 2)
    actual = _kind(value)
    if actual != kind and not (kind == "double" and actual == "int"):
        return "nonsensical", 2  # a variant gave another type than the base declared
    if kind == "boolean":
        return ("1" if value else "0"), 1
    if kind == "java.lang.String":
        return json.dumps(value), 1
    if kind == "hashcode":
        return str(value.get("__id__", 1) if isinstance(value, dict) else 1), 1
    return repr(value), 1


def daikon_name(name: str, names: set[str]) -> str:
    """Dotted names keep their dots only when the parent variable is declared too."""
    if "." in name and name.rsplit(".", 1)[0] in names and not name.endswith(".__len__"):
        return name
    return name.replace(".__len__", "_size").replace(".", "_")


def _declare(lines: list[str], name: str, kind: str, names: set[str]) -> None:
    shown = daikon_name(name, names)
    parent = name.rsplit(".", 1)[0] if shown == name and "." in name else None
    lines.append(f"variable {shown}")
    lines.append("  var-kind field " + name.rsplit(".", 1)[1] if parent else
                 ("  var-kind return" if name == "return" else "  var-kind variable"))
    if parent:
        lines.append(f"  enclosing-var {parent}")
    rep = "int" if kind == "boolean" else kind
    lines.append(f"  dec-type {kind if kind != 'hashcode' else 'java.lang.Object'}")
    lines.append(f"  rep-type {rep}")
    if name in ("this",):
        lines.append("  flags is_param")
    elif "." not in name and name != "return":
        lines.append("  flags is_param")


def daikon_types(records: list[dict]) -> tuple[dict, dict]:
    """Per program point, one Daikon type per variable (entry, exit); mixed-type variables are dropped."""
    enter_types: dict[str, dict[str, set]] = {}
    exit_types: dict[str, dict[str, set]] = {}
    for record in records:
        if record["kind"] == "raise":
            continue
        target = enter_types if record["kind"] == "enter" else exit_types
        point = target.setdefault(record["ppt"], {})
        for name, value in record["vars"].items():
            point.setdefault(name, set())
            if _kind(value):
                point[name].add(_kind(value))
    def single(types):
        out = {}
        for ppt, variables in types.items():
            kept = {k: next(iter(v)) for k, v in sorted(variables.items()) if len(v) == 1}
            # Daikon needs a declared parent for a dotted name; otherwise use a plain name.
            out[ppt] = {k: v for k, v in kept.items()}
        return out
    enter, exit_ = single(enter_types), single(exit_types)
    for ppt in exit_:  # an exit carries the same parameters as its entry
        exit_[ppt] = {k: v for k, v in exit_[ppt].items() if k == "return" or k.startswith("return.")
                      or enter.get(ppt, {}).get(k) == v}
    return enter, exit_


def write_daikon(records: list[dict], path: Path, types: tuple[dict, dict] | None = None) -> None:
    """Write one dtrace with declarations; ``types`` (from the base run) keeps declarations equal across variants."""
    enter, exit_ = types or daikon_types(records)
    lines = ["decl-version 2.0", "var-comparability none", ""]
    for ppt in sorted(enter):
        for suffix, types, ppt_type in ((":::ENTER", enter[ppt], "enter"), (":::EXIT1", exit_.get(ppt, {}), "subexit")):
            lines.append(f"ppt {ppt}{suffix}".replace(" ", "\\_").replace("ppt\\_", "ppt ", 1))
            lines.append(f"ppt-type {ppt_type}")
            for name, kind in types.items():
                _declare(lines, name, kind, set(types))
            lines.append("")
    for record in records:
        if record["kind"] == "raise" or record["ppt"] not in enter:
            continue
        types = enter[record["ppt"]] if record["kind"] == "enter" else exit_.get(record["ppt"], {})
        suffix = ":::ENTER" if record["kind"] == "enter" else ":::EXIT1"
        lines.append(f"{record['ppt']}{suffix}".replace(" ", "\\_"))
        lines.append("this_invocation_nonce")
        lines.append(str(record["nonce"]))
        for name, kind in types.items():
            text, modified = _value(kind, record["vars"].get(name))
            lines += [daikon_name(name, set(types)), text, str(modified)]
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pytest_sessionfinish(session):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "trace.jsonl").open("w", encoding="utf-8") as file:
        for record in RECORDS:
            file.write(json.dumps(record, default=str) + "\n")
    write_daikon(RECORDS, OUT / "trace.dtrace")
