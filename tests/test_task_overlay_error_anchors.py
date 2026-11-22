"""Error messages become G_task anchors (proposal §6.6, spec 2026-11-20 §5.3); find_task_anchors also lists the
components the issue traces to (§9.1 "candidate files/functions/components")."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.source_evidence import message_matches
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.task_overlay import TaskOverlayBuilder

REPO = {
    "pkg/__init__.py": "",
    "pkg/errors.py": "class WidgetError(Exception):\n    pass\n",
    "pkg/paint.py": ("from pkg.errors import WidgetError\n\n\n"
                     "def paint(widget):\n    raise WidgetError('widget could not be painted today')\n"),
    "pkg/other.py": "def other():\n    return 1\n",
}
ISSUE = "Painting fails.\n\nWidgetError: widget could not be painted today\n"


class Untouchable(Mapping):
    """Sources that must not be read."""

    def __getitem__(self, key):
        raise AssertionError("sources were read")

    def __iter__(self):
        raise AssertionError("sources were read")

    def __len__(self):
        raise AssertionError("sources were read")


def _build(root: Path, files: dict[str, str]) -> dict:
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return PythonGraphBuilder(repo_key="t/errors", repository_revision="rev").build(root)


def _sources(root: Path, files: dict[str, str]) -> dict[str, str]:
    return {path: (root / path).read_text(encoding="utf-8") for path in files}


def _id(document: dict, qualified_name: str) -> str:
    return next(node["id"] for node in document["nodes"] if node["qualified_name"] == qualified_name)


def _anchor(overlay, node_id):
    return next((anchor for anchor in overlay.grounding.anchors if anchor.node_id == node_id), None)


def _mentions(overlay, node_id):
    return [edge for edge in overlay.edges if edge["type"] == "MENTIONS" and edge["target_id"] == node_id]


def test_exception_named_in_the_issue_becomes_an_error_anchor(tmp_path):
    document = _build(tmp_path, REPO)
    overlay = TaskOverlayBuilder(document).build("t", ISSUE)
    anchor = _anchor(overlay, _id(document, "pkg.errors.WidgetError"))
    assert anchor is not None and "error" in {item.kind for item in anchor.evidence}
    assert [edge["confidence"] for edge in _mentions(overlay, anchor.node_id)] == [anchor.score]


def test_log_line_matching_one_string_literal_is_an_error_message_anchor_0_85(tmp_path):
    document = _build(tmp_path, REPO)
    overlay = TaskOverlayBuilder(document).build("t", ISSUE, sources=_sources(tmp_path, REPO))
    anchor = _anchor(overlay, _id(document, "pkg.paint.paint"))
    assert anchor is not None and anchor.score == 0.85
    assert "error_message" in {item.kind for item in anchor.evidence}
    assert len(_mentions(overlay, anchor.node_id)) == 1


def test_two_functions_sharing_the_message_get_0_5_each(tmp_path):
    files = {**REPO, "pkg/again.py": ("from pkg.errors import WidgetError\n\n\n"
                                      "def again(widget):\n    raise WidgetError('widget could not be painted today')\n")}
    document = _build(tmp_path, files)
    overlay = TaskOverlayBuilder(document).build("t", ISSUE, sources=_sources(tmp_path, files))
    scores = {_anchor(overlay, _id(document, name)).score for name in ("pkg.paint.paint", "pkg.again.again")}
    assert scores == {0.5}


def test_without_sources_no_error_message_anchor_is_added(tmp_path):
    document = _build(tmp_path, REPO)
    overlay = TaskOverlayBuilder(document).build("t", ISSUE)
    assert not any(item.kind == "error_message" for anchor in overlay.grounding.anchors for item in anchor.evidence)


def test_issue_without_log_lines_never_reads_sources(tmp_path):
    document = _build(tmp_path, REPO)
    assert message_matches(document["nodes"], Untouchable(), "paint is slow") == {}
    overlay = TaskOverlayBuilder(document).build("t", "paint is slow", sources=Untouchable())
    assert not any(item.kind == "error_message" for anchor in overlay.grounding.anchors for item in anchor.evidence)


def _service(tmp_path: Path, files: dict[str, str]) -> tuple[SQLiteGraphService, dict]:
    document = _build(tmp_path / "repo", files)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    service = SQLiteGraphService(store, repository_root=tmp_path / "repo", count_tokens=len, counter_label="test")
    return service, document


def test_find_task_anchors_adds_error_message_anchors_from_the_repository(tmp_path):
    service, document = _service(tmp_path, REPO)
    result = service.find_task_anchors(ISSUE, None, graph_version=document["graph_version"], task_id="t")
    paint = next(anchor for anchor in result["anchors"] if anchor["node_id"] == _id(document, "pkg.paint.paint"))
    assert "error_message" in {item["kind"] for item in paint["evidence"]}


def test_find_task_anchors_lists_traced_components(tmp_path):
    files = {"shop/__init__.py": "", "shop/pricing/__init__.py": "",
             "shop/pricing/rounding.py": "def round_vnd(a):\n    return a\n",
             "shop/checkout/__init__.py": "",
             "shop/checkout/cart.py": "from shop.pricing.rounding import round_vnd\n\n\ndef total(x):\n    return round_vnd(x)\n"}
    service, document = _service(tmp_path, files)
    result = service.find_task_anchors("round_vnd drops cents", None, graph_version=document["graph_version"],
                                       task_id="t")
    assert result["components"]
    assert set(result["components"][0]) == {"component_id", "confidence", "anchor_count"}


def test_find_task_anchors_without_traces_returns_empty_components(tmp_path):
    service, document = _service(tmp_path, REPO)
    result = service.find_task_anchors("it crashes sometimes", None, graph_version=document["graph_version"],
                                       task_id="t")
    assert result["components"] == []
