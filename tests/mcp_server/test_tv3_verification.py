"""EV-2 checks with a real sealed Python snapshot and original diff bytes."""
import json
import sys
from pathlib import Path

import anyio
import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.storage_capabilities import (
    SnapshotGraphStore,
    SQLiteSnapshotStorage,
    legacy_profile,
)
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import bind_context, source_inventory_hash
from vgar.mcp.proposal.graph_jobs import resolver_fingerprint
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.resources import ResourceBoundaryError, ResourceReader
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.proposal.verification_provider import StaticVerificationProvider
from vgar.repair.evidence import digest
from vgar.repair.patch import PatchPolicy

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = ("src/a.py", "src/b.py")
SAFE = "--- a/src/a.py\n+++ b/src/a.py\n@@ -2 +2 @@\n-    return 1\n+    return 2\n"
BREAK_API = "--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-def value():\n+def value(required):\n"
CYCLE = "--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1,2 @@\n+import b as _b\n def value():\n"


@pytest.fixture
def verifier(bound):
    authority, ctx = bound
    (ctx.repo_root / "src").mkdir()
    (ctx.repo_root / ALLOWED[0]).write_text("def value():\n    return 1\n", encoding="utf-8")
    (ctx.repo_root / ALLOWED[1]).write_text(
        "from a import value\nraise RuntimeError('Static checker must never execute target code')\n", encoding="utf-8",
    )
    doc = PythonGraphBuilder(repo_key="tv3/fixture", repository_revision="baseline").build(ctx.repo_root)
    source_hash = source_inventory_hash(ctx.repo_root)
    profile = legacy_profile(resolver_hash=resolver_fingerprint(), profile_hash=c.digest("static fixture"))
    storage = SQLiteSnapshotStorage(ctx.output_root, profiles=(profile,))
    identity = storage.identity(doc, source_inventory_hash=source_hash)

    def bind(snapshot_hash, config_hash, task=ctx.task_id):
        return bind_context(authority, repo_root=ctx.repo_root, lease_root=ctx.lease_root,
                            output_root=ctx.output_root, request_id=ctx.request_id, run_id=ctx.run_id, task_id=task,
                            source_hash=source_hash, snapshot_hash=snapshot_hash, config_hash=config_hash,
                            deadline=ctx.deadline)

    write_ctx = bind(identity.snapshot_id, profile.profile_hash)
    manifest = storage.ingest(doc, context=authority.grant(write_ctx, "storage_ingest", identity.snapshot_id))
    store = SnapshotGraphStore(manifest, graph_version=identity.graph_version, profiles=(profile,))
    provider = StaticVerificationProvider(store, PatchPolicy(ALLOWED, ("tests",)))
    read_ctx = bind(identity.graph_version, provider.config_hash)
    registry = ProviderRegistry((ProviderBinding(provider, c.SnapshotBinding.from_context(read_ctx),
                                                 frozenset({"verification", "resource_baseline"})),))
    return CoreTools(registry), provider, store, read_ctx, bind


@pytest.mark.parametrize(("diff", "status", "reason", "coverage"), [
    (SAFE, "PASS", None, "COMPLETE"),
    (BREAK_API, "FAIL", "API_SIGNATURE_INCOMPATIBLE", "COMPLETE"),
    (CYCLE, "FAIL", "NEW_IMPORT_CYCLE", "COMPLETE"),
    (SAFE.replace("return 1", "return 999"), "FAIL", "PATCH_BASELINE_MISMATCH", "PARTIAL"),
    (SAFE.replace("return 2", "return ("), "FAIL", "CANDIDATE_SYNTAX_ERROR", "PARTIAL"),
    (SAFE.replace("src/a.py", "../a.py"), "FAIL", "PATCH_POLICY_REJECTED", "PARTIAL"),
    (SAFE.replace("return 2", "return 2\n+__all__ = list()").replace("+2 @@", "+2,2 @@"),
     "NOT_RUN", "API_DYNAMIC_EXPORTS", "PARTIAL"),
])
def test_static_patch_results_bind_sidecar_and_preserve_source(verifier, diff, status, reason, coverage):
    tools, _, store, ctx, _ = verifier
    request = c.DiffRequest.from_diff(diff)
    result = tools.verify(request, ctx)
    assert result.status == status and result.coverage == coverage
    if reason:
        assert reason in result.reasons
    ref, = result.evidence
    raw = (ctx.output_root / ref.path).read_bytes()
    assert digest(raw) == ref.sha256
    proof = json.loads(raw)
    assert proof["binding"] == c.SnapshotBinding.from_context(ctx).model_dump()
    assert proof["snapshot_id"] == store.identity.snapshot_id and proof["diff_hash"] == request.diff_hash
    assert (proof["status"], proof["coverage"]) == (result.status, result.coverage)
    assert proof["limitations"]
    if status == "PASS":
        assert proof["candidate_graph_version"] != store.identity.graph_version
        assert {name: check["status"] for name, check in proof["checks"].items()} == {
            "api": "PASS", "structural": "PASS", "schema": "PASS",
            "source_imports": "PASS",
        }
    assert source_inventory_hash(ctx.repo_root) == ctx.source_hash
    assert not list(ctx.state_root.glob("tv3-ev2-*")) and not list(ctx.lease_root.iterdir())


