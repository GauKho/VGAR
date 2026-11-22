"""T1: profiles scored on one shared graph per build (spec 2026-11-19 §7)."""
import json

from baseline import run_offline
from baseline.frontier_v2 import frontier_core_v2
from vgar.evaluation.retrieval.scoring import (
    FALLBACK_COUNTER_LABEL,
    CorpusIndex,
    bytes_div4_counter,
)
from vgar.graph.builder import PythonGraphBuilder

FILES = {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n",
         "pkg/b.py": "from pkg.a import f\n\n\ndef g():\n    return f()\n"}


def _hunk(path, line, old, new):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -{line} +{line} @@\n-{old}\n+{new}\n"


ROW = {"instance_id": "o__r-1", "repo": "o/r", "base_commit": "c" * 40,
       "problem_statement": "g returns the wrong value because f returns 1",
       "patch": _hunk("pkg/a.py", 2, "    return 1", "    return 2") + _hunk("pkg/b.py", 5, "    return f()",
                                                                          "    return f() + 1")}


def _tree(tmp_path):
    tree = tmp_path / "tree"
    for path, text in FILES.items():
        (tree / path).parent.mkdir(parents=True, exist_ok=True)
        (tree / path).write_text(text, encoding="utf-8")
    return tree


def _evaluate(tmp_path, profiles, with_text=True):
    tree = _tree(tmp_path)
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    return run_offline.evaluate_profiles(ROW, dict(FILES), tree, {"base": document}, profiles,
                                         counter=bytes_div4_counter, label=FALLBACK_COUNTER_LABEL,
                                         budget_tokens=4000, with_text=with_text)


def test_profiles_share_one_gold_with_frontier_v2_and_report_served_context(tmp_path):
    out = _evaluate(tmp_path, ["P0", "A1", "A2", "A3"])
    assert set(out["arms"]) == {"P0", "A1", "A2", "A3", "bm25", "grep", "neighbor"}
    assert out["gold"]["frontier_functions"] == frontier_core_v2(ROW["patch"], out["gold"], CorpusIndex(dict(FILES)))
    assert "native_frontier_in_context" in out["arms"]["A2"]["metrics"]
    assert "function_recall@5" in out["arms"]["A2"]["metrics"]
    assert out["cross_file"] is True and set(out["impact"]) == {"base"}


def test_ranking_is_frozen_before_gold(tmp_path, monkeypatch):
    order = []
    rank, gold = run_offline.graph_rank, run_offline.extract_gold
    monkeypatch.setattr(run_offline, "graph_rank", lambda *a, **k: order.append("rank") or rank(*a, **k))
    monkeypatch.setattr(run_offline, "extract_gold", lambda *a, **k: order.append("gold") or gold(*a, **k))
    _evaluate(tmp_path, ["A1", "A2"])
    assert order == ["rank", "rank", "gold"]


def test_resume_computes_only_missing_profiles(tmp_path, monkeypatch):
    tree = _tree(tmp_path)
    monkeypatch.setattr(run_offline, "prepare_task", lambda root, row: (dict(FILES), tree))
    out_dir = tmp_path / "out"
    (out_dir / "tasks").mkdir(parents=True)
    previous = {"instance_id": ROW["instance_id"], "status": "SUCCEEDED", "gold": {}, "impact": {}, "graphs": {},
                "arms": {name: {"metrics": {"sentinel": 1}} for name in ("P0", "A1", "bm25", "grep", "neighbor")}}
    (out_dir / "tasks" / f"{ROW['instance_id']}.json").write_text(json.dumps(previous), encoding="utf-8")
    result = run_offline.run_offline_task(tmp_path, ROW, ["P0", "A1", "A2"], {}, out_dir=out_dir,
                                          graphs_dir=tmp_path / "graphs", builder_hash="h", budget_tokens=4000,
                                          resume=True)
    assert result["arms"]["P0"]["metrics"] == {"sentinel": 1} and result["arms"]["bm25"]["metrics"] == {"sentinel": 1}
    assert "function_recall@5" in result["arms"]["A2"]["metrics"]
    saved = json.loads((out_dir / "tasks" / f"{ROW['instance_id']}.json").read_text(encoding="utf-8"))
    assert set(saved["arms"]) == {"P0", "A1", "A2", "bm25", "grep", "neighbor"}


def test_arm_flags_reach_every_graph_arm(tmp_path):
    tree = _tree(tmp_path)
    document = PythonGraphBuilder(repo_key="o__r", repository_revision="c" * 40).build(tree)
    out = run_offline.evaluate_profiles(ROW, dict(FILES), tree, {"base": document}, ["A1", "A2"],
                                        counter=bytes_div4_counter, label=FALLBACK_COUNTER_LABEL, budget_tokens=4000,
                                        with_text=False, arm_flags={"max_candidates": 7})
    assert {out["arms"][name]["diagnostics"]["retrieval_config"]["max_candidates"] for name in ("A1", "A2")} == {7}


def test_metrics_record_candidate_count_and_traversal_flag(tmp_path):
    metrics = _evaluate(tmp_path, ["A2"], with_text=False)["arms"]["A2"]["metrics"]
    assert metrics["candidate_count"] >= 1 and isinstance(metrics["traversal_limited"], bool)


def test_unknown_arm_flag_is_rejected_before_any_task(tmp_path, capsys):
    import pytest
    with pytest.raises(SystemExit):
        run_offline.main([str(tmp_path), str(tmp_path / "m.json"), "--out", str(tmp_path / "out"),
                          "--arm-flags", '{"no_such_field": 1}'])
    assert "unknown RetrievalConfig field" in capsys.readouterr().err
