"""T2 tools (spec 2026-11-19 §8): file tools for every arm, and the graph server's tools over MCP SDK 2.2 stdio.

Every tool returns a ``ToolResult``: the text the model sees (capped) and the code spans it showed, so the
harness knows which code the model has read.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import re
import sqlite3
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from vgar.contracts.prompt_context import render_context_for_repair

ROOT = Path(__file__).resolve().parents[2]
MAX_GREP_MATCHES, MAX_READ_LINES, MAX_LIST_ENTRIES = 50, 200, 200


@dataclass
class ToolResult:
    text: str
    spans: list[tuple[str, int, int]] = field(default_factory=list)
    raw: Any = None   # the server's full answer (graph tools), kept for the log only


def cap_tokens(text: str, limit: int = 1500) -> str:
    """Cut ``text`` to ``limit`` tokens counted as UTF-8 bytes / 4, marking the cut."""
    data = text.encode("utf-8")
    if len(data) <= limit * 4:
        return text
    return data[: limit * 4].decode("utf-8", errors="ignore") + "\n[truncated]"


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties,
                                                            "required": required}}}


def _grep_scan(tree: str, pattern: str, glob: str) -> tuple[str, list[tuple[str, int, int]]]:
    """The grep itself; runs in a child process so a pathological pattern can be stopped."""
    root, regex = Path(tree), re.compile(pattern)
    lines, spans = [], []
    for path in sorted(root.glob(glob)):
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:   # a glob such as "../**" reaching outside the tree
            continue
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if regex.search(line):
                lines.append(f"{relative}:{number}: {line.strip()[:200]}")
                spans.append((relative, number, number))
                if len(lines) >= MAX_GREP_MATCHES:
                    return "\n".join(lines + ["[more matches not shown]"]), spans
    return "\n".join(lines) or "no match", spans


class FileTools:
    """grep / read_file / list_dir inside one task tree; paths outside the tree are refused."""

    def __init__(self, tree: Path, grep_timeout: float = 30) -> None:
        self.tree = Path(tree).resolve()
        self.grep_timeout = grep_timeout
        self._pool: Any = None

    def _inside(self, path: str) -> Path | None:
        target = (self.tree / path).resolve()
        return target if target == self.tree or target.is_relative_to(self.tree) else None

    def grep(self, pattern: str, glob: str = "**/*.py") -> ToolResult:
        try:
            re.compile(pattern)
        except re.error as error:
            return ToolResult(f"bad pattern: {error}")
        if self._pool is None:   # Python's re cannot be interrupted, so the scan runs where it can be killed
            self._pool = multiprocessing.get_context("spawn").Pool(1)
        pending = self._pool.apply_async(_grep_scan, (str(self.tree), pattern, glob))
        try:
            text, spans = pending.get(timeout=self.grep_timeout)
        except multiprocessing.TimeoutError:
            self._pool.terminate()
            self._pool = None
            return ToolResult(f"grep timed out after {self.grep_timeout:g} s; use a simpler pattern")
        return ToolResult(text, [tuple(span) for span in spans])

    def close(self) -> None:
        if self._pool is not None:
            self._pool.terminate()
            self._pool = None

    def read_file(self, path: str, start: int = 1, end: int | None = None) -> ToolResult:
        target = self._inside(path)
        if target is None or not target.is_file():
            return ToolResult(f"refused: {path} is not a file inside the repository")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start))
        end = min(len(lines), int(end) if end else len(lines), start + MAX_READ_LINES - 1)
        if start > end:
            return ToolResult(f"{path} has {len(lines)} lines")
        relative = target.relative_to(self.tree).as_posix()
        body = "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))
        return ToolResult(body, [(relative, start, end)])

    def list_dir(self, path: str = ".") -> ToolResult:
        target = self._inside(path)
        if target is None or not target.is_dir():
            return ToolResult(f"refused: {path} is not a directory inside the repository")
        entries = sorted(f"{child.name}/" if child.is_dir() else child.name for child in target.iterdir())
        return ToolResult("\n".join(entries[:MAX_LIST_ENTRIES]) or "(empty)")

    def schemas(self) -> list[dict[str, Any]]:
        return [
            _function("grep", "Search the repository's Python files with a regular expression.",
                      {"pattern": {"type": "string"}, "glob": {"type": "string", "default": "**/*.py"}}, ["pattern"]),
            _function("read_file", "Read lines of a repository file (at most 200 lines per call).",
                      {"path": {"type": "string"}, "start": {"type": "integer", "default": 1},
                       "end": {"type": "integer"}}, ["path"]),
            _function("list_dir", "List a repository directory.", {"path": {"type": "string", "default": "."}}, []),
        ]


def _spans(payload: Any) -> list[tuple[str, int, int]]:
    """Code ranges in a graph tool result: every object with a ``path`` and a ``range`` of lines."""
    found = []
    if isinstance(payload, dict):
        span = payload.get("range")
        if isinstance(payload.get("path"), str) and isinstance(span, dict) and "start_line" in span:
            found.append((payload["path"], int(span["start_line"]), int(span.get("end_line", span["start_line"]))))
        for value in payload.values():
            found += _spans(value)
    elif isinstance(payload, list):
        for value in payload:
            found += _spans(value)
    return found


_EDGE_SQL = """
    SELECT MAX(calls.confidence), calls.resolution, calls.provenance_json FROM edges AS calls
    JOIN edges AS holds ON holds.target_id = calls.source_id AND holds.graph_version = calls.graph_version
    WHERE calls.graph_version = ? AND calls.type = 'CALLS' AND holds.type = 'CONTAINS'
      AND holds.source_id = ? AND calls.target_id = ?"""


def edge_evidence(db: Path, graph_version: str, caller: str, callee: str) -> dict[str, Any] | None:
    """Confidence and provenance of ``caller -CONTAINS-> callsite -CALLS-> callee`` (best call site), read-only."""
    with sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True) as connection:
        confidence, resolution, provenance = connection.execute(_EDGE_SQL, (graph_version, caller, callee)).fetchone()
    if confidence is None:
        return None
    source = json.loads(provenance or "{}")
    return {"edge_confidence": confidence, "edge_resolution": resolution, "edge_source_tool": source.get("source_tool"),
            "edge_rule": source.get("rule_id")}


MAX_ANCHORS_SHOWN = 15
CONTEXT_RESULT_TOKENS = 2000   # 1000 tokens of code + ~50 tokens per item header (path, node id, lines)


def _present(name: str, payload: Any) -> str:
    """What the model reads. The server answers in JSON built for programs: each token of code costs about 3.6 tokens
    of escaping and per-item fields, and anchors come with ~7k tokens of overlay edges. Context is shown with the
    repository's own text renderer and anchors as a short list, so a capped result still carries the code."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and name == "get_related_context" and isinstance(data.get("context"), dict):
        return render_context_for_repair(data["context"])
    if isinstance(data, dict) and name == "find_task_anchors" and isinstance(data.get("anchors"), list):
        anchors = sorted(data["anchors"], key=lambda anchor: -float(anchor.get("score") or 0))
        return json.dumps({"status": payload.get("status"), "anchor_count": len(anchors), "anchors": [
            {"node_id": a.get("node_id"), "path": a.get("path"), "symbol": a.get("symbol"), "score": a.get("score"),
             "evidence": sorted({e.get("kind") for e in a.get("evidence", []) if isinstance(e, dict)} - {None})}
            for a in anchors[:MAX_ANCHORS_SHOWN]]}, ensure_ascii=False)
    return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)


