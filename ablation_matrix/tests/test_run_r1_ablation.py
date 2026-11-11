"""Summary of the full R1 run: every pair of the spec is reported."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_r1_ablation as run


def _write(directory: Path, instance_id: str, values: dict[str, float]) -> None:
    arms = {arm: {"metrics": {"file_recall@5": value, "component_recall@5": value}} for arm, value in values.items()}
    (directory / f"{instance_id}.json").write_text(json.dumps({"instance_id": instance_id, "status": "SUCCEEDED",
                                                               "arms": arms}), encoding="utf-8")


def test_summary_reports_every_pair(tmp_path):
    (tmp_path / "tasks").mkdir()
    arms = run.ALL_ARMS
    _write(tmp_path / "tasks", "a", {arm: 0.0 for arm in arms} | {"task_trace": 1.0})
    _write(tmp_path / "tasks", "b", {arm: 1.0 for arm in arms})
    summary = run.summarize(tmp_path)
    assert set(summary["pairs"]) == {f"{c} - {b}" for c, b in run.PAIRS}
    pair = summary["pairs"]["task_trace - no_task_trace"]["file_recall@5"]
    assert pair["n"] == 2 and pair["mean_delta"] == 0.5 and pair["wins"] == 1
    assert summary["pairs"]["task_trace - no_task_trace"]["component_recall@5"]["mean_delta"] == 0.5
    assert summary["means"]["task_trace"]["file_recall@5"] == 1.0
