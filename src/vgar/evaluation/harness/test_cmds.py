"""Pinned SWE-bench (repo, version) -> test command table; never guess a runner for an unknown pair."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TABLE_PATH = ROOT/'configs/m1/swebench_410_test_cmds.json'
SPHINX_TOX = 'tox --current-env -epy39 -v --'


def classify(test_cmd) -> dict:
    """Split one upstream test_cmd into runner kind, leading KEY=VALUE env and argv."""
    if not test_cmd:
        return {'runner': 'unsupported', 'env': {}, 'argv': [], 'source': None}
    if isinstance(test_cmd, list):
        if len(test_cmd) != 1:
            return {'runner': 'unsupported', 'env': {}, 'argv': [], 'source': json.dumps(test_cmd)}
        test_cmd = test_cmd[0]
    tokens, env = shlex.split(test_cmd), {}
    while tokens and re.fullmatch(r'[A-Z_][A-Z0-9_]*=.*', tokens[0]):
        key, value = tokens.pop(0).split('=', 1)
        env[key] = value
    argv = [tokens[0].removeprefix('./')] + tokens[1:] if tokens else []
    entry = {'env': env, 'argv': argv, 'source': test_cmd}
    if argv[:1] == ['pytest']:
        return {'runner': 'pytest', **entry}
    if test_cmd.strip() == SPHINX_TOX:
        return {'runner': 'pytest', 'equivalence': 'tox --current-env runs pytest', **entry}
    if argv[:1] == ['tests/runtests.py']:
        return {'runner': 'django_runtests', **entry}
    if argv[:1] == ['bin/test']:
        return {'runner': 'sympy_bin_test', **entry}
    return {'runner': 'unsupported', **entry}


def build_table(specs: dict, *, swebench_version: str) -> dict:
    return {'swebench_version': swebench_version,
            'repos': {repo: {version: classify(spec.get('test_cmd')) for version, spec in sorted(versions.items())}
                      for repo, versions in sorted(specs.items())}}


def load_test_cmds(path: Path = TABLE_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lookup(table: dict, repo: str, version: str) -> dict:
    entry = table['repos'].get(repo, {}).get(version)
    if entry is None:
        raise ValueError(f'No pinned SWE-bench {table["swebench_version"]} test command for {repo} {version}')
    if entry['runner'] == 'unsupported':
        raise ValueError(f'unsupported test command for {repo} {version}: {entry["source"]}')
    return entry
