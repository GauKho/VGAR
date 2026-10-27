"""Pinned mypy/Ruff bundle copied into SWE-bench containers, whose images ship neither tool.

mypy 2.4 needs Python >= 3.10 and compiled dependencies, so it runs on a standalone
Python from the bundle and reads the testbed packages through --python-executable.
Its interpreter probe cannot run on testbeds older than the lock minimum; there mypy
is UNAVAILABLE, decided from the pinned profile before any generation.
"""
import json
import os
from pathlib import Path

from vgar.repair.config import CONFIG_DIR

LOCK_PATH = CONFIG_DIR / 'static/tools.lock.json'
CONTAINER_ROOT = '/vgar/tools'


def lock():
    return json.loads(LOCK_PATH.read_text(encoding='utf-8'))


def load_bundle():
    """Host bundle root; a missing bundle is an OSError so static evidence records ERROR."""
    root = Path(os.environ.get('VGAR_STATIC_TOOLS') or Path.home() / '.cache/vgar/static-tools')
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    expected = lock()
    if any(manifest.get(key) != expected[key] for key in ('python', 'mypy', 'ruff')):
        raise ValueError('Static tool bundle differs from tools.lock.json: ' + str(root))
    return root


def mypy_unavailable_reason(testbed_python):
    minimum = tuple(int(p) for p in lock()['mypy_min_testbed_python'].split('.'))
    if tuple(int(p) for p in testbed_python.split('.')[:2]) < minimum:
        return 'TESTBED_PYTHON_UNSUPPORTED'
    return None
