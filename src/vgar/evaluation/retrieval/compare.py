"""Paired Graph vs BM25 comparison from two finished runs. Stdlib only; reads artifacts, never re-runs retrieval.

Fairness rules enforced (comparison refuses to run otherwise): same dataset revision, budget, counter, scoring version,
snippet policy; per task same query_hash and corpus_hash; neither run uses the bytes/4 fallback counter.
The primary BM25 column uses its full saved ranking. An optional cap produces
rank-only sensitivity results, never a new packed-context measurement.
"""
from __future__ import annotations

import json
import random
import re
import statistics
import time
from pathlib import Path
from typing import Any

from .evidence import new_run, sha256, source_fingerprint, write_json
from .metrics import aggregate_metrics, evaluate_ranking

DELTA_METRICS = ("file_recall@3", "file_recall@5", "file_recall@10", "function_recall@3", "function_recall@5",
                 "function_recall@10", "file_mrr", "function_mrr", "packed_gold_file_in_context",
                 "packed_gold_function_in_context", "context_tokens")
SAME_CONFIG = ("budget_tokens", "counter_label", "scoring_version", "snippet_policy")
GRAPH_ARMS = ("graph", "graph_f2p")
RANK_METRICS = ("file_recall@3", "file_recall@5", "file_recall@10", "function_recall@3",
                "function_recall@5", "function_recall@10", "file_mrr", "function_mrr",
                "file_reach", "function_reach", "rank_items")


def _load(path: Path) -> dict[str, Any]:
    record = json.loads((path / "result.json").read_text(encoding="utf-8"))
    if not record.get("complete"):
        raise ValueError(f"Run {path} is not complete")
    return record


def _validate_graph_run(record: dict[str, Any], run_label: str) -> None:
    """Graph runs produced by run_graph_retrieval.py carry per-task arm data."""
    if record.get("kind") != "retrieval_graph":
        raise ValueError(f"{run_label}: expected a retrieval_graph run, not a BM25 run")
    for task in record.get("task_results", []):
        if task.get("status") != "SUCCEEDED":
            continue
        arms = task.get("arms")
        if not isinstance(arms, dict) or set(arms) != set(GRAPH_ARMS):
            raise ValueError(f"{run_label}: {task.get('instance_id')}: arms must contain {GRAPH_ARMS}")
        if not all(isinstance(data, dict) for data in arms.values()):
            raise ValueError(f"{run_label}: malformed per-task arms")


def _task(run: Path, summary: dict[str, Any]) -> dict[str, Any]:
    try:
        data = (run / "tasks" / f"{summary['instance_id']}.json").read_bytes()
    except OSError as exc:
        raise ValueError(f"Missing task artifact: {summary['instance_id']}") from exc
    if not summary.get("artifact_hash") or summary["artifact_hash"] != sha256(data):
        raise ValueError(f"Artifact hash mismatch: {summary['instance_id']}")
    task = json.loads(data)
    if not isinstance(task, dict) or task.get("instance_id") != summary["instance_id"] or task.get("status") != summary["status"]:
        raise ValueError(f"Artifact instance_id/status mismatch: {summary['instance_id']}")
    return task


def _index_tasks(record: dict, label: str) -> dict[str, dict]:
    tasks = record.get("task_results")
    if not isinstance(tasks, list):
        raise ValueError(f"{label}: missing task_results")
    out = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("instance_id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", task["instance_id"]):
            raise ValueError(f"{label}: invalid instance_id")
        if task["instance_id"] in out:
            raise ValueError(f"{label}: Duplicate instance_id: {task['instance_id']}")
        if task.get("status") not in {"SUCCEEDED", "FAILED", "ERROR", "NOT_RUN"}:
            raise ValueError(f"{label}: invalid task status")
        out[task["instance_id"]] = task
    return out


def _coverage(tasks: dict[str, dict]) -> dict[str, Any]:
    counts = {status: sum(t["status"] == status for t in tasks.values())
              for status in ("SUCCEEDED", "FAILED", "ERROR", "NOT_RUN")}
    return {"attempted_tasks": len(tasks), "completed_tasks": counts["SUCCEEDED"],
            "failed_tasks": counts["FAILED"] + counts["ERROR"], "not_run_tasks": counts["NOT_RUN"],
            "status_counts": counts}


