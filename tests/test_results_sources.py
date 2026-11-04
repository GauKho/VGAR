"""M3-W12-3: every table in the Results draft is followed by a `Nguồn:` (existing script) or `Đang chờ:` line."""
import subprocess
import sys
from pathlib import Path

from vgar.evaluation.results_sources import check_sources

ROOT = Path(__file__).resolve().parents[1]
TABLE = '| a | b |\n|---|---|\n| 1 | 2 |\n'


def test_table_with_source_passes():
    text = TABLE + '\nNguồn: `scripts/bench_incremental.py` · `results/m1/w12/u1/x/u1.json` · abc123\n'
    assert check_sources(text, ROOT) == []


def test_table_waiting_passes():
    assert check_sources(TABLE + 'Đang chờ: H5 (M1)\n', ROOT) == []


def test_table_without_source_fails():
    errors = check_sources('# R1\n\n' + TABLE + '\nMột đoạn văn.\n', ROOT)
    assert len(errors) == 1 and 'line 3' in errors[0]


def test_last_table_without_source_fails():
    assert len(check_sources(TABLE + '\nNguồn: `scripts/bench_incremental.py`\n\n' + TABLE, ROOT)) == 1


def test_missing_script_fails():
    errors = check_sources(TABLE + 'Nguồn: `scripts/nope.py`\n', ROOT)
    assert len(errors) == 1 and 'scripts/nope.py' in errors[0]


def test_results_draft_passes():
    assert check_sources((ROOT / 'docs/paper/results_draft_v1.md').read_text(encoding='utf-8'), ROOT) == []


def test_cli_exit_code(tmp_path):
    bad = tmp_path / 'bad.md'
    bad.write_text(TABLE, encoding='utf-8')
    process = subprocess.run([sys.executable, 'scripts/check_results_sources.py', str(bad)], cwd=ROOT,
                             capture_output=True, text=True)
    assert process.returncode == 1 and 'line 1' in process.stdout
    assert subprocess.run([sys.executable, 'scripts/check_results_sources.py'], cwd=ROOT).returncode == 0
