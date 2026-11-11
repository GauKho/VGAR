"""Offline R1 ablation: text baselines (A0) and graph configs (A1, A2, A3, AST-only, +arch, +RT-1) on one task set.

For each dev task: download the archive at ``base_commit``, build the graph once,
run every graph arm of ``retrieval_variants.GRAPH_ARM_SPECS`` and the text
baselines (BM25, grep, file-neighbor), score all of them against the same gold
with the pipeline's scorer, add component recall, write ``<out>/tasks/<id>.json``
and delete the task's archive and tree (``--prune``). ``summarize`` reports the
mean of every arm and the paired pairs of the spec (bootstrap CI95).

Usage:
    python ablation_matrix/run_r1_ablation.py <root> <gold manifest> --out <dir> \
        --allow-fallback-counter [--only ids.txt] [--prune] [--resume]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "scripts")]

import run_graph_retrieval as runner
from component_metrics import component_metrics
from retrieval_variants import GRAPH_ARMS, variant_outputs
from run_no_trace_ablation import _prune
from text_baselines import grep_rank, neighbor_rank

from vgar.evaluation.retrieval.dataset import (
    read_repository_sources,
    require_split,
    validate_task,
)
from vgar.evaluation.retrieval.graph_arm import evaluate_graph_task, extract_python_tree
from vgar.evaluation.retrieval.resolver_comparison import native_context_metrics
from vgar.evaluation.retrieval.scoring import (
    FALLBACK_COUNTER_LABEL,
    CorpusIndex,
    bm25_rank,
    bytes_div4_counter,
    flat_metrics,
    make_include,
    score_record,
)

TEXT_ARMS = ("bm25", "grep", "neighbor")
ALL_ARMS = TEXT_ARMS + GRAPH_ARMS
# (candidate, base): the candidate adds one thing to the base.
PAIRS = (
    ("no_task_trace", "bm25"), ("no_task_trace", "grep"), ("no_task_trace", "neighbor"),   # graph vs text (A1 vs A0)
    ("task_trace", "bm25"),                                                                   # A2 vs A0
    ("task_trace", "no_task_trace"),                                                          # task trace (A2 vs A1)
    ("a3", "task_trace"),                                                                     # architecture (A3 vs A2)
    ("no_task_trace", "ast_no_task_trace"),                                                   # call/import edges vs AST only
    ("arch_no_task_trace", "no_task_trace"),                                                  # architecture without task trace
    ("task_trace_rt1", "task_trace"),                                                         # RT1_CONFIG
)
METRICS = ("file_recall@1", "file_recall@3", "file_recall@5", "file_recall@10", "function_recall@1",
           "function_recall@3", "function_recall@5", "function_recall@10", "file_mrr", "function_mrr",
           "packed_gold_file_in_context", "packed_gold_function_in_context", "context_tokens",
           "component_recall@1", "component_recall@3", "component_recall@5", "component_mrr")


def _text_arm(record: Any, gold: dict[str, Any], document: dict[str, Any], budget: int, counter: Any,
              label: str) -> dict[str, Any]:
    scored = score_record(record, gold, budget_tokens=budget, counter=counter, counter_label=label)
    metrics = flat_metrics(scored) | component_metrics(document, [item.path for item in record.items],
                                                       gold_files=gold["gold_files"])
    detail = record.to_json()
    return {"rank_hash": record.rank_hash, "ranked": detail["items"][:100], "meta": record.meta, "metrics": metrics}


def evaluate_task(root: Path, row: dict[str, Any], args: argparse.Namespace, builder_hash: str,
                  counter: Any, label: str) -> dict[str, Any]:
    """Build one task's graph and score every arm on it.

    Args:
        root: Evaluation root holding ``data/``.
        row: Gold manifest task.
        args: Parsed command line.
        builder_hash: Fingerprint of the vgar source tree.
        counter: Token counter.
        label: Counter label.
    """
    started = time.perf_counter()
    patch = (root / row["gold_patch_path"]).read_text(encoding="utf-8")
    if runner.sha256(patch) != row["patch_hash"] or runner.sha256(row["problem_statement"]) != row["query_hash"]:
        raise ValueError("Manifest patch/query hash mismatch")
    sources, provenance = read_repository_sources(row, root / "data" / "repositories", network=not args.offline)
    tree = root / "data" / "repositories" / "trees" / runner.key_of(row)
    extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
    document, graph_meta = runner.load_or_build_graph(root, row, tree, rebuild=False, builder_hash=builder_hash,
                                                      cache=False)
    corpus = CorpusIndex(sources)
    # Every ranking is computed before the gold patch is parsed.
    outputs = variant_outputs(document, tree, row["problem_statement"], include=make_include(corpus),
                              count_tokens=counter, counter_label=label, budget_tokens=args.budget_tokens,
                              arms=GRAPH_ARMS)
    text_records = {"bm25": bm25_rank(row["instance_id"], row["problem_statement"], sources),
                    "grep": grep_rank(row["instance_id"], row["problem_statement"], sources),
                    "neighbor": neighbor_rank(row["instance_id"], row["problem_statement"], sources)}
    contexts = {arm: outputs[arm].pop("context") for arm in GRAPH_ARMS}
    nodes = {node["id"]: node for node in document["nodes"]}
    result = evaluate_graph_task(dict(row, patch=patch), sources, corpus, nodes, outputs,
                                 budget_tokens=args.budget_tokens, counter=counter, counter_label=label)
    for arm in GRAPH_ARMS:
        metrics = result["arms"][arm]["metrics"]
        metrics.update(native_context_metrics(contexts[arm], result["gold"], corpus))
        metrics.update(component_metrics(document, [row_["path"] for row_ in result["arms"][arm]["ranked"]],
                                         gold_files=result["gold"]["gold_files"]))
    for arm, record in text_records.items():
        result["arms"][arm] = _text_arm(record, result["gold"], document, args.budget_tokens, counter, label)
    result.update(graph={k: graph_meta[k] for k in ("build_seconds", "nodes", "edges", "graph_version")},
                  duration_seconds=time.perf_counter() - started)
    return result


def _bootstrap(deltas: list[float], seed: int, rounds: int = 2000) -> list[float]:
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(deltas) for _ in deltas) for _ in range(rounds))
    return [means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]]


def summarize(out: Path, seed: int = 0) -> dict[str, Any]:
    """Mean of every arm and the spec's paired comparisons over succeeded tasks.

    Args:
        out: Run folder holding ``tasks/*.json``.
        seed: Bootstrap seed.
    """
    done, failed = {}, []
    for path in sorted((out / "tasks").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "SUCCEEDED":
            done[data["instance_id"]] = data
        else:
            failed.append(data["instance_id"])

    def values(arm: str, name: str) -> dict[str, float]:
        return {i: v for i, d in done.items() if (v := d["arms"].get(arm, {}).get("metrics", {}).get(name)) is not None}

    means = {arm: {name: statistics.fmean(v.values()) if (v := values(arm, name)) else None for name in METRICS}
             for arm in ALL_ARMS}
    pairs: dict[str, dict[str, Any]] = {}
    for candidate, base in PAIRS:
        rows = {}
        for name in METRICS:
            cand, ref = values(candidate, name), values(base, name)
            deltas = [cand[i] - ref[i] for i in sorted(cand.keys() & ref.keys())]
            if deltas:
                rows[name] = {"n": len(deltas), "mean_delta": statistics.fmean(deltas), "ci95": _bootstrap(deltas, seed),
                              "wins": sum(d > 1e-9 for d in deltas), "losses": sum(d < -1e-9 for d in deltas)}
        pairs[f"{candidate} - {base}"] = rows
    return {"succeeded": len(done), "failed": failed, "means": means, "pairs": pairs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", type=Path)
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--budget-tokens", type=int, default=12000)
    parser.add_argument("--allow-fallback-counter", action="store_true", required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for task in manifest["tasks"]:
        validate_task(task)
    require_split(manifest, allowed=("dev",))
    tasks = manifest["tasks"]
    if args.only:
        wanted = set(args.only.read_text(encoding="utf-8").split())
        tasks = [task for task in tasks if task["instance_id"] in wanted]
    (args.out / "tasks").mkdir(parents=True, exist_ok=True)
    builder_hash = runner.source_fingerprint(ROOT)["digest"]
    for number, row in enumerate(tasks, 1):
        artifact = args.out / "tasks" / f"{row['instance_id']}.json"
        if artifact.exists():
            if args.resume:
                continue
            raise SystemExit(f"{artifact} exists; pass --resume")
        try:
            result = evaluate_task(root, row, args, builder_hash, bytes_div4_counter, FALLBACK_COUNTER_LABEL)
        except Exception as exc:  # noqa: BLE001 - one bad task never kills the run
            result = {"instance_id": row["instance_id"], "status": "FAILED", "error_class": type(exc).__name__,
                      "error": str(exc)}
        runner.write_json(artifact, result)
        print(f"[{number}/{len(tasks)}] {row['instance_id']}: {result['status']}", flush=True)
        if args.prune:
            _prune(root, row)
    summary = summarize(args.out)
    summary.update(manifest_hash=runner.sha256(args.manifest.read_bytes()), budget_tokens=args.budget_tokens,
                   counter_label=FALLBACK_COUNTER_LABEL, builder_hash=builder_hash)
    runner.write_json(args.out / "summary.json", summary)
    print(json.dumps({"succeeded": summary["succeeded"], "failed": summary["failed"]}))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
