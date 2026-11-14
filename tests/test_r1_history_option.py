"""R1 runner history option (proposal line 760 downstream on retrieval): none / raw / graphdiff."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def r1():
    spec = importlib.util.spec_from_file_location("run_r1_ablation", ROOT / "ablation_matrix" / "run_r1_ablation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_history_none_keeps_default_arms(r1):
    args = r1.parse_args(["root", "manifest.json", "--out", "o", "--allow-fallback-counter"])
    assert args.history == "none" and r1.arms_for(args) == (r1.GRAPH_ARMS, True)
    args = r1.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--history", "raw",
                          "--git-root", "clones"])
    assert r1.arms_for(args) == (("task_trace",), False)


def test_history_needs_git_root(r1):
    with pytest.raises(SystemExit):
        r1.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--history", "graphdiff"])


def test_graphdiff_counts_are_validated_commits_per_node(r1):
    edits = [SimpleNamespace(commit_id="c1", node_id="n1", validated=True),
             SimpleNamespace(commit_id="c1", node_id="n1", validated=True),   # same commit counts once
             SimpleNamespace(commit_id="c2", node_id="n1", validated=True),
             SimpleNamespace(commit_id="c2", node_id="n2", validated=False),  # not validated
             SimpleNamespace(commit_id="c3", node_id="n3", validated=True)]
    assert r1.graphdiff_counts(edits) == {"n1": 2, "n3": 1}


def test_missing_clone_raises_history_unavailable(r1, tmp_path):
    row = {"repo": "o/r", "base_commit": "a" * 40}
    with pytest.raises(r1.HistoryUnavailable):
        r1.history_counts("raw", row, {}, git_root=tmp_path, max_commits=50)


def test_raw_counts_come_from_the_task_window(r1, tmp_path):
    from git_fixture import linear_repo

    ids = linear_repo(tmp_path / "o__r", [("a", {"x.py": b"A = 1\n"}), ("b", {"x.py": b"A = 2\n", "y.py": b""}),
                                          ("later", {"x.py": b"A = 3\n", "y.py": b"B = 1\n"})])
    counts, label = r1.history_counts("raw", {"repo": "o/r", "base_commit": ids[1]}, {}, git_root=tmp_path,
                                      max_commits=50)
    assert counts == {"x.py": 2, "y.py": 1} and ids[1] in label


def _task(folder: Path, instance: str, values: dict[str, float]) -> None:
    (folder / "tasks").mkdir(parents=True, exist_ok=True)
    data = {"instance_id": instance, "status": "SUCCEEDED", "arms": {"task_trace": {"metrics": values}}}
    (folder / "tasks" / f"{instance}.json").write_text(json.dumps(data), encoding="utf-8")


def test_compare_history_runs_known_deltas(r1, tmp_path):
    for name, (a, b) in {"none": (0.0, 0.5), "raw": (0.5, 0.5), "graphdiff": (1.0, 0.0)}.items():
        _task(tmp_path / name, "t1", {"file_recall@5": a, "function_mrr": 0.2})
        _task(tmp_path / name, "t2", {"file_recall@5": b, "function_mrr": 0.2})
    result = r1.compare_history_runs(tmp_path / "none", tmp_path / "raw", tmp_path / "graphdiff")
    assert result["means"]["graphdiff"]["file_recall@5"] == 0.5
    delta = result["pairs"]["graphdiff - none"]["file_recall@5"]
    assert (delta["n"], delta["mean_delta"], delta["wins"], delta["losses"]) == (2, 0.25, 1, 1)
    assert result["pairs"]["raw - none"]["function_mrr"]["mean_delta"] == 0.0
