"""Serializable M2 test and verification evidence contracts."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class AnalysisCheckResult(BaseModel):
    """C1 API/structural result, with a reader for legacy CheckResult placeholders.

    References are paths relative to the evidence bundle's artifact directory.
    Their existence and binding are checked by the producer, not this DTO.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Status = "NOT_RUN"
    reasons: list[str] = Field(default_factory=list)
    details_ref: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy(cls, value: Any) -> Any:
        if isinstance(value, CheckResult):
            value = value.model_dump(mode='json')
        if not isinstance(value, dict) or 'reason' not in value:
            return value
        normalized = dict(value)
        legacy_reason = normalized.pop('reason')
        if legacy_reason is not None:
            if 'reasons' in normalized:
                raise ValueError('Cannot combine legacy reason with C1 reasons')
            reason = FailureReason.model_validate(legacy_reason)
            normalized['reasons'] = [reason.code]
        return normalized

    @field_validator('reasons')
    @classmethod
    def validate_reason_codes(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(r'[A-Z][A-Z0-9_]*', code) is None for code in values):
            raise ValueError('Analysis reasons must be nonempty uppercase reason codes')
        return values

    @field_validator('details_ref')
    @classmethod
    def validate_details_ref(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.strip() or value != value.strip() or '\\' in value or ':' in value
            or any(ord(char) < 32 for char in value)
            or any(part in ('', '.', '..') for part in value.split('/'))
        ):
            raise ValueError('details_ref must be a normalized relative artifact path')
        return value


class TestGroupResult(BaseModel):
    """Post-patch outcomes for one group of tests, with each test's baseline outcome."""
    model_config = ConfigDict(extra="forbid")

    status: Status = "NOT_RUN"
    cases: list[TestCaseResult] = Field(default_factory=list)
    baseline: dict[str, str] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_applied: bool = False
    tests: TestRunResult
    failing_tests: TestGroupResult = Field(default_factory=TestGroupResult)  # failed at baseline, must pass
    relevant_tests: TestGroupResult = Field(default_factory=TestGroupResult)  # other selected tests (regression)
    typecheck: CheckResult = Field(default_factory=CheckResult)
    lint: CheckResult = Field(default_factory=CheckResult)
    api_check: AnalysisCheckResult = Field(default_factory=AnalysisCheckResult)
    structural_check: AnalysisCheckResult = Field(default_factory=AnalysisCheckResult)
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
    diff: str = ""  # applied unified diff; empty when no patch was applied
    recommendation: Literal["ACCEPT", "REVISE", "REJECT"] = "REJECT"
    artifact_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
