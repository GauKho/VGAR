"""Level 1 (formulas hold) and level 2 (where each gold function is lost) checks of the A2 retrieval."""
from baseline.verify_retrieval import check_path_confidence, verify_task
from vgar.evaluation.retrieval.scoring import FALLBACK_COUNTER_LABEL, bytes_div4_counter
from vgar.graph.builder import PythonGraphBuilder

FILES = {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n",
         "pkg/b.py": "from pkg.a import f\n\n\ndef g():\n    return f()\n",
         "pkg/c.py": "def h():\n    return 0\n"}


def _hunk(path, line, old, new):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -{line} +{line} @@\n-{old}\n+{new}\n"


ROW = {"instance_id": "o__r-1", "repo": "o/r", "base_commit": "c" * 40,
       "problem_statement": "g in pkg/b.py returns the wrong value because f returns 1",
       "patch": _hunk("pkg/a.py", 2, "    return 1", "    return 2") + _hunk("pkg/c.py", 2, "    return 0", "    return 3")}


def _verify(tmp_path):
    tree = tmp_path / "tree"
    for path, text in FILES.items():
        (tree / path).parent.mkdir(parents=True, exist_ok=True)
        (tree / path).write_text(text, encoding="utf-8")
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    return verify_task(ROW, dict(FILES), tree, document, counter=bytes_div4_counter, label=FALLBACK_COUNTER_LABEL,
                       budget_tokens=4000)


def test_level1_formulas_hold_on_the_real_retriever(tmp_path):
    checks = _verify(tmp_path)["checks"]
    assert checks["candidates"] > 0
    for name in ("path_confidence", "graph_distance", "edge_confidence", "relevance_score"):
        assert checks[name]["mismatch"] == 0 and checks[name]["checked"] > 0, (name, checks[name])


def test_level2_puts_each_gold_function_in_one_stage(tmp_path):
    funnel = _verify(tmp_path)["funnel"]
    stages = {row["gold_function"].split("::")[-1]: row["stage"] for row in funnel}
    assert stages["pkg.a.f"] == "packed"
    assert stages["pkg.c.h"] == "no_anchor_in_file"   # nothing in the issue points at pkg/c.py and no edge leads there
    assert all(row["stage"] in {"packed", "candidate_not_packed", "walk_cap", "no_path", "no_anchor_in_file",
                                "not_in_graph"} for row in funnel)


def test_wrong_path_confidence_is_detected():
    adjacency = {"a": [("b", 0.9, "CALLS")], "b": [("c", 0.6, "CALLS")]}
    good = {"node_id": "c", "confidence": 0.6, "graph_rationale": ["TASK_ANCHOR", "CALLS:a->b", "CALLS:b->c"]}
    bad = dict(good, confidence=0.9)
    assert check_path_confidence(good, adjacency, {"a": 0.8}) is True
    assert check_path_confidence(bad, adjacency, {"a": 0.8}) is False
    assert check_path_confidence(dict(good, confidence=0.5), adjacency, {"a": 0.5}) is True   # anchor caps it


def test_summary_covers_every_task_file_in_the_run_directory(tmp_path):
    import json

    from baseline.verify_retrieval import summary_from_dir

    tasks = tmp_path / "tasks"
    tasks.mkdir()
    base = {"cross_file": False, "traversal_limited": False,
            "checks": {name: {"checked": 1, "mismatch": 0, "unverifiable": 0}
                       for name in ("path_confidence", "graph_distance", "edge_confidence", "relevance_score")}}
    (tasks / "a.json").write_text(json.dumps(base | {"instance_id": "a", "funnel": [{"stage": "packed"}]}))
    (tasks / "b.json").write_text(json.dumps(base | {"instance_id": "b", "funnel": [{"stage": "no_path"}]}))
    (tasks / "c.json").write_text(json.dumps({"instance_id": "c", "error": "boom"}))
    summary = summary_from_dir(tmp_path)
    assert summary["tasks"] == 2 and summary["errors"] == ["c"]
    assert summary["funnel"]["packed"] == 1 and summary["funnel"]["no_path"] == 1
