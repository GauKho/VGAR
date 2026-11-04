"""Spec 2026-11-03-m3-w12-trace §4 E6: which VGAR code a run used, including uncommitted files."""
import subprocess

from vgar.observability.code_state import code_label, code_state


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_code_state_lists_dirty_files(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-q", "-m", "c")
    (tmp_path / "a.py").write_text("x = 2\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y = 1\n", encoding="utf-8")
    (tmp_path / "results").mkdir()
    (tmp_path / "results/x.json").write_text("{}", encoding="utf-8")
    state = code_state(tmp_path)
    assert len(state["head"]) == 40
    assert [d["path"] for d in state["dirty"]] == ["a.py", "b.py"]
    assert all(len(d["sha256_12"]) == 12 for d in state["dirty"])
    assert code_label(state) == state["head"][:7] + " + dirty 2 files"


def test_code_state_outside_git_is_none(tmp_path):
    assert code_state(tmp_path) is None
    assert code_label(None) == "unknown"


def test_clean_label_is_the_short_head():
    assert code_label({"head": "a" * 40, "dirty": []}) == "a" * 7


def test_missing_git_binary_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert code_state(tmp_path) is None
