"""Serializable M2 test and verification evidence contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .repair import FailureReason, Status


class TestCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Status
    duration_ms: int = Field(ge=0, default=0)
    detail: str | None = None


class TestRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    command: str
    argv: list[str]
    exit_code: int | None
    duration_ms: int = Field(ge=0)
    stdout: str
    stderr: str
    timeout_seconds: float | None = None
    cases: list[TestCaseResult] = Field(default_factory=list)
    case_counts: dict[str, int] = Field(default_factory=dict)
    reason: FailureReason | None = None
    complete: bool = True
    output_truncated: bool = False
    stdout_bytes: int = Field(ge=0, default=0)
    stderr_bytes: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def validate_outcome(self) -> "TestRunResult":
        if self.status == "PASS" and (self.exit_code != 0 or self.reason is not None or not self.complete):
            raise ValueError("PASS requires exit code zero, complete output and no reason")
        if self.status in ("FAIL", "ERROR") and self.reason is None:
            raise ValueError("FAIL/ERROR requires a failure reason")
        if self.status == "NOT_RUN" and self.exit_code is not None:
            raise ValueError("NOT_RUN cannot have an exit code")
        return self


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status = "NOT_RUN"
    reason: FailureReason | None = None


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_applied: bool = False
    tests: TestRunResult
    typecheck: CheckResult = Field(default_factory=CheckResult)
    lint: CheckResult = Field(default_factory=CheckResult)
    api_check: CheckResult = Field(default_factory=CheckResult)
    structural_check: CheckResult = Field(default_factory=CheckResult)
    reasons: list[FailureReason] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    task_id: str | None = None
    source_repo: str
    source_hash_before: str
    source_hash_after: str
    worktree_id: str
    verification: VerificationResult
    artifact_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