def cap_bm25(task: dict[str, Any], cap: int) -> dict[str, Any]:
    """Re-score ONLY the rank-mode metrics of a BM25 task on its top-``cap`` chunks (packed metrics are unchanged)."""
    chunks = {c["chunk_id"]: c for c in task["candidate_map"]}
    rows = []
    for chunk_id in task["rank_order"][:cap]:
        chunk = chunks[chunk_id]
        row = {"path": chunk["path"], "kind": chunk["kind"]}
        if chunk["kind"] != "module":
            row["parent_id"] = chunk["parent_id"]
        rows.append(row)
    gold = task["gold"]
    gold_files = set(gold["gold_files"])
    gold_funcs = set(gold["gold_functions"]) if gold.get("function_labels_complete", True) else set()
    metrics = dict(task["metrics"])
    metrics.update(evaluate_ranking(rows, gold))
    metrics["file_reach"] = len(gold_files & {r["path"] for r in rows}) / len(gold_files) if gold_files else None
    metrics["function_reach"] = len(gold_funcs & {r["parent_id"] for r in rows if "parent_id" in r}) / len(gold_funcs) if gold_funcs else None
    metrics["rank_items"] = len(rows)
    return metrics


def _bootstrap(values: list[float], seed: int, rounds: int = 2000) -> list[float]:
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(rounds))
    return [means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]]


def paired_stats(base: dict[str, dict], other: dict[str, dict], seed: int = 0) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in DELTA_METRICS:
        deltas = [other[i][name] - base[i][name] for i in base
                  if base[i].get(name) is not None and other[i].get(name) is not None]
        if not deltas:
            out[name] = {"n": 0}
            continue
        out[name] = {"n": len(deltas), "mean_delta": statistics.fmean(deltas), "ci95": _bootstrap(deltas, seed),
                     "wins": sum(d > 1e-9 for d in deltas), "ties": sum(abs(d) <= 1e-9 for d in deltas),
                     "losses": sum(d < -1e-9 for d in deltas)}
    return out


