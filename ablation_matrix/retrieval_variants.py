"""Retrieval with and without the task trace (G_task), for the offline ablation.

``task_trace`` (R-A2) is what the repository does today: the issue is grounded
into a per-task overlay (G_task: frames, paths, error messages, TRACES_TO) and
its anchors start the graph walk. ``no_task_trace`` (R-A1) builds no overlay:
anchors come from matching issue words against symbol names, the way an agent
would call ``search_symbols``. Both use the same RetrievalConfig, so the only
difference is G_task. This module only calls vgar; it does not change it.
"""
from __future__ import annotations

import gc
import math
import re
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from vgar.graph.grounding import issue_symbol_text
from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
from vgar.graph.task_overlay import TaskOverlayBuilder

ARMS = ("no_task_trace", "task_trace")
# arm -> (anchor source, RetrievalConfig flags on top of the frozen default, AST-only graph)
GRAPH_ARM_SPECS: dict[str, tuple[str, dict[str, Any], bool]] = {
    "no_task_trace": ("symbols", {}, False),                                    # R-A1: repo symbol graph only
    "task_trace": ("overlay", {}, False),                                       # R-A2: + task trace (G_task)
    "ast_no_task_trace": ("symbols", {}, True),                                 # R-AST: AST-only graph
    "arch_no_task_trace": ("symbols", {"use_component_dependents": True}, False),   # R-A1+arch
    "a3": ("overlay", {"use_component_dependents": True, "use_trace_component": True}, False),  # R-A3
    "task_trace_rt1": ("overlay", {"may_call_factor": 0.5}, False),             # R-A2 + RT1_CONFIG
}
GRAPH_ARMS = tuple(GRAPH_ARM_SPECS)
AST_EDGES = frozenset({"CONTAINS", "HAS_METHOD", "HAS_CALLSITE"})
SYMBOL_TYPES = frozenset({"Class", "Function", "Method", "Test"})
# Without an overlay GraphContextRetriever gives every anchor confidence 1.0;
# all R-A1 anchors are equal, so only issue similarity orders them.
ANCHOR_CONFIDENCE = 1.0
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STOP = frozenset(["a", "an", "and", "are", "as", "at", "be", "by", "can", "describe", "does", "failing", "for", "from", "how", "in", "is", "it", "of", "on", "or", "problem", "python", "related", "request", "should", "that", "the", "this", "to", "use", "using", "was", "when", "with", "would", "not", "but", "if", "then", "there", "line", "file", "error", "none", "true", "false", "self"])


def issue_words(issue_text: str) -> list[str]:
    """Lower-cased identifier words of the issue, minus stop words and words under 3 letters.

    Args:
        issue_text: Problem statement.
    """
    seen: dict[str, None] = {}
    for word in _IDENTIFIER.findall(issue_symbol_text(issue_text)):
        lowered = word.lower()
        if len(lowered) >= 3 and lowered not in _STOP:
            seen.setdefault(lowered, None)
    return list(seen)


def symbol_search_anchors(document: Mapping[str, Any], issue_text: str, *, limit: int,
                          include: Callable[[Mapping[str, Any]], bool] | None = None) -> list[str]:
    """Anchor ids for R-A1: symbols whose name equals, then contains, an issue word.

    Args:
        document: Graph document of the repository.
        issue_text: The issue (problem statement); only its words are used, no G_task.
        limit: Maximum number of anchors.
        include: Optional filter; symbols it rejects are never anchors.
    """
    symbols = [node for node in document["nodes"]
               if node["type"] in SYMBOL_TYPES and node.get("path") and node.get("range")
               and (include is None or include(node))]
    words = issue_words(issue_text)
    matches: dict[str, tuple[int, float, str]] = {}
    for word in words:
        exact = [node for node in symbols if node["name"].lower() == word]
        partial = [node for node in symbols if len(word) >= 4 and word in node["name"].lower()
                   and node["name"].lower() != word]
        frequency = len(exact) + len(partial)
        if not frequency:
            continue
        idf = math.log(1 + len(symbols) / frequency)
        for kind, group in ((0, exact), (1, partial)):
            for node in group:
                key = (kind, -idf, node["id"])
                if node["id"] not in matches or key < matches[node["id"]]:
                    matches[node["id"]] = key
    return [node_id for node_id, _ in sorted(matches.items(), key=lambda item: item[1])][:limit]


