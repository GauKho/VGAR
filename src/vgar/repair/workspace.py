"""Private seed/worktree; never add a worktree to the source repository."""
from dataclasses import dataclass, field
import errno
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import tempfile
import time
import uuid

from vgar.repair.contracts import safe_path
from vgar.repair.executor import remaining_timeout
from vgar.repair.evidence import atomic_json, digest
from vgar.repair.executor import run_bounded, utc_now
from vgar.repair.diagnostics import exception_details

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
    private, temp_root = Path(private).absolute(), Path(temp_root).resolve()

    def assert_owned():
        if (private.resolve().parent != temp_root or not private.name.startswith('m2-w78-')
                or private.is_symlink() or (hasattr(private, 'is_junction') and private.is_junction())):
            raise ValueError('Refusing cleanup outside owned private directory')

    assert_owned()
    start = time.monotonic()
    delays = (0.05, 0.1, 0.2, 0.4, 0.8)
    path = temp_root / '.cleanup-records' / (private.name + '.json')
    report = dict(status='NOT_RUN', complete=False, private_path=str(private),
        diagnostics_path=str(path), cleanup_process_id=os.getpid(), lock_owner='not_identified',
        started_utc=utc_now(), ended_utc=None, duration_ms=None, attempts=[],
        max_attempts=6, scheduled_wait_limit_ms=1550)
    operation = None

    def onerror(func, path, exc):
        nonlocal operation
        operation = getattr(func, '__name__', str(func))
        error = exc[1]
        # Preserve the existing read-only-file repair, not for sharing locks or
        # unrelated I/O errors. Chmod cannot release another process's handle.
        if getattr(error, 'winerror', None) == 5 or (
                getattr(error, 'winerror', None) is None and error.errno in (errno.EACCES, errno.EPERM)):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            func(path)
        else:
            raise error.with_traceback(exc[2])

    def finish(status):
        report.update(status=status, complete=True, ended_utc=utc_now(),
                      duration_ms=round((time.monotonic() - start) * 1000))
        atomic_json(path, report)

    for index in range(len(delays) + 1):
        entry = dict(number=index + 1, started_utc=utc_now(), winerror=None)
        report['attempts'].append(entry)
        atomic_json(path, report)
        try:
            # Revalidate before every recursive delete; never follow a swapped
            # root symlink/junction or broaden the target to temp_root/source.
            assert_owned()
            shutil.rmtree(private, onerror=onerror)
        except Exception as error:
            code = getattr(error, 'winerror', None)
            entry.update(status='ERROR', ended_utc=utc_now(), winerror=code,
                errno=getattr(error, 'errno', None), operation=operation,
                failed_path=str(getattr(error, 'filename', None) or private),
                **exception_details(error))
            if code in (32, 33) and index < len(delays):
                entry['retry_wait_ms'] = round(delays[index] * 1000)
                atomic_json(path, report)
                time.sleep(delays[index])
                continue
            error.cleanup_diagnostics = report
            error.add_note('Owned cleanup failed; diagnostics: ' + str(path))
            finish('ERROR')
            raise
        else:
            entry.update(status='PASS', ended_utc=utc_now())
            finish('PASS')
            return report


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
    cleanup_diagnostics: dict = field(default_factory=dict)

    def assert_original(self):
        if inventory(self.source_repo) != self.before:
            raise ValueError('Original source changed')

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.active = False
        if not self.keep and self.private.exists():
            try:
                self.cleanup_diagnostics = _remove_owned(self.private, self.temp_root)
            except Exception as error:
                self.cleanup_diagnostics = getattr(error, 'cleanup_diagnostics', {})
                raise


def create_workspace(source: Path, temp_root: Path, policy=None, *, deadline=None, allow_attributes=False) -> WorkspaceLease:
    remaining_timeout(deadline)
    source = Path(source)
    before = inventory(source)
    source, temp_root = source.resolve(strict=True), Path(temp_root).resolve()
    if source == temp_root or source in temp_root.parents or temp_root in source.parents:
        raise ValueError('Temporary root must not overlap source')
    if not allow_attributes and any(Path(name).name == '.gitattributes' for name in before):
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
        if allow_attributes:
            # Highest-precedence attributes disable target-defined clean/smudge/EOL transformations.
            (seed/'.git/info').mkdir(exist_ok=True)
            (seed/'.git/info/attributes').write_text('* -text -filter -ident -working-tree-encoding\n', encoding='utf-8')
        _git(seed, 'add', '--all', '--force', deadline=deadline)  # copy gitignored files too
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


# Helpers kept for vgar run/chat and the MCP repository server.
_IGNORED = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            "artifacts", "logs", ".vgar", "node_modules"}


def safe_relative_path(value: str) -> Path:
    """Accept one repository-relative path; never silently normalize traversal."""
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if not value or posix.is_absolute() or windows.is_absolute() or windows.drive or ".." in posix.parts:
        raise ValueError(f"Unsafe repository-relative path: {value}")
    if any(part in ("", ".") for part in normalized.split("/")):
        raise ValueError(f"Unsafe repository-relative path: {value}")
    return Path(*posix.parts)


def _source_files(root: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []

    def visit(directory: Path) -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            if entry.name in _IGNORED:
                continue
            path = Path(entry.path)
            if entry.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError(f"Source contains a link: {path}")
            if entry.is_dir(follow_symlinks=False):
                visit(path)
            elif entry.is_file(follow_symlinks=False):
                found.append((path.relative_to(root).as_posix(), path))
            else:
                raise ValueError(f"Unsupported source entry: {path}")

    visit(root)
    return found


def fingerprint_source(source_repo: Path) -> str:
    root = Path(source_repo).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a repository directory: {root}")
    digest = hashlib.sha256()
    for relative, path in _source_files(root):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()
