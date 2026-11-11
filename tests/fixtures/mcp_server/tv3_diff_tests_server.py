"""Fixture host for real EV-3. The operator pins the only approved diff hash."""
import sys
import time
from pathlib import Path
from uuid import uuid4

from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.context import (
    ContextAuthority,
    bind_context,
    source_inventory_hash,
)
from vgar.mcp.proposal.contracts import SnapshotBinding, digest
from vgar.mcp.proposal.diff_tests_provider import DiffTestsProvider
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools
from vgar.repair.contracts import RepairPolicy, RepairTask


def main():
    root = Path(sys.argv[1])
    approved = sys.argv[2]
    task = RepairTask.model_validate_json((root / "task.json").read_bytes())
    authority = ContextAuthority(root / "state")
    source = source_inventory_hash(root / "repo")

    def context_factory(operation, request):
        ctx = bind_context(authority, repo_root=root / "repo", lease_root=root / "lease", output_root=root / "output",
                           request_id=uuid4().hex, run_id="ev3-wire", task_id=task.task_id, snapshot_hash=task.graph_version,
                           source_hash=source, config_hash=digest("ev3-fixture"), deadline=time.time() + 60)
        if operation == "run_relevant_tests" and request.diff_hash == approved:
            return authority.grant(ctx, operation, request.input_hash())
        return ctx

    binding = SnapshotBinding.from_context(context_factory(None, None))
    provider = DiffTestsProvider(task, RepairPolicy(), binding, candidate_workspace="ev3", approved_fixture_diffs=(approved,))
    record = ProviderBinding(provider, binding, frozenset({"tests"}), lifecycle="guarded-v1", candidate_workspace="ev3")
    from vgar.mcp.servers import execution_server
    execution_server.core_tools = CoreTools(ProviderRegistry((record,)), context_factory=context_factory)
    execution_server._audit_logger = AuditLogger(root / "output" / "audit.jsonl")
    execution_server.main()


if __name__ == "__main__":
    main()
