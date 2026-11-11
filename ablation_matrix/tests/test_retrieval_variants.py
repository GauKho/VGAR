"""R-A1 (no task trace) vs R-A2 (task trace) retrieval variants."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval_variants import (
    ARMS,
    symbol_search_anchors,
    variant_outputs,
)

from vgar.graph.builder import PythonGraphBuilder

REPO = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n\n\ndef round_vnd_cents(amount):\n    return amount\n",
    "shop/checkout.py": "from shop.pricing import round_vnd\n\n\ndef total(lines):\n    return round_vnd(sum(lines))\n",
    "tests/test_pricing.py": "from shop.pricing import round_vnd\n\n\ndef test_round_vnd():\n    assert round_vnd(1) == 1\n",
}


def _build(tmp_path):
    for path, text in REPO.items():
        target = tmp_path / "repo" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return PythonGraphBuilder(repo_key="t/variants", repository_revision="rev").build(tmp_path / "repo")


def _name(document, node_id):
    return next(node["qualified_name"] for node in document["nodes"] if node["id"] == node_id)


def _not_test(node):
    return not (node.get("path") or "").startswith("tests/")


def test_exact_symbol_name_comes_before_names_that_contain_it(tmp_path):
    document = _build(tmp_path)
    anchors = symbol_search_anchors(document, "round_vnd gives a wrong value", limit=10, include=_not_test)
    assert [_name(document, a) for a in anchors][:2] == ["shop.pricing.round_vnd", "shop.pricing.round_vnd_cents"]


def test_paths_and_line_numbers_do_not_make_anchors(tmp_path):
    document = _build(tmp_path)
    assert symbol_search_anchors(document, 'see "shop/checkout.py", line 5', limit=10, include=_not_test) == []


def test_anchor_limit_and_include_are_respected(tmp_path):
    document = _build(tmp_path)
    anchors = symbol_search_anchors(document, "round_vnd test_round_vnd", limit=1, include=_not_test)
    assert len(anchors) == 1 and not _name(document, anchors[0]).startswith("tests.")


def test_variants_differ_only_by_the_task_trace(tmp_path):
    document = _build(tmp_path)
    issue = "total() is wrong because round_vnd drops cents"
    outputs = variant_outputs(document, tmp_path / "repo", issue, include=_not_test,
                              count_tokens=lambda text: len(text) // 4, counter_label="test")
    assert set(outputs) == set(ARMS) == {"no_task_trace", "task_trace"}
    assert outputs["no_task_trace"]["diagnostics"]["overlay_id"] is None
    assert outputs["task_trace"]["diagnostics"]["overlay_id"] is not None
    a1 = outputs["no_task_trace"]["diagnostics"]["retrieval_config"]["ranking_config_hash"]
    a2 = outputs["task_trace"]["diagnostics"]["retrieval_config"]["ranking_config_hash"]
    assert a1 == a2                                   # same ranking config, only the anchors/G_task differ
    assert outputs["no_task_trace"]["candidates"] and outputs["task_trace"]["candidates"]


def test_issue_without_symbol_words_gives_an_empty_no_trace_arm(tmp_path):
    document = _build(tmp_path)
    outputs = variant_outputs(document, tmp_path / "repo", "it crashes sometimes", include=_not_test,
                              count_tokens=lambda text: len(text) // 4, counter_label="test")
    assert outputs["no_task_trace"]["anchors"] == []
