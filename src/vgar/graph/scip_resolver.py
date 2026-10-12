"""Snapshot-bound SCIP enrichment with explicit, observable static fallback."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import re
import sys
import subprocess
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from vgar.graph.scip_wire import read_index
from vgar.graph.scip_profile import auxiliary_fingerprint, local_profile, runtime_fingerprint
from vgar.observability.graph_trace import GraphTrace


@dataclass(frozen=True)
class ScipConfig:
    # Explicit command prefix, e.g. (node, '-r', shim, scip_python_index_js).
    command: tuple[str, ...] = ()
    output_directory: str | Path = "artifacts/m1/w7-w8/scip"
    timeout_seconds: float = 120
    bundle: str | Path | None = None
    strict: bool = False
    max_index_bytes: int = 128 * 1024 * 1024
    environment_file: str | Path | None = None
    configure_imports: bool = True
    import_roots: tuple[str, ...] = ("src", "lib")
    target_only: str | None = None
    python_executable: str | Path | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("SCIP timeout must be finite and positive")
        if self.max_index_bytes <= 0:
            raise ValueError("SCIP index size limit must be positive")
        if not all(isinstance(item, str) and item for item in self.command):
            raise ValueError("SCIP command must be an argument list")


def source_fingerprint(root: Path, files: list[Path]) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def current_fingerprint(root: Path) -> dict[str, str]:
    # Import at call time to avoid the builder/resolver module dependency cycle.
    from vgar.graph.builder import discover_python_files
    return source_fingerprint(root, discover_python_files(root))


def _kill(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()
    process.wait()


def _normalize_index_root(index, root, target_only):
    """SCIP target-only indexes use a subset root and subset-relative paths."""
    indexed_root = index["root_uri"]
    if indexed_root.rstrip("/").casefold() == root.as_uri().rstrip("/").casefold():
        return indexed_root
    from vgar.graph.scip_profile import import_paths
    if not target_only or not import_paths(root, (target_only,)):
        raise ValueError("SCIP index belongs to another repository root")
    expected = (root / target_only).resolve().as_uri()
    if indexed_root.rstrip("/").casefold() != expected.rstrip("/").casefold():
        raise ValueError("SCIP index belongs to another repository root")
    for document in index["documents"]:
        path = document["path"].replace("\\", "/")
        posix = PurePosixPath(path)
        if (not path or posix.is_absolute() or PureWindowsPath(path).drive or
            ".." in posix.parts or posix.as_posix() != path):
            raise ValueError("Unsafe SCIP subset document path")
        document["path"] = f"{target_only}/{path}"
    index["root_uri"] = root.as_uri()
    return indexed_root


def prepare_scip(root: Path, files: list[Path], config: ScipConfig, trace: GraphTrace) -> tuple[dict | None, dict]:
    before = source_fingerprint(root, files)
    inputs_before = auxiliary_fingerprint(root)
    started = time.perf_counter()
    report = {"requested": "scip", "active": "static", "status": "fallback", "reason": ""}
    trace.emit("resolver_start", backend="scip", source_count=len(files))
    try:
        if config.bundle:
            manifest_path = Path(config.bundle).resolve()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            index_path = manifest_path.parent / "index.scip"
            if manifest["sources"] != before:
                raise ValueError("SCIP bundle source snapshot is stale")
            if manifest.get("auxiliary_inputs", {}) != inputs_before:
                raise ValueError("SCIP bundle config/stub snapshot is stale")
        else:
            if not config.command:
                raise FileNotFoundError("Configure a scip-python command or a verified bundle")
            interpreter = Path(config.python_executable or sys.executable).absolute()
            if not interpreter.is_file():
                raise FileNotFoundError("SCIP Python interpreter does not exist")
            if interpreter != Path(sys.executable).absolute() and config.environment_file is None:
                raise ValueError("A different SCIP Python interpreter requires its matching environment inventory")
            child_env = dict(os.environ)
            child_env["PATH"] = str(interpreter.parent) + os.pathsep + child_env.get("PATH", "")
            venv = interpreter.parent.parent
            if (venv / "pyvenv.cfg").is_file():
                child_env["VIRTUAL_ENV"] = str(venv)
            else:
                child_env.pop("VIRTUAL_ENV", None)
            report["python_executable"] = str(interpreter)
            directory = Path(config.output_directory).resolve() / uuid.uuid4().hex
            directory.mkdir(parents=True)
            report["log_directory"] = str(directory)
            manifest_path, index_path = directory / "manifest.json", directory / "index.scip"
            environment = Path(config.environment_file).resolve() if config.environment_file else directory / "environment.json"
            if config.environment_file is None:
                packages = [{"name": dist.metadata["Name"], "version": dist.version,
                             "files": [str(path).replace("\\", "/") for path in dist.files or []]}
                            for dist in importlib.metadata.distributions()]
                environment.write_text(json.dumps(packages), encoding="utf-8")
            command = [*config.command, "index", "--cwd", str(root), "--project-name", root.name,
                       "--project-version", "snapshot", "--output", str(index_path), "--environment", str(environment)]
            if config.target_only:
                from vgar.graph.scip_profile import import_paths
                if not import_paths(root, (config.target_only,)):
                    raise ValueError("SCIP target-only directory does not exist")
                command += ["--target-only", str(root / config.target_only)]
            report["target_only"] = config.target_only
            report["environment_sha256"] = hashlib.sha256(environment.read_bytes()).hexdigest()
            report["runtime_inputs"] = runtime_fingerprint(config.command)
            # Redirect logs to disk: minified JS errors can otherwise flood memory/stdout.
            with local_profile(root, enabled=config.configure_imports, roots=config.import_roots) as profile, \
                    (directory / "stdout.log").open("wb") as out, (directory / "stderr.log").open("wb") as err:
                report["profile"] = profile
                (directory / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
                trace.emit("resolver_profile", profile=profile, target_only=config.target_only)
                process = subprocess.Popen(command, cwd=root, stdout=out, stderr=err,
                                           env=child_env,
                                           start_new_session=os.name != "nt",
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                try:
                    code = process.wait(timeout=config.timeout_seconds)
                except subprocess.TimeoutExpired:
                    _kill(process)
                    raise TimeoutError(f"SCIP exceeded {config.timeout_seconds:g}s") from None
            report["log_directory"] = str(directory)
            if code:
                raise RuntimeError(f"SCIP exited with code {code}; see {directory / 'stderr.log'}")
            if before != current_fingerprint(root):
                raise ValueError("Source files changed during SCIP indexing")
            manifest = {"sources": before, "auxiliary_inputs": inputs_before, "index_sha256": "", "root_uri": root.as_uri(),
                        "profile": report["profile"], "target_only": config.target_only,
                        "python_executable": report["python_executable"],
                        "environment_sha256": report["environment_sha256"], "runtime_inputs": report["runtime_inputs"]}
        if index_path.stat().st_size > config.max_index_bytes:
            raise ValueError("SCIP index exceeds configured size limit")
        data = index_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if config.bundle and digest != manifest["index_sha256"]:
            raise ValueError("SCIP bundle index checksum mismatch")
        index = read_index(data)
        report["indexed_root_uri"] = _normalize_index_root(index, root, manifest.get("target_only"))
        # A bundle records both the source snapshot and the exact index bytes.
        manifest.update(index_sha256=digest, root_uri=root.as_uri(), tool=index["tool"], tool_version=index["tool_version"])
        if not config.bundle:
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        semantic = {"tool": index["tool"], "tool_version": index["tool_version"],
                    "documents": sorted([{**doc, "path": doc["path"].replace("\\", "/")} for doc in index["documents"]],
                                        key=lambda doc: doc["path"])}
        semantic_digest = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
        index["source_fingerprint"] = before
        index["auxiliary_inputs"] = inputs_before
        report["profile"] = manifest.get("profile", {"mode": "legacy_bundle"})
        report["python_executable"] = manifest.get("python_executable")
        report["target_only"] = manifest.get("target_only")
        report["document_count"] = len(index["documents"])
        report["occurrence_count"] = sum(len(d["occurrences"]) for d in index["documents"])
        report.update(active="scip", status="ready", reason="", index_sha256=digest,
                      semantic_sha256=semantic_digest,
                      tool=index["tool"], tool_version=index["tool_version"], bundle=str(manifest_path))
        trace.emit("resolver_ready", **report)
        return index, report
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        report.update(reason=str(error), error_type=type(error).__name__)
        trace.emit("resolver_fallback", **report)
        if config.strict:
            raise
        return None, report
    finally:
        report["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)


def _byte_column(text: str, column: int, encoding: int) -> int:
    codec = {1: "utf-8", 2: "utf-16-le", 3: "utf-32-le"}.get(encoding)
    if codec is None:
        raise ValueError("SCIP position encoding is unspecified")
    unit = {1: 1, 2: 2, 3: 4}[encoding]
    raw = text.encode(codec)
    if column * unit > len(raw):
        raise ValueError("SCIP range is outside the source line")
    return len(raw[:column * unit].decode(codec).encode("utf-8"))


class ScipResolver:
    def __init__(self, index: dict, root: Path, nodes: list[dict], *, trace: GraphTrace | None = None) -> None:
        self.references = defaultdict(list)
        self.skipped_paths = set()
        skipped_documents = []
        definitions = defaultdict(set)
        local_definitions = set()
        symbols_by_path = defaultdict(list)
        for node in nodes:
            if node["type"] in {"Function", "Method", "Class", "Test"}:
                symbols_by_path[node["path"]].append(node)
        for document in index["documents"]:
            # scip-python 0.6.6 emits native separators on Windows despite the SCIP convention.
            path = document["path"].replace("\\", "/")
            posix = PurePosixPath(path)
            if not path or posix.is_absolute() or PureWindowsPath(path).drive or ".." in posix.parts or posix.as_posix() != path:
                raise ValueError("Unsafe SCIP document path")
            source = (root / path).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ValueError("SCIP document is outside the source snapshot")
            data = source.read_bytes()
            expected = index.get("source_fingerprint", {}).get(path)
            if expected and hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("Source changed after SCIP indexing")
            try:
                lines = data.decode("utf-8").split("\n")
            except UnicodeDecodeError:
                # Graph ranges/snippets use original UTF-8 bytes. Transcoding or
                # replacement would make occurrence offsets unverifiable. Keep
                # other documents usable and expose this per-file limitation.
                detail = {"path": path, "reason": "source_encoding_not_utf8"}
                self.skipped_paths.add(path)
                skipped_documents.append(detail)
                if trace is not None:
                    trace.emit("resolver_document_skipped", **detail)
                continue
            encoding = document["encoding"]
            # Definitions must match the declaration's name token, not any same-named
            # assignment inside its body. The latter fabricates recursive call edges.
            declarations = defaultdict(set)
            for node in symbols_by_path[path]:
                span = node["range"]
                header = lines[span["start_line"] - 1].encode("utf-8")[span["start_col"]:]
                match = re.match(rb"(?:async[ \t]+)?(?:def|class)[ \t]+([^\s(:]+)", header)
                if match and match.group(1) == node["name"].encode("utf-8"):
                    key = (span["start_line"], span["start_col"] + match.start(1),
                           span["start_line"], span["start_col"] + match.end(1))
                    declarations[key].add(node["id"])
                for alias in node['properties'].get('symbol_aliases', []):
                    span = alias['range']
                    a, b, c, d = (span[key] for key in ('start_line', 'start_col', 'end_line', 'end_col'))
                    if a == c and 1 <= a <= len(lines) and lines[a-1].encode('utf-8')[b:d] == alias['name'].encode('utf-8'):
                        declarations[(a, b, c, d)].add(node['id'])
            # Pinned scip-python 0.6.6 predates position_encoding and uses JS UTF-16 offsets.
            if not encoding and index["tool"] in {"scip-python", "@sourcegraph/scip-python"} and index["tool_version"] == "0.6.6":
                encoding = 2
            for occurrence in document["occurrences"]:
                a, b, c, d = occurrence["range"]
                if a >= len(lines) or c >= len(lines):
                    raise ValueError("SCIP line is outside source")
                start = (a + 1, _byte_column(lines[a], b, encoding))
                end = (c + 1, _byte_column(lines[c], d, encoding))
                symbol = occurrence["symbol"]
                if not symbol:
                    continue
                if symbol.startswith("local "):
                    symbol = f"{path}:{symbol}"
                if occurrence["roles"] & 1:
                    local_definitions.add(symbol)
                    definitions[symbol].update(declarations.get((*start, *end), ()))
                else:
                    self.references[(path, *end)].append(symbol)
        self.definitions = definitions
        self.local_definitions = local_definitions
        self.statistics = {"symbols_with_internal_targets": sum(bool(v) for v in definitions.values()),
                           "ambiguous_internal_symbols": sum(len(v) > 1 for v in definitions.values()),
                           "usable_document_count": len(index['documents']) - len(skipped_documents),
                           "skipped_document_count": len(skipped_documents),
                           "skipped_documents": skipped_documents}

    def resolve(self, path: str, line: int, column: int) -> tuple[str, list[str]]:
        if path in self.skipped_paths:
            return "source_encoding_not_utf8", []
        symbols = self.references.get((path, line, column), [])
        if not symbols:
            return "no_occurrence", []
        targets = sorted({target for symbol in symbols for target in self.definitions[symbol]})
        if len(targets) == 1 and all(self.definitions[symbol] == {targets[0]} for symbol in symbols):
            return "resolved", targets
        return ("ambiguous" if targets else "local_non_callable" if all(symbol in self.local_definitions for symbol in symbols)
                else "external_or_non_callable"), targets
