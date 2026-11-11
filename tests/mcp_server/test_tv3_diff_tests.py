"""Real fixture tests for the TV3 execution adapter. No target or diff is model-selected."""
import json
import shutil
import sys
import threading
from pathlib import Path

import anyio
import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import bind_context, source_inventory_hash
from vgar.mcp.proposal.diff_tests_provider import DiffTestsProvider
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools
from vgar.repair.contracts import RepairPolicy, RepairTask
from vgar.repair.evidence import digest
from vgar.repair.executor import run_bounded
from vgar.repair.semantic_contract import ContractExample, SemanticContract

ROOT = Path(__file__).resolve().parents[2]
TASK = "single_file_login"
FAILURE = "tests/test_auth.py::test_login_rejects_whitespace"
REGRESSION = "tests/test_auth.py::test_login_accepts_name"
WORKSPACE = "ev3"
DIFF = "--- a/auth.py\n+++ b/auth.py\n@@ -2 +2 @@\n-    return bool(value)\n+    return bool(value.strip())\n"
BAD = DIFF.replace("bool(value.strip())", "False")


@pytest.fixture
def job(bound):
    authority, seed = bound
    shutil.copytree(ROOT / "examples/m2/snapshots" / TASK, seed.repo_root, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    version = PythonGraphBuilder(repo_key="fixture/login", repository_revision="fixture-v1").build(seed.repo_root)["graph_version"]
    task = RepairTask(task_id=TASK, issue_text="Reject whitespace-only usernames", source_repo=seed.repo_root,
                      repo_key="fixture/login", revision="fixture-v1", graph_version=version, bundle_directory=seed.output_root,
                      failing_selectors=(FAILURE,), fallback_scope=("tests",), allowed_source_paths=("auth.py",), trusted_fixture=True)
    ctx = bind_context(authority, repo_root=seed.repo_root, lease_root=seed.lease_root, output_root=seed.output_root,
                       request_id=seed.request_id, run_id=seed.run_id, task_id=task.task_id, snapshot_hash=version,
                       source_hash=source_inventory_hash(seed.repo_root), config_hash=seed.config_hash, deadline=seed.deadline)
    binding = c.SnapshotBinding.from_context(ctx)
    provider = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace=WORKSPACE,
                                 approved_fixture_diffs=(digest(DIFF), digest(BAD)))
    registry = ProviderRegistry((ProviderBinding(provider, binding, frozenset({"tests"}),
                                                 lifecycle="guarded-v1", candidate_workspace=WORKSPACE),))
    return CoreTools(registry), provider, task, authority, ctx


@pytest.mark.parametrize(("diff", "verdict", "regression"), [(DIFF, "PASS", "PASS"), (BAD, "FAIL", "FAIL")],
                         ids=["fix", "regression"])
def test_real_patch_apply_and_transition(job, diff, verdict, regression):
    tools, _, _, authority, ctx = job
    request = c.DiffRequest.from_diff(diff)
    grant = authority.grant(ctx, "run_relevant_tests", request.input_hash())
    result = anyio.run(tools.tests, request, grant)
    assert result.status == verdict and result.coverage == "COMPLETE"
    assert result.receipt.applied_count == 1 and result.receipt.executed and result.receipt.cleaned
    ref, = result.evidence
    raw = (ctx.output_root / ref.path).read_bytes()
    assert digest(raw) == ref.sha256
    evidence = json.loads(raw)
    assert evidence["diff_hash"] == request.diff_hash and evidence["receipt"] == result.receipt.model_dump()
    assert evidence["baseline"]["outcomes"] == {FAILURE: "FAIL", REGRESSION: "PASS"}
    assert evidence["candidate"]["outcomes"] == {FAILURE: "PASS", REGRESSION: regression}
    assert evidence["baseline"]["junit_sha256"] and evidence["candidate"]["junit_sha256"]
    assert evidence["coverage_count"] == "NOT_MEASURED"
    assert not list(ctx.lease_root.iterdir()) and source_inventory_hash(ctx.repo_root) == ctx.source_hash
    with pytest.raises(ValueError, match="already used"):
        anyio.run(tools.tests, request, grant)
    assert len(list(ctx.output_root.glob("tv3-ev3-*.json"))) == 1


def test_no_grant_or_unapproved_diff_never_executes(job):
    tools, _, _, authority, ctx = job
    with pytest.raises(ValueError, match="write grant"):
        anyio.run(tools.tests, c.DiffRequest.from_diff(DIFF), ctx)
    request = c.DiffRequest.from_diff(DIFF + "\n")
    with pytest.raises(ValueError, match="not approved"):
        anyio.run(tools.tests, request, authority.grant(ctx, "run_relevant_tests", request.input_hash()))
    assert not list(ctx.lease_root.iterdir()) and not list(ctx.output_root.glob("tv3-ev3-*.json"))


def test_preexisting_candidate_workspace_is_preserved(job):
    tools, _, _, authority, ctx = job
    workspace = ctx.lease_root / WORKSPACE
    workspace.mkdir()
    marker = workspace / "owned-by-host.txt"
    marker.write_bytes(b"leave untouched")
    request = c.DiffRequest.from_diff(DIFF)
    with pytest.raises(FileExistsError):
        anyio.run(tools.tests, request, authority.grant(ctx, "run_relevant_tests", request.input_hash()))
    assert marker.read_bytes() == b"leave untouched"
    assert not list(ctx.output_root.glob("tv3-ev3-*.json"))


