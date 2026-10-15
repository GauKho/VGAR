"""Read-only pin checks before importing VGAR's shared boundary modules."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def verify_hashes(root: Path, hashes: dict[str, str]) -> None:
    for relative, expected in hashes.items():
        file = root / relative
        if not file.is_file() or file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError('Shared boundary hash mismatch: ' + relative)


def remaining_timeout(deadline=None, cap=30):
    remaining = cap if deadline is None else min(cap, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError('Global run deadline exhausted')
    return remaining


def verify_reference(pin_path: Path | None = None, *, deadline=None) -> dict:
    pin_path = pin_path or ROOT / 'config/source_pin.json'
    pin = json.loads(pin_path.read_text(encoding='utf-8'))
    root = (pin_path.parent / pin['reference_root']).resolve()
    command = ['git', '-c', f'safe.directory={root.as_posix()}', '-C', str(root)]
    head = subprocess.check_output(command + ['rev-parse', 'HEAD'], text=True, timeout=remaining_timeout(deadline)).strip()
    if head != pin['revision']:
        raise ValueError('Reference HEAD differs from approved pin')
    verify_hashes(root, pin['hashes'])
    existing = sys.modules.get('vgar')
    if existing and Path(existing.__file__).resolve() != root / 'src/vgar/__init__.py':
        raise ValueError('Another VGAR checkout was already imported')
    source = str(root / 'src')
    if source not in sys.path:
        sys.path.insert(0, source)
    module = importlib.import_module('vgar.contracts.consumer')
    if Path(module.__file__).resolve() != root / 'src/vgar/contracts/consumer.py':
        raise ValueError('Consumer import origin differs from approved reference')
    dirty = subprocess.check_output(command + ['diff', '--name-only'], text=True, timeout=remaining_timeout(deadline)).splitlines()
    return {'head': head, 'root': str(root), 'hashes': pin['hashes'], 'dirty_paths': dirty}

