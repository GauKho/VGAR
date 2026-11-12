"""W10 locked dev manifest and the pinned SWE-bench (repo, version) -> test command table."""
import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _dev_ids(count):
    from vgar.evaluation.retrieval.dataset import split_of
    ids, n = [], 0
    while len(ids) < count:
        candidate = f'fixture__project-{n}'
        if split_of(candidate) == 'dev':
            ids.append(candidate)
        n += 1
    return ids


def _rows(ids, version='3.0'):
    return [{'instance_id': i, 'repo': 'django/django', 'base_commit': 'a'*40, 'problem_statement': 'broken',
             'version': version, 'patch': 'GOLD', 'FAIL_TO_PASS': ['SECRET']} for i in ids]


def test_pilot_manifest_hash_unchanged():
    from vgar.evaluation.retrieval.pilot_manifest import validate_manifest
    manifest = json.loads((ROOT/'configs/m1/w9_pilot_manifest.json').read_text(encoding='utf-8'))
    validate_manifest(manifest, expected_hash='sha256:98984466d59da122d4798d436359275030f79e1190936d7d9a6f9a0a58458425')


def test_w10_manifest_keeps_version_and_no_gold():
    from vgar.evaluation.retrieval.pilot_manifest import W10_SELECTION, make_manifest, validate_manifest
    manifest = make_manifest(_rows(_dev_ids(3)), parquet_hash='sha256:'+'a'*64, selection_policy=W10_SELECTION)
    for task in manifest['tasks']:
        assert set(task) == {'instance_id', 'repo', 'base_commit', 'problem_statement', 'query_hash', 'split', 'version'}
    validate_manifest(manifest, expected_ids=None)
    with pytest.raises(ValueError, match='approved five tasks'):
        validate_manifest(manifest)
    bad = copy.deepcopy(manifest)
    bad['tasks'][0]['version'] = '9.9'
    with pytest.raises(ValueError):
        validate_manifest(bad, expected_ids=None)


def _table():
    from vgar.evaluation.harness.test_cmds import build_table
    specs = {
        'django/django': {'1.11': {'test_cmd': './tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1'},
                          '1.9': {'test_cmd': './tests/runtests.py --verbosity 2'}},
        'sympy/sympy': {'1.9': {'test_cmd': "PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' bin/test -C --verbose"}},
        'sphinx-doc/sphinx': {'5.0': {'test_cmd': 'tox --current-env -epy39 -v --'}},
        'pydata/xarray': {'0.12': {'test_cmd': 'pytest -rA'}},
        'odd/repo': {'1.0': {'test_cmd': 'make check'}},
    }
    return build_table(specs, swebench_version='4.1.0')


def test_table_classifies_runners_from_test_cmd():
    from vgar.evaluation.harness.test_cmds import lookup
    table = _table()
    django = lookup(table, 'django/django', '1.11')
    assert django['runner'] == 'django_runtests'
    assert django['argv'] == ['tests/runtests.py', '--verbosity', '2', '--settings=test_sqlite', '--parallel', '1']
    assert django['env'] == {}
    assert lookup(table, 'django/django', '1.9')['argv'] == ['tests/runtests.py', '--verbosity', '2']
    sympy = lookup(table, 'sympy/sympy', '1.9')
    assert sympy['runner'] == 'sympy_bin_test'
    assert sympy['env'] == {'PYTHONWARNINGS': 'ignore::UserWarning,ignore::SyntaxWarning'}
    assert sympy['argv'] == ['bin/test', '-C', '--verbose']
    sphinx = lookup(table, 'sphinx-doc/sphinx', '5.0')
    assert sphinx['runner'] == 'pytest' and 'equivalence' in sphinx
    assert lookup(table, 'pydata/xarray', '0.12')['runner'] == 'pytest'


def test_lookup_refuses_unknown_or_unsupported():
    from vgar.evaluation.harness.test_cmds import lookup
    table = _table()
    with pytest.raises(ValueError):
        lookup(table, 'x/y', '1.0')
    with pytest.raises(ValueError):
        lookup(table, 'django/django', '0.1')
    with pytest.raises(ValueError, match='unsupported'):
        lookup(table, 'odd/repo', '1.0')


def test_committed_table_covers_dev_repos():
    from vgar.evaluation.harness.test_cmds import load_test_cmds, lookup
    table = load_test_cmds()
    assert table['swebench_version'] == '4.1.0'
    assert lookup(table, 'django/django', '1.11')['runner'] == 'django_runtests'
    assert lookup(table, 'sympy/sympy', '1.9')['runner'] == 'sympy_bin_test'


def _table_with(version):
    from vgar.evaluation.harness.test_cmds import build_table
    return build_table({'django/django': {version: {'test_cmd': './tests/runtests.py --verbosity 2'}}},
                       swebench_version='4.1.0')
