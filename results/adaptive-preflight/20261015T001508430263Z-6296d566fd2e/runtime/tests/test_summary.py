import json
from pathlib import Path
import subprocess
import sys


def test_summary_separates_fake_real_and_prompt_versions(tmp_path):
    for name, mode, version, status in [('a','real','m2-w78-v1','FAIL'),
                                      ('b','real','m2-w78-v2','FAIL'), ('c','fake','m2-w78-v2','PASS')]:
        folder = tmp_path / name
        folder.mkdir()
        (folder/'run_record.json').write_text(json.dumps(dict(mode=mode, policy={'prompt_version':version},
            status=status, complete=True, stages={}, task_id='test')), encoding='utf-8')
    script = Path(__file__).resolve().parents[1] / 'scripts/summarize_runs.py'
    result = subprocess.run([sys.executable, str(script), '--root', str(tmp_path), '--mode', 'real'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report['groups']['m2-w78-v1']['statuses'] == {'FAIL':1}
    assert report['groups']['m2-w78-v2']['attempts'] == 1
