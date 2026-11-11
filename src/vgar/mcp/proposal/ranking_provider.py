"""TV3 EV-1 ranking over host-selected, hash-bound verification receipts."""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, get_args
from uuid import uuid4

from pydantic import Field, StrictFloat, TypeAdapter, model_validator

from vgar.repair.evidence import atomic_json, digest, encode_json
from vgar.repair.semantic_contract import SemanticContract

from . import contracts as c
from .context import check_context, check_source, request_commit_guard
from .diff_tests_provider import PROFILE as TEST_PROFILE
from .resources import _json_object
from .security import read_lease_bytes, resolve_read_path
from .verification_provider import PROFILE as GRAPH_PROFILE

Check = Literal[
    "tests_passed", "previously_failing_tests_fixed", "static_typecheck_passed", "lint_passed",
    "schema_conformance_passed", "no_new_forbidden_dependency", "public_api_compatible",
    "semantic_invariant_preserved", "impact_radius_acceptable",
]
CHECKS = get_args(Check)
HASH = TypeAdapter(c.Hash)
STATUS = TypeAdapter(c.Status)
RUNTIME_TEST_STATUS = {"PASS", "FAIL", "ERROR", "SKIP", "XFAIL", "XPASS"}


class CandidateEvidence(c.DTO):
    graph: c.EvidenceRef | None = None
    tests: c.EvidenceRef | None = None


class ScoreWeights(c.DTO):
    tests: StrictFloat = Field(ge=0, le=1)
    schema_conformance: StrictFloat = Field(ge=0, le=1)
    architecture: StrictFloat = Field(ge=0, le=1)
    api: StrictFloat = Field(ge=0, le=1)
    semantic: StrictFloat = Field(ge=0, le=1)
    impact_risk: StrictFloat = Field(ge=0, le=1)

    @model_validator(mode="after")
    def nonzero(self):
        if not any(self.model_dump().values()):
            raise ValueError("At least one ranking weight must be positive")
        return self


class RankingPolicy(c.DTO):
    required_checks: tuple[Check, ...] = Field(min_length=1)
    weights: ScoreWeights

    @model_validator(mode="after")
    def unique_checks(self):
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("Duplicate required ranking check")
        return self


