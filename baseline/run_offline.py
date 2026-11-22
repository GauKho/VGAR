"""T1 (spec 2026-11-19 §7): retrieval and impact of every layer profile, offline, on one SQLite graph per build.

One run: ``<out>/tasks/<instance_id>.json`` holds every profile as an arm (P0, A1, A2, A3, A3_scip, ...) next to the
text baselines, so ``ablation_matrix/compare_runs.py <results> <run> --arms-vs A2`` compares profiles on the same task.
Scores use F*_core v2 and also the context the MCP server returns (``native_*``). Dev split only; no LLM.

  PYTHONPATH=src python baseline/run_offline.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
      --out ~/rt1/results/layers --profiles P0,A1,A2,A3
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import baseline._paths  # noqa: F401

# isort: split
import run_graph_retrieval as runner
from component_metrics import component_metrics
from retrieval_variants import variant_outputs
from run_r1_ablation import _text_arm
from text_baselines import grep_rank, neighbor_rank

from baseline.frontier_v2 import frontier_core_v2
from baseline.graph_store import load_or_build
from baseline.profiles import PROFILE_ORDER, PROFILES, build_layers
from vgar.evaluation.gold_impact import cross_file_reach, filter_patch
from vgar.evaluation.retrieval.dataset import (
    read_repository_sources,
    require_split,
    validate_task,
)
from vgar.evaluation.retrieval.gold_labels import extract_gold
from vgar.evaluation.retrieval.graph_arm import extract_python_tree
from vgar.evaluation.retrieval.resolver_comparison import native_context_metrics
from vgar.evaluation.retrieval.scoring import (
    FALLBACK_COUNTER_LABEL,
    CorpusIndex,
    bm25_rank,
    bytes_div4_counter,
    flat_metrics,
    graph_rank,
    make_include,
    score_record,
)
from vgar.graph.retrieval import RetrievalConfig

TEXT_ARMS = ("bm25", "grep", "neighbor")
ROOT = Path(__file__).resolve().parents[1]


def evaluate_profiles(row: dict, sources: dict[str, str], tree: Path, documents: dict[str, dict], profiles: list[str],
                      *, counter: Any, label: str, budget_tokens: int, with_text: bool,
                      arm_flags: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Score the profiles of one task; every ranking is computed before the gold patch is read.

    Args:
        row: Manifest task with ``patch`` (gold patch text) and ``problem_statement``.
        sources: Python sources of the task tree.
        tree: Extracted task tree.
        documents: Graph document per build needed by ``profiles``.
        profiles: Names from ``baseline.profiles.PROFILES``.
        counter: Token counter.
        label: Counter label.
        budget_tokens: Context budget.
        with_text: Also score the text baselines (BM25, grep, file neighbour).
        arm_flags: ``RetrievalConfig`` fields applied to every graph arm (T1 steps of spec 2026-11-20 §6.1).
    """
    corpus = CorpusIndex(sources)
    include = make_include(corpus)
    by_build: dict[str, list[str]] = {}
    for name in profiles:
        by_build.setdefault(PROFILES[name][0], []).append(name)
    outputs, records = {}, {}
    for build, names in by_build.items():
        document = documents[build]
        arms = tuple(sorted({PROFILES[name][1] for name in names}))
        built = variant_outputs(document, tree, row["problem_statement"], include=include, count_tokens=counter,
                                counter_label=label, budget_tokens=budget_tokens, arms=arms, sources=sources,
                                arm_flags={arm: dict(arm_flags) for arm in arms} if arm_flags else None)
        nodes = {node["id"]: node for node in document["nodes"]}
        for name in names:
            outputs[name] = built[PROFILES[name][1]]
            records[name] = graph_rank(row["instance_id"], outputs[name]["candidates"], nodes, sources, corpus, arm=name)
    text = ({"bm25": bm25_rank(row["instance_id"], row["problem_statement"], sources),
             "grep": grep_rank(row["instance_id"], row["problem_statement"], sources),
             "neighbor": neighbor_rank(row["instance_id"], row["problem_statement"], sources)} if with_text else {})
    gold = extract_gold(row["patch"], sources)   # only after every ranking above
    if gold.get("function_labels_complete", True):
        gold["frontier_functions"] = frontier_core_v2(row["patch"], gold, corpus)
    arms: dict[str, Any] = {}
    for name, record in records.items():
        out, document = outputs[name], documents[PROFILES[name][0]]
        scored = score_record(record, gold, budget_tokens=budget_tokens, counter=counter, counter_label=label)
        metrics = (flat_metrics(scored) | native_context_metrics(out["context"], gold, corpus)
                   | component_metrics(document, [item.path for item in record.items], gold_files=gold["gold_files"]))
        metrics.update(anchor_count=len(out["anchors"]), retrieve_seconds=out["seconds"],
                       candidate_count=len(out["candidates"]),
                       traversal_limited=bool(out["diagnostics"]["traversal_limited"]))
        arms[name] = {"metrics": metrics, "ranked": record.to_json()["items"][:100], "anchors": list(out["anchors"])[:50],
                      "diagnostics": out.get("diagnostics", {})}
    for name, record in text.items():
        arms[name] = _text_arm(record, gold, documents.get("base") or next(iter(documents.values())), budget_tokens,
                               counter, label)
    cross_file = len(gold["gold_files"]) >= 2
    impact: dict[str, Any] = {}
    if cross_file:
        diff, _ = filter_patch(row["patch"], set(gold["gold_files"]))
        for build in by_build:
            try:
                impact[build] = cross_file_reach(diff, documents[build], tree)
            except Exception as error:  # noqa: BLE001 -- recorded, the retrieval scores still count
                impact[build] = {"error": f"{type(error).__name__}: {error}"}
    return {"instance_id": row["instance_id"], "status": "SUCCEEDED", "cross_file": cross_file, "gold": gold,
            "arms": arms, "impact": impact}


