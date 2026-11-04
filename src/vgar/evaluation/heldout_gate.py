"""M3-W12-2: held-out data opens only after the signed protocol freeze (spec §4.4).

Conditions: a `protocol-freeze` tag exists (or a later `protocol-freeze-amend-<n>`); the freeze document in the working
tree equals its content at that tag; the held-out manifest carries the same `freeze_sha256`. Every opening is logged.
Line endings are normalised before hashing, so a CRLF checkout of an unchanged file still matches the tag.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FREEZE_FILE = 'docs/protocol_freeze_heldout.md'
TAG = 'protocol-freeze'
ACCESS_LOG = 'results/heldout_access.log'
_TAG = re.compile(r'^protocol-freeze(?:-amend-(\d+))?$')


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout.decode('utf-8')


def _digest(data: bytes) -> str:
    return 'sha256:' + hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def latest_freeze_tag(repo: Path) -> str | None:
    """`protocol-freeze`, or the amendment with the highest number."""
    ranked = []
    for name in _git(Path(repo), 'tag', '--list', f'{TAG}*').split():
        match = _TAG.match(name)
        if match:
            ranked.append((int(match.group(1) or 0), name))
    return max(ranked)[1] if ranked else None


def freeze_sha256(repo: Path) -> str:
    tag = latest_freeze_tag(repo)
    if tag is None:
        raise ValueError(f'held-out is locked: no {TAG} tag (sign {FREEZE_FILE} and tag it first)')
    blob = subprocess.run(['git', '-C', str(repo), 'show', f'{tag}:{FREEZE_FILE}'], check=True,
                          capture_output=True).stdout
    return _digest(blob)


def assert_heldout_unlocked(manifest: dict, *, repo: Path | None = None, command: str | None = None) -> None:
    repo = Path(repo if repo is not None else ROOT)
    tag = latest_freeze_tag(repo)
    if tag is None:
        raise ValueError(f'held-out is locked: no {TAG} tag (sign {FREEZE_FILE} and tag it first)')
    frozen = freeze_sha256(repo)
    path = repo / FREEZE_FILE
    if not path.is_file() or _digest(path.read_bytes()) != frozen:
        raise ValueError(f'{FREEZE_FILE} changed after {tag}; add an amendment and a new tag')
    if manifest.get('freeze_sha256') != frozen:
        raise ValueError(f'manifest freeze_sha256 differs from {tag}; regenerate the held-out manifest')
    log = repo / ACCESS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = {'time': datetime.now(timezone.utc).isoformat(), 'tag': tag, 'commit': _git(repo, 'rev-parse', 'HEAD').strip(),
             'user': getpass.getuser(), 'command': command or ' '.join(sys.argv),
             'manifest_hash': manifest.get('manifest_hash')}
    with log.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
