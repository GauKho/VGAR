"""TV2 SC-1: measure how schema validation time grows with graph size (proposal lines 878-882: O(|V|+|E|)).

Builds valid synthetic graphs of growing size, times ``validate_graph_document`` on each, and fits
log(time) against log(|V|+|E|). A slope close to 1 means linear growth. Real graphs saved as JSON can be timed too.

Example (from the project root):
  python scripts/bench_schema_validation.py --output results/schema_bench.json --graph xarray_graph.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.contracts.schema import NODE_PROPERTIES, validate_graph_document

DEFAULT_SIZES = (20, 50, 120, 280, 660, 1600, 4000)  # files; |V|+|E| from about 1,000 to 200,000
_SAMPLES = {"string": "x", "integer": 1, "number": 1.0, "boolean": False, "array": [], "object": {}}
_RANGE = {"start_line": 1, "start_col": 0, "end_line": 1, "end_col": 1, "start_byte": 0, "end_byte": 1}


def _properties(node_type: str, **values: Any) -> dict[str, Any]:
    properties = {key: _SAMPLES[rule.split("|")[0]] for key, rule in NODE_PROPERTIES[node_type].items()}
    properties.update(values)
    return properties


def synthetic_document(files: int, depth: int = 6) -> dict[str, Any]:
    """A valid graph shaped like a real one: per file a module, ``depth`` nested classes, one method and one call each.

    Args:
        files: Number of files; the size grows linearly with it.
        depth: How deep the classes of one file are nested.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, node_type: str, properties: dict[str, Any], path: str | None) -> None:
        nodes.append({"id": node_id, "type": node_type, "repo_key": "bench/synthetic", "name": node_id.rsplit(":", 1)[-1],
                      "qualified_name": node_id, "path": path, "range": dict(_RANGE) if path else None,
                      "graph_version": "sha256:bench", "properties": properties})

    def add_edge(edge_type: str, source: str, target: str, **properties: Any) -> None:
        edges.append({"id": f"e{len(edges)}", "type": edge_type, "source_id": source, "target_id": target, "confidence": 1.0,
                      "graph_version": "sha256:bench", "properties": properties,
                      "provenance": {"source_tool": "bench", "rule_id": "bench.synthetic", "source_revision": "rev"}})

    add_node("repo", "Repository", _properties("Repository"), None)
    for index in range(files):
        path = f"pkg{index}/m.py"
        add_node(f"file:{index}", "File", _properties("File"), path)
        add_node(f"module:{index}", "Module", _properties("Module", module_name=f"pkg{index}.m"), path)
        add_edge("CONTAINS", "repo", f"file:{index}")
        add_edge("CONTAINS", f"file:{index}", f"module:{index}")
        parent = f"module:{index}"
        for level in range(depth):
            class_id, method_id, call_id = f"class:{index}:{level}", f"method:{index}:{level}", f"call:{index}:{level}"
            add_node(class_id, "Class", _properties("Class"), path)
            add_node(method_id, "Method", _properties("Method", owner_class_id=class_id), path)
            add_node(call_id, "CallSite", _properties("CallSite", candidate_count=1), path)
            add_edge("CONTAINS", parent, class_id)
            add_edge("CONTAINS", class_id, method_id)
            add_edge("CONTAINS", method_id, call_id)
            add_edge("CALLS", call_id, f"method:{(index + 1) % files}:{level}")
            parent = class_id
        component_id, port_id = f"component:{index}", f"port:{index}"
        add_node(component_id, "Component", _properties("Component", files=[path]), None)
        add_node(port_id, "Port", _properties("Port", owner_component_id=component_id, symbol_id=f"method:{index}:0"), None)
        add_edge("CONTAINS_COMPONENT", f"module:{index}", component_id)
        add_edge("EXPOSES_PORT", component_id, port_id)
    return {"repo_key": "bench/synthetic", "repository_revision": "rev", "graph_version": "sha256:bench",
            "nodes": nodes, "edges": edges}


def fit_slope(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Least-squares slope of log(time) against log(size), and its R².

    Args:
        points: (|V|+|E|, time) pairs with positive values.
    """
    xs = [math.log(size) for size, _ in points]
    ys = [math.log(value) for _, value in points]
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - mean_y) ** 2 for y in ys)
    return slope, 1.0 - residual / total if total else 1.0


def _median_ms(document: dict[str, Any], repeats: int) -> float:
    timings = []
    for _ in range(repeats):
        started = time.perf_counter()
        validate_graph_document(document)
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.median(timings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure how schema validation time grows with graph size")
    parser.add_argument("--sizes", default=",".join(map(str, DEFAULT_SIZES)), help="comma-separated file counts")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--graph", type=Path, action="append", default=[], help="a saved graph document to time as well")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    points = []
    for files in (int(item) for item in args.sizes.split(",")):
        document = synthetic_document(files)
        nodes, edges = len(document["nodes"]), len(document["edges"])
        points.append({"files": files, "nodes": nodes, "edges": edges, "n": nodes + edges, "median_ms": _median_ms(document, args.repeats)})
    slope, r2 = fit_slope([(point["n"], point["median_ms"]) for point in points])
    graphs = []
    for path in args.graph:
        document = json.loads(path.read_text(encoding="utf-8"))
        graphs.append({"path": str(path), "n": len(document["nodes"]) + len(document["edges"]), "median_ms": _median_ms(document, args.repeats)})
    result = {"repeats": args.repeats, "points": points, "slope": slope, "r2": r2, "graphs": graphs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"slope={slope:.3f} r2={r2:.4f} points={len(points)} graphs={len(graphs)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
