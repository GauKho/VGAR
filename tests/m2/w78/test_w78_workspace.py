import subprocess

import pytest
from vgar.repair import workspace as m_workspace


def test_source_git_metadata_unchanged(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    subprocess.run(['git', 'init', '--template=', str(source)], check=True, capture_output=True)
    (source / 'app.py').write_bytes(b'value = 1\n')
    before = {p.relative_to(source).as_posix(): p.read_bytes() for p in (source / '.git').rglob('*') if p.is_file()}
    with m_workspace.create_workspace(source, tmp_path / 'temp') as lease:
        assert (lease.path / '.git').is_file()
        assert lease.path != source
    assert before == {p.relative_to(source).as_posix(): p.read_bytes() for p in (source / '.git').rglob('*') if p.is_file()}


def test_workspace_rejects_overlap(tmp_path):
    (tmp_path / 'app.py').write_bytes(b'value = 1\n')
    with pytest.raises(ValueError):
        m_workspace.create_workspace(tmp_path, tmp_path / 'temp')

