"""Guide-style layer 5 functions: verify_patch, run_patch_tests, rank_candidates (spec §7.3, §7.6, §7.7).

Patches come from tests/fixtures/m2/{reference,wrong}_patches and apply to tests/fixtures/w7_w8_handoff/<task>/repo.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from graph_fixture import fixture_service
from vgar.repair.patch_evidence import verify_patch

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOGIN_REPO = FIXTURES / "w7_w8_handoff" / "single_file_login" / "repo"
INVOICE_REPO = FIXTURES / "w7_w8_handoff" / "multi_file_invoice" / "repo"
REF = (FIXTURES / "m2" / "reference_patches" / "single_file_login.diff").read_text(encoding="utf-8")
WRONG = (FIXTURES / "m2" / "wrong_patches" / "single_file_login.diff").read_text(encoding="utf-8")
INVOICE_REF = (FIXTURES / "m2" / "reference_patches" / "multi_file_invoice.diff").read_text(encoding="utf-8")
REMOVE_LOGIN = "--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +0,0 @@\n-def login(value):\n-    return bool(value)\n"


def _service(tmp_path, repo=LOGIN_REPO):
    service = fixture_service(tmp_path / "graph", repo=repo)
    return service, service.get_repository_summary().graph_version


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


# --- Task 5: verify_patch -----------------------------------------------------------------------

def test_reference_patch_passes_graph_checks(tmp_path):
    service, version = _service(tmp_path)
    result = verify_patch(service, REF, graph_version=version)
    assert result["status"] == "PASS", result
    assert {"schema", "structural", "api", "source_imports", "port_check", "fanout"} <= set(result["checks"])
    assert result["checks"]["fanout"]["status"] == "NOT_RUN"
    assert result["graph_version"] == version and result["diff_sha256"].startswith("sha256:")


def test_multi_file_reference_patch_passes(tmp_path):
    service, version = _service(tmp_path, INVOICE_REPO)
    assert verify_patch(service, INVOICE_REF, graph_version=version)["status"] == "PASS"


def test_removing_a_public_function_fails_on_port_or_api(tmp_path):
    service, version = _service(tmp_path)
    result = verify_patch(service, REMOVE_LOGIN, graph_version=version)
    assert result["status"] == "FAIL", result
    assert "FAIL" in {result["checks"]["api"]["status"], result["checks"]["port_check"]["status"]}


def test_malformed_diff_is_error_and_repo_is_untouched(tmp_path):
    service, version = _service(tmp_path)
    before = _tree_hash(LOGIN_REPO)
    result = verify_patch(service, "not a diff", graph_version=version)
    assert result["status"] == "ERROR" and result["reasons"]
    assert _tree_hash(LOGIN_REPO) == before


def test_diff_outside_the_graph_is_error(tmp_path):
    service, version = _service(tmp_path)
    outside = "--- a/elsewhere.py\n+++ b/elsewhere.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    assert verify_patch(service, outside, graph_version=version)["status"] == "ERROR"


def test_missing_repository_root_is_not_ready(tmp_path):
    from vgar.contracts.error import GraphNotReadyError
    service, version = _service(tmp_path)
    service.repository_root = None
    with pytest.raises(GraphNotReadyError):
        verify_patch(service, REF, graph_version=version)


def test_verify_tool_runs_without_a_provider(tmp_path, monkeypatch):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import graph_server
    service, _ = _service(tmp_path)
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    import asyncio
    response = asyncio.run(graph_server.verify_patch_graph_constraints(REF))
    assert response["status"] == "PASS", response
    assert response["data"]["status"] == "PASS"


# --- Task 6: run_patch_tests --------------------------------------------------------------------

FAILING = ["tests/test_auth.py::test_login_rejects_whitespace"]


def test_reference_patch_fixes_the_failing_test(tmp_path):
    from vgar.repair.patch_evidence import run_patch_tests
    service, version = _service(tmp_path)
    result = run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING)
    assert result["status"] == "PASS", result
    assert FAILING[0] in result["previously_failing_fixed"] and result["regressions"] == []
    assert result["baseline"][FAILING[0]] == "FAIL" and result["candidate"][FAILING[0]] == "PASS"
    assert result["cleaned"] is True
    assert result["broader_suite"] == "NOT_RUN" and result["coverage"] == "NOT_RUN"


def test_wrong_patch_fails(tmp_path):
    from vgar.repair.patch_evidence import run_patch_tests
    service, version = _service(tmp_path)
    result = run_patch_tests(service, WRONG, graph_version=version, failing_tests=FAILING)
    assert result["status"] == "FAIL", result
    assert FAILING[0] not in result["previously_failing_fixed"]


def test_failing_test_that_does_not_fail_is_not_run(tmp_path):
    from vgar.repair.patch_evidence import run_patch_tests
    service, version = _service(tmp_path)
    result = run_patch_tests(service, REF, graph_version=version,
                             failing_tests=["tests/test_auth.py::test_login_accepts_name"])
    assert result["status"] == "NOT_RUN" and "FAILING_TEST_NOT_REPRODUCED" in result["reasons"]


def test_timeout_is_error_and_copy_is_cleaned(tmp_path, monkeypatch):
    from vgar.mcp import pytest_runner
    from vgar.mcp.schemas import TIMEOUT, CodedToolError
    from vgar.repair.patch_evidence import run_patch_tests

    def slow(*args, **kwargs):
        raise CodedToolError(TIMEOUT, "pytest exceeded the server timeout")

    monkeypatch.setattr(pytest_runner, "run_selector", slow)
    service, version = _service(tmp_path)
    result = run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING)
    assert result["status"] == "ERROR" and result["cleaned"] is True


def test_original_repository_is_never_modified(tmp_path):
    from vgar.repair.patch_evidence import run_patch_tests
    service, version = _service(tmp_path)
    before = _tree_hash(LOGIN_REPO)
    run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING)
    run_patch_tests(service, "not a diff", graph_version=version)
    assert _tree_hash(LOGIN_REPO) == before


def test_malformed_diff_is_error_for_tests(tmp_path):
    from vgar.repair.patch_evidence import run_patch_tests
    service, version = _service(tmp_path)
    assert run_patch_tests(service, "not a diff", graph_version=version)["status"] == "ERROR"


def test_execution_tool_runs_without_a_provider(tmp_path, monkeypatch):
    import asyncio

    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import execution_server
    service, _ = _service(tmp_path)
    monkeypatch.setattr(execution_server, "_graph_service", service)
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    response = asyncio.run(execution_server.run_relevant_tests(REF))
    assert response["status"] == "PASS", response
    assert response["data"]["status"] in {"PASS", "FAIL"} and response["data"]["selectors"]


# --- Task 7: rank_candidates --------------------------------------------------------------------

WEIGHTS = {"tests": 0.5, "schema_conformance": 0.15, "architecture": 0.1, "api": 0.15, "semantic": 0.1,
           "impact_risk": 0.2}
FIELDS = ("tests_passed", "previously_failing_tests_fixed", "static_typecheck_passed", "lint_passed",
          "schema_conformance_passed", "no_new_forbidden_dependency", "public_api_compatible",
          "semantic_invariant_preserved", "impact_radius_acceptable")


def test_score_matches_tv3_when_impact_is_unmeasured():
    from vgar.mcp.proposal.ranking_provider import ScoreWeights, _score_interval
    from vgar.repair.patch_evidence import score_patch
    fields = dict(zip(FIELDS, ("PASS", "FAIL", "NOT_RUN", "NOT_RUN", "PASS", "ERROR", "PASS", "NOT_RUN", "NOT_RUN")))
    assert score_patch(fields, WEIGHTS, None) == pytest.approx(_score_interval(fields, ScoreWeights(**WEIGHTS)))


def test_measured_impact_only_subtracts_the_measured_risk():
    from vgar.repair.patch_evidence import score_patch
    fields = dict.fromkeys(FIELDS, "PASS")
    assert score_patch(fields, WEIGHTS, 0.0)[0] == pytest.approx(1.0)
    assert score_patch(fields, WEIGHTS, 1.0)[0] == pytest.approx(0.8)


def test_evidence_fields_has_the_nine_proposal_fields(tmp_path):
    from vgar.repair.patch_evidence import evidence_fields, run_patch_tests
    service, version = _service(tmp_path)
    fields = evidence_fields(verify_patch(service, REF, graph_version=version),
                             run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING))
    assert set(fields) == set(FIELDS)
    assert fields["tests_passed"] == "PASS" and fields["previously_failing_tests_fixed"] == "PASS"
    assert fields["static_typecheck_passed"] == fields["lint_passed"] == fields["semantic_invariant_preserved"] == "NOT_RUN"


def test_reference_patch_ranks_above_wrong_patch(tmp_path):
    from vgar.repair.patch_evidence import diff_sha256, rank_candidates, run_patch_tests
    service, version = _service(tmp_path)
    candidates = [{"candidate_id": "wrong", "diff": WRONG}, {"candidate_id": "good", "diff": REF}]
    verify = {diff_sha256(d): verify_patch(service, d, graph_version=version) for d in (REF, WRONG)}
    tests = {diff_sha256(d): run_patch_tests(service, d, graph_version=version, failing_tests=FAILING) for d in (REF, WRONG)}
    ranking = rank_candidates(candidates, verify_results=verify, test_results=tests, weights=WEIGHTS)["ranking"]
    assert [row["candidate_id"] for row in ranking] == ["good", "wrong"]
    assert ranking[0]["eligible"] is True and ranking[1]["eligible"] is False


def test_failed_required_check_never_ranks_first():
    from vgar.repair.patch_evidence import diff_sha256, rank_candidates
    good_tests = {"status": "PASS", "previously_failing_fixed": ["t"], "regressions": []}
    failed_verify = {"status": "FAIL", "checks": {"schema": {"status": "PASS"}, "api": {"status": "FAIL"},
                                                  "structural": {"status": "PASS", "details": {}},
                                                  "port_check": {"status": "PASS"}}}
    weak_verify = {"status": "PASS", "checks": {"schema": {"status": "PASS"}, "api": {"status": "PASS"},
                                                "structural": {"status": "PASS", "details": {}},
                                                "port_check": {"status": "NOT_RUN"}}}
    weak_tests = {"status": "PASS", "previously_failing_fixed": [], "regressions": []}
    candidates = [{"candidate_id": "a-high", "diff": "A"}, {"candidate_id": "b-low", "diff": "B"}]
    ranking = rank_candidates(candidates, weights=WEIGHTS,
                              verify_results={diff_sha256("A"): failed_verify, diff_sha256("B"): weak_verify},
                              test_results={diff_sha256("A"): good_tests, diff_sha256("B"): weak_tests})["ranking"]
    assert ranking[0]["candidate_id"] == "b-low" and ranking[1]["eligible"] is False


def test_weights_file_holds_the_provisional_values():
    from vgar.repair.patch_evidence import load_ranking_weights
    assert load_ranking_weights() == WEIGHTS


def test_rank_tool_runs_without_a_provider(tmp_path, monkeypatch):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.contracts import Candidate, DiffRequest
    from vgar.mcp.servers import graph_server
    service, _ = _service(tmp_path)
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    candidates = [Candidate(candidate_id=name, **DiffRequest.from_diff(diff).model_dump())
                  for name, diff in (("wrong", WRONG), ("good", REF))]
    import asyncio
    response = asyncio.run(graph_server.rank_patch_candidates(candidates))
    assert response["status"] == "PASS", response
    assert [row["candidate_id"] for row in response["data"]["ranking"]][0] == "good"


# --- Final review fixes ------------------------------------------------------------------------

STALE = "--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n-def nothere(value):\n+def nothere(x):\n     return bool(value)\n"


def test_tests_for_a_diff_that_does_not_apply_are_error_not_raised(tmp_path):
    from vgar.repair.patch_evidence import run_patch_tests
    service, version = _service(tmp_path)
    before = _tree_hash(LOGIN_REPO)
    result = run_patch_tests(service, STALE, graph_version=version)
    assert result["status"] == "ERROR" and result["reasons"][0].startswith("PATCH_DOES_NOT_APPLY")
    assert result["cleaned"] is True and _tree_hash(LOGIN_REPO) == before


def test_rank_survives_one_stale_candidate(tmp_path, monkeypatch):
    import asyncio

    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.contracts import Candidate, DiffRequest
    from vgar.mcp.servers import graph_server
    service, _ = _service(tmp_path)
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    candidates = [Candidate(candidate_id=name, **DiffRequest.from_diff(diff).model_dump())
                  for name, diff in (("stale", STALE), ("good", REF))]
    response = asyncio.run(graph_server.rank_patch_candidates(candidates))
    assert response["status"] == "PASS", response
    ranking = response["data"]["ranking"]
    assert ranking[0]["candidate_id"] == "good" and ranking[1]["eligible"] is False


def test_total_test_budget_stops_the_run(tmp_path, monkeypatch):
    import time

    from vgar.mcp import pytest_runner
    from vgar.repair.patch_evidence import run_patch_tests

    def slow(root, selector, *, timeout_seconds, output_cap):
        time.sleep(0.3)
        return {"exit_code": 1, "stdout": "", "stderr": "", "truncated": False}

    monkeypatch.setattr(pytest_runner, "run_selector", slow)
    service, version = _service(tmp_path)
    result = run_patch_tests(service, REF, graph_version=version, failing_tests=FAILING, budget_seconds=0.2)
    assert result["status"] == "ERROR" and "TEST_BUDGET_EXCEEDED" in result["reasons"] and result["cleaned"] is True


def test_graph_server_uses_the_execution_test_limits(tmp_path, monkeypatch):
    from vgar.mcp.servers import graph_server
    from vgar.mcp.tooling import PYTEST_OUTPUT_CAP, PYTEST_TIMEOUT_SECONDS
    seen = {}
    monkeypatch.setattr("vgar.repair.patch_evidence.run_patch_tests",
                        lambda *a, **k: seen.update(k) or {"status": "NOT_RUN"})
    service, _ = _service(tmp_path)
    monkeypatch.setattr(graph_server, "graph_service", service)
    graph_server._test_cache.clear()
    graph_server._tested(REF)
    assert seen["timeout_seconds"] == PYTEST_TIMEOUT_SECONDS and seen["output_cap"] == PYTEST_OUTPUT_CAP


def test_long_running_tools_run_off_the_event_loop(tmp_path, monkeypatch):
    import asyncio
    import inspect
    import threading

    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import execution_server, graph_server
    for tool in (graph_server.verify_patch_graph_constraints, graph_server.rank_patch_candidates,
                 execution_server.run_relevant_tests):
        assert inspect.iscoroutinefunction(tool)
    threads = []
    monkeypatch.setattr("vgar.repair.patch_evidence.verify_patch",
                        lambda *a, **k: threads.append(threading.get_ident()) or {"status": "PASS", "reasons": []})
    service, _ = _service(tmp_path)
    monkeypatch.setattr(graph_server, "graph_service", service)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    graph_server._verify_cache.clear()

    async def call():
        loop_thread = threading.get_ident()
        await graph_server.verify_patch_graph_constraints(REF)
        return loop_thread

    loop_thread = asyncio.run(call())
    assert threads[-1] != loop_thread


def test_example_environment_uses_a_real_graph_backend():
    root = Path(__file__).resolve().parents[1]
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert "VGAR_GRAPH_BACKEND=demo" not in example and "VGAR_GRAPH_BACKEND=sqlite" in example
    assert "| `VGAR_GRAPH_BACKEND` | `demo` |" not in (root / "README.md").read_text(encoding="utf-8")
