"""M2/M3: Graph retrieval arm on a dev manifest -> results/retrieval/<run>/ (same scoring as BM25).

Per task: one graph build (cached), then TWO arms from the same retriever:
  graph      anchors from problem_statement only
  graph_f2p  anchors from problem_statement + SWE-bench FAIL_TO_PASS (task trace)

  python scripts/run_graph_retrieval.py . data/manifests/verified-<rev12>-dev-25.json \
      --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json --budget-tokens 8000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.dataset import read_repository_sources, require_split, validate_task
from vgar.evaluation.retrieval.evaluation import DEFAULT_BUDGET_TOKENS, DEFAULT_SNIPPET_LINES
from vgar.evaluation.retrieval.evidence import new_run, sha256, source_fingerprint, utc_now, write_json
from vgar.evaluation.retrieval.graph_arm import (ARMS, evaluate_graph_task, extract_python_tree, load_fail_to_pass)
from vgar.evaluation.retrieval.metrics import aggregate_metrics
from vgar.evaluation.retrieval.scoring import (FALLBACK_COUNTER_LABEL, SCORING_VERSION, CorpusIndex, bytes_div4_counter,
                                               make_include)

KEY_METRICS = ("file_recall@5", "function_recall@5", "file_mrr", "function_mrr", "packed_gold_function_in_context",
               "no_anchors", "unmapped_count", "context_tokens")


def key_of(row: dict) -> str:
    return f"{row['repo'].replace('/', '__')}-{row['base_commit']}"


def load_or_build_graph(root: Path, row: dict, tree: Path, *, use_jedi: bool, rebuild: bool, builder_hash: str):
    """Graph cache key includes the builder source hash: when M1 patches builder.py the cache invalidates itself."""
    from vgar.graph.builder import PythonGraphBuilder
    name = f"{key_of(row)}-{'jedi' if use_jedi else 'nojedi'}-{builder_hash}"
    graph_path = root / "data" / "graphs" / f"{name}.json"
    meta_path = graph_path.with_suffix(".meta.json")
    if graph_path.exists() and meta_path.exists() and not rebuild:
        return json.loads(graph_path.read_text(encoding="utf-8")), json.loads(meta_path.read_text(encoding="utf-8")) | {"cached": True}
    started = time.perf_counter()
    builder = PythonGraphBuilder(repo_key=row["repo"].replace("/", "__"), repository_revision=row["base_commit"], use_jedi=use_jedi)
    document = builder.build(tree)
    meta = {"build_seconds": time.perf_counter() - started, "nodes": len(document["nodes"]), "edges": len(document["edges"]),
            "graph_version": document["graph_version"], "use_jedi": use_jedi, "builder_hash": builder_hash,
            "skipped_failed_files": len(getattr(builder, "skipped_failed_files", []) or [])}
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_json(meta_path, meta)
    return document, meta | {"cached": False}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--budget-tokens", type=int, default=DEFAULT_BUDGET_TOKENS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--no-jedi", action="store_true", help="tree-sitter only (faster, weaker CALLS); recorded in config")
    parser.add_argument("--rebuild-graphs", action="store_true")
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=100)
    parser.add_argument("--allow-heldout", action="store_true", help="FINAL evaluation only; never use while tuning")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tokenizer-manifest", type=Path)
    group.add_argument("--allow-fallback-counter", action="store_true")
    args = parser.parse_args()

    from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
    from vgar.graph.task_overlay import TaskOverlayBuilder
    if args.tokenizer_manifest:
        from vgar.graph.token_counter import LocalTokenizerCounter
        counter = LocalTokenizerCounter(args.tokenizer_manifest)
        label, fallback = counter.counter_label, False
    else:
        counter, label, fallback = bytes_div4_counter, FALLBACK_COUNTER_LABEL, True
        print("WARNING: fallback bytes/4 counter; NOT comparable with the BM25 baseline run", flush=True)

    root = args.root
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    for task in manifest["tasks"]:
        validate_task(task)
    require_split(manifest, allowed=("dev", "heldout") if args.allow_heldout else ("dev",))
    tasks = manifest["tasks"][:args.limit] if args.limit else manifest["tasks"]
    fail_to_pass = load_fail_to_pass(root, manifest)
    builder_hash = hashlib.sha256((ROOT / "src" / "vgar" / "graph" / "builder.py").read_bytes()).hexdigest()[:12]
    retrieval_config = RetrievalConfig(max_hops=args.max_hops, max_candidates=args.max_candidates)

    config = {"manifest_hash": sha256(manifest_bytes), "budget_tokens": args.budget_tokens, "scoring_version": SCORING_VERSION,
              "counter_label": label, "counter_is_fallback": fallback,
              "snippet_policy": {"max_snippet_lines": DEFAULT_SNIPPET_LINES, "header": True, "overlap": "skip_if_overlaps_different_group"},
              "arms": {arm: {"uses_fail_to_pass": uses} for arm, uses in ARMS.items()},
              "graph": {"use_jedi": not args.no_jedi, "builder_hash": builder_hash, "source_roots": ["src"]},
              "retrieval": {"max_hops": args.max_hops, "max_candidates": args.max_candidates,
                            "min_edge_confidence": retrieval_config.min_edge_confidence, "weights": retrieval_config.weights,
                            "include": "make_include(corpus): not Test and path in is_source corpus"}, "limit": args.limit}
    directory, record = new_run(root / "results" / "retrieval", "retrieval_graph")
    record.update(config=config, source=source_fingerprint(root), dataset_id=manifest["dataset_id"],
                  dataset_revision=manifest["dataset_revision"], manifest_path=str(args.manifest.resolve()),
                  task_results=[], stdout="", stderr="", exit_code=None)
    write_json(directory / "result.json", record)
    started = time.perf_counter()
    per_arm: dict[str, list[dict]] = {arm: [] for arm in ARMS}

    for number, row in enumerate(tasks, 1):
        task_start = time.perf_counter()
        try:
            patch_path = (root / row["gold_patch_path"]).resolve()
            if not patch_path.is_relative_to(root.resolve() / "data" / "gold"):
                raise ValueError("Gold patch path outside data/gold")
            patch = patch_path.read_text(encoding="utf-8")
            if sha256(patch) != row["patch_hash"] or sha256(row["problem_statement"]) != row["query_hash"]:
                raise ValueError("Manifest patch/query hash mismatch")
            sources, provenance = read_repository_sources(row, root / "data" / "repositories", network=not args.offline)
            tree = root / "data" / "repositories" / "trees" / key_of(row)
            tree_meta = extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
            document, graph_meta = load_or_build_graph(root, row, tree, use_jedi=not args.no_jedi, rebuild=args.rebuild_graphs,
                                                       builder_hash=builder_hash)
            corpus = CorpusIndex(sources)
            include = make_include(corpus)
            overlays = TaskOverlayBuilder(document)
            retriever = GraphContextRetriever(document, tree, count_tokens=counter, counter_label=label, config=retrieval_config)
            outputs = {}
            for arm, uses_f2p in ARMS.items():
                arm_start = time.perf_counter()
                overlay = overlays.build(f"{row['instance_id']}:{arm}", row["problem_statement"],
                                         list(fail_to_pass[row["instance_id"]]) if uses_f2p else None)
                anchors = [{"node_id": a.node_id, "score": a.score, "symbol": retriever.nodes[a.node_id]["qualified_name"],
                            "type": retriever.nodes[a.node_id]["type"], "path": retriever.nodes[a.node_id]["path"]}
                           for a in overlay.grounding.anchors]
                result = retriever.retrieve([a["node_id"] for a in anchors], args.budget_tokens,
                                            issue_text=row["problem_statement"], overlay=overlay, include=include)
                reasons: dict[str, int] = {}
                for omission in result.omissions:
                    reasons[omission["reason"]] = reasons.get(omission["reason"], 0) + 1
                outputs[arm] = {"candidates": result.candidates, "anchors": anchors, "seconds": time.perf_counter() - arm_start,
                                "diagnostics": {"m1_native_total_tokens": result.context.total_token_count,
                                                "m1_native_items": len(result.context.items),
                                                "m1_native_truncated": result.context.truncated,
                                                "traversal_limited": result.traversal_limited,
                                                "unavailable_features": result.unavailable_features,
                                                "omissions": reasons, "retrieval_config": result.config}}
            result = evaluate_graph_task(dict(row, patch=patch), sources, corpus, retriever.nodes, outputs,
                                         budget_tokens=args.budget_tokens, counter=counter, counter_label=label)
            result.update(graph=graph_meta, source_tree={k: tree_meta[k] for k in ("python_file_count", "tree_hash")},
                          source_provenance=provenance, fail_to_pass_count=len(fail_to_pass[row["instance_id"]]),
                          duration_seconds=time.perf_counter() - task_start)
            for arm, data in result["arms"].items():
                per_arm[arm].append({"instance_id": row["instance_id"], "status": "SUCCEEDED", "metrics": data["metrics"]})
            summary_row = {"instance_id": row["instance_id"], "status": "SUCCEEDED", "duration_seconds": result["duration_seconds"],
                           "graph_build_seconds": graph_meta["build_seconds"], "graph_cached": graph_meta["cached"],
                           "graph_nodes": graph_meta["nodes"], "graph_edges": graph_meta["edges"],
                           "corpus_hash": result["corpus_hash"], "query_hash": result["query_hash"],
                           "arms": {arm: {k: data["metrics"].get(k) for k in KEY_METRICS} for arm, data in result["arms"].items()}}
        except Exception as exc:                                      # one bad task never kills the run
            result = {"instance_id": row["instance_id"], "status": "FAILED", "error_class": type(exc).__name__, "error": str(exc),
                      "duration_seconds": time.perf_counter() - task_start}
            for arm in ARMS:
                per_arm[arm].append({"instance_id": row["instance_id"], "status": "FAILED", "metrics": {}})
            record["stderr"] += f"{row['instance_id']}: {type(exc).__name__}: {exc}\n"
            summary_row = {k: result[k] for k in ("instance_id", "status", "error_class", "error", "duration_seconds")}
        artifact = directory / "tasks" / f"{row['instance_id']}.json"
        write_json(artifact, result)
        summary_row["artifact_hash"] = sha256(artifact.read_bytes())
        record["task_results"].append(summary_row)
        message = f"[{number}/{len(tasks)}] {row['instance_id']}: {result['status']} ({result['duration_seconds']:.1f}s)"
        print(message, flush=True)
        record["stdout"] += message + "\n"
        record["summary_by_arm"] = {arm: aggregate_metrics(items) for arm, items in per_arm.items()}
        write_json(directory / "result.json", record)

    failed = sum(item["status"] != "SUCCEEDED" for item in record["task_results"])
    record.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                  status="SUCCEEDED" if not failed else "PARTIAL_FAILURE", exit_code=0 if not failed else 1)
    write_json(directory / "result.json", record)
    print(f"\nrun: {directory}")
    for arm, summary in record["summary_by_arm"].items():
        cells = [f"{name}={summary['metrics'][name]['mean']:.3f}" for name in KEY_METRICS
                 if name in summary["metrics"] and summary["metrics"][name]["mean"] is not None]
        print(f"  {arm}: " + "  ".join(cells))
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
