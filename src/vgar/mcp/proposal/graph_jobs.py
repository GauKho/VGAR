"""Host-authorized graph jobs, persistent per-session extraction worker, immutable snapshots.

Only static Python/legacy profile is implemented. This controller is trusted Python
bootstrap code, not a JSON-configurable model plugin or an external agent loop.
"""
from __future__ import annotations

import atexit
import json
import math
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from uuid import uuid4

import anyio

from vgar.contracts.schema import validate_graph_document
from vgar.graph.builder import (
    RESOLVER_PROFILE,
    PythonGraphBuilder,
    discover_python_files,
)
from vgar.graph.storage_capabilities import (
    SnapshotGraphStore,
    SQLiteSnapshotStorage,
    canonical_bytes,
    digest,
    legacy_profile,
)
from vgar.repair.evidence import atomic_json, encode_json
from vgar.repair.executor import _WindowsJob
from vgar.repair.workspace import inventory

from .context import (
    authorize_write,
    cancel_request,
    check_context,
    check_source,
    request_cancelled,
    request_commit_guard,
)
from .contracts import BuildRequest, BuildResult, EvidenceRef, SnapshotBinding
from .locking import lock_key, no_links
from .ports import ProviderBinding, ProviderRegistry
from .security import read_lease_bytes, resolve_read_path
from .state import repo_guard

CAPABILITY = "legacy_static_python"


def resolver_fingerprint():
    root = Path(__file__).resolve().parents[2] / "graph"
    return digest(canonical_bytes({"resolver": RESOLVER_PROFILE, "python": list(sys.version_info[:3]),
        "packages": {p: metadata.version(p) for p in ("tree-sitter", "tree-sitter-python")}, "sources": {
        name: digest((root/name).read_bytes()) for name in ("builder.py", "incremental.py", "method_aliases.py")}}))


def implementation_fingerprint():
    return digest(canonical_bytes({name: digest(Path(__file__).with_name(name).read_bytes())
                                   for name in ("graph_jobs.py", "_graph_worker.py")}))


@dataclass(frozen=True)
class GraphJobConfig:
    repo_root: Path
    output_root: Path
    state_root: Path
    repo_key: str
    repository_revision: str
    config_hash: str
    profile_hash: str
    source_roots: tuple[str, ...] = ("src",)
    required_capabilities: tuple[str, ...] = (CAPABILITY,)

    def __post_init__(self):
        for name in ("repo_root", "output_root", "state_root"):
            path = no_links(getattr(self, name)).resolve(strict=True)
            if not path.is_dir():
                raise ValueError("Existing host roots required")
            object.__setattr__(self, name, path)
        if not self.repo_key or not self.repository_revision or type(self.source_roots) is not tuple:
            raise ValueError("Pinned builder configuration required")
        if not self.source_roots or any(not isinstance(p, str) or not p or p.startswith(("/", "\\")) or ".." in Path(p).parts or ":" in p for p in self.source_roots):
            raise ValueError("Relative source roots required")
        # Reuse strict hash validation without inventing a second hash contract.
        legacy_profile(resolver_hash=self.config_hash, profile_hash=self.profile_hash)


