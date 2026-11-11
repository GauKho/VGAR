"""Offline ablation: retrieval without the task trace (R-A1) vs with it (R-A2).

For each dev task: download the source archive at ``base_commit``, build the
graph once, run both arms of ``retrieval_variants``, score them with the
pipeline's ``evaluate_graph_task`` (same gold, budget and packing as
``run_graph_retrieval.py``), write ``<out>/tasks/<id>.json``, then delete the
task's archive and tree (``--prune``). ``--resume`` skips tasks already written.
``summarize`` pairs the arms per task (bootstrap CI95).

Usage:
    python ablation_matrix/run_no_trace_ablation.py <root> <gold manifest> --out <dir> \
        --allow-fallback-counter [--only ids.txt] [--prune] [--resume]
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "scripts")]

import run_graph_retrieval as runner
from retrieval_variants import ARMS, variant_outputs

from vgar.evaluation.retrieval.compare import paired_stats
from vgar.evaluation.retrieval.dataset import (
    read_repository_sources,
    require_split,
    validate_task,
)
from vgar.evaluation.retrieval.graph_arm import (
    evaluate_graph_task,
    extract_python_tree,
)
from vgar.evaluation.retrieval.resolver_comparison import (
    native_context_metrics,
)
from vgar.evaluation.retrieval.scoring import (
    FALLBACK_COUNTER_LABEL,
    CorpusIndex,
    bytes_div4_counter,
    make_include,
)

KEY_METRICS = ("file_recall@5", "function_recall@5", "file_mrr", "function_mrr",
               "packed_gold_file_in_context", "packed_gold_function_in_context", "context_tokens", "no_anchors")


def evaluate_task(root: Path, row: dict[str, Any], args: argparse.Namespace, builder_hash: str,
                  counter: Any, label: str) -> dict[str, Any]:
    """Build one task's graph and score both arms on it.

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
    tree_meta = extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
    document, graph_meta = runner.load_or_build_graph(root, row, tree, rebuild=False, builder_hash=builder_hash,
                                                      cache=False)
    corpus = CorpusIndex(sources)
    outputs = variant_outputs(document, tree, row["problem_statement"], include=make_include(corpus),
                              count_tokens=counter, counter_label=label, budget_tokens=args.budget_tokens)
    contexts = {arm: outputs[arm].pop("context") for arm in ARMS}
    nodes = {node["id"]: node for node in document["nodes"]}
    result = evaluate_graph_task(dict(row, patch=patch), sources, corpus, nodes, outputs,
                                 budget_tokens=args.budget_tokens, counter=counter, counter_label=label)
    for arm, context in contexts.items():
        result["arms"][arm]["metrics"].update(native_context_metrics(context, result["gold"], corpus))
    result.update(graph={k: graph_meta[k] for k in ("build_seconds", "nodes", "edges", "graph_version")},
                  source_tree={k: tree_meta[k] for k in ("python_file_count", "tree_hash")},
                  duration_seconds=time.perf_counter() - started)
    return result


def _prune(root: Path, row: dict[str, Any]) -> None:
    stem = runner.key_of(row)
    archive = root / "data" / "repositories" / "archives" / f"{stem}.tar.gz"
    for path in (archive, archive.with_suffix(".json")):
        path.unlink(missing_ok=True)
    shutil.rmtree(root / "data" / "repositories" / "trees" / stem, ignore_errors=True)


def summarize(out: Path, seed: int = 0) -> dict[str, Any]:
    """Means per arm and paired deltas (no_task_trace minus task_trace) over succeeded tasks.

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
    per_arm = {arm: {i: done[i]["arms"][arm]["metrics"] for i in done} for arm in ARMS}
    means = {arm: {name: statistics.fmean(values) if (values := [m[name] for m in per_arm[arm].values()
                                                                  if m.get(name) is not None]) else None
                   for name in KEY_METRICS} for arm in ARMS}
    pairs = paired_stats(per_arm["task_trace"], per_arm["no_task_trace"], seed) if done else {}
    return {"succeeded": len(done), "failed": failed, "means": means,
            "no_task_trace_minus_task_trace": {k: v for k, v in pairs.items() if v.get("n")}}


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
    print(json.dumps({"means": summary["means"], "failed": summary["failed"]}, indent=1))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
