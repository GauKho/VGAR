"""Trusted fixture bootstrap for the real TV3 verification provider."""
import sys
import time
from pathlib import Path
from uuid import uuid4

from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.storage_capabilities import SnapshotGraphStore, legacy_profile
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.context import ContextAuthority, bind_context
from vgar.mcp.proposal.contracts import SnapshotBinding
from vgar.mcp.proposal.graph_jobs import resolver_fingerprint
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.proposal.verification_provider import StaticVerificationProvider
from vgar.repair.patch import PatchPolicy


def main():
    raw_root, manifest, graph_version, profile_hash = sys.argv[1:]
    root = Path(raw_root)
    profile = legacy_profile(resolver_hash=resolver_fingerprint(), profile_hash=profile_hash)
    store = SnapshotGraphStore(manifest, graph_version=graph_version, profiles=(profile,))
    authority = ContextAuthority(root / "state")
    provider = StaticVerificationProvider(store, PatchPolicy(("src/a.py", "src/b.py"), ("tests",)))

    def context_factory(_operation, _request):
        return bind_context(authority, repo_root=root / "repo", lease_root=root / "lease", output_root=root / "output",
                            request_id=uuid4().hex, run_id="wire-run", task_id="wire-task", snapshot_hash=graph_version,
                            source_hash=store.identity.source_inventory_hash, config_hash=provider.config_hash,
                            deadline=time.time() + 90)

    binding = ProviderBinding(provider, SnapshotBinding.from_context(context_factory(None, None)),
                              frozenset({"verification", "resource_baseline"}))
    from vgar.mcp.servers import graph_server
    graph_server.core_tools = CoreTools(ProviderRegistry((binding,)), context_factory=context_factory)
    graph_server.graph_service = SQLiteGraphService(store)
    graph_server._audit_logger = AuditLogger(root / "output" / "audit.jsonl")
    graph_server.main()


if __name__ == "__main__":
    main()