def test_snapshot_config_and_source_drift_fail_before_publishing(verifier):
    tools, provider, store, ctx, bind = verifier
    request = c.DiffRequest.from_diff(SAFE)
    with pytest.raises(ValueError, match="snapshot/source/config"):
        provider.verify_graph(request, bind(store.identity.snapshot_id, ctx.config_hash))
    with pytest.raises(ValueError, match="snapshot/source/config"):
        provider.verify_graph(request, bind(ctx.snapshot_hash, c.digest("other config")))
    (ctx.repo_root / ALLOWED[0]).write_text("def value():\n    return 9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory changed"):
        tools.verify(request, ctx)
    assert not list(ctx.output_root.glob("tv3-ev2-*.json"))


def test_configured_rules_only_reject_new_violations_and_replay_is_stable(verifier):
    _, _, store, ctx, bind = verifier
    provider = StaticVerificationProvider(store, PatchPolicy(ALLOWED, ("tests",)), structural_policy={
        "repo_key": "tv3/fixture", "forbidden_imports": [{"source": "b", "target": "a"}, {"source": "a", "target": "b"}],
        "layers": {"base": ["a"], "service": ["b"]}, "allowed_layer_imports": {"base": [], "service": ["base"]},
    })
    ctx = bind(ctx.snapshot_hash, provider.config_hash)
    safe = c.DiffRequest.from_diff(SAFE)
    reports = [provider.verify_graph(safe, ctx) for _ in range(2)]
    assert all(report.status == "PASS" for report in reports)
    proofs = [json.loads((ctx.output_root / report.evidence[0].path).read_bytes()) for report in reports]
    assert proofs[0] == proofs[1]
    rejected = provider.verify_graph(c.DiffRequest.from_diff(CYCLE), ctx)
    assert rejected.status == "FAIL"
    assert set(rejected.reasons) == {"NEW_IMPORT_CYCLE", "FORBIDDEN_IMPORT", "LAYER_VIOLATION"}


def test_baseline_resource_is_hash_bound_and_cannot_cross_task(verifier):
    tools, _, store, ctx, bind = verifier
    reader = ResourceReader(tools, SQLiteGraphService(store), AuditLogger(ctx.output_root / "audit.jsonl"))
    uri = "vgar://evidence/baseline"
    payload = json.loads(reader.read(uri, context=ctx))
    metadata = payload["_resource"]
    assert metadata["availability"] == "PARTIAL" and "BASELINE_TESTS_NOT_MEASURED" in metadata["reasons"]
    assert payload["snapshot_id"] == store.identity.snapshot_id and payload["python_file_count"] == 2
    ref, = metadata["evidence"]
    raw = (ctx.output_root / ref["path"]).read_bytes()
    assert digest(raw) == ref["sha256"]
    assert json.loads(raw)["binding"] == c.SnapshotBinding.from_context(ctx).model_dump()
    assert "def value" not in raw.decode("utf-8")
    wrong_task = bind(ctx.snapshot_hash, ctx.config_hash, task="other")
    with pytest.raises(ResourceBoundaryError, match="binding mismatch"):
        reader.read(uri, context=wrong_task)
    assert len(list(ctx.output_root.glob("tv3-baseline-*.json"))) == 1


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
def test_static_provider_through_sdk2_stdio(verifier, mode):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    _, _, store, ctx, _ = verifier
    params = StdioServerParameters(
        command=sys.executable,
        args=["-B", str(ROOT / "tests/fixtures/mcp_server/tv3_verification_server.py"),
              str(ctx.repo_root.parent), str(store.manifest_path), ctx.snapshot_hash, store.identity.profile_hash],
        env={"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
             "PYTHON_DOTENV_DISABLED": "1", "VGAR_GRAPH_BACKEND": "demo"},
    )

    async def run():
        with anyio.fail_after(45):
            async with Client(params, mode=mode) as client:
                for diff, expected in ((SAFE, "PASS"), (BREAK_API, "FAIL"), (CYCLE, "FAIL")):
                    response = await client.call_tool("verify_patch_graph_constraints", {"diff": diff})
                    assert not response.is_error
                    envelope = response.structured_content or json.loads(response.content[0].text)
                    assert envelope["status"] == "PASS", envelope
                    data = envelope["data"]
                    assert data["status"] == expected and data["diff_hash"] == c.digest(diff)
                    assert data["binding"]["snapshot_hash"] == ctx.snapshot_hash
                    ref, = data["evidence"]
                    assert digest((ctx.output_root / ref["path"]).read_bytes()) == ref["sha256"]
                result = await client.read_resource("vgar://evidence/baseline")
                baseline = json.loads(result.contents[0].text)
                assert baseline["snapshot_id"] == store.identity.snapshot_id
                assert baseline["_resource"]["availability"] == "PARTIAL"
                ref, = baseline["_resource"]["evidence"]
                assert digest((ctx.output_root / ref["path"]).read_bytes()) == ref["sha256"]

    anyio.run(run)
