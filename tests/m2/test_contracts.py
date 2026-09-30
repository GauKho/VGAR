from __future__ import annotations

import pytest
from pydantic import ValidationError

from vgar.contracts.evidence import CheckResult, EvidenceBundle, TestRunResult as M2TestRunResult, VerificationResult
from vgar.contracts.repair import FailureReason, PatchApplyResult


def test_patch_apply_contract_roundtrip() -> None:
    result = PatchApplyResult(status="PASS", patch_applied=True, worktree_id="wt-1", changed_files=["auth/token.py"])
    assert PatchApplyResult.model_validate_json(result.model_dump_json()) == result
    assert "schema_version" not in result.model_dump()


def test_failed_patch_requires_reason() -> None:
    with pytest.raises(ValidationError):
        PatchApplyResult(status="FAIL", patch_applied=False, worktree_id="wt-1")
    result = PatchApplyResult(
        status="FAIL", patch_applied=False, worktree_id="wt-1",
        error=FailureReason(code="PATCH_APPLY_FAILED", message="hunk rejected"),
    )
    assert result.error.code == "PATCH_APPLY_FAILED"


def test_baseline_bundle_never_claims_unrun_checks() -> None:
    tests = M2TestRunResult(status="PASS", command="python -m pytest", argv=["python", "-m", "pytest"],
                          exit_code=0, duration_ms=12, stdout="ok", stderr="")
    verification = VerificationResult(patch_applied=False, tests=tests)
    assert all(check.status == "NOT_RUN" for check in (
        verification.typecheck, verification.lint, verification.api_check, verification.structural_check
    ))
    bundle = EvidenceBundle(run_id="r1", task_id="fixture", source_repo="D:/fixture",
                            source_hash_before="a", source_hash_after="a", worktree_id="wt-1",
                            verification=verification)
    assert EvidenceBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert "schema_version" not in bundle.model_dump()


def test_invalid_success_exit_code_rejected() -> None:
    with pytest.raises(ValidationError):
        M2TestRunResult(status="PASS", command="pytest", argv=["pytest"], exit_code=1,
                      duration_ms=1, stdout="", stderr="")


def test_check_default_is_not_run() -> None:
    assert CheckResult().status == "NOT_RUN"
