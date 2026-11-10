"""TR-1 trace links from G_task nodes to G_repo and G_arch (proposal 491; spec 2026-11-10-tv2-tr-1-trace-links-design)."""
from __future__ import annotations

import builtins
import logging
from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Any

from vgar.graph.grounding import (
    _SYMBOL_TYPES,
    AnchorResult,
    _contains_line,
    is_absolute_path,
    resolve_absolute_frame,
)

logger = logging.getLogger(__name__)

_MAX_TRACE_EVIDENCE = 5
_BUILTIN_EXCEPTIONS = frozenset(
    name for name, value in vars(builtins).items() if isinstance(value, type) and issubclass(value, BaseException)
)


@dataclass(frozen=True)
class TraceLink:
    edge_type: str  # "TRACES_TO" or "RESOLVES_TO"
    source_id: str
    target_id: str
    confidence: float
    rule_id: str
    evidence: list[dict[str, str]]
    properties: dict[str, Any]


def build_trace_links(
    issue_id: str, task_nodes: list[dict[str, Any]], grounding: AnchorResult, nodes: list[dict[str, Any]],
) -> list[TraceLink]:
    """Links from one task to the repository and its components; nothing is guessed when several targets fit.

    Args:
        issue_id: Node id of the task's Issue.
        task_nodes: The G_task nodes built for this task, without the Issue.
        grounding: Anchors found for the issue text.
        nodes: Nodes of the repository graph.
    """
    links = _component_links(issue_id, grounding, nodes)
    files = {node["path"]: node for node in nodes if node["type"] == "File"}
    symbols: dict[str, list[dict[str, Any]]] = defaultdict(list)
    classes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        if node["type"] in _SYMBOL_TYPES:
            symbols[node["path"]].append(node)
        if node["type"] == "Class":
            classes[node["name"]].append(node)
    scores = {anchor.node_id: anchor.score for anchor in grounding.anchors}
    for node in task_nodes:
        if node["type"] == "StackTraceFrame":
            links.extend(_frame_links(node, files, symbols))
        elif node["type"] == "FailingTest":
            links.extend(
                TraceLink("RESOLVES_TO", node["id"], test_id, scores[test_id], "task.resolves_to.failing_test.v1",
                          [{"kind": "test_selector", "selector": node["properties"]["selector"]}], {})
                for test_id in node["properties"]["test_node_ids"]
            )
        elif node["type"] == "ErrorMessage":
            links.extend(_error_links(node, classes))
    logger.debug("built %d trace links for %s", len(links), issue_id)
    return links


