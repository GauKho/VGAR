"""TR-1 trace link precision and recall, with the files of the gold patch as approximate labels (plan G1; [rq] section 4)."""
from __future__ import annotations

import logging
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.task_overlay import TaskOverlay
from vgar.graph.trace_links import rank_component_traces

logger = logging.getLogger(__name__)

_MAIN_CUT = 0.7
_CUTS = (0.5, 0.6, _MAIN_CUT, 0.8)


@dataclass(frozen=True)
class RankedTrace:
    confidence: float
    correct: bool


@dataclass(frozen=True)
class TraceScore:
    task_id: str
    has_traceback: bool
    components: int
    gold_files: int
    gold_components: int
    largest_component_correct: bool
    traces: tuple[RankedTrace, ...]  # in the order of rank_component_traces
    top_tied: bool
    mentioned_files: int
    mentioned_correct: int


_Selection = Callable[[TraceScore], tuple[int, int, int]]  # (kept, correct, gold) of one task


def score_task(document: dict[str, Any], overlay: TaskOverlay, gold_files: Sequence[str]) -> TraceScore:
    """Compare one task's trace links with the files of its gold patch.

    Args:
        document: The repository graph the overlay was built from.
        overlay: The task overlay.
        gold_files: Source files changed by the gold patch.
    """
    gold = set(gold_files)
    components = [node for node in document["nodes"] if node["type"] == "Component"]
    gold_components = {node["id"] for node in components if gold & set(node["properties"]["files"])}
    largest = min(components, key=lambda node: (-len(node["properties"]["files"]), node["id"]), default=None)
    ranked = rank_component_traces(edge for edge in overlay.edges if edge["type"] == "TRACES_TO")
    paths = {node["id"]: node.get("path") for node in [*document["nodes"], *overlay.nodes]}
    mentioned = {paths[edge["target_id"]] for edge in overlay.edges if edge["type"] == "MENTIONS" and paths[edge["target_id"]]}
    code_files = {path for path in mentioned if not PythonGraphBuilder._is_test_path(path)}
    return TraceScore(
        task_id=overlay.task_id,
        has_traceback=any(node["type"] == "StackTraceFrame" for node in overlay.nodes),
        components=len(components),
        gold_files=len(gold),
        gold_components=len(gold_components),
        largest_component_correct=largest is not None and largest["id"] in gold_components,
        traces=tuple(RankedTrace(edge["confidence"], edge["target_id"] in gold_components) for edge in ranked),
        top_tied=len(ranked) >= 2 and _rank_value(ranked[0]) == _rank_value(ranked[1]),
        mentioned_files=len(code_files),
        mentioned_correct=len(code_files & gold),
    )


def summarise(scores: Sequence[TraceScore], seed: int = 0, rounds: int = 2000) -> dict[str, Any]:
    """Pooled metrics for every task and for the tasks with and without a traceback.

    Args:
        scores: One score per task.
        seed: Seed of the bootstrap.
        rounds: Bootstrap rounds.
    """
    logger.debug("summarising %d tasks", len(scores))
    return {
        "all": _group(scores, seed, rounds),
        "with_traceback": _group([score for score in scores if score.has_traceback], seed, rounds),
        "without_traceback": _group([score for score in scores if not score.has_traceback], seed, rounds),
    }


def _rank_value(edge: dict[str, Any]) -> tuple[float, int]:
    return edge["confidence"], edge["properties"]["anchor_count"]


def _traces(traces: Sequence[RankedTrace], gold: int) -> tuple[int, int, int]:
    return len(traces), sum(trace.correct for trace in traces), gold


def _all_edges(score: TraceScore) -> tuple[int, int, int]:
    return _traces(score.traces, score.gold_components)


def _at_least(threshold: float) -> _Selection:
    def select(score: TraceScore) -> tuple[int, int, int]:
        return _traces([trace for trace in score.traces if trace.confidence >= threshold], score.gold_components)

    return select


def _top(count: int) -> _Selection:
    def select(score: TraceScore) -> tuple[int, int, int]:
        return _traces([trace for trace in score.traces if trace.confidence >= _MAIN_CUT][:count], score.gold_components)

    return select


def _largest(score: TraceScore) -> tuple[int, int, int]:
    return int(score.components > 0), int(score.largest_component_correct), score.gold_components


def _mentioned(score: TraceScore) -> tuple[int, int, int]:
    return score.mentioned_files, score.mentioned_correct, score.gold_files


def _view(scores: Sequence[TraceScore], selection: _Selection) -> dict[str, Any]:
    """Sum over the tasks first, then divide."""
    counts = [selection(score) for score in scores]
    kept, correct, gold = (sum(column) for column in zip(*counts)) if counts else (0, 0, 0)
    return {"kept": kept, "correct": correct, "gold": gold,
            "precision": correct / kept if kept else None, "recall": correct / gold if gold else None}


def _interval(scores: Sequence[TraceScore], selection: _Selection, seed: int, rounds: int) -> dict[str, list[float] | None]:
    """Bootstrap over tasks, because the edges of one task are not independent (same convention as retrieval/compare.py)."""
    rng = random.Random(seed)
    values: dict[str, list[float]] = {"precision": [], "recall": []}
    for _ in range(rounds if scores else 0):
        view = _view(rng.choices(scores, k=len(scores)), selection)
        for name, collected in values.items():
            if view[name] is not None:
                collected.append(view[name])
    return {name: _percentiles(sorted(collected)) for name, collected in values.items()}


def _percentiles(values: list[float]) -> list[float] | None:
    return [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]] if values else None


def _reciprocal_rank(score: TraceScore) -> float:
    return next((1 / rank for rank, trace in enumerate(score.traces, 1) if trace.correct), 0.0)


def _group(scores: Sequence[TraceScore], seed: int, rounds: int) -> dict[str, Any]:
    with_components = [score for score in scores if score.components]
    component = {
        "all": _view(scores, _all_edges),
        **{f"confidence_{cut}": _view(scores, _at_least(cut)) for cut in _CUTS},
        "top1": _view(scores, _top(1)),
        "top2": _view(scores, _top(2)),
    }
    intervals: dict[str, _Selection] = {f"confidence_{_MAIN_CUT}": _at_least(_MAIN_CUT), "top1": _top(1), "largest_component": _largest}
    return {
        "n": len(scores),
        "component": component,
        "mrr": sum(_reciprocal_rank(score) for score in scores) / len(scores) if scores else None,
        "top_ties": sum(score.top_tied for score in scores),
        "baselines": {
            "random_precision": sum(score.gold_components / score.components for score in with_components) / len(with_components) if with_components else None,
            "largest_component": _view(scores, _largest),
        },
        "file": _view(scores, _mentioned),
        "ci95": {name: _interval(scores, selection, seed, rounds) for name, selection in intervals.items()},
    }
