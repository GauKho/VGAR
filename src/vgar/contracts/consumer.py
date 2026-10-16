"""Receive an M1 handoff using independently approved task identity.

This adapter validates and renders inputs. Model calls, patch application and
pytest collection belong to M2. No graph builder or model runtime is imported.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vgar.contracts.handoff import (ContextManifest, TestHints, _relative,
                                    adapt_test_hints, validate_context_handoff)
from vgar.contracts.prompt_context import render_context_for_repair


class HandoffTarget(BaseModel):
    """Private consumer configuration; populated from M2's approved task."""

    model_config = ConfigDict(extra='forbid', strict=True)
    task_id: str = Field(min_length=1)
    repo_key: str = Field(min_length=1)
    repository_revision: str = Field(min_length=1)
    graph_version: str = Field(min_length=1)

    @field_validator('task_id', 'repo_key', 'repository_revision', 'graph_version')
    @classmethod
    def nonblank_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Task identity must not be blank')
        return value


def _changed_path_report(inputs: dict, manifest: ContextManifest, changed_paths: list[str]) -> dict:
    if not isinstance(changed_paths, list):
        raise ValueError('Changed paths must be a list of repository-relative POSIX paths')
    paths = tuple(sorted({_relative(path) for path in changed_paths}))
    links = inputs['test_links']
    details = inputs['diagnostics']['link_details']
    targets, graph_selectors = {}, set()
    for path in paths:
        symbols = {node_id for node_id, binding in manifest.items.items() if binding.path == path}
        matched = sorted(({path} | symbols) & links.keys())
        selectors = tuple(sorted({value for key in matched for value in links[key]}))
        if path not in manifest.files:
            status = 'outside_source_scope'
        elif path in links:
            status = 'linked' if links[path] else 'unlinked'
        else:
            # Packed symbol hints cannot establish coverage of a whole changed file.
            status = 'partial_mapping' if matched else 'missing_mapping'
        truncated = any(details[key]['truncated'] for key in matched)
        limited = any(details[key]['traversal_limited'] for key in matched)
        reasons = ([status] if status != 'linked' else [])
        if truncated:
            reasons.append('links_truncated')
        if limited:
            reasons.append('traversal_limited')
        targets[path] = {
            'mapping_status': status, 'matched_targets': tuple(matched), 'selectors': selectors,
            'truncated': truncated, 'traversal_limited': limited, 'fallback_reasons': tuple(reasons),
        }
        graph_selectors.update(selectors)
    required = any(target['fallback_reasons'] for target in targets.values())
    available = bool(inputs['failing_selectors'] or inputs['fallback_scope'])
    return {
        'changed_paths': paths, 'targets': targets, 'graph_selectors': tuple(sorted(graph_selectors)),
        'candidate_tests': tuple(sorted(graph_selectors | set(inputs['failing_selectors']))),
        'failing_selectors': inputs['failing_selectors'], 'fallback_scope': inputs['fallback_scope'],
        'fallback_required': required, 'fallback_available': available,
        'requires_fallback_input': required and not available,
        'coverage_verified': False, 'collection_verified': False,
    }


def diagnose_changed_paths(hints: TestHints | dict, manifest: ContextManifest | dict,
                           source_repo: str | Path, changed_paths: list[str]) -> dict:
    """Check actual diff paths against hints bound to the original source snapshot.

    New/deleted/non-Python paths can be reported without reading patched files.
    Candidate selectors and fallback scope are inputs to M2, not a test run plan
    or proof of coverage. M2 collects and chooses tests on its patched worktree.
    """
    inputs = adapt_test_hints(hints, manifest, source_repo)
    sidecar = ContextManifest.model_validate(manifest.model_dump() if isinstance(manifest, ContextManifest) else manifest)
    return _changed_path_report(inputs, sidecar, changed_paths)


def receive_context_handoff(bundle_directory: str | Path, source_repo: str | Path,
                            target: HandoffTarget | dict, *,
                            count_tokens: Callable[[str], int], counter_label: str,
                            changed_paths: list[str] | None = None) -> dict:
    """Read exported files, validate against the original snapshot, then render.

    The producer's repair-context.txt is deliberately not trusted as input.
    When supplied, actual diff paths are checked for missing/partial mappings.
    M2 collects selectors on its patched worktree, keeping this snapshot intact.
    """
    approved = HandoffTarget.model_validate(target.model_dump() if isinstance(target, HandoffTarget) else target)
    bundle = Path(bundle_directory)
    payload, manifest, hints = (json.loads((bundle / name).read_text(encoding='utf-8'))
                                for name in ('context.json', 'context_manifest.json', 'test_links.json'))
    context = validate_context_handoff(payload, manifest, source_repo,
        expected_graph_version=approved.graph_version, expected_repo_key=approved.repo_key,
        expected_revision=approved.repository_revision, count_tokens=count_tokens, counter_label=counter_label)
    test_inputs = adapt_test_hints(hints, manifest, source_repo)
    received = {
        'context': context.model_dump(mode='json'),
        'context_text': render_context_for_repair(context),
        'test_inputs': test_inputs,
        'metadata': {
            **approved.model_dump(), 'source_digest': manifest['source_digest'],
            'counter_label': counter_label, 'context_items': len(context.items),
            'snippet_tokens': context.total_token_count, 'snippet_budget': context.token_budget,
            'context_truncated': context.truncated, 'token_budget_unit': 'snippets-only',
            'coverage_verified': False, 'collection_verified': False,
        },
    }
    if changed_paths is not None:
        received['test_target_report'] = _changed_path_report(
            test_inputs, ContextManifest.model_validate(manifest), changed_paths)
    return received
