"""Receipt for bounded final pytest without changing the W3-4 workspace hasher."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, record_command, source_fingerprint, utc_now, write_json

selectors = ['tests/m2/test_context_gold_handoff.py', 'tests/m2/test_graph_arm.py',
    'tests/m2/test_retrieval_eval_graph.py', 'tests/m2/test_retrieval_scoring.py',
    'tests/m2/test_retrieval_evaluation.py', 'tests/m2/test_dataset_split.py', 'tests/test_m1_handoff.py']
folder, interrupted = new_run(ROOT/'artifacts/m2/w5-w6/commands', 'm2-w56-recorder-interrupted')
interrupted.update(status='INTERRUPTED', complete=False, started_utc='2026-10-13T12:53:08.6742836Z',
    ended_utc=utc_now(), exit_code=None, source=source_fingerprint(ROOT),
    command_argv=[sys.executable, '-B', 'scripts/record_m2_test.py', *selectors,
                  '--task-id', 'm2-w56-final-regression', '--timeout-seconds', '300'],
    stopped_launcher_pid=22168, terminated_owned_child_pid=24956,
    process_note='Child exited with the launcher job; second explicit Stop was not issued after process identity became unavailable.',
    reason='Recorder exceeded 5min without terminal result; workspace fingerprint includes data/results/.venv-m2-w5-w6. No pytest outcome assumed.',
    scope='Stopped only the verified owned launcher; child also exited. No source changed.')
write_json(folder/'result.json', interrupted)
print('interruption:', folder/'result.json', flush=True)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONPATH'] = str(ROOT/'src')
path, result = record_command([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',*selectors],
    ROOT, ROOT/'artifacts/m2/w5-w6/commands', timeout=300, kind='m2-w56-final-targeted-pytest')
assert result['source']['digest'] == source_fingerprint(ROOT)['digest'], 'Code changed during test'
print('regression:', path)
print(result['status'], result['exit_code'])
print(result['stdout'])
print(result['stderr'])
raise SystemExit(result['exit_code'])
