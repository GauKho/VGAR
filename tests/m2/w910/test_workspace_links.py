"""Tracked in-repo file symlinks (Django docs/_theme/*.png) are inventoried by target, never followed."""
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX symlinks (runner host is WSL)')


def make_repo(tmp_path, *, commit=True):
    root = tmp_path/'src'
    (root/'pkg').mkdir(parents=True)
    (root/'docs/static').mkdir(parents=True)
    (root/'pkg/core.py').write_bytes(b'def f():\n    return 1\n')
    (root/'docs/img.png').write_bytes(b'\x89PNG fake')
    os.symlink('../img.png', root/'docs/static/icon.png')
    if commit:
        for args in (('init', '-q'), ('config', 'core.autocrlf', 'false'), ('add', '--all'),
                     ('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'base')):
            subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    return root


def git_head(root):
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


def test_inventory_records_link_target_without_following(tmp_path):
    from vgar.repair.evidence import digest
    from vgar.repair.workspace import inventory, link_entry
    root = make_repo(tmp_path, commit=False)
    found = inventory(root)
    assert found['docs/static/icon.png'] == link_entry('../img.png') == 'symlink:' + digest(b'../img.png')
    assert found['docs/img.png'] == digest(b'\x89PNG fake')
    os.remove(root/'docs/static/icon.png')
    os.symlink('../other.png', root/'docs/static/icon.png')  # retargeting is drift
    assert inventory(root)['docs/static/icon.png'] != found['docs/static/icon.png']


@pytest.mark.parametrize('name,target,directory', [
    ('pkg/alias.py', 'core.py', False),            # code is never a link
    ('docs/abs.png', '/etc/passwd', False),        # absolute target
    ('docs/up.png', '../../outside.png', False),   # escapes the repository
    ('docs/dirlink', 'static', True),              # directory links stay unsupported
])
def test_inventory_rejects_unsafe_links(tmp_path, name, target, directory):
    from vgar.repair.workspace import inventory
    root = make_repo(tmp_path, commit=False)
    os.symlink(target, root/name, target_is_directory=directory)
    with pytest.raises(ValueError, match='link'):
        inventory(root)


def test_base_inventory_proves_link_target_against_git_tree(tmp_path):
    from vgar.repair.admission import base_inventory
    from vgar.repair.workspace import inventory, link_entry
    root = make_repo(tmp_path)
    assert base_inventory(root, git_head(root)) == inventory(root)
    assert base_inventory(root, git_head(root))['docs/static/icon.png'] == link_entry('../img.png')
    os.remove(root/'docs/static/icon.png')
    os.symlink('../pkg/core.py', root/'docs/static/icon.png')
    with pytest.raises(ValueError, match='Git blob'):
        base_inventory(root, git_head(root))


def test_private_workspace_keeps_link_as_link(tmp_path):
    from vgar.repair.workspace import create_workspace, inventory
    root = make_repo(tmp_path)
    lease = create_workspace(root, tmp_path/'tmp')
    try:
        link = lease.path/'docs/static/icon.png'
        assert link.is_symlink() and os.readlink(link) == '../img.png'
        assert inventory(lease.path) == lease.before
    finally:
        lease.__exit__()


def test_docker_transport_ships_regular_files_only():
    from vgar.repair.docker_executor import transport_snapshot
    from vgar.repair.workspace import link_entry
    expected = {'pkg/core.py': 'sha256:' + 'a'*64, 'docs/static/icon.png': link_entry('../img.png')}
    # The container's /testbed is reset to the base commit, which already holds the same links.
    assert transport_snapshot(expected) == {'pkg/core.py': 'sha256:' + 'a'*64}
