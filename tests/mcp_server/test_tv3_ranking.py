"""Real EV-2 and EV-3 measurements feeding the TV3 rank tool."""
import json
import sys
from pathlib import Path

import anyio
import pytest
from tv3_evidence_fixture import (
    BAD,
    FAILURE,
    GOOD,
    REGRESSION,
    STRUCTURAL_POLICY,
    seed_snapshot,
)

from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import source_inventory_hash
from vgar.mcp.proposal.diff_tests_provider import DiffTestsProvider
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.ranking_provider import (
    CHECKS,
    CandidateEvidence,
    EvidenceRankingProvider,
    RankingPolicy,
    ScoreWeights,
)
from vgar.mcp.proposal.tools import CoreTools
from vgar.repair.contracts import RepairPolicy
from vgar.repair.evidence import digest

ROOT = Path(__file__).resolve().parents[2]
POLICY = RankingPolicy(
    required_checks=("tests_passed", "previously_failing_tests_fixed", "schema_conformance_passed",
                     "no_new_forbidden_dependency", "public_api_compatible"),
    weights=ScoreWeights(tests=0.5, schema_conformance=0.15, architecture=0.1, api=0.15, semantic=0.1, impact_risk=0.2),
)


def candidate(name, diff):
    return c.Candidate(candidate_id=name, diff=diff, diff_hash=digest(diff))


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    root = tmp_path_factory.mktemp("ev1")
    store, task, binding, verification, authority, context = seed_snapshot(root)
    identity = store.identity
    execution = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace="ev3", snapshot_id=identity.snapshot_id,
                                  approved_fixture_diffs=(digest(GOOD), digest(BAD)))
    adapters = CoreTools(ProviderRegistry((
        ProviderBinding(verification, binding, frozenset({"verification"})),
        ProviderBinding(execution, binding, frozenset({"tests"}), lifecycle="guarded-v1", candidate_workspace="ev3"),
    )))
    pins = {}
    for diff, expected_test in ((GOOD, "PASS"), (BAD, "FAIL")):
        request = c.DiffRequest.from_diff(diff)
        graph = adapters.verify(request, context(config_hash=verification.config_hash))
        assert graph.status == "PASS", graph
        execution_ctx = context(config_hash=verification.config_hash)
        grant = authority.grant(execution_ctx, "run_relevant_tests", request.input_hash())
        tests = anyio.run(adapters.tests, request, grant)
        assert tests.status == expected_test, tests
        pins[request.diff_hash] = CandidateEvidence(graph=graph.evidence[0], tests=tests.evidence[0])
    return root, binding, identity, pins, context


def rank_tools(binding, identity, pins, policy=POLICY):
    provider = EvidenceRankingProvider(binding, snapshot_id=identity.snapshot_id, policy=policy, evidence_by_diff=pins)
    return CoreTools(ProviderRegistry((ProviderBinding(provider, binding, frozenset({"ranking"})),),
                                      required_checks=policy.required_checks))


def test_ranking_uses_measured_transitions_and_keeps_unknown_fields(measured):
    root, binding, identity, pins, context = measured
    request = c.RankRequest(candidates=(candidate("bad", BAD), candidate("z-good", GOOD),
                                        candidate("a-good", GOOD), candidate("unmeasured", GOOD + "\n")))
    result = rank_tools(binding, identity, pins).rank(request, context(config_hash=binding.config_hash))
    assert [row.candidate_id for row in result.candidates] == ["a-good", "z-good", "bad", "unmeasured"]
    assert [row.eligible for row in result.candidates] == [True, True, False, False]
    assert [row.score for row in result.candidates] == pytest.approx([0.7, 0.7, 0.45, -0.2])
    assert len(result.evidence) == 5 and result.reasons == ("PARTIAL_EVIDENCE",)
    record = json.loads((root / "output" / result.evidence[0].path).read_bytes())
    assert record["policy_hash"] == POLICY.input_hash()
    good, _, bad, unmeasured = record["candidates"]
    assert set(good["evidence_fields"]) == set(CHECKS)
    assert good["score_interval"] == pytest.approx([0.7, 1.0])
    assert good["evidence_fields"]["semantic_invariant_preserved"] == "NOT_RUN"
    assert good["evidence_fields"]["impact_radius_acceptable"] == "NOT_RUN"
    assert bad["evidence_fields"]["tests_passed"] == "FAIL"
    assert bad["evidence_fields"]["previously_failing_tests_fixed"] == "PASS"
    assert set(unmeasured["evidence_fields"].values()) == {"NOT_RUN"}
    assert not list((root / "lease").iterdir())


