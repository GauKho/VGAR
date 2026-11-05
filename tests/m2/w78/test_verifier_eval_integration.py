"""Verify-once uses the real lease/executor/pytest and no generation path."""
import copy
import json
import shutil

import pytest

from vgar.evaluation.repair.verifier_eval import derive_verdict, verify_once
from vgar.repair.contracts import RepairPolicy
from vgar.repair.policy import load_variant
from vgar.repair.workspace import inventory
from w78_support import REPO

FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
SKIP = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    raise __import__("unittest").SkipTest("synthetic mutant")\n'


@pytest.mark.parametrize('patch,want', [(FIX, 'PASS'), (SKIP, 'ERROR')])
def test_full_vector_real_fixture_without_generator(m1_case, tmp_path, patch, want):
    task, _ = m1_case
    before = inventory(task.source_repo)
    out = tmp_path / 'verified'
    vector = verify_once(task, patch, RepairPolicy(), out, temp_root=tmp_path / 'temp')
    assert json.loads((out / 'vector.json').read_bytes()) == vector
    assert vector['integrity']['status'] == 'PASS'
    assert 'variant_policy_hash' not in vector['baseline']['static']
    assert 'variant_policy_hash' not in vector['post']['static']
    assert vector['post']['compatibility']['api']['status'] == 'PASS'
    assert vector['post']['compatibility']['structural']['status'] == 'PASS'
    assert inventory(task.source_repo) == before
    for name in ('A0', 'A1', 'A2', 'A3'):
        path = REPO / 'configs/m2/variants' / ('A3.json' if name == 'A3' else f'w10/{name}.json')
        result = derive_verdict(vector, load_variant(path))
        assert result['status'] == want
        if want == 'ERROR':
            assert 'VERIFICATION_INCOMPLETE' in result['reasons']


def test_interruption_persists_incomplete_vector_before_propagating(m1_case, tmp_path, monkeypatch):
    from vgar.evaluation.repair import verifier_eval as api
    task, _ = m1_case
    def interrupt(*a, **kw):
        raise KeyboardInterrupt()
    monkeypatch.setattr(api, 'collect_patch_vector', interrupt)
    with pytest.raises(KeyboardInterrupt):
        api.verify_once(task, FIX, RepairPolicy(), tmp_path / 'interrupted', temp_root=tmp_path / 'temp')
    vector = json.loads((tmp_path / 'interrupted/vector.json').read_bytes())
    assert vector['integrity']['status'] == 'ERROR'
    assert 'INTERRUPTED' in vector['integrity']['reasons']


def test_frozen_pool_end_to_end_and_consumer_rejects_wrong_candidate_proof(m1_case, tmp_path):
    from vgar.evaluation.repair import verifier_eval as api
    from vgar.evaluation.repair.mutant_pool import PoolTask, build_pool
    task, _ = m1_case
    before = inventory(task.source_repo)
    pool_root, run_root = tmp_path / 'pool', tmp_path / 'run'
    pool = build_pool([PoolTask(task.task_id, task.repo_key, task.revision, task.source_repo,
        FIX, task.allowed_source_paths, task.protected_paths, fixture=True)], pool_root)
    variants = {name: load_variant(REPO / 'configs/m2/variants' /
        ('A3.json' if name == 'A3' else f'w10/{name}.json')) for name in ('A0', 'A1', 'A2', 'A3')}
    run = api.evaluate_pool(pool_root, run_root, lambda task_id: (task, None), RepairPolicy(), variants,
        expected_pool_hash=pool['pool_hash'], temp_root=tmp_path / 'temp')
    summary = api.report_campaign(pool_root, run_root, expected_pool_hash=pool['pool_hash'])
    assert summary['complete'] is True and summary['expected_slots'] == 6
    assert summary['generated_patches'] == 4
    assert inventory(task.source_repo) == before
    gold = next(r for r in run['slots'] if r['operator'] == 'gold')
    bad = next(r for r in run['slots'] if r['operator'] == 'signature_change')
    gold_dir, bad_dir = (run_root / gold['vector_ref']).parent, (run_root / bad['vector_ref']).parent
    original_campaign = copy.deepcopy(run)
    original_bad = {p.relative_to(bad_dir).as_posix(): p.read_bytes() for p in bad_dir.rglob('*') if p.is_file()}
    gv, bv = json.loads((gold_dir / 'vector.json').read_bytes()), json.loads((bad_dir / 'vector.json').read_bytes())
    for name in ('api', 'structural'):
        shutil.copyfile(gold_dir / gv['post']['compatibility'][name]['details_ref'],
                        bad_dir / bv['post']['compatibility'][name]['details_ref'])
    bv['post'] = copy.deepcopy(gv['post'])
    api.atomic_json(bad_dir / 'vector.json', api.seal_vector(bv))
    bad['vector_file_hash'] = api.digest((bad_dir / 'vector.json').read_bytes())
    api._save_campaign(run_root, run)
    with pytest.raises(ValueError, match='(binding|source|candidate)'):
        api.report_campaign(pool_root, run_root, expected_pool_hash=pool['pool_hash'])
    # Restore fixture evidence, then reproduce the ERROR-row bypass with no vector edits.
    for name, raw in original_bad.items():
        (bad_dir / name).write_bytes(raw)
    run = original_campaign
    bad = next(r for r in run['slots'] if r['operator'] == 'signature_change')
    bad.update(status='ERROR', vector_ref=gold['vector_ref'], vector_file_hash=gold['vector_file_hash'])
    api._save_campaign(run_root, run)
    with pytest.raises(ValueError, match='(state|binding|ERROR)'):
        api.report_campaign(pool_root, run_root, expected_pool_hash=pool['pool_hash'])
