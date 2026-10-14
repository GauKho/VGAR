from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('handoff_demo', ROOT / 'scripts/demo_w7_w8_handoff.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
CASES = json.loads((demo.FIXTURES / 'cases.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['task_id'])
def test_static_demo_exports_portable_context_and_expected_mapping(case, tmp_path):
    result = demo.run_case(case, demo.FIXTURES, tmp_path / 'demo', count_tokens=len, counter_label='test:characters')
    assert result['status'] == 'PASS', result
    output = Path(result['output_directory'])
    assert result['source_unchanged'] and not result['collection_verified']
    assert result['scope'] == 'm1_handoff_no_model_no_patch_no_test_execution'
    assert json.loads((output / 'result.json').read_text(encoding='utf-8')) == json.loads(json.dumps(result))
    assert (output / 'bundle/context_manifest.json').is_file()
    assert (output / 'approved-task-target.json').is_file()
    if case['task_id'] == 'missing_links':
        assert not result['graph_selectors']
        assert result['fallback_required']
        assert set(result['candidate_tests']) == set(case['failing_tests'])
        assert result['fallback_scope'] == ('tests',)


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['task_id'])
def test_demo_fixture_has_declared_failures_and_passing_regression(case, tmp_path):
    # Verify fixture design independently; this is not M2's repair pipeline.
    repository = tmp_path / 'fixture-clone'
    shutil.copytree(demo.FIXTURES / case['repository'], repository,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    junit = tmp_path / 'baseline.xml'
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', '-c', 'pytest.ini', '-q',
        '--junitxml', str(junit)], cwd=repository, env=env, capture_output=True,
        text=True, encoding='utf-8', shell=False, timeout=30)
    assert completed.returncode == 1, completed.stdout + completed.stderr
    cases = list(ET.parse(junit).getroot().iter('testcase'))
    failures = {item.attrib['name'] for item in cases if item.find('failure') is not None}
    expected = {selector.split('::')[-1] for selector in case['failing_tests']}
    assert failures == expected
    assert any(item.find('failure') is None and item.find('error') is None for item in cases)
    assert not any(item.find('error') is not None for item in cases)


def test_demo_failed_expectation_is_recorded(tmp_path):
    case = {**CASES[0], 'expected_mapping_status': {'auth.py': 'missing_mapping'}}
    result = demo.run_case(case, demo.FIXTURES, tmp_path / 'demo', count_tokens=len, counter_label='test:characters')
    assert result['status'] == 'ERROR' and result['error_stage'] == 'check_expectations'
    events = (tmp_path / 'demo/events.jsonl').read_text(encoding='utf-8')
    assert 'demo_error' in events
