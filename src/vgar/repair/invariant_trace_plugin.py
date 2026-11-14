"""L5-1: record entry, exit and exceptional exit of workspace functions while pytest runs.

Enabled with ``-p vgar.repair.invariant_trace_plugin --vgar-trace-dir=<absolute folder outside the
workspace>``. Writes ``trace.jsonl`` (one record per line) and ``trace_meta.json``. Traced: code files
under the pytest working directory that are not test files (the graph builder's rule) and not generated
(``<string>``). Values are flattened to primitives (objects give ``x.field`` one level deep and a stable
id, containers give ``x.__len__``). At most 1,000 calls per program point and 50 MB per run are kept;
``truncated`` in the meta file says when a limit was hit. Standard library only: the plugin runs in the
interpreter of the code under test.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import zlib
from pathlib import Path

MAX_CALLS_PER_POINT = 1000
MAX_BYTES = 50 * 1024 * 1024
_CONTAINERS = (list, tuple, set, frozenset, dict)


def pytest_addoption(parser):
    parser.addoption("--vgar-trace-dir", default=None, help="folder for the L5-1 invariant trace")


def _primitive(value) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _fields(value) -> dict:
    if dataclasses.is_dataclass(value):
        names = [field.name for field in dataclasses.fields(value)]
    else:
        try:
            names = list(object.__getattribute__(value, "__dict__"))
        except Exception:  # noqa: BLE001 - no instance dict, or a hostile __getattribute__
            names = []
        for cls in type(value).__mro__:
            slots = cls.__dict__.get("__slots__", ())
            names += [slots] if isinstance(slots, str) else list(slots)
    out = {}
    for name in dict.fromkeys(names):
        try:
            out[name] = getattr(value, name)
        except Exception:  # noqa: BLE001, S112 - a field that cannot be read is skipped (no logging inside traced code)
            continue
    return out


def _flatten(name: str, value, out: dict) -> None:
    if _primitive(value):
        out[name] = value
        return
    if isinstance(value, _CONTAINERS):
        try:
            out[f"{name}.__len__"] = len(value)
        except Exception:  # noqa: BLE001, S110 - never break the code under trace
            pass
        return
    fields = _fields(value)
    primitives = {}
    for field, item in fields.items():
        if _primitive(item):
            primitives[f"{name}.{field}"] = item
        elif isinstance(item, _CONTAINERS):
            try:
                primitives[f"{name}.{field}.__len__"] = len(item)
            except Exception:  # noqa: BLE001, S110 - never break the code under trace
                pass
    identity = json.dumps([type(value).__name__, sorted(primitives.items())], default=str)
    out[name] = {"__object__": type(value).__name__, "__id__": zlib.crc32(identity.encode("utf-8")) + 1}
    out.update(primitives)


def _flatten_safe(name: str, value, out: dict) -> None:
    """``_flatten`` that never raises into the code under trace (e.g. proxies whose attribute access raises)."""
    try:
        _flatten(name, value, out)
    except Exception:  # noqa: BLE001
        out[name] = {"__object__": "unreadable", "__id__": 1}


_ITERATION_END = (StopIteration, StopAsyncIteration, GeneratorExit)


def _is_test_path(path: str) -> bool:
    return Path(path).name.startswith("test_") or "/tests/" in f"/{path}"


class _Tracer:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.records: list[str] = []
        self.size = 0
        self.truncated = False
        self.calls: dict[str, int] = {}
        self.frames: dict[int, dict] = {}
        self.nonce = 0
        self.test = ""
        self._paths: dict[object, str | None] = {}

    def _path(self, code) -> str | None:
        if code not in self._paths:
            path = None
            if not code.co_filename.startswith("<") and not code.co_name.startswith("<"):
                try:
                    relative = Path(code.co_filename).resolve().relative_to(self.root).as_posix()
                    path = None if _is_test_path(relative) else relative
                except (ValueError, OSError):
                    path = None
            self._paths[code] = path
        return self._paths[code]

    def _emit(self, record: dict) -> None:
        if self.truncated and self.size >= MAX_BYTES:
            return
        line = json.dumps(record, default=str)
        if self.size + len(line) > MAX_BYTES:
            self.truncated = True
            self.size = MAX_BYTES
            return
        self.size += len(line) + 1
        self.records.append(line)

    def global_trace(self, frame, event, arg):
        if event != "call":
            return None
        try:
            return self._call(frame)
        except Exception:  # noqa: BLE001 - tracing must never break the test
            return None

    def _call(self, frame):
        code = frame.f_code
        path = self._path(code)
        if path is None:
            return None
        qualname = getattr(code, "co_qualname", code.co_name)
        names = code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]
        module = frame.f_globals.get("__name__", "")
        ppt = f"{module}.{qualname}({', '.join(names)})"
        count = self.calls.get(ppt, 0)
        if count >= MAX_CALLS_PER_POINT:
            self.truncated = True
            return None
        self.calls[ppt] = count + 1
        values: dict = {}
        for index, name in enumerate(names):
            _flatten_safe("this" if index == 0 and name == "self" else name, frame.f_locals.get(name), values)
        self.nonce += 1
        state = {"ppt": ppt, "path": path, "qualname": qualname, "nonce": self.nonce, "test": self.test,
                 "vars": values, "raised": None}
        self.frames[id(frame)] = state
        self._emit({**{k: state[k] for k in ("ppt", "path", "qualname", "nonce", "test", "vars")}, "kind": "enter"})
        return self.local_trace

    def local_trace(self, frame, event, arg):
        try:
            return self._local(frame, event, arg)
        except Exception:  # noqa: BLE001 - tracing must never break the test
            return None

    def _local(self, frame, event, arg):
        state = self.frames.get(id(frame))
        if state is None:
            return None
        if event == "exception":
            kind = arg[0] if arg and isinstance(arg[0], type) else Exception
            if not issubclass(kind, _ITERATION_END):  # a for loop ending is not a raise
                state["raised"] = kind.__name__
        elif event == "line":
            state["raised"] = None  # the exception was handled inside the function
        elif event == "return":
            self.frames.pop(id(frame), None)
            base = {k: state[k] for k in ("ppt", "path", "qualname", "nonce", "test")}
            if state["raised"] is not None and arg is None:
                self._emit({**base, "kind": "raise", "vars": state["vars"], "exception": state["raised"]})
            else:
                values = dict(state["vars"])
                _flatten_safe("return", arg, values)
                self._emit({**base, "kind": "exit", "vars": values})
        return self.local_trace


_TRACER: _Tracer | None = None


def pytest_configure(config):
    global _TRACER
    if config.getoption("--vgar-trace-dir"):
        _TRACER = _Tracer(Path.cwd())


def pytest_runtest_call(item):
    if _TRACER is not None:
        _TRACER.test = item.nodeid
        sys.settrace(_TRACER.global_trace)


def pytest_runtest_teardown(item):
    if _TRACER is not None:
        sys.settrace(None)
        _TRACER.frames.clear()


def pytest_sessionfinish(session):
    folder = session.config.getoption("--vgar-trace-dir")
    if _TRACER is None or not folder:
        return
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    (target / "trace.jsonl").write_text("".join(line + "\n" for line in _TRACER.records), encoding="utf-8")
    meta = {"records": len(_TRACER.records), "truncated": _TRACER.truncated, "python": sys.version.split()[0]}
    (target / "trace_meta.json").write_text(json.dumps(meta), encoding="utf-8")
