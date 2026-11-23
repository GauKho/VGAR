"""Grounding probe: top task anchors for issue texts against expected files and symbols (spec 2026-11-23 §5.2).

Builds the graph of a repository in memory, grounds each case with the same task overlay ``find_task_anchors``
serves (stored source passed as ``sources``) and reports, per case, whether a top-k anchor is in an expected file
and whether one is an expected symbol (qualified name ends with it).

    python scripts/probe_task_anchors.py <repo_root> <cases.json> --out result.json [--top 5]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.snapshot_sources import read_graph_sources
from vgar.graph.task_overlay import TaskOverlayBuilder

logger = logging.getLogger(__name__)


def probe(root: Path, cases: list[dict], top: int = 5) -> list[dict]:
    """Per case: top anchors and file/symbol hits.

    Args:
        root: Repository root.
        cases: Items with ``id``, ``text``, ``files`` and ``symbols``.
        top: Number of anchors that count.
    """
    document = PythonGraphBuilder(repo_key=root.name, repository_revision="probe").build(root)
    sources = read_graph_sources(root, document)
    builder = TaskOverlayBuilder(document)
    results = []
    for case in cases:
        anchors = builder.build(case["id"], case["text"], None, sources=sources).grounding.anchors[:top]
        results.append({
            "id": case["id"],
            "anchors": [{"symbol": a.symbol, "path": a.path, "score": a.score,
                         "kinds": sorted({e.kind for e in a.evidence})} for a in anchors],
            "file_hit": any(a.path in case["files"] for a in anchors),
            "symbol_hit": any(a.symbol.endswith(s) for a in anchors for s in case["symbols"]) if case["symbols"] else None,
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()
    results = probe(args.root.resolve(), json.loads(args.cases.read_text(encoding="utf-8"))["cases"], args.top)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    symbol_cases = [r for r in results if r["symbol_hit"] is not None]
    logger.info("file hits %d/%d, symbol hits %d/%d", sum(r["file_hit"] for r in results), len(results),
                sum(r["symbol_hit"] for r in symbol_cases), len(symbol_cases))
    for r in results:
        logger.info("%-28s file=%-5s symbol=%-5s %s", r["id"], r["file_hit"], r["symbol_hit"],
                    ", ".join(f"{a['symbol'].rsplit('.', 2)[-2:][-1]}({a['score']:.2f},{'/'.join(a['kinds'])})"
                              for a in r["anchors"]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
