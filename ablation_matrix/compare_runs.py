"""Paired comparison of two R1 runs (candidate - base), per arm and metric, with a bootstrap CI95.

  python ablation_matrix/compare_runs.py ~/rt1/results r1_50 r1_scip50 [--ready scip]
  python ablation_matrix/compare_runs.py ~/rt1/results scope_a_tune25_seed --arms-vs task_trace_rt1

``--ready LAYER`` keeps only the tasks where that optional layer was ``ready`` in the candidate run (for example the
tasks where SCIP really ran instead of falling back to the static resolver). Writes
``<results>/<candidate>/paired_vs_<base>[_ready_<layer>].json`` and prints the tables. Same method as the comparison
used for the full-layer report (``tv2_r1_full_layers_2026-11-16.md``): bootstrap 2,000 rounds, seed 7.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import statistics
from pathlib import Path
from typing import Any

ARMS = ("bm25", "grep", "neighbor", "no_task_trace", "task_trace", "a3", "ast_no_task_trace", "arch_no_task_trace",
        "task_trace_rt1")
METRICS = ("file_recall@1", "file_recall@5", "file_recall@10", "function_recall@5", "function_recall@10", "file_mrr",
           "function_mrr", "function_reach", "packed_gold_file_in_context", "packed_gold_function_in_context",
           "packed_all_gold_files_in_context", "packed_frontier_in_context", "component_recall@1", "context_tokens",
           # the context the MCP server returns (packed_* above is R1's own re-pack of the ranking)
           "native_gold_function_in_context", "native_all_gold_files_in_context", "native_frontier_in_context",
           "native_context_tokens")


def load(run: Path) -> dict[str, dict[str, Any]]:
    return {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in sorted(run.glob("tasks/*.json"))}


def layer_status(task: dict[str, Any], layer: str) -> str | None:
    return ((task.get("layers_and_flags") or {}).get("layer_status") or {}).get(layer, {}).get("status")


def ci95(deltas: list[float], seed: int = 7, rounds: int = 2000) -> list[float]:
    if not any(deltas):
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(deltas) for _ in deltas) for _ in range(rounds))
    return [means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]]


def _add_pair(out: dict[str, Any], label: str, ids: list[str], before, after) -> None:
    """Paired stats per metric of ``after(i) - before(i)`` metric dicts, stored under ``label``."""
    out["means"][label], out["pairs"][label] = {}, {}
    for metric in METRICS:
        pairs = [(before(i).get(metric), after(i).get(metric)) for i in ids]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if not pairs:
            continue
        deltas = [b - a for a, b in pairs]
        out["means"][label][metric] = [statistics.fmean(a for a, _ in pairs), statistics.fmean(b for _, b in pairs)]
        out["pairs"][label][metric] = {"n": len(deltas), "delta": statistics.fmean(deltas), "ci95": ci95(deltas),
                                       "wins": sum(d > 0 for d in deltas), "losses": sum(d < 0 for d in deltas)}


def gold_file_count(task: dict[str, Any]) -> int:
    return len(task.get("gold", {}).get("gold_files", []))


def compare_arms(run: dict[str, dict], base_arm: str, arms: list[str], min_gold_files: int = 0) -> dict[str, Any]:
    """Each arm against ``base_arm`` inside one run (same tasks, same graphs): the tuning comparison."""
    ids = sorted(i for i in run if base_arm in run[i]["arms"] and gold_file_count(run[i]) >= min_gold_files)
    out: dict[str, Any] = {"n_tasks": len(ids), "base_arm": base_arm, "min_gold_files": min_gold_files,
                           "means": {}, "pairs": {}}
    for arm in arms:
        if ids and all(arm in run[i]["arms"] for i in ids):
            _add_pair(out, arm, ids, lambda i: run[i]["arms"][base_arm]["metrics"],
                      lambda i, arm=arm: run[i]["arms"][arm]["metrics"])
    return out


def compare(base: dict[str, dict], cand: dict[str, dict], ready: str | None = None,
            min_gold_files: int = 0) -> dict[str, Any]:
    ids = sorted(i for i in set(base) & set(cand) if (ready is None or layer_status(cand[i], ready) == "ready")
                 and gold_file_count(cand[i]) >= min_gold_files)
    out: dict[str, Any] = {"n_tasks": len(ids), "ready_filter": ready, "min_gold_files": min_gold_files,
                           "means": {}, "pairs": {}}
    for arm in ARMS:
        if not ids or arm not in cand[ids[0]]["arms"] or arm not in base[ids[0]]["arms"]:
            continue
        _add_pair(out, arm, ids, lambda i, arm=arm: base[i]["arms"][arm]["metrics"],
                  lambda i, arm=arm: cand[i]["arms"][arm]["metrics"])
    statuses, failed = collections.Counter(), []
    for i in sorted(set(base) & set(cand)):
        for layer, value in ((cand[i].get("layers_and_flags") or {}).get("layer_status") or {}).items():
            statuses[f"{layer}:{value['status']}"] += 1
            if value["status"] == "failed":
                failed.append([i, layer, (value.get("reason") or "")[:80]])
    out["layer_status"], out["layer_failed"] = dict(statuses), failed
    if ids:
        out["build_seconds"] = {"base": statistics.fmean(base[i]["graph"]["build_seconds"] for i in ids),
                                "candidate": statistics.fmean(cand[i]["graph"]["build_seconds"] for i in ids)}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", type=Path, help="folder holding the run folders, e.g. ~/rt1/results")
    parser.add_argument("base", help="base run folder, or the one run compared with --arms-vs")
    parser.add_argument("candidate", nargs="?")
    parser.add_argument("--ready", help="keep only tasks where this layer was ready in the candidate run")
    parser.add_argument("--min-gold-files", type=int, default=0,
                        help="keep only tasks whose gold patch changes at least this many files (2 = multi-file)")
    parser.add_argument("--arms-vs", metavar="BASE_ARM",
                        help="compare every other graph arm of the one run BASE with this arm (tuning)")
    args = parser.parse_args(argv)
    results = args.results.expanduser()
    multi = f"_min{args.min_gold_files}files" if args.min_gold_files else ""
    if args.arms_vs:
        run = load(results / args.base)
        arms = sorted({arm for task in run.values() for arm in task["arms"]} - set(ARMS[:3]) - {args.arms_vs})
        out = compare_arms(run, args.arms_vs, arms, args.min_gold_files)
        target = results / args.base / f"arms_vs_{args.arms_vs}{multi}.json"
    elif args.candidate:
        out = compare(load(results / args.base), load(results / args.candidate), args.ready, args.min_gold_files)
        suffix = f"_ready_{args.ready}" if args.ready else ""
        target = results / args.candidate / f"paired_vs_{args.base}{suffix}{multi}.json"
    else:
        parser.error("give a candidate run, or --arms-vs BASE_ARM")
    target.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out.get(k) for k in ("n_tasks", "base_arm", "ready_filter", "layer_status", "build_seconds")
                      if k in out}, indent=1))
    for arm, pairs in out["pairs"].items():
        print(arm, {m: (round(p["delta"], 3), [round(x, 3) for x in p["ci95"]], p["wins"], p["losses"])
                    for m, p in pairs.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
