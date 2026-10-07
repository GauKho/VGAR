"""Graph retrieval evaluation: isolated tasks, verified caches and immutable resume forks.

No inference/model weights. graph_f2p is explicitly oracle-assisted benchmark metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.dataset import require_split, validate_task
from vgar.evaluation.retrieval.evaluation import DEFAULT_BUDGET_TOKENS, DEFAULT_SNIPPET_LINES
from vgar.evaluation.retrieval.evidence import new_run, sha256, source_fingerprint, utc_now, write_json
from vgar.evaluation.retrieval.graph_arm import ARMS, load_fail_to_pass
from vgar.evaluation.retrieval.graph_cache import load_or_build_graph
from vgar.evaluation.retrieval.lifecycle import resume_successes, run_worker
from vgar.evaluation.retrieval.metrics import aggregate_metrics
from vgar.evaluation.retrieval.scoring import FALLBACK_COUNTER_LABEL, SCORING_VERSION

KEY_METRICS = ("file_recall@5", "function_recall@5", "file_mrr", "function_mrr", "packed_gold_function_in_context",
               "no_anchors", "unmapped_count", "context_tokens")


def _summary(result: dict) -> dict:
    keys = ("instance_id", "status", "duration_seconds", "error_class", "error", "phase", "peak_rss_bytes")
    summary = {key: result[key] for key in keys if key in result}
    if result["status"] == "SUCCEEDED":
        meta = result["graph"]
        summary.update(graph_build_seconds=meta["build_seconds"], graph_cached=meta["cached"],
                       graph_nodes=meta["nodes"], graph_edges=meta["edges"],
                       corpus_hash=result["corpus_hash"], query_hash=result["query_hash"],
                       arms={arm: {k: data["metrics"].get(k) for k in KEY_METRICS} for arm, data in result["arms"].items()})
    return summary


def _execute(args, directory: Path, record: dict) -> None:
    from vgar.graph.retrieval import RetrievalConfig
    root = args.root.resolve()
    for key, value in (("budget", args.budget_tokens), ("max_candidates", args.max_candidates),
                       ("limit", args.limit)):
        if value is not None and value < 1:
            raise ValueError(f"{key} must be positive")
    if not math.isfinite(args.task_timeout_seconds) or args.task_timeout_seconds <= 0:
        raise ValueError("task timeout must be positive and finite")
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest.get("tasks"), list) or not manifest["tasks"]:
        raise ValueError("Manifest needs a nonempty task list")
    ids = set()
    for task in manifest["tasks"]:
        validate_task(task)
        if task["instance_id"] in ids:
            raise ValueError("Duplicate instance IDs in manifest")
        ids.add(task["instance_id"])
    require_split(manifest, allowed=("dev", "heldout") if args.allow_heldout else ("dev",))
    tasks = manifest["tasks"]
    if args.task_id:
        if len(set(args.task_id)) != len(args.task_id) or set(args.task_id) - ids:
            raise ValueError("Duplicate or unknown --task-id")
        tasks = [task for task in tasks if task["instance_id"] in args.task_id]
    if args.limit is not None:
        tasks = tasks[:args.limit]
    if args.tokenizer_manifest:
        from vgar.graph.token_counter import LocalTokenizerCounter
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        label, fallback, tokenizer_binding = counter.counter_label, False, counter.provenance
    else:
        label, fallback, tokenizer_binding = FALLBACK_COUNTER_LABEL, True, None
        print("WARNING: fallback bytes/4 is diagnostic, not official benchmark accounting", flush=True)
    fail_to_pass = load_fail_to_pass(root, dict(manifest, tasks=tasks))
    builder_hash = hashlib.sha256((ROOT / "src/vgar/graph/builder.py").read_bytes()).hexdigest()[:12]
    retrieval = RetrievalConfig(max_hops=args.max_hops, max_candidates=args.max_candidates)
    config = {"manifest_hash": sha256(manifest_bytes), "budget_tokens": args.budget_tokens, "scoring_version": SCORING_VERSION,
              "counter_label": label, "counter_is_fallback": fallback,
              "snippet_policy": {"max_snippet_lines": DEFAULT_SNIPPET_LINES, "header": True, "overlap": "skip_if_overlaps_different_group"},
              "arms": {arm: {"uses_fail_to_pass": uses} for arm, uses in ARMS.items()},
              "graph": {"use_jedi": not args.no_jedi, "builder_hash": builder_hash, "source_roots": ["src"]},
              "retrieval": {"max_hops": args.max_hops, "max_candidates": args.max_candidates,
                            "min_edge_confidence": retrieval.min_edge_confidence, "weights": retrieval.weights,
                            "include": "make_include(corpus): not Test and path in is_source corpus"},
              "limit": args.limit, "task_ids": [row["instance_id"] for row in tasks],
              "execution": {"task_timeout_seconds": args.task_timeout_seconds, "offline": args.offline,
                            "rebuild_graphs": args.rebuild_graphs, "rebuild_trees": args.rebuild_trees}}
    source = source_fingerprint(ROOT)
    identity = {"config": config, "source_digest": source["digest"], "source_root": str(root),
                "dataset_id": manifest["dataset_id"], "dataset_revision": manifest["dataset_revision"],
                "tokenizer_binding": tokenizer_binding, "f2p_hash": sha256(json.dumps(fail_to_pass, sort_keys=True))}
    record.update(config=config, source=source, resume_identity=identity, inference="NOT_RUN",
                  dataset_id=manifest["dataset_id"], dataset_revision=manifest["dataset_revision"],
                  manifest_path=str(args.manifest.resolve()), selected_task_ids=config["task_ids"])
    successes = resume_successes(args.resume_run, directory, identity) if args.resume_run else {}
    if set(successes) - set(config["task_ids"]):
        raise ValueError("Resume successes outside selected population")
    record.update(phase="TASKS", resumed_from=str(args.resume_run.resolve()) if args.resume_run else None)
    write_json(directory / "result.json", record)
    per_arm = {arm: [] for arm in ARMS}
    for number, row in enumerate(tasks, 1):
        iid = row["instance_id"]
        interrupted = False
        if iid in successes:
            summary = successes[iid]
            result = json.loads((directory / "tasks" / f"{iid}.json").read_text(encoding="utf-8"))
        else:
            attempt = directory / "attempts" / iid / uuid.uuid4().hex
            request = {"root": str(root), "row": row, "config": config, "failing_tests": fail_to_pass[iid],
                       "offline": args.offline, "rebuild_graphs": args.rebuild_graphs,
                       "rebuild_trees": args.rebuild_trees,
                       "tokenizer_manifest": str(args.tokenizer_manifest.resolve()) if args.tokenizer_manifest else None}
            try:
                result = run_worker(request, attempt, args.task_timeout_seconds)
            except KeyboardInterrupt:
                result = json.loads((attempt / "result.json").read_text(encoding="utf-8"))
                interrupted = True
            artifact = directory / "tasks" / f"{iid}.json"
            write_json(artifact, result)
            summary = _summary(result)
            summary.update(artifact_hash=sha256(artifact.read_bytes()), attempt_path=str(attempt.resolve()))
        record["task_results"].append(summary)
        for arm in ARMS:
            per_arm[arm].append({"instance_id": iid, "status": result["status"],
                                "metrics": result.get("arms", {}).get(arm, {}).get("metrics", {})})
        record["summary_by_arm"] = {arm: aggregate_metrics(values) for arm, values in per_arm.items()}
        message = f"[{number}/{len(tasks)}] {iid}: {result['status']} ({result.get('duration_seconds', 0):.1f}s)"
        record["stdout"] += message + "\n"
        if result["status"] != "SUCCEEDED":
            record["stderr"] += f"{iid}: {result.get('error_class')}: {result.get('error')}\n"
        print(message, flush=True)
        write_json(directory / "result.json", record)
        if interrupted:
            raise KeyboardInterrupt()
    failed = sum(item["status"] != "SUCCEEDED" for item in record["task_results"])
    record.update(status="SUCCEEDED" if not failed else "PARTIAL_FAILURE", exit_code=0 if not failed else 1, phase="DONE")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--budget-tokens", type=int, default=DEFAULT_BUDGET_TOKENS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--no-jedi", action="store_true")
    parser.add_argument("--rebuild-graphs", action="store_true")
    parser.add_argument("--rebuild-trees", action="store_true",
                        help="Extract NEW raw-byte source trees; preserve legacy caches (e.g. Git CRLF checkout)")
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=100)
    parser.add_argument("--allow-heldout", action="store_true")
    parser.add_argument("--task-timeout-seconds", type=float, default=300)
    parser.add_argument("--resume-run", type=Path, help="NEW continuation run; prior successes/failed attempts stay immutable")
    parser.add_argument("--task-id", action="append", help="Select explicit manifest task(s); repeat option for multiple IDs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tokenizer-manifest", type=Path)
    group.add_argument("--allow-fallback-counter", action="store_true")
    args = parser.parse_args()
    # The first durable write precedes tokenizer, manifest, fingerprint and dataset setup.
    directory, record = new_run(args.root.resolve() / "results/retrieval", "retrieval_graph")
    started = time.perf_counter()
    record.update(phase="SETUP", task_results=[], stdout="", stderr="", exit_code=None, inference="NOT_RUN")
    write_json(directory / "result.json", record)
    print(f"run: {directory}", flush=True)
    try:
        _execute(args, directory, record)
    except (Exception, KeyboardInterrupt) as exc:
        record.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "ERROR",
                      error_class=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                      exit_code=130 if isinstance(exc, KeyboardInterrupt) else 1)
        record["stderr"] += record["traceback"]
        attempted = {r["instance_id"] for r in record["task_results"]}
        for iid in record.get("selected_task_ids", []):
            if iid not in attempted:
                record["task_results"].append({"instance_id": iid, "status": "NOT_RUN", "error": "run terminated before task"})
    finally:
        record.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
        write_json(directory / "result.json", record)
    print(f"status: {record['status']}; exit: {record['exit_code']}", flush=True)
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
