"""Internal M2 repair configuration; public result DTOs stay in vgar.contracts."""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def safe_path(value: str) -> str:
    if not isinstance(value, str) or not value or any(c in value for c in ('\\', ':', '\0', '\r', '\n')):
        raise ValueError('Expected a normalized repository-relative POSIX path')
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or '..' in path.parts or path.as_posix() != value:
        raise ValueError('Path escapes repository or is not normalized')
    if value == '.' or '.git' in path.parts or value.startswith('-'):
        raise ValueError('Protected or option-like path')
    return value


def safe_selector(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Selector must be a string')
    parts = value.split('::')
    safe_path(parts[0])
    if any(not p or p.startswith('-') or any(c in p for c in ('\0', '\n', '\r', '\\', '/')) for p in parts[1:]):
        raise ValueError('Invalid pytest node selector')
    return value


class RepairTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: str = Field(min_length=1)
    issue_text: str = Field(min_length=1)
    source_repo: Path
    repo_key: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    graph_version: str = Field(min_length=1)
    bundle_directory: Path
    failing_selectors: tuple[str, ...]
    fallback_scope: tuple[str, ...]
    allowed_source_paths: tuple[str, ...]
    protected_paths: tuple[str, ...] = ('tests', 'pytest.ini')
    trusted_fixture: bool = False

    @field_validator('task_id', 'issue_text', 'repo_key', 'revision', 'graph_version')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Task identity and issue must not be blank')
        return value

    @field_validator('failing_selectors', 'fallback_scope')
    @classmethod
    def selectors(cls, values):
        return tuple(sorted({safe_selector(v) for v in values}))

    @field_validator('allowed_source_paths', 'protected_paths')
    @classmethod
    def paths(cls, values):
        return tuple(sorted({safe_path(v) for v in values}))


class RepairPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    prompt_version: str = Field(default='m2-w78-v11', pattern=r'^m2-w78-v[1-9][0-9]*$')
    input_cap: int = Field(default=6000, gt=0)
    output_cap: int = Field(default=1536, gt=0)
    reserved_margin: int = Field(default=256, ge=0)
    generation_timeout: float = Field(default=900.0, gt=0)
    command_timeout: float = Field(default=120.0, gt=0)
    global_timeout: float = Field(default=1800.0, gt=0)
    max_output_bytes: int = Field(default=8 * 1024 * 1024, gt=0)
    max_diff_bytes: int = Field(default=256 * 1024, gt=0)
    max_files: int = Field(default=5, gt=0)
    max_changed_lines: int = Field(default=500, gt=0)
    runtime: Literal['native_trusted_fixtures', 'docker_admitted'] = 'native_trusted_fixtures'


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model_id: Literal['Qwen/Qwen3-4B-Instruct-2507'] = 'Qwen/Qwen3-4B-Instruct-2507'
    revision: Literal['cdbee75f17c01a7cc42f958dc650907174af0554'] = 'cdbee75f17c01a7cc42f958dc650907174af0554'
    snapshot: Path
    interpreter: Path
    tokenizer_manifest: Path
    approved_prototype: bool = False
    do_sample: Literal[False] = False
    dtype: Literal['float16'] = 'float16'
    device_map: Literal['auto'] = 'auto'

