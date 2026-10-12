"""Bounded, snapshot-verified definition queries over LSP stdio.

Only declaration name tokens become graph targets. External, variable and union
bindings never become guessed CALLS edges. Source code is never executed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from vgar.graph.scip_profile import auxiliary_fingerprint, import_paths, runtime_fingerprint
from vgar.graph.scip_resolver import _kill, current_fingerprint
from vgar.observability.graph_trace import GraphTrace


@dataclass(frozen=True)
class LspConfig:
    command: tuple[str, ...] = ()
    output_directory: str | Path = "artifacts/m1/w5-w6/lsp"
    request_timeout: float = 5
    initialize_timeout: float = 10
    total_timeout: float = 30
    max_requests: int = 200
    max_document_bytes: int = 2 * 1024 * 1024
    import_roots: tuple[str, ...] = ("src", "lib")
    python_executable: str | Path | None = None
    strict: bool = False

    def __post_init__(self):
        for value in (self.request_timeout, self.initialize_timeout, self.total_timeout):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("LSP timeouts must be finite and positive")
        for value in (self.max_requests, self.max_document_bytes):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("LSP limits must be positive integers")
        if isinstance(self.command, str) or not all(isinstance(v, str) and v for v in self.command):
            raise ValueError("LSP command must be an argument list")


class _Rpc:
    """One outstanding client request; server requests are serviced while waiting."""
    MAX_MESSAGE = 16 * 1024 * 1024

    def __init__(self, command, root, stderr, settings, trace):
        self.settings, self.root, self.trace = settings, root, trace
        self.inbox = queue.Queue(maxsize=256)
        self.stopped = threading.Event()
        self.sequence = 0
        self.process = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=stderr, bufsize=0,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _enqueue(self, item):
        while not self.stopped.is_set():
            try:
                self.inbox.put(item, timeout=.1)
                return
            except queue.Full:
                pass

    def _read(self):
        try:
            stream = self.process.stdout
            while not self.stopped.is_set():
                headers = {}
                size = 0
                while True:
                    line = stream.readline(8193)
                    if not line:
                        raise EOFError("LSP server closed stdout")
                    size += len(line)
                    if size > 8192:
                        raise ValueError("LSP header exceeds limit")
                    if line == b"\r\n":
                        break
                    key, sep, value = line.decode("ascii").partition(":")
                    if not sep or key.lower() in headers:
                        raise ValueError("Invalid LSP header")
                    headers[key.lower()] = value.strip()
                length = int(headers.get("content-length", "-1"))
                if not 0 <= length <= self.MAX_MESSAGE:
                    raise ValueError("Invalid LSP content length")
                body = bytearray()
                while len(body) < length:
                    part = stream.read(length - len(body))
                    if not part:
                        raise EOFError("Truncated LSP response")
                    body.extend(part)
                message = json.loads(body)
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise ValueError("Invalid JSON-RPC response")
                # Diagnostics/progress/log notifications need no reply. They must
                # not fill the queue or write source text into graph debug logs.
                if "id" in message:
                    self._enqueue(message)
        except (OSError, ValueError, EOFError, UnicodeError) as error:
            self._enqueue(error)

    def send(self, message):
        body = json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=False).encode("utf-8")
        if len(body) > self.MAX_MESSAGE:
            raise ValueError("LSP outgoing message exceeds limit")
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.process.stdin.flush()

    def notify(self, method, params=None):
        self.send({"method": method, "params": params})

    def _server_request(self, message):
        method, params = message.get("method"), message.get("params") or {}
        if method == "workspace/configuration":
            result = []
            for item in params.get("items", []):
                value = self.settings
                for key in (item.get("section") or "").split("."):
                    if key:
                        value = value.get(key) if isinstance(value, dict) else None
                result.append(value)
        elif method == "workspace/workspaceFolders":
            result = [{"uri": self.root.as_uri(), "name": self.root.name}]
        elif method in {"client/registerCapability", "client/unregisterCapability", "window/workDoneProgress/create"}:
            result = None
        else:
            self.send({"id": message["id"], "error": {"code": -32601, "message": "Unsupported client method"}})
            return
        self.send({"id": message["id"], "result": result})

    def request(self, method, params, timeout):
        self.sequence += 1
        identifier = self.sequence
        self.send({"id": identifier, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.notify("$/cancelRequest", {"id": identifier})
                raise TimeoutError(f"LSP request timed out: {method}")
            try:
                message = self.inbox.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"LSP request timed out: {method}") from None
            if isinstance(message, Exception):
                raise RuntimeError(f"LSP transport failed: {type(message).__name__}") from message
            if "method" in message:
                self._server_request(message)
                continue
            if message.get("id") != identifier:
                continue
            if "error" in message:
                raise RuntimeError(f"LSP request failed: {method}, code={message['error'].get('code')}")
            if "result" not in message:
                raise ValueError("LSP response has no result")
            return message["result"]

    def close(self):
        if self.process.poll() is None:
            try:
                self.request("shutdown", None, 1)
                self.notify("exit")
                self.process.wait(timeout=1)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired):
                pass
        self.stopped.set()
        if self.process.poll() is None:
            _kill(self.process)
        self.reader.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()


def _byte_column(line, character):
    if isinstance(character, bool) or not isinstance(character, int) or character < 0:
        raise ValueError("Invalid LSP character")
    raw = line.encode("utf-16-le")
    if character * 2 > len(raw):
        raise ValueError("LSP position outside source")
    return len(raw[:character * 2].decode("utf-16-le").encode("utf-8"))


class DefinitionMapper:
    """Map only checked declaration/alias tokens, never the containing function."""
    def __init__(self, root, nodes, fingerprints):
        self.root, self.fingerprints = root, fingerprints
        self.sources, self.declarations = {}, {}
        for node in nodes:
            if node["type"] not in {"Function", "Method", "Class"}:
                continue
            lines = self.lines(node["path"])
            if lines is None:
                continue
            span = node["range"]
            header = lines[span["start_line"] - 1].encode("utf-8")[span["start_col"]:]
            match = re.match(rb"(?:async[ \t]+)?(?:def|class)[ \t]+([^\s(:]+)", header)
            if match and match.group(1) == node["name"].encode("utf-8"):
                key = (node["path"], span["start_line"] - 1, span["start_col"] + match.start(1),
                       span["start_col"] + match.end(1))
                self.declarations.setdefault(key, set()).add(node["id"])
            for alias in node["properties"].get("symbol_aliases", []):
                span = alias["range"]
                if (span["start_line"] == span["end_line"] and
                    lines[span["start_line"]-1].encode("utf-8")[span["start_col"]:span["end_col"]] == alias["name"].encode("utf-8")):
                    key = (node["path"], span["start_line"]-1, span["start_col"], span["end_col"])
                    self.declarations.setdefault(key, set()).add(node["id"])

    def lines(self, path):
        if path not in self.sources:
            target = (self.root / path).resolve()
            if not target.is_relative_to(self.root) or path not in self.fingerprints:
                return None
            data = target.read_bytes()
            if hashlib.sha256(data).hexdigest() != self.fingerprints[path]:
                raise ValueError("LSP source snapshot changed")
            try:
                self.sources[path] = data.decode("utf-8").split("\n")
            except UnicodeDecodeError:
                self.sources[path] = None
        return self.sources[path]

    def map(self, response):
        if response is None or response == []:
            return "no_definition", []
        locations = response if isinstance(response, list) else [response]
        targets, unsupported = set(), False
        for location in locations:
            uri = urlsplit(location.get("targetUri", location.get("uri", "")))
            if uri.scheme != "file" or uri.netloc not in {"", "localhost"} or uri.query or uri.fragment:
                unsupported = True
                continue
            # Pyright percent-encodes the drive colon on Windows. Decode once
            # before interpreting the file URI (url2pathname would decode twice).
            decoded = unquote(uri.path)
            if os.name == "nt":
                decoded = decoded.removeprefix("/") if re.match(r"^/[A-Za-z]:/", decoded) else decoded
            target = Path(decoded).resolve()
            if not target.is_relative_to(self.root):
                unsupported = True
                continue
            path = target.relative_to(self.root).as_posix()
            if path not in self.fingerprints:
                unsupported = True
                continue
            lines = self.lines(path)
            if lines is None:
                unsupported = True
                continue
            span = location.get("targetSelectionRange", location.get("range"))
            a, b = span["start"], span["end"]
            for point in (a, b):
                if (isinstance(point["line"], bool) or not isinstance(point["line"], int)
                    or not 0 <= point["line"] < len(lines)):
                    raise ValueError("LSP range outside source")
            start, end = _byte_column(lines[a["line"]], a["character"]), _byte_column(lines[b["line"]], b["character"])
            found = self.declarations.get((path, a["line"], start, end), set()) if a["line"] == b["line"] else set()
            if not found:
                unsupported = True
            targets.update(found)
        if unsupported:
            return "external_or_non_callable", []
        return ("resolved", sorted(targets)) if len(targets) == 1 else ("ambiguous", sorted(targets))


def resolve_lsp_calls(root, nodes, calls, config, trace):
    """Query eligible call sites once; return immutable snapshot results/report."""
    started = time.monotonic()
    before, inputs = current_fingerprint(root), auxiliary_fingerprint(root)
    report = {"requested": "lsp", "active": "static", "status": "fallback", "reason": "",
              "eligible_call_count": len(calls), "request_count": 0, "resolved_count": 0,
              "request_limit": config.max_requests, "total_timeout": config.total_timeout,
              "call_binding_statuses": {}}
    results, rpc = {}, None
    try:
        if not calls:
            report.update(status="not_needed", reason="No unresolved or weak static call bindings")
        else:
            if not config.command:
                raise FileNotFoundError("Configure a Pyright language-server command")
            interpreter = Path(config.python_executable or sys.executable).resolve()
            if not interpreter.is_file():
                raise FileNotFoundError("LSP Python interpreter does not exist")
            extras = import_paths(root, config.import_roots)
            settings = {"python": {"pythonPath": str(interpreter), "analysis": {
                "extraPaths": [str(root / p) for p in extras], "diagnosticMode": "openFilesOnly",
                "typeCheckingMode": "off", "autoImportCompletions": False}}}
            report["runtime_inputs"] = runtime_fingerprint(config.command)
            report["settings"] = settings
            directory = Path(config.output_directory).resolve() / uuid.uuid4().hex
            directory.mkdir(parents=True)
            report["log_directory"] = str(directory)
            trace.emit("lsp_start", eligible_call_count=len(calls), request_limit=config.max_requests)
            mapper = DefinitionMapper(root, nodes, before)
            opened = set()
            deadline = started + config.total_timeout
            with (directory / "stderr.log").open("wb") as stderr:
                try:
                    rpc = _Rpc(config.command, root, stderr, settings, trace)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("LSP total time budget exhausted")
                    initialized = rpc.request("initialize", {"processId": os.getpid(),
                        "rootUri": root.as_uri(), "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
                        "capabilities": {"general": {"positionEncodings": ["utf-16"]},
                            "workspace": {"configuration": True, "workspaceFolders": True},
                            "textDocument": {"definition": {"linkSupport": True}}}},
                        min(config.initialize_timeout, remaining))
                    capabilities = initialized.get("capabilities", {})
                    if not capabilities.get("definitionProvider"):
                        raise ValueError("LSP server has no definition provider")
                    if capabilities.get("positionEncoding", "utf-16") != "utf-16":
                        raise ValueError("LSP server selected unsupported position encoding")
                    package_info = {"name": "unknown", "version": "unknown"}
                    for argument in config.command:
                        entry = Path(argument)
                        if entry.name == "langserver.index.js" and (entry.parent / "package.json").is_file():
                            package = json.loads((entry.parent / "package.json").read_text(encoding="utf-8"))
                            package_info = {"name": package["name"], "version": package["version"]}
                    report["server_info"] = initialized.get("serverInfo", package_info)
                    rpc.notify("initialized", {})
                    rpc.notify("workspace/didChangeConfiguration", {"settings": settings})
                    report.update(active="lsp", status="ready")
                    trace.emit("lsp_ready", server_info=report["server_info"])
                    for call in calls:
                        if report["request_count"] >= config.max_requests:
                            report.update(status="partial", reason="LSP request limit reached")
                            break
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            report.update(status="partial", reason="LSP total time budget exhausted")
                            break
                        lines = mapper.lines(call.path)
                        if lines is None:
                            results[call.node_id] = ("source_encoding_not_utf8", [])
                            continue
                        source = (root / call.path).read_bytes()
                        if len(source) > config.max_document_bytes:
                            results[call.node_id] = ("document_limit", [])
                            continue
                        uri = (root / call.path).as_uri()
                        if uri not in opened:
                            rpc.notify("textDocument/didOpen", {"textDocument": {"uri": uri,
                                "languageId": "python", "version": 1, "text": source.decode("utf-8")}})
                            opened.add(uri)
                        # Call record is the exclusive end of the callee token in
                        # UTF-8 bytes. LSP needs an interior UTF-16 position.
                        prefix = lines[call.line-1].encode("utf-8")[:call.column].decode("utf-8")
                        character = len(prefix[:-1].encode("utf-16-le")) // 2
                        report["request_count"] += 1
                        response = rpc.request("textDocument/definition", {"textDocument": {"uri": uri},
                            "position": {"line": call.line-1, "character": character}},
                            min(config.request_timeout, remaining))
                        status, targets = mapper.map(response)
                        results[call.node_id] = (status, targets)
                        trace.emit("lsp_call_result", node_id=call.node_id, path=call.path,
                                   status=status, target_ids=targets)
                finally:
                    if rpc is not None:
                        rpc.close()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError) as error:
        report.update(status="partial" if results else "fallback", reason=str(error), error_type=type(error).__name__)
        if not results:
            report["active"] = "static"
        trace.emit("lsp_fallback", reason=report["reason"], error_type=report["error_type"], retained_results=len(results))
        if config.strict:
            raise
    finally:
        if before != current_fingerprint(root) or inputs != auxiliary_fingerprint(root):
            raise ValueError("Repository sources/config/stubs changed during LSP resolution")
        statuses = report["call_binding_statuses"]
        for status, _ in results.values():
            statuses[status] = statuses.get(status, 0) + 1
        report["resolved_count"] = statuses.get("resolved", 0)
        report["unqueried_call_count"] = len(calls) - len(results)
        # Runtime/settings and actual answers identify semantic graph output.
        # Timing, log directory, PID and absolute source root never enter this digest.
        identity = {"results": sorted((k, v) for k, v in results.items()),
                    "status": report["status"], "error_type": report.get("error_type"),
                    "runtime_hashes": sorted(report.get("runtime_inputs", {}).values()),
                    "server_info": report.get("server_info"), "auxiliary_inputs": inputs,
                    "limits": [config.max_requests, config.max_document_bytes],
                    "import_roots": list(config.import_roots)}
        report["semantic_sha256"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        report["duration_ms"] = round((time.monotonic()-started)*1000, 2)
        trace.emit("lsp_complete", **report)
    # Preserve why each eligible site was skipped, while keeping query statistics
    # separate from fallback placeholders and including no fabricated target.
    skipped_reason = ("request_limit" if report["reason"] == "LSP request limit reached" else
                      "time_budget" if report["reason"] == "LSP total time budget exhausted" else "server_failure")
    for call in calls:
        results.setdefault(call.node_id, (skipped_reason, []))
    return results, report
