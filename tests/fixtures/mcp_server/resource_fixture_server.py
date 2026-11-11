"""Explicit synthetic STDIO server for URI and resource isolation tests; no real graph experiment."""
import argparse
import json
import time
from pathlib import Path

from vgar.contracts.graph import GraphNodeRef, GraphNodeRepo, GraphSubgraphResult
from vgar.graph.demo_service import DemoGraphService
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import (
    ContextAuthority,
    bind_context,
    request_scope,
    source_inventory_hash,
)
from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    for name in ("repo", "lease", "output", "state"):
        (root / name).mkdir(parents=True, exist_ok=False)
    ctx = bind_context(ContextAuthority(root / "state"), repo_root=root / "repo", lease_root=root / "lease",
        output_root=root / "output", request_id="synthetic-resource-read", run_id="synthetic-run", task_id="synthetic-task",
        snapshot_hash=c.digest("synthetic-resource-snapshot"), source_hash=source_inventory_hash(root / "repo"),
        config_hash=c.digest("synthetic-resource-config"), deadline=time.time()+90, secrets=("synthetic-secret-value",))
    details = '{"public":true,"synthetic":true}'
    (ctx.output_root / "baseline.json").write_text(details, encoding="utf-8")
    log = AuditLogger(ctx.output_root / "audit.jsonl")
    with request_scope(ctx):
        log.write("synthetic-seed", {"number": 0})

    class SyntheticService(DemoGraphService):
        def get_repository_summary(self):
            return super().get_repository_summary().model_copy(update={"graph_version": ctx.snapshot_hash})

        def get_node(self, node_id):
            from vgar.contracts.error import NodeNotFoundError
            if node_id not in {"fixture:a/b:π", "fixture:a%2Fb", "fixture:simple"}:
                raise NodeNotFoundError(node_id)
            return GraphNodeRef(repo=GraphNodeRepo(node_id=node_id, type="Function", path="synthetic.py",
                                                 provenance="synthetic handwritten URI fixture"))

        def get_subgraph(self, node_id, *, depth=2, limit=200):
            return GraphSubgraphResult(anchor_id=node_id, depth=depth, nodes=[self.get_node(node_id)], edges=[])

    class SyntheticResourceProvider:
        def snapshot_resource(self, request, context):
            payload = {"synthetic": True, "kind": request.kind, "id": request.resource_id,
                       "password": "must-hide", "note": "synthetic-secret-value", "env": {"OTHER": "must-hide"}}
            if request.kind == "baseline": payload["public"] = True
            return c.ResourceResult(binding=c.SnapshotBinding.from_context(context), resource_kind=request.kind,
                resource_id=request.resource_id, payload_json=json.dumps(payload, ensure_ascii=False), availability="AVAILABLE",
                evidence=(c.EvidenceRef(path="baseline.json", sha256=c.digest(details)),))

    registry = ProviderRegistry((ProviderBinding(SyntheticResourceProvider(), c.SnapshotBinding.from_context(ctx),
        frozenset({"resource_schema", "resource_component", "resource_task", "resource_baseline"}), synthetic=True),), test_only=True)
    from vgar.mcp.servers import graph_server as module
    module.core_tools = CoreTools(registry, context_factory=lambda operation, request: ctx)
    module.graph_service = SyntheticService()
    module._audit_logger = log
    # Fixture-only entrypoint; production main rejects this registry.
    module.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
