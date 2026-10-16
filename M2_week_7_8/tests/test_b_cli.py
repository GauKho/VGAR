import json
import subprocess
import sys

from conftest import ROOT
from test_bootstrap import api


def test_b_cli_status_is_read_only_and_never_initializes(tmp_path):
    folder = tmp_path/'absent-experiment'
    result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/run_b_experiment.py'),
        '--status', '--campaign', str(folder)], text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['reason'] == 'CAMPAIGN_NOT_CREATED'
    assert not folder.exists()


def test_b_cli_refuses_external_write_before_freezing_or_model(tmp_path):
    folder = tmp_path/'external'
    result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/run_b_experiment.py'),
        '--init', '--campaign', str(folder)], text=True, capture_output=True, timeout=20)
    assert result.returncode == 2
    assert 'results/b_repair' in result.stderr and not folder.exists()


def test_freeze_is_b_only_and_preserves_parser_tests_and_history():
    value = api('b_inputs').freeze_b_inputs()
    assert value['task_id'] == value['task']['task_id'] == 'multi_file_invoice'
    assert value['model']['do_sample'] is False and value['policy']['input_cap'] == 6000
    protected = value['files']
    assert str(ROOT/'src/vgar_m2_w78/patch.py') in protected
    assert str(ROOT/'src/vgar_m2_w78/verification.py') in protected
    assert str(ROOT/'examples/tasks/multi_file_invoice.json') in protected
    assert str(ROOT/'results/adaptive_acceptance/2026-10-15-v5-plus/campaign.json') in protected
    # Old worker outputs are historical evidence too; only this new experiment
    # must stay outside the immutable protected-input set.
    assert not any('/results/b_repair/' in p.replace('\\','/') for p in protected)
