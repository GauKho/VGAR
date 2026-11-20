"""T2 paired report: graph_v0 vs base per task with a bootstrap CI, all tasks and multi-file tasks."""
import json

from baseline.nav.nav_paired import report


def _write(root, arm, instance, recall, cross_file, files_read):
    path = root / arm / f"{instance}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "instance_id": instance, "status": "OK", "answer": {"files": ["a.py"], "functions": ["a.py::f"]},
        "tool_calls": [{"name": "grep"}], "usage": {"seconds": 10.0},
        "metrics": {"status": "OK", "file_recall@1": recall, "files_read": files_read, "cross_file": cross_file}}),
        encoding="utf-8")


def test_report_pairs_tasks_present_in_both_arms_and_splits_multi_file(tmp_path):
    _write(tmp_path, "base", "t1", 0.0, True, 3)
    _write(tmp_path, "graph_v0", "t1", 1.0, True, 1)
    _write(tmp_path, "base", "t2", 1.0, False, 2)
    _write(tmp_path, "graph_v0", "t2", 1.0, False, 2)
    _write(tmp_path, "base", "only_base", 1.0, False, 2)   # no graph_v0 result: not a pair
    text = report(tmp_path)
    assert "All paired tasks (n=2)" in text and "Multi-file tasks (>= 2 gold files) (n=1)" in text
    assert "| file_recall@1 | 0.500 | 1.000 | +0.500 [" in text
    assert "| files_read | 2.500 | 1.500 | -1.000 [" in text
