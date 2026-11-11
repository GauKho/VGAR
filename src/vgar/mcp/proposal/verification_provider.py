"""TV3 EV-2 provider for static Python checks on a sealed legacy snapshot."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from vgar.contracts.schema import GraphValidationError
from vgar.graph.builder import (
    RESOLVER_PROFILE,
    PythonGraphBuilder,
    discover_python_files,
)
from vgar.graph.storage_capabilities import (
    SnapshotGraphStore,
    canonical_bytes,
    legacy_profile,
)
from vgar.repair.api_check import check_api
from vgar.repair.contracts import safe_path
from vgar.repair.evidence import atomic_json, digest, encode_json
from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff
from vgar.repair.source_imports import PROFILE as SOURCE_IMPORT_PROFILE
from vgar.repair.source_imports import check_source_import_cycles
from vgar.repair.structural_check import check_structure
from vgar.repair.structural_config import validate_structural_config

from . import contracts as c
from .context import BoundContext, check_context, check_source, request_commit_guard
from .graph_jobs import resolver_fingerprint
from .resources import encode_resource
from .security import read_lease_bytes, resolve_read_path

PROFILE = "tv3-static-ev2-v1"
LIMITATIONS = ("ARCHITECTURE_PORT_AND_FANOUT_NOT_MEASURED", "RUNTIME_INVARIANTS_NOT_MEASURED")


class StaticVerificationProvider:
    """Verify modify-only patches against a host-selected snapshot and policy."""

    def __init__(self, store: SnapshotGraphStore, patch_policy: PatchPolicy, *,
                 source_roots: tuple[str, ...] = ("src",), structural_policy=None):
        identity = store.identity
        expected = legacy_profile(resolver_hash=resolver_fingerprint(), profile_hash=identity.profile_hash)
        if (identity.schema_hash, identity.resolver_hash) != (expected.schema_hash, expected.resolver_hash):
            raise ValueError("EV-2 requires the current static legacy schema and resolver")
        if (type(patch_policy) is not PatchPolicy or type(patch_policy.allowed_paths) is not tuple
                or not patch_policy.allowed_paths or any(not safe_path(path).endswith(".py") for path in patch_policy.allowed_paths)):
            raise ValueError("EV-2 requires explicit Python patch paths")
        if type(patch_policy.protected_paths) is not tuple or any(not safe_path(path) for path in patch_policy.protected_paths):
            raise ValueError("EV-2 requires pinned protected paths")
        if any(type(limit) is not int or limit < 1 for limit in (
            patch_policy.max_bytes, patch_policy.max_files, patch_policy.max_changed_lines,
        )):
            raise ValueError("EV-2 requires positive integer patch limits")
        if type(source_roots) is not tuple or any(not safe_path(path) for path in source_roots):
            raise ValueError("EV-2 requires pinned repository-relative source roots")
        self._store = store
        self._patch_policy = patch_policy
        self._source_roots = source_roots
        doc = store.load_document(identity.graph_version)
        resolver = doc.get("statistics", {}).get("resolver", {})
        if (resolver.get("requested"), resolver.get("active"), resolver.get("profile")) != (
            "static", "static", RESOLVER_PROFILE,
        ):
            raise ValueError("EV-2 baseline must use the static resolver")
        self._structural_policy = (None if structural_policy is None
                                   else validate_structural_config(structural_policy, repo_key=doc["repo_key"]))
        policy = self._structural_policy or {}
        self._limitations = LIMITATIONS + tuple(f"{name.upper()}_POLICY_NOT_CONFIGURED"
                                                for name in ("forbidden_imports", "layers") if name not in policy)
        self._config_hash = digest(canonical_bytes({
            "verification_profile": PROFILE, "schema_hash": identity.schema_hash, "resolver_hash": identity.resolver_hash,
            "storage_profile_hash": identity.profile_hash,
            "source_roots": source_roots, "patch_policy": asdict(patch_policy), "structural_policy": self._structural_policy,
            "source_import_profile": SOURCE_IMPORT_PROFILE,
        }))

    @property
    def config_hash(self) -> str:
        return self._config_hash

    def _baseline(self, context: BoundContext):
        check_source(context)
        identity = self._store.identity
        if (context.snapshot_hash, context.source_hash, context.config_hash) != (
            identity.graph_version, identity.source_inventory_hash, self.config_hash,
        ):
            raise ValueError("Verification snapshot/source/config binding mismatch")
        return self._store.load_document(identity.graph_version)

    def verify_graph(self, request: c.DiffRequest, context: BoundContext) -> c.CheckEvidence:
        baseline = self._baseline(context)
        status, coverage, scope, reasons, checks, candidate = self._verify(request, context, baseline)
        binding = c.SnapshotBinding.from_context(context)
        record = {
            "profile": PROFILE, "binding": binding.model_dump(), "diff_hash": request.diff_hash,
            "snapshot_id": self._store.identity.snapshot_id, "status": status, "coverage": coverage,
            "scope": scope, "reasons": reasons, "checks": checks, "candidate_graph_version": candidate,
            "limitations": self._limitations,
        }
        if len(encode_json(record)) > context.limits.read_bytes:
            status, coverage, reasons = "ERROR", "PARTIAL", ("EVIDENCE_BYTE_LIMIT",)
            record.update(status=status, coverage=coverage, reasons=reasons, checks={})
        ref = self._publish(context, record)
        return c.CheckEvidence(binding=binding, diff_hash=request.diff_hash, status=status,
                               coverage=coverage, scope=scope, reasons=reasons, evidence=(ref,))

    def snapshot_resource(self, request: c.ResourceRequest, context: BoundContext) -> c.ResourceResult:
        if request.kind != "baseline":
            raise ValueError("Verification provider only serves baseline evidence")
        baseline = self._baseline(context)
        identity = self._store.identity
        binding = c.SnapshotBinding.from_context(context)
        reasons = ("BASELINE_TESTS_NOT_MEASURED", "RUNTIME_INVARIANTS_NOT_MEASURED")
        payload = {
            "profile": PROFILE, "snapshot_id": identity.snapshot_id, "graph_version": identity.graph_version,
            "graph_document_hash": identity.canonical_document_hash, "schema_hash": identity.schema_hash,
            "resolver_hash": identity.resolver_hash,
            "python_file_count": sum(1 for _ in self._baseline_sources(context, baseline)),
            "checks": {"schema": "PASS", "baseline_tests": "NOT_RUN", "semantic_invariants": "NOT_RUN"},
            "limitations": self._limitations,
        }
        ref = self._publish(context, {**payload, "binding": binding.model_dump(), "availability": "PARTIAL",
                                      "reasons": reasons}, prefix="tv3-baseline")
        return c.ResourceResult(binding=binding, resource_kind="baseline", resource_id=request.resource_id,
                                payload_json=encode_resource(payload), availability="PARTIAL", reasons=reasons,
                                evidence=(ref,))

    def _baseline_sources(self, context, baseline):
        hashes = {node["path"]: node["content_hash"] for node in baseline["nodes"] if node["type"] == "File"}
        paths = {path.relative_to(context.repo_root).as_posix() for path in discover_python_files(context.repo_root)}
        if paths != hashes.keys() or not set(self._patch_policy.allowed_paths) <= paths:
            raise ValueError("Verification Python inventory or policy scope differs from snapshot")
        for path in sorted(paths):
            check_context(context)
            raw, size = read_lease_bytes(context.repo_root, path, 16 * 1024 * 1024)
            if len(raw) != size or digest(raw) != hashes[path]:
                raise ValueError("Verification source bytes differ from snapshot")
            yield path, raw

    def _verify(self, request, context, baseline):
        try:
            patch = parse_unified_diff(request.diff, self._patch_policy)
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return "FAIL", "PARTIAL", (), ("PATCH_POLICY_REJECTED",), {}, None
        scope = tuple(sorted(patch.files))
        before = {}
        with TemporaryDirectory(prefix="tv3-ev2-", dir=context.state_root) as folder:
            root = Path(folder)
            for path, raw in self._baseline_sources(context, baseline):
                before[path] = raw
                output = resolve_read_path(root, path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(raw)

            builder = PythonGraphBuilder(repo_key=baseline["repo_key"], repository_revision=baseline["repository_revision"],
                                         source_roots=self._source_roots)
            builder.trace.path = None  # Static verification publishes its own bounded evidence.
            if builder._calculate_graph_version(root, discover_python_files(root)) != baseline["graph_version"]:
                raise ValueError("Verification builder options differ from snapshot")
            try:
                changed, _ = _bind(patch, root)
            except (ValueError, UnicodeError):
                return "FAIL", "PARTIAL", scope, ("PATCH_BASELINE_MISMATCH",), {}, None
            for path, raw in changed.items():
                try:
                    compile(raw, path, "exec", dont_inherit=True)
                except (SyntaxError, ValueError):
                    return "FAIL", "PARTIAL", scope, ("CANDIDATE_SYNTAX_ERROR",), {}, None
                resolve_read_path(root, path).write_bytes(raw)
            check_context(context)
            try:
                candidate = builder.build(root)
            except GraphValidationError:
                return "FAIL", "PARTIAL", scope, ("CANDIDATE_SCHEMA_VIOLATION",), {}, None

        baseline_repo = next(node for node in baseline["nodes"] if node["type"] == "Repository")
        candidate_repo = next(node for node in candidate["nodes"] if node["type"] == "Repository")
        candidate_repo["name"] = baseline_repo["name"]
        candidate_repo["properties"]["root_uri"] = baseline_repo["properties"]["root_uri"]
        candidate["statistics"].pop("build_time_ms", None)
        api = check_api({path: before[path] for path in scope}, changed, changed_only=True)
        structure = check_structure(baseline, candidate, before_sources=before, after_sources={**before, **changed},
                                    repo_config=self._structural_policy)
        source_imports = check_source_import_cycles(baseline, candidate, before, {**before, **changed})
        # Full-repo source hashes are already pinned by the baseline and candidate graph versions.
        structural_details = {key: val for key, val in structure.details.items() if key != "source_hashes"}
        checks = {"schema": {"status": "PASS", "schema_hash": self._store.identity.schema_hash},
                  "api": asdict(api), "structural": {**asdict(structure), "details": structural_details},
                  "source_imports": asdict(source_imports)}
        states = {api.status, structure.status, source_imports.status}
        reasons = tuple(dict.fromkeys((*api.reasons, *structure.reasons, *source_imports.reasons)))
        status = next(value for value in ("ERROR", "FAIL", "NOT_RUN", "PASS") if value in states)
        coverage = "PARTIAL" if states & {"NOT_RUN", "ERROR"} else "COMPLETE"
        return status, coverage, scope, reasons, checks, candidate["graph_version"]

    def _publish(self, context, record, *, prefix="tv3-ev2"):
        name = f"{prefix}-{uuid4().hex}.json"
        raw = encode_json(record)
        if len(raw) > context.limits.read_bytes:
            raise ValueError("Verification evidence cannot fit the host byte limit")
        with request_commit_guard(context):
            check_source(context)
            self._store.resolve_graph_version()
            target = resolve_read_path(context.output_root, name)
            check_context(context)
            atomic_json(target, record)
        return c.EvidenceRef(path=name, sha256=digest(raw))
