"""Private seed/worktree; never add a worktree to the source repository."""
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
import tempfile
import uuid

from .contracts import safe_path
from .bootstrap import remaining_timeout
from .evidence import digest
from .executor import run_bounded

IGNORED = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.venv'}


def inventory(root: Path) -> dict[str, str]:
    if root.is_symlink() or (hasattr(root, 'is_junction') and root.is_junction()):
        raise ValueError('Source root is a link')
    result, total = {}, 0
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(n for n in names if n not in IGNORED)
        for name in [*names, *files]:
            path = Path(directory) / name
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Source links/junctions are not allowed')
        for name in sorted(files):
            if name in IGNORED:
                continue
            path = Path(directory) / name
            relative = safe_path(path.relative_to(root).as_posix())
            size = path.stat().st_size
            total += size
            if size > 16 * 1024 * 1024 or total > 256 * 1024 * 1024:
                raise ValueError('Source inventory exceeds size limits')
            result[relative] = digest(path.read_bytes())
    return result


def _git(cwd, *args, deadline=None):
    argv = ('git', '-c', f'safe.directory={cwd.as_posix()}', '-c', 'core.autocrlf=false',
            '-c', 'core.hooksPath=', '-c', 'commit.gpgsign=false', '-c', 'user.name=VGAR M2 fixture',
            '-c', 'user.email=m2@fixture.local', *args)
    result = run_bounded(argv, cwd, remaining_timeout(deadline))
    if result['status'] != 'PASS':
        raise RuntimeError(result['stderr'] or result['stdout'])
    return result


def _remove_owned(private: Path, temp_root: Path):
    if private.resolve().parent != temp_root.resolve() or not private.name.startswith('m2-w78-') or private.is_symlink():
        raise ValueError('Refusing cleanup outside owned private directory')
    def onerror(func, path, exc):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    shutil.rmtree(private, onerror=onerror)


@dataclass
class WorkspaceLease:
    path: Path
    private: Path
    temp_root: Path
    source_repo: Path
    before: dict
    worktree_id: str
    active: bool = True
    keep: bool = False

    def assert_original(self):
        if inventory(self.source_repo) != self.before:
            raise ValueError('Original source changed')

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.active = False
        if not self.keep and self.private.exists():
            _remove_owned(self.private, self.temp_root)


def create_workspace(source: Path, temp_root: Path, policy=None, *, deadline=None) -> WorkspaceLease:
    remaining_timeout(deadline)
    source = Path(source)
    before = inventory(source)
    source, temp_root = source.resolve(strict=True), Path(temp_root).resolve()
    if source == temp_root or source in temp_root.parents or temp_root in source.parents:
        raise ValueError('Temporary root must not overlap source')
    if any(Path(name).name == '.gitattributes' for name in before):
        raise ValueError('Attribute transformations are unsupported in this fixture profile')
    temp_root.mkdir(parents=True, exist_ok=True)
    private = Path(tempfile.mkdtemp(prefix='m2-w78-', dir=temp_root)).resolve()
    seed, worktree = private / 'seed', private / 'worktree'
    seed.mkdir()
    try:
        for relative in before:
            target = seed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
        _git(seed, 'init', '--template=', deadline=deadline)
        # Persist on the private repository: later apply calls must not inherit
        # the host's core.autocrlf=true and alter raw bytes on Windows.
        _git(seed, 'config', '--local', 'core.autocrlf', 'false', deadline=deadline)
        _git(seed, 'add', '--all', deadline=deadline)
        _git(seed, 'commit', '--no-verify', '-m', 'Private fixture snapshot', deadline=deadline)
        _git(seed, 'worktree', 'add', '--detach', str(worktree), 'HEAD', deadline=deadline)
        lease = WorkspaceLease(worktree.resolve(), private, temp_root, source, before, 'wt-' + uuid.uuid4().hex)
        if inventory(worktree) != before:
            raise ValueError('Worktree bytes differ from original snapshot')
        lease.assert_original()
        return lease
    except BaseException:
        _remove_owned(private, temp_root)
        raise

