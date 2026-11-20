"""Verify the A2 graph retrieval (served default ``task_trace``) on the dev tasks; no LLM, offline.

Level 1, the formulas that are the team's choice (not in the proposal) hold in the running code:
  - path confidence = min(anchor score, confidence of every hop in ``graph_rationale``) — hops read from
    ``retriever.adjacency``, the folded edges the walk itself uses;
  - ``features.graph_distance`` = confidence / (1 + hops) and ``features.edge_confidence`` = confidence;
  - ``relevance_score`` = sum(normalized weight x feature) over the active features.
Level 2, where each gold function is lost: packed / candidate_not_packed (with the packing reason) / walk_cap
(candidate cap reached) / no_path (an anchor in its file, but not reached) / no_anchor_in_file / not_in_graph.

  PYTHONPATH=src python baseline/verify_retrieval.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
      --out ~/rt1/results/verify_retrieval
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import baseline._paths

# isort: split
import run_graph_retrieval as runner
from retrieval_variants import arm_config

from baseline.graph_store import load_or_build
from baseline.profiles import build_layers
from vgar.evaluation.retrieval.dataset import require_split, validate_task
from vgar.evaluation.retrieval.gold_labels import extract_gold
from vgar.evaluation.retrieval.scoring import (
    FALLBACK_COUNTER_LABEL,
    CorpusIndex,
    bytes_div4_counter,
    make_include,
)
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder

TOLERANCE = 1e-9
STAGES = ("packed", "candidate_not_packed", "walk_cap", "no_path", "no_anchor_in_file", "not_in_graph")


def _hops(rationale: list[str]) -> list[tuple[str, str, str]]:
    """``RELATION:source->target`` entries of a rationale as (relation, source, target)."""
    hops = []
    for step in rationale:
        relation, sep, ends = step.partition(":")
        if sep and "->" in ends:
            source, _, target = ends.partition("->")
            hops.append((relation, source, target))
    return hops


def check_path_confidence(candidate: dict[str, Any], adjacency: dict[str, list[tuple[str, float, str]]],
                          anchor_scores: dict[str, float]) -> bool | None:
    """True when the candidate's confidence is min(anchor score, hop confidences); None when not checkable."""
    hops = _hops(candidate.get("graph_rationale") or [])
    seed = hops[0][1] if hops else candidate["node_id"]
    if seed not in anchor_scores:   # component/diagnostic/test seeds carry their own starting values
        return None
    values = [anchor_scores[seed]]
    for relation, source, target in hops:
        matching = [conf for to, conf, rel in adjacency.get(source, ()) if to == target and rel == relation]
        if not matching:
            return False
        values.append(max(matching))   # the walk keeps the best of parallel edges with the same relation
    return abs(min(values) - candidate["confidence"]) <= TOLERANCE


def _covered(items: list[dict[str, Any]], definition: dict[str, Any]) -> bool:
    start = definition["start_line"], definition["start_col"]
    end = definition["end_line"], definition["end_col"]
    return any(item["path"] == definition["path"] and (item["range"]["start_line"], item["range"]["start_col"]) <= start
               and end <= (item["range"]["end_line"], item["range"]["end_col"]) for item in items)


