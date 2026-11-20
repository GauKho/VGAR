"""Paired comparison of two R1 runs, with the optional filter on a ready layer."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import compare_runs


def _task(r5: float, scip: str | None = None) -> dict:
    task = {"arms": {"task_trace_rt1": {"metrics": {"function_recall@5": r5}}}, "graph": {"build_seconds": 1.0}}
    if scip:
        task["layers_and_flags"] = {"layer_status": {"scip": {"status": scip, "reason": None}}}
    return task


def test_paired_delta_and_ready_filter():
    base = {"a": _task(1.0), "b": _task(0.0), "c": _task(1.0)}
    cand = {"a": _task(0.0, "ready"), "b": _task(1.0, "ready"), "c": _task(0.0, "failed")}
    every = compare_runs.compare(base, cand)["pairs"]["task_trace_rt1"]["function_recall@5"]
    assert every["n"] == 3 and every["wins"] == 1 and every["losses"] == 2
    ready = compare_runs.compare(base, cand, "scip")
    pair = ready["pairs"]["task_trace_rt1"]["function_recall@5"]
    assert ready["n_tasks"] == 2 and pair["delta"] == 0.0 and pair["wins"] == 1 and pair["losses"] == 1
    assert ready["layer_status"] == {"scip:ready": 2, "scip:failed": 1}


def test_compare_arms_within_one_run():
    run = {name: {"arms": {"task_trace_rt1": {"metrics": {"function_recall@5": base}},
                           "a_seed20": {"metrics": {"function_recall@5": arm}}},
                  "graph": {"build_seconds": 1.0}}
           for name, base, arm in (("a", 0.0, 1.0), ("b", 1.0, 1.0))}
    out = compare_runs.compare_arms(run, "task_trace_rt1", ["a_seed20"])
    pair = out["pairs"]["a_seed20"]["function_recall@5"]
    assert out["n_tasks"] == 2 and pair["delta"] == 0.5 and pair["wins"] == 1 and pair["losses"] == 0
    assert out["means"]["a_seed20"]["function_recall@5"] == [0.5, 1.0]


def test_min_gold_files_keeps_only_multi_file_tasks():
    def task(r5, files, frontier):
        return {"gold": {"gold_files": files}, "graph": {"build_seconds": 1.0},
                "arms": {"task_trace_rt1": {"metrics": {"function_recall@5": r5,
                                                        "packed_frontier_in_context": frontier}}}}
    base = {"one": task(0.0, ["a.py"], 0.0), "two": task(0.0, ["a.py", "b.py"], 0.5)}
    cand = {"one": task(1.0, ["a.py"], 1.0), "two": task(0.0, ["a.py", "b.py"], 1.0)}
    every = compare_runs.compare(base, cand)
    multi = compare_runs.compare(base, cand, min_gold_files=2)
    assert every["n_tasks"] == 2 and multi["n_tasks"] == 1
    assert multi["pairs"]["task_trace_rt1"]["function_recall@5"]["delta"] == 0.0
    assert multi["pairs"]["task_trace_rt1"]["packed_frontier_in_context"]["delta"] == 0.5
    arms = compare_runs.compare_arms({"two": {**cand["two"], "arms": {**cand["two"]["arms"],
                                     "a_e20": {"metrics": {"function_recall@5": 1.0}}}}, "one": cand["one"]},
                                     "task_trace_rt1", ["a_e20"], min_gold_files=2)
    assert arms["n_tasks"] == 1
