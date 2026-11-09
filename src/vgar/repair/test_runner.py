"""Capture actual pytest collection/outcomes alongside raw command/JUnit evidence."""
import json
import math
import sys
import uuid
import xml.etree.ElementTree as ET

from vgar.repair.contracts import safe_selector
from vgar.repair.diagnostics import exception_details


def _validate_report(data):
    if not isinstance(data, dict) or type(data.get('complete')) is not bool or type(data.get('exit_code')) is not int:
        raise ValueError('Invalid test report completion/exit code')
    for name in ('node_ids', 'collection_errors'):
        values = data.get(name)
        if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
            raise ValueError('Invalid test report ' + name)
    if len(set(data['node_ids'])) != len(data['node_ids']):
        raise ValueError('Duplicate test node IDs')
    outcomes, durations = data.get('outcomes'), data.get('durations_ms')
    if (not isinstance(outcomes, dict) or not isinstance(durations, dict)
            or not set(outcomes).issubset(data['node_ids']) or not set(durations).issubset(data['node_ids'])
            or any(v not in ('PASS', 'FAIL', 'ERROR', 'SKIP', 'XFAIL', 'XPASS') for v in outcomes.values())
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in durations.values())):
        raise ValueError('Invalid test outcomes/durations')


def is_collection_failure(result):
    """A reason/exit code alone cannot promote incomplete evidence to a patch failure."""
    try:
        _validate_report(result)
        command = result['command']
        xml = ET.fromstring(result['junit_xml'])
        return bool(result.get('status') == 'FAIL' and result.get('reason') == 'TEST_COLLECTION_FAILED'
            and result['complete'] is True and command['complete'] is True
            and not command.get('timed_out') and not command.get('output_truncated')
            and type(command['exit_code']) is int and command['exit_code'] == result['exit_code'] == 2
            and result['collection_errors'] and xml.tag in ('testsuite', 'testsuites'))
    except (KeyError, TypeError, ValueError, ET.ParseError):
        return False


def _invoke(lease, selectors, executor, timeout_seconds, collect):
    if not selectors:
        raise ValueError('No selectors')
    selected = tuple(safe_selector(s) for s in selectors)
    directory = lease.private / 'reports' / uuid.uuid4().hex
    directory.mkdir(parents=True)
    report, junit = directory / 'nodeids.json', directory / 'junit.xml'
    args = (sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '-p', 'vgar.repair.pytest_plugin', '--m2-report-json=' + str(report),
            '--junitxml=' + str(junit), *(('--collect-only',) if collect else ()), *selected)
    command = executor.run(args, lease.path, timeout_seconds)
    result = dict(command=command, status='ERROR', reason='VERIFICATION_INCOMPLETE',
                  node_ids=[], outcomes={}, durations_ms={}, junit_xml=None)
    try:
        data = json.loads(report.read_text(encoding='utf-8'))
        _validate_report(data)
        xml = junit.read_text(encoding='utf-8')
        if ET.fromstring(xml).tag not in ('testsuite', 'testsuites'):
            raise ValueError('Invalid JUnit root')
        result.update({k: data[k] for k in ('node_ids', 'outcomes', 'durations_ms',
                                           'collection_errors', 'complete', 'exit_code')}, junit_xml=xml)
        if (command['complete'] is not True or not data['complete'] or command.get('timed_out')
                or command.get('output_truncated') or type(command['exit_code']) is not int
                or command['exit_code'] != data['exit_code']):
            return result
        if data['collection_errors']:
            if command['exit_code'] == 2:
                result.update(status='FAIL', reason='TEST_COLLECTION_FAILED')
            return result
        if not data['node_ids'] or (collect and command['exit_code'] != 0):
            return result
        if not collect and (set(data['outcomes']) != set(data['node_ids'])
                or not any(v in ('PASS', 'FAIL', 'ERROR') for v in data['outcomes'].values())):
            return result
        result['status'] = ('PASS' if command['exit_code'] == 0 else 'FAIL' if command['exit_code'] == 1 else 'ERROR')
        result['reason'] = None if result['status'] == 'PASS' else 'TEST_FAILED' if result['status'] == 'FAIL' else 'VERIFICATION_INCOMPLETE'
    except (OSError, ValueError, ET.ParseError) as error:
        result['diagnostic'] = str(error)
        result['exception'] = exception_details(error)
    return result


def collect_tests(lease, selectors, executor, timeout_seconds=120):
    return _invoke(lease, selectors, executor, timeout_seconds, True)


def run_tests(lease, selectors, executor, timeout_seconds):
    return _invoke(lease, selectors, executor, timeout_seconds, False)

