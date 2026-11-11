"""Summary of the R-A1 vs R-A2 run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_no_trace_ablation as run


def _task(directory: Path, instance_id: str, a1: float, a2: float) -> None:
    metrics = lambda value: {"file_recall@5": value, "function_recall@5": value, "file_mrr": value}
    data = {"instance_id": instance_id, "status": "SUCCEEDED",
            "arms": {"no_task_trace": {"metrics": metrics(a1)}, "task_trace": {"metrics": metrics(a2)}}}
    (directory / f"{instance_id}.json").write_text(json.dumps(data), encoding="utf-8")


def test_summary_pairs_no_trace_against_trace(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _task(tasks, "a", 0.0, 1.0)
    _task(tasks, "b", 1.0, 1.0)
    (tasks / "c.json").write_text(json.dumps({"instance_id": "c", "status": "FAILED"}), encoding="utf-8")
    summary = run.summarize(tmp_path)
    assert summary["succeeded"] == 2 and summary["failed"] == ["c"]
    assert summary["means"]["task_trace"]["file_recall@5"] == 1.0
    assert summary["means"]["no_task_trace"]["file_recall@5"] == 0.5
    pair = summary["no_task_trace_minus_task_trace"]["file_recall@5"]
    assert pair["n"] == 2 and pair["mean_delta"] == -0.5 and pair["losses"] == 1
