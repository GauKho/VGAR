"""Seed a sealed snapshot for a byte-approved TV3 repair fixture."""
import shutil
import time
from pathlib import Path
from uuid import uuid4

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.storage_capabilities import (
    SnapshotGraphStore,
    SQLiteSnapshotStorage,
    legacy_profile,
)
from vgar.mcp.proposal import contracts as c
from vgar.mcp.proposal.context import (
    ContextAuthority,
    bind_context,
    source_inventory_hash,
)
from vgar.mcp.proposal.graph_jobs import resolver_fingerprint
from vgar.mcp.proposal.verification_provider import StaticVerificationProvider
from vgar.repair.config import load_task
from vgar.repair.evidence import digest
from vgar.repair.patch import PatchPolicy

ROOT = Path(__file__).resolve().parents[2]
TASK = "single_file_login"
FAILURE = "tests/test_auth.py::test_login_rejects_whitespace"
REGRESSION = "tests/test_auth.py::test_login_accepts_name"
GOOD = "--- a/auth.py\n+++ b/auth.py\n@@ -2 +2 @@\n-    return bool(value)\n+    return bool(value.strip())\n"
BAD = GOOD.replace("bool(value.strip())", "False")
STRUCTURAL_POLICY = {"repo_key": "fixture/login", "forbidden_imports": [{"source": "auth", "target": "tests"}]}


def seed_snapshot(root, *, task_id=TASK, structural_policy=STRUCTURAL_POLICY, run_id="ev1-run"):
    repo, lease, output, state = (root / name for name in ("repo", "lease", "output", "state"))
    for folder in (lease, output, state):
        folder.mkdir()
    fixture = load_task(ROOT / "examples/m2/tasks" / f"{task_id}.json")
    repo_key = structural_policy["repo_key"]
    shutil.copytree(fixture.source_repo, repo,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    doc = PythonGraphBuilder(repo_key=repo_key, repository_revision=fixture.revision).build(repo)
    source_hash = source_inventory_hash(repo)
    profile = legacy_profile(resolver_hash=resolver_fingerprint(), profile_hash=digest("ranking fixture"))
    storage = SQLiteSnapshotStorage(output, profiles=(profile,))
    identity = storage.identity(doc, source_inventory_hash=source_hash)
    authority = ContextAuthority(state)

    def context(*, snapshot_hash=identity.graph_version, config_hash=profile.profile_hash, run_id=run_id):
        return bind_context(authority, repo_root=repo, lease_root=lease, output_root=output, request_id=uuid4().hex,
                            run_id=run_id, task_id=task_id, snapshot_hash=snapshot_hash, source_hash=source_hash,
                            config_hash=config_hash, deadline=time.time() + 90)

    write = context(snapshot_hash=identity.snapshot_id)
    manifest = storage.ingest(doc, context=authority.grant(write, "storage_ingest", identity.snapshot_id))
    store = SnapshotGraphStore(manifest, graph_version=identity.graph_version, profiles=(profile,))
    verification = StaticVerificationProvider(store, PatchPolicy(fixture.allowed_source_paths, fixture.fallback_scope),
                                              structural_policy=structural_policy)
    ctx = context(config_hash=verification.config_hash)
    binding = c.SnapshotBinding.from_context(ctx)
    task = fixture.model_copy(update={"source_repo": repo, "repo_key": repo_key,
                                      "graph_version": identity.graph_version, "bundle_directory": output})
    return store, task, binding, verification, authority, context
