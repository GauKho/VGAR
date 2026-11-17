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
# Protocol -> (freeze file, tag). "r1": the R1 retrieval held-out run (plan 2026-11-17 Task 7).
PROTOCOLS = {'repair': (FREEZE_FILE, TAG), 'r1': ('docs/protocol_freeze_r1_heldout.md', 'protocol-freeze-r1')}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout.decode('utf-8')


def _digest(data: bytes) -> str:
    return 'sha256:' + hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def _protocol(protocol: str) -> tuple[str, str]:
    if protocol not in PROTOCOLS:
        raise ValueError(f'unknown freeze protocol {protocol!r}; known: {sorted(PROTOCOLS)}')
    return PROTOCOLS[protocol]


def latest_freeze_tag(repo: Path, protocol: str = 'repair') -> str | None:
    """The protocol's tag, or its amendment with the highest number; another protocol's tags never count."""
    tag = _protocol(protocol)[1]
    pattern = re.compile(rf'^{re.escape(tag)}(?:-amend-(\d+))?$')
    ranked = []
    for name in _git(Path(repo), 'tag', '--list', f'{tag}*').split():
        match = pattern.match(name)
        if match:
            ranked.append((int(match.group(1) or 0), name))
    return max(ranked)[1] if ranked else None


def freeze_sha256(repo: Path, protocol: str = 'repair') -> str:
    freeze_file, base = _protocol(protocol)
    tag = latest_freeze_tag(repo, protocol)
    if tag is None:
        raise ValueError(f'held-out is locked: no {base} tag (sign {freeze_file} and tag it first)')
    blob = subprocess.run(['git', '-C', str(repo), 'show', f'{tag}:{freeze_file}'], check=True,
                          capture_output=True).stdout
    return _digest(blob)


def assert_heldout_unlocked(manifest: dict, *, repo: Path | None = None, command: str | None = None,
                            protocol: str | None = None) -> None:
    """Refuse unless the manifest's protocol (``freeze_protocol``, default ``repair``) is signed and unchanged.

    ``protocol`` is the one the caller runs under; a manifest of another protocol is refused, so one protocol's tag
    never opens another protocol's runner.
    """
    repo = Path(repo if repo is not None else ROOT)
    declared = manifest.get('freeze_protocol', 'repair')
    if protocol is not None and declared != protocol:
        raise ValueError(f'manifest freeze protocol {declared!r} differs from the runner protocol {protocol!r}')
    protocol = declared
    freeze_file, base = _protocol(protocol)
    tag = latest_freeze_tag(repo, protocol)
    if tag is None:
        raise ValueError(f'held-out is locked: no {base} tag (sign {freeze_file} and tag it first)')
    frozen = freeze_sha256(repo, protocol)
    path = repo / freeze_file
    if not path.is_file() or _digest(path.read_bytes()) != frozen:
        raise ValueError(f'{freeze_file} changed after {tag}; add an amendment and a new tag')
    if manifest.get('freeze_sha256') != frozen:
        raise ValueError(f'manifest freeze_sha256 differs from {tag}; regenerate the held-out manifest')
    log = repo / ACCESS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = {'time': datetime.now(timezone.utc).isoformat(), 'tag': tag, 'commit': _git(repo, 'rev-parse', 'HEAD').strip(),
             'user': getpass.getuser(), 'command': command or ' '.join(sys.argv),
             'manifest_hash': manifest.get('manifest_hash'), 'protocol': protocol}
    with log.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
