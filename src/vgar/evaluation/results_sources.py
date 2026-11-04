"""M3-W12-3 (R8): every markdown table of the Results draft names its source or says what it is waiting for.

The first non-blank line after a table must start with `Nguồn:` or `Đang chờ:`. Scripts named on a `Nguồn:` line
(`scripts/...py`) must exist in the repository; record paths outside Git are not checked.
"""
from __future__ import annotations

import re
from pathlib import Path

SOURCE, WAITING = 'Nguồn:', 'Đang chờ:'
_SCRIPT = re.compile(r'`(scripts/[\w./-]+\.py)`')


def check_sources(text: str, repo: Path) -> list[str]:
    lines = text.splitlines()
    errors, index = [], 0
    while index < len(lines):
        if not lines[index].lstrip().startswith('|'):
            index += 1
            continue
        start = index
        while index < len(lines) and lines[index].lstrip().startswith('|'):
            index += 1
        follow = index
        while follow < len(lines) and not lines[follow].strip():
            follow += 1
        line = lines[follow].strip() if follow < len(lines) else ''
        if line.startswith(SOURCE):
            for script in _SCRIPT.findall(line):
                if not (Path(repo) / script).is_file():
                    errors.append(f'line {follow + 1}: source script {script} does not exist')
        elif not line.startswith(WAITING):
            errors.append(f'line {start + 1}: table has no "{SOURCE}" or "{WAITING}" line after it')
    return errors
