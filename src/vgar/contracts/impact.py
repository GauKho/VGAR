"""W9 impact interchange contract. No graph traversal, patch apply or model imports."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Hash = Annotated[str, Field(pattern=r'^sha256:[0-9a-f]{64}$')]
Text = Annotated[str, Field(min_length=1, pattern=r'\S')]


def canonical_hash(value: dict) -> str:
    """Hash canonical JSON (not raw file bytes). Nonfinite numbers are rejected."""
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


class _Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ImpactRange(_Contract):
    """Baseline range: one-based lines, zero-based UTF-8 columns, exclusive end."""
    start_line: int = Field(ge=1)
    start_col: int = Field(ge=0)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=0)

    @model_validator(mode='after')
    def ordered(self) -> ImpactRange:
        if (self.end_line, self.end_col) <= (self.start_line, self.start_col):
            raise ValueError('Baseline symbol range must be nonempty and ordered')
        return self


class ChangeSpan(_Contract):
    """Changed block within a hunk; context-only lines excluded by the producer."""
    hunk_index: int = Field(ge=1)
    old_start: int = Field(ge=0)
    old_count: int = Field(ge=0)
    new_start: int = Field(ge=0)
    new_count: int = Field(ge=0)

    @model_validator(mode='after')
    def valid_coordinates(self) -> ChangeSpan:
        if not self.old_count and not self.new_count:
            raise ValueError('Change span must change at least one line')
        if (self.old_count and self.old_start == 0) or (self.new_count and self.new_start == 0):
            raise ValueError('Nonempty side needs a one-based start')
        return self


class _Located(_Contract):
    path: Text

    @field_validator('path')
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (any(c in value for c in ('\\', ':', '\0', '\r', '\n'))
                or path.is_absolute() or '..' in path.parts or '.git' in path.parts
                or path.as_posix() != value or value == '.' or value.startswith('-')):
            raise ValueError('Expected normalized repository-relative POSIX source path')
        return value


class ChangedNode(_Located):
    node_id: Text
    kind: Literal['Function', 'Method', 'Class']
    source_range: ImpactRange
    basis: Literal['baseline_changed_lines', 'insertion_in_existing_scope']
    spans: list[ChangeSpan] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_spans(self) -> ChangedNode:
        keys = [tuple(span.model_dump().values()) for span in self.spans]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate supporting span')
        return self


class UnmappedChange(_Located):
    span: ChangeSpan
    reason: Literal['NO_BASELINE_SYMBOL_AT_INSERTION', 'MODULE_LEVEL_CHANGE',
                    'NO_MATCHING_BASELINE_SYMBOL', 'AMBIGUOUS_BASELINE_SYMBOL',
                    'UNSUPPORTED_SOURCE', 'MAPPING_LIMIT']


class ImpactedNodes(_Contract):
    status: Literal['NOT_COMPUTED'] = 'NOT_COMPUTED'
    items: list[Text] = Field(default_factory=list, max_length=0)


class UnavailableRiskFeature(_Contract):
    name: Text
    available: Literal[False] = False
    value: None = None
    reason: Literal['NOT_COMPUTED'] = 'NOT_COMPUTED'

    @field_validator('available', mode='before')
    @classmethod
    def boolean_only(cls, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError('Availability must be a boolean')
        return value


class RiskReport(_Contract):
    status: Literal['NOT_COMPUTED'] = 'NOT_COMPUTED'
    features: list[UnavailableRiskFeature] = Field(default_factory=list)


class MappingLimits(_Contract):
    scope: Literal['baseline-symbol-mapping'] = 'baseline-symbol-mapping'
    status: Literal['COMPLETE', 'PARTIAL'] = 'COMPLETE'
    truncated: bool = False
    reasons: list[Text] = Field(default_factory=list)
    max_diff_bytes: int = Field(default=256 * 1024, gt=0)
    max_files: int = Field(default=5, gt=0)
    max_changed_lines: int = Field(default=500, gt=0)
    unsupported_operations: list[Literal['add_file', 'delete_file', 'rename_file']] = Field(
        default_factory=lambda: ['add_file', 'delete_file', 'rename_file'])

    @model_validator(mode='after')
    def honest_completion(self) -> MappingLimits:
        if self.status == 'COMPLETE' and (self.truncated or self.reasons):
            raise ValueError('Complete mapping cannot carry truncation or limit reasons')
        if self.status == 'PARTIAL' and not self.reasons:
            raise ValueError('Partial mapping needs explicit limit reasons')
        return self


class ImpactReport(_Contract):
    repo_key: Text
    repository_revision: Text
    graph_version: Text
    graph_hash: Hash
    source_hash: Hash
    patch_hash: Hash
    source_scope: Literal['python-inventory'] = 'python-inventory'
    changed: list[ChangedNode]
    unmapped: list[UnmappedChange]
    impacted: ImpactedNodes = Field(default_factory=ImpactedNodes)
    risk: RiskReport = Field(default_factory=RiskReport)
    limits: MappingLimits = Field(default_factory=MappingLimits)

    @model_validator(mode='after')
    def unique_entries(self) -> ImpactReport:
        ids = [node.node_id for node in self.changed]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate node ID; combine supporting spans into one entry')
        unmapped = [canonical_hash(item.model_dump()) for item in self.unmapped]
        if len(unmapped) != len(set(unmapped)):
            raise ValueError('Duplicate unmapped entry')
        return self

    def canonical_json(self) -> str:
        """Stable collection ordering without mutating the report or its lists."""
        data = self.model_dump(mode='json')
        for node in data['changed']:
            node['spans'].sort(key=lambda span: tuple(span.values()))
        data['changed'].sort(key=lambda node: (node['path'], node['node_id']))
        data['unmapped'].sort(key=lambda item: json.dumps(item, sort_keys=True))
        data['risk']['features'].sort(key=lambda item: item['name'])
        data['limits']['reasons'].sort()
        data['limits']['unsupported_operations'].sort()
        return json.dumps(data, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
