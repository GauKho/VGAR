"""Capture actual pytest collection/outcomes alongside raw command/JUnit evidence."""
import json
import sys
import uuid
import xml.etree.ElementTree as ET

from .contracts import safe_selector


def _invoke(lease, selectors, executor, timeout_seconds, collect):
    if not selectors:
        raise ValueError('No selectors')
    selected = tuple(safe_selector(s) for s in selectors)
    directory = lease.private / 'reports' / uuid.uuid4().hex
    directory.mkdir(parents=True)
    report, junit = directory / 'nodeids.json', directory / 'junit.xml'
    args = (sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '-p', 'vgar_m2_w78.pytest_plugin', '--m2-report-json=' + str(report),
            '--junitxml=' + str(junit), *(('--collect-only',) if collect else ()), *selected)
    command = executor.run(args, lease.path, timeout_seconds)
    result = dict(command=command, status='ERROR', reason='VERIFICATION_INCOMPLETE',
                  node_ids=[], outcomes={}, durations_ms={}, junit_xml=None)
    try:
        data = json.loads(report.read_text(encoding='utf-8'))
        xml = junit.read_text(encoding='utf-8')
        ET.fromstring(xml)
        result.update(data, command=command, junit_xml=xml)
        if (not command['complete'] or not data['complete'] or not data['node_ids']
                or data['collection_errors'] or (collect and command['exit_code'] != 0)):
            return result
        if not collect and (set(data['outcomes']) != set(data['node_ids'])
                or not any(v in ('PASS', 'FAIL', 'ERROR') for v in data['outcomes'].values())):
            return result
        result['status'] = ('PASS' if command['exit_code'] == 0 else 'FAIL' if command['exit_code'] == 1 else 'ERROR')
        result['reason'] = None if result['status'] == 'PASS' else 'TEST_FAILED' if result['status'] == 'FAIL' else 'VERIFICATION_INCOMPLETE'
    except (OSError, ValueError, ET.ParseError) as error:
        result['diagnostic'] = str(error)
    return result


def collect_tests(lease, selectors, executor, timeout_seconds=120):
    return _invoke(lease, selectors, executor, timeout_seconds, True)


def run_tests(lease, selectors, executor, timeout_seconds):
    return _invoke(lease, selectors, executor, timeout_seconds, False)

