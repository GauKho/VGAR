"""Bounded, append-only evidence for the M1 handoff integration (no model runs)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
AUDIT = Path(__file__).resolve().parent
UPSTREAM = ROOT.parent / '.integration-m1-w7-w8-20261014'
BEFORE = '73814b8f89666c71b1911e42e98b8ecc7f6e3e99'
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import record_command, write_json


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ['git', '-c', f'safe.directory={root.as_posix()}', '-C', str(root), *args],
        encoding='utf-8', errors='strict').strip()


def digest(path: Path) -> str:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def changed_paths() -> list[str]:
    return git(UPSTREAM, 'diff', '--name-only', BEFORE, 'HEAD').splitlines()


def snapshot() -> None:
    target = AUDIT / 'before.json'
    if target.exists():
        raise RuntimeError('Before snapshot already exists; do not overwrite it')
    paths = git(ROOT, 'ls-files').splitlines()
    untracked = git(ROOT, 'ls-files', '--others', '--exclude-standard').splitlines()
    protected = [p for p in untracked if not p.startswith('docs/audit/')]
    write_json(target, {
        'head': git(ROOT, 'rev-parse', 'HEAD'),
        'branch': git(ROOT, 'branch', '--show-current'),
        'upstream_head': git(UPSTREAM, 'rev-parse', 'HEAD'),
        'status': git(ROOT, 'status', '--short', '--branch'),
        'incoming_paths': changed_paths(),
        'tracked_hashes': {p: digest(ROOT / p) for p in paths if (ROOT / p).is_file()},
        'untracked_hashes': {p: digest(ROOT / p) for p in protected if (ROOT / p).is_file()},
        'interpreters_reused_only': sys.executable,
    })
    for relative in ('src/vgar/evaluation/retrieval/compare.py',
                     'src/vgar/evaluation/retrieval/scoring.py',
                     'artifacts/sample_graph.db', 'PROGRESS.md', 'Task Status.md'):
        path = ROOT / relative
        if path.is_file():
            backup = AUDIT / 'originals' / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
    print(target, flush=True)


def verify_preservation() -> dict:
    saved = json.loads((AUDIT / 'before.json').read_text(encoding='utf-8'))
    incoming = saved['incoming_paths']
    mismatch = [p for p in incoming if digest(ROOT / p) != digest(UPSTREAM / p)]
    unrelated = [p for p, h in saved['tracked_hashes'].items()
                 if p not in incoming and (not (ROOT / p).is_file() or digest(ROOT / p) != h)]
    lost = [p for p, h in saved['untracked_hashes'].items()
            if p != 'PROGRESS.md' and (not (ROOT / p).is_file() or digest(ROOT / p) != h)]
    report = {'incoming_files': len(incoming), 'incoming_mismatch': mismatch,
              'unrelated_tracked_changes': unrelated, 'lost_or_changed_untracked': lost,
              'head': git(ROOT, 'rev-parse', 'HEAD'),
              'status': 'PASS' if not mismatch and not unrelated and not lost else 'FAIL'}
    write_json(AUDIT / 'preservation.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def run(command: list[str], kind: str, timeout: int = 300) -> int:
    os.environ.update(PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1',
                      PYTHONUTF8='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                      GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='safe.directory',
                      GIT_CONFIG_VALUE_0=ROOT.as_posix())
    path, result = record_command(command, ROOT, AUDIT / 'commands', timeout=timeout, kind=kind)
    print('Evidence:', path, flush=True)
    print(result['stdout'], flush=True)
    print(result['stderr'], flush=True)
    print('Exit:', result['exit_code'], 'Duration:', result['duration_seconds'], flush=True)
    return result['exit_code']


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['snapshot', 'baseline', 'm1', 'full', 'demo', 'package', 'preservation'])
    phase = parser.parse_args().phase
    if phase == 'snapshot':
        snapshot()
        return 0
    if phase == 'preservation':
        return 0 if verify_preservation()['status'] == 'PASS' else 1
    prefix = [sys.executable, '-B']
    if phase == 'baseline':
        return run(prefix + ['-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            'tests/test_hf_model.py', 'tests/test_m1_handoff.py', 'tests/test_w7_w8_m1.py',
            'tests/m2/test_context_gold_handoff.py',
            '--junitxml', str(AUDIT / 'baseline.xml')], 'baseline-existing-behavior')
    if phase == 'm1':
        return run(prefix + ['scripts/run_m1_tests.py', '-p', 'no:cacheprovider',
            '--junitxml', str(AUDIT / 'm1.xml')], 'integrated-m1-suite')
    if phase == 'full':
        return run(prefix + ['-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '--junitxml', str(AUDIT / 'integrated-full.xml')], 'integrated-full-suite')
    if phase == 'demo':
        return run(prefix + ['scripts/demo_w7_w8_handoff.py', '--tokenizer-manifest',
            str(ROOT / 'artifacts/m2/w5-w6/tokenizer_manifest.json')], 'real-local-tokenizer-three-handoff-demos')
    return run(prefix + ['scripts/package_m1.py', '--list'], 'integration-package-completeness')


if __name__ == '__main__':
    raise SystemExit(main())
