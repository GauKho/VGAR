"""Explicit arm/hash binding never changes the shared producer DTO."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_arm_and_hash_optin_works_without_changing_legacy_metadata(w9_case):
    from vgar.repair.context_adapter import load_handoff
    task, count, _ = w9_case
    legacy = load_handoff(task, count, count.counter_label)
    assert 'arm' not in legacy.metadata
    for arm in ('bm25', 'graph'):
        value = load_handoff(task, count, count.counter_label, arm=arm, expected_hashes=legacy.hashes)
        assert value.metadata['arm'] == arm
        assert value.context == legacy.context and value.hashes == legacy.hashes


@pytest.mark.parametrize('arm', ['', 'A0', 'GRAPH', 1, False])
def test_invalid_arm_is_rejected(w9_case, arm):
    from vgar.repair.context_adapter import load_handoff
    task, count, _ = w9_case
    with pytest.raises(ValueError):
        load_handoff(task, count, count.counter_label, arm=arm)


@pytest.mark.parametrize('kind', ['missing', 'extra', 'mismatch', 'bad_digest'])
def test_expected_hashes_require_complete_exact_binding(w9_case, kind):
    from vgar.repair.context_adapter import load_handoff
    task, count, _ = w9_case
    hashes = load_handoff(task, count, count.counter_label).hashes.copy()
    if kind == 'missing':
        hashes.pop('test_links.json')
    elif kind == 'extra':
        hashes['repair-context.txt'] = 'sha256:'+'a'*64
    else:
        hashes['context.json'] = 'wrong' if kind == 'bad_digest' else 'sha256:'+'a'*64
    with pytest.raises(ValueError):
        load_handoff(task, count, count.counter_label, arm='graph', expected_hashes=hashes)


def test_real_w9_bundle_arm_label_does_not_claim_algorithm_or_collection():
    from vgar.repair.config import load_task
    from vgar.repair.context_adapter import load_handoff
    task = load_task(ROOT/'tests/fixtures/w9_bundle/task.json')
    value = load_handoff(task, len, 'fixture-only:characters', arm='bm25')
    assert value.metadata['arm'] == 'bm25'
    assert value.metadata['collection_verified'] is False
    assert 'arm' not in json.loads((task.bundle_directory/'context.json').read_text(encoding='utf-8'))