def compare_runs(bm25_run, graph_run, results_root, cap: int | None = None, seed: int = 0, allow_fallback: bool = False):
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 1):
        raise ValueError("cap must be a positive integer or None")
    bm25_run, graph_run = Path(bm25_run), Path(graph_run)
    bm, gr = _load(bm25_run), _load(graph_run)
    if bm.get("kind") != "retrieval":
        raise ValueError("bm25_run: expected a retrieval run")
    for key in ("dataset_id", "dataset_revision"):
        if not bm.get(key) or bm[key] != gr.get(key):
            raise ValueError(f"Different or missing {key}")
    for key in SAME_CONFIG:
        if key not in bm.get("config", {}) or key not in gr.get("config", {}) or bm["config"][key] != gr["config"][key]:
            raise ValueError(f"Config mismatch or missing field: {key}")
    if (bm["config"].get("counter_is_fallback") or gr["config"].get("counter_is_fallback")) and not allow_fallback:
        raise ValueError("A run used the bytes/4 fallback counter; not valid for the official comparison")
    bm_summaries = _index_tasks(bm, "bm25_run")
    graph_summaries = _index_tasks(gr, "graph_run")
    if set(bm_summaries) != set(graph_summaries):
        raise ValueError("Different task populations; compare runs for the same task subset")
    _validate_graph_run(gr, "graph_run")
    per_task: dict[str, dict[str, dict]] = {a: {} for a in ("bm25", *GRAPH_ARMS)}
    capped_metrics: dict[str, dict] = {}
    info: dict[str, dict] = {}
    skipped = []
    for summary in bm["task_results"]:
        iid = summary["instance_id"]
        other = graph_summaries.get(iid)
        if summary["status"] != "SUCCEEDED" or other is None or other["status"] != "SUCCEEDED":
            skipped.append({"instance_id": iid, "reason": "not_succeeded_in_both_runs",
                            "bm25_status": summary["status"], "graph_status": other["status"] if other else "MISSING"})
            continue
        b, g = _task(bm25_run, summary), _task(graph_run, other)
        for key in ("query_hash", "corpus_hash", "base_commit", "repository", "patch_hash", "gold"):
            if key not in b or key not in g or b[key] != g[key]:
                raise ValueError(f"{iid}: {key} differs or is missing between runs")
        if not isinstance(b.get("metrics"), dict) or not isinstance(g.get("arms"), dict) or set(g["arms"]) != set(GRAPH_ARMS):
            raise ValueError(f"{iid}: missing metrics or graph arms in task artifact")
        per_task["bm25"][iid] = b["metrics"]
        if cap is not None:
            rescored = cap_bm25(b, cap)
            capped_metrics[iid] = {key: rescored[key] for key in RANK_METRICS if key in rescored}
        for arm in GRAPH_ARMS:
            if not isinstance(g["arms"][arm], dict) or not isinstance(g["arms"][arm].get("metrics"), dict):
                raise ValueError(f"{iid}: {arm} missing metrics")
            per_task[arm][iid] = g["arms"][arm]["metrics"]
        info[iid] = {"repository": b["repository"], "graph_build_seconds": other["graph_build_seconds"],
                     "anchors": {arm: [a["symbol"] for a in g["arms"][arm]["anchors"]][:8] for arm in GRAPH_ARMS}}
    ids = sorted(per_task["bm25"])
    summaries = {arm: aggregate_metrics([{"status": "SUCCEEDED", "metrics": per_task[arm][i]} for i in ids])
                 for arm in per_task}
    paired = {arm: paired_stats(per_task["bm25"], per_task[arm], seed) for arm in GRAPH_ARMS}
    by_repo: dict[str, dict] = {}
    for iid in ids:
        by_repo.setdefault(info[iid]["repository"], []).append(iid)
    repo_rows = {repo: {"n": len(members), **{f"{arm}.{m}": statistics.fmean(per_task[arm][i][m] for i in members
                                              if per_task[arm][i].get(m) is not None) if any(per_task[arm][i].get(m) is not None for i in members) else None
                                              for arm in ("bm25", *GRAPH_ARMS) for m in ("file_recall@5", "function_recall@5")}}
                 for repo, members in sorted(by_repo.items())}
    diagnostics = {arm: {"no_anchor_tasks": sum(int(per_task[arm][i]["no_anchors"]) for i in ids),
                         "mean_anchor_count": statistics.fmean(per_task[arm][i]["anchor_count"] for i in ids) if ids else None,
                         "unmapped_total": sum(per_task[arm][i]["unmapped_count"] for i in ids),
                         "mean_unmapped_per_task": statistics.fmean(per_task[arm][i]["unmapped_count"] for i in ids) if ids else None,
                         "mean_candidates": statistics.fmean(per_task[arm][i]["candidates_in"] for i in ids) if ids else None}
                   for arm in GRAPH_ARMS}
    # manual inspection: where the graph arm moved the most (file + function Recall@5), both directions
    inspection = {}
    for arm in GRAPH_ARMS:
        scored = sorted(((sum((per_task[arm][i][m] or 0) - (per_task["bm25"][i][m] or 0) for m in ("file_recall@5", "function_recall@5")), i)
                         for i in ids), key=lambda x: (x[0], x[1]))
        inspection[arm] = {"graph_loses": [{"instance_id": i, "delta": d, "anchors": info[i]["anchors"][arm]} for d, i in scored[:3] if d < 0],
                           "graph_wins": [{"instance_id": i, "delta": d, "anchors": info[i]["anchors"][arm]} for d, i in scored[::-1][:3] if d > 0]}
    directory, report = new_run(Path(results_root), "graph_vs_bm25")
    status = "NO_PAIRED_TASKS" if not ids else ("COMPARED_PARTIAL" if skipped else "COMPARED")
    sensitivity = None if cap is None else {
        "cap": cap, "packed_context_recomputed": False,
        "summary": aggregate_metrics([{"status": "SUCCEEDED", "metrics": capped_metrics[i]} for i in ids]),
        "paired": {arm: paired_stats(capped_metrics, per_task[arm], seed) for arm in GRAPH_ARMS},
    }
    report.update(source=source_fingerprint(Path(__file__).resolve().parents[4]),
                  bm25_run=str(bm25_run.resolve()), graph_run=str(graph_run.resolve()),
                  bm25_run_hash=sha256((bm25_run / "result.json").read_bytes()), graph_run_hash=sha256((graph_run / "result.json").read_bytes()),
                  status=status, paired_tasks=len(ids), eligible_bm25_tasks=_coverage(bm_summaries)["completed_tasks"],
                  coverage={"bm25": _coverage(bm_summaries), "graph": _coverage(graph_summaries)},
                  comparison_semantics="bm25_full_rank_primary_v1", rank_sensitivity=sensitivity,
                  graph_max_candidates=gr["config"].get("retrieval", {}).get("max_candidates"),
                  arm_information={"graph": "issue-only", "graph_f2p": "oracle-assisted FAIL_TO_PASS benchmark metadata"},
                  scoring_version=bm["config"]["scoring_version"], bm25_cap=cap, bootstrap_seed=seed, skipped=skipped,
                  summaries=summaries, paired=paired, by_repo=repo_rows, graph_diagnostics=diagnostics, inspection=inspection,
                  per_task={arm: {i: {m: per_task[arm][i].get(m) for m in ("file_recall@5", "function_recall@5", "function_mrr",
                                                                              "packed_gold_function_in_context")} for i in ids}
                            for arm in per_task},
                  complete=True, exit_code=0 if status == "COMPARED" else 1, stdout="", stderr="")
    write_json(directory / "result.json", report)
    return directory, report
