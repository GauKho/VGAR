"""Summary of the full R1 run: every pair of the spec is reported."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

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
    assert set(summary["pairs"]) == {f"{c} - {b}" for c, b in run.PAIRS} and summary["pairs_missing"] == []
    pair = summary["pairs"]["task_trace - no_task_trace"]["file_recall@5"]
    assert pair["n"] == 2 and pair["mean_delta"] == 0.5 and pair["wins"] == 1
    assert summary["pairs"]["task_trace - no_task_trace"]["component_recall@5"]["mean_delta"] == 0.5
    assert summary["means"]["task_trace"]["file_recall@5"] == 1.0


def test_summary_lists_pairs_without_shared_tasks_as_missing(tmp_path):
    (tmp_path / "tasks").mkdir()
    arms = [arm for arm in run.ALL_ARMS if arm != "embedding"]   # a run without --embedding-model
    _write(tmp_path / "tasks", "a", {arm: 0.5 for arm in arms})
    summary = run.summarize(tmp_path)
    embedding = {f"{c} - {b}" for c, b in run.PAIRS if "embedding" in (c, b)}
    assert set(summary["pairs_missing"]) == embedding and not embedding & set(summary["pairs"])
    assert set(summary["pairs"]) | embedding == {f"{c} - {b}" for c, b in run.PAIRS}


def test_scip_and_lsp_options_turn_on_the_resolver_layers(tmp_path):
    scip, lsp = tmp_path / "index.js", tmp_path / "langserver.index.js"
    base = ["root", "m.json", "--out", "o", "--allow-fallback-counter"]
    layers = run.run_layers(run.parse_args(base + ["--scip-entry", str(scip), "--scip-timeout", "2700",
                                                   "--lsp-entry", str(lsp), "--lsp-max-requests", "2000"]))
    assert str(scip.resolve()) in layers.scip.command and layers.scip.timeout_seconds == 2700
    assert str(lsp.resolve()) in layers.lsp.command and layers.lsp.max_requests == 2000
    assert not run.run_layers(run.parse_args(base)).any_optional


def test_graph_build_receives_scip_and_lsp(tmp_path, monkeypatch):
    import vgar.graph.builder as builder_module
    from vgar.graph.layer_config import LayerConfigs

    seen = {}

    class Builder:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def build(self, tree):
            return {"nodes": [], "edges": [], "graph_version": "v", "statistics": {"resolver": {}}}

    monkeypatch.setattr(builder_module, "PythonGraphBuilder", Builder)
    tree = tmp_path / "tree"
    tree.mkdir()
    row = {"repo": "o/r", "base_commit": "c" * 40}
    run.runner.load_or_build_graph(tmp_path, row, tree, rebuild=True, builder_hash="h",
                                   layers=LayerConfigs(scip="SCIP", lsp="LSP"))
    assert seen["scip"] == "SCIP" and seen["lsp"] == "LSP"


def test_arms_option_runs_only_those_graph_arms_and_no_text():
    base = ["root", "m.json", "--out", "o", "--allow-fallback-counter"]
    assert run.arms_for(run.parse_args(base + ["--arms", "task_trace_rt1,task_trace"])) == (("task_trace_rt1", "task_trace"), False)
    assert run.arms_for(run.parse_args(base)) == (run.GRAPH_ARMS, True)
    with pytest.raises(SystemExit):
        run.parse_args(base + ["--arms", "no_such_arm"])


def test_i1_multifile_summary_compares_graph_with_same_directory():
    import run_i1_multifile

    rows = [{"others": ["b.py", "c.py"], "reached": ["b.py"], "same_dir_reached": [], "region_files": 4,
             "same_dir_files": 2},
            {"others": ["a.py"], "reached": [], "same_dir_reached": ["a.py"], "region_files": 0, "same_dir_files": 6}]
    summary = run_i1_multifile.summarize(rows)
    assert summary["graph_reach"] == 0.25 and summary["same_dir_reach"] == 0.5
    assert summary["graph_any"] == 1 and summary["same_dir_any"] == 1 and summary["median_graph_region_files"] == 2
    assert run_i1_multifile.summarize([])["graph_reach"] is None
