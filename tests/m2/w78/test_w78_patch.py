import pytest
from vgar.repair import executor as m_executor
from vgar.repair import patch as m_patch
from vgar.repair import workspace as m_workspace

PATCH = '--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n def answer():\n-    return 1\n+    return 2\n'


def make_source(tmp_path, crlf=False):
    root = tmp_path / 'source'
    root.mkdir()
    text = b'def answer():\n    return 1\n'
    (root / 'app.py').write_bytes(text.replace(b'\n', b'\r\n') if crlf else text)
    return root


@pytest.mark.parametrize('crlf', [False, True])
def test_private_apply_preserves_original_and_line_endings(tmp_path, crlf):
    source = make_source(tmp_path, crlf)
    before = (source / 'app.py').read_bytes()
    module = m_patch
    with m_workspace.create_workspace(source, tmp_path / 'temp') as lease:
        parsed = module.parse_unified_diff(PATCH, module.PatchPolicy(('app.py',), ('tests',)))
        result = module.apply_patch(lease, parsed, m_executor.NativeExecutor(lease))
        assert result.status == 'PASS' and result.changed_files == ['app.py']
        assert (lease.path / 'app.py').read_bytes() == before.replace(b'return 1', b'return 2')
    assert (source / 'app.py').read_bytes() == before
    assert not lease.path.exists()


def test_bad_second_file_never_partially_applies(tmp_path):
    source = make_source(tmp_path)
    (source / 'other.py').write_bytes(b'value = 1\n')
    raw = PATCH + '\n--- a/other.py\n+++ b/other.py\n@@ -1 +1 @@\n-value = 99\n+value = 2\n'
    module = m_patch
    with m_workspace.create_workspace(source, tmp_path / 'temp') as lease:
        parsed = module.parse_unified_diff(raw, module.PatchPolicy(('app.py', 'other.py'), ('tests',)))
        result = module.apply_patch(lease, parsed, m_executor.NativeExecutor(lease))
        assert result.status == 'FAIL' and not result.patch_applied
        assert (lease.path / 'app.py').read_bytes() == (source / 'app.py').read_bytes()


@pytest.mark.parametrize('raw', [PATCH.replace('app.py', '../app.py'), PATCH.replace('app.py', 'tests/test_x.py'),
    PATCH.replace('-1,2 +1,2', '-1,99 +1,2'), PATCH.replace('+    return 2\n', ''),
    PATCH + 'please run it\n', PATCH.replace('app.py', '/dev/null')])
def test_bad_diff_is_rejected(raw):
    with pytest.raises(ValueError):
        m_patch.parse_unified_diff(raw, m_patch.PatchPolicy(('app.py',), ('tests',)))


def test_multifile_unicode_space_and_no_final_newline(tmp_path):
    source = make_source(tmp_path)
    (source / 'tên file.py').write_bytes(b'value = 1')
    raw = PATCH + '--- a/tên file.py\n+++ b/tên file.py\n@@ -1 +1 @@\n-value = 1\n\\ No newline at end of file\n+value = 2\n\\ No newline at end of file\n'
    module = m_patch
    with m_workspace.create_workspace(source, tmp_path / 'temp') as lease:
        result = module.apply_patch(lease, module.parse_unified_diff(raw,
            module.PatchPolicy(('app.py', 'tên file.py'), ('tests',))), m_executor.NativeExecutor(lease))
        assert result.status == 'PASS'
        assert (lease.path / 'tên file.py').read_bytes() == b'value = 2'

