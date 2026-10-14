"""Bounded static test selection. Selected tests are candidates, not coverage proof."""
from __future__ import annotations

import heapq
from collections import defaultdict
from pathlib import PurePosixPath, PureWindowsPath

from vgar.contracts.error import InvalidLimitError, InvalidQueryError, NodeNotFoundError
from vgar.contracts.schema import validate_graph_document
from vgar.observability.graph_trace import GraphTrace


def _selector(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.startswith("-") or "\n" in value or "\r" in value:
        raise InvalidQueryError("test selector must be a nonempty single-line string")
    path = value.split("::", 1)[0]
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive or ".." in PurePosixPath(path).parts or "\\" in path:
        raise InvalidQueryError("test selector must use a repository-relative POSIX path")
    return value


def select_related_tests(document: dict, symbol_ids: list[str], *, changed_paths: list[str] | None = None,
                         failing_tests: list[str] | None = None, selected_tests: list[str] | None = None,
                         max_hops: int = 2, limit: int = 50, trace: GraphTrace | None = None) -> dict:
    validate_graph_document(document)
    for values in (symbol_ids, *(value if value is not None else []
                                for value in (changed_paths, failing_tests, selected_tests))):
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise InvalidQueryError("test selection inputs must be lists of strings")
    if isinstance(max_hops, bool) or not isinstance(max_hops, int) or not 0 <= max_hops <= 8:
        raise InvalidLimitError("test selection max_hops must be within [0, 8]")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise InvalidLimitError("test selection limit must be within [1, 1000]")
    nodes = {node["id"]: node for node in document["nodes"]}
    for symbol in symbol_ids:
        if symbol not in nodes:
            raise NodeNotFoundError(symbol)
    paths = {_selector(path) for path in changed_paths or []}
    if any("::" in path for path in paths):
        raise InvalidQueryError("changed_paths must contain paths, not test selectors")
    parents = {edge["target_id"]: edge["source_id"] for edge in document["edges"] if edge["type"] == "CONTAINS"}
    reverse_calls, tests = defaultdict(dict), defaultdict(list)
    for edge in document["edges"]:
        if edge["type"] == "CALLS":
            caller = parents.get(edge["source_id"])
            # TESTS already accounts for calls originating in a test. Traversing
            # those calls again neither finds additional callers nor adds proof.
            if caller and nodes[caller]['type'] != 'Test':
                reverse_calls[edge["target_id"]][caller] = max(reverse_calls[edge["target_id"]].get(caller, 0), edge["confidence"])
        elif edge["type"] == "TESTS":
            tests[edge["target_id"]].append(edge)
    targets = set(symbol_ids)
    target_paths = paths | {nodes[node_id]["path"] for node_id in targets if nodes[node_id]["type"] in {"File", "Module"}}
    targets.update(node["id"] for node in nodes.values() if node.get("path") in target_paths
                   and node["type"] in {"Function", "Method", "Class", "Test"})

    def test_selector(node: dict) -> str:
        names = [node["name"]]
        parent = parents.get(node["id"])
        while parent and nodes[parent]["type"] == "Class":
            names.insert(0, nodes[parent]["name"])
            parent = parents.get(parent)
        return node["path"] + "::" + "::".join(names)

    candidates, visited, boundary = {}, set(), set()
    traversal_limited = False

    def offer_test(node: dict, distance: int, route: tuple, confidence: float, reason: str) -> None:
        selector = test_selector(node)
        entry = {"selector": selector, "node_id": node["id"], "distance": distance,
                 "confidence": confidence, "reason": reason, "via": list(route), "coverage_verified": False}
        existing = candidates.get(selector)
        if existing is None or (distance, -confidence, route) < (
                existing['distance'], -existing['confidence'], tuple(existing['via'])):
            candidates[selector] = entry

    # Resolve shortest routes first, then the strongest equal-hop route. A
    # weaker first discovery must not suppress stronger evidence for the test.
    best = {target: (0, -1.0, (target,)) for target in targets}
    queue = [(0, -1.0, (target,), target) for target in targets]
    heapq.heapify(queue)
    while queue:
        distance, negative_confidence, route, target = heapq.heappop(queue)
        if target in visited or (distance, negative_confidence, route) != best[target]:
            continue
        if len(visited) >= 2000:
            traversal_limited = True
            break
        visited.add(target)
        route_confidence = -negative_confidence
        if nodes[target]['type'] == 'Test':
            offer_test(nodes[target], distance, route, route_confidence,
                       'changed_test' if nodes[target]['path'] in target_paths else 'test_target')
        for edge in tests[target]:
            offer_test(nodes[edge['source_id']], distance, route, min(edge['confidence'], route_confidence),
                       'direct_call' if not distance else 'transitive_call')
        if distance == max_hops:
            boundary.update(reverse_calls[target])
            continue
        for caller, confidence in reverse_calls[target].items():
            state = (distance + 1, -min(route_confidence, confidence), route + (caller,))
            if caller not in best or state < best[caller]:
                best[caller] = state
                heapq.heappush(queue, (*state, caller))
    # Do not flag a cycle or caller already reachable within the same bound.
    traversal_limited = traversal_limited or bool(boundary - best.keys())
    failing = sorted({_selector(value) for value in failing_tests or []})
    selected = sorted({_selector(value) for value in selected_tests or []})
    ordered = sorted(candidates.values(), key=lambda item: (item["distance"], -item["confidence"], item["selector"]))
    # Always retain all supplied fallback tests. Never silently drop failing tests under the graph limit.
    graph_tests = [entry["selector"] for entry in ordered[:limit]]
    truncated = len(ordered) > limit
    reason = ('no_graph_test_links' if not graph_tests else 'test_traversal_limited' if traversal_limited
              else 'test_candidates_truncated' if truncated else None)
    mode = "graph" if graph_tests else "failing_tests" if failing else "selected_tests" if selected else "unavailable"
    chosen = sorted(set(graph_tests + failing)) if graph_tests else failing or selected
    result = {"graph_version": document["graph_version"], "tests": chosen, "selection_mode": mode,
              "fallback_reason": reason, "candidates": ordered[:limit],
              "truncated": truncated, "traversal_limited": traversal_limited,
              "requires_full_suite": not chosen, "coverage_verified": False}
    (trace or GraphTrace()).emit("test_selection", **result)
    return result
