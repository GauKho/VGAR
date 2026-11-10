"""RT-1 ablation over a dev manifest, one task at a time (RT-1 spec §5).

Each task's graph is built once and every named config is evaluated on it.
Every config gets its own run folder ``<out>/<NAME>/`` in the layout of
``run_graph_retrieval.py`` (``result.json`` + ``tasks/<id>.json``), so
``compare_graph_runs`` reads them. ``--prune`` deletes the task's archive,
source tree and graph once all configs are done, so the disk holds one task
at a time. ``--resume`` skips tasks that already have a result in every config.

Usage:
    python scripts/run_rt1_ablation.py <root> <gold manifest> --config default \
        --config trace=configs/rt1/trace.json --out <dir> --budget-tokens 12000 \
        --allow-fallback-counter [--only ids.txt] [--prune] [--resume]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Imported under its own module name, so run_bounded_task's spawned worker can
# unpickle task_worker (spawn copies sys.path into the child).
sys.path.insert(0, str(ROOT / "scripts"))
import run_graph_retrieval as runner


def builder_digest() -> str:
    """Fingerprint of this source tree, bound into graph cache keys."""
    return runner.source_fingerprint(ROOT)["digest"]


def _parse_configs(values: list[str]) -> dict[str, Path | None]:
    configs: dict[str, Path | None] = {}
    for value in values:
        name, _, path = value.partition("=")
        if not name or name in configs or (name != "default" and not path):
            raise SystemExit(f"bad --config {value!r}: use NAME=PATH, or 'default'")
        configs[name] = Path(path) if path else None
    if "default" not in configs:
        raise SystemExit("--config default is required: every flag is compared with it")
    return configs


def _task_args(args: argparse.Namespace, config: Path | None, graph_root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        tokenizer_manifest=args.tokenizer_manifest, budget_tokens=args.budget_tokens, offline=args.offline,
        rebuild_graphs=False, cache_graphs=True, graph_cache_root=graph_root, max_hops=args.max_hops,
        max_candidates=args.max_candidates, retrieval_config=config, task_timeout=args.task_timeout)


def _new_record(directory: Path, args: argparse.Namespace, manifest: dict[str, Any], manifest_bytes: bytes,
                config: Path | None, label: str, fallback: bool) -> dict[str, Any]:
    """A run record in the layout written by run_graph_retrieval.py."""
    retrieval_config = runner.retrieval_config_from_args(_task_args(args, config, directory))
    record = {"run_id": directory.name, "kind": "retrieval_graph", "status": "RUNNING", "started_utc": runner.utc_now(),
              "complete": False, "command_argv": sys.argv, "dataset_id": manifest["dataset_id"],
              "dataset_revision": manifest["dataset_revision"], "manifest_path": str(Path(args.manifest).resolve()),
              "task_results": [], "stdout": "", "stderr": "", "exit_code": None,
              "config": {"manifest_hash": runner.sha256(manifest_bytes), "budget_tokens": args.budget_tokens,
                         "scoring_version": runner.SCORING_VERSION, "counter_label": label, "counter_is_fallback": fallback,
                         "snippet_policy": {"max_snippet_lines": runner.DEFAULT_SNIPPET_LINES, "header": True,
                                            "overlap": "skip_if_overlaps_different_group"},
                         "arms": {arm: {"uses_fail_to_pass": uses} for arm, uses in runner.ARMS.items()},
                         "graph": {"resolver": runner.RESOLVER_PROFILE, "source_roots": ["src"]},
                         "retrieval": {"max_hops": args.max_hops, "max_candidates": args.max_candidates,
                                       "ranking_config_hash": runner_hash(retrieval_config),
                                       "override_file": str(config) if config else None,
                                       "include": "make_include(corpus): not Test and path in is_source corpus"},
                         "task_timeout_seconds": args.task_timeout, "rt1_ablation": True}}
    return record


def runner_hash(config: Any) -> str:
    from vgar.graph.retrieval import ranking_config_hash
    return ranking_config_hash(config)


def _summary_row(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "SUCCEEDED":
        return {key: result.get(key) for key in ("instance_id", "status", "error_class", "error", "duration_seconds")}
    graph = result["graph"]
    return {"instance_id": row["instance_id"], "status": "SUCCEEDED", "duration_seconds": result["duration_seconds"],
            "graph_build_seconds": graph["build_seconds"], "graph_cached": graph["cached"],
            "graph_nodes": graph["nodes"], "graph_edges": graph["edges"], "corpus_hash": result.get("corpus_hash"),
            "query_hash": result.get("query_hash"),
            "arms": {arm: {k: data["metrics"].get(k) for k in runner.KEY_METRICS} for arm, data in result["arms"].items()}}


def _prune(root: Path, row: dict[str, Any], graph_root: Path) -> None:
    """Delete the archive, source trees and graph of one finished task."""
    stem = f"{row['repo'].replace('/', '__')}-{row['base_commit']}"
    repositories = root / "data" / "repositories"
    archive = repositories / "archives" / f"{stem}.tar.gz"
    # read_repository_sources names the sidecar archive.with_suffix(".json"), i.e. "<stem>.tar.json".
    for path in (archive, archive.with_suffix(".json")):
        path.unlink(missing_ok=True)
    for tree in (repositories / "trees" / stem, repositories / "trees" / f"{stem}-scip-inputs-v1"):
        shutil.rmtree(tree, ignore_errors=True)
    shutil.rmtree(graph_root, ignore_errors=True)


def _resume_record(directory: Path, args: argparse.Namespace, config: Path | None,
                   rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Reload a run for --resume: refuse a changed config, restore summaries of written artifacts.

    Args:
        directory: Run folder of one config.
        args: Parsed command line.
        config: Override file of this config, or None for the default.
        rows: Manifest tasks keyed by instance_id.
    """
    record = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    expected = runner_hash(runner.retrieval_config_from_args(_task_args(args, config, directory)))
    if record["config"]["retrieval"]["ranking_config_hash"] != expected:
        raise SystemExit(f"{directory} was made with ranking config {record['config']['retrieval']['ranking_config_hash']}, "
                         f"not {expected}; use a new --out or the original override file")
    known = {summary["instance_id"] for summary in record["task_results"]}
    for artifact in sorted((directory / "tasks").glob("*.json")):
        if artifact.stem in known or artifact.stem not in rows:
            continue
        # The run stopped after writing the artifact but before saving the record.
        summary = _summary_row(rows[artifact.stem], json.loads(artifact.read_text(encoding="utf-8")))
        summary["artifact_hash"] = runner.sha256(artifact.read_bytes())
        record["task_results"].append(summary)
    record.update(complete=False, status="RUNNING")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--config", action="append", required=True, help="NAME=PATH of a RetrievalConfig override, or 'default'")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", type=Path, help="File with one instance_id per line")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--budget-tokens", type=int, default=12000)
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=100)
    parser.add_argument("--task-timeout", type=float, default=1800)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tokenizer-manifest", type=Path)
    group.add_argument("--allow-fallback-counter", action="store_true")
    args = parser.parse_args(argv)

    configs = _parse_configs(args.config)
    root = args.root.resolve()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    for task in manifest["tasks"]:
        runner.validate_task(task)
    runner.require_split(manifest, allowed=("dev",))
    tasks = manifest["tasks"]
    if args.only:
        wanted = {line.strip() for line in args.only.read_text(encoding="utf-8").splitlines() if line.strip()}
        tasks = [task for task in tasks if task["instance_id"] in wanted]
    if args.tokenizer_manifest:
        from vgar.graph.token_counter import LocalTokenizerCounter
        label, fallback = LocalTokenizerCounter(args.tokenizer_manifest).counter_label, False
    else:
        label, fallback = runner.FALLBACK_COUNTER_LABEL, True

    records: dict[str, dict[str, Any]] = {}
    for name, config in configs.items():
        directory = args.out / name
        if (directory / "result.json").exists():
            if not args.resume:
                raise SystemExit(f"{directory} already has a run; pass --resume to continue it")
            records[name] = _resume_record(directory, args, config, {t["instance_id"]: t for t in manifest["tasks"]})
        else:
            (directory / "tasks").mkdir(parents=True, exist_ok=True)
            records[name] = _new_record(directory, args, manifest, manifest_bytes, config, label, fallback)
        runner.write_json(directory / "result.json", records[name])

    fail_to_pass = runner.load_fail_to_pass(root, manifest)
    digest = builder_digest()
    started = time.perf_counter()
    for number, row in enumerate(tasks, 1):
        done = [(args.out / name / "tasks" / f"{row['instance_id']}.json").exists() for name in configs]
        if args.resume and all(done):
            continue
        graph_root = args.out / "graphs" / row["instance_id"]
        for name, config in configs.items():
            artifact = args.out / name / "tasks" / f"{row['instance_id']}.json"
            if artifact.exists():
                continue
            task_started = time.perf_counter()
            try:
                result = runner.run_bounded_task(root, row, fail_to_pass[row["instance_id"]],
                                                 _task_args(args, config, graph_root), digest)
            except Exception as exc:  # noqa: BLE001 - one bad task never kills the run
                result = {"instance_id": row["instance_id"], "status": "FAILED", "error_class": type(exc).__name__,
                          "error": str(exc), "duration_seconds": time.perf_counter() - task_started}
            runner.write_json(artifact, result)
            summary = _summary_row(row, result)
            summary["artifact_hash"] = runner.sha256(artifact.read_bytes())
            record = records[name]
            record["task_results"] = [t for t in record["task_results"] if t["instance_id"] != row["instance_id"]]
            record["task_results"].append(summary)
            if result.get("status") != "SUCCEEDED":
                record["stderr"] += f"{row['instance_id']}: {result.get('error_class')}: {result.get('error')}\n"
            runner.write_json(args.out / name / "result.json", record)
            print(f"[{number}/{len(tasks)}] {row['instance_id']} {name}: {result.get('status')}", flush=True)
        if args.prune:
            _prune(root, row, graph_root)

    for name, record in records.items():
        per_arm = {arm: [{"instance_id": t["instance_id"], "status": t["status"],
                          "metrics": json.loads((args.out / name / "tasks" / f"{t['instance_id']}.json").read_text(
                              encoding="utf-8")).get("arms", {}).get(arm, {}).get("metrics", {})}
                         for t in record["task_results"]] for arm in runner.ARMS}
        failed = sum(t["status"] != "SUCCEEDED" for t in record["task_results"])
        record.update(summary_by_arm={arm: runner.aggregate_metrics(items) for arm, items in per_arm.items()},
                      complete=True, ended_utc=runner.utc_now(), duration_seconds=time.perf_counter() - started,
                      status="SUCCEEDED" if not failed else "PARTIAL_FAILURE", exit_code=0 if not failed else 1)
        runner.write_json(args.out / name / "result.json", record)
    return 0 if all(record["exit_code"] == 0 for record in records.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
