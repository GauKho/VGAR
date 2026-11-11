"""Thin adapters: validate binding/evidence, never implement graph or verifier algorithms."""
from __future__ import annotations

import hashlib
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from weakref import WeakKeyDictionary

import anyio

from vgar.contracts.error import GraphError
from vgar.mcp.tooling import run_tool, run_tool_async
from vgar.repair.evidence import atomic_json

from . import contracts as c
from .context import (
    authorize_write,
    check_context,
    check_source,
    current_context,
    request_scope,
)
from .locking import lock_key, locked, no_links
from .ports import ProviderRegistry
from .security import read_lease_bytes, resolve_read_path

CORE_TOOLS = frozenset({"graph_build_or_update_graph", "graph_search_symbols", "graph_find_task_anchors",
                        "graph_get_related_context", "graph_get_callers", "graph_get_callees",
                        "graph_explain_dependency_path", "graph_analyze_patch_impact",
                        "graph_verify_patch_graph_constraints", "graph_rank_patch_candidates",
                        "execution_run_relevant_tests"})
_LOOP_LOCKS = WeakKeyDictionary()


@asynccontextmanager
async def _async_repo_guard(ctx):
    # FileLock is reentrant by thread, while two async requests share that thread.
    # Serialize tasks first; OS lock still protects other loops/processes.
    check_context(ctx)
    loop = anyio.lowlevel.current_token().native_token
    locks = _LOOP_LOCKS.setdefault(loop, {})
    key = (str(ctx.state_root), lock_key(ctx.repo_root))
    lock = locks.setdefault(key, anyio.Lock())
    with anyio.fail_after(min(ctx.limits.lock_seconds, max(0, ctx.deadline - time.time()))):
        await lock.acquire()
    try:
        end = min(time.time() + ctx.limits.lock_seconds, ctx.deadline)
        path = ctx.state_root / "locks" / ("repo-" + lock_key(ctx.repo_root) + ".lock")
        while True:
            check_context(ctx)
            manager = locked(path, timeout=0, deadline=ctx.deadline)
            try:
                manager.__enter__()
                break
            except TimeoutError:
                if time.time() >= end:
                    raise
                await anyio.sleep(min(.02, max(0, end - time.time())))
        try:
            check_context(ctx)
            yield
        finally:
            manager.__exit__(None, None, None)
    finally:
        lock.release()


def legacy_binding(*, graph_version=None, task_id=None):
    """Only strengthen legacy validation when the host explicitly bound a context."""
    ctx = current_context()
    if ctx is not None:
        check_source(ctx)
        if graph_version is not None and graph_version != ctx.snapshot_hash:
            raise ValueError("Legacy graph_version does not match bound snapshot")
        if task_id is not None and task_id != ctx.task_id:
            raise ValueError("Legacy task_id does not match bound task")
    return ctx