def test_required_unknown_and_wrong_run_are_not_eligible(measured):
    _, binding, identity, pins, context = measured
    policy = RankingPolicy(required_checks=(*POLICY.required_checks, "semantic_invariant_preserved"), weights=POLICY.weights)
    tools = rank_tools(binding, identity, pins, policy)
    request = c.RankRequest(candidates=(candidate("good", GOOD),))
    result = tools.rank(request, context(config_hash=binding.config_hash))
    assert not result.candidates[0].eligible
    assert result.candidates[0].checks[-1].status == "NOT_RUN"
    with pytest.raises(ValueError, match="binding mismatch"):
        tools.rank(request, context(config_hash=binding.config_hash, run_id="another-run"))


@pytest.mark.parametrize("fault", ["hash", "snapshot", "diff", "source_bytes", "transition"])
def test_misbound_or_corrupt_receipt_is_rejected(measured, fault):
    root, binding, identity, pins, context = measured
    pinned = pins[digest(GOOD)]
    record = json.loads((root / "output" / pinned.tests.path).read_bytes())
    if fault == "snapshot":
        record["snapshot_id"] = digest("another snapshot")
    elif fault == "diff":
        record["diff_hash"] = digest(BAD)
    elif fault == "source_bytes":
        record["changed_source_hashes"]["auth.py"] = digest("different candidate bytes")
    elif fault == "transition":
        record["candidate"]["outcomes"][record["required_failures"][0]] = "FAIL"
    raw = json.dumps(record).encode()
    name = f"bad-pin-{fault}.json"
    (root / "output" / name).write_bytes(raw)
    bad = c.EvidenceRef(path=name, sha256=pinned.tests.sha256 if fault == "hash" else digest(raw))
    tools = rank_tools(binding, identity, {digest(GOOD): CandidateEvidence(graph=pinned.graph, tests=bad)})
    before = set((root / "output").glob("tv3-ev1-*.json"))
    with pytest.raises(ValueError, match="hash mismatch|binding or profile|candidate source bytes|observed transitions"):
        tools.rank(c.RankRequest(candidates=(candidate("good", GOOD),)), context(config_hash=binding.config_hash))
    assert set((root / "output").glob("tv3-ev1-*.json")) == before


