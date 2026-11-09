"""Strict adapter DTOs, separate from the frozen legacy graph/repair payloads."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

Hash = Annotated[StrictStr, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
Identifier = Annotated[StrictStr, Field(min_length=1, max_length=2048)]
Status = Literal["PASS", "FAIL", "ERROR", "NOT_RUN"]


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    def input_hash(self) -> str:
        return digest(json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False))


class SnapshotBinding(DTO):
    snapshot_hash: Hash
    source_hash: Hash
    config_hash: Hash
    task_id: Identifier
    run_id: Identifier

    @classmethod
    def from_context(cls, ctx):
        return cls(**{key: getattr(ctx, key) for key in cls.model_fields})


class AdapterLimits(DTO):
    max_hops: StrictInt = Field(default=2, ge=1, le=32)
    max_nodes: StrictInt = Field(default=200, ge=1, le=10000)
    max_examined_edges: StrictInt = Field(default=10000, ge=1, le=1000000)
    max_candidates: StrictInt = Field(default=20, ge=1, le=1000)
    max_diff_bytes: StrictInt = Field(default=65536, ge=1, le=10000000)


class BuildRequest(DTO):
    repo_path: Identifier


class DiffRequest(DTO):
    diff: StrictStr
    diff_hash: Hash

    @model_validator(mode="after")
    def verify_hash(self):
        if digest(self.diff) != self.diff_hash:
            raise ValueError("Diff hash mismatch")
        return self

    @classmethod
    def from_diff(cls, diff):
        return cls(diff=diff, diff_hash=digest(diff))


class PathRequest(DTO):
    source_id: Identifier
    target_id: Identifier
    max_hops: StrictInt = Field(default=2, ge=1)
    max_nodes: StrictInt = Field(default=200, ge=1)
    max_examined_edges: StrictInt = Field(default=10000, ge=1)


class TraversalRequest(DTO):
    symbol_id: Identifier
    direction: Literal["callers", "callees"]
    depth: StrictInt = Field(default=1, ge=1)
    max_nodes: StrictInt = Field(default=200, ge=1)
    max_examined_edges: StrictInt = Field(default=10000, ge=1)


class EvidenceRef(DTO):
    path: Identifier
    sha256: Hash


class BoundResult(DTO):
    binding: SnapshotBinding
    reasons: tuple[Identifier, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()


class ResourceRequest(DTO):
    uri: Annotated[StrictStr, Field(min_length=1, max_length=2048)]
    kind: Literal["summary", "schema", "node", "subgraph", "component", "task", "baseline", "audit"]
    resource_id: Identifier | None = None
    k: StrictInt | None = Field(default=None, ge=1, le=2)
    cursor: StrictInt = Field(default=0, ge=0)
    legacy: StrictBool = False


class ResourceResult(BoundResult):
    resource_kind: Literal["schema", "component", "task", "baseline"]
    resource_id: Identifier | None = None
    payload_json: Annotated[StrictStr, Field(max_length=65536)]
    availability: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE"]


class BuildResult(BoundResult):
    result_snapshot_hash: Hash
    capabilities: tuple[Identifier, ...]
    changed_paths: tuple[Identifier, ...] = ()
    published: StrictBool = False


class Witness(DTO):
    edge_id: Identifier
    edge_type: Identifier
    source_id: Identifier
    target_id: Identifier
    direction: Literal["outgoing", "incoming"] = "outgoing"
    confidence: StrictFloat = Field(ge=0, le=1)
    provenance: Identifier


class PathResult(BoundResult):
    nodes: tuple[Identifier, ...] = ()
    edges: tuple[Witness, ...] = ()
    examined_edges: StrictInt = Field(ge=0)
    truncated: StrictBool = False
    unsupported: tuple[Identifier, ...] = ()


class RelatedSymbol(DTO):
    symbol_id: Identifier
    name: StrictStr
    kind: Identifier
    path: StrictStr
    hop: StrictInt = Field(ge=1)


class TraversalResult(BoundResult):
    symbols: tuple[RelatedSymbol, ...] = ()
    evidence_edges: tuple[Witness, ...] = ()
    examined_edges: StrictInt = Field(ge=0)
    truncated: StrictBool = False


class CheckEvidence(BoundResult):
    diff_hash: Hash
    status: Status
    scope: tuple[Identifier, ...] = ()
    coverage: Literal["COMPLETE", "PARTIAL", "UNKNOWN"] = "UNKNOWN"


class TestReceipt(DTO):
    workspace: Identifier
    diff_hash: Hash
    admitted: StrictBool
    applied_count: StrictInt = Field(ge=0, le=1)
    executed: StrictBool
    cleaned: StrictBool


class TestEvidence(CheckEvidence):
    receipt: TestReceipt | None = None


class NamedCheck(DTO):
    name: Identifier
    status: Status


class Candidate(DiffRequest):
    candidate_id: Identifier


class RankRequest(DTO):
    candidates: tuple[Candidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique(self):
        ids = [x.candidate_id for x in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate IDs")
        return self


class RankedCandidate(DTO):
    candidate_id: Identifier
    diff_hash: Hash
    score: StrictFloat
    checks: tuple[NamedCheck, ...]
    eligible: StrictBool = False


class RankResult(BoundResult):
    candidates: tuple[RankedCandidate, ...]