class CoreTools:
    def __init__(self, registry: ProviderRegistry, *, limits=None, context_factory=None, graph_jobs=None):
        if type(registry) is not ProviderRegistry:
            raise ValueError("Host registry required")
        self.registry = registry
        self.limits = c.AdapterLimits.model_validate((limits or c.AdapterLimits()).model_dump())
        self.context_factory = context_factory
        if graph_jobs is not None:
            from .graph_jobs import GraphJobController
            if type(graph_jobs) is not GraphJobController or registry.get("build") is not None:
                raise ValueError("Trusted graph controller required; duplicate build provider forbidden")
        self.graph_jobs = graph_jobs

    def _record(self, capability, ctx):
        check_source(ctx)
        registry = self.graph_jobs.registry_for(ctx) if capability == "build" and self.graph_jobs is not None else self.registry
        record = registry.get(capability)
        if record is not None and record.binding != c.SnapshotBinding.from_context(ctx):
            raise ValueError("Provider snapshot/source/config/task/run binding mismatch")
        return record

    def _required(self, capability, ctx):
        record = self._record(capability, ctx)
        if record is None:
            raise GraphError("Provider capability unavailable", details={"reason": "CAPABILITY_UNAVAILABLE", "capability": capability})
        return record.provider

    def _result(self, cls, value, ctx, *, diff_hash=None):
        # Revalidate even model instances: model_copy/model_construct can bypass DTO validators.
        data = value.model_dump(mode="python") if isinstance(value, c.DTO) else value
        result = cls.model_validate(data)
        check_source(ctx)
        if result.binding != c.SnapshotBinding.from_context(ctx):
            raise ValueError("Provider output binding mismatch")
        if diff_hash is not None and result.diff_hash != diff_hash:
            raise ValueError("Provider output diff hash mismatch")
        if len(result.evidence) > ctx.limits.audit_records:
            raise ValueError("Evidence count exceeds host limit")
        for ref in result.evidence:
            raw, size = read_lease_bytes(ctx.output_root, ref.path, ctx.limits.read_bytes)
            if size > ctx.limits.read_bytes or "sha256:" + hashlib.sha256(raw).hexdigest() != ref.sha256:
                raise ValueError("Evidence file/hash mismatch")
        return result

    def _diff(self, request):
        req = c.DiffRequest.model_validate(request.model_dump())
        if len(req.diff.encode("utf-8")) > self.limits.max_diff_bytes:
            raise ValueError("Diff exceeds operator byte limit")
        return req

    def _bounds(self, request):
        hops = request.depth if isinstance(request, c.TraversalRequest) else request.max_hops
        if hops > self.limits.max_hops or request.max_nodes > self.limits.max_nodes or request.max_examined_edges > self.limits.max_examined_edges:
            raise ValueError("Traversal exceeds operator limits")

    @asynccontextmanager
    async def _provider_job(self, operation, request, ctx, *, candidate_workspace=None):
        def lease_state():
            root = no_links(ctx.lease_root)
            facts = {}
            for path in root.rglob("*"):
                no_links(path)
                relative = path.relative_to(root).as_posix()
                if path.is_dir():
                    facts[relative + "/"] = "directory"
                elif path.is_file():
                    with path.open("rb") as stream:
                        facts[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
                else:
                    raise ValueError("Unsupported lease entry in cleanup manifest")
            return facts
        before = lease_state()
        status, error_type = "ERROR", None
        try:
            with anyio.fail_after(max(0, min(ctx.limits.worker_seconds, ctx.deadline - time.time()))):
                yield
            status = "PASS"
        except BaseException as exc:
            error_type = type(exc).__name__
            raise
        finally:
            # A host observation, not a substitute for the provider's executor/container receipt.
            after = lease_state()
            # Only the host-bound admitted test workspace may disappear. Builds
            # preserve every lease entry, including ignored files and empty dirs.
            prefix = candidate_workspace.replace("\\", "/").rstrip("/") if candidate_workspace else None
            expected = {name: value for name, value in before.items()
                        if not prefix or (name != prefix and not name.startswith(prefix + "/"))}
            cleaned = after == expected
            cleanup_failure = status == "PASS" and not cleaned
            if cleanup_failure:
                status, error_type = "ERROR", "LEASE_CLEANUP_INCOMPLETE"
            root = no_links(ctx.output_root)
            atomic_json(root / ("adapter-" + uuid4().hex + ".json"), {
                "operation": operation, "input_hash": request.input_hash(), "status": status,
                "binding": c.SnapshotBinding.from_context(ctx).model_dump(), "request_id": ctx.request_id,
                "cleanup_observed": cleaned, "error_type": error_type})
            if cleanup_failure:
                raise ValueError("Provider lease cleanup incomplete")

    def path(self, request, ctx):
        req = c.PathRequest.model_validate(request.model_dump()); self._bounds(req)
        value = self._required("path", ctx).explain_path(req, ctx)
        result = self._result(c.PathResult, value, ctx)
        if len(result.nodes) > req.max_nodes or len(result.edges) > req.max_hops or result.examined_edges > req.max_examined_edges:
            raise ValueError("Path output exceeds limits")
        if result.nodes:
            if result.nodes[0] != req.source_id or result.nodes[-1] != req.target_id or len(result.edges) != len(result.nodes) - 1:
                raise ValueError("Path endpoints/witness mismatch")
            for left, right, edge in zip(result.nodes, result.nodes[1:], result.edges, strict=False):
                endpoints = (edge.source_id, edge.target_id) if edge.direction == "outgoing" else (edge.target_id, edge.source_id)
                if endpoints != (left, right):
                    raise ValueError("Disconnected path witness")
        elif result.edges:
            raise ValueError("Path edges without nodes")
        return result

    def traverse(self, request, ctx):
        req = c.TraversalRequest.model_validate(request.model_dump()); self._bounds(req)
        result = self._result(c.TraversalResult, self._required("traversal", ctx).traverse(req, ctx), ctx)
        ids = [s.symbol_id for s in result.symbols]
        if len(ids) != len(set(ids)) or req.symbol_id in ids or len(ids) > req.max_nodes or any(s.hop > req.depth for s in result.symbols) or result.examined_edges > req.max_examined_edges:
            raise ValueError("Traversal output exceeds bounds or has duplicate/seed nodes")
        if len(result.evidence_edges) > req.max_examined_edges:
            raise ValueError("Traversal evidence exceeds limits")
        return result

    async def build(self, request, ctx):
        req = c.BuildRequest.model_validate(request.model_dump())
        check_source(ctx)
        if no_links(Path(req.repo_path)).resolve(strict=True) != ctx.repo_root:
            raise ValueError("Build repo_path differs from host-bound repo")
        provider = self._required("build", ctx)
        if self.graph_jobs is not None:
            # Controller thread owns validate/auth/repo lock/worker/storage for
            # the complete job. Do not hold another OS lock while awaiting it.
            async with self._provider_job("build_or_update_graph", req, ctx):
                result = self._result(c.BuildResult, await provider.build_or_update(req, ctx), ctx)
                if result.published and not result.evidence:
                    raise ValueError("Published snapshot requires persisted publication evidence")
                return result
        async with _async_repo_guard(ctx):
            check_source(ctx)
            authorize_write(ctx, "build_or_update_graph", req.input_hash())
            async with self._provider_job("build_or_update_graph", req, ctx):
                result = await provider.build_or_update(req, ctx)
                result = self._result(c.BuildResult, result, ctx)
                if result.published and not result.evidence:
                    raise ValueError("Published snapshot requires persisted publication evidence")
                return result

    def verify(self, request, ctx):
        req = self._diff(request); record = self._record("verification", ctx)
        if record is None:
            return c.CheckEvidence(binding=c.SnapshotBinding.from_context(ctx), diff_hash=req.diff_hash,
                                   status="NOT_RUN", reasons=("CAPABILITY_UNAVAILABLE",))
        result = self._result(c.CheckEvidence, record.provider.verify_graph(req, ctx), ctx, diff_hash=req.diff_hash)
        if result.status == "PASS" and (result.coverage != "COMPLETE" or not result.scope or not result.evidence):
            raise ValueError("PASS check requires complete scope and persisted evidence")
        return result

    def rank(self, request, ctx):
        req = c.RankRequest.model_validate(request.model_dump())
        if len(req.candidates) > self.limits.max_candidates:
            raise ValueError("Candidate count exceeds operator limit")
        for candidate in req.candidates:
            self._diff(c.DiffRequest(diff=candidate.diff, diff_hash=candidate.diff_hash))
        result = self._result(c.RankResult, self._required("ranking", ctx).rank_candidates(req, ctx), ctx)
        expected = {x.candidate_id: x.diff_hash for x in req.candidates}
        actual = {x.candidate_id: x.diff_hash for x in result.candidates}
        if len(actual) != len(result.candidates) or actual != expected:
            raise ValueError("Ranking candidate ID/hash mismatch")
        ranked = []
        for item in result.candidates:
            checks = {x.name: x.status for x in item.checks}
            if len(checks) != len(item.checks):
                raise ValueError("Duplicate candidate checks")
            eligible = bool(result.evidence) and bool(self.registry.required_checks) and set(checks) == set(self.registry.required_checks) and all(x == "PASS" for x in checks.values())
            ranked.append(item.model_copy(update={"eligible": item.eligible and eligible}))
        return result.model_copy(update={"candidates": tuple(sorted(ranked, key=lambda x: (not x.eligible, -x.score, x.candidate_id)))})

    async def tests(self, request, ctx):
        req = self._diff(request); record = self._record("tests", ctx)
        if record is None:
            return c.TestEvidence(binding=c.SnapshotBinding.from_context(ctx), diff_hash=req.diff_hash,
                                  status="NOT_RUN", reasons=("CAPABILITY_UNAVAILABLE",))
        async with _async_repo_guard(ctx):
            check_source(ctx)
            authorize_write(ctx, "run_relevant_tests", req.input_hash())
            async with self._provider_job("run_relevant_tests", req, ctx, candidate_workspace=record.candidate_workspace):
                value = await record.provider.run_diff_tests(req, ctx)
                result = self._result(c.TestEvidence, value, ctx, diff_hash=req.diff_hash)
                receipt = result.receipt
                if receipt is None or receipt.diff_hash != req.diff_hash or not receipt.admitted or not receipt.cleaned:
                    raise ValueError("Missing/invalid admission, diff or cleanup receipt")
                workspace = resolve_read_path(ctx.lease_root, receipt.workspace, protect=False)
                if workspace != resolve_read_path(ctx.lease_root, record.candidate_workspace, protect=False):
                    raise ValueError("Test receipt workspace differs from host binding")
                if workspace.exists():
                    raise ValueError("Candidate workspace not cleaned")
                if result.status in {"PASS", "FAIL"} and (not receipt.executed or receipt.applied_count != 1 or result.coverage != "COMPLETE" or not result.scope or not result.evidence):
                    raise ValueError("Terminal test evidence requires execution/scope/artifacts")
                return result

    def _context(self, operation, request):
        ctx = current_context()
        if ctx is None and self.context_factory is not None:
            ctx = self.context_factory(operation, request)
        return check_context(ctx)

    def respond(self, operation, request_factory, *, server, audit, invoke, serialize=None):
        kwargs = {"server": server, "tool": operation, "backend": "proposal-adapter", "audit": audit, "untrusted": True}
        try:
            request = request_factory(); ctx = self._context(operation, request)
        except Exception as exc:  # noqa: BLE001 - envelope/audit boundary
            def fail(error=exc): raise error
            return run_tool(**kwargs, call=fail)
        with request_scope(ctx):
            def call():
                result = invoke(request, ctx)
                return serialize(result) if serialize else result.model_dump(mode="json")
            return run_tool(**kwargs, call=call)

    async def respond_async(self, operation, request_factory, *, server, audit, invoke):
        kwargs = {"server": server, "tool": operation, "backend": "proposal-adapter", "audit": audit, "untrusted": True}
        try:
            request = request_factory(); ctx = self._context(operation, request)
        except Exception as exc:  # noqa: BLE001 - envelope/audit boundary
            def fail(error=exc): raise error
            return run_tool(**kwargs, call=fail)
        async def call():
            return (await invoke(request, ctx)).model_dump(mode="json")
        with request_scope(ctx):
            return await run_tool_async(**kwargs, call=call)

    def readiness(self):
        return {name: "SYNTHETIC_ONLY" if record and record.synthetic else "BOUND_UNVERIFIED" if record else "WAITING_PROVIDER"
                for name in ("build", "path", "traversal", "verification", "ranking", "tests")
                for record in (self.graph_jobs if name == "build" and self.graph_jobs is not None else self.registry.get(name),)}
