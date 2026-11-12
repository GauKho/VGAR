"""Manifest no-gold boundary and sequential export controller."""
import copy

import pytest


def test_projection_ignores_gold_and_oracle():
    from vgar.evaluation.retrieval.pilot_manifest import project_retrieval_task
    row = {'instance_id': 'astropy__astropy-13398', 'repo': 'astropy/astropy',
           'base_commit': 'a'*40, 'problem_statement': 'normalize broken',
           'patch': 'GOLD', 'FAIL_TO_PASS': ['SECRET'], 'changed_source_files': ['answer.py']}
    projected = project_retrieval_task(row)
    other = copy.deepcopy(row)
    other.update(patch='DIFFERENT GOLD', FAIL_TO_PASS=['OTHER'], changed_source_files=['gold.py'])
    assert project_retrieval_task(other) == projected
    assert set(projected) == {'instance_id', 'repo', 'base_commit', 'problem_statement', 'query_hash', 'split'}


def test_manifest_is_pinned_and_hash_bound():
    from vgar.evaluation.retrieval.pilot_manifest import (
        PILOT_IDS,
        make_manifest,
        validate_manifest,
    )
    tasks = [{'instance_id': i, 'repo': 'fixture/project', 'base_commit': 'a'*40,
              'problem_statement': 'normalize'} for i in PILOT_IDS]
    manifest = make_manifest(tasks, parquet_hash='sha256:'+'a'*64)
    validate_manifest(manifest)
    bad = copy.deepcopy(manifest)
    bad['tasks'][0]['base_commit'] = 'b'*40
    with pytest.raises(ValueError):
        validate_manifest(bad)
    bad = copy.deepcopy(manifest)
    bad['tasks'] = bad['tasks'][:-1]
    with pytest.raises(ValueError):
        validate_manifest(bad)


def test_tokenizer_identity_must_match_approved_model(tmp_path):
    import json
    from pathlib import Path

    from vgar.evaluation.retrieval.pilot_manifest import require_tokenizer_identity
    approved = Path(__file__).resolve().parents[1]/'artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json'
    value = json.loads(approved.read_text(encoding='utf-8'))
    relocated = tmp_path/'manifest.json'
    value['assets_directory'] = '/different/cache/location'
    relocated.write_text(json.dumps(value), encoding='utf-8')
    require_tokenizer_identity(relocated, approved)
    value['model_id'] = 'other/valid-model'
    relocated.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError):
        require_tokenizer_identity(relocated, approved)
