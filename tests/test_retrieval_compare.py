"""Tune-step comparison (E3, plan Task 4): paired bootstrap between two graph retrieval runs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vgar.evaluation.retrieval.compare import compare_graph_runs

CONFIG = {"manifest_hash": "sha256:m", "budget_tokens": 8000, "counter_label": "c", "scoring_version": "s",
          "snippet_policy": {"max_snippet_lines": 80}}


def _run(directory: Path, recalls: dict[str, float | None], *, ranking_hash: str, manifest: str = "sha256:m") -> Path:
    (directory / "tasks").mkdir(parents=True)
    rows = []
    for instance_id, recall in recalls.items():
        status = "FAILED" if recall is None else "SUCCEEDED"
        rows.append({"instance_id": instance_id, "status": status})
        if recall is not None:
            metrics = {"file_recall@5": recall, "function_recall@5": recall / 2, "file_mrr": recall}
            (directory / "tasks" / f"{instance_id}.json").write_text(
                json.dumps({"arms": {"graph": {"metrics": metrics}}}), encoding="utf-8")
    config = {**CONFIG, "manifest_hash": manifest, "retrieval": {"ranking_config_hash": ranking_hash}}
    (directory / "result.json").write_text(json.dumps({"complete": True, "config": config, "task_results": rows}),
                                           encoding="utf-8")
    return directory


def test_consistent_gain_is_accepted(tmp_path):
    # T1
    ids = [f"t{i}" for i in range(10)]
    previous = _run(tmp_path / "a", {i: 0.2 for i in ids}, ranking_hash="sha256:old")
    candidate = _run(tmp_path / "b", {i: 0.4 for i in ids}, ranking_hash="sha256:new")

    result = compare_graph_runs(previous, candidate)

    assert result["verdict"] == "ACCEPT"
    assert result["n"] == 10 and result["wins"] == 10 and result["losses"] == 0
    assert (result["previous_hash"], result["candidate_hash"]) == ("sha256:old", "sha256:new")


def test_task_failed_in_one_run_is_excluded_from_pairing(tmp_path):
    # T2 (Review Focus 4): a timeout in either run must not enter the paired deltas.
    ids = [f"t{i}" for i in range(10)]
    previous = _run(tmp_path / "a", {i: 0.2 for i in ids}, ranking_hash="sha256:old")
    candidate = _run(tmp_path / "b", {**{i: 0.4 for i in ids}, "t9": None}, ranking_hash="sha256:new")

    result = compare_graph_runs(previous, candidate)

    assert result["n"] == 9
    assert result["excluded"] == ["t9"]


def test_mixed_changes_with_no_clear_gain_are_rejected(tmp_path):
    # T3
    ids = [f"t{i}" for i in range(10)]
    previous = _run(tmp_path / "a", {i: 0.5 for i in ids}, ranking_hash="sha256:old")
    candidate = _run(tmp_path / "b", {i: (0.9 if n % 2 else 0.1) for n, i in enumerate(ids)}, ranking_hash="sha256:new")

    assert compare_graph_runs(previous, candidate)["verdict"] == "REJECT"


def test_runs_on_different_manifests_are_refused(tmp_path):
    # T4
    previous = _run(tmp_path / "a", {"t0": 0.2}, ranking_hash="sha256:old")
    candidate = _run(tmp_path / "b", {"t0": 0.4}, ranking_hash="sha256:new", manifest="sha256:other")

    with pytest.raises(ValueError, match="manifest_hash"):
        compare_graph_runs(previous, candidate)
