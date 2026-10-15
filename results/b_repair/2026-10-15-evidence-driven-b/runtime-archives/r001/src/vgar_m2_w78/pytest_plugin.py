"""Tool-owned exact node ID/outcome reporter; never changes target tests."""
import json
from pathlib import Path

STATE = {'node_ids': [], 'outcomes': {}, 'durations_ms': {}, 'collection_errors': [], 'complete': False}


def pytest_addoption(parser):
    parser.addoption('--m2-report-json', default=None)


def pytest_collection_finish(session):
    STATE['node_ids'] = [item.nodeid for item in session.items]


def pytest_collectreport(report):
    if report.failed:
        STATE['collection_errors'].append(str(report.longrepr))


def pytest_runtest_logreport(report):
    previous = STATE['outcomes'].get(report.nodeid)
    status = None
    if report.failed:
        status = 'FAIL' if report.when == 'call' else 'ERROR'
    elif report.skipped:
        status = 'XFAIL' if hasattr(report, 'wasxfail') else 'SKIP'
    elif report.when == 'call' and report.passed:
        status = 'XPASS' if hasattr(report, 'wasxfail') else 'PASS'
    if status and (previous not in ('FAIL', 'ERROR') or status == 'ERROR'):
        STATE['outcomes'][report.nodeid] = status
    STATE['durations_ms'][report.nodeid] = STATE['durations_ms'].get(report.nodeid, 0) + round(report.duration * 1000)


def pytest_sessionfinish(session, exitstatus):
    output = session.config.getoption('--m2-report-json')
    if output:
        STATE.update(complete=True, exit_code=int(exitstatus))
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding='utf-8')

