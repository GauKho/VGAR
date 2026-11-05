"""V13/V14: deterministic labelled source mutations, independent of verification."""
from __future__ import annotations

import ast
import importlib
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GOLD = '--- a/a.py\n+++ b/a.py\n@@ -1,4 +1,4 @@\n def public(value=0):\n     if value > 0:\n-        return value\n+        return value + 1\n     return 0\n'
OPERATORS = ('condition_flip', 'public_function_delete', 'signature_change', 'import_cycle', 'test_skip')


def api():
    assert importlib.util.find_spec('vgar.evaluation.repair.mutant_pool'), 'M2-W12-2 pool builder missing'
    return importlib.import_module('vgar.evaluation.repair.mutant_pool')


@pytest.fixture
def task(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_bytes(b'def public(value=0):\n    if value > 0:\n        return value\n    return 0\n')
    (root / 'b.py').write_bytes(b'import a\n')
    (root / 'tests').mkdir()
    (root / 'tests/test_protected.py').write_bytes(b'# do not touch\n')
    return root


def spec(root, **updates):
    return api().PoolTask(**(dict(task_id='fixture-1', repo='fixture/repo', base_commit='fixture-base',
        source_repo=root, gold_patch=GOLD, allowed_paths=('a.py', 'b.py'), fixture=True) | updates))


def predict(root, raw):
    from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff
    return _bind(parse_unified_diff(raw, PatchPolicy(('a.py', 'b.py'), ('tests',))), root)[0]


def test_mutant_pool_has_six_labelled_slots_with_real_net_patches(task, tmp_path):
    module = api()
    before = {p.relative_to(task).as_posix(): p.read_bytes() for p in task.rglob('*') if p.is_file()}
    out = tmp_path / 'pool'
    result = module.build_pool([spec(task)], out)
    assert result['schema'] == 'vgar-mutant-pool-v1'
    assert result['expected_slots'] == 6
    assert result['seed'] == 0
    assert [s['operator'] for s in result['slots']] == ['gold', *OPERATORS]
    assert [s['label'] for s in result['slots']] == ['GOOD', *(['BAD'] * 5)]
    assert all(s['status'] == 'CREATED' for s in result['slots'])
    assert module.load_pool(out, expected_pool_hash=result['pool_hash']) == result
    mutations = {}
    for slot in result['slots']:
        assert slot['slot_id'] == 'fixture-1::' + slot['operator']
        raw = (out / slot['patch_ref']).read_text(encoding='utf-8')
        changed = predict(task, raw)
        mutations[slot['operator']] = changed
        assert set(changed) <= {'a.py', 'b.py'}
        for source in changed.values():
            ast.parse(source)
        assert slot['patch_hash'].startswith('sha256:')
    assert b'return value + 1' in mutations['condition_flip']['a.py']
    assert b'not (' in mutations['condition_flip']['a.py']
    assert b'def public' not in mutations['public_function_delete']['a.py']
    assert b'_vgar_required' in mutations['signature_change']['a.py']
    assert b'_vgar_cycle' in mutations['import_cycle']['a.py']
    assert b'SkipTest' in mutations['test_skip']['a.py']
    assert {p.relative_to(task).as_posix(): p.read_bytes() for p in task.rglob('*') if p.is_file()} == before


def test_mutant_pool_deterministic_and_relocatable(task, tmp_path):
    module = api()
    first, second = tmp_path / 'first', tmp_path / 'second'
    module.build_pool([spec(task)], first, seed=0)
    module.build_pool([spec(task)], second, seed=0)
    a = {p.relative_to(first).as_posix(): p.read_bytes() for p in first.rglob('*') if p.is_file()}
    b = {p.relative_to(second).as_posix(): p.read_bytes() for p in second.rglob('*') if p.is_file()}
    assert a == b
    serialized = (first / 'pool.json').read_text(encoding='utf-8')
    assert str(tmp_path) not in serialized
    assert 'source_repo' not in serialized


def test_mutant_labels_independent_of_verifier():
    api()
    pending = ['vgar.evaluation.repair.mutant_pool']
    seen = set()
    forbidden = ('vgar.repair.verification', 'vgar.repair.session', 'vgar.repair.pipeline',
                 'vgar.evaluation.repair.verifier_eval')
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        assert not any(module == bad or module.startswith(bad + '.') for bad in forbidden), module
        path = ROOT / 'src' / (module.replace('.', '/') + '.py')
        if not path.exists():
            path = ROOT / 'src' / module.replace('.', '/') / '__init__.py'
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names if alias.name.startswith('vgar.'))
            elif isinstance(node, ast.ImportFrom):
                package = module if path.name == '__init__.py' else module.rpartition('.')[0]
                name = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level else node.module
                if name and name.startswith('vgar.'):
                    pending.append(name)
                    for alias in node.names:
                        child = name + '.' + alias.name
                        if (ROOT / 'src' / (child.replace('.', '/') + '.py')).is_file():
                            pending.append(child)
        # Python also executes package initializers on the import path.
        parts = module.split('.')
        pending.extend('.'.join(parts[:n]) for n in range(1, len(parts))
                       if (ROOT / 'src' / Path(*parts[:n]) / '__init__.py').is_file())


