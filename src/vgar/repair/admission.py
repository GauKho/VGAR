"""Externally pinned SWE-bench admission, separate from native fixture trust.

Hashes ensure consistency with caller-supplied pins, not signatures/authentication.
Only base bytes and independently authored issue-reproduction overlays are accepted.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from vgar.evaluation.harness.task_env import (
    canonical_hash,
    docker_environment,
    validate_profile,
)
from vgar.evaluation.retrieval.pilot_manifest import W10_SELECTION, validate_manifest
from vgar.repair.contracts import RepairTask, safe_path
from vgar.repair.evidence import digest
from vgar.repair.executor import run_bounded
from vgar.repair.experiment import validate_hashes
from vgar.repair.workspace import IGNORED, create_workspace, inventory, link_entry

SCHEMA = "vgar-repair-admission-v1"
VISIBILITY = "issue_reproduction_no_benchmark_oracle"


def _git(source, *args):
    command = (
        "git",
        "--no-replace-objects",
        "-c",
        "core.hooksPath=",
        "-c",
        "core.quotePath=false",
        *args,
    )
    result = run_bounded(command, Path(source), 30)
    if not result["complete"] or result["exit_code"] != 0:
        raise ValueError("Cannot verify base Git identity: " + result["stderr"])
    return result["stdout"]


def base_inventory(source, commit):
    """Prove exact file bytes against tree object IDs, independent of index/filters."""
    source = Path(source)
    actual = inventory(source)
    if _git(source, "rev-parse", "HEAD").strip() != commit:
        raise ValueError("Source HEAD differs from pinned base_commit")
    rows = _git(source, "ls-tree", "-rz", "--full-tree", commit).split("\0")
    expected = {}
    for row in rows:
        if not row:
            continue
        metadata, relative = row.split("\t", 1)
        mode, kind, oid = metadata.split()
        safe_path(relative)
        if kind != "blob" or mode not in ("100644", "100755", "120000"):
            raise ValueError("Base tree contains unsupported submodule/object")
        if any(part in IGNORED for part in Path(relative).parts):
            raise ValueError("Tracked file overlaps ignored execution inventory")
        if mode == "120000":
            # A Git link blob is its target string; inventory() already refused unsafe targets.
            if not (source / relative).is_symlink():
                raise ValueError("Source bytes differ from pinned Git blob: " + relative)
            target = os.readlink(source / relative)
            raw = target.encode("utf-8")
        else:
            raw = (source / relative).read_bytes()
        git_hash = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw
        ).hexdigest()
        if git_hash != oid:
            raise ValueError("Source bytes differ from pinned Git blob: " + relative)
        expected[relative] = link_entry(target) if mode == "120000" else digest(raw)
    if expected != actual:
        raise ValueError("Source inventory differs from exact pinned base tree")
    return actual


def _inputs(task, manifest_path, profile_path, manifest_hash, profile_hash):
    if any(
        not isinstance(h, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", h)
        for h in (manifest_hash, profile_hash)
    ):
        raise ValueError("Independent nonempty manifest/profile SHA-256 pins required")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    # The independent hash pin fixes the population; the pilot also keeps its five-task order check.
    validate_manifest(manifest, expected_hash=manifest_hash,
                      **({'expected_ids': None} if manifest.get('selection_policy') == W10_SELECTION else {}))
    rows = [r for r in manifest["tasks"] if r["instance_id"] == task.task_id]
    if len(rows) != 1:
        raise ValueError("Task missing/duplicated in approved manifest")
    row = rows[0]
    if (task.repo_key, task.revision, task.issue_text) != (
        row["repo"],
        row["base_commit"],
        row["problem_statement"],
    ):
        raise ValueError("Repair task differs from manifest repo/base/issue")
    profile = validate_profile(
        json.loads(Path(profile_path).read_text(encoding="utf-8")), expected_task=row
    )
    if profile["profile_hash"] != profile_hash:
        raise ValueError("Environment differs from independently expected profile hash")
    if profile["status"] != "COLLECTED":
        raise ValueError(
            "Admission requires a COLLECTED profile; excluded tasks stay excluded"
        )
    return profile


def _scope(task, roots, files, overlay):
    if not isinstance(roots, list) or not roots or roots != sorted(set(roots)):
        raise ValueError("Sorted nonempty production source roots required")
    for root in roots:
        safe_path(root)
        if any(p.lower() in ("test", "tests", "testing") for p in root.split("/")):
            raise ValueError("Production scope cannot be a test directory")
    allowed = tuple(
        sorted(
            p
            for p in files
            if p.endswith(".py")
            and any(p.startswith(r + "/") for r in roots)
            and not any(
                s.lower() in ("test", "tests", "testing") for s in p.split("/")[:-1]
            )
            and not Path(p).name.startswith(("test_", "conftest"))
        )
    )
    if not allowed or task.allowed_source_paths != allowed or task.trusted_fixture:
        raise ValueError(
            "Allowed paths must equal the production inventory scope, without fixture trust"
        )
    if any(
        p == protected or p.startswith(protected + "/")
        for p in allowed
        for protected in task.protected_paths
    ):
        raise ValueError("Allowed paths overlap protected paths")
    if not isinstance(overlay, dict):
        raise ValueError("Overlay must be a path/text mapping")
    for path, text in overlay.items():
        safe_path(path)
        if (
            # Reserved marker in any component: repo-native runners need e.g. tests/vgar_w9_repro_x/ (Django app)
            # or <package>/vgar_w9_repro_x/test_*.py (sympy bin/test ignores files outside the package).
            not any(part.startswith("vgar_w9_repro_") for part in path.split("/"))
            or not path.endswith(".py")
            or path in files
            or not isinstance(text, str)
            or not text
            or len(text.encode()) > 65536
            or not any(
                path == r or path.startswith(r + "/") for r in task.protected_paths
            )
        ):
            raise ValueError(
                "Only new bounded protected issue reproduction test overlays are allowed"
            )
    if not task.failing_selectors or not task.fallback_scope:
        raise ValueError("Explicit failing selectors and regression scope required")
    for selector in (*task.failing_selectors, *task.fallback_scope):
        path = selector.split("::")[0]
        matches = [
            p for p in (*files, *overlay) if p == path or p.startswith(path + "/")
        ]
        if not matches or any(p in allowed for p in matches):
            raise ValueError(
                "Test scope must reference base/overlay tests outside editable production paths"
            )


@dataclass(frozen=True)
class RepairAdmission:
    _value: dict

    def snapshot(self):
        return copy.deepcopy(self._value)


def admit_task(
    task,
    manifest_path,
    profile_path,
    *,
    expected_manifest_hash,
    expected_profile_hash,
    bundle_hashes,
    source_roots,
    overlay=None,
    docker_host="unix:///var/run/docker.sock",
):
    task = RepairTask.model_validate(task.model_dump())
    profile = _inputs(
        task, manifest_path, profile_path, expected_manifest_hash, expected_profile_hash
    )
    files = base_inventory(task.source_repo, task.revision)
    overlay = copy.deepcopy(overlay or {})
    _scope(task, source_roots, files, overlay)
    pyfiles = [
        [p, files[p].removeprefix("sha256:")]
        for p in sorted(files)
        if p.endswith(".py")
    ]
    identity = profile["source_before"]
    if (
        canonical_hash(pyfiles) != identity["inventory_hash"]
        or len(pyfiles) != identity["inventory_count"]
    ):
        raise ValueError("Source differs from qualified profile Python inventory")
    hashes = validate_hashes(bundle_hashes)
    if hashes is None or any(
        digest((task.bundle_directory / n).read_bytes()) != h for n, h in hashes.items()
    ):
        raise ValueError("Independent handoff bundle hashes required/mismatched")
    docker_environment(docker_host)
    value = dict(
        schema=SCHEMA,
        visibility=VISIBILITY,
        manifest_path=str(Path(manifest_path).resolve()),
        profile_path=str(Path(profile_path).resolve()),
        expected_manifest_hash=expected_manifest_hash,
        expected_profile_hash=expected_profile_hash,
        task_hash=canonical_hash(task.model_dump(mode="json")),
        inventory=files,
        inventory_hash=canonical_hash(files),
        source_roots=list(source_roots),
        overlay=overlay,
        overlay_hash=canonical_hash(overlay),
        bundle_hashes=hashes,
        docker_host=docker_host,
    )
    value["admission_hash"] = canonical_hash(value)
    return RepairAdmission(value)


def validate_admission(task, value, *, verify_source=True):
    if isinstance(value, RepairAdmission):
        value = value.snapshot()
    if not isinstance(value, dict):
        raise ValueError("Explicit admission snapshot required")
    keys = {
        "schema",
        "visibility",
        "manifest_path",
        "profile_path",
        "expected_manifest_hash",
        "expected_profile_hash",
        "task_hash",
        "inventory",
        "inventory_hash",
        "source_roots",
        "overlay",
        "overlay_hash",
        "bundle_hashes",
        "docker_host",
        "admission_hash",
    }
    if (
        set(value) != keys
        or value["schema"] != SCHEMA
        or value["visibility"] != VISIBILITY
    ):
        raise ValueError("Invalid admission schema/visibility")
    if (
        canonical_hash({k: v for k, v in value.items() if k != "admission_hash"})
        != value["admission_hash"]
    ):
        raise ValueError("Admission snapshot hash mismatch")
    task = RepairTask.model_validate(task.model_dump())
    if (
        value["task_hash"] != canonical_hash(task.model_dump(mode="json"))
        or value["inventory_hash"] != canonical_hash(value["inventory"])
        or value["overlay_hash"] != canonical_hash(value["overlay"])
    ):
        raise ValueError("Admission task/inventory/overlay hash mismatch")
    _scope(task, value["source_roots"], value["inventory"], value["overlay"])
    if validate_hashes(value["bundle_hashes"]) is None:
        raise ValueError("Admission must retain bundle pins")
    if not verify_source:
        return RepairAdmission(copy.deepcopy(value))
    regenerated = admit_task(
        task,
        value["manifest_path"],
        value["profile_path"],
        **{
            k: value[k]
            for k in (
                "expected_manifest_hash",
                "expected_profile_hash",
                "bundle_hashes",
                "source_roots",
                "overlay",
                "docker_host",
            )
        },
    )
    if regenerated.snapshot() != value:
        raise ValueError("Admission task/source/profile binding changed")
    return regenerated


def check_session_admission(state, record):
    state_runtime = state.get("policy", {}).get("runtime")
    record_runtime = record.get("policy", {}).get("runtime")
    opted = state_runtime == "docker_admitted" or record_runtime == "docker_admitted"
    opted |= any("admission" in x or "admission_required" in x for x in (state, record))
    if not opted:
        return None
    if (
        state_runtime != "docker_admitted"
        or record_runtime != "docker_admitted"
        or state.get("admission_required") is not True
        or record.get("admission_required") is not True
        or not state.get("admission")
        or state.get("admission") != record.get("admission")
        or state.get("task") != record.get("task")
    ):
        raise ValueError("Session/record admission missing or inconsistent")
    return validate_admission(
        RepairTask.model_validate(state["task"]),
        state["admission"],
        verify_source=False,
    )


def prepare_admitted_workspace(task, admission, temp_root, *, deadline=None):
    value = validate_admission(task, admission).snapshot()
    lease = create_workspace(
        task.source_repo, temp_root, deadline=deadline, allow_attributes=True
    )
    try:
        if lease.before != value["inventory"]:
            raise ValueError("Source drift during private workspace creation")
        for relative, text in value["overlay"].items():
            target = lease.path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(text.encode("utf-8"))
        lease.execution_before = inventory(lease.path)
        return lease
    except BaseException:
        lease.__exit__()
        raise
