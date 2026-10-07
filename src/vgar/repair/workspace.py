"""Disposable repository copies with explicit size and path boundaries."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from vgar.source_scope import SourceScope

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


def _source_files(root: Path, scope: SourceScope | None = None) -> list[tuple[str, Path]]:
    return (scope or SourceScope.for_repository(root)).files(root)


def fingerprint_source(source_repo: Path, *, scope: SourceScope | None = None) -> str:
    root = Path(source_repo).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a repository directory: {root}")
    digest = hashlib.sha256()
    for relative, path in _source_files(root, scope):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


@dataclass
class WorkspaceLease:
    path: Path
    worktree_id: str
    source_repo: Path
    source_hash_before: str
    temp_root: Path

    def __enter__(self) -> "WorkspaceLease":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        resolved = self.path.resolve()
        if resolved.parent != self.temp_root.resolve() or not resolved.name.startswith("vgar-m2-"):
            raise ValueError("Refusing cleanup outside the M2 temporary root")
        if resolved.exists():
            shutil.rmtree(resolved)


def create_workspace(source_repo: Path, temp_root: Path, *, max_file_bytes: int = 16 * 1024 * 1024,
                     max_total_bytes: int = 256 * 1024 * 1024) -> WorkspaceLease:
    root = Path(source_repo).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a repository directory: {root}")
    target_root = Path(temp_root).resolve()
    if root == target_root or root in target_root.parents or target_root in root.parents:
        raise ValueError("Temporary root must be separate from the source repository")
    files = _source_files(root)
    total = 0
    for _, path in files:
        size = path.stat().st_size
        total += size
        if size > max_file_bytes or total > max_total_bytes:
            raise ValueError(f"Source size limit exceeded: {path}")
    before = fingerprint_source(root)
    target_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="vgar-m2-", dir=target_root))
    try:
        for relative, path in files:
            destination = workspace / safe_relative_path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        if fingerprint_source(root) != before:
            raise RuntimeError("Source changed while creating disposable workspace")
    except BaseException:
        shutil.rmtree(workspace)
        raise
    return WorkspaceLease(path=workspace, worktree_id=f"wt-{uuid.uuid4().hex}", source_repo=root,
                          source_hash_before=before, temp_root=target_root)
