"""Bounded semantic retrieval and source-verified context packing for M1."""
from __future__ import annotations

import copy
import hashlib
import heapq
import math
import re
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from vgar.contracts.context import ContextItem, ContextPayload, SourceRange
from vgar.contracts.error import GraphError, InvalidLimitError, InvalidQueryError, NodeNotFoundError
from vgar.contracts.schema import validate_graph_document
from vgar.graph.builder import IGNORED_DIRECTORY_NAMES
from vgar.graph.task_overlay import TaskOverlay


_RETRIEVABLE = {"File", "Module", "Class", "Function", "Method", "Test"}
_WORDS = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_WEIGHTS = {"task_similarity": 0.2, "graph_distance": 0.3, "edge_confidence": 0.2,
            "failing_test_proximity": 0.2, "public_api_risk": 0.1, "recent_change_frequency": 0.1}


@dataclass(frozen=True)
class RetrievalConfig:
    max_hops: int = 2
    max_candidates: int = 100
    min_edge_confidence: float = 0.6
    weights: dict[str, float] = field(default_factory=lambda: dict(_WEIGHTS))

    def __post_init__(self) -> None:
        for name, value, minimum in (("max_hops", self.max_hops, 0),
                                     ("max_candidates", self.max_candidates, 1)):
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise InvalidLimitError(f"{name} must be an integer >= {minimum}")
        if not _number(self.min_edge_confidence) or not 0 <= self.min_edge_confidence <= 1:
            raise InvalidQueryError("min_edge_confidence must be within [0, 1]")
        if set(self.weights) != set(_WEIGHTS) or any(
            not _number(value) or value < 0 for value in self.weights.values()
        ) or sum(self.weights.values()) <= 0:
            raise InvalidQueryError("weights must contain all six features with finite nonnegative values")


@dataclass
class RetrievalResult:
    """M1 diagnostics sidecar; ContextPayload remains the shared output."""

    context: ContextPayload
    overlay_id: str | None
    counter_label: str
    config: dict[str, Any]
    candidates: list[dict[str, Any]]
    omissions: list[dict[str, str]]
    traversal_limited: bool
    unavailable_features: list[str]
    history_label: str | None