@pytest.mark.parametrize('fault', ['patch_bytes', 'index_bytes', 'expected_hash'])
def test_pool_consumer_rejects_hash_drift(task, tmp_path, fault):
    module = api()
    out = tmp_path / 'pool'
    result = module.build_pool([spec(task)], out)
    expected = result['pool_hash']
    if fault == 'patch_bytes':
        (out / result['slots'][0]['patch_ref']).write_bytes(b'not the sealed patch')
    elif fault == 'index_bytes':
        value = json.loads((out / 'pool.json').read_bytes())
        value['slots'][0]['label'] = 'BAD'
        (out / 'pool.json').write_text(json.dumps(value), encoding='utf-8')
    else:
        expected = 'sha256:' + 'f' * 64
    with pytest.raises(ValueError):
        module.load_pool(out, expected_pool_hash=expected)


@pytest.mark.parametrize('source', [b'value = 1\n', b'def _private(value):\n    return value\n'])
def test_inapplicable_operators_stay_in_ledger(task, tmp_path, source):
    (task / 'a.py').write_bytes(source)
    old = source.decode('utf-8').splitlines()
    gold = '--- a/a.py\n+++ b/a.py\n@@ -1,' + str(len(old)) + ' +1,' + str(len(old) + 1) + ' @@\n'
    gold += ''.join(' ' + line + '\n' for line in old) + '+# gold\n'
    result = api().build_pool([spec(task, gold_patch=gold)], tmp_path / 'pool')
    assert len(result['slots']) == 6
    slots = {s['operator']: s for s in result['slots']}
    assert slots['gold']['status'] == 'CREATED'
    for name in ('condition_flip', 'public_function_delete', 'signature_change', 'test_skip'):
        assert slots[name]['status'] == 'NOT_APPLICABLE'
        assert slots[name]['reason']
        assert slots[name]['patch_ref'] is None


def test_gold_failure_preserves_all_slots_as_errors(task, tmp_path):
    result = api().build_pool([spec(task, gold_patch='not a diff')], tmp_path / 'pool')
    assert result['expected_slots'] == len(result['slots']) == 6
    assert all(s['status'] == 'ERROR' and s['patch_ref'] is None for s in result['slots'])


def test_protected_test_gold_patch_cannot_enter_pool(task, tmp_path):
    raw = '--- a/tests/test_protected.py\n+++ b/tests/test_protected.py\n@@ -1 +1 @@\n-# do not touch\n+# changed\n'
    result = api().build_pool([spec(task, gold_patch=raw)], tmp_path / 'pool')
    assert all(s['status'] == 'ERROR' for s in result['slots'])
    assert (task / 'tests/test_protected.py').read_bytes() == b'# do not touch\n'


def test_labels_are_fixed_before_outcomes_and_skip_only_edits_production(task, tmp_path):
    result = api().build_pool([spec(task)], tmp_path / 'pool')
    slot = next(s for s in result['slots'] if s['operator'] == 'test_skip')
    assert slot['label'] == 'BAD'
    raw = (tmp_path / 'pool' / slot['patch_ref']).read_text(encoding='utf-8')
    assert set(predict(task, raw)) == {'a.py'}
    assert '__import__("unittest").SkipTest' in raw


@pytest.mark.parametrize('bad_seed', [True, 0.0, '0', -1])
def test_invalid_seed_rejected(task, tmp_path, bad_seed):
    with pytest.raises(ValueError):
        api().build_pool([spec(task)], tmp_path / 'pool', seed=bad_seed)


def test_duplicate_task_and_existing_output_rejected(task, tmp_path):
    module = api()
    with pytest.raises(ValueError):
        module.build_pool([spec(task), spec(task)], tmp_path / 'pool')
    out = tmp_path / 'already'
    out.mkdir()
    with pytest.raises(FileExistsError):
        module.build_pool([spec(task)], out)


def test_unicode_crlf_and_eof_preserved_in_bound_net_patch(task, tmp_path):
    before = 'def public(value="é"):\r\n    if value:\r\n        return value\r\n    return ""'.encode()
    (task / 'a.py').write_bytes(before)
    raw = '--- a/a.py\n+++ b/a.py\n@@ -1,4 +1,4 @@\n def public(value="é"):\n     if value:\n-        return value\n+        return value.strip()\n     return ""\n\\ No newline at end of file\n'
    result = api().build_pool([spec(task, gold_patch=raw)], tmp_path / 'pool')
    slot = next(s for s in result['slots'] if s['operator'] == 'condition_flip')
    assert slot['status'] == 'CREATED'
    changed = predict(task, (tmp_path / 'pool' / slot['patch_ref']).read_text(encoding='utf-8'))['a.py']
    assert b'\r\n' in changed and not changed.endswith(b'\n')
    assert 'é'.encode() in changed
    assert (task / 'a.py').read_bytes() == before