class EvidenceRankingProvider:
    def __init__(self, binding: c.SnapshotBinding, *, snapshot_id: str, policy: RankingPolicy,
                 evidence_by_diff: Mapping[str, CandidateEvidence]):
        self._binding = c.SnapshotBinding.model_validate(binding.model_dump())
        self._snapshot_id = HASH.validate_python(snapshot_id)
        self.policy = RankingPolicy.model_validate(policy.model_dump())
        self._pins = MappingProxyType({HASH.validate_python(key): CandidateEvidence.model_validate(value.model_dump())
                                       for key, value in evidence_by_diff.items()})

    def rank_candidates(self, request: c.RankRequest, context) -> c.RankResult:
        request = c.RankRequest.model_validate(request.model_dump())
        check_source(context)
        if c.SnapshotBinding.from_context(context) != self._binding:
            raise ValueError("Ranking snapshot/source/config/task/run binding mismatch")

        results, rows, input_refs = [], [], []
        by_diff = {}
        for candidate in request.candidates:
            check_context(context)
            if candidate.diff_hash not in by_diff:
                pins = self._pins.get(candidate.diff_hash, CandidateEvidence())
                by_diff[candidate.diff_hash] = self._measure(candidate.diff_hash, pins, context)
                input_refs.extend(ref for ref in (pins.graph, pins.tests) if ref is not None)
            fields, graph_status, test_status = by_diff[candidate.diff_hash]
            lower, upper = _score_interval(fields, self.policy.weights)
            checks = tuple(c.NamedCheck(name=name, status=fields[name]) for name in self.policy.required_checks)
            eligible = graph_status == test_status == "PASS" and all(check.status == "PASS" for check in checks)
            result = c.RankedCandidate(candidate_id=candidate.candidate_id, diff_hash=candidate.diff_hash,
                                       score=lower, checks=checks, eligible=eligible)
            results.append(result)
            rows.append({**result.model_dump(), "evidence_fields": fields, "score_interval": [lower, upper],
                         "graph_verdict": graph_status, "test_verdict": test_status,
                         "inputs": self._pins.get(candidate.diff_hash, CandidateEvidence()).model_dump()})

        input_refs = tuple(dict.fromkeys(input_refs))
        if len(input_refs) + 1 > context.limits.audit_records:
            raise ValueError("Ranking evidence count exceeds the host limit")
        rows.sort(key=lambda row: (not row["eligible"], -row["score"], row["candidate_id"]))
        reasons = ("PARTIAL_EVIDENCE",) if any(
            set(row["evidence_fields"].values()) & {"NOT_RUN", "ERROR"} for row in rows
        ) else ()
        evidence = self._publish(context, {
            "profile": "tv3-ev1-v1", "binding": self._binding.model_dump(), "snapshot_id": self._snapshot_id,
            "policy": self.policy.model_dump(), "policy_hash": self.policy.input_hash(),
            "reasons": reasons, "candidates": rows,
        })
        ordered = sorted(results, key=lambda item: (not item.eligible, -item.score, item.candidate_id))
        return c.RankResult(binding=self._binding, candidates=tuple(ordered), reasons=reasons, evidence=(evidence, *input_refs))

    def _measure(self, diff_hash, pins, context):
        fields = dict.fromkeys(CHECKS, "NOT_RUN")
        graph_status = test_status = "NOT_RUN"
        graph_bytes = test_bytes = None
        if pins.graph is not None:
            graph = self._load(pins.graph, GRAPH_PROFILE, diff_hash, context)
            graph_status = graph["status"]
            graph_bytes = _graph_fields(graph, fields)
        if pins.tests is not None:
            tests = self._load(pins.tests, TEST_PROFILE, diff_hash, context)
            test_status = tests["status"]
            test_bytes = _test_fields(tests, fields)
        if graph_bytes is not None and test_bytes is not None and graph_bytes != test_bytes:
            raise ValueError("Graph and test receipts disagree on candidate source bytes")
        return fields, graph_status, test_status

    def _load(self, ref, profile, diff_hash, context):
        raw, size = read_lease_bytes(context.output_root, ref.path, context.limits.read_bytes)
        if size != len(raw) or digest(raw) != ref.sha256:
            raise ValueError("Ranking input evidence file/hash mismatch")
        record = _json_object(raw)
        status = c.CheckEvidence.model_validate({key: record[key] for key in c.CheckEvidence.model_fields if key in record})
        if (status.binding, status.diff_hash, record.get("snapshot_id"), record.get("profile")) != (
            self._binding, diff_hash, self._snapshot_id, profile,
        ):
            raise ValueError("Ranking input evidence binding or profile mismatch")
        if status.status == "PASS" and (status.coverage != "COMPLETE" or not status.scope):
            raise ValueError("Ranking PASS requires complete measured evidence")
        return record

    def _publish(self, context, record):
        name = f"tv3-ev1-{uuid4().hex}.json"
        raw = encode_json(record)
        if len(raw) > context.limits.read_bytes:
            raise ValueError("Ranking evidence exceeds the host byte limit")
        with request_commit_guard(context):
            check_source(context)
            target = resolve_read_path(context.output_root, name)
            check_context(context)
            atomic_json(target, record)
        return c.EvidenceRef(path=name, sha256=digest(raw))


def _graph_fields(record, fields):
    checks = record["checks"]
    schema = STATUS.validate_python(checks.get("schema", {}).get("status", "NOT_RUN"))
    api = STATUS.validate_python(checks.get("api", {}).get("status", "NOT_RUN"))
    structure = STATUS.validate_python(checks.get("structural", {}).get("status", "NOT_RUN"))
    imports = checks.get("structural", {}).get("details", {}).get("subchecks", {}).get("forbidden_imports", {})
    fields["no_new_forbidden_dependency"] = STATUS.validate_python(imports.get("status", "NOT_RUN"))
    fields["schema_conformance_passed"] = "FAIL" if "CANDIDATE_SCHEMA_VIOLATION" in record["reasons"] else schema
    fields["public_api_compatible"] = api
    if record["status"] == "PASS" and (
        fields["schema_conformance_passed"] != "PASS" or api != "PASS" or structure != "PASS"
        or fields["no_new_forbidden_dependency"] in {"FAIL", "ERROR"}
        or ("source_imports" in checks
            and STATUS.validate_python(checks["source_imports"].get("status", "NOT_RUN")) != "PASS")
    ):
        raise ValueError("Ranking graph PASS is inconsistent with its check results")
    raw = checks.get("api", {}).get("details", {}).get("source_hashes", {}).get("candidate")
    return _candidate_bytes(raw, record["scope"]) if record["status"] == "PASS" or raw is not None else None


