"""SYNTHETIC ONLY: scripted SDK wire oracle, no model, Docker or production provider."""
import argparse
import time
from pathlib import Path

from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import (
    ContextAuthority,
    bind_context,
    source_inventory_hash,
)
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--server", choices=("graph", "execution"), required=True)
    args = parser.parse_args()
    root = Path(args.root)
    for name in ("repo", "lease", "output", "state"):
        (root / name).mkdir(parents=True, exist_ok=False)
    authority = ContextAuthority(root / "state")
    base = bind_context(authority, repo_root=root / "repo", lease_root=root / "lease", output_root=root / "output",
                        request_id="synthetic-wire", run_id="synthetic-run", task_id="synthetic-task",
                        snapshot_hash=c.digest("synthetic-snapshot"), source_hash=source_inventory_hash(root / "repo"),
                        config_hash=c.digest("synthetic-config"), deadline=time.time()+90)

    class SyntheticProvider:
        def evidence(self):
            path = base.output_root / "synthetic-details.json"
            path.write_text('{"synthetic":true}', encoding="utf-8")
            return (c.EvidenceRef(path=path.name, sha256=c.digest('{"synthetic":true}')),)

        async def build_or_update(self, request, context):
            return c.BuildResult(binding=c.SnapshotBinding.from_context(context), result_snapshot_hash=context.snapshot_hash,
                                 capabilities=("synthetic-only",), evidence=self.evidence())

        def explain_path(self, request, context):
            return c.PathResult(binding=c.SnapshotBinding.from_context(context), nodes=(request.source_id, request.target_id),
                edges=(c.Witness(edge_id="synthetic-call", edge_type="CALLS", source_id=request.source_id,
                                 target_id=request.target_id, confidence=1, provenance="handwritten synthetic oracle"),),
                examined_edges=1, evidence=self.evidence())

        def traverse(self, request, context):
            return c.TraversalResult(binding=c.SnapshotBinding.from_context(context), symbols=(
                c.RelatedSymbol(symbol_id="fixture-related", name="related", kind="Function", path="synthetic.py", hop=1),),
                examined_edges=1, evidence=self.evidence())

        def verify_graph(self, request, context):
            return c.CheckEvidence(binding=c.SnapshotBinding.from_context(context), diff_hash=request.diff_hash,
                status="FAIL" if request.diff == "BAD" else "PASS", reasons=("SYNTHETIC_ONLY",), scope=("synthetic-cycle",),
                coverage="COMPLETE", evidence=self.evidence())

        def rank_candidates(self, request, context):
            return c.RankResult(binding=c.SnapshotBinding.from_context(context), evidence=self.evidence(), candidates=tuple(
                c.RankedCandidate(candidate_id=item.candidate_id, diff_hash=item.diff_hash, eligible=True,
                                  score=99 if item.diff == "BAD" else 1,
                                  checks=(c.NamedCheck(name="tests", status="FAIL" if item.diff == "BAD" else "PASS"),))
                for item in request.candidates))

        async def run_diff_tests(self, request, context):
            # Simulated provider lifecycle. This does not claim to execute target pytest.
            candidate = context.lease_root / "synthetic-candidate"
            candidate.mkdir()
            try:
                (candidate / "patch.txt").write_bytes(request.diff.encode("utf-8"))
            finally:
                (candidate / "patch.txt").unlink(); candidate.rmdir()
            return c.TestEvidence(binding=c.SnapshotBinding.from_context(context), diff_hash=request.diff_hash,
                status="PASS", reasons=("SYNTHETIC_SIMULATED_EXECUTION",), scope=("synthetic",), coverage="COMPLETE",
                evidence=self.evidence(), receipt=c.TestReceipt(workspace="synthetic-candidate", diff_hash=request.diff_hash,
                    admitted=True, applied_count=1, executed=True, cleaned=True))

    provider = SyntheticProvider()
    record = ProviderBinding(provider, c.SnapshotBinding.from_context(base), frozenset({"build", "path", "traversal", "verification", "ranking", "tests"}),
                             synthetic=True, lifecycle="guarded-v1", candidate_workspace="synthetic-candidate")

    def context_factory(operation, request):
        # This is trusted fixture bootstrap, not a production auto-grant rule.
        if operation in {"build_or_update_graph", "run_relevant_tests"}:
            return authority.grant(base, operation, request.input_hash())
        return base

    tools = CoreTools(ProviderRegistry((record,), test_only=True, required_checks=("tests",)), context_factory=context_factory)
    if args.server == "graph":
        from vgar.mcp.servers import graph_server as module
    else:
        from vgar.mcp.servers import execution_server as module
    module.core_tools = tools
    module._audit_logger = AuditLogger(base.output_root / "audit.jsonl")
    # Deliberately bypass production main, which rejects test-only registries.
    module.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