def verify_task(row: dict, sources: dict[str, str], tree: Path, document: dict, *, counter: Any, label: str,
                budget_tokens: int) -> dict[str, Any]:
    """Level 1 checks and level 2 funnel for one task (A2 arm, as T1 and the MCP server run it)."""
    corpus = CorpusIndex(sources)
    overlay = TaskOverlayBuilder(document).build("ablation:task_trace", row["problem_statement"], None)
    retriever = GraphContextRetriever(document, tree, count_tokens=counter, counter_label=label,
                                      config=arm_config("task_trace"))
    anchors = {anchor.node_id: anchor.score for anchor in overlay.grounding.anchors}
    result = retriever.retrieve(list(anchors), budget_tokens, issue_text=row["problem_statement"], overlay=overlay,
                                include=make_include(corpus))
    weights, active = result.config["normalized_weights"], result.config["active_features"]
    checks: dict[str, Any] = {"candidates": len(result.candidates)}
    for name in ("path_confidence", "graph_distance", "edge_confidence", "relevance_score"):
        checks[name] = {"checked": 0, "mismatch": 0, "unverifiable": 0, "examples": []}

    def record(name: str, ok: bool | None, candidate: dict[str, Any]) -> None:
        bucket = checks[name]
        if ok is None:
            bucket["unverifiable"] += 1
            return
        bucket["checked"] += 1
        if not ok:
            bucket["mismatch"] += 1
            if len(bucket["examples"]) < 3:
                bucket["examples"].append({"node_id": candidate["node_id"], "confidence": candidate["confidence"],
                                           "graph_distance": candidate["graph_distance"],
                                           "features": candidate["features"],
                                           "relevance_score": candidate["relevance_score"],
                                           "graph_rationale": candidate.get("graph_rationale")})

    for candidate in result.candidates:
        features, confidence, hops = candidate["features"], candidate["confidence"], candidate["graph_distance"]
        record("path_confidence", check_path_confidence(candidate, retriever.adjacency, anchors), candidate)
        record("graph_distance", abs(features["graph_distance"] - confidence / (1 + hops)) <= TOLERANCE, candidate)
        record("edge_confidence", abs(features["edge_confidence"] - confidence) <= TOLERANCE, candidate)
        expected = sum(weights[name] * features[name] for name in active)
        record("relevance_score", abs(candidate["relevance_score"] - expected) <= 1e-6, candidate)

    gold = extract_gold(row["patch"], sources)
    definitions = {d["parent_id"]: d for values in corpus.definitions.values() for d in values}
    by_symbol = {(c["path"], c["symbol"]): (rank, c) for rank, c in enumerate(result.candidates, 1)}
    node_ids = {(n.get("path"), n.get("qualified_name")): n["id"] for n in document["nodes"]}
    omitted = {o["node_id"]: o["reason"] for o in result.omissions}
    items = result.context.model_dump(mode="json")["items"]
    anchor_paths = {retriever.nodes[node_id]["path"] for node_id in anchors if node_id in retriever.nodes}
    funnel = []
    for gold_id in gold["gold_functions"]:
        path, _, symbol = gold_id.partition("::")
        definition = definitions.get(gold_id)
        found = by_symbol.get((path, symbol))
        row_out: dict[str, Any] = {"gold_function": gold_id, "rank": found[0] if found else None,
                                   "relevance_score": found[1]["relevance_score"] if found else None}
        if definition is not None and _covered(items, definition):
            stage = "packed"
        elif found:
            stage = "candidate_not_packed"
            row_out["reason"] = omitted.get(found[1]["node_id"], "below_packed_items")
        elif (path, symbol) not in node_ids:
            stage = "not_in_graph"
        elif path in anchor_paths:
            stage = "walk_cap" if result.traversal_limited else "no_path"
        else:
            stage = "no_anchor_in_file"
        row_out["stage"] = stage
        funnel.append(row_out)
    return {"instance_id": row["instance_id"], "cross_file": len(gold["gold_files"]) >= 2,
            "traversal_limited": result.traversal_limited, "anchors": len(anchors),
            "weights": {"normalized": weights, "active": active,
                        "unavailable": result.unavailable_features}, "checks": checks, "funnel": funnel}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals of level 1 checks and the level 2 funnel (all tasks, and multi-file tasks)."""
    checks = {name: Counter() for name in ("path_confidence", "graph_distance", "edge_confidence", "relevance_score")}
    funnel, multi, reasons = Counter(), Counter(), Counter()
    for result in results:
        for name, counter in checks.items():
            counter.update({key: result["checks"][name][key] for key in ("checked", "mismatch", "unverifiable")})
        for row in result["funnel"]:
            funnel[row["stage"]] += 1
            if result["cross_file"]:
                multi[row["stage"]] += 1
            if row["stage"] == "candidate_not_packed":
                reasons[row["reason"]] += 1
    return {"tasks": len(results), "checks": {k: dict(v) for k, v in checks.items()},
            "funnel": {stage: funnel[stage] for stage in STAGES},
            "funnel_multi_file": {stage: multi[stage] for stage in STAGES}, "not_packed_reasons": dict(reasons),
            "traversal_limited_tasks": sum(r["traversal_limited"] for r in results)}


def summary_from_dir(out: Path) -> dict[str, Any]:
    """Summary over every task file of a run directory (several partial runs add up); failed tasks are listed."""
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(out).glob("tasks/*.json"))]
    summary = summarize([result for result in loaded if "error" not in result])
    summary["errors"] = [result["instance_id"] for result in loaded if "error" in result]
    return summary


def main(argv: list[str] | None = None) -> int:
    from baseline.run_offline import prepare_task

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", type=Path)
    parser.add_argument("--graphs-dir", type=Path)
    parser.add_argument("--budget-tokens", type=int, default=12000)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require_split(manifest, allowed=("dev",), protocol="r1")
    tasks = manifest["tasks"]
    if args.only:
        wanted = set(args.only.read_text(encoding="utf-8").split())
        tasks = [task for task in tasks if task["instance_id"] in wanted]
    graphs_dir = (args.graphs_dir or root / "graphs").expanduser()
    builder_hash = runner.source_fingerprint(baseline._paths.ROOT)["digest"]
    (args.out / "tasks").mkdir(parents=True, exist_ok=True)
    for number, row in enumerate(tasks, 1):
        validate_task(row)
        target = args.out / "tasks" / f"{row['instance_id']}.json"
        if target.exists() and "error" not in json.loads(target.read_text(encoding="utf-8")):
            continue   # done in an earlier run of the same directory
        row = dict(row, patch=(root / row["gold_patch_path"]).read_text(encoding="utf-8"))
        try:
            sources, tree = prepare_task(root, row)
            document, _ = load_or_build(root, row, tree, build="base", layers=build_layers("base", {}),
                                        graphs_dir=graphs_dir, builder_hash=builder_hash)
            result = verify_task(row, sources, tree, document, counter=bytes_div4_counter,
                                 label=FALLBACK_COUNTER_LABEL, budget_tokens=args.budget_tokens)
            status = "OK"
        except Exception as error:  # noqa: BLE001 -- listed, the other tasks go on
            result, status = {"instance_id": row["instance_id"], "error": f"{type(error).__name__}: {error}"}, "ERROR"
        target.write_text(
            json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        print(f"[{number}/{len(tasks)}] {row['instance_id']}: {status}", flush=True)
    summary = summary_from_dir(args.out)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
