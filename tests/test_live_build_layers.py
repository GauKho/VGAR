"""Served build with host-configured layers, the HEAD revision and a layer report (spec 2026-11-15 §1)."""
from __future__ import annotations

from pathlib import Path

import pytest
from git_fixture import linear_repo, write_tree

from vgar.graph.layer_config import LayerConfigs
from vgar.graph.live_build import LiveGraphBuilder, head_revision
from vgar.graph.tsg_extractor import TsgConfig

pytest.importorskip("dulwich")
FILES = {"pkg/mod.py": b"LIMIT = 3\n\n\ndef f():\n    return LIMIT\n"}


def _git_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    sha = linear_repo(root, [("base", FILES)])[-1]
    from dulwich import porcelain

    porcelain.reset(str(root), "hard")  # a dulwich commit writes neither worktree nor index; check out HEAD
    return root, sha


def test_revision_is_head_sha_in_git_repo(tmp_path):
    root, sha = _git_repo(tmp_path)
    assert head_revision(root) == (sha, False)
    result = LiveGraphBuilder(root, tmp_path / "g.db").run()
    assert result["revision"] == sha


def test_non_git_repo_keeps_cli(tmp_path):
    root = write_tree(tmp_path / "plain", FILES)
    assert head_revision(root) == ("cli", False)
    assert LiveGraphBuilder(root, tmp_path / "g.db").run()["revision"] == "cli"


def test_root_below_git_repo_is_reported_not_silent(tmp_path, monkeypatch, caplog):
    from vgar.graph.sqlite_store import SQLiteGraphStore

    outer, _ = _git_repo(tmp_path)
    root = write_tree(outer / "sub", FILES)
    seen = []
    original = SQLiteGraphStore.ingest
    monkeypatch.setattr(SQLiteGraphStore, "ingest", lambda self, document, **kwargs: seen.append(document) or original(self, document, **kwargs))
    with caplog.at_level("WARNING", logger="vgar.graph.live_build"):
        result = LiveGraphBuilder(root, tmp_path / "g.db").run()
    assert head_revision(root) == ("cli", False) and result["revision"] == "cli"
    assert seen[0]["statistics"]["revision_source"] == "parent-repo-not-supported"
    assert str(outer) in caplog.text


def test_dirty_worktree_keeps_head_revision(tmp_path):
    root, sha = _git_repo(tmp_path)
    (root / "pkg" / "mod.py").write_bytes(FILES["pkg/mod.py"] + b"\nX = 1\n")
    assert head_revision(root) == (sha, True)


def test_dirty_check_never_writes_the_index(tmp_path):
    import os

    root, sha = _git_repo(tmp_path)
    os.utime(root / "pkg" / "mod.py", (1_000_000_000, 1_000_000_000))  # stat drifts, content does not
    before = (root / ".git" / "index").read_bytes()
    assert head_revision(root) == (sha, False)
    assert (root / ".git" / "index").read_bytes() == before


def test_incremental_build_infers_dirty_without_status(tmp_path, monkeypatch):
    from dulwich import porcelain

    root, _ = _git_repo(tmp_path)
    calls = []
    original = porcelain.status
    monkeypatch.setattr(porcelain, "status", lambda *a, **k: calls.append(1) or original(*a, **k))
    live = LiveGraphBuilder(root, tmp_path / "g.db")
    assert live.run()["worktree_dirty"] is False and len(calls) == 1
    (root / "pkg" / "mod.py").write_bytes(FILES["pkg/mod.py"] + b"\nY = 2\n")
    second = live.run()
    assert second["mode"] == "incremental" and second["worktree_dirty"] is True and len(calls) == 1
    (root / "pkg" / "mod.py").write_bytes(FILES["pkg/mod.py"])  # back to HEAD: stays dirty until HEAD moves
    assert live.run()["worktree_dirty"] is True and len(calls) == 1