def test_external_import_with_internal_prefix_is_not_a_cycle_anchor(task, tmp_path):
    (task / 'b.py').write_bytes(b'import a.external\n')
    result = api().build_pool([spec(task)], tmp_path / 'pool')
    slot = next(s for s in result['slots'] if s['operator'] == 'import_cycle')
    assert slot['status'] == 'NOT_APPLICABLE'


def test_dynamic_export_mutation_is_not_misreported_as_public(task, tmp_path):
    source = (task / 'a.py').read_bytes()
    (task / 'a.py').write_bytes(b'__all__ = ["public"]\n__all__.clear()\n' + source)
    shifted = GOLD.replace('@@ -1,4 +1,4 @@', '@@ -3,4 +3,4 @@')
    result = api().build_pool([spec(task, gold_patch=shifted)], tmp_path / 'pool')
    for slot in result['slots']:
        if slot['operator'] in ('public_function_delete', 'signature_change', 'test_skip'):
            assert slot['status'] == 'NOT_APPLICABLE'


def test_source_drift_during_build_leaves_error_slots_not_published_patches(task, tmp_path, monkeypatch):
    module = api()
    original = module._snapshot
    calls = 0

    def changed(task):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError('Concurrent source drift')
        return original(task)

    monkeypatch.setattr(module, '_snapshot', changed)
    result = module.build_pool([spec(task)], tmp_path / 'pool')
    assert all(s['status'] == 'ERROR' and s['reason'] == 'SOURCE_CHANGED_DURING_BUILD' for s in result['slots'])
    assert not list((tmp_path / 'pool').rglob('*.diff'))


@pytest.mark.parametrize('fault', ['missing_slot', 'duplicate_slot', 'seed', 'prediction', 'no_source', 'protected_prediction'])
def test_consumer_rejects_forged_internal_shape_even_with_recomputed_hash(task, tmp_path, fault):
    module = api()
    out = tmp_path / 'pool'
    data = module.build_pool([spec(task)], out)
    if fault == 'missing_slot':
        data['slots'].pop()
    elif fault == 'duplicate_slot':
        data['slots'][-1] = data['slots'][0]
    elif fault == 'seed':
        data['seed'] = True
    elif fault == 'no_source':
        data['tasks'][0]['source_inventory'] = None
        data['tasks'][0]['source_inventory_hash'] = None
    elif fault == 'prediction':
        data['slots'][0]['predicted_inventory_hash'] = 'sha256:' + '0' * 64
    else:
        slot = data['slots'][0]
        slot['predicted_inventory']['tests/test_protected.py'] = 'sha256:' + '1' * 64
        slot['predicted_inventory_hash'] = module._hash(module._canonical(slot['predicted_inventory']))
    data['pool_hash'] = module._hash(module._canonical({k: v for k, v in data.items() if k != 'pool_hash'}))
    (out / 'pool.json').write_bytes(module._canonical(data) + b'\n')
    with pytest.raises(ValueError):
        module.load_pool(out)


def test_approved_population_is_exact_11_plus_14_w10_ids():
    module = api()
    configs = module.approved_w10_population()
    assert [len(c['source']['task_ids']) for _, c in configs] == [11, 14]
    ids = [t for _, c in configs for t in c['source']['task_ids']]
    assert len(ids) == len(set(ids)) == 25
    assert tuple(ids) == module.W10_IDS


def test_missing_parquet_keeps_all_150_slots_with_error_reasons(tmp_path):
    module = api()
    tasks, pins = module.load_w10_tasks(tmp_path / 'missing.parquet', tmp_path / 'no-data')
    result = module.build_pool(tasks, tmp_path / 'pool', provenance=pins)
    assert result['expected_slots'] == len(result['slots']) == 150
    assert all(s['status'] == 'ERROR' and s['reason'] == 'PARQUET_NOT_READY' for s in result['slots'])
    assert result['ready'] is False
    assert len(result['tasks']) == 25


def test_bad_parquet_hash_is_integrity_error_not_replacement_population(tmp_path):
    module = api()
    (tmp_path / 'wrong.parquet').write_bytes(b'wrong snapshot')
    tasks, pins = module.load_w10_tasks(tmp_path / 'wrong.parquet', tmp_path / 'no-data')
    result = module.build_pool(tasks, tmp_path / 'pool', provenance=pins)
    assert len(result['tasks']) == 25
    assert all(s['reason'] == 'PARQUET_HASH_MISMATCH' for s in result['slots'])
    assert result['provenance']['dataset_status'] == 'PARQUET_HASH_MISMATCH'