class GraphContextRetriever:
    def __init__(
        self, document: dict[str, Any], repository_root: str | Path, *,
        count_tokens: Callable[[str], int], counter_label: str,
        config: RetrievalConfig | None = None,
        change_counts: Mapping[str, float] | None = None, history_label: str | None = None,
    ) -> None:
        validate_graph_document(document)
        self.document = copy.deepcopy(document)
        self.nodes = {node["id"]: node for node in self.document["nodes"]}
        self.root = Path(repository_root).resolve()
        if not self.root.is_dir():
            raise InvalidQueryError("repository_root must be an existing directory")
        if not callable(count_tokens) or not isinstance(counter_label, str) or not counter_label.strip():
            raise InvalidQueryError("provide count_tokens and an explicit counter_label")
        self.count_tokens = count_tokens
        self.counter_label = counter_label
        self.config = copy.deepcopy(config or RetrievalConfig())
        if change_counts is not None and (
            not history_label or any(not isinstance(key, str) or not _number(value) or value < 0
                                     for key, value in change_counts.items())
        ):
            raise InvalidQueryError("change_counts needs finite nonnegative counts and history_label")
        self.change_counts = dict(change_counts) if change_counts is not None else None
        self.history_label = history_label
        self.files = {node["path"]: node for node in self.nodes.values() if node["type"] == "File"}
        self.adjacency: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        self.callers: dict[str, set[str]] = defaultdict(set)
        self._index_relations()

    def get_related_context(self, anchor_ids: list[str], budget_tokens: int, **kwargs: Any) -> ContextPayload:
        return self.retrieve(anchor_ids, budget_tokens, **kwargs).context

    def retrieve(
        self, anchor_ids: list[str], budget_tokens: int, *,
        issue_text: str = "", overlay: TaskOverlay | None = None, include: Callable[[dict[str, Any]], bool] | None = None,
    ) -> RetrievalResult:
        if isinstance(budget_tokens, bool) or not isinstance(budget_tokens, int) or budget_tokens <= 0:
            raise InvalidLimitError("budget_tokens must be a positive integer")
        if not isinstance(anchor_ids, list) or any(not isinstance(value, str) for value in anchor_ids):
            raise InvalidQueryError("anchor_ids must be a list of node ID strings")
        if not isinstance(issue_text, str):
            raise InvalidQueryError("issue_text must be a string")
        anchors = sorted(set(anchor_ids))
        for node_id in anchors:
            if node_id not in self.nodes:
                raise NodeNotFoundError(node_id)
            if not self._eligible(self.nodes[node_id]):
                raise InvalidQueryError("anchor must be a source-backed file/module/symbol/test")
        anchor_scores: dict[str, float] = {}
        failing_tests: list[str] = []
        if overlay is not None:
            if overlay.graph_version != self.document["graph_version"]:
                raise InvalidQueryError("task overlay belongs to a different graph snapshot")
            validate_graph_document({
                **self.document, "nodes": self.document["nodes"] + overlay.nodes,
                "edges": self.document["edges"] + overlay.edges,
            })
            anchor_scores = {anchor.node_id: anchor.score for anchor in overlay.grounding.anchors}
            failing_tests = sorted({edge["source_id"] for edge in overlay.edges
                                    if edge["type"] == "REPRODUCES"})
            if not issue_text:
                issue_text = overlay.nodes[0]["properties"].get("issue_text", "")
        available = list(_WEIGHTS)
        unavailable = ["architecture_dependencies"]
        if self.change_counts is None:
            available.remove("recent_change_frequency")
            unavailable.append("recent_change_frequency")
        if not failing_tests:
            available.remove("failing_test_proximity")
            unavailable.append("failing_test_proximity")
        weight_sum = sum(self.config.weights[name] for name in available)
        if weight_sum <= 0:
            raise InvalidQueryError("active ranking features must have positive total weight")
        states, limited = self._walk(anchors, anchor_scores, include)
        test_states, test_limited = self._walk(failing_tests, {})
        task_words = _words(issue_text)
        history_max = max(self.change_counts.values(), default=0) if self.change_counts is not None else 0
        candidates = []
        filtered_by_include = 0
        for node_id, (distance, confidence, rationale) in states.items():
            node = self.nodes[node_id]
            if include is not None and (not include(node) or node["qualified_name"].startswith("tests.")):
                filtered_by_include += 1
                continue
            words = _words(" ".join((node["name"], node["qualified_name"], node["path"],
                                    node["properties"].get("signature", ""))))
            public = node["properties"].get("visibility") == "public"
            fanin = len(self.callers[node_id])
            features = {
                "task_similarity": len(words & task_words) / max(1, len(words | task_words)),
                "graph_distance": 1 / (1 + distance), "edge_confidence": confidence,
                "failing_test_proximity": (1 / (1 + test_states[node_id][0])
                                           if node_id in test_states else 0.0) if failing_tests else None,
                "public_api_risk": (0.5 + 0.5 * fanin / (1 + fanin)) if public else 0.0,
                "recent_change_frequency": (self.change_counts.get(node_id,
                    self.change_counts.get(node["path"], 0)) / history_max if history_max else 0.0)
                    if self.change_counts is not None else None,
            }
            score = sum(self.config.weights[name] * features[name] for name in available) / weight_sum
            candidates.append({"node_id": node_id, "path": node["path"], "symbol": node["qualified_name"],
                               "graph_distance": distance, "confidence": confidence,
                               "graph_rationale": list(rationale), "features": features,
                               "relevance_score": score})
        candidates.sort(key=lambda item: (-item["relevance_score"], item["graph_distance"],
                                          item["path"], item["symbol"], item["node_id"]))
        items: list[ContextItem] = []
        omissions = []
        total = 0
        truncated = limited
        if candidates:
            sources = self._verify_snapshot()
            selected: list[tuple[str, int, int]] = []
            for candidate in candidates:
                node = self.nodes[candidate["node_id"]]
                if include is not None and (not include(node) or node["qualified_name"].startswith("tests.")):
                    filtered_by_include += 1
                    continue
                source_range = node["range"]
                start, end = source_range["start_byte"], source_range["end_byte"]
                if node["path"] not in sources:
                    raise GraphError("Graph node path has no source File in this snapshot")
                snippet = self._snippet(node, sources[node["path"]])
                if any(path == node["path"] and start < other_end and other_start < end
                       for path, other_start, other_end in selected):
                    omissions.append({"node_id": node["id"], "reason": "overlapping_selected_range"})
                    continue
                tokens = self.count_tokens(snippet)
                if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
                    raise InvalidQueryError("count_tokens must return a nonnegative integer")
                candidate["token_count"] = tokens
                if total + tokens > budget_tokens:
                    truncated = True
                    omissions.append({"node_id": node["id"], "reason": "token_budget"})
                    continue
                items.append(ContextItem(
                    node_id=node["id"], path=node["path"], symbol=node["qualified_name"],
                    range=SourceRange(**{key: source_range[key] for key in
                                        ("start_line", "start_col", "end_line", "end_col")}),
                    snippet=snippet, relevance_score=candidate["relevance_score"],
                    graph_distance=candidate["graph_distance"], graph_rationale=candidate["graph_rationale"],
                    confidence=candidate["confidence"], token_count=tokens,
                ))
                selected.append((node["path"], start, end))
                total += tokens
            # Detect edits/additions/deletions while token counting/packing was running.
            self._verify_snapshot()
        result = ContextPayload(graph_version=self.document["graph_version"], anchor_ids=anchors,
                                items=items, total_token_count=total,
                                token_budget=budget_tokens, truncated=truncated)
        diagnostics = asdict(self.config)
        diagnostics.update({"profile": "semantic-context-v1", "active_features": available,
                            "normalized_weights": {name: self.config.weights[name] / weight_sum for name in available},
                            "failing_test_traversal_limited": test_limited,
                            "filtered_by_include": filtered_by_include})
        return RetrievalResult(result, overlay.overlay_id if overlay else None, self.counter_label,
                               diagnostics, candidates, omissions, limited, unavailable, self.history_label)

    @staticmethod
    def _eligible(node: dict[str, Any]) -> bool:
        return node["type"] in _RETRIEVABLE and bool(node.get("path")) and bool(node.get("range"))

    def _index_relations(self) -> None:
        parents = {edge["target_id"]: edge for edge in self.document["edges"] if edge["type"] == "CONTAINS"}

        def connect(source: str, target: str, confidence: float, forward: str, reverse: str) -> None:
            if not self._eligible(self.nodes[source]) or not self._eligible(self.nodes[target]):
                return
            if confidence < self.config.min_edge_confidence:
                return
            self.adjacency[source].append((target, confidence, forward))
            self.adjacency[target].append((source, confidence, reverse))

        for edge in self.document["edges"]:
            source, target, confidence = edge["source_id"], edge["target_id"], edge["confidence"]
            if edge["type"] in {"CALLS", "IMPORTS"}:
                parent = parents.get(source)
                if parent is None:
                    continue
                source = parent["source_id"]
                confidence = min(confidence, parent["confidence"])
                connect(source, target, confidence, edge["type"],
                        "CALLERS" if edge["type"] == "CALLS" else "IMPORTED_BY")
                if edge["type"] == "CALLS" and confidence >= self.config.min_edge_confidence:
                    self.callers[target].add(source)
            elif edge["type"] in {"CONTAINS", "TESTS", "INHERITS", "REFERENCES"}:
                connect(source, target, confidence, edge["type"],
                        {"CONTAINS": "CONTAINED_BY", "TESTS": "TESTED_BY",
                         "INHERITS": "SUBCLASS", "REFERENCES": "REFERENCED_BY"}[edge["type"]])
        for node_id in self.adjacency:
            self.adjacency[node_id] = sorted(set(self.adjacency[node_id]))

    def _walk(
        self, starts: list[str], scores: dict[str, float],
        include: Callable[[dict[str, Any]], bool] | None = None,
    ) -> tuple[dict[str, tuple[int, float, tuple[str, ...]]], bool]:
        def counts(node_id: str) -> bool:
            return include is None or include(self.nodes[node_id])

        hard_cap = self.config.max_candidates * 4
        kept = 0
        states: dict[str, tuple[int, float, tuple[str, ...]]] = {}
        queue = []
        ordered = sorted(set(starts), key=lambda node_id: (-scores.get(node_id, 1.0), node_id))
        limited = len(ordered) > self.config.max_candidates
        for node_id in ordered[:self.config.max_candidates]:
            confidence = scores.get(node_id, 1.0)
            states[node_id] = (0, confidence, ("TASK_ANCHOR",))
            kept += 1
            heapq.heappush(queue, (0, -confidence, node_id, ("TASK_ANCHOR",)))
        while queue:
            distance, negative, node_id, rationale = heapq.heappop(queue)
            if states[node_id] != (distance, -negative, rationale) or distance >= self.config.max_hops:
                continue
            for target, edge_confidence, relation in self.adjacency[node_id]:
                path = rationale + (f"{relation}:{node_id}->{target}",)
                candidate = (distance + 1, min(-negative, edge_confidence), path)
                existing = states.get(target)
                if existing is not None and (existing[0], -existing[1], existing[2]) <= (
                    candidate[0], -candidate[1], candidate[2]
                ):
                    continue
                if existing is None:
                    if counts(target):
                        if kept >= self.config.max_candidates:
                            limited = True
                            continue
                        kept += 1
                    elif len(states) >= hard_cap:
                        limited = True
                        continue
                states[target] = candidate
                heapq.heappush(queue, (candidate[0], -candidate[1], target, candidate[2]))
        return states, limited

    def _verify_snapshot(self) -> dict[str, bytes]:
        actual = {path.relative_to(self.root).as_posix() for path in self.root.rglob("*.py")
                  if not any(part in IGNORED_DIRECTORY_NAMES for part in path.parts)}
        if actual != set(self.files):
            raise GraphError("Source file set differs from graph snapshot; rebuild graph",
                             details={"reason": "source_snapshot_mismatch",
                                      "added": sorted(actual - set(self.files)),
                                      "missing": sorted(set(self.files) - actual)})
        sources = {}
        for relative, node in sorted(self.files.items()):
            path = PurePosixPath(relative)
            if path.is_absolute() or PureWindowsPath(relative).drive or ".." in path.parts or path.as_posix() != relative:
                raise GraphError("Invalid repository-relative graph source path")
            resolved = (self.root / relative).resolve()
            if not resolved.is_relative_to(self.root):
                raise GraphError("Graph source path escapes repository root")
            try:
                data = resolved.read_bytes()
            except OSError as error:
                raise GraphError("Cannot read graph source; rebuild graph", details={"path": relative}) from error
            if _hash(data) != node.get("content_hash"):
                raise GraphError("Source content differs from graph snapshot; rebuild graph", details={"path": relative})
            sources[relative] = data
        return sources

    @staticmethod
    def _snippet(node: dict[str, Any], data: bytes) -> str:
        source_range = node["range"]
        start, end = source_range["start_byte"], source_range["end_byte"]
        if not 0 <= start <= end <= len(data):
            raise GraphError("Graph source byte range is out of bounds")
        for prefix, offset in (("start", start), ("end", end)):
            head = data[:offset]
            line = head.count(b"\n") + 1
            column = len(head.rsplit(b"\n", 1)[-1])
            if (line, column) != (source_range[f"{prefix}_line"], source_range[f"{prefix}_col"]):
                raise GraphError("Graph byte range does not match line/column metadata")
        snippet = data[start:end]
        if _hash(snippet) != node.get("content_hash"):
            raise GraphError("Graph snippet content hash mismatch; rebuild graph")
        try:
            return snippet.decode("utf-8")
        except UnicodeDecodeError as error:
            raise GraphError("Snippet cannot be decoded as UTF-8") from error


def _number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _words(text: str) -> set[str]:
    expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return {match.lower() for match in _WORDS.findall(expanded)}