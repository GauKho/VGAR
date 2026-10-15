"""Behavioral tests for the root delivery runner, no model generation."""
from pathlib import Path
import json
import subprocess
import shutil
import runpy
import importlib.metadata
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT/'test_abc_v11_r002.ps1'


def run_ps(*args):
    return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SCRIPT),*args],
        cwd=ROOT, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=120)


def test_saved_mode_audits_all_cases_and_prints_all_artifact_families(tmp_path):
    assert SCRIPT.is_file(), 'PowerShell runner has not been implemented'
    output = ROOT/'results/delivery-tests'/(tmp_path.parent.name+'-'+tmp_path.name)
    result = run_ps('-Mode','ReadSaved','-OutputRoot',str(output))
    assert result.returncode == 0, result.stdout[-3000:]+result.stderr[-3000:]
    summary = json.loads((output/'summary.json').read_text(encoding='utf-8-sig'))
    assert summary['status'] == 'PASS' and summary['mode'] == 'ReadSaved'
    assert summary['skip_self_tests'] is False
    assert [a['task_id'] for a in summary['cases']] == ['single_file_login','multi_file_invoice','missing_links']
    assert all(a['status'] == 'PASS' for a in summary['cases'])
    transcript = (output/'all_logs.txt').read_text(encoding='utf-8-sig')
    for family in ('CANONICAL','PROMPT','RAW OUTPUT','CANDIDATE','APPLIED','EVIDENCE BUNDLE','WORKER JSON'):
        assert family in transcript
    assert '3/3' in transcript


def test_existing_output_is_never_overwritten(tmp_path):
    assert SCRIPT.is_file(), 'PowerShell runner has not been implemented'
    output = ROOT/'results/delivery-tests'/(tmp_path.parent.name+'-'+tmp_path.name)
    output.mkdir(parents=True)
    marker = output/'untouched.txt'
    marker.write_text('keep', encoding='utf-8')
    result = run_ps('-Mode','ReadSaved','-OutputRoot',str(output))
    assert result.returncode != 0 and marker.read_text(encoding='utf-8') == 'keep'
    assert not (output/'summary.json').exists()


def test_output_outside_results_is_rejected_before_any_mutation(tmp_path):
    assert SCRIPT.is_file(), 'PowerShell runner has not been implemented'
    output = ROOT/'examples'/'must-not-be-created-by-runner'
    assert not output.exists()
    result = run_ps('-Mode','Check','-OutputRoot',str(output))
    assert result.returncode != 0 and not output.exists()


def test_check_mode_never_launches_real_or_creates_case_directories(tmp_path):
    assert SCRIPT.is_file(), 'PowerShell runner has not been implemented'
    output = ROOT/'results/delivery-tests'/(tmp_path.parent.name+'-'+tmp_path.name)
    result = run_ps('-Mode','Check','-OutputRoot',str(output))
    assert result.returncode == 0, result.stdout[-3000:]+result.stderr[-3000:]
    summary = json.loads((output/'summary.json').read_text(encoding='utf-8-sig'))
    assert summary['status'] == 'PASS' and summary['mode'] == 'Check'
    assert not any((output/x).exists() for x in ('A','B','C'))


def test_optimized_python_is_rejected_before_acceptance(tmp_path, monkeypatch):
    output = ROOT/'results/delivery-tests'/(tmp_path.parent.name+'-'+tmp_path.name)
    monkeypatch.setenv('PYTHONOPTIMIZE','1')
    result = run_ps('-Mode','ReadSaved','-OutputRoot',str(output))
    assert result.returncode != 0, 'Optimized Python must not disable acceptance checks'
    assert not (output/'summary.json').exists() or json.loads((output/'summary.json').read_text(encoding='utf-8-sig'))['status'] != 'PASS'


def test_core_pin_mismatch_is_not_readiness_pass(tmp_path, monkeypatch):
    helper = SCRIPT.read_text(encoding='utf-8').split("$helper = @'\n",1)[1].split("\n'@",1)[0]
    path = tmp_path/'helper.py'
    path.write_text(helper,encoding='utf-8')
    actual = importlib.metadata.version
    monkeypatch.setattr(importlib.metadata,'version',lambda name:'8.4.3' if name=='pytest' else actual(name))
    monkeypatch.setattr(sys,'argv',[str(path),'preflight',str(ROOT),str(tmp_path),'ReadSaved'])
    with pytest.raises((AssertionError,RuntimeError),match='[Cc]ore|[Pp]in|version'):
        runpy.run_path(str(path),run_name='__main__')
    assert not (tmp_path/'preflight.json').exists()


def test_missing_prompt_does_not_hide_remaining_saved_logs(tmp_path):
    output = ROOT/'results/delivery-tests'/(tmp_path.parent.name+'-'+tmp_path.name)
    saved = tmp_path/'saved'
    shutil.copytree(ROOT/'results/final_acceptance/2026-10-15-v11-r002/A',saved/'A')
    prompt = next((saved/'A').glob('*/prompt.txt'))
    prompt.unlink()  # Only a test-owned copy, never original evidence.
    result = run_ps('-Mode','ReadSaved','-SavedRoot',str(saved),'-OutputRoot',str(output))
    assert result.returncode != 0
    log = (output/'all_logs.txt').read_text(encoding='utf-8-sig')
    assert 'RAW OUTPUT' in log and 'WORKER JSON' in log
    assert json.loads((output/'summary.json').read_text(encoding='utf-8-sig'))['status']=='ERROR'


def test_failed_selftests_print_real_pytest_diagnostics_and_never_generate(tmp_path, monkeypatch):
    output = ROOT/'results/delivery-tests'/(tmp_path.parent.name+'-'+tmp_path.name)
    monkeypatch.setenv('PYTEST_ADDOPTS','--delivery-invalid-option')
    result = run_ps('-Mode','Run','-OutputRoot',str(output))
    assert result.returncode != 0
    log = (output/'all_logs.txt').read_text(encoding='utf-8-sig')
    assert 'unrecognized arguments: --delivery-invalid-option' in log
    assert not any((output/x).exists() for x in ('A','B','C'))
