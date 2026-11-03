"""Derive a runner experiment config from a template and freshly exported bundles (M1-W12, spec §4.8)."""
import copy
import hashlib
import json

import subprocess
import sys

import pytest
from m3_support import ROOT, write_json

from vgar.evaluation.repair.derive_config import BUNDLE_FILES, derive_config
from vgar.evaluation.repair.manifest import load_experiment

TEMPLATE = {
    'schema': 'vgar-m3-experiment-v1',
    'source': {
        'type': 'swebench',
        'manifest': {'path': '../m1/w10_dev_manifest.json', 'sha256': 'sha256:' + 'a' * 64},
        'task_ids': ['t1', 't2', 't3'],
        'profiles': {t: {'path': f'@data/profiles/{t}.json', 'sha256': 'sha256:' + '0' * 64} for t in ('t1', 't2', 't3')},
        'checkouts': '@data/repositories/{task_id}',
        'bundle_profile': {'path': '../m1/w9_bundle_profile_repair.json', 'sha256': 'sha256:' + 'b' * 64},
        'bundles': {t: {} for t in ('t1', 't2', 't3')},
        'graph_documents': {t: {'path': f'@data/bundles/repair/{t}/graph.json', 'sha256': 'x'} for t in ('t1', 't2', 't3')},
        'task_inputs': 'w10_dev/tasks',
        'docker_host': 'unix:///var/run/docker.sock',
    },
    'repair_config': '../m2/w9_pilot_linux.json',
    'generation': 'real',
    'variants': [{'path': '../m2/variants/w10/A0.json', 'arm': 'bm25'}],
}


def _sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_hash(task):
    return 'sha256:' + hashlib.sha256(task.encode()).hexdigest()


def _data_root(tmp_path, tasks):
    data = tmp_path / 'data'
    for task in tasks:
        (data / 'profiles').mkdir(parents=True, exist_ok=True)
        (data / f'profiles/{task}.json').write_text(json.dumps({'task': task, 'profile_hash': _profile_hash(task)}),
                                                    encoding='utf-8')
        base = data / 'w12/bundles/repair' / task
        for arm in ('bm25', 'graph'):
            (base / arm).mkdir(parents=True, exist_ok=True)
            for name in BUNDLE_FILES:
                (base / arm / name).write_text(f'{task}/{arm}/{name}', encoding='utf-8')
        (base / 'graph.json').write_text(f'{{"graph": "{task}"}}', encoding='utf-8')
    return data


def _derive(tmp_path, data, task_ids, **kwargs):
    return derive_config(TEMPLATE, template_dir=tmp_path / 'configs/m3', data_root=data, task_ids=task_ids,
                         bundle_dir='@data/w12/bundles/repair', **kwargs)


def test_derive_recomputes_hashes_and_keeps_order(tmp_path):
    data = _data_root(tmp_path, ['t1', 't2'])
    before = copy.deepcopy(TEMPLATE)
    out = _derive(tmp_path, data, ['t2', 't1'], variants=[{'path': '/abs/A0.json', 'arm': 'bm25'}])
    source = out['source']
    assert source['task_ids'] == ['t2', 't1']
    assert set(source['profiles']) == set(source['bundles']) == set(source['graph_documents']) == {'t1', 't2'}
    graph = source['bundles']['t1']['graph']
    assert graph['path'] == '@data/w12/bundles/repair/t1/graph'
    assert graph['hashes']['context.json'] == _sha(data / 'w12/bundles/repair/t1/graph/context.json')
    assert source['graph_documents']['t1'] == {'path': '@data/w12/bundles/repair/t1/graph.json',
                                               'sha256': _sha(data / 'w12/bundles/repair/t1/graph.json')}
    assert source['profiles']['t2']['sha256'] == _profile_hash('t2')   # admission compares profile['profile_hash']
    assert out['variants'] == [{'path': '/abs/A0.json', 'arm': 'bm25'}]
    assert TEMPLATE == before


def test_relative_paths_become_absolute_from_the_template_dir(tmp_path):
    data = _data_root(tmp_path, ['t1'])
    out = _derive(tmp_path, data, ['t1'], variants=[])
    base = (tmp_path / 'configs/m3').resolve()
    assert out['repair_config'] == str((base / '../m2/w9_pilot_linux.json').resolve())
    assert out['source']['manifest']['path'] == str((base / '../m1/w10_dev_manifest.json').resolve())
    assert out['source']['bundle_profile']['path'] == str((base / '../m1/w9_bundle_profile_repair.json').resolve())
    assert out['source']['task_inputs'] == str((base / 'w10_dev/tasks').resolve())
    assert out['source']['checkouts'] == '@data/repositories/{task_id}'
    assert out['source']['manifest']['sha256'] == TEMPLATE['source']['manifest']['sha256']


def test_missing_bundle_file_fails(tmp_path):
    data = _data_root(tmp_path, ['t1'])
    (data / 'w12/bundles/repair/t1/bm25/test_links.json').unlink()
    with pytest.raises(FileNotFoundError, match='test_links.json'):
        _derive(tmp_path, data, ['t1'], variants=[])


def test_cli_writes_a_config_the_runner_loads(swebench_config, tmp_path):
    config, data = swebench_config
    for arm in ('bm25', 'graph'):
        for name in BUNDLE_FILES:
            write_json(data / 'w12/bundles/repair/demo__demo-1' / arm / name, {'arm': arm, 'name': name})
    out = tmp_path / 'run/w12_dry_run.json'
    subprocess.run([sys.executable, 'scripts/derive_experiment_config.py', '--template', str(config),
                    '--data-root', str(data), '--tasks', 'demo__demo-1', '--bundle-dir', '@data/w12/bundles/repair',
                    '--variants', 'A0:bm25,A2:graph', '--out', str(out)], check=True, cwd=ROOT)
    experiment = load_experiment(out, data)
    assert list(experiment.task_ids) == ['demo__demo-1']
    assert [v.variant_id for v in experiment.variants] == ['A0', 'A2']


def test_cli_removes_output_when_runner_rejects_it(swebench_config, tmp_path):
    config, data = swebench_config
    template = json.loads(config.read_text(encoding='utf-8'))
    template['source']['manifest']['sha256'] = 'sha256:' + '9' * 64      # runner: pinned manifest hash mismatch
    write_json(config, template)
    for arm in ('bm25', 'graph'):
        for name in BUNDLE_FILES:
            write_json(data / 'w12/bundles/repair/demo__demo-1' / arm / name, {})
    out = tmp_path / 'run/w12_dry_run.json'
    process = subprocess.run([sys.executable, 'scripts/derive_experiment_config.py', '--template', str(config),
                              '--data-root', str(data), '--tasks', 'demo__demo-1',
                              '--bundle-dir', '@data/w12/bundles/repair', '--variants', 'A0:bm25', '--out', str(out)],
                             cwd=ROOT, capture_output=True, text=True)
    assert process.returncode != 0 and not out.exists() and 'rejected' in process.stderr


def test_task_not_in_template_fails(tmp_path):
    data = _data_root(tmp_path, ['t1'])
    with pytest.raises(ValueError, match='zz'):
        _derive(tmp_path, data, ['t1', 'zz'], variants=[])
