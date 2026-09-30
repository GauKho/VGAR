"""M2 repair boundary types (no patch engine in the W3-W4 milestone)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["PASS", "FAIL", "ERROR", "NOT_RUN"]
FailureCode = Literal[
    "PATCH_PARSE_ERROR", "PATCH_APPLY_FAILED", "WORKTREE_ERROR", "TEST_TIMEOUT",
    "TEST_FAILED", "TYPECHECK_FAILED", "LINT_FAILED", "API_BREAK",
    "STRUCTURAL_VIOLATION", "VERIFICATION_INCOMPLETE", "INTERNAL_ERROR",
]


class FailureReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: FailureCode
    message: str = Field(min_length=1)


class PatchApplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    patch_applied: bool
    worktree_id: str = Field(min_length=1)
    changed_files: list[str] = Field(default_factory=list)
    error: FailureReason | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "PatchApplyResult":
        if self.status == "PASS" and (not self.patch_applied or self.error is not None):
            raise ValueError("PASS requires an applied patch and no error")
        if self.status in ("FAIL", "ERROR") and self.error is None:
            raise ValueError("FAIL/ERROR requires a failure reason")
        if self.status == "NOT_RUN" and self.patch_applied:
            raise ValueError("NOT_RUN cannot have an applied patch")
        return self
