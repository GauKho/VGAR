import hashlib

import pytest

from vgar.evaluation.retrieval.dataset import SPLIT_POLICY, require_split, select_tasks, split_of

SHA = "a" * 40
PATCH = ("diff --git a/src/{n}/a.py b/src/{n}/a.py\n--- a/src/{n}/a.py\n+++ b/src/{n}/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
         "diff --git a/src/{n}/b.py b/src/{n}/b.py\n--- a/src/{n}/b.py\n+++ b/src/{n}/b.py\n@@ -1 +1 @@\n-y = 1\n+y = 2\n")
ONE_FILE = "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"


def rows(n=200, patch=None):
    return [{"instance_id": f"proj__repo-{i}", "repo": f"o/r{i % 3}", "base_commit": SHA, "problem_statement": "bug",
             "patch": patch or PATCH.format(n=i)} for i in range(n)]


def test_split_is_deterministic_and_matches_documented_formula():
    for iid in ("django__django-11099", "sympy__sympy-20590", "t-1", "t-2"):
        bucket = int(hashlib.sha256(iid.encode()).hexdigest()[:8], 16) % 100
        assert split_of(iid) == ("dev" if bucket < 40 else "heldout") == split_of(iid)
    assert split_of("t-2") == "dev" and split_of("t-1") == "heldout"
    assert SPLIT_POLICY.endswith("_v1")


def test_split_ratio_is_about_40_percent():
    ids = [f"proj__repo-{i}" for i in range(2000)]
    assert 0.35 < sum(split_of(i) == "dev" for i in ids) / len(ids) < 0.45


def test_select_tasks_only_returns_requested_split_and_reports_both():
    data = rows()
    dev, audit = select_tasks(data, 20, split="dev")
    held, _ = select_tasks(data, 20, split="heldout")
    assert {split_of(r["instance_id"]) for r in dev} == {"dev"}
    assert {split_of(r["instance_id"]) for r in held} == {"heldout"}
    assert not {r["instance_id"] for r in dev} & {r["instance_id"] for r in held}
    assert sum(audit["raw_by_split"].values()) == audit["raw_count"] == 200 and audit["split"] == "dev"
    assert dev == select_tasks(list(reversed(data)), 20, split="dev")[0]          # input order does not matter


def test_min_source_files_controls_single_file_tasks():
    data = rows(120, patch=ONE_FILE)
    with pytest.raises(ValueError, match="Only 0 eligible"):
        select_tasks(data, 5, split="dev", min_source_files=2)
    selected, audit = select_tasks(data, 5, split="dev", min_source_files=1)
    assert len(selected) == 5 and audit["min_source_files"] == 1


def test_require_split_blocks_heldout_and_forged_labels():
    dev_id, held_id = "t-2", "t-1"
    ok = {"split": "dev", "tasks": [{"instance_id": dev_id, "split": "dev"}]}
    require_split(ok)
    with pytest.raises(ValueError, match="allowed"):
        require_split({"split": "test", "tasks": ok["tasks"]})                       # legacy manifest
    with pytest.raises(ValueError, match="heldout"):
        require_split({"split": "dev", "tasks": [{"instance_id": held_id, "split": "dev"}]})   # forged label
    with pytest.raises(ValueError):
        require_split({"split": "dev", "tasks": [{"instance_id": dev_id}]})          # missing task label
    require_split({"split": "heldout", "tasks": [{"instance_id": held_id, "split": "heldout"}]}, allowed=("dev", "heldout"))
