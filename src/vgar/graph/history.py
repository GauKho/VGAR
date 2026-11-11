"""Read a pinned, first-parent commit window for GraphDiff and retrieval."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dulwich.objects import TreeEntry


@dataclass(frozen=True)
class FileVersion:
    path: str
    object_id: str
    mode: int


@dataclass(frozen=True)
class FileChange:
    kind: str
    before: FileVersion | None
    after: FileVersion | None


@dataclass(frozen=True)
class CommitChange:
    commit_id: str
    parent_ids: tuple[str, ...]
    commit_time: int
    subject: str
    files: tuple[FileChange, ...]


@dataclass(frozen=True)
class CommitHistory:
    revision: str
    max_commits: int
    commits: tuple[CommitChange, ...]

    @property
    def history_label(self) -> str:
        return f"git:first-parent:v1:{self.revision}:{self.max_commits}"

    @property
    def change_counts(self) -> dict[str, int]:
        """Count each repository-relative path once per commit in the window."""
        counts: Counter[str] = Counter()
        for commit in self.commits:
            counts.update({version.path for change in commit.files
                           for version in (change.before, change.after) if version is not None})
        return dict(sorted(counts.items()))


def read_commit_history(repo_root: str | Path, *, revision: str, max_commits: int) -> CommitHistory:
    """Read committed trees at a full SHA-1, using only local Git objects.

    Changes for a merge are relative to its first parent. A missing parent
    needed for a tree comparison makes the requested window unavailable.
    """
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("revision must be a full lowercase Git SHA-1 commit ID")
    if type(max_commits) is not int or max_commits < 1:
        raise ValueError("max_commits must be a positive integer")

    from dulwich.diff_tree import tree_changes
    from dulwich.objects import Commit, ObjectID
    from dulwich.repo import Repo

    with Repo(str(Path(repo_root).resolve(strict=True))) as repo:
        try:
            commit = repo.get_object(ObjectID(revision.encode("ascii")))
            if not isinstance(commit, Commit):
                raise TypeError("revision does not identify a Git commit")
            commits: list[CommitChange] = []
            for _ in range(max_commits):
                parent = repo.get_object(commit.parents[0]) if commit.parents else None
                if parent is not None and not isinstance(parent, Commit):
                    raise TypeError("Git first parent is not a commit")
                before_tree = parent.tree if parent is not None else None
                files = tuple(FileChange(change.type, _version(change.old), _version(change.new))
                              for change in tree_changes(repo.object_store, before_tree, commit.tree))
                subject = commit.message.partition(b"\n")[0].decode("utf-8", errors="replace")
                commits.append(CommitChange(commit.id.decode("ascii"), tuple(p.decode("ascii") for p in commit.parents),
                                            commit.commit_time, subject, files))
                if parent is None:
                    break
                commit = parent
        except KeyError as exc:
            raise ValueError("Pinned history requires a Git object missing from the local repository") from exc
    return CommitHistory(revision, max_commits, tuple(commits))


def _version(entry: TreeEntry | None) -> FileVersion | None:
    if entry is None:
        return None
    return FileVersion(entry.path.decode("utf-8", errors="surrogateescape"), entry.sha.decode("ascii"), entry.mode)
