import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bad_task_cli_returns_error_artifact(tmp_path):
    script = ROOT / 'scripts/run_demo.py'
    assert script.is_file(), 'Demo CLI not implemented'
    completed = subprocess.run([sys.executable, '-B', str(script), '--task', str(tmp_path / 'missing.json'),
        '--config', str(ROOT / 'config/demo.json'), '--mode', 'fake', '--output-root', str(tmp_path / 'runs')],
        capture_output=True, text=True, timeout=15)
    assert completed.returncode == 2
    path = Path(completed.stdout.strip().splitlines()[-1])
    assert path.is_file()


def test_prepare_inputs_builds_three_portable_tasks(tmp_path):
    assert (ROOT / 'scripts/prepare_inputs.py').is_file(), 'Input provisioning not implemented'
    completed = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/prepare_inputs.py'),
        '--destination', str(tmp_path / 'examples')], capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert sorted(p.stem for p in (tmp_path / 'examples/tasks').glob('*.json')) == [
        'missing_links', 'multi_file_invoice', 'single_file_login']

