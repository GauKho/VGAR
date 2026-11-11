"""Compare the same labeled fixture patches with and without EV-2 checks."""
import json
from dataclasses import dataclass

import anyio
from tv3_evidence_fixture import BAD, GOOD, seed_snapshot

from vgar.evaluation.repair.verifier_eval import confusion_metrics
from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import source_inventory_hash
from vgar.mcp.proposal.diff_tests_provider import DiffTestsProvider
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.ranking_provider import (
    CandidateEvidence,
    EvidenceRankingProvider,
    RankingPolicy,
    ScoreWeights,
)
from vgar.mcp.proposal.tools import CoreTools
from vgar.repair.contracts import RepairPolicy
from vgar.repair.evidence import atomic_json, digest
from vgar.repair.semantic_contract import ContractExample, SemanticContract

API_BREAK = (
    "--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n"
    "-def login(value):\n-    return bool(value)\n+def login(text):\n+    return bool(text.strip())\n"
)
FORBIDDEN_IMPORT = GOOD.replace(
    "@@ -2 +2 @@", "@@ -1,2 +1,3 @@\n+from pathlib import Path as _Path\n def login(value):",
)
PRICE_FIX = "--- a/pricing.py\n+++ b/pricing.py\n@@ -2 +2 @@\n-    return price - discount_percent\n+    return price * (1 - discount_percent / 100)\n"
TAX_FIX = "--- a/invoice.py\n+++ b/invoice.py\n@@ -6 +6 @@\n-    return net + tax_percent\n+    return net * (1 + tax_percent / 100)\n"
OPTIONAL_PARAMETER = (
    "--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n"
    "-def login(value):\n-    return bool(value)\n"
    "+def login(value, *, strict=False):\n+    return bool(value.strip())\n"
)
LOCAL_CYCLE = PRICE_FIX.replace("@@ -2 +2 @@", "@@ -2 +2,2 @@\n+    import invoice as _invoice") + TAX_FIX
MODULE_CYCLE = PRICE_FIX.replace("@@ -2 +2 @@", "@@ -2 +2,3 @@").replace(
    "(1 - discount_percent / 100)\n", "(1 - discount_percent / 100)\n+\n+import invoice as _invoice\n",
) + TAX_FIX


@dataclass(frozen=True)
class Case:
    name: str
    label: str
    diff: str
    graph_reason: str | None = None
    failures_after: tuple[str, ...] = ()


FIXTURES = (
    ("single_file_login", {"repo_key": "fixture/login", "forbidden_imports": [{"source": "auth", "target": "pathlib"}]}, (
        Case("good", "GOOD", GOOD),
        Case("regression", "BAD", BAD, failures_after=("tests/test_auth.py::test_login_accepts_name",)),
        Case("api_keyword_rename", "BAD", API_BREAK, "API_SIGNATURE_INCOMPATIBLE"),
        Case("forbidden_import", "BAD", FORBIDDEN_IMPORT, "FORBIDDEN_IMPORT"),
        Case("compatible_optional_parameter", "GOOD", OPTIONAL_PARAMETER),
        Case("overfit_alice", "BAD", GOOD.replace("bool(value.strip())", "value == 'alice'")),
    )),
    ("multi_file_invoice", {"repo_key": "fixture/invoice", "forbidden_imports": [{"source": "invoice", "target": "pricing"}]}, (
        Case("good_preserves_baseline_import", "GOOD", PRICE_FIX + TAX_FIX),
        Case("partial_fix", "BAD", PRICE_FIX, failures_after=("tests/test_invoice.py::test_invoice_percentage_tax",)),
        Case("module_import_cycle", "BAD", MODULE_CYCLE, "NEW_IMPORT_CYCLE"),
        Case("local_import_cycle", "BAD", LOCAL_CYCLE, "NEW_SOURCE_IMPORT_CYCLE"),
    )),
)
RECOMMENDATIONS = {"PASS": "ACCEPT", "FAIL": "REVISE", "ERROR": "REJECT", "NOT_RUN": None}
LOGIN_CONTRACT = SemanticContract(examples=tuple(
    ContractExample(case_id=name, module="auth", function="login", args=(value,), expected=expected)
    for name, value, expected in (("bob", "bob", True), ("charlie", "charlie", True), ("empty", "", False))
))


