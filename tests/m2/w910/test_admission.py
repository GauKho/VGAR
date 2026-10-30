"""Opt-in SWE-bench admission: pins and private lifecycle, no Docker required."""

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "pydata__xarray-3305"
OVERLAY = {"tests/vgar_w9_repro_issue.py": "def test_issue():\n    assert False\n"}


def git(root, *args):
    return (
        subprocess.check_output(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.hooksPath=",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@local",
                *args,
            ],
            cwd=root,
        )
        .decode()
        .strip()
    )


@pytest.fixture
def admitted_case(tmp_path):
    from vgar.evaluation.harness.task_env import build_profile, canonical_hash
    from vgar.contracts.handoff import payload_digest
    from vgar.repair.contracts import RepairTask

    source = tmp_path / "source"
    (source / "xarray").mkdir(parents=True)
    (source / "tests").mkdir()
    (source / "xarray/core.py").write_bytes(b"def value():\n    return 0\n")
    (source / "tests/test_base.py").write_bytes(b"def test_base():\n    assert True\n")
    (source / ".gitattributes").write_bytes(b"* -text\n")
    git(source, "init", "--template=")
    git(source, "add", "--all")
    git(source, "commit", "--no-verify", "-m", "base")
    commit = git(source, "rev-parse", "HEAD")
    manifest = json.loads(
        (ROOT / "configs/m1/w9_pilot_manifest.json").read_text(encoding="utf-8")
    )
    row = next(r for r in manifest["tasks"] if r["instance_id"] == TASK_ID)
    row["base_commit"] = commit
    row["problem_statement"] = "value should return one"
    row["query_hash"] = (
        "sha256:" + hashlib.sha256(row["problem_statement"].encode()).hexdigest()
    )
    manifest["manifest_hash"] = payload_digest(
        {k: v for k, v in manifest.items() if k != "manifest_hash"}
    )
    files = [
        [p.relative_to(source).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()]
        for p in sorted(source.rglob("*.py"))
    ]
    identity = {
        "head": commit,
        "clean": True,
        "inventory_hash": canonical_hash(files),
        "inventory_count": len(files),
    }
    image = {
        "reference": "swebench/sweb.eval.x86_64.pydata_1776_xarray-3305@sha256:"
        + "a" * 64,
        "image_id": "sha256:" + "b" * 64,
    }
    probe = {
        "protocol": "vgar-pytest-collection-v1",
        "status": "COLLECTED",
        "reason": None,
        "source_before": identity,
        "source_after": identity,
        "runtime": {
            "python": "3.10.15",
            "pytest": "7.4.0",
            "executable": "/opt/miniconda3/envs/testbed/bin/python",
        },
        "collection": {
            "exit_code": 0,
            "node_ids": ["tests/test_base.py::test_base"],
            "errors": [],
        },
    }
    profile = build_profile(
        row, image, ["@pytest-default"], probe, daemon_id="unit-daemon"
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("context.json", "context_manifest.json", "test_links.json"):
        (bundle / name).write_text("{}", encoding="utf-8")
    task = RepairTask(
        task_id=TASK_ID,
        issue_text=row["problem_statement"],
        source_repo=source,
        repo_key=row["repo"],
        revision=commit,
        graph_version="unit-graph",
        bundle_directory=bundle,
        failing_selectors=("tests/vgar_w9_repro_issue.py::test_issue",),
        fallback_scope=("tests/vgar_w9_repro_issue.py",),
        allowed_source_paths=("xarray/core.py",),
    )
    mp, pp = tmp_path / "manifest.json", tmp_path / "profile.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    pp.write_text(json.dumps(profile), encoding="utf-8")
    kwargs = {
        "expected_manifest_hash": manifest["manifest_hash"],
        "expected_profile_hash": profile["profile_hash"],
        "bundle_hashes": {
            n: "sha256:" + hashlib.sha256((bundle / n).read_bytes()).hexdigest()
            for n in ("context.json", "context_manifest.json", "test_links.json")
        },
        "source_roots": ["xarray"],
        "overlay": OVERLAY,
    }
    return task, mp, pp, kwargs


def admit(case):
    from vgar.repair.admission import admit_task

    task, mp, pp, kwargs = case
    return admit_task(task, mp, pp, **kwargs)


def test_admission_pins_exact_tree_profile_bundle_and_independent_overlay(
    admitted_case,
):
    from vgar.repair.admission import validate_admission

    value = admit(admitted_case)
    snapshot = value.snapshot()
    assert snapshot["visibility"] == "issue_reproduction_no_benchmark_oracle"
    assert snapshot["inventory"]["xarray/core.py"].startswith("sha256:")
    assert snapshot["overlay"] == OVERLAY
    assert validate_admission(admitted_case[0], snapshot).snapshot() == snapshot
    assert admitted_case[0].trusted_fixture is False


@pytest.mark.parametrize(
    "fault",
    [
        "manifest_pin",
        "profile_pin",
        "bundle",
        "base",
        "issue",
        "source",
        "untracked",
        "allowed",
        "overlay",
    ],
)
def test_wrong_identity_or_hash_is_rejected_before_execution(admitted_case, fault):
    task, mp, pp, kw = admitted_case
    if fault == "manifest_pin":
        kw["expected_manifest_hash"] = "sha256:" + "0" * 64
    elif fault == "profile_pin":
        kw["expected_profile_hash"] = "sha256:" + "0" * 64
    elif fault == "bundle":
        (task.bundle_directory / "context.json").write_text("changed")
    elif fault == "base":
        task = task.model_copy(update={"revision": "0" * 40})
    elif fault == "issue":
        task = task.model_copy(update={"issue_text": "unapproved issue"})
    elif fault == "source":
        (task.source_repo / "xarray/core.py").write_text("changed")
    elif fault == "untracked":
        (task.source_repo / "untracked.py").write_text("print(1)")
    elif fault == "allowed":
        task = task.model_copy(update={"allowed_source_paths": ("tests/test_base.py",)})
    else:
        kw["overlay"] = {"xarray/core.py": "overwritten"}
    from vgar.repair.admission import admit_task

    with pytest.raises(ValueError):
        admit_task(task, mp, pp, **kw)


def test_excluded_profile_cannot_be_admitted(admitted_case):
    from vgar.evaluation.harness.task_env import canonical_hash

    task, mp, pp, kw = admitted_case
    p = json.loads(pp.read_text())
    p.update(status="EXCLUDED", reason="COLLECTION_FAILED")
    p["collection"]["exit_code"] = 2
    p["collection"]["errors"] = ["collection error"]
    p["profile_hash"] = canonical_hash(
        {k: v for k, v in p.items() if k != "profile_hash"}
    )
    pp.write_text(json.dumps(p))
    kw["expected_profile_hash"] = p["profile_hash"]
    with pytest.raises(ValueError, match="COLLECTED"):
        admit(admitted_case)


def test_source_and_overlay_checked_again_after_admission(admitted_case):
    from vgar.repair.admission import validate_admission

    value = admit(admitted_case)
    (admitted_case[0].source_repo / "xarray/core.py").write_text("drift")
    with pytest.raises(ValueError):
        validate_admission(admitted_case[0], value)


def test_docker_session_requires_admission_and_legacy_cannot_borrow_it(
    admitted_case, tmp_path
):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import start_session

    task = admitted_case[0]
    value = admit(admitted_case)
    with pytest.raises(ValueError):
        start_session(
            task, RepairPolicy(runtime="docker_admitted"), "fake", tmp_path / "bad"
        )
    with pytest.raises(ValueError):
        start_session(task, RepairPolicy(), "fake", tmp_path / "bad2", admission=value)
    session = start_session(
        task,
        RepairPolicy(runtime="docker_admitted"),
        "fake",
        tmp_path / "runs",
        admission=value,
        experiment={
            "variant_policy": {"variant_id": "A0", "required_checks": ["tests"]},
            "arm": "bm25",
        },
    )
    assert (
        session.state["admission"]
        == session.run.record["admission"]
        == value.snapshot()
    )


@pytest.mark.parametrize("fault", ["state", "record", "both", "tamper"])
def test_resume_lost_or_altered_admission_rejected_without_write(
    admitted_case, tmp_path, fault
):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import RepairSession, start_session

    s = start_session(
        admitted_case[0],
        RepairPolicy(runtime="docker_admitted"),
        "fake",
        tmp_path / "runs",
        admission=admit(admitted_case),
        experiment={
            "variant_policy": {"variant_id": "A0", "required_checks": ["tests"]},
            "arm": "bm25",
        },
    )
    sp = s.run.directory / "session.json"
    state, record = json.loads(sp.read_text()), json.loads(s.run.path.read_text())
    if fault in ("state", "both"):
        state.pop("admission")
    if fault in ("record", "both"):
        record.pop("admission")
    if fault == "tamper":
        state["admission"]["expected_profile_hash"] = "sha256:" + "c" * 64
    sp.write_text(json.dumps(state))
    s.run.path.write_text(json.dumps(record))
    before = sp.read_bytes(), s.run.path.read_bytes()
    with pytest.raises(ValueError):
        RepairSession.load(s.run.directory)
    assert before == (sp.read_bytes(), s.run.path.read_bytes())


def test_private_attributes_and_overlay_preserve_original(admitted_case, tmp_path):
    from vgar.repair.admission import prepare_admitted_workspace
    from vgar.repair.workspace import inventory

    task = admitted_case[0]
    before = inventory(task.source_repo)
    lease = prepare_admitted_workspace(task, admit(admitted_case), tmp_path / "private")
    try:
        assert inventory(task.source_repo) == before
        assert (lease.path / ".gitattributes").read_bytes() == b"* -text\n"
        assert (lease.path / "tests/vgar_w9_repro_issue.py").read_text() == OVERLAY[
            "tests/vgar_w9_repro_issue.py"
        ]
        assert lease.execution_before == inventory(lease.path)
        lease.assert_original()
    finally:
        lease.__exit__()


def test_source_drift_can_be_recorded_as_error_and_owned_lease_cleaned(
    admitted_case, tmp_path
):
    from vgar.repair.admission import prepare_admitted_workspace
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import start_session, finish

    task = admitted_case[0]
    admission = admit(admitted_case)
    s = start_session(
        task,
        RepairPolicy(runtime="docker_admitted"),
        "fake",
        tmp_path / "runs",
        admission=admission,
        experiment={
            "variant_policy": {"variant_id": "A0", "required_checks": ["tests"]},
            "arm": "bm25",
        },
    )
    lease = prepare_admitted_workspace(task, admission, tmp_path / "lease")
    s.state["lease"] = {
        "path": str(lease.path),
        "private": str(lease.private),
        "temp_root": str(lease.temp_root),
        "source_repo": str(lease.source_repo),
        "before": lease.before,
        "worktree_id": lease.worktree_id,
        "keep": False,
        "execution_before": lease.execution_before,
    }
    s.state["outcome"] = ["ERROR", "WORKTREE_ERROR"]
    (task.source_repo / "xarray/core.py").write_text("external source drift")
    run = finish(s)
    assert run.record["status"] == "ERROR"
    assert run.record["original_source_unchanged"] is False
    assert not lease.private.exists()


def test_resume_revalidates_source_before_writing(admitted_case, tmp_path):
    from vgar.repair.contracts import RepairPolicy
    from vgar.repair.session import start_session, RepairSession

    task = admitted_case[0]
    s = start_session(
        task,
        RepairPolicy(runtime="docker_admitted"),
        "fake",
        tmp_path / "runs",
        admission=admit(admitted_case),
        experiment={
            "variant_policy": {"variant_id": "A0", "required_checks": ["tests"]},
            "arm": "bm25",
        },
    )
    state_path = s.run.directory / "session.json"
    before = state_path.read_bytes(), s.run.path.read_bytes()
    (task.source_repo / "xarray/core.py").write_text("external drift")
    with pytest.raises(ValueError):
        RepairSession.load(s.run.directory)
    assert before == (state_path.read_bytes(), s.run.path.read_bytes())


def test_git_replacement_tree_cannot_admit_non_python_config_drift(admitted_case):
    task = admitted_case[0]
    original_tree = git(task.source_repo, "rev-parse", "HEAD^{tree}")
    (task.source_repo / ".gitattributes").write_bytes(b"* text\n")
    git(task.source_repo, "add", ".gitattributes")
    replacement_tree = git(task.source_repo, "write-tree")
    git(task.source_repo, "replace", original_tree, replacement_tree)
    assert git(task.source_repo, "rev-parse", "HEAD") == task.revision
    assert (
        task.source_repo / "xarray/core.py"
    ).read_bytes() == b"def value():\n    return 0\n"
    with pytest.raises(ValueError, match="Git blob"):
        admit(admitted_case)


def test_target_identity_ignores_git_replacement_tree(admitted_case):
    from vgar.repair.docker_probe import base_identity

    task = admitted_case[0]
    original_tree = git(task.source_repo, "rev-parse", "HEAD^{tree}")
    (task.source_repo / ".gitattributes").write_bytes(b"* text\n")
    git(task.source_repo, "add", ".gitattributes")
    replacement_tree = git(task.source_repo, "write-tree")
    git(task.source_repo, "replace", original_tree, replacement_tree)
    identity = base_identity(str(task.source_repo))
    assert identity["head"] == task.revision
    assert identity["clean"] is False


def test_w10_manifest_population_is_admitted_by_hash_pin(admitted_case):
    from vgar.contracts.handoff import payload_digest
    from vgar.evaluation.retrieval.pilot_manifest import W10_SELECTION
    from vgar.repair.admission import validate_admission

    task, mp, pp, kwargs = admitted_case
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    manifest["selection_policy"] = W10_SELECTION
    manifest["tasks"] = [dict(r, version="0.12") for r in manifest["tasks"] if r["instance_id"] == TASK_ID]
    manifest["manifest_hash"] = payload_digest({k: v for k, v in manifest.items() if k != "manifest_hash"})
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    kwargs = dict(kwargs, expected_manifest_hash=manifest["manifest_hash"])
    value = admit((task, mp, pp, kwargs))
    assert validate_admission(task, value.snapshot()).snapshot() == value.snapshot()


def test_repo_native_reproduction_layout_is_admitted(admitted_case):
    # sympy bin/test only runs test_*.py inside the package, so its reproduction lives in xarray-like roots.
    task, mp, pp, kw = admitted_case
    overlay = {"xarray/vgar_w9_repro_issue/test_repro.py": "def test_issue():\n    assert False\n"}
    task = task.model_copy(update={"protected_paths": ("tests", "xarray/vgar_w9_repro_issue"),
                                   "failing_selectors": ("xarray/vgar_w9_repro_issue/test_repro.py::test_issue",),
                                   "fallback_scope": ("xarray/vgar_w9_repro_issue/test_repro.py",)})
    from vgar.repair.admission import admit_task

    assert admit_task(task, mp, pp, **dict(kw, overlay=overlay)).snapshot()["overlay"] == overlay


@pytest.mark.parametrize("path", ["xarray/repro_issue/test_repro.py", "xarray/vgar_w9_repro_issue/test_repro.txt"])
def test_overlay_without_reserved_marker_or_python_suffix_is_rejected(admitted_case, path):
    task, mp, pp, kw = admitted_case
    task = task.model_copy(update={"protected_paths": ("tests", "xarray/repro_issue", "xarray/vgar_w9_repro_issue"),
                                   "fallback_scope": ("tests/vgar_w9_repro_issue.py",)})
    from vgar.repair.admission import admit_task

    with pytest.raises(ValueError, match="reproduction test overlays"):
        admit_task(task, mp, pp, **dict(kw, overlay={**OVERLAY, path: "def test_x():\n    pass\n"}))
