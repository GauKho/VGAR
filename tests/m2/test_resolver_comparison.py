"""Paired-input integrity, missing outcomes, native range scoring, and cache isolation."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from vgar.evaluation.retrieval.resolver_comparison import native_context_metrics, paired_summary, resolver_cache_key
from vgar.evaluation.retrieval.scoring import CorpusIndex


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("graph_eval_runner", ROOT / "scripts/run_graph_retrieval.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def outcome(value, active="static"):
    return {"status": "SUCCEEDED", "instance_id": "example-1", "base_commit": "commit", "query_hash": "query",
            "patch_hash": "patch", "corpus_hash": "corpus", "comparison_binding": "config",
            "source_tree": {"tree_hash": "tree"},
            "graph": {"build_seconds": 1, "source_digest": "source", "resolver_report": {"active": active}},
            "arms": {arm: {"metrics": {"quality": value}} for arm in ("graph", "graph_f2p")}}


def test_failures_and_null_labels_keep_denominators():
    pairs = [{"instance_id": "example-1", "static": outcome(0), "scip": outcome(1, "scip")},
             {"instance_id": "example-2", "static": outcome(1), "scip": {"status": "FAILED"}},
             {"instance_id": "example-3", "static": outcome(None), "scip": outcome(None, "scip")}]
    summary = paired_summary(pairs, ["quality"])
    assert summary["attempted_pairs"] == 3
    assert summary["successful_pairs"] == 2
    assert len(summary["failed_pairs"]) == 1
    metric = summary["metrics_by_arm"]["graph"]["quality"]
    assert metric["eligible_pairs"] == 1
    assert metric["mean_delta_scip_minus_static"] == 1


@pytest.mark.parametrize("key", ["query_hash", "patch_hash", "base_commit", "corpus_hash", "comparison_binding"])
def test_rejects_mismatched_pairs(key):
    left, right = outcome(0), outcome(1, "scip")
    right[key] = "different"
    with pytest.raises(ValueError, match="mismatch"):
        paired_summary([{"instance_id": "example-1", "static": left, "scip": right}], ["quality"])


@pytest.mark.parametrize("mutation", ["fallback", "source"])
def test_rejects_fallback_and_stale_actual_source(mutation):
    right = outcome(1, "scip")
    if mutation == "fallback":
        right["graph"]["resolver_report"]["active"] = "static"
    else:
        right["graph"]["source_digest"] = "different"
    with pytest.raises(ValueError):
        paired_summary([{"instance_id": "example-1", "static": outcome(0), "scip": right}], ["quality"])


def test_native_context_requires_entire_utf8_range_but_accepts_class_container():
    corpus = CorpusIndex({"src/a.py": "class A:\n    def f(self):\n        return '🚀'\n"})
    definition = corpus.definitions["src/a.py"][0]
    gold = {"gold_files": ["src/a.py"], "gold_functions": [definition["parent_id"]], "function_labels_complete": True}
    context = {"items": [{"path": "src/a.py", "range": {"start_line": 1, "start_col": 0,
                "end_line": definition["end_line"], "end_col": definition["end_col"] - 1}}],
               "total_token_count": 10, "truncated": False}
    assert native_context_metrics(context, gold, corpus)["native_gold_function_in_context"] == 0
    context["items"][0]["range"]["end_col"] += 1
    assert native_context_metrics(context, gold, corpus)["native_gold_function_in_context"] == 1
    gold["function_labels_complete"] = False
    assert native_context_metrics(context, gold, corpus)["native_gold_function_in_context"] is None


def test_resolver_cache_identity_changes_for_every_bound_input():
    base = ["repo", "revision", "sources", "implementation", {"resolver": "static"}]
    identity = resolver_cache_key(*base)
    for index in range(4):
        changed = list(base)
        changed[index] += "-changed"
        assert resolver_cache_key(*changed) != identity
    for profile in ({"resolver": "scip"}, {"resolver": "scip", "entry_hash": "changed"}):
        assert resolver_cache_key(*base[:4], profile) != identity


def test_cache_reuses_identical_snapshot_and_rejects_tampering(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    row = {"repo": "local/example", "base_commit": "revision"}
    options = dict(rebuild=False, builder_hash="implementation", cache=True, cache_root=tmp_path / "cache")
    first, meta = runner.load_or_build_graph(tmp_path, row, tree, **options)
    second, cached = runner.load_or_build_graph(tmp_path, row, tree, **options)
    assert cached["cached"] is True
    assert first == second
    (tree / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    changed, new_meta = runner.load_or_build_graph(tmp_path, row, tree, **options)
    assert new_meta["cached"] is False
    assert meta["cache_identity"] != new_meta["cache_identity"]
    graph_path = options["cache_root"] / (new_meta["cache_identity"] + ".json")
    graph_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        runner.load_or_build_graph(tmp_path, row, tree, **options)


def test_worker_memory_is_scoped_explicitly():
    result = runner.worker_peak_memory()
    assert result["indexer_peak_rss_bytes"] is None
    if result["python_worker_peak_rss_bytes"] is not None:
        assert result["python_worker_peak_rss_bytes"] > 0
        assert "excludes Node" in result["scope"]
