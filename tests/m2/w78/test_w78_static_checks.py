"""Catch type/lint errors passing, repository config weakening checks, and cache left behind."""
import pytest

from vgar.repair.contracts import RepairPolicy
from vgar.repair.executor import NativeExecutor
from vgar.repair.static_checks import run_static_checks
from vgar.repair.workspace import create_workspace


def checks(tmp_path, files):
    source = tmp_path / 'source'
    (source / 'pkg').mkdir(parents=True)
    for name, text in files.items():
        (source / name).write_text(text, encoding='utf-8')
    with create_workspace(source, tmp_path / 'temp') as lease:
        before = sorted(p.relative_to(lease.path).as_posix() for p in lease.path.rglob('*'))
        result = run_static_checks(lease, ('pkg/a.py',), RepairPolicy(), NativeExecutor(lease))
        after = sorted(p.relative_to(lease.path).as_posix() for p in lease.path.rglob('*'))
    return result, before, after


def test_clean_file_passes_and_leaves_no_cache(tmp_path):
    result, before, after = checks(tmp_path, {'pkg/a.py': 'def f(x: int) -> int:\n    return x\n'})
    assert [result[k]['status'] for k in ('syntax', 'mypy', 'ruff')] == ['PASS', 'PASS', 'PASS']
    assert after == before


def test_type_error_fails_mypy(tmp_path):
    result, _, _ = checks(tmp_path, {'pkg/a.py': "def f(x: int) -> int:\n    return 'no'\n"})
    assert result['mypy']['status'] == 'FAIL'
    assert 'pkg/a.py' in result['mypy']['stdout'].replace('\\', '/')


def test_undefined_name_fails_ruff(tmp_path):
    result, _, _ = checks(tmp_path, {'pkg/a.py': 'def f(x: int) -> int:\n    return y\n'})
    assert result['ruff']['status'] == 'FAIL'
    assert 'F821' in result['ruff']['stdout']


def test_repository_config_cannot_weaken_checks(tmp_path):
    result, _, _ = checks(tmp_path, {'pkg/a.py': 'def f(x: int) -> int:\n    return y\n',
                                     'ruff.toml': "[lint]\nignore = ['F']\n",
                                     'mypy.ini': '[mypy]\nignore_errors = True\n'})
    assert result['ruff']['status'] == 'FAIL'
    assert result['mypy']['status'] == 'FAIL'


def test_syntax_error_is_reported(tmp_path):
    result, _, _ = checks(tmp_path, {'pkg/a.py': 'def f(:\n'})
    assert result['syntax']['status'] == 'FAIL'


def test_no_targets_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='approved source targets'):
        run_static_checks(None, (), RepairPolicy(), None)
