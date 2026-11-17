"""Reciprocal Rank Fusion of saved R1 rankings (a secondary result, beyond the proposal) and the Holm adjustment.

RRF fuses file lists and function lists separately, from each arm's saved top-100 ``ranked`` rows, with k = 60 and
equal weights (spec 2026-11-17 §3.1). Statistics follow the 2-week plan, not the proposal.
"""
from __future__ import annotations

import random
import statistics
from typing import Any

FUNCTION_KINDS = frozenset({"function", "method"})
FUSIONS = {"rrf_graph_bm25_neighbor": ("task_trace_rt1", "bm25", "neighbor"), "rrf_bm25_neighbor": ("bm25", "neighbor"),
           "rrf_graph_embedding": ("task_trace_rt1", "embedding"), "rrf_embedding_bm25": ("embedding", "bm25")}
FUSION_PAIRS = (("rrf_graph_bm25_neighbor", "rrf_bm25_neighbor"), ("rrf_graph_embedding", "rrf_embedding_bm25"))


def ranked_lists(arm_result: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Files and functions in order of first appearance in the arm's saved ranking."""
    files: list[str] = []
    functions: list[str] = []
    for row in arm_result["ranked"]:
        if row["path"] not in files:
            files.append(row["path"])
        function_id = row.get("function_id")
        if row["kind"] in FUNCTION_KINDS and function_id and function_id not in functions:
            functions.append(function_id)
    return files, functions


def rrf(lists: list[list[str]], k: int = 60) -> list[str]:
    """Items by summed 1 / (k + rank); ties by the item string."""
    score: dict[str, float] = {}
    for items in lists:
        for rank, item in enumerate(items, 1):
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(score, key=lambda item: (-score[item], item))


def _recall(ranked: list[str], gold: set[str], k: int) -> float | None:
    return len(set(ranked[:k]) & gold) / len(gold) if gold else None


def _mrr(ranked: list[str], gold: set[str]) -> float | None:
    if not gold:
        return None
    return next((1.0 / rank for rank, item in enumerate(ranked, 1) if item in gold), 0.0)


def fused_metrics(task: dict[str, Any], members: tuple[str, ...]) -> dict[str, float | None]:
    """File R@1, R@5, function R@5, R@10 and MRR of the fused ranking; ``{}`` when a member arm is missing."""
    if any(member not in task["arms"] or "ranked" not in task["arms"][member] for member in members):
        return {}
    lists = [ranked_lists(task["arms"][member]) for member in members]
    files, functions = rrf([files for files, _ in lists]), rrf([functions for _, functions in lists])
    gold = task["gold"]
    gold_files = set(gold["gold_files"])
    # Incomplete function labels give no function metric, as in scoring.score_record.
    gold_functions = set(gold["gold_functions"]) if gold.get("function_labels_complete", True) else set()
    return {"file_recall@1": _recall(files, gold_files, 1), "file_recall@5": _recall(files, gold_files, 5),
            "function_recall@5": _recall(functions, gold_functions, 5),
            "function_recall@10": _recall(functions, gold_functions, 10), "function_mrr": _mrr(functions, gold_functions)}


def _bootstrap_means(deltas: list[float], seed: int, rounds: int) -> list[float]:
    rng = random.Random(seed)
    return sorted(statistics.fmean(rng.choice(deltas) for _ in deltas) for _ in range(rounds))


def bootstrap_p(deltas: list[float], seed: int, rounds: int = 2000) -> float:
    """Two-sided bootstrap p of a paired mean difference, at most 1.

    Uses (count + 1) / (rounds + 1) per side, so it is never 0: ``rounds`` resamples cannot show p below 1 / rounds.
    """
    means = _bootstrap_means(deltas, seed, rounds)
    below = (sum(mean <= 0 for mean in means) + 1) / (rounds + 1)
    above = (sum(mean >= 0 for mean in means) + 1) / (rounds + 1)
    return min(1.0, 2 * min(below, above))


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm–Bonferroni step-down adjusted p values, monotone and capped at 1."""
    ordered = sorted(pvalues, key=lambda name: pvalues[name])
    adjusted: dict[str, float] = {}
    running = 0.0
    for position, name in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - position) * pvalues[name]))
        adjusted[name] = running
    return adjusted
