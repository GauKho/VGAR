from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.repair.baseline import run_baseline
from vgar.repair.workspace import fingerprint_source

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "m2"


def test_clean_baseline_is_pass_and_source_unchanged(tmp_path: Path) -> None:
    source = FIXTURES / "clean_repo"
    before = fingerprint_source(source)
    bundle = run_baseline(source, ("tests/test_demo.py",), tmp_path / "records", "clean",
                          temp_root=tmp_path / "workspaces")
    assert bundle.verification.tests.status == "PASS"
    assert bundle.verification.patch_applied is False
    assert bundle.source_hash_before == bundle.source_hash_after == before
    assert all(check.status == "NOT_RUN" for check in (
        bundle.verification.typecheck, bundle.verification.lint,
        bundle.verification.api_check, bundle.verification.structural_check))
    record = json.loads(Path(bundle.artifact_path).read_text(encoding="utf-8"))
    assert record["complete"] is True
    assert record["evidence_bundle"]["run_id"] == bundle.run_id


def test_failing_baseline_is_fail_not_patch_failure(tmp_path: Path) -> None:
    source = FIXTURES / "failing_repo"
    bundle = run_baseline(source, ("tests/test_demo.py",), tmp_path / "records", "failing",
                          temp_root=tmp_path / "workspaces")
    assert bundle.verification.tests.status == "FAIL"
    assert bundle.verification.tests.reason.code == "TEST_FAILED"
    assert bundle.verification.patch_applied is False
    assert bundle.source_hash_before == bundle.source_hash_after


def test_timeout_is_recorded_and_workspace_cleaned(tmp_path: Path) -> None:
    source = tmp_path / "slow"
    (source / "tests").mkdir(parents=True)
    (source / "tests" / "test_slow.py").write_text("import time\ndef test_slow():\n    time.sleep(30)\n", encoding="utf-8")
    workspace_root = tmp_path / "workspaces"
    bundle = run_baseline(source, ("tests/test_slow.py",), tmp_path / "records", "slow",
                          temp_root=workspace_root, timeout_seconds=0.5)
    assert bundle.verification.tests.status == "ERROR"
    assert bundle.verification.tests.reason.code == "TEST_TIMEOUT"
    assert not list(workspace_root.glob("vgar-m2-*"))


def test_writer_failure_leaves_pending_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import vgar.repair.baseline as baseline

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(baseline, "finish_run", fail)
    with pytest.raises(OSError, match="simulated"):
        run_baseline(FIXTURES / "clean_repo", ("tests/test_demo.py",), tmp_path / "records", "disk",
                     temp_root=tmp_path / "workspaces")
    records = list((tmp_path / "records").glob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text(encoding="utf-8"))["complete"] is False
