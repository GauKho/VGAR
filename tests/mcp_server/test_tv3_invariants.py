"""L5-1/L5-2 inside run_relevant_tests (EV-3): invariants learned on the baseline run, checked on the candidate."""
import json
import shutil
import time
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
from vgar.repair.daikon import DaikonConfig
from vgar.repair.evidence import digest
from vgar.repair.invariants import (
    InvariantSettings,
    compute_semantic_invariants,
    fit_record,
    not_run_record,
)

FAILURE = "tests/test_auth.py::test_login_rejects_whitespace"
WORKSPACE = "ev3"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "invariants" / "login"
FIX = "--- a/auth.py\n+++ b/auth.py\n@@ -2 +2 @@\n-    return bool(value)\n+    return bool(value.strip())\n"
BAD = FIX.replace("bool(value.strip())", "False")


@pytest.fixture
def setup(bound):
    authority, seed = bound
    shutil.copytree(FIXTURE, seed.repo_root, dirs_exist_ok=True)  # trusted fixture "login_invariants"
    version = PythonGraphBuilder(repo_key="fixture/login", repository_revision="fixture-v1").build(seed.repo_root)["graph_version"]
    task = RepairTask(task_id="login_invariants", issue_text="Reject whitespace-only usernames", source_repo=seed.repo_root,
                      repo_key="fixture/login", revision="fixture-v1", graph_version=version,
                      bundle_directory=seed.output_root, failing_selectors=(FAILURE,), fallback_scope=("tests",),
                      allowed_source_paths=("auth.py",), trusted_fixture=True)
    ctx = bind_context(authority, repo_root=seed.repo_root, lease_root=seed.lease_root, output_root=seed.output_root,
                       request_id=seed.request_id, run_id=seed.run_id, task_id=task.task_id, snapshot_hash=version,
                       source_hash=source_inventory_hash(seed.repo_root), config_hash=seed.config_hash, deadline=seed.deadline)
    return authority, ctx, task


def _run(setup, diff, invariants):
    authority, ctx, task = setup
    binding = c.SnapshotBinding.from_context(ctx)
    provider = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace=WORKSPACE,
                                 approved_fixture_diffs=(digest(FIX), digest(BAD)), invariants=invariants)
    tools = CoreTools(ProviderRegistry((ProviderBinding(provider, binding, frozenset({"tests"}),
                                                       lifecycle="guarded-v1", candidate_workspace=WORKSPACE),)))
    request = c.DiffRequest.from_diff(diff)
    result = anyio.run(tools.tests, request, authority.grant(ctx, "run_relevant_tests", request.input_hash()))
    return result, json.loads((ctx.output_root / result.evidence[0].path).read_bytes()), ctx


def test_invariants_off_by_default_record_unchanged(setup):
    result, record, _ = _run(setup, FIX, None)
    assert result.status == "PASS" and "semantic_invariants" not in record


@pytest.mark.parametrize(("diff", "tests", "invariants"), [(FIX, "PASS", "PASS"), (BAD, "FAIL", "FAIL")],
                         ids=["fix", "regression"])
def test_fix_passes_and_regression_fails_invariants(setup, diff, tests, invariants):
    result, record, _ = _run(setup, diff, InvariantSettings())
    semantic = record["semantic_invariants"]
    assert result.status == tests and semantic["status"] == invariants, semantic
    assert semantic["engine"] == "python-fallback" and "LIKELY_INVARIANTS_NOT_PROOF" in semantic["limitations"]
    assert semantic["learned"] > 0
    if invariants == "FAIL":
        assert any("auth.py" in v["node_id"] and "return" in v["invariant"] for v in semantic["violations"])


def test_workspace_inventory_unchanged_with_tracing(setup):
    result, record, ctx = _run(setup, FIX, InvariantSettings())
    assert result.status == "PASS" and record["status"] == "PASS" and result.receipt.cleaned
    assert source_inventory_hash(ctx.repo_root) == ctx.source_hash and not list(ctx.lease_root.iterdir())


def test_docker_admission_gives_trace_output_unavailable():
    record = not_run_record("TRACE_OUTPUT_UNAVAILABLE")
    assert (record["status"], record["reasons"]) == ("NOT_RUN", ["TRACE_OUTPUT_UNAVAILABLE"])
    assert "LIKELY_INVARIANTS_NOT_PROOF" in record["limitations"]


def test_violation_list_capped_under_byte_limit():
    violations = [{"program_point": f"m.f{i}(x):::EXIT", "node_id": "n", "invariant": "x == 1", "test": "t"}
                  for i in range(10_000)]
    record = fit_record({**not_run_record("X"), "status": "FAIL", "violations": violations,
                         "violations_total": 10_000}, 20_000)
    assert len(json.dumps(record)) <= 20_000 and record["violations_total"] == 10_000
    assert 0 < len(record["violations"]) < 10_000 and record["status"] == "FAIL"


def test_daikon_failure_falls_back_with_reason(tmp_path):
    from invariant_helpers import run_variant

    base, outcomes = run_variant("base", tmp_path)
    cand, _ = run_variant("M5_product_name_upper", tmp_path)
    settings = InvariantSettings(daikon=DaikonConfig(jar=tmp_path / "missing.jar", java_home=tmp_path), repo_key="shop")
    record = compute_semantic_invariants(base, cand, outcomes, settings, time.monotonic() + 60)
    assert record["engine"] == "python-fallback" and record["status"] == "FAIL"
    assert any(reason.startswith("daikon unavailable") for reason in record["reasons"])


def test_no_baseline_passing_test_is_not_run(tmp_path):
    from invariant_helpers import run_variant

    base, outcomes = run_variant("base", tmp_path)
    record = compute_semantic_invariants(base, base, {k: "FAIL" for k in outcomes}, InvariantSettings(),
                                         time.monotonic() + 60)
    assert (record["status"], record["reasons"]) == ("NOT_RUN", ["NO_BASELINE_PASSING_TEST"])


def test_invariant_analysis_error_keeps_test_verdict(setup, monkeypatch):
    import vgar.mcp.proposal.diff_tests_provider as provider_module

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(provider_module, "compute_semantic_invariants", boom)
    result, record, _ = _run(setup, FIX, InvariantSettings())
    assert result.status == "PASS" and record["status"] == "PASS"
    semantic = record["semantic_invariants"]
    assert (semantic["status"], semantic["reasons"]) == ("ERROR", ["INVARIANT_ANALYSIS_ERROR:OSError"])


def test_profile_hash_unchanged_when_invariants_off(setup):
    from vgar.graph.storage_capabilities import canonical_bytes

    _, ctx, task = setup
    binding = c.SnapshotBinding.from_context(ctx)
    provider = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace=WORKSPACE,
                                 approved_fixture_diffs=(digest(FIX),))
    legacy = digest(canonical_bytes({"task": provider._task.model_dump(mode="json"), "policy": provider._policy.model_dump(mode="json"),
                                     "admission": None, "fixture_diff_hashes": [digest(FIX)], "semantic_contract": None}))
    assert provider._profile_hash == legacy


def test_trusted_fixture_bytes_are_pinned_against_line_ending_conversion():
    import subprocess

    out = subprocess.run(["git", "check-attr", "text", "tests/fixtures/invariants/login/auth.py"],
                         cwd=FIXTURE.parents[3], capture_output=True, text=True, check=True).stdout
    assert out.strip().endswith("text: unset")
