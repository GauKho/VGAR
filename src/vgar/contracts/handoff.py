"""Portable M1 sidecars and consumer checks; no graph/MCP/model imports.

The manifest declares a Python source scope, not a whole-repository attestation.
Expected snapshot identity comes from the consumer's approved task configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from vgar.contracts.context import ContextPayload, SourceRange
from vgar.contracts.prompt_context import CONTEXT_FORMAT


def payload_digest(value: dict) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return byte_digest(data.encode('utf-8'))


def byte_digest(data: bytes) -> str:
    return 'sha256:' + hashlib.sha256(data).hexdigest()


class _Sidecar(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class SourceScope(_Sidecar):
    pattern: Literal['*.py'] = '*.py'
    excluded_directories: list[str]
    follow_links: Literal[False] = False


class ItemBinding(_Sidecar):
    path: str
    symbol: str
    range: SourceRange
    start_byte: int = Field(ge=0)
    end_byte: int = Field(ge=0)
    snippet_sha256: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')


class ContextManifest(_Sidecar):
    format: Literal['vgar.m1-handoff.v1'] = 'vgar.m1-handoff.v1'
    context_format: Literal['vgar.context.v1'] = CONTEXT_FORMAT
    context_origin: Literal['m1-retrieval'] = 'm1-retrieval'
    graph_version: str = Field(min_length=1)
    repo_key: str = Field(min_length=1)
    repository_revision: str = Field(min_length=1)
    context_sha256: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    source_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    files: dict[str, str]
    source_scope: SourceScope
    items: dict[str, ItemBinding]
    range_encoding: Literal['utf-8-bytes'] = 'utf-8-bytes'
    line_base: Literal[1] = 1
    end_exclusive: Literal[True] = True
    snippet_policy: Literal['whole-range-no-wrapper'] = 'whole-range-no-wrapper'
    counter_label: str = Field(min_length=1)
    token_budget_unit: Literal['snippets-only'] = 'snippets-only'


class TestHints(_Sidecar):
    format: Literal['vgar.test-links.v1'] = 'vgar.test-links.v1'
    graph_version: str
    repo_key: str
    repository_revision: str
    source_digest: str
    test_links: dict[str, list[str]]
    link_details: dict[str, dict]
    failing_selectors: list[str]
    fallback_scope: list[str]
    coverage_verified: Literal[False] = False
    collection_verified: Literal[False] = False


def _relative(value: str) -> str:
    if not isinstance(value, str) or not value or any(c in value for c in ('\\', ':', '\n', '\r', '\0')):
        raise ValueError('Source paths must be repository-relative POSIX paths')
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or '..' in path.parts or path.as_posix() != value or value == '.':
        raise ValueError('Source paths must be normalized and stay inside the repository')
    return value


def _linked(path: Path) -> bool:
    attributes = getattr(path.lstat(), 'st_file_attributes', 0)
    return path.is_symlink() or bool(attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _source_path(root: Path, relative: str) -> Path:
    path = root
    for part in PurePosixPath(_relative(relative)).parts:
        path = path / part
        if not path.exists() or _linked(path):
            raise ValueError(f'Source path is missing or uses a filesystem link: {relative}')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Source path escapes the repository')
    return path


def read_source_inventory(root: Path, scope: SourceScope) -> dict[str, bytes]:
    if not root.is_dir():
        raise ValueError('Source repository must be an existing directory')
    if any(not name or '/' in name or '\\' in name or name in {'.', '..'} for name in scope.excluded_directories):
        raise ValueError('Excluded directories must be directory names')
    result = {}
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in scope.excluded_directories
                          and not _linked(Path(directory) / name))
        for name in sorted(files):
            path = Path(directory) / name
            if name.endswith('.py') and not _linked(path):
                relative = path.relative_to(root).as_posix()
                result[_relative(relative)] = path.read_bytes()
    return result


def _verified_sources(root: Path, manifest: ContextManifest) -> dict[str, bytes]:
    actual = read_source_inventory(root, manifest.source_scope)
    hashes = {path: byte_digest(data) for path, data in actual.items()}
    if hashes != manifest.files or payload_digest(hashes) != manifest.source_digest:
        raise ValueError('Source inventory/hash differs from the declared snapshot')
    return actual


def _position(data: bytes, offset: int) -> tuple[int, int]:
    if not 0 <= offset <= len(data):
        raise ValueError('Source byte range is out of bounds')
    prefix = data[:offset]
    prefix.decode('utf-8')  # Reject a column inside a multibyte character.
    return prefix.count(b'\n') + 1, len(prefix.rsplit(b'\n', 1)[-1])


def validate_context_handoff(payload: ContextPayload | dict, manifest: ContextManifest | dict,
                             source_repo: str | Path, *, expected_graph_version: str,
                             expected_repo_key: str, expected_revision: str,
                             count_tokens: Callable[[str], int], counter_label: str) -> ContextPayload:
    """Validate a cloned snapshot before prompt assembly; return the frozen DTO.

    Token counts cover snippets only. M2 must separately count its whole prompt.
    A transport hash detects corruption; it is not a digital signature.
    """
    context = ContextPayload.model_validate(payload.model_dump() if isinstance(payload, ContextPayload) else payload)
    sidecar = ContextManifest.model_validate(manifest.model_dump() if isinstance(manifest, ContextManifest) else manifest)
    if (sidecar.graph_version, sidecar.repo_key, sidecar.repository_revision) != (
            expected_graph_version, expected_repo_key, expected_revision) or context.graph_version != sidecar.graph_version:
        raise ValueError('Context identity differs from the approved target snapshot')
    if not callable(count_tokens) or not counter_label or counter_label != sidecar.counter_label:
        raise ValueError('Use the same explicit snippet token counter as the producer')
    if not context.items or any(not item.snippet.strip() for item in context.items):
        raise ValueError('Repair context must contain usable source snippets')
    if payload_digest(context.model_dump(mode='json')) != sidecar.context_sha256:
        raise ValueError('Context transport hash mismatch')
    ids = [item.node_id for item in context.items]
    if len(set(ids)) != len(ids) or set(ids) != set(sidecar.items):
        raise ValueError('Context nodes differ from the manifest bindings')
    root = Path(source_repo).resolve()
    sources = _verified_sources(root, sidecar)
    for item in context.items:
        binding = sidecar.items[item.node_id]
        if (item.path, item.symbol, item.range) != (binding.path, binding.symbol, binding.range):
            raise ValueError('Context path/symbol/range differs from its node binding')
        if item.path not in sources or binding.end_byte < binding.start_byte:
            raise ValueError('Context source/range is not part of the declared inventory')
        data = sources[item.path]
        bounds = item.range
        if (_position(data, binding.start_byte), _position(data, binding.end_byte)) != (
                (bounds.start_line, bounds.start_col), (bounds.end_line, bounds.end_col)):
            raise ValueError('Byte range differs from source line/column coordinates')
        snippet = data[binding.start_byte:binding.end_byte]
        if byte_digest(snippet) != binding.snippet_sha256 or snippet.decode('utf-8') != item.snippet:
            raise ValueError('Context snippet differs from the exact source slice')
        tokens = count_tokens(item.snippet)
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0 or tokens != item.token_count:
            raise ValueError('Context snippet token accounting mismatch')
    _verified_sources(root, sidecar)  # Detect edits/additions during counter callbacks.
    return context


def adapt_test_hints(hints: TestHints | dict, manifest: ContextManifest | dict,
                     source_repo: str | Path) -> dict:
    """Return M2's tuple mapping/explicit/fallback inputs; never run pytest.

    Paths are checked, but pytest collection and verification belong to M2.
    Empty links preserve all provided fallback selectors.
    """
    data = TestHints.model_validate(hints.model_dump() if isinstance(hints, TestHints) else hints)
    sidecar = ContextManifest.model_validate(manifest.model_dump() if isinstance(manifest, ContextManifest) else manifest)
    identity = ('graph_version', 'repo_key', 'repository_revision', 'source_digest')
    if any(getattr(data, field) != getattr(sidecar, field) for field in identity):
        raise ValueError('Test links and context belong to different snapshots')
    root = Path(source_repo).resolve()
    _verified_sources(root, sidecar)

    def selector(value: str, *, allow_directory: bool = False) -> str:
        if not value or value.startswith('-') or any(c in value for c in ('\n', '\r', '\0')):
            raise ValueError('Invalid pytest selector')
        parts = value.split('::')
        path = _source_path(root, parts[0])
        if any(not name or name.startswith('-') for name in parts[1:]):
            raise ValueError('Invalid pytest node selector')
        if path.is_dir():
            if not allow_directory or len(parts) > 1 or not any(p.startswith(parts[0] + '/') for p in sidecar.files):
                raise ValueError('Fallback directory contains no declared Python sources')
        elif not path.is_file() or parts[0] not in sidecar.files:
            raise ValueError('Test selector file is outside the declared source scope')
        return value

    links = {}
    if set(data.link_details) != set(data.test_links):
        raise ValueError('Test links must carry selection details for each target')
    for target, values in data.test_links.items():
        if target not in sidecar.files and target not in sidecar.items:
            raise ValueError('Test-link target is outside the context/source scope')
        links[target] = tuple(sorted({selector(value) for value in values}))
    return {'test_links': links,
            'failing_selectors': tuple(sorted({selector(value) for value in data.failing_selectors})),
            'fallback_scope': tuple(sorted({selector(value, allow_directory=True) for value in data.fallback_scope}))}
