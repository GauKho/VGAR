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
        [--history none|raw|graphdiff --git-root <clones> [--history-commits 50]]
    python ablation_matrix/run_r1_ablation.py --compare-history <none dir> <raw dir> <graphdiff dir>

``--history raw|graphdiff`` (GraphDiff downstream, proposal line 760) runs only the ``task_trace`` arm with
``recent_change_frequency`` fed from the first-parent window ending at the task's base commit, read from a
full-history clone ``<git-root>/<owner>__<name>``: ``raw`` counts commits per path, ``graphdiff`` counts
commits with at least one validated graph edit per node id. A task without that history fails with
``HistoryUnavailable``.
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


class HistoryUnavailable(RuntimeError):
    """The task's clone or its base commit history is missing."""


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


def arm_flags(args: argparse.Namespace) -> dict[str, dict[str, bool]]:
    """Extra retrieval flags per arm: --use-variable-references applies to task_trace only (spec 2026-11-15 §5)."""
    return {"task_trace": {"use_variable_references": True}} if args.use_variable_references else {}


def arms_for(args: argparse.Namespace) -> tuple[tuple[str, ...], bool]:
    """Graph arms to run and whether the text baselines run."""
    return (GRAPH_ARMS, True) if args.history == "none" else (("task_trace",), False)


def graphdiff_counts(edits: Any) -> dict[str, int]:
    """Per node id, the number of commits with at least one validated graph edit on it."""
    commits: dict[str, set[str]] = {}
    for edit in edits:
        if edit.validated:
            commits.setdefault(edit.node_id, set()).add(edit.commit_id)
    return {node_id: len(ids) for node_id, ids in sorted(commits.items())}


def history_counts(mode: str, row: dict[str, Any], document: dict[str, Any], *, git_root: Path,
                   max_commits: int) -> tuple[dict[str, int], str]:
    """Change counts and their label for one task; never reads commits after ``base_commit``.

    Args:
        mode: ``raw`` or ``graphdiff``.
        row: Gold manifest task.
        document: Graph built at the task's base commit.
        git_root: Folder of full-history clones named ``<owner>__<name>``.
        max_commits: Window size.

    Raises:
        HistoryUnavailable: The clone or the base commit's history is missing.
    """
    from vgar.graph.history import read_commit_history

    clone = git_root / row["repo"].replace("/", "__")
    if not clone.is_dir():
        raise HistoryUnavailable(f"clone missing: {clone}")
    try:
        window = read_commit_history(clone, revision=row["base_commit"], max_commits=max_commits)
        if mode == "raw":
            return window.change_counts, window.history_label
        from vgar.graph.graphdiff import run_graphdiff
        from vgar.graph.refactorings import RefactoringMinerConfig

        result = run_graphdiff(clone, document, max_commits=max_commits, source_roots=("src",),
                               rm_config=RefactoringMinerConfig.from_env(), repository_name=runner.key_of(row))
    except (ValueError, TypeError) as error:
        raise HistoryUnavailable(f"history unavailable: {error}") from error
    return graphdiff_counts(result.edits), f"graphdiff:v1:{window.history_label}"


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
    from vgar.graph.layer_config import layers_from_args

    document, graph_meta = runner.load_or_build_graph(root, row, tree, rebuild=False, builder_hash=builder_hash,
                                                      cache=False, layers=layers_from_args(args))
    corpus = CorpusIndex(sources)
    graph_arms, run_text = arms_for(args)
    counts, history_label, history = None, None, None
    if args.history != "none":
        counts, history_label = history_counts(args.history, row, document, git_root=args.git_root,
                                               max_commits=args.history_commits)
        history = {"mode": args.history, "label": history_label, "keys": len(counts)}
    # Every ranking is computed before the gold patch is parsed.
    outputs = variant_outputs(document, tree, row["problem_statement"], include=make_include(corpus),
                              count_tokens=counter, counter_label=label, budget_tokens=args.budget_tokens,
                              arms=graph_arms, change_counts=counts, history_label=history_label,
                              arm_flags=arm_flags(args))
    text_records = {"bm25": bm25_rank(row["instance_id"], row["problem_statement"], sources),
                    "grep": grep_rank(row["instance_id"], row["problem_statement"], sources),
                    "neighbor": neighbor_rank(row["instance_id"], row["problem_statement"], sources)} if run_text else {}
    contexts = {arm: outputs[arm].pop("context") for arm in graph_arms}
    nodes = {node["id"]: node for node in document["nodes"]}
    result = evaluate_graph_task(dict(row, patch=patch), sources, corpus, nodes, outputs,
                                 budget_tokens=args.budget_tokens, counter=counter, counter_label=label)
    for arm in graph_arms:
        metrics = result["arms"][arm]["metrics"]
        metrics.update(native_context_metrics(contexts[arm], result["gold"], corpus))
        metrics.update(component_metrics(document, [row_["path"] for row_ in result["arms"][arm]["ranked"]],
                                         gold_files=result["gold"]["gold_files"]))
    for arm, record in text_records.items():
        result["arms"][arm] = _text_arm(record, result["gold"], document, args.budget_tokens, counter, label)
    result.update(graph={k: graph_meta[k] for k in ("build_seconds", "nodes", "edges", "graph_version")},
                  duration_seconds=time.perf_counter() - started)
    if history is not None:
        result["history"] = history
    provenance = layers_and_flags(args, document)
    if provenance is not None:
        result["layers_and_flags"] = provenance
    return result


