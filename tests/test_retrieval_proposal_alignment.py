"""Retrieval follows proposal §9.2 (spec 2026-11-20 §5.1): every k=2 neighbour of the given anchors is a candidate,
the seeds are the anchors only, MAY_CALL is walked with its stored confidence (§6.4) and packing is plain rank order."""
from __future__ import annotations

from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import (
    RESOURCE_LIMIT_CANDIDATES,
    GraphContextRetriever,
    RetrievalConfig,
)


def _build(root: Path, files: dict[str, str]) -> dict:
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return PythonGraphBuilder(repo_key="t/align", repository_revision="rev").build(root)


def _retriever(document: dict, root: Path) -> GraphContextRetriever:
    return GraphContextRetriever(document, root, count_tokens=lambda text: len(text.split()), counter_label="test")


def _node(document: dict, qualified_name: str) -> str:
    return next(node["id"] for node in document["nodes"] if node["qualified_name"] == qualified_name)


def test_default_config_follows_proposal_9_2():
    config = RetrievalConfig()
    assert config.max_candidates == RESOURCE_LIMIT_CANDIDATES
    assert config.may_call_factor == 1.0
    assert config.reference_budget_fraction == 0.0
    assert config.use_component_seeds is False


def test_every_two_hop_neighbour_is_a_candidate_past_the_old_cap(tmp_path):
    functions = "".join(f"def f{i}():\n    return {i}\n\n\n" for i in range(150))
    calls = "".join(f"    f{i}()\n" for i in range(150))
    document = _build(tmp_path, {"pkg/__init__.py": "", "pkg/hub.py": functions + f"def hub():\n{calls}"})
    result = _retriever(document, tmp_path).retrieve([_node(document, "pkg.hub.hub")], 12000)
    assert len(result.candidates) >= 151
    assert result.traversal_limited is False


def test_mentioned_directory_and_log_line_do_not_seed(tmp_path):
    document = _build(tmp_path, {
        "widgets/__init__.py": "",
        "widgets/core.py": "def paint(widget):\n    raise ValueError('widget not painted')\n",
        "app/__init__.py": "",
        "app/main.py": "def run():\n    return 1\n",
    })
    issue = "The widgets break.\n\nValueError: widget not painted\n"
    result = _retriever(document, tmp_path).retrieve([_node(document, "app.main.run")], 12000, issue_text=issue)
    assert _node(document, "widgets.core.paint") not in {candidate["node_id"] for candidate in result.candidates}


def test_may_call_neighbour_is_walked_with_its_stored_confidence(tmp_path):
    document = _build(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/shapes.py": ("class Square:\n    def refresh(self):\n        return 1\n\n\n"
                          "class Circle:\n    def refresh(self):\n        return 2\n\n\n"
                          "def handler(item):\n    item.refresh()\n"),
    })
    may_calls = [edge for edge in document["edges"] if edge["type"] == "MAY_CALL"]
    assert may_calls   # the unresolved item.refresh() is kept as possible calls (§6.4)
    edge = may_calls[0]
    result = _retriever(document, tmp_path).retrieve([_node(document, "pkg.shapes.handler")], 12000)
    found = {candidate["node_id"]: candidate for candidate in result.candidates}
    assert edge["target_id"] in found
    assert found[edge["target_id"]]["confidence"] == edge["confidence"]
    assert any(step.startswith("MAY_CALL:") for step in found[edge["target_id"]]["graph_rationale"])


def test_equal_scores_are_ordered_by_own_issue_similarity_before_the_path(tmp_path):
    """Neighbours that inherit the anchor's similarity tie; the one whose own name matches the issue comes first,
    not the one whose name sorts first (review 2026-11-22 R2)."""
    document = _build(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/paint.py": ("def aaa_noop():\n    return 0\n\n\n"
                         "def zz_widget_helper():\n    return 1\n\n\n"
                         "def paint_widget_border():\n    aaa_noop()\n    zz_widget_helper()\n"),
    })
    issue = "paint_widget_border crashes when the widget border is painted"
    result = _retriever(document, tmp_path).retrieve([_node(document, "pkg.paint.paint_widget_border")], 12000,
                                                     issue_text=issue)
    found = {candidate["symbol"]: candidate for candidate in result.candidates}
    noop, helper = found["pkg.paint.aaa_noop"], found["pkg.paint.zz_widget_helper"]
    assert noop["relevance_score"] == helper["relevance_score"]          # both inherit the anchor's similarity
    assert helper["direct_task_similarity"] > noop["direct_task_similarity"]
    order = [candidate["symbol"] for candidate in result.candidates]
    assert order.index("pkg.paint.zz_widget_helper") < order.index("pkg.paint.aaa_noop")
