"""Build small dulwich repositories with nested trees for GraphDiff tests."""
from __future__ import annotations

from pathlib import Path


def _tree(repo, files: dict[str, bytes]):
    from dulwich.objects import Blob, Tree

    tree = Tree()
    folders: dict[str, dict[str, bytes]] = {}
    for path, content in files.items():
        head, _, rest = path.partition("/")
        if rest:
            folders.setdefault(head, {})[rest] = content
        else:
            blob = Blob.from_string(content)
            repo.object_store.add_object(blob)
            tree.add(head.encode("utf-8"), 0o100644, blob.id)
    for name, children in folders.items():
        tree.add(name.encode("utf-8"), 0o040000, _tree(repo, children).id)
    repo.object_store.add_object(tree)
    return tree


def commit(repo, subject: str, files: dict[str, bytes], *, parents=(), time: int = 100):
    """Commit ``files`` (the whole tree) with the given parents; returns the commit id as str."""
    from dulwich.objects import Commit

    item = Commit()
    item.tree = _tree(repo, files).id
    item.parents = [p.encode("ascii") if isinstance(p, str) else p for p in parents]
    item.author = item.committer = b"VGAR fixture <fixture@example.invalid>"
    item.author_time = item.commit_time = time
    item.author_timezone = item.commit_timezone = 0
    item.message = subject.encode("utf-8") + b"\n"
    repo.object_store.add_object(item)
    return item.id.decode("ascii")


def linear_repo(root: Path, snapshots: list[tuple[str, dict[str, bytes]]]) -> list[str]:
    """Create a repository at ``root`` with one first-parent commit per snapshot; returns ids oldest first."""
    from dulwich.repo import Repo

    root.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(str(root))
    ids: list[str] = []
    for number, (subject, files) in enumerate(snapshots):
        ids.append(commit(repo, subject, files, parents=ids[-1:], time=100 + number))
    repo.refs[b"HEAD"] = ids[-1].encode("ascii")
    repo.close()
    return ids


def write_tree(root: Path, files: dict[str, bytes]) -> Path:
    """Write ``files`` as a worktree (for building the snapshot graph)."""
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return root
