"""Bounded semantic retrieval and source-verified context packing for M1."""
from __future__ import annotations

import copy
import hashlib
import heapq
import math
import re
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from vgar.contracts.context import ContextItem, ContextPayload, SourceRange
from vgar.contracts.error import GraphError, InvalidLimitError, InvalidQueryError, NodeNotFoundError
from vgar.contracts.schema import validate_graph_document
from vgar.graph.builder import discover_python_files
from vgar.graph.grounding import issue_symbol_text, issue_topic_text
from vgar.graph.source_evidence import SourceEvidence, diagnostic_lines
from vgar.graph.task_overlay import TaskOverlay
from vgar.observability.graph_trace import GraphTrace


_RETRIEVABLE = {"File", "Module", "Class", "Function", "Method", "Test"}
_WORDS = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_TOPIC_STOP = frozenset('a an and are as at be by can describe does failing for from how i in is it of on or problem python related request should that the this to use using was when with would'.split())
_WEIGHTS = {"task_similarity": 0.5, "graph_distance": 0.2, "edge_confidence": 0.1,
            "failing_test_proximity": 0.2, "public_api_risk": 0.0, "recent_change_frequency": 0.1}


@dataclass(frozen=True)
class RetrievalConfig:
    max_hops: int = 2
    max_candidates: int = 100
    min_edge_confidence: float = 0.6
    weights: dict[str, float] = field(default_factory=lambda: dict(_WEIGHTS))
    reference_budget_fraction: float = 0.2
    use_source_evidence: bool = True
    prefer_relevant_paths: bool = True
    gate_failing_test_evidence: bool = True
    use_diagnostic_evidence: bool = True
    use_component_seeds: bool = True
    use_topic_evidence: bool = False

    def __post_init__(self) -> None:
        for name, value, minimum in (("max_hops", self.max_hops, 0),
                                     ("max_candidates", self.max_candidates, 1)):
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise InvalidLimitError(f"{name} must be an integer >= {minimum}")
        if not _number(self.min_edge_confidence) or not 0 <= self.min_edge_confidence <= 1:
            raise InvalidQueryError("min_edge_confidence must be within [0, 1]")
        if not _number(self.reference_budget_fraction) or not 0 <= self.reference_budget_fraction <= 1:
            raise InvalidQueryError("reference_budget_fraction must be within [0, 1]")
        if any(not isinstance(flag, bool) for flag in (
            self.use_source_evidence, self.prefer_relevant_paths, self.gate_failing_test_evidence,
            self.use_diagnostic_evidence,
            self.use_component_seeds,
            self.use_topic_evidence,
        )):
            raise InvalidQueryError("retrieval evidence flags must be booleans")
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
        trace: GraphTrace | None = None,
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
        self.trace = trace or GraphTrace()
        self.files = {node["path"]: node for node in self.nodes.values() if node["type"] == "File"}
        self.adjacency: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        self.callers: dict[str, set[str]] = defaultdict(set)
        self.reference_dependencies: dict[str, set[str]] = defaultdict(set)
        frequencies: dict[str, int] = defaultdict(int)
        symbols = [node for node in self.nodes.values() if node["type"] in {"Class", "Function", "Method", "Test"}]
        for node in symbols:
            names = [node['name'], *[alias['name'] for alias in node['properties'].get('symbol_aliases', [])]]
            for word in set().union(*(_words(name) for name in names)):
                frequencies[word] += 1
        self._name_idf = {word: math.log(1 + len(symbols) / frequency) for word, frequency in frequencies.items()}
        self._max_name_idf = max(self._name_idf.values(), default=1.0)
        self._source_evidence = None
        self._spellings = {
            node_id: [(_words(name), _words(qualified + ' ' + node['path'])) for name, qualified in
                      [(node['name'], node['qualified_name']),
                       *[(alias['name'], alias['qualified_name']) for alias in node['properties'].get('symbol_aliases', [])]]]
            for node_id, node in self.nodes.items() if node.get('path')
        }
        self._similarity_cache = lru_cache(maxsize=8192)(self._score_task_similarity)
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
        self.trace.emit("retrieval_start", graph_version=self.document["graph_version"],
                        anchor_ids=anchors, budget_tokens=budget_tokens, overlay_id=overlay.overlay_id if overlay else None)
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
        visible_issue = issue_symbol_text(issue_text)
        task_words = frozenset(_words(visible_issue))
        topic_words = (frozenset(_words(issue_topic_text(issue_text))) - _TOPIC_STOP
                       if self.config.use_topic_evidence and self.config.use_source_evidence else frozenset())
        logs = diagnostic_lines(visible_issue) if self.config.use_diagnostic_evidence else ()
        component_nodes = self._component_nodes(visible_issue, anchors, include) if self.config.use_component_seeds else {}
        sources = None
        if (anchors and task_words and self.config.use_source_evidence) or logs or component_nodes:
            verified_sources = self._verify_snapshot()
            sources = verified_sources
            if self._source_evidence is None or (logs and not self._source_evidence.has_messages):
                self._source_evidence = SourceEvidence(self.nodes.values(), verified_sources, _words,
                                                       include_messages=bool(logs))
        diagnostic_matches = self._source_evidence.diagnostic_matches(logs) if logs else {}
        diagnostic_matches = {node_id: fragments for node_id, fragments in diagnostic_matches.items()
                              if include is None or (include(self.nodes[node_id])
                                  and not self.nodes[node_id]['qualified_name'].startswith('tests.'))}
        # A literal message is a source hint, never a resolved runtime binding.
        # Shared templates stay ambiguous; the normal candidate quota bounds
        # expansion. Keep all matches in diagnostics even when traversal caps.
        diagnostic_scores = {node_id: 0.5 if len(diagnostic_matches) > 1 else 0.85
                             for node_id in diagnostic_matches}
        component_limit = min(10, max(1, self._anchor_seed_limit() // 5))
        component_seeds = sorted(
            (node_id for node_id in component_nodes
             if node_id in self._source_evidence.terms
             and self._source_evidence.similarity(node_id, task_words | topic_words) > 0),
            key=lambda node_id: (-(self._source_evidence.similarity(node_id, task_words)
                                  + self._source_evidence.similarity(node_id, topic_words)) / 2
                                if topic_words else -self._source_evidence.similarity(node_id, task_words), node_id),
        )[:component_limit] if component_nodes else []
        starts = sorted(set(anchors) | set(diagnostic_matches) | set(component_seeds))
        scores = dict(anchor_scores)
        for node_id in component_seeds:
            scores[node_id] = max(scores.get(node_id, 1.0 if node_id in anchors else 0), 0.45)
            self.trace.emit('retrieval_component_seed', node_id=node_id,
                            components=component_nodes[node_id], confidence=0.45)
        for node_id, score in diagnostic_scores.items():
            scores[node_id] = max(scores.get(node_id, 1.0 if node_id in anchors else 0), score)
            self.trace.emit('retrieval_diagnostic_seed', node_id=node_id,
                            matched_fragments=diagnostic_matches[node_id], confidence=score)
        seed_rationales = {node_id: ('SOURCE_COMPONENT',) for node_id in component_seeds if node_id not in anchors}
        seed_rationales.update({node_id: ('SOURCE_DIAGNOSTIC',) for node_id in diagnostic_matches if node_id not in anchors})
        states, limited = self._walk(starts, scores, include, task_words=task_words,
                                     diagnostic_scores=diagnostic_scores,
                                     seed_rationales=seed_rationales, topic_words=topic_words)
        test_states, test_limited = self._walk(
            failing_tests, {}, relations={"CALLS", "CALLERS", "TESTS", "TESTED_BY"},
        )
        history_max = max(self.change_counts.values(), default=0) if self.change_counts is not None else 0
        candidates = []
        filtered_by_include = 0
        for node_id, (distance, confidence, rationale) in states.items():
            node = self.nodes[node_id]
            if include is not None and (not include(node) or node["qualified_name"].startswith("tests.")):
                filtered_by_include += 1
                continue
            public = node["properties"].get("visibility") == "public"
            fanin = len(self.callers[node_id])
            direct_similarity = self._task_similarity(node, task_words, diagnostic_scores, topic_words)
            raw_test_proximity = 1 / (1 + test_states[node_id][0]) if node_id in test_states else 0.0
            test_proximity = raw_test_proximity
            if self.config.gate_failing_test_evidence and task_words and node["type"] != "Test":
                # A failing test also calls setup/cleanup helpers. Their test
                # proximity supports ranking only in proportion to direct
                # evidence from the issue, without a task-specific threshold.
                test_proximity *= direct_similarity
            features = {
                "task_similarity": self._path_similarity(node_id, distance, rationale, task_words, diagnostic_scores, topic_words),
                # A weak prose seed must not gain full distance credit merely
                # because it is at hop zero.
                "graph_distance": confidence / (1 + distance), "edge_confidence": confidence,
                "failing_test_proximity": test_proximity if failing_tests else None,
                "public_api_risk": (0.5 + 0.5 * fanin / (1 + fanin)) if public else 0.0,
                "recent_change_frequency": (self.change_counts.get(node_id,
                    self.change_counts.get(node["path"], 0)) / history_max if history_max else 0.0)
                    if self.change_counts is not None else None,
            }
            score = sum(self.config.weights[name] * features[name] for name in available) / weight_sum
            candidates.append({"node_id": node_id, "path": node["path"], "symbol": node["qualified_name"],
                               "graph_distance": distance, "confidence": confidence,
                               "direct_task_similarity": direct_similarity,
                               "raw_failing_test_proximity": raw_test_proximity if failing_tests else None,
                               "failing_test_rationale": list(test_states[node_id][2]) if node_id in test_states else [],
                               "source_task_similarity": self._source_evidence.similarity(node_id, task_words)
                               if self._source_evidence and node_id in self._source_evidence.terms else None,
                               "diagnostic_fragments": diagnostic_matches.get(node_id, []),
                               "topic_source_similarity": self._source_evidence.similarity(node_id, topic_words)
                               if topic_words and self._source_evidence and node_id in self._source_evidence.terms else None,
                               "component_hints": component_nodes.get(node_id, []) if node_id in component_seeds else [],
                               "graph_rationale": list(rationale), "features": features,
                               "relevance_score": score})
        candidates.sort(key=lambda item: (-item["relevance_score"], item["graph_distance"],
                                          item["path"], item["symbol"], item["node_id"]))
        items: list[ContextItem] = []
        omissions = []
        total = 0
        reference_tokens = 0
        reference_selected = []
        truncated = limited
        if candidates:
            if sources is None:
                sources = self._verify_snapshot()
            selected: list[tuple[str, int, int]] = []
            candidate_index = {candidate["node_id"]: candidate for candidate in candidates}
            # Only the first three ranked seeds can reserve dependency snippets.
            reference_anchors = set([c["node_id"] for c in candidates if c["graph_distance"] == 0][:3])
            queue = deque((candidate, False) for candidate in candidates)
            selected_ids = set()
            while queue:
                candidate, reserved_reference = queue.popleft()
                node = self.nodes[candidate["node_id"]]
                if node["id"] in selected_ids:
                    continue
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
                if reserved_reference and reference_tokens + tokens > int(budget_tokens * self.config.reference_budget_fraction):
                    continue  # It remains in the ordinary ranked queue.
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
                selected_ids.add(node["id"])
                if reserved_reference:
                    reference_tokens += tokens
                    reference_selected.append(node["id"])
                    self.trace.emit("context_reference_selected", node_id=node["id"], token_count=tokens,
                                    runtime_dispatch_verified=False)
                if node["id"] in reference_anchors and self.config.reference_budget_fraction:
                    dependencies = [candidate_index[target] for target in self.reference_dependencies[node["id"]]
                                    if target in candidate_index and target not in selected_ids]
                    dependencies.sort(key=lambda c: (-c["relevance_score"], c["path"], c["symbol"], c["node_id"]))
                    queue.extendleft((dependency, True) for dependency in reversed(dependencies))
            # Detect edits/additions/deletions while token counting/packing was running.
            self._verify_snapshot()
        result = ContextPayload(graph_version=self.document["graph_version"], anchor_ids=starts,
                                items=items, total_token_count=total,
                                token_budget=budget_tokens, truncated=truncated)
        diagnostics = asdict(self.config)
        diagnostics.update({"profile": "semantic-context-v10-source-cache", "active_features": available,
                            "topic_words": sorted(topic_words),
                            "similarity_cache_limit": 8192,
                            "diagnostic_seed_ids": sorted(diagnostic_matches),
                            "component_seed_ids": component_seeds,
                            "component_seed_limit": component_limit,
                            "source_evidence_nodes": len(self._source_evidence.terms) if self._source_evidence else 0,
                            "source_evidence_unavailable_paths": self._source_evidence.unavailable_paths if self._source_evidence else [],
                            "semantic_similarity_decay": 0.7,
                            "reference_reserved_tokens": reference_tokens,
                            "reference_reserved_ids": reference_selected,
                            "name_similarity": "corpus-idf+executable-source" if self._source_evidence else "corpus-idf",
                            "frontier_selection": "global-relevance",
                            "public_api_risk_is_default_rank_signal": False,
                            "distance_uses_anchor_confidence": True,
                            "file_scope_folding": True,
                            "anchor_seed_limit": self._anchor_seed_limit(),
                            "excluded_nodes_use_candidate_quota": False,
                            "normalized_weights": {name: self.config.weights[name] / weight_sum for name in available},
                            "failing_test_traversal_limited": test_limited,
                            "failing_test_evidence": "semantic-path+direct-issue" if self.config.gate_failing_test_evidence else "semantic-path",
                            "filtered_by_include": filtered_by_include})
        for candidate in candidates:
            self.trace.emit("retrieval_candidate", **candidate)
        self.trace.emit('retrieval_cache', **self._similarity_cache.cache_info()._asdict())
        for omission in omissions:
            self.trace.emit("retrieval_omitted", **omission)
        self.trace.emit("retrieval_complete", selected_ids=[item.node_id for item in items],
                        total_token_count=total, truncated=truncated, traversal_limited=limited)
        return RetrievalResult(result, overlay.overlay_id if overlay else None, self.counter_label,
                               diagnostics, candidates, omissions, limited, unavailable, self.history_label)

    @staticmethod
    def _eligible(node: dict[str, Any]) -> bool:
        return node["type"] in _RETRIEVABLE and bool(node.get("path")) and bool(node.get("range"))

    def _component_nodes(self, issue, anchors, include):
        """Mentioned source directories are bounded hints, not symbol bindings."""
        tokens = {token.lower() for token in re.findall(r'\b[A-Za-z_]\w*\b', issue)}
        by_component = defaultdict(list)
        callables = [node for node in self.nodes.values() if node['type'] in {'Function', 'Method'}
                     and (include is None or (include(node) and not node['qualified_name'].startswith('tests.')))]
        for node in callables:
            for component in set(PurePosixPath(node['path']).parts[:-1]):
                if component.lower() in tokens:
                    by_component[component].append(node['id'])
        result = defaultdict(list)
        for component, nodes in by_component.items():
            # A package root appearing across most code cannot narrow a query.
            # Preserve explicit in-component anchors as the primary source.
            if len(nodes) > len(callables) / 2 or any(
                component in PurePosixPath(self.nodes[anchor]['path']).parts[:-1]
                for anchor in anchors
            ):
                continue
            for node_id in nodes:
                result[node_id].append(component)
        return {node_id: sorted(components) for node_id, components in result.items()}

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
            elif edge["type"] == "REFERENCES" and self.nodes[source]["type"] == "CallSite":
                parent = parents.get(source)
                if parent is not None:
                    connect(parent["source_id"], target, min(confidence, parent["confidence"]),
                            "MEMBER_REFERENCE", "MEMBER_REFERENCED_BY")
                    if (confidence >= self.config.min_edge_confidence
                            and edge["properties"].get("binding_kind") == "return_contract_hint"):
                        evidence = edge["properties"].get("evidence", {})
                        declared = evidence.get("declared_member_ids", [])
                        if target in declared or (not declared and self.nodes[target]["properties"].get("owner_class_id") == evidence.get("class_id")):
                            self.reference_dependencies[parent["source_id"]].add(target)
            elif edge["type"] in {"CONTAINS", "TESTS", "INHERITS", "REFERENCES"}:
                connect(source, target, confidence, edge["type"],
                        {"CONTAINS": "CONTAINED_BY", "TESTS": "TESTED_BY",
                         "INHERITS": "SUBCLASS", "REFERENCES": "REFERENCED_BY"}[edge["type"]])
        # File -> Module -> Class -> Method is representational nesting,
        # not three semantic dependencies. Fold verified containment only.
        for node in self.nodes.values():
            if node["type"] not in {"Function", "Method", "Test"}:
                continue
            current = node["id"]
            confidence = 1.0
            seen = set()
            while current in parents and current not in seen:
                seen.add(current)
                edge = parents[current]
                confidence = min(confidence, edge["confidence"])
                current = edge["source_id"]
                if self.nodes[current]["type"] == "File":
                    connect(current, node["id"], confidence, "SOURCE_CONTAINS", "SOURCE_FILE")
                    break
        for node_id in self.adjacency:
            # Prefer semantic neighbors before broad container/sibling expansion.
            self.adjacency[node_id] = sorted(set(self.adjacency[node_id]), key=lambda item: (
                0 if item[2] in {"CALLS", "CALLERS", "TESTS", "TESTED_BY", "MEMBER_REFERENCE", "MEMBER_REFERENCED_BY"} else
                2 if item[2] in {"CONTAINS", "CONTAINED_BY"} else 1,
                -item[1], item[0], item[2],
            ))

    def _anchor_seed_limit(self) -> int:
        # Reserve half the candidate quota for expansion when traversal is enabled.
        return (max(1, self.config.max_candidates // 2) if self.config.max_hops
                else self.config.max_candidates)

    def _walk(
        self, starts: list[str], scores: dict[str, float],
        include: Callable[[dict[str, Any]], bool] | None = None,
        *, task_words: set[str] | frozenset[str] | None = None,
        relations: set[str] | None = None,
        diagnostic_scores: dict[str, float] | None = None,
        seed_rationales: dict[str, tuple[str, ...]] | None = None,
        topic_words: frozenset[str] = frozenset(),
    ) -> tuple[dict[str, tuple[int, float, tuple[str, ...]]], bool]:
        def counts(node_id: str) -> bool:
            node = self.nodes[node_id]
            return include is None or (include(node) and not node["qualified_name"].startswith("tests."))

        hard_cap = self.config.max_candidates * 4
        kept = 0
        states: dict[str, tuple[int, float, tuple[str, ...]]] = {}
        queue = []
        def priority(node_id: str, distance: int, confidence: float, rationale=("TASK_ANCHOR",)) -> float:
            similarity = self._path_similarity(node_id, distance, rationale, task_words, diagnostic_scores, topic_words) if task_words else 0.0
            return 0.5 * similarity + 0.3 * confidence / (1 + distance)

        def path_order(node_id, state):
            distance, confidence, rationale = state
            relevance = priority(node_id, distance, confidence, rationale) if task_words and self.config.prefer_relevant_paths else 0.0
            # Preserve shortest-hop semantics. At the same hop, a broad
            # containment path must not hide stronger issue dependency evidence.
            return distance, -relevance, -confidence, rationale

        ordered = sorted(set(starts), key=lambda node_id: (
            -priority(node_id, 0, scores.get(node_id, 1.0)), node_id))
        limited = False
        for node_id in ordered:
            counted = counts(node_id)
            if (counted and kept >= self._anchor_seed_limit()) or len(states) >= hard_cap:
                limited = True
                continue
            confidence = scores.get(node_id, 1.0)
            rationale = (seed_rationales or {}).get(node_id, ("TASK_ANCHOR",))
            states[node_id] = (0, confidence, rationale)
            kept += int(counted)
            heapq.heappush(queue, (-priority(node_id, 0, confidence), 0, -confidence, node_id, rationale))
        # Pending neighbors do not consume the candidate quota until selected.
        # This lets all anchors compete, rather than letting the first broad
        # API fill the quota with its callers before other anchors expand.
        pending: dict[str, tuple[int, float, tuple[str, ...]]] = {}
        while queue:
            _, distance, negative, node_id, rationale = heapq.heappop(queue)
            state = (distance, -negative, rationale)
            if node_id in pending and pending[node_id] == state:
                del pending[node_id]
                if node_id not in states:
                    if counts(node_id):
                        if kept >= self.config.max_candidates:
                            limited = True
                            continue
                        kept += 1
                    elif len(states) >= hard_cap:
                        limited = True
                        continue
                states[node_id] = state
            if states.get(node_id) != state or distance >= self.config.max_hops:
                continue
            neighbors = self.adjacency[node_id]
            if task_words:
                neighbors = sorted(neighbors, key=lambda item: (
                    0 if item[2] in {"CALLS", "CALLERS", "TESTS", "TESTED_BY", "MEMBER_REFERENCE", "MEMBER_REFERENCED_BY"} else 1,
                    -self._task_similarity(self.nodes[item[0]], task_words, diagnostic_scores, topic_words), -item[1], item[0], item[2]))
            for target, edge_confidence, relation in neighbors:
                if relations is not None and relation not in relations:
                    continue
                path = rationale + (f"{relation}:{node_id}->{target}",)
                candidate = (distance + 1, min(-negative, edge_confidence), path)
                existing = pending.get(target, states.get(target))
                if existing is not None and path_order(target, existing) <= path_order(target, candidate):
                    continue
                pending[target] = candidate
                semantic_bonus = 0.05 if relation in {"CALLS", "CALLERS", "TESTS", "TESTED_BY", "MEMBER_REFERENCE", "MEMBER_REFERENCED_BY"} else 0.0
                heapq.heappush(queue, (-priority(target, candidate[0], candidate[1], path) - semantic_bonus,
                                      candidate[0], -candidate[1], target, candidate[2]))
        return states, limited

    def _path_similarity(self, node_id, distance, rationale, task_words, diagnostic_scores=None, topic_words=frozenset()) -> float:
        direct = self._task_similarity(self.nodes[node_id], task_words, diagnostic_scores, topic_words)
        relations = {"CALLS", "CALLERS", "TESTS", "TESTED_BY", "MEMBER_REFERENCE", "MEMBER_REFERENCED_BY"}
        # A dependency need not repeat the API name from the issue. Propagate
        # relevance only along semantic relations; file/sibling membership
        # alone must not make unrelated code relevant.
        if not distance or len(rationale) < 2 or any(step.split(":", 1)[0] not in relations for step in rationale[1:]):
            return direct
        origin = rationale[1].split(":", 1)[1].split("->", 1)[0]
        if origin not in self.nodes:
            return direct
        inherited = self._task_similarity(self.nodes[origin], task_words, diagnostic_scores, topic_words) * 0.7 ** distance
        return max(direct, inherited)

    def _task_similarity(self, node: dict[str, Any], task_words: set[str], diagnostic_scores=None, topic_words=frozenset()) -> float:
        return self._similarity_cache(node['id'], frozenset(task_words), frozenset(topic_words),
                                      (diagnostic_scores or {}).get(node['id'], 0.0),
                                      bool(self.config.use_source_evidence and self._source_evidence))

    def _score_task_similarity(self, node_id, task_words, topic_words, diagnostic_score, has_source) -> float:
        # Rare API words carry more evidence than ubiquitous helpers. IDF
        # depends only on source symbol names, never on benchmark labels.
        def similarity(names, context):
            matched = sum(self._name_idf.get(word, self._max_name_idf) for word in sorted(names & task_words))
            vocabulary = sum(self._name_idf.get(word, self._max_name_idf) for word in sorted(names))
            specificity = min(1.0, matched / (2 * self._max_name_idf))
            contextual = (self._source_evidence.similarity(node_id, task_words)
                          if has_source and node_id in self._source_evidence.terms
                          else len(context & task_words) / max(1, len(context)))
            return 0.8 * specificity * matched / max(1.0, vocabulary) + 0.2 * contextual
        focused = (.5 * self._source_evidence.similarity(node_id, topic_words)
                   if has_source and topic_words and node_id in self._source_evidence.terms else 0.0)
        return max(max(similarity(names, context) for names, context in self._spellings[node_id]),
                   diagnostic_score, focused)

    def _verify_snapshot(self) -> dict[str, bytes]:
        actual = {path.relative_to(self.root).as_posix() for path in discover_python_files(self.root)}
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