class GraphJobController:
    synthetic = False

    def __init__(self, config: GraphJobConfig, *, storage_issuer):
        if type(config) is not GraphJobConfig or not callable(storage_issuer):
            raise ValueError("Trusted graph configuration/storage issuer required")
        self.config, self.storage_issuer = config, storage_issuer
        self._lock = threading.Lock()
        self._process = self._job = self._worker_root = self._stderr = self._reader = None
        self._messages = queue.Queue()
        self._active_cancel = None
        self._worker_fingerprint = None
        self._worker_source_hash = self._worker_graph_version = None
        self._closed = False
        atexit.register(self.close)

    def _validate(self, request, ctx):
        check_source(ctx)
        if type(request) is not BuildRequest:
            raise ValueError("Build request required")
        cfg = self.config
        if (no_links(Path(request.repo_path)).resolve(strict=True) != cfg.repo_root
                or ctx.repo_root != cfg.repo_root or ctx.output_root != cfg.output_root
                or ctx.state_root != cfg.state_root or ctx.config_hash != cfg.config_hash):
            raise ValueError("Graph job context/config/repo binding mismatch")
        if cfg.required_capabilities != (CAPABILITY,):
            raise ValueError("Requested graph capability unavailable; schema/provider required")

    def registry_for(self, ctx):
        self._validate(BuildRequest(repo_path=str(ctx.repo_root)), ctx)
        return ProviderRegistry((ProviderBinding(self, SnapshotBinding.from_context(ctx),
                                                 frozenset({"build"}), lifecycle="guarded-v1"),))

    def profile(self):
        # Wrapper config/code affects storage compatibility even when the graph's
        # semantic facts happen to remain identical. Never infer these from DB.
        effective = digest(canonical_bytes({"operator_profile": self.config.profile_hash,
            "config": self.config.config_hash, "implementation": implementation_fingerprint()}))
        return legacy_profile(resolver_hash=resolver_fingerprint(), profile_hash=effective)

    async def build_or_update(self, request, ctx):
        self._validate(request, ctx)
        cancel, done = threading.Event(), threading.Event()
        def work():
            try:
                return self._execute(request, ctx, cancel)
            finally:
                done.set()
        try:
            return await anyio.to_thread.run_sync(work, abandon_on_cancel=True)
        except BaseException as exc:
            if isinstance(exc, anyio.get_cancelled_exc_class()) or not done.is_set():
                cancel.set()
                marker_error = None
                try:
                    cancel_request(ctx)
                except (OSError, ValueError) as error:
                    marker_error = error
                finally:
                    with anyio.CancelScope(shield=True):
                        cleaned = await anyio.to_thread.run_sync(done.wait, 10)
                        if not cleaned:
                            raise RuntimeError("Graph controller cleanup incomplete") from None
                if marker_error:
                    raise RuntimeError("Graph cancellation persistence failed after cleanup") from marker_error
            raise

    def _check(self, ctx, cancel, end):
        check_context(ctx)
        if cancel.is_set():
            raise ValueError("Graph job cancelled")
        if time.time() >= end:
            raise TimeoutError("Graph job deadline exhausted")

    def _start_worker(self, ctx):
        root = no_links(ctx.output_root / (".graph-worker-" + uuid4().hex))
        root.mkdir(exist_ok=False)
        self._worker_root = root
        self._stderr = (root / "stderr.bin").open("wb")
        allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC"}
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="1", PYTHONOPTIMIZE="0")
        self._messages = queue.Queue(maxsize=2)
        self._ipc_error = threading.Event()
        self._worker_instance = uuid4().hex
        self._process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).with_name("_graph_worker.py")), self._worker_instance],
            cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
            shell=False, creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | 0x4) if os.name == "nt" else 0,
            start_new_session=os.name != "nt")
        if os.name == "nt":
            self._job = _WindowsJob(self._process)
        stream, messages = self._process.stdout, self._messages
        def read():
            while True:
                line = stream.readline(12001)
                try:
                    messages.put_nowait(line)
                except queue.Full:
                    self._ipc_error.set()
                    return
                if not line or len(line) > 12000:
                    return
        self._reader = threading.Thread(target=read, daemon=True)
        self._reader.start()

    def _exchange(self, message, ctx, cancel, end):
        process = self._process
        stderr_start = (self._worker_root / "stderr.bin").stat().st_size
        process.stdin.write(canonical_bytes(message) + b"\n")
        process.stdin.flush()
        while True:
            self._check(ctx, cancel, end)
            if self._ipc_error.is_set():
                raise ValueError("Graph worker unsolicited IPC output")
            if (self._worker_root / "stderr.bin").stat().st_size - stderr_start > ctx.limits.output_bytes:
                raise ValueError("Graph worker output limit exceeded")
            try:
                line = self._messages.get(timeout=.02)
            except queue.Empty:
                if process.poll() is not None:
                    raise ValueError("Graph worker exited without completion") from None
                continue
            if not line or len(line) > min(12000, ctx.limits.output_bytes):
                raise ValueError("Graph worker IPC missing/oversized")
            if (self._worker_root / "stderr.bin").stat().st_size - stderr_start > ctx.limits.output_bytes:
                raise ValueError("Graph worker output limit exceeded")
            result = json.loads(line)
            if result.get("job_id") != message["job_id"]:
                raise ValueError("Graph worker job binding mismatch")
            return result

    def _stop_worker(self):
        process = self._process
        if self._job:
            self._job.close()
            self._job = None
        elif process and os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdin.close()
            self._reader.join(5) if self._reader else None
            process.stdout.close()
        if self._stderr:
            self._stderr.close()
        self._process = self._stderr = self._reader = None
        self._worker_fingerprint = None
        self._worker_source_hash = self._worker_graph_version = None
        if self._worker_root is not None:
            self._remove_private(self._worker_root, ".graph-worker-")
            self._worker_root = None

    def _remove_private(self, path, prefix):
        no_links(path)
        if path.parent != self.config.output_root or not path.name.startswith(prefix):
            raise ValueError("Unsafe graph staging cleanup")
        for item in path.rglob("*"):
            no_links(item)
        shutil.rmtree(path)

    def close(self):
        if self._active_cancel is not None:
            self._active_cancel.set()
        if not self._lock.acquire(timeout=10):
            raise RuntimeError("Graph controller still active during shutdown")
        try:
            self._stop_worker()
            self._closed = True
        finally:
            self._lock.release()

    async def aclose(self):
        atexit.unregister(self.close)
        await anyio.to_thread.run_sync(self.close)

    def _execute(self, request, ctx, cancel):
        self._validate(request, ctx)
        end = min(ctx.deadline, time.time() + ctx.limits.worker_seconds)
        lock_end = min(end, time.time()+ctx.limits.lock_seconds)
        while not self._lock.acquire(timeout=.02):
            self._check(ctx, cancel, lock_end)
        try:
            if self._closed:
                raise ValueError("Graph controller closed")
            self._active_cancel = cancel
            with repo_guard(ctx, cancel_event=cancel):
                self._validate(request, ctx)
                authorize_write(ctx, "build_or_update_graph", request.input_hash())
                return self._authorized(request, ctx, cancel, end)
        finally:
            self._active_cancel = None
            self._lock.release()

    def _authorized(self, request, ctx, cancel, end):
        cfg = self.config
        profile = self.profile()
        options = {"repo_key": cfg.repo_key, "repository_revision": cfg.repository_revision, "source_roots": cfg.source_roots}
        fingerprint = digest(canonical_bytes({"repo": lock_key(cfg.repo_root), "options": options,
            "schema": profile.schema_hash, "resolver": profile.resolver_hash, "profile": profile.profile_hash,
            "config": cfg.config_hash, "implementation": implementation_fingerprint()}))
        key = digest(canonical_bytes({"binding": fingerprint, "source": ctx.source_hash})).removeprefix("sha256:")
        index_path = resolve_read_path(ctx.output_root, "graph-cache/" + key + ".json")
        job_id = uuid4().hex
        stage = ctx.output_root / (".graph-job-" + job_id)
        receipt = {"job_id": job_id, "binding": SnapshotBinding.from_context(ctx).model_dump(),
                   "input_hash": request.input_hash(), "fingerprint": fingerprint, "status": "ERROR",
                   "baseline_snapshot_hash": ctx.snapshot_hash,
                   "cache_mode": "NOT_RUN", "published": False, "cleanup": "NOT_RUN"}
        manifest, index_entry, result = None, None, None
        receipts = no_links(ctx.output_root / "graph-jobs")
        receipt_path = receipts / (job_id + ".json")
        try:
            self._check(ctx, cancel, end)
            if index_path.exists():
                entry = json.loads(read_lease_bytes(ctx.output_root, index_path.relative_to(ctx.output_root).as_posix(), 65536)[0])
                if entry.get("key") != key or entry.get("fingerprint") != fingerprint or entry.get("source_hash") != ctx.source_hash:
                    raise ValueError("Graph cache binding mismatch")
                manifest = resolve_read_path(ctx.output_root, entry["manifest"])
                if digest(manifest.read_bytes()) != entry["manifest_hash"]:
                    raise ValueError("Graph cache manifest hash mismatch")
                proof, proof_size = read_lease_bytes(ctx.output_root, entry["receipt"], ctx.limits.read_bytes)
                if proof_size > ctx.limits.read_bytes or digest(proof) != entry["receipt_hash"]:
                    raise ValueError("Graph cache publication evidence hash mismatch")
                published = json.loads(proof)
                if (published.get("status") != "PASS" or published.get("published") is not True
                        or published.get("manifest") != entry["manifest"]
                        or published.get("manifest_hash") != entry["manifest_hash"]
                        or published.get("storage_snapshot_id") != entry["snapshot_id"]):
                    raise ValueError("Graph cache publication evidence mismatch")
                store = SnapshotGraphStore(manifest, graph_version=entry["graph_version"], profiles=(profile,))
                if asdict(store.identity) != entry["identity"] or store.identity.source_inventory_hash != ctx.source_hash:
                    raise ValueError("Graph cache identity mismatch")
                if self._process is not None and self._worker_source_hash != ctx.source_hash:
                    # A previously returned snapshot may differ from the worker's
                    # extraction lineage. Never label that lineage as a warm diff.
                    self._stop_worker()
                receipt.update(cache_mode="SNAPSHOT_REUSE", manifest=entry["manifest"],
                               storage_snapshot_id=store.identity.snapshot_id, graph_version=store.identity.graph_version,
                               storage_identity=asdict(store.identity),
                               changes_baseline_snapshot_hash=store.identity.graph_version,
                               changed_files=[], added_files=[], deleted_files=[], cache_hits=None, worker_pid=None)
            else:
                stage.mkdir(exist_ok=False)
                source = stage / "source"
                source.mkdir()
                facts = inventory(ctx.repo_root)
                for path in discover_python_files(ctx.repo_root):
                    self._check(ctx, cancel, end)
                    relative = path.relative_to(ctx.repo_root).as_posix()
                    no_links(path)
                    raw, size = read_lease_bytes(ctx.repo_root, relative, 16*1024*1024)
                    if size > 16*1024*1024 or digest(raw) != facts.get(relative):
                        raise ValueError("Graph source copy hash mismatch")
                    target = source / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                check_source(ctx)
                if self._process is not None and self._worker_fingerprint != fingerprint:
                    self._stop_worker()
                if self._process is None:
                    self._start_worker(ctx)
                    self._worker_fingerprint = fingerprint
                message = {"action": "build", "job_id": job_id, "stage": str(stage),
                           "fingerprint": fingerprint, "options": options}
                response = self._exchange(message, ctx, cancel, end)
                if response.get("status") != "READY" or response.get("fingerprint") != fingerprint:
                    raise ValueError("Graph worker result incomplete")
                raw, size = read_lease_bytes(stage, "document.json", 256*1024*1024)
                summary_raw, summary_size = read_lease_bytes(stage, "summary.json", 65536)
                if (size > 256*1024*1024 or summary_size > 65536 or digest(raw) != response.get("document_hash")
                        or digest(summary_raw) != response.get("summary_hash")):
                    raise ValueError("Graph worker document/summary hash mismatch")
                document, summary = json.loads(raw), json.loads(summary_raw)
                for field in ("changed_files", "added_files", "deleted_files"):
                    paths = summary.get(field)
                    if (type(paths) is not list or any(not isinstance(p, str) or not p.endswith(".py") for p in paths)
                            or len(paths) != len(set(paths))):
                        raise ValueError("Graph worker summary path list invalid")
                    for path in paths:
                        resolve_read_path(source, path, protect=False)
                for field in ("cache_hits", "total_files", "affected_node_count"):
                    if type(summary.get(field)) is not int or summary[field] < 0:
                        raise ValueError("Graph worker summary count invalid")
                for field in ("extract_seconds", "validate_seconds", "total_seconds", "worker_elapsed_ms"):
                    value = summary.get(field, 0)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                        raise ValueError("Graph worker summary duration invalid")
                if (summary["total_files"] != len(discover_python_files(source))
                        or summary["cache_hits"] > summary["total_files"]
                        or type(response.get("worker_pid")) is not int or response["worker_pid"] <= 0
                        or response.get("worker_instance") != self._worker_instance
                        or response.get("mode") not in {"COLD_BUILD", "WARM_UPDATE"}):
                    raise ValueError("Graph worker summary/process binding invalid")
                validate_graph_document(document)
                repositories = [n for n in document["nodes"] if n["type"] == "Repository"]
                if (len(repositories) != 1 or repositories[0]["name"] != source.name
                        or repositories[0]["properties"].get("root_uri") != source.as_uri()):
                    raise ValueError("Graph worker repository metadata mismatch")
                # Project only physical-copy metadata back to the trusted host
                # root; all IDs, facts, ranges and graph_version stay unchanged.
                repositories[0]["name"] = ctx.repo_root.name
                repositories[0]["properties"]["root_uri"] = ctx.repo_root.as_uri()
                expected = PythonGraphBuilder(**options)._calculate_graph_version(source, discover_python_files(source))
                files = {p.relative_to(source).as_posix(): digest(p.read_bytes()) for p in discover_python_files(source)}
                actual_files = {n["path"]: n["content_hash"] for n in document["nodes"] if n["type"] == "File"}
                if (document["graph_version"] != expected or document["repo_key"] != cfg.repo_key
                        or document["repository_revision"] != cfg.repository_revision or actual_files != files):
                    raise ValueError("Graph worker source/document binding mismatch")
                ack = self._exchange({"action": "ack", "job_id": job_id}, ctx, cancel, end)
                if ack.get("status") != "ACK":
                    raise ValueError("Graph worker completion not acknowledged")
                check_source(ctx)
                snapshots = no_links(ctx.output_root / "snapshots")
                snapshots.mkdir(exist_ok=True)
                cap = SQLiteSnapshotStorage(snapshots, profiles=(profile,))
                identity = cap.identity(document, source_inventory_hash=ctx.source_hash)
                derived = self.storage_issuer(ctx, identity)
                self._check(ctx, cancel, end)
                manifest = cap.ingest(document, context=derived, request_context=ctx, cancel_event=cancel,
                                      operation_deadline=end)
                SnapshotGraphStore(manifest, graph_version=document["graph_version"], profiles=(profile,))
                receipt.update(summary, cache_mode=response["mode"], worker_pid=response["worker_pid"],
                               manifest=manifest.relative_to(ctx.output_root).as_posix(),
                               storage_snapshot_id=identity.snapshot_id, graph_version=identity.graph_version,
                               changes_baseline_snapshot_hash=self._worker_graph_version if response["mode"] == "WARM_UPDATE" else None,
                               storage_identity=asdict(identity))
                index_entry = {"key": key, "fingerprint": fingerprint, "source_hash": ctx.source_hash,
                    "identity": asdict(identity), "graph_version": identity.graph_version,
                    "snapshot_id": identity.snapshot_id,
                    "manifest": receipt["manifest"], "manifest_hash": digest(manifest.read_bytes()),
                    "receipt": receipt_path.relative_to(ctx.output_root).as_posix()}
            self._check(ctx, cancel, end)
            check_source(ctx)
            if stage.exists():
                self._remove_private(stage, ".graph-job-")
            receipt.update(status="PASS", published=True, cleanup="PASS", manifest_hash=digest(manifest.read_bytes()))
            receipt_bytes = encode_json(receipt)
            if len(receipt_bytes) > ctx.limits.read_bytes:
                raise ValueError("Graph receipt exceeds evidence limit")
            result = BuildResult(binding=SnapshotBinding.from_context(ctx), result_snapshot_hash=receipt["graph_version"],
                capabilities=(CAPABILITY,), reasons=("LEGACY_PROFILE_ONLY",), published=True,
                changed_paths=tuple(sorted(set(receipt["changed_files"]+receipt["added_files"]+receipt["deleted_files"]))),
                evidence=(EvidenceRef(path=receipt_path.relative_to(ctx.output_root).as_posix(), sha256=digest(receipt_bytes)),))
            with request_commit_guard(ctx):
                self._check(ctx, cancel, end)
                check_source(ctx)
                receipts.mkdir(exist_ok=True)
                atomic_json(receipt_path, receipt)
                if index_entry is not None:
                    index_path.parent.mkdir(exist_ok=True)
                    index_entry["receipt_hash"] = digest(receipt_bytes)
                    atomic_json(index_path, index_entry)
                if index_entry is not None:
                    self._worker_source_hash, self._worker_graph_version = ctx.source_hash, receipt["graph_version"]
        except BaseException as exc:
            receipt.update(status="ERROR", published=False)
            receipt["error_type"] = type(exc).__name__
            receipt["timed_out"] = isinstance(exc, TimeoutError) or time.time() >= end
            receipt["cancelled"] = cancel.is_set()
            try:
                receipt["cancelled"] |= request_cancelled(ctx)
            except (ValueError, OSError):
                receipt["cancellation_state"] = "UNAVAILABLE_CONTEXT"
            self._stop_worker()
            raise
        finally:
            try:
                if stage.exists():
                    self._remove_private(stage, ".graph-job-")
                receipt["cleanup"] = "PASS"
            except BaseException:
                receipt.update(status="ERROR", published=False, cleanup="ERROR")
                raise
            finally:
                if receipt["status"] != "PASS":
                    receipts.mkdir(exist_ok=True)
                    atomic_json(receipt_path, receipt)
        return result
