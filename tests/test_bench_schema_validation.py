"""SC-1: the schema validation benchmark script.

Spec: docs/superpowers/specs/2026-11-10-tv2-sc-1-schema-design.md §5
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from vgar.contracts.schema import validate_graph_document

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bench_schema_validation.py"
_spec = importlib.util.spec_from_file_location("bench_schema_validation", SCRIPT)
assert _spec is not None and _spec.loader is not None
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def _size(document: dict) -> tuple[int, int]:
    return len(document["nodes"]), len(document["edges"])


def test_synthetic_document_is_valid() -> None:
    validate_graph_document(bench.synthetic_document(5))


def test_synthetic_document_grows_linearly() -> None:
    small_nodes, small_edges = _size(bench.synthetic_document(10))
    large_nodes, large_edges = _size(bench.synthetic_document(20))
    assert (large_nodes + large_edges) / (small_nodes + small_edges) == pytest.approx(2.0, rel=0.05)
    assert 1.1 <= large_edges / large_nodes <= 1.5


def test_synthetic_document_nests_classes() -> None:
    document = bench.synthetic_document(1, depth=8)
    assert sum(node["type"] == "Class" for node in document["nodes"]) == 8


def test_fit_slope_on_exact_line() -> None:
    slope, r2 = bench.fit_slope([(10, 30.0), (100, 300.0), (1000, 3000.0)])
    assert slope == pytest.approx(1.0, abs=1e-9) and r2 == pytest.approx(1.0, abs=1e-9)


def test_fit_slope_on_quadratic() -> None:
    slope, _ = bench.fit_slope([(10, 100.0), (100, 10000.0), (1000, 1000000.0)])
    assert slope == pytest.approx(2.0, abs=1e-9)


def test_main_writes_json(tmp_path: Path) -> None:
    output = tmp_path / "bench.json"
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps(bench.synthetic_document(3)), encoding="utf-8")
    assert bench.main(["--sizes", "5,10", "--repeats", "2", "--graph", str(graph), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert [point["files"] for point in result["points"]] == [5, 10]
    assert {"slope", "r2", "graphs"} <= set(result) and result["graphs"][0]["n"] > 0
