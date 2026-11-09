"""FIXTURE INPUTS ONLY; real static builder/storage, no synthetic graph provider.

Auto-grants below are explicit test bootstrap authorization, never production
policy or model-controlled confirmation. Target Python is parsed, not executed.
"""
import argparse
import json
import time
from pathlib import Path

from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.storage_capabilities import SnapshotGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.context import (
    ContextAuthority,
    bind_context,
    source_inventory_hash,
)
from vgar.mcp.proposal.contracts import digest
from vgar.mcp.proposal.graph_jobs import GraphJobConfig, GraphJobController
from vgar.mcp.proposal.ports import ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root
    for name in ("repo", "lease", "output", "state"):
        (root / name).mkdir(parents=True, exist_ok=False)
    (root / "repo/src").mkdir()
    (root / "repo/src/a.py").write_text("raise RuntimeError('TARGET_MUST_NOT_EXECUTE')\ndef value():\n    return 1\n", encoding="utf-8")
    authority = ContextAuthority(root / "state")
    config_hash = digest("fixture-static-config")
    config = GraphJobConfig(repo_root=root/"repo", output_root=root/"output", state_root=root/"state",
        repo_key="demo/serving", repository_revision="fixture-revision", config_hash=config_hash, profile_hash=config_hash)
    selected = {"version": digest("fixture-unbuilt-anchor")}

    def context_factory(operation, request):
        ctx = bind_context(authority, repo_root=root/"repo", lease_root=root/"lease", output_root=root/"output",
            request_id="fixture-"+str(time.monotonic_ns()), run_id="fixture-run", task_id="fixture-task",
            snapshot_hash=selected["version"], source_hash=source_inventory_hash(root/"repo"),
            config_hash=config_hash, deadline=time.time()+90)
        if operation == "build_or_update_graph":
            if Path(request.repo_path).resolve() != ctx.repo_root:
                raise ValueError("Fixture operator did not authorize this repo")
            return authority.grant(ctx, operation, request.input_hash())
        return ctx

    def issue(ctx, identity):
        derived = bind_context(authority, repo_root=ctx.repo_root, lease_root=ctx.lease_root,
            output_root=ctx.output_root, request_id=ctx.request_id, run_id=ctx.run_id, task_id=ctx.task_id,
            snapshot_hash=identity.snapshot_id, source_hash=ctx.source_hash, config_hash=ctx.config_hash,
            deadline=ctx.deadline, limits=ctx.limits)
        return authority.grant(derived, "storage_ingest", identity.snapshot_id)

    controller = GraphJobController(config, storage_issuer=issue)
    tools = CoreTools(ProviderRegistry(), graph_jobs=controller, context_factory=context_factory)
    from vgar.mcp.servers import graph_server as server
    server.core_tools = tools
    server._audit_logger = AuditLogger(root / "output/audit.jsonl")
    original_build = tools.build
    async def build(request, ctx):
        result = await original_build(request, ctx)
        evidence = json.loads((ctx.output_root/result.evidence[0].path).read_bytes())
        # Host explicitly binds this returned manifest for subsequent reads;
        # never query filesystem 'latest' or rebind an existing reader.
        store = SnapshotGraphStore(ctx.output_root/evidence["manifest"], graph_version=result.result_snapshot_hash,
                                   profiles=(controller.profile(),))
        server.graph_service = SQLiteGraphService(store)
        selected["version"] = result.result_snapshot_hash
        return result
    tools.build = build
    server.main()


if __name__ == "__main__":
    main()
