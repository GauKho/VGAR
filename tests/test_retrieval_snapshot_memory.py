"""Keep isolation while avoiding unused graph-sized task-overlay copies."""
import copy
import tracemalloc

import pytest

from vgar.contracts.schema import GraphValidationError
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder


def graph(tmp_path):
    (tmp_path / "code.py").write_text("def fix_target():\n    return 1\n", encoding="utf-8")
    return PythonGraphBuilder(repo_key="fixture", repository_revision="base", use_jedi=False).build(tmp_path)


def test_task_overlay_does_not_duplicate_unused_graph_metadata(tmp_path):
    document = graph(tmp_path)
    # JSON-compatible cold metadata must not become a second task-sized graph.
    document["statistics"]["cold_metadata"] = [{"value": str(i)} for i in range(30_000)]
    tracemalloc.start()
    try:
        builder = TaskOverlayBuilder(document)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 512_000, f"Task overlay copied unused metadata: {peak} bytes"
    # Still owns its relevant source records, rather than borrowing mutable input.
    for node in document["nodes"]:
        if node["name"] == "fix_target":
            node["name"] = node["qualified_name"] = "changed"
    overlay = builder.build("task", "fix_target")
    assert any(anchor.symbol == "code.fix_target" for anchor in overlay.grounding.anchors)


def test_owned_worker_snapshot_matches_isolated_retriever(tmp_path):
    document = graph(tmp_path)
    reference = GraphContextRetriever(document, tmp_path, count_tokens=len, counter_label="fixture-char")
    moved = copy.deepcopy(document)
    worker = GraphContextRetriever(moved, tmp_path, count_tokens=len, counter_label="fixture-char", _take_ownership=True)
    anchor = next(node["id"] for node in document["nodes"] if node["type"] == "Function")
    assert worker.retrieve([anchor], 1000, issue_text="fix_target") == reference.retrieve([anchor], 1000, issue_text="fix_target")
    # The private worker route transfers ownership; public default still isolates.
    assert worker.document is moved
    moved["nodes"][-1]["properties"]["external_mutation"] = True
    assert "external_mutation" not in reference.document["nodes"][-1]["properties"]


def test_compact_overlay_still_rejects_base_edge_id_collision(tmp_path):
    document = graph(tmp_path)
    overlay = TaskOverlayBuilder(document).build("task", "fix_target")
    document["edges"][0]["id"] = overlay.edges[0]["id"]
    with pytest.raises(GraphValidationError, match="duplicate edge id"):
        TaskOverlayBuilder(document).build("task", "fix_target")


def test_compact_overlay_still_validates_unused_base_records(tmp_path):
    document = graph(tmp_path)
    document["edges"][0]["target_id"] = "missing"
    with pytest.raises(GraphValidationError, match="target_id does not exist"):
        TaskOverlayBuilder(document)
