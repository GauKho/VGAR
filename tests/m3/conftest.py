"""Experiment configs for runner tests: a copied native fixture and a synthetic SWE-bench-shaped source."""
import shutil

import pytest
from m3_support import ROOT, git, variants, write_json


@pytest.fixture
def fixture_config(tmp_path):
    """Native trusted fixture copied under tmp_path, same relative layout as examples/m2."""
    examples = ROOT/'examples/m2'
    for part in ('snapshots/single_file_login', 'handoffs/single_file_login'):
        shutil.copytree(examples/part, tmp_path/'examples'/part,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    (tmp_path/'examples/tasks').mkdir(parents=True)
    shutil.copy(examples/'tasks/single_file_login.json', tmp_path/'examples/tasks/single_file_login.json')
    config = {'schema': 'vgar-m3-experiment-v1',
              'source': {'type': 'fixture', 'tasks': [str(tmp_path/'examples/tasks/single_file_login.json')]},
              'repair_config': str(ROOT/'configs/m2/demo.json'), 'generation': 'fake', 'variants': variants()}
    return write_json(tmp_path/'config.json', config)


@pytest.fixture
def swebench_config(tmp_path):
    """One COLLECTED and one EXCLUDED synthetic task; data paths live under tmp_path/'data'."""
    from vgar.evaluation.harness.task_env import build_profile
    data = tmp_path/'data'
    repo = data/'repositories/demo__demo-1'
    (repo/'pkg').mkdir(parents=True)
    (repo/'tests').mkdir()
    (repo/'pkg/core.py').write_text('def f():\n    return 1\n', encoding='utf-8')
    (repo/'pkg/test_core.py').write_text('def test_f():\n    pass\n', encoding='utf-8')
    (repo/'tests/test_f.py').write_text('def test_f():\n    pass\n', encoding='utf-8')
    git(repo, 'init', '-q')
    git(repo, 'config', 'core.autocrlf', 'false')
    git(repo, '-c', 'user.email=t@t', '-c', 'user.name=t', 'add', '.')
    git(repo, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'base')
    head = git(repo, 'rev-parse', 'HEAD')
    rows = [{'instance_id': 'demo__demo-1', 'repo': 'demo/demo', 'base_commit': head, 'problem_statement': 'f is wrong'},
            {'instance_id': 'demo__demo-2', 'repo': 'demo/demo', 'base_commit': head, 'problem_statement': 'g is wrong'}]
    manifest = write_json(tmp_path/'manifest.json', {'tasks': rows, 'manifest_hash': 'sha256:' + 'a'*64})
    profiles = {}
    for row, status, reason in ((rows[0], 'COLLECTED', None), (rows[1], 'EXCLUDED', 'PYTEST_UNAVAILABLE')):
        image = {'reference': 'swebench/sweb.eval.x86_64.' + row['instance_id'].replace('__', '_1776_') + '@sha256:' + 'b'*64,
                 'image_id': 'sha256:' + 'c'*64}
        source = {'head': head, 'clean': True, 'inventory_hash': 'sha256:' + 'd'*64, 'inventory_count': 1}
        probe = {'protocol': 'vgar-pytest-collection-v1', 'status': status, 'reason': reason,
                 'source_before': source, 'source_after': dict(source),
                 'runtime': {'python': '3.11.0', 'pytest': None if reason else '8.0.0',
                             'executable': '/opt/miniconda3/envs/testbed/bin/python'},
                 'collection': {'exit_code': None if reason else 0,
                                'node_ids': [] if reason else ['tests/test_f.py::test_f'], 'errors': []}}
        profile = build_profile(row, image, ['tests/test_f.py'], probe, daemon_id='synthetic-daemon')
        write_json(data/'profiles'/(row['instance_id'] + '.json'), profile)
        profiles[row['instance_id']] = {'path': '@data/profiles/' + row['instance_id'] + '.json',
                                        'sha256': profile['profile_hash']}
    bundles = {}
    for task_id in ('demo__demo-1', 'demo__demo-2'):
        bundles[task_id] = {}
        for arm, version in (('bm25', 'e'), ('graph', 'f')):
            write_json(data/'bundles'/task_id/arm/'context_manifest.json', {'graph_version': 'sha256:' + version*64})
            bundles[task_id][arm] = {'path': f'@data/bundles/{task_id}/{arm}',
                                     'hashes': {n: 'sha256:' + '1'*64 for n in
                                                ('context.json', 'context_manifest.json', 'test_links.json')}}
    inputs = tmp_path/'tasks'
    write_json(inputs/'demo__demo-1.json', {
        'source_roots': ['pkg'], 'failing_selectors': ['tests/vgar_w9_repro_f.py::test_f'],
        'fallback_scope': ['tests'], 'protected_paths': ['tests'],
        'overlay': {'tests/vgar_w9_repro_f.py': 'repro_f.py'}})
    (inputs/'repro_f.py').write_text('def test_f():\n    assert False\n', encoding='utf-8')
    config = {'schema': 'vgar-m3-experiment-v1',
              'source': {'type': 'swebench', 'manifest': {'path': str(manifest), 'sha256': 'sha256:' + 'a'*64},
                         'profiles': profiles, 'checkouts': '@data/repositories/{task_id}', 'bundles': bundles,
                         'task_inputs': str(inputs), 'docker_host': 'unix:///var/run/docker.sock'},
              'repair_config': str(ROOT/'configs/m2/demo.json'), 'generation': 'real', 'variants': variants()}
    return write_json(tmp_path/'config.json', config), data
