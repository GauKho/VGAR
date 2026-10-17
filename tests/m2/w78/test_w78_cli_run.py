"""vgar run/chat use the M2 workspace; unsupported repositories fail with a clear message."""
import pytest

from vgar.cli import sandbox_workspace


def test_w78_cli_run_rejects_gitattributes_with_clear_error(tmp_path):
    (tmp_path / 'repo').mkdir()
    (tmp_path / 'repo/.gitattributes').write_text('* text\n')
    with pytest.raises(ValueError, match='Attribute transformations are unsupported'):
        with sandbox_workspace(tmp_path / 'repo', tmp_path / 'ws'):
            pass


def test_w78_cli_sandbox_workspace_yields_disposable_copy(tmp_path):
    (tmp_path / 'repo').mkdir()
    (tmp_path / 'repo/app.py').write_text('x = 1\n')
    with sandbox_workspace(tmp_path / 'repo', tmp_path / 'ws') as lease:
        assert (lease.path / 'app.py').read_text() == 'x = 1\n'
        assert lease.path != tmp_path / 'repo'