@pytest.mark.parametrize('fault', ['real_seed', 'real_population', 'mixed_fixture', 'dataset_revision', 'parquet_pin', 'manifest_pin', 'ready_dataset_actual_hash'])
def test_real_pool_pins_and_population_cannot_be_forged(tmp_path, fault):
    module = api()
    tasks, pins = module.load_w10_tasks(tmp_path / 'missing.parquet', tmp_path / 'no-data')
    out = tmp_path / 'pool'
    data = module.build_pool(tasks, out, provenance=pins)
    if fault == 'real_seed':
        data['seed'] = 1
    elif fault == 'real_population':
        data['tasks'][0]['task_id'] = 'replacement-task'
        for slot in data['slots'][:6]:
            slot['task_id'] = 'replacement-task'
            slot['slot_id'] = 'replacement-task::' + slot['operator']
    elif fault == 'mixed_fixture':
        data['tasks'][0]['fixture'] = True
    elif fault == 'dataset_revision':
        data['provenance']['dataset_revision'] = '0' * 40
    elif fault == 'parquet_pin':
        data['provenance']['parquet_hash'] = 'sha256:' + '0' * 64
    elif fault == 'manifest_pin':
        data['provenance']['manifest_hash'] = 'sha256:' + '0' * 64
    else:
        data['provenance']['dataset_status'] = 'READY'
        data['provenance']['dataset_actual_hash'] = 'sha256:' + '0' * 64
    data['pool_hash'] = module._hash(module._canonical({k: v for k, v in data.items() if k != 'pool_hash'}))
    (out / 'pool.json').write_bytes(module._canonical(data) + b'\n')
    with pytest.raises(ValueError):
        module.load_pool(out)


def test_builder_rejects_real_seed_drift_before_writing(tmp_path):
    module = api()
    tasks, pins = module.load_w10_tasks(tmp_path / 'missing.parquet', tmp_path / 'no-data')
    with pytest.raises(ValueError):
        module.build_pool(tasks, tmp_path / 'pool', seed=1, provenance=pins)
    assert not (tmp_path / 'pool').exists()


def test_target_source_is_never_imported_or_executed(task, tmp_path):
    source = (task / 'a.py').read_bytes()
    (task / 'a.py').write_bytes(b'raise AssertionError("target code executed")\n' + source)
    shifted = GOLD.replace('@@ -1,4 +1,4 @@', '@@ -2,4 +2,4 @@')
    result = api().build_pool([spec(task, gold_patch=shifted)], tmp_path / 'pool')
    assert all(s['status'] == 'CREATED' for s in result['slots'])


def _tree_bytes(root):
    return {p.relative_to(root).as_posix(): ('link', str(p.readlink())) if p.is_symlink()
            else ('file', p.read_bytes()) if p.is_file() else ('directory', None)
            for p in root.rglob('*')}


@pytest.mark.parametrize('relation', ['equal', 'output_inside_source', 'source_inside_output'])
@pytest.mark.parametrize('unavailable', [False, True])
def test_output_source_overlap_rejected_before_any_filesystem_write(task, tmp_path, relation, unavailable):
    source = task if not unavailable else tmp_path / 'missing' / 'source'
    output = {'equal': source, 'output_inside_source': source / 'new' / 'pool',
              'source_inside_output': source.parent}[relation]
    before = _tree_bytes(tmp_path)
    task_spec = spec(source, unavailable_reason='SOURCE_NOT_READY' if unavailable else None)
    with pytest.raises(ValueError, match='overlap'):
        api().build_pool([task_spec], output)
    assert _tree_bytes(tmp_path) == before


@pytest.mark.parametrize('alias_side', ['output', 'source'])
def test_output_source_overlap_resolves_directory_symlinks_before_writing(task, tmp_path, alias_side):
    alias = tmp_path / 'source-alias'
    try:
        alias.symlink_to(task, target_is_directory=True)
    except (OSError, NotImplementedError):
        if os.name != 'nt':
            pytest.skip('Directory symlinks are not supported by this host')
        try:
            import _winapi
            _winapi.CreateJunction(str(task), str(alias))
        except (OSError, AttributeError):
            pytest.skip('Directory symlinks and junctions are not supported by this host')
    try:
        source = alias if alias_side == 'source' else task
        output = (alias if alias_side == 'output' else task) / 'new' / 'pool'
        before = _tree_bytes(tmp_path)
        with pytest.raises(ValueError, match='overlap'):
            api().build_pool([spec(source)], output)
        assert _tree_bytes(tmp_path) == before
    finally:
        if alias.is_symlink():
            alias.unlink()
        else:
            alias.rmdir()