def test_layers_off_uses_incremental_path(tmp_path):
    root, _ = _git_repo(tmp_path)
    live = LiveGraphBuilder(root, tmp_path / "g.db")
    assert live.run()["mode"] == "cold"
    (root / "pkg" / "mod.py").write_bytes(FILES["pkg/mod.py"] + b"\nY = 2\n")
    second = live.run()
    assert second["mode"] == "incremental" and all(v["status"] == "off" for v in second["layers"].values())


def test_layers_on_uses_full_build(tmp_path, monkeypatch):
    from vgar.graph import live_build

    root, _ = _git_repo(tmp_path)
    seen = []
    original = live_build.PythonGraphBuilder

    class Recording(original):
        def __init__(self, **kwargs):
            seen.append(kwargs)
            super().__init__(**{k: v for k, v in kwargs.items() if k != "tsg"})

    monkeypatch.setattr(live_build, "PythonGraphBuilder", Recording)
    fake = TsgConfig(executable=tmp_path / "tsg", tree_sitter_dir=tmp_path)
    live = LiveGraphBuilder(root, tmp_path / "g.db", layers=LayerConfigs(tsg=fake))
    assert live.run()["mode"] == "cold" and live.run()["mode"] == "cold"
    assert seen and seen[0]["tsg"] is fake


def test_failed_layer_is_reported_and_build_continues(tmp_path):
    root, _ = _git_repo(tmp_path)
    missing = TsgConfig(executable=tmp_path / "no-such-tsg", tree_sitter_dir=tmp_path)
    result = LiveGraphBuilder(root, tmp_path / "g.db", layers=LayerConfigs(tsg=missing)).run()
    assert result["layers"]["tsg"]["status"] == "failed" and result["layers"]["tsg"]["reason"]
    assert result["nodes"] > 0


def test_tool_result_carries_layers_and_revision(tmp_path):
    root, sha = _git_repo(tmp_path)
    result = LiveGraphBuilder(root, tmp_path / "g.db").run()
    assert set(result["layers"]) == {"tsg", "scip", "lsp", "jarvis", "joern"}
    assert result["revision"] == sha and result["worktree_dirty"] is False


def test_unreadable_git_data_falls_back_to_cli(tmp_path, monkeypatch):
    import dulwich.repo

    root, _ = _git_repo(tmp_path)

    def broken(*args, **kwargs):
        raise ValueError("bad index")

    monkeypatch.setattr(dulwich.repo.Repo, "head", broken)
    assert head_revision(root) == ("cli", False)


def test_full_rebuild_with_layers_lists_changed_files(tmp_path):
    """Spec 2026-11-24 §4.5: with a layer on every build is full, and changed_files still names the edited files."""
    root = write_tree(tmp_path / "plain", FILES)
    missing = TsgConfig(executable=tmp_path / "no-such-tsg", tree_sitter_dir=tmp_path)
    live = LiveGraphBuilder(root, tmp_path / "g.db", layers=LayerConfigs(tsg=missing))
    assert live.run()["changed_files"] == []
    (root / "pkg/mod.py").write_bytes(FILES["pkg/mod.py"] + b"\nX = 1\n")
    edited = live.run()
    assert edited["mode"] == "cold" and edited["changed_files"] == ["pkg/mod.py"]
    (root / "pkg/new.py").write_text("Y = 2\n", encoding="utf-8")
    (root / "pkg/mod.py").unlink()
    assert live.run()["changed_files"] == ["pkg/mod.py", "pkg/new.py"]


def test_changed_files_survive_a_server_restart(tmp_path):
    """Final review: hosts start a new server per session; the first layered build must still name edited files."""
    root = write_tree(tmp_path / "plain", FILES)
    missing = TsgConfig(executable=tmp_path / "no-such-tsg", tree_sitter_dir=tmp_path)
    LiveGraphBuilder(root, tmp_path / "g.db", layers=LayerConfigs(tsg=missing)).run()
    (root / "pkg/mod.py").write_bytes(FILES["pkg/mod.py"] + b"\nX = 1\n")
    restarted = LiveGraphBuilder(root, tmp_path / "g.db", layers=LayerConfigs(tsg=missing))
    assert restarted.run()["changed_files"] == ["pkg/mod.py"]
