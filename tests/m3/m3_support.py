"""Shared helpers for M3 runner tests (imported by name, like tests/m2/w78/w78_support.py)."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ROOT/'configs/m2/variants'
ARMS = {'A0': 'bm25', 'A1': 'graph', 'A2': 'graph'}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')
    return path


def variants(arms=ARMS):
    return [{'path': str(VARIANTS/f'{v}.json'), 'arm': arm} for v, arm in arms.items()]


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
