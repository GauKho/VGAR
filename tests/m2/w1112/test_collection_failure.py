"""T5: only complete, structured collection errors establish a test failure."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.repair import test_runner
from vgar.repair.executor import NativeExecutor
from vgar.repair.workspace import create_workspace


@pytest.mark.parametrize('source', [b'import missing_vgar_t5_dependency\n', b'def broken(:\n'])
@pytest.mark.parametrize('collect', [False, True])
def test_real_pytest_collection_failure_has_complete_evidence(tmp_path, source, collect):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'test_broken.py').write_bytes(source)
    with create_workspace(root, tmp_path / 'ws') as lease:
        invoke = test_runner.collect_tests if collect else test_runner.run_tests
        result = invoke(lease, ('test_broken.py',), NativeExecutor(lease), 30)
        assert result['command']['exit_code'] == result['exit_code'] == 2
        assert result['complete'] is True and result['collection_errors']
        assert result['junit_xml']
        assert (result['status'], result['reason']) == ('FAIL', 'TEST_COLLECTION_FAILED')
        assert result['node_ids'] == []


def collection_evidence():
    return dict(status='FAIL', reason='TEST_COLLECTION_FAILED', complete=True, exit_code=2,
        command=dict(complete=True, exit_code=2, timed_out=False, output_truncated=False),
        collection_errors=['ImportError: missing public function'], node_ids=[], outcomes={},
        durations_ms={}, junit_xml='<testsuite><testcase><error>ImportError</error></testcase></testsuite>')


@pytest.mark.parametrize('fault', [None, 'missing_json', 'missing_junit', 'json', 'junit',
    'mismatch', 'timeout', 'truncated', 'incomplete', 'zero_tests', 'all_skip',
    'internal', 'usage', 'interrupt', 'missing_fields', 'bad_type', 'injected_status'])
def test_report_evidence_never_infers_collection_failure_from_exit_alone(tmp_path, fault):
    evidence = collection_evidence()
    data = {k: copy.deepcopy(evidence[k]) for k in (
        'complete', 'exit_code', 'collection_errors', 'node_ids', 'outcomes', 'durations_ms')}
    command = copy.deepcopy(evidence['command'])
    xml = evidence['junit_xml']
    if fault == 'mismatch':
        data['exit_code'] = 0
    elif fault in ('timeout', 'truncated'):
        command['timed_out' if fault == 'timeout' else 'output_truncated'] = True
    elif fault == 'incomplete':
        data['complete'] = False
    elif fault == 'zero_tests':
        data['collection_errors'] = []
        data['exit_code'] = command['exit_code'] = 5
    elif fault == 'all_skip':
        data.update(node_ids=['test_skip'], outcomes={'test_skip': 'SKIP'}, collection_errors=[], exit_code=0)
        command['exit_code'] = 0
    elif fault in ('internal', 'usage', 'interrupt'):
        data['exit_code'] = command['exit_code'] = {'internal': 3, 'usage': 4, 'interrupt': 2}[fault]
        data['collection_errors'] = []
    elif fault == 'missing_fields':
        del data['collection_errors']
    elif fault == 'bad_type':
        data['collection_errors'] = 'not a list'
    elif fault == 'injected_status':
        data.update(status='FAIL', reason='TEST_COLLECTION_FAILED', collection_errors=[])

    class Executor:
        def run(self, argv, cwd, timeout):
            report = Path(next(a.split('=', 1)[1] for a in argv if a.startswith('--m2-report-json=')))
            junit = report.with_name('junit.xml')
            if fault != 'missing_json':
                report.write_text('{' if fault == 'json' else json.dumps(data), encoding='utf-8')
            if fault != 'missing_junit':
                junit.write_text('<broken' if fault == 'junit' else xml, encoding='utf-8')
            return command

    lease = SimpleNamespace(path=tmp_path, private=tmp_path / 'private')
    invoke = test_runner.run_tests if fault == 'all_skip' else test_runner.collect_tests
    result = invoke(lease, ('test_broken.py',), Executor(), 30)
    if fault is None:
        assert (result['status'], result['reason']) == ('FAIL', 'TEST_COLLECTION_FAILED')
    else:
        assert (result['status'], result['reason']) == ('ERROR', 'VERIFICATION_INCOMPLETE')


def test_probe_report_inventory_distinguishes_present_and_missing(tmp_path):
    import hashlib
    from vgar.repair import docker_probe
    raw = b'{"complete": true}\n'
    (tmp_path / 'nodeids.json').write_bytes(raw)
    assert docker_probe.report_inventory(str(tmp_path), ['nodeids.json', 'junit.xml']) == {
        'nodeids.json': {'state': 'AVAILABLE', 'size_bytes': len(raw),
                         'sha256': 'sha256:' + hashlib.sha256(raw).hexdigest()},
        'junit.xml': {'state': 'MISSING'}}


@pytest.mark.parametrize('names', [['../escape'], ['other.json'], ['nodeids.json', 'nodeids.json']])
def test_probe_report_inventory_rejects_unapproved_names(tmp_path, names):
    from vgar.repair import docker_probe
    with pytest.raises(ValueError):
        docker_probe.report_inventory(str(tmp_path), names)


def test_probe_report_inventory_rejects_directory(tmp_path):
    from vgar.repair import docker_probe
    (tmp_path / 'nodeids.json').mkdir()
    with pytest.raises(ValueError):
        docker_probe.report_inventory(str(tmp_path), ['nodeids.json'])