class GraphTools:
    """The graph server's tools for one task; ``graph_version`` and ``task_id`` are filled in by the harness.

    ``with_confidence`` (arm ``graph_conf``, a harness-side trial of a server change): callers/callees also carry the
    confidence and provenance of their CALLS edge, most confident first.
    """

    TOOLS = ("search_symbols", "find_task_anchors", "get_related_context", "get_callers", "get_callees",
             "explain_dependency_path")
    BOUND = ("graph_version", "task_id")

    def __init__(self, tree: Path, db: Path, graph_version: str, task_id: str, audit_log: Path,
                 context_budget: int = 1000, with_confidence: bool = False, timeout_seconds: float = 300) -> None:
        self.tree, self.db, self.audit_log = Path(tree).resolve(), Path(db).resolve(), Path(audit_log).resolve()
        self.bound = {"graph_version": graph_version, "task_id": task_id}
        self.context_budget = context_budget
        self.with_confidence = with_confidence
        self.timeout_seconds = timeout_seconds
        self.unavailable: str | None = None
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._tools: dict[str, Any] = {}

    async def __aenter__(self) -> Self:
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), VGAR_REPOSITORY_ROOT=str(self.tree),
                   VGAR_GRAPH_DATABASE=str(self.db), VGAR_MCP_AUDIT_LOG=str(self.audit_log))
        env.pop("VGAR_GRAPH_VERSION", None)
        params = StdioServerParameters(command=sys.executable, args=["-m", "vgar.mcp.servers.graph_server"], env=env,
                                       cwd=str(self.tree))   # not the repo root: its .env must not reach the server
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        listed = await self._session.list_tools()
        self._tools = {tool.name: tool for tool in listed.tools if tool.name in self.TOOLS}
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._stack is not None:
            await self._stack.aclose()

    def schemas(self) -> list[dict[str, Any]]:
        out = []
        for name in self.TOOLS:
            schema = dict(self._tools[name].input_schema)
            properties = {k: v for k, v in schema.get("properties", {}).items() if k not in self.BOUND}
            required = [k for k in schema.get("required", []) if k not in self.BOUND]
            out.append(_function(name, self._tools[name].description or "", properties, required))
        return out

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(f"unknown tool {name!r}")
        if self.unavailable:   # a call timed out: the server may still be busy, so do not queue more work on it
            return ToolResult(f"graph tools unavailable for this task: {self.unavailable}")
        arguments = dict(arguments)
        accepted = self._tools[name].input_schema.get("properties", {})
        arguments.update({key: value for key, value in self.bound.items() if key in accepted})
        if name == "get_related_context":
            arguments.setdefault("budget_tokens", self.context_budget)
        try:
            result = await self._session.call_tool(name, arguments, read_timeout_seconds=self.timeout_seconds)
        except Exception as error:  # noqa: BLE001 -- reported to the model; the task goes on with file tools
            self.unavailable = f"{name} timed out after {self.timeout_seconds:g} s ({type(error).__name__})"
            return ToolResult(f"error: {self.unavailable}")
        payload = result.structured_content
        if isinstance(payload, dict) and "data" in payload:   # server envelope: keep the answer, drop metadata
            payload = {key: payload[key] for key in ("status", "data", "error") if key in payload}
        if payload is None:
            payload = "\n".join(getattr(item, "text", "") for item in result.content)
        if self.with_confidence and name in ("get_callers", "get_callees") and isinstance(payload, dict):
            self._add_confidence(payload.get("data") or {}, name, arguments.get("symbol_id"))
        text = _present(name, payload)
        limit = CONTEXT_RESULT_TOKENS if name == "get_related_context" else 1500
        return ToolResult(cap_tokens(("error: " if result.is_error else "") + text, limit), _spans(payload),
                          raw=result.structured_content)

    def _add_confidence(self, data: dict[str, Any], name: str, symbol_id: str | None) -> None:
        key = "callers" if name == "get_callers" else "callees"
        items = data.get(key)
        if not isinstance(items, list) or not symbol_id:
            return
        for item in items:
            pair = (item["symbol_id"], symbol_id) if key == "callers" else (symbol_id, item["symbol_id"])
            item.update(edge_evidence(self.db, self.bound["graph_version"], *pair) or {"edge_confidence": None})
        items.sort(key=lambda item: -(item["edge_confidence"] or 0.0))