def _test_fields(record, fields):
    receipt = c.TestReceipt.model_validate(record["receipt"])
    if receipt.diff_hash != record["diff_hash"] or not receipt.admitted or not receipt.cleaned:
        raise ValueError("Ranking test receipt lacks matching admission or cleanup")
    fields["tests_passed"] = record["status"]
    if record["status"] not in {"PASS", "FAIL"}:
        return None
    if not receipt.executed or receipt.applied_count != 1 or record["coverage"] != "COMPLETE" or not record["scope"]:
        raise ValueError("Ranking terminal test evidence lacks an apply-once execution")
    baseline, post = record["baseline"], record["candidate"]
    for report in (baseline, post):
        if report["complete"] is not True or set(report["outcomes"].values()) - RUNTIME_TEST_STATUS:
            raise ValueError("Ranking test execution was incomplete")
        HASH.validate_python(report["junit_sha256"])
    original, outcomes = baseline["outcomes"], post["outcomes"]
    contract_record = record.get("semantic_contract")
    if contract_record is not None:
        if digest(contract_record["definition"]) != contract_record["sha256"]:
            raise ValueError("Semantic contract hash mismatch")
        contract = SemanticContract.model_validate_json(contract_record["definition"])
        ids = [example.node_id for example in contract.examples]
        if any(original.get(key) != "PASS" for key in ids):
            raise ValueError("Semantic contract baseline was not qualified")
        observed = {outcomes.get(key) for key in ids}
        if observed == {"PASS"}:
            fields["semantic_invariant_preserved"] = "PASS"
        elif "FAIL" in observed:
            fields["semantic_invariant_preserved"] = "FAIL"
    required = tuple(record["required_failures"])
    if (baseline["status"] != "FAIL" or "ERROR" in original.values() or not required
            or set(required) != {k for k, v in original.items() if v == "FAIL"}):
        raise ValueError("Ranking test baseline lacks qualified failing tests")
    repaired = [outcomes.get(key) for key in required]
    if all(value in {"PASS", "FAIL"} for value in repaired):
        fields["previously_failing_tests_fixed"] = "PASS" if all(value == "PASS" for value in repaired) else "FAIL"
    if record["status"] == "PASS" and (
        post["status"] != "PASS" or fields["previously_failing_tests_fixed"] != "PASS"
        or {"FAIL", "ERROR"}.intersection(outcomes.values())
        or any(outcomes.get(k) != "PASS" for k, v in original.items() if v == "PASS")
    ):
        raise ValueError("Ranking test PASS is inconsistent with the observed transitions")
    return _candidate_bytes(record.get("changed_source_hashes"), record["changed_paths"])


def _candidate_bytes(value, scope):
    if not isinstance(value, dict) or not value or set(value) != set(scope):
        raise ValueError("Ranking input lacks the changed file hashes")
    return {path: HASH.validate_python(value[path]) for path in value}


def _score_interval(fields, weights):
    terms = (
        ("tests_passed", weights.tests / 2), ("previously_failing_tests_fixed", weights.tests / 2),
        ("schema_conformance_passed", weights.schema_conformance), ("no_new_forbidden_dependency", weights.architecture),
        ("public_api_compatible", weights.api), ("semantic_invariant_preserved", weights.semantic),
    )
    lower = sum(weight for name, weight in terms if fields[name] == "PASS")
    upper = lower + sum(weight for name, weight in terms if fields[name] in {"ERROR", "NOT_RUN"})
    # Impact is unmeasured in this profile. Preserve the possible penalty in the lower bound.
    return lower - weights.impact_risk, upper