@pytest.mark.parametrize("source_status", ["FAIL", "ERROR", "NOT_RUN"])
def test_graph_pass_rejects_nonpassing_source_import_evidence(measured, source_status):
    root, binding, identity, pins, context = measured
    pinned = pins[digest(GOOD)]
    record = json.loads((root / "output" / pinned.graph.path).read_bytes())
    record["checks"]["source_imports"]["status"] = source_status
    raw = json.dumps(record).encode()
    name = f"source-import-{source_status}.json"
    (root / "output" / name).write_bytes(raw)
    graph = c.EvidenceRef(path=name, sha256=digest(raw))
    tools = rank_tools(binding, identity, {digest(GOOD): CandidateEvidence(graph=graph, tests=pinned.tests)})
    before = set((root / "output").glob("tv3-ev1-*.json"))
    with pytest.raises(ValueError, match="graph PASS is inconsistent"):
        tools.rank(c.RankRequest(candidates=(candidate("good", GOOD),)), context(config_hash=binding.config_hash))
    assert set((root / "output").glob("tv3-ev1-*.json")) == before


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"], ids=["modern", "legacy"])
def test_verify_test_rank_over_stdio(tmp_path_factory, mode):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    root = tmp_path_factory.mktemp("ev-wire")
    store, task, binding, _, _, _ = seed_snapshot(root)
    identity = store.identity
    candidates = (candidate("good", GOOD), candidate("bad", BAD))
    config = {
        "binding": binding.model_dump(), "snapshot_id": identity.snapshot_id, "manifest": str(store.manifest_path),
        "profile_hash": identity.profile_hash, "structural_policy": STRUCTURAL_POLICY,
        "task": task.model_dump(mode="json"), "approved_diffs": [item.diff_hash for item in candidates],
        "policy": POLICY.model_dump(),
    }
    config_path = root / "handoff.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    def client_for(stage):
        return Client(StdioServerParameters(
            command=sys.executable,
            args=["-B", str(ROOT / "tests/fixtures/mcp_server/tv3_handoff_server.py"), str(root), stage],
            env={"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                 "PYTHON_DOTENV_DISABLED": "1", "VGAR_GRAPH_BACKEND": "demo"},
        ), mode=mode)

    def evidence_record(ref):
        raw = (root / "output" / ref["path"]).read_bytes()
        assert digest(raw) == ref["sha256"]
        record = json.loads(raw)
        assert record["binding"] == config["binding"] and record["snapshot_id"] == identity.snapshot_id
        return record

    async def call(client, tool, arguments):
        result = await client.call_tool(tool, arguments)
        envelope = result.structured_content or json.loads(result.content[0].text)
        assert not result.is_error and envelope["status"] == "PASS", envelope
        data = envelope["data"]
        assert data["binding"] == config["binding"]
        return data

    async def run():
        graph_refs, pins, outcomes = {}, {}, {}
        with anyio.fail_after(90):
            async with client_for("verify") as client:
                resource = await client.read_resource("vgar://evidence/baseline")
                baseline = json.loads(resource.contents[0].text)["_resource"]
                assert baseline["availability"] == "PARTIAL"
                baseline_ref, = baseline["evidence"]
                evidence_record(baseline_ref)
                for item in candidates:
                    data = await call(client, "verify_patch_graph_constraints", {"diff": item.diff})
                    assert data["status"] == "PASS" and data["diff_hash"] == item.diff_hash
                    ref, = data["evidence"]
                    record = evidence_record(ref)
                    assert record["status"] == "PASS" and record["diff_hash"] == item.diff_hash
                    graph_refs[item.diff_hash] = ref

            async with client_for("test") as client:
                for item, verdict in zip(candidates, ("PASS", "FAIL"), strict=True):
                    data = await call(client, "run_relevant_tests", {"diff": item.diff})
                    assert data["status"] == verdict and data["diff_hash"] == item.diff_hash
                    receipt = data["receipt"]
                    assert receipt["applied_count"] == 1 and receipt["executed"] and receipt["cleaned"]
                    ref, = data["evidence"]
                    record = evidence_record(ref)
                    assert record["status"] == verdict and record["diff_hash"] == item.diff_hash
                    assert record["baseline"]["outcomes"] == {FAILURE: "FAIL", REGRESSION: "PASS"}
                    assert record["candidate"]["outcomes"] == {FAILURE: "PASS", REGRESSION: verdict}
                    graph = evidence_record(graph_refs[item.diff_hash])
                    assert graph["checks"]["api"]["details"]["source_hashes"]["candidate"] == record["changed_source_hashes"]
                    pins[item.diff_hash] = {"graph": graph_refs[item.diff_hash], "tests": ref}
                    outcomes[item.candidate_id] = {"verify": graph["status"], "tests": verdict,
                                                   "candidate_tests": record["candidate"]["outcomes"], "receipt": receipt}
                    assert not list((root / "lease").iterdir())

            config_path.write_text(json.dumps({**config, "pins": pins}), encoding="utf-8")
            async with client_for("rank") as client:
                data = await call(client, "rank_patch_candidates", {
                    "candidates": [item.model_dump() for item in reversed(candidates)],
                })
            good, bad = data["candidates"]
            assert [(row["candidate_id"], row["eligible"]) for row in (good, bad)] == [("good", True), ("bad", False)]
            assert [good["score"], bad["score"]] == pytest.approx([0.7, 0.45])
            rank_ref, *refs = data["evidence"]
            assert {ref["sha256"] for ref in refs} == {ref["sha256"] for pair in pins.values() for ref in pair.values()}
            ranking = evidence_record(rank_ref)
            fields = ranking["candidates"][1]["evidence_fields"]
            assert fields["previously_failing_tests_fixed"] == "PASS" and fields["tests_passed"] == "FAIL"

        assert source_inventory_hash(task.source_repo) == binding.source_hash
        assert store.load_document(identity.graph_version)["graph_version"] == identity.graph_version
        (root / "output" / "tv3-handoff-summary.json").write_text(json.dumps({
            "mode": mode, "binding": config["binding"], "snapshot_id": identity.snapshot_id,
            "baseline_resource": baseline_ref, "outcomes": outcomes, "pins": pins, "ranking": rank_ref,
            "candidate_order": [row["candidate_id"] for row in data["candidates"]],
        }, indent=2) + "\n", encoding="utf-8")

    anyio.run(run)