def layers_and_flags(args: argparse.Namespace, document: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Arm flags and optional layers of the run for the task result; ``None`` when none is on (results stay as before).

    With the built ``document`` and a layer on, ``layer_status`` says per layer whether it was ready, failed or off.
    """
    from vgar.graph.layer_config import layer_summary, layers_from_args

    flags = arm_flags(args)
    configs = layers_from_args(args)
    layers = sorted(k for k, v in configs.builder_kwargs().items() if v)
    if not flags and not layers:
        return None
    provenance = {"arm_flags": flags, "layers": layers}
    if document is not None and layers:
        provenance["layer_status"] = layer_summary(document, configs)
    return provenance


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


HISTORY_METRICS = ("file_recall@1", "file_recall@3", "file_recall@5", "file_recall@10", "function_recall@1",
                   "function_recall@3", "function_recall@5", "function_recall@10", "file_mrr", "function_mrr")


def compare_history_runs(none_dir: Path, raw_dir: Path, graphdiff_dir: Path, seed: int = 0) -> dict[str, Any]:
    """Means of the ``task_trace`` arm per history mode and paired deltas against ``none``.

    Args:
        none_dir: Run without history.
        raw_dir: Run with ``--history raw``.
        graphdiff_dir: Run with ``--history graphdiff``.
        seed: Bootstrap seed.
    """
    def values(folder: Path) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for path in sorted((folder / "tasks").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") == "SUCCEEDED" and "task_trace" in data.get("arms", {}):
                out[data["instance_id"]] = data["arms"]["task_trace"]["metrics"]
        return out

    runs = {"none": values(none_dir), "raw": values(raw_dir), "graphdiff": values(graphdiff_dir)}
    means = {mode: {name: statistics.fmean(v) if (v := [m[name] for m in run.values() if m.get(name) is not None])
                    else None for name in HISTORY_METRICS} for mode, run in runs.items()}
    pairs: dict[str, dict[str, Any]] = {}
    for mode in ("raw", "graphdiff"):
        rows = {}
        for name in HISTORY_METRICS:
            shared = sorted(i for i in runs[mode].keys() & runs["none"].keys()
                            if runs[mode][i].get(name) is not None and runs["none"][i].get(name) is not None)
            deltas = [runs[mode][i][name] - runs["none"][i][name] for i in shared]
            if deltas:
                rows[name] = {"n": len(deltas), "mean_delta": statistics.fmean(deltas), "ci95": _bootstrap(deltas, seed),
                              "wins": sum(d > 1e-9 for d in deltas), "losses": sum(d < -1e-9 for d in deltas)}
        pairs[f"{mode} - none"] = rows
    return {"tasks": {mode: len(run) for mode, run in runs.items()}, "means": means, "pairs": pairs}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Command line of the R1 run, or of ``--compare-history``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, nargs="?")
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--only", type=Path)
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--budget-tokens", type=int, default=12000)
    parser.add_argument("--allow-fallback-counter", action="store_true")
    parser.add_argument("--history", choices=("none", "raw", "graphdiff"), default="none")
    parser.add_argument("--git-root", type=Path)
    parser.add_argument("--history-commits", type=int, default=50)
    parser.add_argument("--compare-history", type=Path, nargs=3, metavar=("NONE", "RAW", "GRAPHDIFF"))
    parser.add_argument("--use-variable-references", action="store_true",
                        help="context flag on the task_trace arm (needs --tsg-*)")
    from vgar.graph.layer_config import add_layer_options

    add_layer_options(parser)
    args = parser.parse_args(argv)
    if args.compare_history:
        return args
    if args.root is None or args.manifest is None or args.out is None:
        parser.error("root, manifest and --out are required")
    if not args.allow_fallback_counter:
        parser.error("--allow-fallback-counter is required")
    if args.history != "none" and args.git_root is None:
        parser.error("--history raw|graphdiff needs --git-root")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.compare_history:
        print(json.dumps(compare_history_runs(*args.compare_history), indent=2))
        return 0
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
                   counter_label=FALLBACK_COUNTER_LABEL, builder_hash=builder_hash, history=args.history,
                   history_commits=args.history_commits if args.history != "none" else None)
    runner.write_json(args.out / "summary.json", summary)
    print(json.dumps({"succeeded": summary["succeeded"], "failed": summary["failed"]}))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
