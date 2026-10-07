"""Host-granted workspace capability, not an OS security sandbox."""
from __future__ import annotations

from pathlib import Path

from vgar.contracts.error import GraphError
from vgar.repair.workspace import safe_relative_path


class WorkspacePolicyError(GraphError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        self.code = code
        super().__init__(message, details=details)


def leased_root(repo_path: str, workspace_root: Path | None) -> Path:
    if workspace_root is None:
        raise WorkspacePolicyError("WORKSPACE_NOT_BOUND", "Host has not granted a disposable workspace")
    lease_path = Path(workspace_root).absolute()
    if Path(repo_path).absolute() != lease_path:
        raise WorkspacePolicyError("WORKSPACE_ACCESS_DENIED", "Repository root does not match the host workspace lease")
    try:
        for path in (lease_path, *lease_path.parents):
            if getattr(path.lstat(), "st_file_attributes", 0) & 0x400 or path.is_symlink():
                raise WorkspacePolicyError("WORKSPACE_ACCESS_DENIED", "Workspace lease contains a link or junction")
        lease = lease_path.resolve(strict=True)
        requested = Path(repo_path).resolve(strict=True)
    except OSError as error:
        raise WorkspacePolicyError("WORKSPACE_ACCESS_DENIED", "Workspace lease is unavailable or stale") from error
    if not lease.is_dir() or requested != lease:
        raise WorkspacePolicyError("WORKSPACE_ACCESS_DENIED", "Repository root does not match the host workspace lease")
    return lease


def leased_path(root: Path, path: str) -> Path:
    relative = safe_relative_path(path)
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                raise WorkspacePolicyError("WORKSPACE_ACCESS_DENIED", "Workspace path contains a link or junction")
    target = current.resolve()
    if root not in target.parents:
        raise WorkspacePolicyError("WORKSPACE_ACCESS_DENIED", "Path escapes the leased workspace")
    return target
