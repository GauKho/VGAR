"""Syntax, mypy and Ruff evidence with tool-owned configuration the target repository cannot weaken."""
import ast
import sys

from vgar.repair.config import CONFIG_DIR
from vgar.repair.contracts import safe_path
from vgar.repair.evidence import digest
from vgar.repair.diagnostics import exception_details


def run_static_checks(lease, targets, policy, executor):
    targets = tuple(safe_path(t) for t in targets)
    if not targets:
        raise ValueError('Static checks need approved source targets')
    result = {'syntax': {'status': 'PASS'}}
    try:
        for target in targets:
            ast.parse((lease.path / target).read_bytes(), filename=target)
    except (OSError, SyntaxError) as error:
        result['syntax'] = dict(status='FAIL', reason=str(error), exception=exception_details(error))
    configs = {'mypy': CONFIG_DIR / 'static/mypy.ini', 'ruff': CONFIG_DIR / 'static/ruff.toml'}
    before = {key: digest(path.read_bytes()) for key, path in configs.items()}
    for name, config in configs.items():
        args = ((sys.executable, '-m', 'mypy', '--config-file', str(config), '--no-incremental',
                 '--cache-dir', str(lease.private / 'mypy-cache'), *targets) if name == 'mypy' else
                (sys.executable, '-m', 'ruff', 'check', '--config', str(config), '--no-cache', *targets))
        result[name] = executor.run(args, lease.path, policy.command_timeout)
    result['config_hashes'] = before
    if before != {key: digest(path.read_bytes()) for key, path in configs.items()}:
        raise ValueError('Static configuration changed during checks')
    return result