@pytest.mark.parametrize(("diff", "expected_bob", "expected"), [
    (DIFF, True, "PASS"),
    (DIFF.replace("bool(value.strip())", "value == 'alice'"), True, "FAIL"),
    (DIFF, False, "NOT_RUN"),
], ids=["good", "overfit", "unqualified-baseline"])
def test_host_contract_catches_semantic_regression(job, diff, expected_bob, expected):
    _, _, task, authority, ctx = job
    binding = c.SnapshotBinding.from_context(ctx)
    contract = SemanticContract(examples=(ContractExample(case_id="valid_bob", module="auth", function="login",
                                                         args=("bob",), expected=expected_bob),))
    provider = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace=WORKSPACE,
                                 approved_fixture_diffs=(digest(diff),), semantic_contract=contract)
    tools = CoreTools(ProviderRegistry((ProviderBinding(provider, binding, frozenset({"tests"}),
                                                       lifecycle="guarded-v1", candidate_workspace=WORKSPACE),)))
    request = c.DiffRequest.from_diff(diff)
    result = anyio.run(tools.tests, request, authority.grant(ctx, "run_relevant_tests", request.input_hash()))
    assert result.status == expected, result
    record = json.loads((ctx.output_root / result.evidence[0].path).read_bytes())
    assert digest(record["semantic_contract"]["definition"]) == record["semantic_contract"]["sha256"]
    assert result.receipt.cleaned
    if expected == "NOT_RUN":
        assert record["baseline"]["outcomes"]["vgar_contract::valid_bob"] == "FAIL"
        assert result.receipt.applied_count == 0 and not result.receipt.executed
        assert result.reasons == ("BASELINE_CONTRACT_NOT_QUALIFIED",)
    else:
        assert record["baseline"]["outcomes"]["vgar_contract::valid_bob"] == "PASS"
        assert record["candidate"]["outcomes"]["vgar_contract::valid_bob"] == expected
        assert result.receipt.applied_count == 1


def test_unqualified_baseline_does_not_apply_candidate(job):
    _, _, task, authority, ctx = job
    wrong_failure = task.model_copy(update={"failing_selectors": (REGRESSION,)})
    binding = c.SnapshotBinding.from_context(ctx)
    provider = DiffTestsProvider(wrong_failure, RepairPolicy(), binding, candidate_workspace=WORKSPACE,
                                 approved_fixture_diffs=(digest(DIFF),))
    record = ProviderBinding(provider, binding, frozenset({"tests"}), lifecycle="guarded-v1", candidate_workspace=WORKSPACE)
    tools = CoreTools(ProviderRegistry((record,)))
    request = c.DiffRequest.from_diff(DIFF)
    result = anyio.run(tools.tests, request, authority.grant(ctx, "run_relevant_tests", request.input_hash()))
    assert result.status == "NOT_RUN" and result.reasons == ("BASELINE_NOT_QUALIFIED",)
    assert result.receipt.applied_count == 0 and not result.receipt.executed and result.receipt.cleaned
    assert not list(ctx.lease_root.iterdir())


def test_cancellation_does_not_return_before_workspace_cleanup(job, monkeypatch):
    tools, provider, _, authority, ctx = job
    request = c.DiffRequest.from_diff(DIFF)
    grant = authority.grant(ctx, "run_relevant_tests", request.input_hash())
    started = threading.Event()

    def measure(workspace, patch, state, end, stop, guard, output_cap):
        (workspace / "marker").write_text("owned", encoding="utf-8")
        started.set()
        assert stop.wait(10)
        guard()

    monkeypatch.setattr(provider, "_measure", measure)

    async def run():
        with anyio.fail_after(15):
            async with anyio.create_task_group() as group:
                group.start_soon(tools.tests, request, grant)
                assert await anyio.to_thread.run_sync(started.wait, 10)
                group.cancel_scope.cancel()

    anyio.run(run)
    assert not list(ctx.lease_root.iterdir()) and not list(ctx.output_root.glob("tv3-ev3-*.json"))
    adapter, = ctx.output_root.glob("adapter-*.json")
    assert json.loads(adapter.read_bytes())["cleanup_observed"] is True


def test_bounded_runner_interrupts_child(tmp_path):
    event = threading.Event()
    trigger = threading.Timer(0.5, event.set)
    trigger.start()
    try:
        result = run_bounded((sys.executable, "-c", "import time; time.sleep(8)"), tmp_path, 10, cancel_event=event)
    finally:
        trigger.cancel()
    assert result["cancelled"] and result["status"] == "ERROR" and not result["complete"]
    assert result["duration_ms"] < 5000


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
def test_ev3_over_official_mcp_stdio(job, mode):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    _, _, task, _, ctx = job
    root = ctx.repo_root.parent
    (root / "task.json").write_text(task.model_dump_json(), encoding="utf-8")
    params = StdioServerParameters(
        command=sys.executable, args=["-B", str(ROOT / "tests/fixtures/mcp_server/tv3_diff_tests_server.py"), str(root), digest(DIFF)],
        env={"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
             "PYTHON_DOTENV_DISABLED": "1"},
    )

    async def run():
        with anyio.fail_after(45):
            async with Client(params, mode=mode) as client:
                result = await client.call_tool("run_relevant_tests", {"diff": DIFF})
                envelope = result.structured_content or json.loads(result.content[0].text)
                assert not result.is_error and envelope["status"] == "PASS", envelope
                data = envelope["data"]
                assert data["status"] == "PASS" and data["diff_hash"] == digest(DIFF)
                assert data["receipt"]["applied_count"] == 1 and data["receipt"]["cleaned"]
                ref, = data["evidence"]
                assert digest((ctx.output_root / ref["path"]).read_bytes()) == ref["sha256"]

    anyio.run(run)
    assert not list(ctx.lease_root.iterdir())
