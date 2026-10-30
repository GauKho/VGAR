"""Diff normalization (spec §5.4): relocate exact unique context, drop no-op hunks, never rescue fabricated context."""
from pathlib import Path

import pytest

from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT/'tests/fixtures/m2/w10_normalize'
# Spec §1 table: what the 27/10 offline spike observed on the six pilot outputs.
EXPECTED = {'matplotlib_A0': 'OK', 'pylint_A1': 'OK',
            'matplotlib_A1': 'NO_OP', 'xarray_A1': 'NO_OP',
            'xarray_A0': 'CONTEXT_NOT_FOUND', 'pylint_A0': 'CONTEXT_NOT_FOUND'}


def normalize(raw, root, policy):
    from vgar.repair.patch_normalize import normalize_unified_diff
    return normalize_unified_diff(raw, root, policy)


def NormalizationError():
    from vgar.repair.patch_normalize import NormalizationError
    return NormalizationError


def policy_for(root, protected=('tests',)):
    files = tuple(sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()))
    return PatchPolicy(allowed_paths=files, protected_paths=protected)


@pytest.mark.parametrize('case,expected', sorted(EXPECTED.items()))
def test_pilot_diffs(case, expected):
    root = CASES/case/'src'
    raw = (CASES/case/'raw.diff').read_text(encoding='utf-8')
    policy = policy_for(root)
    if expected == 'OK':
        result = normalize(raw, root, policy)
        _bind(parse_unified_diff(result.diff, policy), root)
    else:
        with pytest.raises(NormalizationError()) as error:
            normalize(raw, root, policy)
        assert error.value.code == expected


def repo(tmp_path, text, name='pkg/mod.py', newline='\n'):
    root = tmp_path/'repo'
    path = root/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace('\n', newline).encode())
    return root, PatchPolicy(allowed_paths=(name,), protected_paths=('tests',))


def apply(result, root, policy):
    predicted, _ = _bind(parse_unified_diff(result.diff, policy), root)
    return predicted


BASE = 'def a():\n    return 1\n\n\ndef b():\n    return 2\n'


def test_wrong_header_counts_are_ignored(tmp_path):
    root, policy = repo(tmp_path, BASE)
    raw = '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -40,99 +40,99 @@\n def b():\n-    return 2\n+    return 3\n'
    result = normalize(raw, root, policy)
    assert result.hunks_total == 1 and result.hunks_relocated == 1
    assert apply(result, root, policy)['pkg/mod.py'] == BASE.replace('return 2', 'return 3').encode()


def test_blank_line_is_empty_context(tmp_path):
    root, policy = repo(tmp_path, BASE)
    raw = '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -2,4 +2,4 @@\n     return 1\n\n\n-def b():\n+def c():\n'
    assert apply(normalize(raw, root, policy), root, policy)['pkg/mod.py'] == BASE.replace('def b', 'def c').encode()


def test_ambiguous_context(tmp_path):
    root, policy = repo(tmp_path, 'x = 1\ny = 2\nx = 1\ny = 2\n')
    raw = '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,2 +1,2 @@\n x = 1\n-y = 2\n+y = 3\n'
    with pytest.raises(NormalizationError()) as error:
        normalize(raw, root, policy)
    assert error.value.code == 'CONTEXT_AMBIGUOUS'


def test_hunks_out_of_order(tmp_path):  # Review Focus 2: never match backwards
    root, policy = repo(tmp_path, BASE)
    raw = ('--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -5,2 +5,2 @@\n def b():\n-    return 2\n+    return 3\n'
           '@@ -1,2 +1,2 @@\n def a():\n-    return 1\n+    return 0\n')
    with pytest.raises(NormalizationError()) as error:
        normalize(raw, root, policy)
    assert error.value.code == 'CONTEXT_NOT_FOUND'


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('final', [True, False])
def test_crlf_and_missing_final_newline(tmp_path, newline, final):  # Review Focus 3
    text = BASE if final else BASE[:-1]
    root, policy = repo(tmp_path, text, newline=newline)
    raw = '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1 +1 @@\n def b():\n-    return 2\n+    return 3\n'
    expected = text.replace('return 2', 'return 3').replace('\n', newline).encode()
    assert apply(normalize(raw, root, policy), root, policy)['pkg/mod.py'] == expected


def test_removed_line_starting_with_double_dash(tmp_path):
    root, policy = repo(tmp_path, 'a = 1\n-- b\nc = 3\n')
    raw = '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,3 +1,2 @@\n a = 1\n--- b\n c = 3\n'
    assert apply(normalize(raw, root, policy), root, policy)['pkg/mod.py'] == b'a = 1\nc = 3\n'


def test_protected_path_still_rejected(tmp_path):
    root, _ = repo(tmp_path, BASE, name='tests/test_mod.py')
    policy = PatchPolicy(allowed_paths=('tests/test_mod.py',), protected_paths=('tests',))
    raw = '--- a/tests/test_mod.py\n+++ b/tests/test_mod.py\n@@ -1 +1 @@\n-def a():\n+def z():\n'
    with pytest.raises(ValueError) as error:
        normalize(raw, root, policy)
    assert not isinstance(error.value, NormalizationError())


def test_partial_noop_hunk_dropped(tmp_path):
    root, policy = repo(tmp_path, BASE)
    raw = ('--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,2 +1,2 @@\n def a():\n-    return 1\n+    return 1\n'
           '@@ -5,2 +5,2 @@\n def b():\n-    return 2\n+    return 3\n')
    result = normalize(raw, root, policy)
    assert result.hunks_total == 2 and result.hunks_noop_dropped == 1
    assert apply(result, root, policy)['pkg/mod.py'] == BASE.replace('return 2', 'return 3').encode()


def test_all_noop_is_no_op(tmp_path):
    root, policy = repo(tmp_path, BASE)
    raw = '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,2 +1,2 @@\n def a():\n-    return 1\n+    return 1\n'
    with pytest.raises(NormalizationError()) as error:
        normalize(raw, root, policy)
    assert error.value.code == 'NO_OP'


def test_repeated_consecutive_file_header_is_continuation(tmp_path):
    root, policy = repo(tmp_path, BASE)
    raw = ('--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,2 +1,2 @@\n def a():\n-    return 1\n+    return 0\n'
           '--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -5,2 +5,2 @@\n def b():\n-    return 2\n+    return 3\n')
    expected = BASE.replace('return 1', 'return 0').replace('return 2', 'return 3').encode()
    assert apply(normalize(raw, root, policy), root, policy)['pkg/mod.py'] == expected


def test_non_consecutive_duplicate_file_header_rejected(tmp_path):
    root = tmp_path/'repo'
    for name in ('pkg/mod.py', 'pkg/other.py'):
        (root/name).parent.mkdir(parents=True, exist_ok=True)
        (root/name).write_text(BASE, encoding='utf-8')
    policy = PatchPolicy(allowed_paths=('pkg/mod.py', 'pkg/other.py'), protected_paths=())
    section = '--- a/pkg/{0}.py\n+++ b/pkg/{0}.py\n@@ -1,2 +1,2 @@\n def a():\n-    return 1\n+    return 0\n'
    with pytest.raises(ValueError, match='duplicate'):
        normalize(section.format('mod') + section.format('other') + section.format('mod'), root, policy)