def prepare_task(root: Path, row: dict) -> tuple[dict[str, str], Path]:
    """Sources and extracted tree of a task, the way R1 gets them."""
    sources, provenance = read_repository_sources(row, root / "data" / "repositories", network=True)
    tree = root / "data" / "repositories" / "trees" / runner.key_of(row)
    extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
    return sources, tree


def run_offline_task(root: Path, row: dict, profiles: list[str], tools: dict[str, str], *, out_dir: Path,
                     graphs_dir: Path, builder_hash: str, budget_tokens: int, resume: bool,
                     arm_flags: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Score one task and write ``<out_dir>/tasks/<id>.json``; with ``resume`` only missing profiles are computed."""
    path = out_dir / "tasks" / f"{row['instance_id']}.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if resume and path.exists() else None
    if previous is not None and previous.get("status") != "SUCCEEDED":
        previous = None
    todo = [name for name in profiles if previous is None or name not in previous["arms"]]
    if previous is not None and not todo:
        return previous
    sources, tree = prepare_task(root, row)
    documents, graphs = {}, {}
    for build in dict.fromkeys(PROFILES[name][0] for name in todo):
        documents[build], meta = load_or_build(root, row, tree, build=build, layers=build_layers(build, tools),
                                               graphs_dir=graphs_dir, builder_hash=builder_hash)
        graphs[build] = {key: str(value) if isinstance(value, Path) else value for key, value in meta.items()}
    with_text = previous is None or any(name not in previous["arms"] for name in TEXT_ARMS)
    result = evaluate_profiles(row, sources, tree, documents, todo, counter=bytes_div4_counter,
                               label=FALLBACK_COUNTER_LABEL, budget_tokens=budget_tokens, with_text=with_text,
                               arm_flags=arm_flags)
    result["graphs"] = graphs
    result["arm_flags"] = dict(arm_flags or {})
    if previous is not None:
        result["arms"] = previous["arms"] | result["arms"]
        result["impact"] = previous.get("impact", {}) | result["impact"]
        result["graphs"] = previous.get("graphs", {}) | graphs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return result


def _tools(args: argparse.Namespace) -> dict[str, str]:
    options = {"VGAR_NODE": args.node, "VGAR_SCIP_ENTRY": args.scip_entry, "VGAR_LSP_ENTRY": args.lsp_entry,
               "VGAR_TSG_EXECUTABLE": args.tsg_executable, "VGAR_TSG_TREE_SITTER_DIR": args.tsg_tree_sitter_dir}
    tools = {name: str(Path(value).expanduser().resolve()) for name, value in options.items() if value}
    tools["VGAR_SCIP_TIMEOUT"] = str(args.scip_timeout)
    return tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profiles", default="P0,A1,A2,A3", help=f"comma-separated, from {','.join(PROFILE_ORDER)}")
    parser.add_argument("--only", type=Path, help="file of instance ids")
    parser.add_argument("--resume", action="store_true", help="keep finished profiles, add missing ones")
    parser.add_argument("--graphs-dir", type=Path, help="SQLite graphs (default <root>/graphs)")
    parser.add_argument("--budget-tokens", type=int, default=12000)
    parser.add_argument("--node", help="Node executable for SCIP / LSP")
    parser.add_argument("--scip-entry", help="scip-python index.js")
    parser.add_argument("--scip-timeout", type=float, default=900)
    parser.add_argument("--lsp-entry", help="language server entry")
    parser.add_argument("--tsg-executable")
    parser.add_argument("--tsg-tree-sitter-dir")
    parser.add_argument("--arm-flags", type=json.loads, default={},
                        help='JSON RetrievalConfig fields for every graph arm, e.g. {"max_candidates": 100}')
    args = parser.parse_args(argv)
    unknown = sorted(set(args.arm_flags) - {item.name for item in fields(RetrievalConfig)})
    if unknown:
        parser.error(f"--arm-flags: unknown RetrievalConfig field(s) {unknown}")
    profiles = args.profiles.split(",")
    if set(profiles) - set(PROFILES):
        parser.error(f"--profiles: unknown {sorted(set(profiles) - set(PROFILES))}")
    root = args.root.expanduser().resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require_split(manifest, allowed=("dev",), protocol="r1")
    tasks = manifest["tasks"]
    if args.only:
        wanted = set(args.only.read_text(encoding="utf-8").split())
        tasks = [task for task in tasks if task["instance_id"] in wanted]
    tools = _tools(args)
    for name in profiles:   # fail before any task when a build lacks a tool path
        build_layers(PROFILES[name][0], tools)
    builder_hash = runner.source_fingerprint(ROOT)["digest"]
    graphs_dir = (args.graphs_dir or root / "graphs").expanduser()
    for number, row in enumerate(tasks, 1):
        validate_task(row)
        patch = (root / row["gold_patch_path"]).read_text(encoding="utf-8")
        if runner.sha256(patch) != row["patch_hash"]:
            raise SystemExit(f"{row['instance_id']}: gold patch hash mismatch")
        try:
            run_offline_task(root, dict(row, patch=patch), profiles, tools, out_dir=args.out, graphs_dir=graphs_dir,
                             builder_hash=builder_hash, budget_tokens=args.budget_tokens, resume=args.resume,
                             arm_flags=args.arm_flags)
            status = "SUCCEEDED"
        except Exception as error:  # noqa: BLE001 -- the task stays in the run with its reason
            status = f"ERROR {type(error).__name__}: {error}"
            failed = args.out / "tasks" / f"{row['instance_id']}.json"
            if not failed.exists():
                failed.parent.mkdir(parents=True, exist_ok=True)
                failed.write_text(json.dumps({"instance_id": row["instance_id"], "status": "ERROR",
                                              "reason": status}) + "\n", encoding="utf-8")
        print(f"[{number}/{len(tasks)}] {row['instance_id']}: {status}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