def rank_component_traces(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The TRACES_TO edges of one issue, best first.

    Ties on confidence and anchor count go to the more nested component
    (``fees/discounts`` before ``fees``): an outer package that merely calls
    into the failing one is the less specific trace. The id breaks what is left.

    Args:
        edges: TRACES_TO edges carrying ``properties.anchor_count``.
    """
    return sorted(edges, key=lambda edge: (-edge["confidence"], -edge["properties"]["anchor_count"],
                                           -_component_depth(edge["target_id"]), edge["target_id"]))


def _component_depth(component_id: str) -> int:
    """Number of path segments in a component id's key (``...:component:a/b`` -> 2)."""
    return len(component_id.rsplit(":component:", 1)[-1].split("/"))


def _component_links(issue_id: str, grounding: AnchorResult, nodes: list[dict[str, Any]]) -> list[TraceLink]:
    """Issue -> Component for every Component holding an anchor that is not purely ambiguous."""
    owners = {path: node["id"] for node in nodes if node["type"] == "Component" for path in node["properties"]["files"]}
    ambiguous = {(match.matched_text, node_id) for match in grounding.ambiguous_matches for node_id in match.candidate_ids}
    anchors: dict[str, list[Any]] = defaultdict(list)
    for anchor in grounding.anchors:
        if anchor.path in owners and not all((item.matched_text, anchor.node_id) in ambiguous for item in anchor.evidence):
            anchors[owners[anchor.path]].append(anchor)
    return [
        TraceLink("TRACES_TO", issue_id, component_id, max(member.score for member in members), "task.traces_to.v1",
                  [{"kind": "anchor", "node_id": node_id} for node_id in sorted(member.node_id for member in members)[:_MAX_TRACE_EVIDENCE]],
                  {"anchor_count": len(members)})
        for component_id, members in anchors.items()
    ]


def _frame_links(
    frame: dict[str, Any], files: dict[str, dict[str, Any]], symbols: dict[str, list[dict[str, Any]]],
) -> list[TraceLink]:
    properties = frame["properties"]
    path = _frame_file(properties["file"], files)
    if path is None:
        return []
    target, confidence = _frame_target(properties, files[path], symbols[path])
    return [TraceLink("RESOLVES_TO", frame["id"], target["id"], confidence, "task.resolves_to.frame.v1",
                      [{"kind": "frame_location", "file": properties["file"], "line": str(properties["line"])}], {})]


def _frame_file(raw_path: str, files: Collection[str]) -> str | None:
    path = raw_path.replace("\\", "/")
    if is_absolute_path(path):
        return resolve_absolute_frame(path, files)
    path = path.removeprefix("./")
    if ".." in path.split("/"):
        return None
    if path in files:
        return path
    if "/" not in path:  # a bare name matches only the root file, not any file of that name
        return None
    matches = [candidate for candidate in files if candidate.endswith(f"/{path}")]
    return matches[0] if len(matches) == 1 else None


def _frame_target(
    properties: dict[str, Any], file: dict[str, Any], symbols: list[dict[str, Any]],
) -> tuple[dict[str, Any], float]:
    """The function name decides; the line only narrows it, because tracebacks often come from another version."""
    function = properties["function"]
    if not function or function.startswith("<"):
        return file, 0.7
    named = [symbol for symbol in symbols if symbol["name"] == function]
    containing = [symbol for symbol in named if _contains_line(symbol["range"], properties["line"])]
    if containing:
        return min(containing, key=lambda symbol: (symbol["range"]["end_byte"] - symbol["range"]["start_byte"], symbol["id"])), 0.95
    if len(named) == 1:
        return named[0], 0.8
    return file, 0.6


def _error_links(error: dict[str, Any], classes: dict[str, list[dict[str, Any]]]) -> list[TraceLink]:
    name = error["properties"]["exception_type"]
    short_name = name.rsplit(".", 1)[-1]
    same_name = classes.get(short_name, [])
    exact = [node for node in same_name if node["qualified_name"] == name]
    if "." in name and len(exact) == 1:
        target, confidence = exact[0], 0.9
    elif "." not in name and name in _BUILTIN_EXCEPTIONS:
        return []
    elif len(same_name) == 1 and _is_exception(same_name[0], classes):
        target, confidence = same_name[0], 0.6
    else:
        return []
    return [TraceLink("RESOLVES_TO", error["id"], target["id"], confidence, "task.resolves_to.error.v1",
                      [{"kind": "exception_name", "name": name}], {})]


def _is_exception(node: dict[str, Any], classes: dict[str, list[dict[str, Any]]]) -> bool:
    """Whether the bases reach a built-in exception; a parent that cannot be identified counts as no."""
    seen: set[str] = set()
    pending = [node]
    while pending:
        current = pending.pop()
        if current["id"] in seen:
            continue
        seen.add(current["id"])
        for base in current["properties"]["bases"]:
            if "=" in base:  # metaclass=... and other keyword arguments
                continue
            name = base.split("[", 1)[0].strip().rsplit(".", 1)[-1]
            if name in _BUILTIN_EXCEPTIONS:
                return True
            if len(classes.get(name, [])) == 1:
                pending.append(classes[name][0])
    return False
