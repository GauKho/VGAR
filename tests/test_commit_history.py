"""Exercise pinned commit objects and the existing retrieval history input."""
from dataclasses import asdict

import pytest

from vgar.graph.ast_diff import diff_python_commit
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.history import read_commit_history
from vgar.graph.retrieval import GraphContextRetriever

objects = pytest.importorskip("dulwich.objects")
Repo = pytest.importorskip("dulwich.repo").Repo


def make_commit(repo, subject, files, *, parents=()):
    tree = objects.Tree()
    for path, content in files.items():
        blob = objects.Blob.from_string(content)
        repo.object_store.add_object(blob)
        tree.add(path.encode("utf-8"), 0o100644, blob.id)
    repo.object_store.add_object(tree)
    commit = objects.Commit()
    commit.tree = tree.id
    commit.parents = list(parents)
    commit.author = commit.committer = b"VGAR fixture <fixture@example.invalid>"
    commit.author_time = commit.commit_time = 100
    commit.author_timezone = commit.commit_timezone = 0
    commit.message = subject.encode("utf-8") + b"\n\nFixture body\n"
    repo.object_store.add_object(commit)
    return commit


def test_pinned_window_ignores_newer_commits_and_worktree(tmp_path):
    before, after = b"def value(): return 1\n", b"def value(): return 2\n"
    with Repo.init(str(tmp_path)) as repo:
        root = make_commit(repo, "Start", {"app.py": before, "old.txt": b"old"})
        target = make_commit(repo, "Sửa giá trị", {"app.py": after, "mới.txt": b"new"}, parents=(root.id,))
        later = make_commit(repo, "Later", {"app.py": after, "future.py": before}, parents=(target.id,))
        repo.refs[b"HEAD"] = later.id
    app = tmp_path / "app.py"
    app.write_bytes(b"def value(): return 100\n")

    revision = target.id.decode("ascii")
    window = read_commit_history(tmp_path, revision=revision, max_commits=2)
    changed, initial = window.commits
    assert changed.subject == "Sửa giá trị" and changed.commit_time == 100
    assert changed.commit_id == revision and changed.parent_ids == (root.id.decode("ascii"),)
    by_kind = {change.kind: change for change in changed.files}
    assert by_kind["add"].before is None and by_kind["add"].after.path == "mới.txt"
    assert by_kind["delete"].before.path == "old.txt" and by_kind["delete"].after is None
    edit = by_kind["modify"]
    assert asdict(edit.before) == {"path": "app.py", "object_id": objects.Blob.from_string(before).id.decode("ascii"),
                                  "mode": 0o100644}
    assert edit.after.object_id == objects.Blob.from_string(after).id.decode("ascii")
    assert not initial.parent_ids and all(change.kind == "add" for change in initial.files)
    assert window.change_counts == {"app.py": 2, "mới.txt": 1, "old.txt": 2}
    assert window.history_label == f"git:first-parent:v1:{revision}:2"
    assert read_commit_history(tmp_path, revision=revision, max_commits=1).change_counts["app.py"] == 1
    with Repo(str(tmp_path)) as repo:
        assert repo.head() == later.id
    assert app.read_bytes() == b"def value(): return 100\n"


def test_merge_compares_first_parent_and_preserves_all_parent_ids(tmp_path):
    with Repo.init(str(tmp_path)) as repo:
        root = make_commit(repo, "Root", {"base.py": b"base"})
        main = make_commit(repo, "Main", {"base.py": b"main"}, parents=(root.id,))
        side = make_commit(repo, "Side", {"base.py": b"base", "side.py": b"side"}, parents=(root.id,))
        merge = make_commit(repo, "Merge", {"base.py": b"main", "side.py": b"side"}, parents=(main.id, side.id))

    window = read_commit_history(tmp_path, revision=merge.id.decode("ascii"), max_commits=10)
    assert [commit.commit_id for commit in window.commits] == [item.id.decode("ascii") for item in (merge, main, root)]
    assert window.commits[0].parent_ids == (main.id.decode("ascii"), side.id.decode("ascii"))
    imported, = window.commits[0].files
    assert imported.kind == "add" and imported.after.path == "side.py"
    assert window.change_counts == {"base.py": 2, "side.py": 1}


def test_missing_parent_and_movable_revision_are_rejected(tmp_path):
    with Repo.init(str(tmp_path)) as repo:
        dangling = make_commit(repo, "Shallow tip", {"app.py": b""}, parents=(b"1" * 40,))

    with pytest.raises(ValueError, match="full lowercase Git SHA-1"):
        read_commit_history(tmp_path, revision="HEAD", max_commits=1)
    with pytest.raises(ValueError, match="positive integer"):
        read_commit_history(tmp_path, revision=dangling.id.decode("ascii"), max_commits=0)
    with pytest.raises(ValueError, match="missing from the local repository"):
        read_commit_history(tmp_path, revision=dangling.id.decode("ascii"), max_commits=1)


def test_commit_counts_reach_retrieval_with_provenance(tmp_path):
    content = b"def value():\n    return 1\n"
    with Repo.init(str(tmp_path)) as repo:
        commit = make_commit(repo, "Fixture", {"app.py": content})
    (tmp_path / "app.py").write_bytes(content)
    revision = commit.id.decode("ascii")
    history = read_commit_history(tmp_path, revision=revision, max_commits=5)
    graph = PythonGraphBuilder(repo_key="fixture/history", repository_revision=revision).build(tmp_path)
    symbol = next(node for node in graph["nodes"] if node["type"] == "Function")
    retriever = GraphContextRetriever(graph, tmp_path, count_tokens=len, counter_label="fixture-character-count",
                                      change_counts=history.change_counts, history_label=history.history_label)
    result = retriever.retrieve([symbol["id"]], 1000)
    row = next(row for row in result.candidates if row["node_id"] == symbol["id"])
    assert row["features"]["recent_change_frequency"] == 1.0
    assert result.history_label == history.history_label


def test_ast_diff_reads_the_exact_committed_python_blobs(tmp_path):
    before, after = b"def value(): return 1\n", b"def value(): return 2\n"
    with Repo.init(str(tmp_path)) as repo:
        root = make_commit(repo, "Start", {"app.py": before, "old.py": before, "notes.txt": b"one"})
        target = make_commit(repo, "Edit", {"app.py": after, "new.py": after, "notes.txt": b"two"}, parents=(root.id,))
    (tmp_path / "app.py").write_bytes(b"invalid worktree version")
    commit, = read_commit_history(tmp_path, revision=target.id.decode("ascii"), max_commits=1).commits
    edited, added, removed = diff_python_commit(tmp_path, commit)
    assert edited.before.path == edited.after.path == "app.py"
    assert edited.before.object_id == objects.Blob.from_string(before).id.decode("ascii")
    assert edited.after.object_id == objects.Blob.from_string(after).id.decode("ascii")
    assert edited.ast_diff.edits[0].changed_parts == ("body",)
    assert added.before is None and added.after.path == "new.py" and added.ast_diff.edits[0].change == "ADDED"
    assert removed.after is None and removed.before.path == "old.py" and removed.ast_diff.edits[0].change == "REMOVED"
    assert (tmp_path / "app.py").read_bytes() == b"invalid worktree version"
