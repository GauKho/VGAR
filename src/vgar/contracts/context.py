from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_line: int = Field(ge=1)
    start_col: int = Field(ge=0)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> SourceRange:
        if (self.end_line, self.end_col) < (self.start_line, self.start_col):
            raise ValueError("range end must not precede range start")
        return self


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    range: SourceRange
    snippet: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    graph_distance: int = Field(ge=0)
    graph_rationale: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    token_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_repository_relative_path(self) -> ContextItem:
        normalized = self.path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            path.is_absolute()
            or PureWindowsPath(normalized).drive
            or ".." in path.parts
            or normalized != self.path
        ):
            raise ValueError("path must be a normalized repository-relative POSIX path")
        return self


class ContextPayload(BaseModel):
    """Validated context bundle passed from retrieval to prompt assembly."""

    model_config = ConfigDict(extra="forbid")

    graph_version: str = Field(min_length=1)
    anchor_ids: list[str]
    items: list[ContextItem]
    total_token_count: int = Field(ge=0)
    token_budget: int = Field(gt=0)
    truncated: bool = False

    @model_validator(mode="after")
    def validate_budget_accounting(self) -> ContextPayload:
        calculated = sum(item.token_count for item in self.items)
        if self.total_token_count != calculated:
            raise ValueError(
                "total_token_count must equal the sum of item token_count values"
            )
        if self.total_token_count > self.token_budget:
            raise ValueError("total_token_count must not exceed token_budget")
        return self
