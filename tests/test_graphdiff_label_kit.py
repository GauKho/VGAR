"""L4-7 labelling kit: seeded commit sample, development/evaluation split, labelling sheet."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest
from git_fixture import linear_repo

from vgar.graph.history import CommitChange, CommitHistory, FileChange, FileVersion

pytest.importorskip("dulwich")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "graphdiff_label_kit.py"


def _kit():
    spec = importlib.util.spec_from_file_location("graphdiff_label_kit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _commit(number: int, py_files: int, subject: str, parents: int = 1) -> CommitChange:
    files = tuple(FileChange("modify", FileVersion(f"m{i}.py", "0" * 40, 0o100644),
                             FileVersion(f"m{i}.py", "1" * 40, 0o100644)) for i in range(py_files))
    files += (FileChange("modify", FileVersion("README.md", "0" * 40, 0o100644),
                         FileVersion("README.md", "1" * 40, 0o100644)),)
    return CommitChange(f"{number:040x}", tuple(f"{p:040x}" for p in range(parents)), number, subject, files)


def _windows(count: int = 300) -> dict[str, list[CommitHistory]]:
    commits = []
    for number in range(1, count + 1):
        subject = "Fix bug in parser" if number % 3 == 0 else "Add feature"
        commits.append(_commit(number, (number % 10) + 1, subject))
    commits.append(_commit(10_001, 2, "Merge branch", parents=2))
    commits.append(_commit(10_002, 11, "Fix huge refactor"))
    commits.append(_commit(10_003, 0, "Fix docs only"))
    return {"o/r": [CommitHistory("f" * 40, 400, tuple(commits))]}


def test_sample_is_seeded_and_reproducible():
    kit = _kit()
    first, second = kit.sample_commits(_windows(), seed=7), kit.sample_commits(_windows(), seed=7)
    assert first == second and len(first) == 100
    assert kit.sample_commits(_windows(), seed=8) != first


def test_sample_excludes_merges_and_large_commits():
    ids = {row["commit"] for row in _kit().sample_commits(_windows(), seed=0, target=400)}
    assert not ids & {f"{n:040x}" for n in (10_001, 10_002, 10_003)}


def test_fix_share_within_bounds():
    rows = _kit().sample_commits(_windows(), seed=0)
    share = sum(row["is_fix"] for row in rows) / len(rows)
    assert 0.6 <= share <= 0.7
    assert {row["stratum"] for row in rows} == {"1", "2-3", "4-10"}


def test_commit_shared_by_two_task_windows_is_sampled_once():
    window = _windows()["o/r"][0]
    rows = _kit().sample_commits({"o/r": [window, window]}, seed=0, target=400)
    assert len({row["commit"] for row in rows}) == len(rows)


def test_split_is_by_commit_and_40_60():
    rows = _kit().sample_commits(_windows(), seed=0)
    dev = sum(row["split"] == "dev" for row in rows)
    assert dev == 40 and {row["split"] for row in rows} == {"dev", "eval"}


CART = b"class Cart:\n    def total(self, items):\n        return sum(items)\n\n\ndef helper(x):\n    return x + 1\n"


def _clone(tmp_path: Path) -> tuple[Path, list[str]]:
    git_root = tmp_path / "clones"
    ids = linear_repo(git_root / "o__r", [("base", {"src/shop/cart.py": CART}),
                                          ("Fix total", {"src/shop/cart.py": CART.replace(b"sum(items)", b"sum(items) or 0")
                                                         .replace(b"x + 1", b"x + 1  # note"),
                                                         "tests/test_cart.py": b"def test_x():\n    assert 1\n"})])
    return git_root, ids


def test_sheet_rows_and_no_prediction_columns(tmp_path):
    kit = _kit()
    git_root, ids = _clone(tmp_path)
    sample = [{"repo": "o/r", "commit": ids[1], "subject": "Fix total", "split": "eval", "is_fix": True, "stratum": "2-3"}]
    rows = kit.sheet_rows(sample, git_root)
    sheet = tmp_path / "sheet.csv"
    kit.write_sheet(rows, sheet)
    with sheet.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        data = list(reader)
    assert reader.fieldnames == kit.COLUMNS
    assert not {"validated", "confidence", "edit_type", "is_refactoring"} & set(reader.fieldnames)
    assert {row["entity"] for row in data} == {"shop.cart.Cart.total", "shop.cart.helper"}  # test file excluded
    total = next(row for row in data if row["entity"] == "shop.cart.Cart.total")
    assert "sum(items) or 0" in total["after_code"] and "sum(items)" in total["before_code"]
    assert total["node_id"] == "vgar:o__r:python:method:src/shop/cart.py:shop.cart.Cart.total"
    assert total["diff_link"] == f"https://github.com/o/r/commit/{ids[1]}" and total["label"] == ""


def test_missing_clone_is_reported_not_silent(tmp_path):
    kit = _kit()
    git_root, ids = _clone(tmp_path)
    manifest = {"tasks": [{"instance_id": "a", "repo": "o/r", "base_commit": ids[1]},
                          {"instance_id": "b", "repo": "o/missing", "base_commit": ids[1]},
                          {"instance_id": "c", "repo": "o/r", "base_commit": "e" * 40}]}
    windows, skipped = kit.windows_from_manifest(manifest, git_root, window=50)
    assert set(windows) == {"o/r"} and len(windows["o/r"]) == 1
    assert {(row["instance_id"], row["reason"].split(":")[0]) for row in skipped} == \
        {("b", "clone missing"), ("c", "history unavailable")}
