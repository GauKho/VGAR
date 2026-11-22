"""Layer report: each profile against the previous one present (spec 2026-11-19 §6)."""
import json

from baseline.report import g1_table, layer_table


def _task(path, name, files, a1, a2, extra=None):
    arms = {"A1": {"metrics": {"function_recall@5": a1}}, "A2": {"metrics": {"function_recall@5": a2}}}
    arms.update(extra or {})
    path.write_text(json.dumps({"instance_id": name, "status": "SUCCEEDED", "gold": {"gold_files": files},
                                "arms": arms}), encoding="utf-8")


def _run(tmp_path):
    tasks = tmp_path / "run" / "tasks"
    tasks.mkdir(parents=True)
    _task(tasks / "a.json", "a", ["x.py"], 0.0, 1.0)
    _task(tasks / "b.json", "b", ["x.py", "y.py"], 0.0, 0.0, {"full": {"metrics": {"function_recall@5": 1.0}}})
    (tasks / "c.json").write_text(json.dumps({"instance_id": "c", "status": "ERROR", "reason": "boom"}),
                                  encoding="utf-8")
    return tmp_path / "run"


def test_each_profile_is_compared_with_the_previous_one_on_shared_tasks(tmp_path):
    table = layer_table(_run(tmp_path), ["function_recall@5"])
    a2 = next(line for line in table.splitlines() if line.startswith("| A2 "))
    assert "0.500" in a2 and "+0.500" in a2 and "A1" in a2
    full = next(line for line in table.splitlines() if line.startswith("| full "))
    assert "n=1" in full and "1 ERROR" in table


def test_multi_file_stratum_keeps_only_tasks_with_two_gold_files(tmp_path):
    table = layer_table(_run(tmp_path), ["function_recall@5"], min_gold_files=2)
    a2 = next(line for line in table.splitlines() if line.startswith("| A2 "))
    assert "n=1" in a2 and "+0.000" in a2


def test_g1_table_reads_call_edge_precision_and_recall(tmp_path):
    g1 = tmp_path / "g1.json"
    edge = {"precision": 1.0, "recall": 0.41818, "precision_ci95": [1.0, 1.0], "recall_ci95": [0.31, 0.53]}
    g1.write_text(json.dumps({"configurations": {"static": {"status": "ok", "calls": {
        "calls_only": edge, "with_may_call": dict(edge, precision=0.4855072, recall=0.609)}}, "scip_tsg": {
        "status": "failed"}}}), encoding="utf-8")
    table = g1_table(g1)
    assert "| static | 1.000 | 0.418" in table and "0.486" in table and "scip_tsg" in table and "failed" in table


def test_layer_table_compares_a1_arch_with_a1_and_keeps_a2_against_a1(tmp_path):
    tasks = tmp_path / "run" / "tasks"
    tasks.mkdir(parents=True)
    _task(tasks / "a.json", "a", ["x.py"], 0.0, 1.0, {"A1_arch": {"metrics": {"function_recall@5": 0.5}}})
    table = layer_table(tmp_path / "run", ["function_recall@5"])
    rows = {line.split("|")[1].strip(): line.split("|")[2].strip() for line in table.splitlines()
            if line.startswith("| A")}
    assert rows["A1_arch"] == "A1" and rows["A2"] == "A1"
