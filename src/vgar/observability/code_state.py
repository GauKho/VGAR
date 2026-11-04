"""Which VGAR code ran (spec 2026-11-03-m3-w12-trace §4 E6): HEAD plus uncommitted files with a short hash."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

IGNORED_PREFIXES = ("results/",)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=10).stdout


def _sha12(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:  # deleted, or a directory
        return None


def code_state(root: Path) -> dict | None:
    """{'head': sha, 'dirty': [{'path', 'sha256_12'}]}; None when git or the repository is unavailable."""
    root = Path(root)
    try:
        head = _git(root, "rev-parse", "HEAD").strip()
        status = _git(root, "status", "--porcelain", "--untracked-files=all")
    except Exception:
        return None
    paths = []
    for line in status.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path and not path.startswith(IGNORED_PREFIXES):
            paths.append(path)
    return {"head": head, "dirty": [{"path": p, "sha256_12": _sha12(root / p)} for p in sorted(paths)]}


def code_label(state: dict | None) -> str:
    if not state:
        return "unknown"
    head = state["head"][:7]
    return f"{head} + dirty {len(state['dirty'])} files" if state["dirty"] else head
