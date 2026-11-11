"""Adapter acceptance with host-issued contexts; fixtures are explicitly synthetic."""
import importlib.util

import pytest


@pytest.fixture
def adapters(bound):
    from vgar.mcp.proposal import contracts as c
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    authority, ctx = bound
    return c, authority, ctx, CoreTools(ProviderRegistry())


def test_missing_context_and_forged_context_fail(adapters):
    c, _, ctx, tools = adapters
    with pytest.raises(ValueError, match="context"):
        tools.path(c.PathRequest(source_id="a", target_id="b"), None)
    with pytest.raises(ValueError):
        tools.path(c.PathRequest(source_id="a", target_id="b"), ctx.__dict__)


def test_missing_provider_is_not_empty_success(adapters):
    from vgar.contracts.error import GraphError
    c, _, ctx, tools = adapters
    with pytest.raises(GraphError) as error:
        tools.path(c.PathRequest(source_id="a", target_id="b"), ctx)
    assert error.value.details["reason"] == "CAPABILITY_UNAVAILABLE"
    result = tools.verify(c.DiffRequest.from_diff("patch\r\n"), ctx)
    assert result.status == "NOT_RUN" and result.coverage == "UNKNOWN"
    assert result.reasons == ("CAPABILITY_UNAVAILABLE",)


def test_dto_frozen_strict_extra_and_exact_bytes(adapters):
    import hashlib
    c, _, _, _ = adapters
    req = c.DiffRequest.from_diff("é\r\n")
    assert req.diff_hash == "sha256:" + hashlib.sha256("é\r\n".encode()).hexdigest()
    for value in ({"diff": "x", "diff_hash": req.diff_hash}, {"diff": "x", "diff_hash": c.digest("x"), "confirmed": True}):
        with pytest.raises(ValueError):
            c.DiffRequest(**value)
    with pytest.raises(ValueError):
        req.diff = "changed"
    with pytest.raises(ValueError):
        c.TraversalRequest(symbol_id="a", direction="callers", depth=True)


def test_registry_rejects_synthetic_production_and_is_frozen(adapters):
    from dataclasses import FrozenInstanceError

    from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
    c, _, ctx, _ = adapters
    class Provider:
        def explain_path(self, request, context): return None
    binding = ProviderBinding(Provider(), c.SnapshotBinding.from_context(ctx), frozenset({"path"}), synthetic=True)
    with pytest.raises(ValueError, match="synthetic"):
        ProviderRegistry((binding,))
    registry = ProviderRegistry((binding,), test_only=True)
    with pytest.raises(FrozenInstanceError):
        registry.test_only = False
    with pytest.raises(ValueError, match="Duplicate"):
        ProviderRegistry((binding, binding), test_only=True)


def provider_tools(ctx, provider, capabilities, *, limits=None, required_checks=()):
    from vgar.mcp.proposal.contracts import SnapshotBinding
    from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    binding = ProviderBinding(provider, SnapshotBinding.from_context(ctx), frozenset(capabilities), synthetic=True,
                              lifecycle="guarded-v1", candidate_workspace="candidate" if "tests" in capabilities else None)
    return CoreTools(ProviderRegistry((binding,), test_only=True, required_checks=required_checks), limits=limits)


@pytest.mark.parametrize("field", ["snapshot_hash", "source_hash", "config_hash", "task_id", "run_id"])
def test_provider_binding_mismatch_never_called(adapters, field):
    from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    c, _, ctx, _ = adapters
    class Forbidden:
        def explain_path(self, request, context):
            pytest.fail("stale provider called")
    binding = c.SnapshotBinding.from_context(ctx).model_copy(update={field: "other"})
    record = ProviderBinding(Forbidden(), binding, frozenset({"path"}), synthetic=True)
    tools = CoreTools(ProviderRegistry((record,), test_only=True))
    with pytest.raises(ValueError, match="binding"):
        tools.path(c.PathRequest(source_id="a", target_id="b"), ctx)