def _arm(retriever: GraphContextRetriever, anchors: list[dict[str, Any]], budget_tokens: int, issue_text: str,
         overlay: Any, include: Callable[[Mapping[str, Any]], bool] | None) -> dict[str, Any]:
    started = time.perf_counter()
    result = retriever.retrieve([anchor["node_id"] for anchor in anchors], budget_tokens, issue_text=issue_text,
                                overlay=overlay, include=include)
    return {"candidates": result.candidates, "anchors": anchors, "seconds": time.perf_counter() - started,
            "context": result.context.model_dump(mode="json"),
            "diagnostics": {"overlay_id": result.overlay_id, "retrieval_config": result.config,
                            "unavailable_features": result.unavailable_features,
                            "traversal_limited": result.traversal_limited}}


def _describe(retriever: GraphContextRetriever, node_id: str, score: float) -> dict[str, Any]:
    node = retriever.nodes[node_id]
    return {"node_id": node_id, "score": score, "symbol": node["qualified_name"], "type": node["type"],
            "path": node["path"]}


def ast_only(document: dict[str, Any]) -> dict[str, Any]:
    """The graph with only syntax-tree containment edges ([P] §13.1 "AST-only graph").

    CallSite nodes go too: schema S requires a CallSite's ``candidate_count`` to
    match its outgoing CALLS edges, and the retriever never walks CallSites.

    Args:
        document: Full graph document.
    """
    dropped = {node["id"] for node in document["nodes"] if node["type"] == "CallSite"}
    return {**document, "nodes": [node for node in document["nodes"] if node["id"] not in dropped],
            "edges": [edge for edge in document["edges"] if edge["type"] in AST_EDGES
                      and edge["source_id"] not in dropped and edge["target_id"] not in dropped]}


def variant_outputs(document: dict[str, Any], tree: Path, issue_text: str, *,
                    include: Callable[[Mapping[str, Any]], bool] | None, count_tokens: Callable[[str], int],
                    counter_label: str, budget_tokens: int = 12000,
                    arms: tuple[str, ...] = ARMS) -> dict[str, dict[str, Any]]:
    """Run the named graph arms on one graph; output follows ``evaluate_graph_task``'s ``arm_outputs``.

    Args:
        document: Graph document built at the task's base commit.
        tree: Source tree the graph was built from.
        issue_text: Problem statement of the task.
        include: Evaluation filter (drop tests and files outside the corpus).
        count_tokens: Token counter for packing.
        counter_label: Name of that counter.
        budget_tokens: Context budget.
        arms: Names from ``GRAPH_ARM_SPECS``.
    """
    overlay = TaskOverlayBuilder(document).build("ablation:task_trace", issue_text, None)
    # Arms sharing a config share one retriever. Each retriever deep-copies the
    # graph, so only one lives at a time (sympy-size graphs ran out of RAM when
    # all five were kept).
    groups: dict[tuple[str, bool], list[str]] = {}
    for arm in arms:
        _, flags, ast = GRAPH_ARM_SPECS[arm]
        groups.setdefault((repr(sorted(flags.items())), ast), []).append(arm)
    outputs: dict[str, dict[str, Any]] = {}
    for (_, ast), names in groups.items():
        flags = GRAPH_ARM_SPECS[names[0]][1]
        graph = ast_only(document) if ast else document
        retriever = GraphContextRetriever(graph, tree, count_tokens=count_tokens, counter_label=counter_label,
                                          config=RetrievalConfig(**flags))
        del graph
        for arm in names:
            if GRAPH_ARM_SPECS[arm][0] == "overlay":
                anchors = [_describe(retriever, anchor.node_id, anchor.score) for anchor in overlay.grounding.anchors]
                outputs[arm] = _arm(retriever, anchors, budget_tokens, issue_text, overlay, include)
            else:
                anchors = [_describe(retriever, node_id, ANCHOR_CONFIDENCE) for node_id in symbol_search_anchors(
                    document, issue_text, limit=retriever._anchor_seed_limit(), include=include)]
                outputs[arm] = _arm(retriever, anchors, budget_tokens, issue_text, None, include)
        del retriever
        gc.collect()
    return {arm: outputs[arm] for arm in arms}
