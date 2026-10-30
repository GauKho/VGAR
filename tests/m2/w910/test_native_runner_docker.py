"""Real Docker: native runners through admission + DockerExecutor (opt-in: VGAR_DOCKER_TESTS=1 in WSL).

Needs base-commit checkouts <VGAR_DATA>/repositories/<task> and the :latest official images.
Python 3.5 compatibility of native_runner.py is covered separately on the Django 1.11 image (W10 ledger).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('VGAR_DOCKER_TESTS') != '1', reason='opt-in real Docker test')

ROOT = Path(__file__).resolve().parents[3]
DJANGO_REPRO = ('from django.test import SimpleTestCase\n\n\nclass Repro(SimpleTestCase):\n'
                '    def test_pass(self):\n        self.assertEqual(1, 1)\n\n'
                '    def test_fail(self):\n        self.assertEqual(1, 2)\n')
SYMPY_REPRO = 'def test_pass():\n    assert 1 == 1\n\n\ndef test_fail():\n    assert 1 == 2\n'
CASES = {
    # Admission reserves the 'vgar_w9_repro_' marker; Django needs an app package, sympy a test_*.py in its package.
    'django': dict(task_id='django__django-11138', version='3.0', root='django', test='tests/vgar_w9_repro_issue/tests.py',
                   ids=['tests/vgar_w9_repro_issue/tests.py::Repro::test_fail',
                        'tests/vgar_w9_repro_issue/tests.py::Repro::test_pass'],
                   overlay={'tests/vgar_w9_repro_issue/__init__.py': '# VGAR issue reproduction app\n',
                            'tests/vgar_w9_repro_issue/tests.py': DJANGO_REPRO},
                   protected=('tests',)),
    'sympy': dict(task_id='sympy__sympy-20590', version='1.7', root='sympy',
                  test='sympy/vgar_w9_repro_issue/test_repro.py',
                  ids=['sympy/vgar_w9_repro_issue/test_repro.py::test_fail',
                       'sympy/vgar_w9_repro_issue/test_repro.py::test_pass'],
                  overlay={'sympy/vgar_w9_repro_issue/test_repro.py': SYMPY_REPRO},
                  protected=('sympy/vgar_w9_repro_issue',)),
}


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def manifest_for(task_id, tmp):
    """A one-task W10-policy manifest built from the pinned parquet (admission pins it by hash)."""
    import pyarrow.parquet as pq
    from vgar.evaluation.retrieval.pilot_manifest import W10_SELECTION, make_manifest
    parquet = ROOT/'data/downloads/c104f840cc67f8b6eec6f759ebc8b2693d585d4a/test-00000-of-00001.parquet'
    rows = [r for r in pq.read_table(parquet).to_pylist() if r['instance_id'] == task_id]
    manifest = make_manifest(rows, parquet_hash='sha256:' + hashlib.sha256(parquet.read_bytes()).hexdigest(),
                             selection_policy=W10_SELECTION)
    path = tmp/'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    return path, manifest


@pytest.fixture(scope='module', params=['django', 'sympy'])  # django checkouts carry tracked docs/*.png links
def case(request):
    return CASES[request.param]


@pytest.fixture(scope='module')
def executor_factory(tmp_path_factory, case):
    from vgar.evaluation.harness.task_env import NATIVE_SCOPE, qualify_task, runner_for
    from vgar.evaluation.harness.test_cmds import load_test_cmds
    from vgar.evaluation.repair.manifest import production_paths
    from vgar.repair.admission import admit_task, base_inventory, prepare_admitted_workspace
    from vgar.repair.contracts import RepairTask
    from vgar.repair.docker_executor import DockerExecutor

    tmp = tmp_path_factory.mktemp('native-docker')
    manifest_path, manifest = manifest_for(case['task_id'], tmp)
    row = manifest['tasks'][0]
    repo = 'swebench/sweb.eval.x86_64.' + case['task_id'].replace('__', '_1776_')
    image = {'reference': json.loads(docker('image', 'inspect', '--format', '{{json .RepoDigests}}', repo + ':latest'))[0],
             'image_id': docker('image', 'inspect', '--format', '{{.Id}}', repo + ':latest')}
    entry = runner_for(row['repo'], case['version'], load_test_cmds())
    native = {'runner': entry['runner'], 'native_command': {'env': entry['env'], 'argv': entry['argv']}}
    result = qualify_task(row, image, NATIVE_SCOPE, tmp/'qualify', docker_host='unix:///var/run/docker.sock',
                          daemon_id=json.loads(docker('info', '--format', '{{json .}}'))['ID'], native=native)
    assert result['status'] == 'COLLECTED', result.get('traceback')
    profile_path = Path(result['profile'])
    source = Path(os.environ['VGAR_DATA']).expanduser()/'repositories'/case['task_id']
    bundle = tmp/'bundle'
    bundle.mkdir()
    for name in ('context.json', 'context_manifest.json', 'test_links.json'):
        (bundle/name).write_text('{}', encoding='utf-8')
    task = RepairTask(task_id=case['task_id'], issue_text=row['problem_statement'], source_repo=source,
                      repo_key=row['repo'], revision=row['base_commit'], graph_version='docker-test',
                      bundle_directory=bundle, failing_selectors=(case['ids'][0],), fallback_scope=(case['test'],),
                      allowed_source_paths=production_paths(base_inventory(source, row['base_commit']), [case['root']]),
                      protected_paths=case['protected'])
    admission = admit_task(task, manifest_path, profile_path, expected_manifest_hash=manifest['manifest_hash'],
        expected_profile_hash=json.loads(profile_path.read_text())['profile_hash'],
        bundle_hashes={n: 'sha256:' + hashlib.sha256((bundle/n).read_bytes()).hexdigest()
                       for n in ('context.json', 'context_manifest.json', 'test_links.json')},
        source_roots=[case['root']], overlay=case['overlay'], docker_host='unix:///var/run/docker.sock')

    def make(name):
        lease = prepare_admitted_workspace(task, admission, tmp/name)
        return DockerExecutor(lease, task, admission, time.monotonic() + 600, 8 * 1024 * 1024)
    return make


def argv(lease, name, *tail):
    directory = lease.private/'reports'/name
    directory.mkdir(parents=True)
    return (sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'vgar.repair.pytest_plugin',
            '--m2-report-json=' + str(directory/'nodeids.json'), '--junitxml=' + str(directory/'junit.xml'), *tail), directory


@pytest.mark.parametrize('collect', [True, False])
def test_native_runner_through_docker_executor(executor_factory, case, collect):
    executor = executor_factory('collect' if collect else 'run')
    try:
        command, directory = argv(executor.lease, 'r', *(['--collect-only'] if collect else []), case['test'])
        result = executor.run(command, executor.lease.path, 300)
        assert result['complete'] and result['status'] in ('PASS', 'FAIL'), json.dumps(
            {k: v for k, v in result.items() if k != 'argv'}, default=str)[:6000]
        # Review Focus 4: the native runner must leave /testbed exactly as the snapshot it started from.
        assert result['target_result']['snapshot_after'] == result['target_result']['snapshot_before']
        report = json.loads((directory/'nodeids.json').read_text(encoding='utf-8'))
        assert report['node_ids'] == case['ids']
        if collect:
            assert result['exit_code'] == 0
        else:
            assert result['exit_code'] == 1
            assert report['outcomes'] == {case['ids'][0]: 'FAIL', case['ids'][1]: 'PASS'}
    finally:
        executor.lease.__exit__()