def test_source_drift_prevents_provider_call(adapters):
    c, _, ctx, tools = adapters
    (ctx.repo_root / "new.py").write_text("x=1", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory"):
        tools.path(c.PathRequest(source_id="a", target_id="b"), ctx)


def test_path_validates_witness_and_output_binding(adapters):
    c, _, ctx, _ = adapters
    class Provider:
        def explain_path(self, request, context):
            return result
    result = c.PathResult(binding=c.SnapshotBinding.from_context(ctx), nodes=("a", "b"),
                          edges=(c.Witness(edge_id="e", edge_type="CALLS", source_id="a", target_id="b",
                                           provenance="synthetic handwritten", confidence=1),), examined_edges=1)
    tools = provider_tools(ctx, Provider(), {"path"})
    assert tools.path(c.PathRequest(source_id="a", target_id="b"), ctx) == result
    for bad in (result.model_copy(update={"nodes": ("b", "a")}),
                result.model_copy(update={"binding": result.binding.model_copy(update={"task_id": "other"})})):
        result = bad
        with pytest.raises(ValueError):
            tools.path(c.PathRequest(source_id="a", target_id="b"), ctx)


@pytest.mark.parametrize("bad", ["duplicates", "hop", "cap", "examined"])
def test_traversal_rejects_invalid_provider_results(adapters, bad):
    c, _, ctx, _ = adapters
    node = c.RelatedSymbol(symbol_id="b", name="b", kind="Function", path="b.py", hop=1)
    values = {"binding": c.SnapshotBinding.from_context(ctx), "symbols": (node,), "examined_edges": 1}
    if bad == "duplicates": values["symbols"] = (node, node)
    if bad == "hop": values["symbols"] = (node.model_copy(update={"hop": 3}),)
    if bad == "cap": values["symbols"] = tuple(node.model_copy(update={"symbol_id": str(i)}) for i in range(201))
    if bad == "examined": values["examined_edges"] = 10001
    class Provider:
        def traverse(self, request, context): return c.TraversalResult(**values)
    tools = provider_tools(ctx, Provider(), {"traversal"})
    with pytest.raises(ValueError):
        tools.traverse(c.TraversalRequest(symbol_id="a", direction="callees", depth=2), ctx)


def test_traversal_uses_provider_oracle_and_preserves_diagnostics(adapters):
    c, _, ctx, _ = adapters
    seen = []
    class Provider:
        def traverse(self, request, context):
            seen.append(request)
            # Handwritten diamond/cycle closure: A->B,C; B,C->D; D->A.
            return c.TraversalResult(binding=c.SnapshotBinding.from_context(context), symbols=tuple(
                c.RelatedSymbol(symbol_id=s, name=s, kind="Function", path="f.py", hop=h)
                for s, h in (("B", 1), ("C", 1), ("D", 2))), examined_edges=5, truncated=True,
                reasons=("HOP_LIMIT",))
    tools = provider_tools(ctx, Provider(), {"traversal"})
    result = tools.traverse(c.TraversalRequest(symbol_id="A", direction="callees", depth=2), ctx)
    assert [n.symbol_id for n in result.symbols] == ["B", "C", "D"]
    assert result.truncated and result.reasons == ("HOP_LIMIT",)
    assert seen[0].max_nodes == 200 and seen[0].max_examined_edges == 10000
    with pytest.raises(ValueError):
        tools.traverse(c.TraversalRequest(symbol_id="A", direction="callees", depth=3), ctx)


def test_build_requires_exact_grant_and_single_use(adapters):
    import anyio
    c, authority, ctx, _ = adapters
    calls = []
    class Provider:
        async def build_or_update(self, request, context):
            calls.append(request)
            return c.BuildResult(binding=c.SnapshotBinding.from_context(context), capabilities=("synthetic",),
                                 result_snapshot_hash=context.snapshot_hash)
    tools = provider_tools(ctx, Provider(), {"build"})
    req = c.BuildRequest(repo_path=str(ctx.repo_root))
    with pytest.raises(ValueError, match="grant"):
        anyio.run(tools.build, req, ctx)
    assert calls == []
    ctx = authority.grant(ctx, "build_or_update_graph", req.input_hash())
    assert anyio.run(tools.build, req, ctx).capabilities == ("synthetic",)
    with pytest.raises(ValueError, match="used"):
        anyio.run(tools.build, req, ctx)
    assert len(calls) == 1


def test_ranking_blocks_high_scoring_incomplete_and_ties(adapters):
    c, _, ctx, _ = adapters
    candidates = tuple(c.Candidate(candidate_id=i, diff="patch", diff_hash=c.digest("patch")) for i in ("z", "a", "bad"))
    req = c.RankRequest(candidates=candidates)
    (ctx.output_root / "rank.json").write_text("synthetic", encoding="utf-8")
    class Provider:
        def rank_candidates(self, request, context):
            return c.RankResult(binding=c.SnapshotBinding.from_context(context),
                                evidence=(c.EvidenceRef(path="rank.json", sha256=c.digest("synthetic")),), candidates=tuple(
                c.RankedCandidate(candidate_id=x.candidate_id, diff_hash=x.diff_hash, score=100 if x.candidate_id=="bad" else 1,
                                  checks=(c.NamedCheck(name="tests", status="ERROR" if x.candidate_id=="bad" else "PASS"),),
                                  eligible=True) for x in request.candidates))
    result = provider_tools(ctx, Provider(), {"ranking"}, required_checks=("tests",)).rank(req, ctx)
    assert [x.candidate_id for x in result.candidates] == ["a", "z", "bad"]
    assert result.candidates[-1].eligible is False
    with pytest.raises(ValueError): c.RankRequest(candidates=(candidates[0], candidates[0]))


@pytest.mark.parametrize("status", ["FAIL", "ERROR", "NOT_RUN"])
def test_required_nonpass_is_never_eligible(adapters, status):
    c, _, ctx, _ = adapters
    item = c.Candidate(candidate_id="bad", diff="x", diff_hash=c.digest("x"))
    class Provider:
        def rank_candidates(self, request, context):
            return c.RankResult(binding=c.SnapshotBinding.from_context(context), candidates=(
                c.RankedCandidate(candidate_id="bad", diff_hash=item.diff_hash, score=999, eligible=True,
                                  checks=(c.NamedCheck(name="tests", status=status),)),))
    result = provider_tools(ctx, Provider(), {"ranking"}, required_checks=("tests",)).rank(c.RankRequest(candidates=(item,)), ctx)
    assert not result.candidates[0].eligible


def test_diff_tests_missing_provider_never_consumes_grant(adapters):
    import anyio
    c, _, ctx, tools = adapters
    result = anyio.run(tools.tests, c.DiffRequest.from_diff("x"), ctx)
    assert result.status == "NOT_RUN" and result.receipt is None
    assert not (ctx.state_root / "used").exists()


@pytest.mark.parametrize("mutation", ["hash", "admitted", "cleanup", "double_apply"])
def test_diff_tests_reject_bad_lifecycle_receipt(adapters, mutation):
    import anyio
    c, authority, ctx, _ = adapters
    req = c.DiffRequest.from_diff("x")
    ctx = authority.grant(ctx, "run_relevant_tests", req.input_hash())
    class Provider:
        async def run_diff_tests(self, request, context):
            data = {"diff_hash": request.diff_hash, "admitted": True, "applied_count": 1, "executed": True, "cleaned": True,
                    "workspace": "candidate"}
            data.update({"hash": {"diff_hash": c.digest("other")}, "admitted": {"admitted": False},
                         "cleanup": {"cleaned": False}, "double_apply": {"applied_count": 2}}[mutation])
            return c.TestEvidence(binding=c.SnapshotBinding.from_context(context), diff_hash=request.diff_hash,
                                  status="PASS", scope=("synthetic",), coverage="COMPLETE", receipt=c.TestReceipt(**data))
    with pytest.raises(ValueError):
        anyio.run(provider_tools(ctx, Provider(), {"tests"}).tests, req, ctx)


@pytest.mark.parametrize("case", ["missing", "hash", "escape", "symlink"])
def test_evidence_files_are_consumed_and_verified(adapters, case):
    c, _, ctx, _ = adapters
    req = c.DiffRequest.from_diff("patch")
    (ctx.output_root / "details.json").write_text("synthetic", encoding="utf-8")
    ref = c.EvidenceRef(path="details.json", sha256=c.digest("synthetic"))
    if case == "missing": ref = ref.model_copy(update={"path": "missing.json"})
    if case == "hash": ref = ref.model_copy(update={"sha256": c.digest("other")})
    if case == "escape": ref = ref.model_copy(update={"path": "../repo/a.json"})
    if case == "symlink":
        # All platforms reject traversal aliases, even without symlink privileges.
        ref = ref.model_copy(update={"path": "details.json/../details.json"})
    class Provider:
        def verify_graph(self, request, context):
            return c.CheckEvidence(binding=c.SnapshotBinding.from_context(context), diff_hash=request.diff_hash,
                                   status="PASS", scope=("cycle",), coverage="COMPLETE", evidence=(ref,))
    with pytest.raises((ValueError, OSError)):
        provider_tools(ctx, Provider(), {"verification"}).verify(req, ctx)


def test_verify_reads_real_sidecar_and_rejects_unknown_pass(adapters):
    c, _, ctx, _ = adapters
    req = c.DiffRequest.from_diff("patch")
    (ctx.output_root / "details.json").write_text("synthetic", encoding="utf-8")
    result = c.CheckEvidence(binding=c.SnapshotBinding.from_context(ctx), diff_hash=req.diff_hash, status="PASS",
                             scope=("cycle",), coverage="COMPLETE", evidence=(c.EvidenceRef(path="details.json", sha256=c.digest("synthetic")),))
    class Provider:
        def verify_graph(self, request, context): return result
    tools = provider_tools(ctx, Provider(), {"verification"})
    assert tools.verify(req, ctx).status == "PASS"
    for changes in ({"coverage": "UNKNOWN"}, {"evidence": ()}, {"diff_hash": c.digest("wrong")}):
        original = result
        result = result.model_copy(update=changes)
        with pytest.raises(ValueError): tools.verify(req, ctx)
        result = original


def test_missing_ranking_policy_cannot_claim_eligible(adapters):
    c, _, ctx, _ = adapters
    req = c.RankRequest(candidates=(c.Candidate(candidate_id="a", diff="x", diff_hash=c.digest("x")),))
    class Provider:
        def rank_candidates(self, request, context):
            return c.RankResult(binding=c.SnapshotBinding.from_context(ctx), candidates=(
                c.RankedCandidate(candidate_id="a", diff_hash=c.digest("x"), checks=(), score=1, eligible=True),))
    assert not provider_tools(ctx, Provider(), {"ranking"}).rank(req, ctx).candidates[0].eligible


def test_test_provider_success_uses_private_workspace_and_persisted_receipt(adapters):
    import anyio
    c, authority, ctx, _ = adapters
    req = c.DiffRequest.from_diff("x")
    ctx = authority.grant(ctx, "run_relevant_tests", req.input_hash())
    events = []
    class Provider:
        async def run_diff_tests(self, request, context):
            root = context.lease_root / "candidate"
            root.mkdir(); events.append("admit")
            try:
                (root / "x.py").write_text("x=1", encoding="utf-8")
                events.extend(("apply_once", "execute"))
            finally:
                (root / "x.py").unlink(); root.rmdir(); events.append("cleanup")
            (context.output_root / "tests.json").write_text("synthetic", encoding="utf-8")
            return c.TestEvidence(binding=c.SnapshotBinding.from_context(context), diff_hash=request.diff_hash,
                status="PASS", scope=("synthetic",), coverage="COMPLETE",
                evidence=(c.EvidenceRef(path="tests.json", sha256=c.digest("synthetic")),),
                receipt=c.TestReceipt(workspace="candidate", diff_hash=request.diff_hash, admitted=True,
                                      applied_count=1, executed=True, cleaned=True))
    result = anyio.run(provider_tools(ctx, Provider(), {"tests"}).tests, req, ctx)
    assert result.status == "PASS" and events == ["admit", "apply_once", "execute", "cleanup"]
    assert list(ctx.repo_root.iterdir()) == []
    with pytest.raises(ValueError, match="used"):
        anyio.run(provider_tools(ctx, Provider(), {"tests"}).tests, req, ctx)


def test_async_provider_cancellation_propagates_after_cleanup(adapters):
    import anyio
    c, authority, ctx, _ = adapters
    req = c.DiffRequest.from_diff("x")
    ctx = authority.grant(ctx, "run_relevant_tests", req.input_hash())
    cleaned = []
    class Provider:
        async def run_diff_tests(self, request, context):
            root = context.lease_root / "candidate"; root.mkdir()
            try:
                scope.cancel()
                await anyio.lowlevel.checkpoint()
            finally:
                root.rmdir(); cleaned.append(True)
    async def run():
        nonlocal scope
        with anyio.CancelScope() as scope:
            await provider_tools(ctx, Provider(), {"tests"}).tests(req, ctx)
            pytest.fail("Cancellation must not return success")
    scope = None
    anyio.run(run)
    assert cleaned == [True]


def test_invalid_heavy_provider_rejected_at_bootstrap(adapters):
    from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
    c, _, ctx, _ = adapters
    class Provider:
        def run_diff_tests(self, request, context): return None
    record = ProviderBinding(Provider(), c.SnapshotBinding.from_context(ctx), frozenset({"tests"}), synthetic=True)
    with pytest.raises(ValueError, match="lifecycle"):
        ProviderRegistry((record,), test_only=True)


@pytest.mark.parametrize("field,value", [("score", True), ("score", float("nan")), ("score", float("inf"))])
def test_scores_reject_non_measurements(adapters, field, value):
    c, _, _, _ = adapters
    with pytest.raises(ValueError):
        c.RankedCandidate(candidate_id="a", diff_hash=c.digest("x"), checks=(), **{field: value})


def test_no_persisted_rank_evidence_cannot_claim_eligible(adapters):
    c, _, ctx, _ = adapters
    req = c.RankRequest(candidates=(c.Candidate(candidate_id="a", diff="x", diff_hash=c.digest("x")),))
    class Provider:
        def rank_candidates(self, request, context):
            return c.RankResult(binding=c.SnapshotBinding.from_context(ctx), candidates=(
                c.RankedCandidate(candidate_id="a", diff_hash=c.digest("x"), checks=(c.NamedCheck(name="tests", status="PASS"),),
                                  score=1, eligible=True),))
    assert not provider_tools(ctx, Provider(), {"ranking"}, required_checks=("tests",)).rank(req, ctx).candidates[0].eligible


def test_async_builds_same_repo_do_not_reenter_thread_local_os_lock(adapters):
    import anyio
    c, authority, ctx, _ = adapters
    request = c.BuildRequest(repo_path=str(ctx.repo_root))
    contexts = [authority.grant(ctx, "build_or_update_graph", request.input_hash()) for _ in range(2)]
    entered = []
    async def run():
        first_ready, second_attempted, release = anyio.Event(), anyio.Event(), anyio.Event()
        class Provider:
            async def build_or_update(self, request, context):
                entered.append(context.grants[-1].grant_id)
                first_ready.set()
                await release.wait()
                return c.BuildResult(binding=c.SnapshotBinding.from_context(context), result_snapshot_hash=context.snapshot_hash,
                                     capabilities=("synthetic",))
        tools = provider_tools(ctx, Provider(), {"build"})
        async def second():
            second_attempted.set()
            await tools.build(request, contexts[1])
        async with anyio.create_task_group() as group:
            group.start_soon(tools.build, request, contexts[0])
            await first_ready.wait()
            group.start_soon(second)
            await second_attempted.wait()
            assert len(entered) == 1, "Async tasks reentered the same thread-local OS lock"
            release.set()
    anyio.run(run)
    assert len(entered) == 2


def test_write_provider_timeout_has_cleanup_receipt(adapters):
    import json
    from dataclasses import replace

    import anyio

    from vgar.mcp.proposal.context import SecurityLimits
    c, authority, ctx, _ = adapters
    ctx = authority._sign(replace(ctx, limits=SecurityLimits(worker_seconds=0.05)))
    req = c.BuildRequest(repo_path=str(ctx.repo_root))
    ctx = authority.grant(ctx, "build_or_update_graph", req.input_hash())
    cleaned = []
    class Provider:
        async def build_or_update(self, request, context):
            try:
                await anyio.Event().wait()
            finally:
                cleaned.append(True)
    tools = provider_tools(ctx, Provider(), {"build"})
    async def run():
        with anyio.fail_after(1):
            await tools.build(req, ctx)
    with pytest.raises(TimeoutError):
        anyio.run(run)
    assert cleaned == [True]
    receipt = json.loads(next(ctx.output_root.glob("adapter-*.json")).read_text(encoding="utf-8"))
    assert receipt["status"] == "ERROR" and receipt["cleanup_observed"] is True
    assert receipt["operation"] == "build_or_update_graph"


def test_false_cleanup_receipt_cannot_hide_leaked_workspace(adapters):
    import anyio
    c, authority, ctx, _ = adapters
    request = c.DiffRequest.from_diff("x")
    ctx = authority.grant(ctx, "run_relevant_tests", request.input_hash())
    class Provider:
        async def run_diff_tests(self, request, context):
            (ctx.lease_root / "leaked").mkdir()
            (ctx.lease_root / "leaked/modified.py").write_text("x=1", encoding="utf-8")
            (ctx.output_root / "tests.json").write_text("synthetic", encoding="utf-8")
            return c.TestEvidence(binding=c.SnapshotBinding.from_context(ctx), diff_hash=request.diff_hash,
                status="PASS", scope=("synthetic",), coverage="COMPLETE",
                evidence=(c.EvidenceRef(path="tests.json", sha256=c.digest("synthetic")),),
                receipt=c.TestReceipt(workspace="different-absent-path", diff_hash=request.diff_hash,
                                      admitted=True, applied_count=1, executed=True, cleaned=True))
    with pytest.raises(ValueError, match="cleanup|workspace"):
        anyio.run(provider_tools(ctx, Provider(), {"tests"}).tests, request, ctx)


def test_queued_build_revalidates_source_before_provider_or_grant(adapters):
    import anyio
    c, authority, ctx, _ = adapters
    request = c.BuildRequest(repo_path=str(ctx.repo_root))
    contexts = [authority.grant(ctx, "build_or_update_graph", request.input_hash()) for _ in range(2)]
    entered, errors = [], []
    async def run():
        ready, second_attempted, release = anyio.Event(), anyio.Event(), anyio.Event()
        class Provider:
            async def build_or_update(self, request, context):
                entered.append(True); ready.set()
                await release.wait()
                return c.BuildResult(binding=c.SnapshotBinding.from_context(context), result_snapshot_hash=context.snapshot_hash,
                                     capabilities=("synthetic",))
        tools = provider_tools(ctx, Provider(), {"build"})
        async def job(index):
            if index: second_attempted.set()
            try:
                await tools.build(request, contexts[index])
            except ValueError as error: errors.append(str(error))
        async with anyio.create_task_group() as group:
            group.start_soon(job, 0)
            await ready.wait()
            group.start_soon(job, 1)
            await second_attempted.wait()
            (ctx.repo_root / "drift.py").write_text("x=1", encoding="utf-8")
            release.set()
    anyio.run(run)
    assert len(entered) == 1 and len(errors) == 2
    assert not (ctx.state_root / "used" / contexts[1].grants[-1].grant_id).exists()


def test_external_repo_lock_contention_keeps_event_loop_responsive(adapters):
    import threading

    import anyio

    from vgar.mcp.proposal.locking import lock_key, locked
    c, authority, ctx, _ = adapters
    request = c.BuildRequest(repo_path=str(ctx.repo_root))
    ctx = authority.grant(ctx, "build_or_update_graph", request.input_hash())
    acquired, release = threading.Event(), threading.Event()
    order = []
    def holder():
        with locked(ctx.state_root / "locks" / ("repo-" + lock_key(ctx.repo_root) + ".lock")):
            acquired.set()
            release.wait(3)
    thread = threading.Thread(target=holder)
    thread.start()
    assert acquired.wait(5)
    class Provider:
        async def build_or_update(self, request, context):
            order.append("provider")
            return c.BuildResult(binding=c.SnapshotBinding.from_context(context), result_snapshot_hash=context.snapshot_hash,
                                 capabilities=("synthetic",))
    async def run():
        attempted = anyio.Event()
        async def job():
            attempted.set()
            await provider_tools(ctx, Provider(), {"build"}).build(request, ctx)
        async with anyio.create_task_group() as group:
            group.start_soon(job)
            await attempted.wait()
            order.append("heartbeat")
            release.set()
    try:
        anyio.run(run)
    finally:
        release.set(); thread.join(timeout=5)
    assert order == ["heartbeat", "provider"] and not thread.is_alive()


@pytest.mark.parametrize("mutation", ["ignored_cache", "delete_lease_file"])
def test_build_cannot_change_ignored_or_preexisting_lease_entries(adapters, mutation):
    import anyio
    c, authority, ctx, _ = adapters
    (ctx.lease_root / ".pytest_cache").mkdir()
    (ctx.lease_root / "session.json").write_text("preserve", encoding="utf-8")
    request = c.BuildRequest(repo_path=str(ctx.repo_root))
    ctx = authority.grant(ctx, "build_or_update_graph", request.input_hash())
    class Provider:
        async def build_or_update(self, request, context):
            if mutation == "ignored_cache":
                (ctx.lease_root / ".pytest_cache/new.txt").write_text("leak", encoding="utf-8")
            else:
                (ctx.lease_root / "session.json").unlink()
            return c.BuildResult(binding=c.SnapshotBinding.from_context(ctx), result_snapshot_hash=ctx.snapshot_hash,
                                 capabilities=("synthetic",))
    with pytest.raises(ValueError, match="cleanup"):
        anyio.run(provider_tools(ctx, Provider(), {"build"}).build, request, ctx)


def test_adapter_modules_exist():
    for name in ("contracts", "ports", "tools"):
        assert importlib.util.find_spec("vgar.mcp.proposal." + name), name
