"""Remaining R1 configs: text baselines (grep, file-neighbor), component recall, AST-only / architecture / A3 arms."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from component_metrics import component_metrics
from retrieval_variants import GRAPH_ARMS, ast_only, variant_outputs
from text_baselines import grep_rank, neighbor_rank

from vgar.graph.builder import PythonGraphBuilder

SOURCES = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n",
    "shop/checkout.py": "from shop.pricing import round_vnd\n\n\ndef total(lines):\n    return round_vnd(sum(lines))\n",
    "shop/report/summary.py": "def summarize(rows):\n    return len(rows)\n",
    "other/util.py": "def helper(x):\n    return x\n",
}


def _paths(record):
    return [item.path for item in record.items]


def test_grep_ranks_the_file_with_the_rare_issue_word_first():
    record = grep_rank("t", "summarize breaks on empty rows", SOURCES)
    assert _paths(record)[0] == "shop/report/summary.py"
    assert record.arm == "grep"


def test_grep_without_matching_words_returns_no_items():
    assert grep_rank("t", "zzzz qqqq", SOURCES).items == []


def test_neighbor_puts_the_mentioned_file_then_its_folder_first():
    record = neighbor_rank("t", "error in shop/checkout.py when paying", SOURCES)
    paths = _paths(record)
    assert paths[0] == "shop/checkout.py"
    assert paths.index("shop/pricing.py") < paths.index("other/util.py")
    assert record.meta["mentioned_files"] == ["shop/checkout.py"]


def test_neighbor_without_a_mentioned_file_falls_back_to_bm25():
    record = neighbor_rank("t", "round_vnd returns the wrong amount", SOURCES)
    assert record.meta["mentioned_files"] == [] and record.meta["fallback"] == "bm25"


def _document(tmp_path):
    for path, text in SOURCES.items():
        target = tmp_path / "repo" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return PythonGraphBuilder(repo_key="t/r1", repository_revision="rev").build(tmp_path / "repo")


def test_component_recall_counts_distinct_components_in_rank_order(tmp_path):
    document = _document(tmp_path)
    metrics = component_metrics(document, ["other/util.py", "shop/pricing.py", "shop/checkout.py"],
                                gold_files=["shop/pricing.py"])
    assert metrics["component_recall@1"] == 0.0 and metrics["component_recall@3"] == 1.0
    assert metrics["component_mrr"] == 0.5


def test_component_recall_is_none_without_components(tmp_path):
    document = _document(tmp_path)
    document = {**document, "nodes": [n for n in document["nodes"] if n["type"] not in {"Component", "Port"}]}
    assert component_metrics(document, ["shop/pricing.py"], gold_files=["shop/pricing.py"])["component_recall@1"] is None


def test_ast_only_keeps_only_containment_edges(tmp_path):
    kinds = {edge["type"] for edge in ast_only(_document(tmp_path))["edges"]}
    assert "CALLS" not in kinds and "IMPORTS" not in kinds and "CONTAINS" in kinds


def test_all_graph_arms_run_on_one_graph(tmp_path):
    document = _document(tmp_path)
    outputs = variant_outputs(document, tmp_path / "repo", "total() is wrong because round_vnd drops cents",
                              include=None, count_tokens=lambda text: len(text) // 4, counter_label="test",
                              arms=GRAPH_ARMS)
    assert set(outputs) == set(GRAPH_ARMS)
    configs = {arm: outputs[arm]["diagnostics"]["retrieval_config"] for arm in GRAPH_ARMS}
    assert configs["arch_no_task_trace"]["use_component_dependents"] is True
    assert configs["a3"]["use_component_dependents"] is True and configs["a3"]["use_trace_component"] is True
    assert configs["task_trace_rt1"]["may_call_factor"] == 0.5
    assert outputs["ast_no_task_trace"]["diagnostics"]["overlay_id"] is None
    assert outputs["a3"]["diagnostics"]["overlay_id"] is not None


def test_graph_arms_keep_at_most_one_retriever_alive(tmp_path, monkeypatch):
    import weakref

    import retrieval_variants

    alive: weakref.WeakSet = weakref.WeakSet()
    peak = []

    class Tracked(retrieval_variants.GraphContextRetriever):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            alive.add(self)
            peak.append(len(alive))

    monkeypatch.setattr(retrieval_variants, "GraphContextRetriever", Tracked)
    document = _document(tmp_path)
    variant_outputs(document, tmp_path / "repo", "total() is wrong because round_vnd drops cents", include=None,
                    count_tokens=lambda text: len(text) // 4, counter_label="test", arms=GRAPH_ARMS)
    assert max(peak) == 1
