"""RRF (secondary result) and Holm adjustment in the R1 summary (plan 2026-11-17 Task 6)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_r1_ablation as run
from fusion import bootstrap_p, fused_metrics, holm_adjust, ranked_lists, rrf


def test_rrf_scores_and_ties():
    assert rrf([["a", "b"], ["b", "c"]]) == ["b", "a", "c"]


def test_ranked_lists_dedupe_and_function_kinds():
    arm = {"ranked": [{"path": "p.py", "kind": "method", "function_id": "p.py::C.m"},
                      {"path": "p.py", "kind": "class", "function_id": "p.py::C"},
                      {"path": "q.py", "kind": "function", "function_id": "q.py::f"}]}
    assert ranked_lists(arm) == (["p.py", "q.py"], ["p.py::C.m", "q.py::f"])


def test_fused_metrics_empty_when_member_missing():
    task = {"arms": {"bm25": {"ranked": []}}, "gold": {"gold_files": [], "gold_functions": []}}
    assert fused_metrics(task, ("bm25", "neighbor")) == {}


def test_fused_metrics_values():
    row = lambda path, fid: {"path": path, "kind": "function", "function_id": fid}
    task = {"gold": {"gold_files": ["b.py"], "gold_functions": ["b.py::g"]},
            "arms": {"x": {"ranked": [row("a.py", "a.py::f"), row("b.py", "b.py::g")]},
                     "y": {"ranked": [row("b.py", "b.py::g"), row("a.py", "a.py::f")]}}}
    metrics = fused_metrics(task, ("x", "y"))
    assert metrics["file_recall@1"] == 0.0 and metrics["file_recall@5"] == 1.0     # tie a.py/b.py breaks by name
    assert metrics["function_mrr"] == 0.5



def test_fused_function_metrics_none_when_function_labels_incomplete():
    row = lambda path, fid: {"path": path, "kind": "function", "function_id": fid}
    task = {"gold": {"gold_files": ["b.py"], "gold_functions": ["b.py::g"], "function_labels_complete": False},
            "arms": {"x": {"ranked": [row("b.py", "b.py::g")]}, "y": {"ranked": [row("b.py", "b.py::g")]}}}
    metrics = fused_metrics(task, ("x", "y"))
    assert metrics["file_recall@1"] == 1.0
    assert metrics["function_recall@5"] is None and metrics["function_recall@10"] is None and metrics["function_mrr"] is None


def test_holm_adjust_hand_computed():
    assert holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})


def test_bootstrap_p_extremes():
    assert bootstrap_p([0.2] * 30, seed=0) == pytest.approx(2 / 2001) and bootstrap_p([0.0] * 30, seed=0) == 1.0


def test_primary_family_is_fixed_and_missing_cells_count_as_p_one(tmp_path):
    (tmp_path / "tasks").mkdir()
    for i, value in enumerate((0.0, 1.0)):
        _write_task(tmp_path / "tasks", f"t{i}", ("bm25", "grep", "neighbor", "task_trace_rt1"), value)
    family = run.summarize(tmp_path)["primary_family"]
    assert family["size"] == len(run.PRIMARY_PAIRS) * len(run.PRIMARY_METRICS)
    assert "task_trace_rt1 - embedding|file_recall@1" in family["missing"]


def test_heldout_requires_embedding_arm():
    with pytest.raises(SystemExit):
        run.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--allow-heldout"])
    args = run.parse_args(["root", "m.json", "--out", "o", "--allow-fallback-counter", "--allow-heldout",
                           "--embedding-model", "nomic-ai/CodeRankEmbed", "--embedding-revision", "a" * 40])
    assert args.allow_heldout


def _write_task(folder: Path, instance_id: str, arms: tuple[str, ...], value: float) -> None:
    row = {"path": "a.py", "kind": "function", "function_id": "a.py::f"}
    data = {"instance_id": instance_id, "status": "SUCCEEDED",
            "gold": {"gold_files": ["a.py"], "gold_functions": ["a.py::f"]},
            "arms": {arm: {"ranked": [row], "metrics": {"file_recall@1": value, "function_recall@5": value}}
                     for arm in arms}}
    (folder / f"{instance_id}.json").write_text(json.dumps(data), encoding="utf-8")


def test_summarize_old_run_keeps_tables(tmp_path):
    (tmp_path / "tasks").mkdir()
    for i, value in enumerate((0.0, 1.0)):
        _write_task(tmp_path / "tasks", f"t{i}", ("bm25", "grep", "neighbor", "task_trace_rt1"), value)
    summary = run.summarize(tmp_path)
    assert all(v is None for v in summary["means"]["embedding"].values())
    assert set(summary["secondary"]["means"]) == {"rrf_graph_bm25_neighbor", "rrf_bm25_neighbor"}
    assert summary["secondary"]["note"] == "analysis beyond the proposal"
    assert "task_trace_rt1 - embedding" not in summary["primary"]
    cell = summary["primary"]["task_trace_rt1 - bm25"]["file_recall@1"]
    assert set(cell) == {"mean_delta", "ci95", "p", "p_holm"}
