"""Bounded static test selection. Selected tests are candidates, not coverage proof."""
from __future__ import annotations

from collections import defaultdict, deque
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
    for values in (symbol_ids, changed_paths or [], failing_tests or [], selected_tests or []):
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
            if caller:
                reverse_calls[edge["target_id"]][caller] = max(reverse_calls[edge["target_id"]].get(caller, 0), edge["confidence"])
        elif edge["type"] == "TESTS":
            tests[edge["target_id"]].append(edge)
    targets = set(symbol_ids)
    target_paths = paths | {nodes[node_id]["path"] for node_id in targets if nodes[node_id]["type"] in {"File", "Module"}}
    targets.update(node["id"] for node in nodes.values() if node.get("path") in target_paths and node["type"] in {"Function", "Method", "Class"})

    def test_selector(node: dict) -> str:
        names = [node["name"]]
        parent = parents.get(node["id"])
        while parent and nodes[parent]["type"] == "Class":
            names.insert(0, nodes[parent]["name"])
            parent = parents.get(parent)
        return node["path"] + "::" + "::".join(names)

    candidates, visited = {}, set()
    traversal_limited = False
    queue = deque((target, 0, [target], 1.0) for target in sorted(targets))
    while queue:
        if len(visited) >= 2000:
            traversal_limited = True
            break
        target, distance, route, route_confidence = queue.popleft()
        if target in visited:
            continue
        visited.add(target)
        for edge in tests[target]:
            node = nodes[edge["source_id"]]
            selector = test_selector(node)
            entry = {"selector": selector, "node_id": node["id"], "distance": distance,
                     "confidence": min(edge["confidence"], route_confidence), "reason": "direct_call" if not distance else "transitive_call",
                     "via": route, "coverage_verified": False}
            if selector not in candidates or distance < candidates[selector]["distance"]:
                candidates[selector] = entry
        if distance < max_hops:
            queue.extend((caller, distance + 1, route + [caller], min(route_confidence, reverse_calls[target][caller]))
                         for caller in sorted(reverse_calls[target]))
    failing = sorted({_selector(value) for value in failing_tests or []})
    selected = sorted({_selector(value) for value in selected_tests or []})
    ordered = sorted(candidates.values(), key=lambda item: (item["distance"], -item["confidence"], item["selector"]))
    # Always retain all supplied fallback tests. Never silently drop failing tests under the graph limit.
    graph_tests = [entry["selector"] for entry in ordered[:limit]]
    mode = "graph" if graph_tests else "failing_tests" if failing else "selected_tests" if selected else "unavailable"
    chosen = sorted(set(graph_tests + failing)) if graph_tests else failing or selected
    result = {"graph_version": document["graph_version"], "tests": chosen, "selection_mode": mode,
              "fallback_reason": None if graph_tests else "no_graph_test_links", "candidates": ordered[:limit],
              "truncated": len(ordered) > limit, "traversal_limited": traversal_limited,
              "requires_full_suite": not chosen, "coverage_verified": False}
    (trace or GraphTrace()).emit("test_selection", **result)
    return result