def combine(graph, tests):
    status = next(status for status in ("ERROR", "FAIL", "NOT_RUN", "PASS") if status in (graph, tests))
    return {"status": status, "recommendation": RECOMMENDATIONS[status]}


def evidence_record(output, result, binding, snapshot_id, diff_hash):
    ref, = result.evidence
    raw = (output / ref.path).read_bytes()
    assert digest(raw) == ref.sha256
    record = json.loads(raw)
    assert record["binding"] == binding.model_dump() and record["snapshot_id"] == snapshot_id
    assert record["diff_hash"] == diff_hash and record["status"] == result.status
    return ref.model_dump(), record


def measure_fixture(root, task_id, structural_policy, cases):
    store, task, binding, verification, authority, context = seed_snapshot(
        root, task_id=task_id, structural_policy=structural_policy, run_id="tv3-v1-pilot",
    )
    snapshot_id = store.identity.snapshot_id
    output = root / "output"
    execution = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace="ev3", snapshot_id=snapshot_id,
                                  approved_fixture_diffs=tuple(digest(case.diff) for case in cases))
    tools = CoreTools(ProviderRegistry((
        ProviderBinding(verification, binding, frozenset({"verification"})),
        ProviderBinding(execution, binding, frozenset({"tests"}), lifecycle="guarded-v1", candidate_workspace="ev3"),
    )))
    contract = LOGIN_CONTRACT if task_id == "single_file_login" else None
    enhanced_tools = tools
    if contract is not None:
        enhanced = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace="ev3-contract",
                                     snapshot_id=snapshot_id, approved_fixture_diffs=tuple(digest(case.diff) for case in cases),
                                     semantic_contract=contract)
        enhanced_tools = CoreTools(ProviderRegistry((ProviderBinding(enhanced, binding, frozenset({"tests"}),
                                                                    lifecycle="guarded-v1", candidate_workspace="ev3-contract"),)))

    def run_tests(adapter, request):
        grant = authority.grant(context(config_hash=binding.config_hash), "run_relevant_tests", request.input_hash())
        result = anyio.run(adapter.tests, request, grant)
        assert result.status in ("PASS", "FAIL"), result
        ref, record = evidence_record(output, result, binding, snapshot_id, request.diff_hash)
        assert result.receipt.applied_count == 1 and result.receipt.executed and result.receipt.cleaned
        return ref, record

    rows = []
    for case in cases:
        request = c.DiffRequest.from_diff(case.diff)
        graph = tools.verify(request, context(config_hash=binding.config_hash))
        graph_ref, graph_record = evidence_record(output, graph, binding, snapshot_id, request.diff_hash)
        test_ref, test_record = run_tests(tools, request)
        enhanced_ref, enhanced_record = ((test_ref, test_record) if contract is None else run_tests(enhanced_tools, request))
        assert graph_record["checks"]["api"]["details"]["source_hashes"]["candidate"] == test_record["changed_source_hashes"]
        assert enhanced_record["changed_source_hashes"] == test_record["changed_source_hashes"]
        baseline = test_record["baseline"]["outcomes"]
        assert {test for test, status in baseline.items() if status == "FAIL"} == set(task.failing_selectors)
        expected_after = {test: "FAIL" if test in case.failures_after else "PASS" for test in baseline}
        rows.append({
            "task_id": task_id, "case": case.name, "label": case.label, "diff_hash": request.diff_hash,
            "oracle": {"graph": "FAIL" if case.graph_reason else "PASS", "tests": "FAIL" if case.failures_after else "PASS",
                       "graph_reason": case.graph_reason, "after": expected_after},
            "graph": {"status": graph.status, "reasons": graph.reasons, "evidence": graph_ref},
            "tests": {"status": test_record["status"], "reasons": test_record["reasons"], "evidence": test_ref,
                      "before": test_record["baseline"]["outcomes"], "after": test_record["candidate"]["outcomes"]},
            "tests_with_contract": {"status": enhanced_record["status"], "evidence": enhanced_ref,
                                    "after": enhanced_record["candidate"]["outcomes"]},
            "tests_only": combine("PASS", test_record["status"]),
            "graph_and_tests": combine(graph.status, test_record["status"]),
            "graph_tests_and_contract": combine(graph.status, enhanced_record["status"]),
        })

    required = ("tests_passed",) if contract is None else ("tests_passed", "semantic_invariant_preserved")
    policy = RankingPolicy(required_checks=required, weights=ScoreWeights(tests=1.0, schema_conformance=0.0,
                           architecture=0.0, api=0.0, semantic=0.0, impact_risk=0.0))
    pins = {row["diff_hash"]: CandidateEvidence(graph=c.EvidenceRef.model_validate(row["graph"]["evidence"]),
            tests=c.EvidenceRef.model_validate(row["tests_with_contract"]["evidence"])) for row in rows}
    ranker = EvidenceRankingProvider(binding, snapshot_id=snapshot_id, policy=policy, evidence_by_diff=pins)
    request = c.RankRequest(candidates=tuple(c.Candidate(candidate_id=case.name, diff=case.diff,
                                                         diff_hash=digest(case.diff)) for case in cases))
    ranking = ranker.rank_candidates(request, context(config_hash=binding.config_hash))
    eligibility = {item.candidate_id: item.eligible for item in ranking.candidates}
    assert all(eligibility[row["case"]] == (row["graph_tests_and_contract"]["status"] == "PASS") for row in rows)
    assert source_inventory_hash(task.source_repo) == binding.source_hash
    assert not list((root / "lease").iterdir())
    return rows, {"binding": binding.model_dump(), "snapshot_id": snapshot_id, "structural_policy": structural_policy,
                  "evidence_directory": f"{task_id}/output", "ranking": ranking.evidence[0].model_dump()}


