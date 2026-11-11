"""Host the verify, test and rank stages of the TV3 fixture over STDIO."""
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.storage_capabilities import SnapshotGraphStore, legacy_profile
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.context import ContextAuthority, bind_context
from vgar.mcp.proposal.contracts import SnapshotBinding
from vgar.mcp.proposal.diff_tests_provider import DiffTestsProvider
from vgar.mcp.proposal.graph_jobs import resolver_fingerprint
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.ranking_provider import (
    CandidateEvidence,
    EvidenceRankingProvider,
    RankingPolicy,
)
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.proposal.verification_provider import StaticVerificationProvider
from vgar.repair.contracts import RepairPolicy, RepairTask
from vgar.repair.patch import PatchPolicy


def main():
    raw_root, stage = sys.argv[1:]
    root = Path(raw_root)
    data = json.loads((root / "handoff.json").read_bytes())
    binding = SnapshotBinding.model_validate(data["binding"])
    approved_diffs = frozenset(data["approved_diffs"])
    authority = ContextAuthority(root / "state")

    def context_factory(operation, request):
        context = bind_context(authority, repo_root=root / "repo", lease_root=root / "lease", output_root=root / "output",
                               request_id=uuid4().hex, deadline=time.time() + 60, **binding.model_dump())
        if stage == "test" and operation == "run_relevant_tests" and request.diff_hash in approved_diffs:
            return authority.grant(context, operation, request.input_hash())
        return context

    required = ()
    if stage == "verify":
        from vgar.mcp.servers import graph_server as server

        profile = legacy_profile(resolver_hash=resolver_fingerprint(), profile_hash=data["profile_hash"])
        store = SnapshotGraphStore(data["manifest"], graph_version=binding.snapshot_hash, profiles=(profile,))
        task = RepairTask.model_validate(data["task"])
        provider = StaticVerificationProvider(store, PatchPolicy(task.allowed_source_paths, task.fallback_scope),
                                              structural_policy=data["structural_policy"])
        record = ProviderBinding(provider, binding, frozenset({"verification", "resource_baseline"}))
        server.graph_service = SQLiteGraphService(store)
    elif stage == "test":
        from vgar.mcp.servers import execution_server as server

        task = RepairTask.model_validate(data["task"])
        provider = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace="ev3",
                                     snapshot_id=data["snapshot_id"], approved_fixture_diffs=approved_diffs)
        record = ProviderBinding(provider, binding, frozenset({"tests"}), lifecycle="guarded-v1", candidate_workspace="ev3")
    elif stage == "rank":
        from vgar.mcp.servers import graph_server as server

        policy = RankingPolicy.model_validate(data["policy"])
        pins = {key: CandidateEvidence.model_validate(value) for key, value in data["pins"].items()}
        provider = EvidenceRankingProvider(binding, snapshot_id=data["snapshot_id"], policy=policy, evidence_by_diff=pins)
        record = ProviderBinding(provider, binding, frozenset({"ranking"}))
        required = policy.required_checks
    else:
        raise ValueError(f"Unknown handoff stage: {stage}")

    server.core_tools = CoreTools(ProviderRegistry((record,), required_checks=required), context_factory=context_factory)
    server._audit_logger = AuditLogger(root / "output" / "audit.jsonl")
    server.main()


if __name__ == "__main__":
    main()
