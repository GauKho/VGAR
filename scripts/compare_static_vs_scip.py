"""Compare static and strict SCIP on fixed development tasks; no model, repair, or test execution.

python scripts/compare_static_vs_scip.py . data/manifests/verified-<rev>-dev-25.json \
    --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json --limit 5
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from run_graph_retrieval import KEY_METRICS, run_bounded_task
from vgar.evaluation.retrieval.dataset import require_split, validate_task
from vgar.evaluation.retrieval.evidence import new_run, sha256, source_fingerprint, utc_now, write_json
from vgar.evaluation.retrieval.graph_arm import load_fail_to_pass
from vgar.evaluation.retrieval.resolver_comparison import paired_summary
from vgar.evaluation.retrieval.scoring import SCORING_VERSION
from vgar.graph.retrieval import RetrievalConfig
from vgar.graph.token_counter import LocalTokenizerCounter
from vgar.graph.scip_profile import runtime_fingerprint

METRICS = (*KEY_METRICS, "native_gold_file_in_context", "native_gold_function_in_context", "native_context_tokens",
           "native_context_items", "native_context_truncated", "retrieve_seconds")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--tokenizer-manifest", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--budget-tokens", type=int, default=8000)
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=100)
    parser.add_argument("--task-timeout", type=float, default=300)
    parser.add_argument("--scip-timeout", type=float, default=120)
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--scip-entry", type=Path,
                        default=ROOT / "artifacts/m1/w7-w8/scip-runtime/node_modules/@sourcegraph/scip-python/index.js")
    parser.add_argument("--scip-environment", type=Path, help="Optional target-environment package inventory; does not install packages")
    parser.add_argument("--scip-native-config", action="store_true")
    parser.add_argument("--scip-import-root", action="append", help="Explicit repository-relative import root")
    parser.add_argument("--scip-target-only", help="Partial indexing directory, independent of gold labels")
    parser.add_argument("--scip-python", type=Path, help="Target Python interpreter; requires matching --scip-environment")
    parser.add_argument("--instance-id", action="append", help="Choose development task IDs before seeing results")
    args = parser.parse_args()
    if args.scip_python and not args.scip_environment:
        parser.error("--scip-python requires the target interpreter's --scip-environment inventory")
    if (args.limit <= 0 or args.budget_tokens <= 0 or not math.isfinite(args.task_timeout)
            or not math.isfinite(args.scip_timeout) or args.scip_timeout <= 0 or args.task_timeout <= args.scip_timeout):
        parser.error("Positive limit/budget/deadlines required; task-timeout must exceed scip-timeout")
    root = args.root.resolve()
    args.tokenizer_manifest = args.tokenizer_manifest.resolve()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    require_split(manifest, allowed=("dev",))
    for row in manifest["tasks"]:
        validate_task(row)
    tasks = manifest["tasks"][:args.limit]
    if args.instance_id:
        wanted = set(args.instance_id)
        tasks = [r for r in manifest["tasks"] if r["instance_id"] in wanted]
        if wanted != {r["instance_id"] for r in tasks}:
            parser.error("Requested task ID not in the dev manifest")
    if not tasks:
        parser.error("Manifest contains no tasks")
    counter = LocalTokenizerCounter(args.tokenizer_manifest)
    retrieval = RetrievalConfig(max_hops=args.max_hops, max_candidates=args.max_candidates)
    f2p = load_fail_to_pass(root, dict(manifest, tasks=tasks))
    node = Path(shutil.which(args.node) or args.node).resolve()
    entry = args.scip_entry.resolve()
    shim = ROOT / "scripts/scip_windows_compat.cjs"
    # Validate local runtime before consuming task time; no npm/network activity here.
    runtime_version = subprocess.run([str(node), "--version"], capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    package = json.loads((entry.parent / "package.json").read_text(encoding="utf-8"))
    runtime = {"node_version": runtime_version, "node_binary_hash": sha256(node.read_bytes()),
               "tool": package["name"], "tool_version": package["version"], "entry_hash": sha256(entry.read_bytes()),
               "windows_shim_hash": sha256(shim.read_bytes()), "command": [str(node), "-r", str(shim), str(entry)]}
    runtime["runtime_inputs"] = runtime_fingerprint(runtime["command"])
    interpreter = Path(args.scip_python or sys.executable).absolute()
    runtime["python_executable"] = str(interpreter)
    runtime["python_binary_hash"] = sha256(interpreter.read_bytes())
    directory, record = new_run(root / "results/retrieval", "static_vs_scip_dev")
    environment = directory / "environment.json"
    if args.scip_environment:
        environment.write_bytes(args.scip_environment.read_bytes())
        environment_origin = "supplied package inventory"
    else:
        packages = [{"name": dist.metadata["Name"], "version": dist.version,
                     "files": [str(path).replace("\\", "/") for path in dist.files or []]}
                    for dist in importlib.metadata.distributions()]
        write_json(environment, packages)
        environment_origin = "M1 evaluator environment; target-project dependencies are not installed"
    config = {"manifest_hash": sha256(manifest_bytes), "selected_task_ids": [r["instance_id"] for r in tasks],
              "selection": "Explicit IDs or first N manifest tasks; fixed before results; no replacement of failed tasks",
              "counter_label": counter.counter_label, "counter_provenance": counter.provenance,
              "budget_tokens": args.budget_tokens, "scoring_version": SCORING_VERSION,
              "retrieval": {"max_hops": retrieval.max_hops, "max_candidates": retrieval.max_candidates,
                            "min_edge_confidence": retrieval.min_edge_confidence, "weights": retrieval.weights},
              "arms": {"graph": "problem_statement", "graph_f2p": "problem_statement + FAIL_TO_PASS"},
              "shared_pack": {"max_snippet_lines": 80, "header": True}, "native_pack": "Actual M1 payload; whole ranges; snippet-only tokens",
              "task_timeout_seconds": args.task_timeout, "scip_timeout_seconds": args.scip_timeout,
              "runtime": runtime, "environment_hash": sha256(environment.read_bytes()), "environment_origin": environment_origin,
              "source_policy": "Pinned archives: Python, stubs and Pyright/project configs, tests included; no dependency installation",
              "timing_policy": "One cold build and one retrieval per arm; alternating variant order; no controlled OS-cache or repeated timings",
              "memory_policy": "Python worker peak RSS only; Node/indexer excluded",
              "offline": True, "strict_scip": True, "cache_policy": "New run directory; resolver/runtime/implementation/source-bound keys"}
    config["scip_profile"] = {"configure_imports": not args.scip_native_config,
                              "import_roots": args.scip_import_root or ["src", "lib"], "target_only": args.scip_target_only}
    implementation = source_fingerprint(ROOT)
    binding = sha256(json.dumps(config, sort_keys=True))
    record.update(config=config, comparison_binding=binding, source=implementation, task_results=[])
    write_json(directory / "result.json", record)
    print(f"run: {directory}", flush=True)
    pairs = []
    started = time.perf_counter()
    for number, row in enumerate(tasks):
        pair = {"instance_id": row["instance_id"]}
        order = ("static", "scip") if number % 2 == 0 else ("scip", "static")
        pair["execution_order"] = list(order)
        for variant in order:
            output = directory / "tasks" / row["instance_id"] / variant
            output.mkdir(parents=True)
            profile = {"resolver": variant, "source_roots": ["src"], "strict": variant == "scip"}
            if variant == "scip":
                profile.update(runtime=runtime, environment_hash=config["environment_hash"], timeout_seconds=args.scip_timeout)
                profile.update(config["scip_profile"])
            worker_args = SimpleNamespace(tokenizer_manifest=args.tokenizer_manifest, offline=True,
                rebuild_graphs=False, cache_graphs=True, graph_cache_root=directory / "graphs" / variant,
                max_hops=args.max_hops, max_candidates=args.max_candidates, budget_tokens=args.budget_tokens,
                task_timeout=args.task_timeout, resolver=variant, resolver_profile=profile,
                scip_command=tuple(runtime["command"]), scip_output=output / "index",
                scip_timeout=args.scip_timeout, scip_environment=environment,
                scip_native_config=args.scip_native_config, scip_import_roots=config["scip_profile"]["import_roots"],
                scip_target_only=args.scip_target_only,
                scip_python=interpreter,
                include_scip_inputs=True,
                debug_log=output / "debug.jsonl", persist_context=True, comparison_binding=binding)
            print(f"[{number + 1}/{len(tasks)}] {row['instance_id']} {variant}: starting", flush=True)
            try:
                result = run_bounded_task(root, row, f2p[row["instance_id"]], worker_args, implementation["digest"])
            except Exception as error:
                result = {"instance_id": row["instance_id"], "status": "FAILED", "error_class": type(error).__name__, "error": str(error)}
            write_json(output / "result.json", result)
            pair[variant] = result
            print(f"[{number + 1}/{len(tasks)}] {row['instance_id']} {variant}: {result['status']}"
                  + (f" ({result['duration_seconds']:.1f}s)" if "duration_seconds" in result else ""), flush=True)
        pairs.append(pair)
        write_json(directory / "tasks" / row["instance_id"] / "pair.json", pair)
        record["task_results"].append({"instance_id": row["instance_id"], "execution_order": list(order),
            "static_status": pair["static"]["status"], "scip_status": pair["scip"]["status"],
            "pair_artifact": f"tasks/{row['instance_id']}/pair.json",
            "pair_hash": sha256((directory / "tasks" / row["instance_id"] / "pair.json").read_bytes())})
        record["summary"] = paired_summary(pairs, METRICS)
        write_json(directory / "result.json", record)
    failed = len(record["summary"]["failed_pairs"])
    record.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                  status="SUCCEEDED" if not failed else "PARTIAL_FAILURE", exit_code=int(bool(failed)))
    write_json(directory / "result.json", record)
    print(json.dumps(record["summary"], ensure_ascii=False, indent=2), flush=True)
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