def test_tv3_v1_fixture_comparison(tmp_path_factory):
    root = tmp_path_factory.mktemp("v1-pilot")
    rows, fixtures = [], {}
    for task_id, structural_policy, cases in FIXTURES:
        fixture_root = root / task_id
        fixture_root.mkdir()
        measured, metadata = measure_fixture(fixture_root, task_id, structural_policy, cases)
        rows.extend(measured)
        fixtures[task_id] = metadata
    metrics = {arm: confusion_metrics({"label": row["label"], **row[arm]} for row in rows)
               for arm in ("tests_only", "graph_and_tests", "graph_tests_and_contract")}
    atomic_json(root / "tv3-v1-pilot.json", {
        "scope": "two byte-approved development fixtures", "fixtures": fixtures, "cases": rows, "metrics": metrics,
    })
    for row in rows:
        oracle = row["oracle"]
        assert (row["graph"]["status"], row["tests"]["status"]) == (oracle["graph"], oracle["tests"]), row
        if oracle["graph_reason"] is not None:
            assert oracle["graph_reason"] in row["graph"]["reasons"], row
        assert row["tests"]["after"] == oracle["after"], row
    overfit = next(row for row in rows if row["case"] == "overfit_alice")
    assert overfit["tests_with_contract"]["after"]["vgar_contract::bob"] == "FAIL"
    assert [metrics[arm]["FN"] for arm in metrics] == [5, 1, 0]
    assert all(arm["FRR"] == 0 and arm["bad_total"] == 7 and arm["good_total"] == 3 for arm in metrics.values())
