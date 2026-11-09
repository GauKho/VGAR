"""M1 task-local links over an unchanged repository graph snapshot."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from vgar.contracts.schema import validate_graph_document
from vgar.graph.grounding import _ROUTE, AnchorResult, TaskAnchorFinder
from vgar.graph.task_graph import TaskFacts, extract_task_facts

_MAX_TRACE_EVIDENCE = 5


@dataclass
class TaskOverlay:
    """Internal M1 sidecar; not a standalone portable graph or MCP DTO."""

    graph_version: str
    overlay_id: str
    task_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    grounding: AnchorResult


class TaskOverlayBuilder:
    def __init__(self, document: dict[str, Any]) -> None:
        validate_graph_document(document)
        # Own a snapshot copy so later caller mutations cannot change this task view.
        self._document = copy.deepcopy(document)
        self._finder = TaskAnchorFinder(self._document)
        self._nodes = {node["id"]: node for node in self._document["nodes"]}

    def build(
        self, task_id: str, issue_text: str, failing_tests: list[str] | None = None,
        *, labels: list[str] | None = None,
    ) -> TaskOverlay:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        grounding = self._finder.find_task_anchors(issue_text, failing_tests)
        reports = sorted(set(failing_tests or []))
        facts = extract_task_facts(issue_text, failing_tests=failing_tests or (), labels=labels or ())
        task_hash = _digest({"task_id": task_id})
        overlay_id = _digest({
            "graph_version": grounding.graph_version, "task_id": task_id,
            "issue_text": issue_text, "failing_tests": reports, "labels": facts.labels,
            "profile": "task-overlay-v10-g-task",
        })
        issue_id = f"vgar:{self._document['repo_key']}:issue:{task_hash}"
        if issue_id in self._nodes:
            raise ValueError("base graph already contains this task Issue; use a repository snapshot")
        issue = {
            "id": issue_id, "type": "Issue", "repo_key": self._document["repo_key"],
            "name": task_id, "qualified_name": task_id, "path": None,
            "language": None, "range": None, "graph_version": grounding.graph_version,
            "content_hash": _digest({"issue_text": issue_text, "failing_tests": reports, "labels": facts.labels}),
            "properties": {"task_id": task_id, "issue_text": issue_text, "failing_tests": reports,
                           "labels": list(facts.labels), "overlay_id": overlay_id},
        }
        ambiguous = {
            (match.matched_text, node_id)
            for match in grounding.ambiguous_matches for node_id in match.candidate_ids
        }
        edges = []
        for anchor in grounding.anchors:
            evidence = [asdict(item) for item in anchor.evidence]
            edges.append(self._edge(
                "MENTIONS", issue_id, anchor.node_id, anchor.score, evidence,
                overlay_id, {"has_ambiguous_evidence": any(
                    (item.matched_text, anchor.node_id) in ambiguous for item in anchor.evidence
                )},
            ))
            if self._nodes[anchor.node_id]["type"] != "Test":
                continue
            reproduction_evidence = [
                item for item in anchor.evidence if item.source == "failing_test"
                and (item.matched_text, anchor.node_id) not in ambiguous
            ]
            if reproduction_evidence:
                scores = {"pytest_selector": 1.0, "path_line": 0.95, "symbol": 0.6}
                confidence = max(
                    0.8 if item.kind == "symbol" and "." in item.matched_text
                    else scores[item.kind] for item in reproduction_evidence
                )
                edges.append(self._edge(
                    "REPRODUCES", anchor.node_id, issue_id, confidence,
                    [asdict(item) for item in reproduction_evidence], overlay_id,
                    {"input_reported_failure": True, "execution_verified": False},
                ))
        task_nodes = self._add_task_facts(facts, grounding, issue, task_hash, overlay_id, edges, ambiguous)
        edges.sort(key=lambda edge: (edge["type"], edge["source_id"], edge["target_id"]))
        # Validate existing endpoints/provenance without changing the shared contract.
        validate_graph_document({
            **self._document, "nodes": self._document["nodes"] + [issue, *task_nodes],
            "edges": self._document["edges"] + edges,
        })
        return TaskOverlay(grounding.graph_version, overlay_id, task_id, [issue, *task_nodes], edges, grounding)

    def _add_task_facts(
        self, facts: TaskFacts, grounding: AnchorResult, issue: dict[str, Any], task_hash: str, overlay_id: str,
        edges: list[dict[str, Any]], ambiguous: set[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """G_task nodes for the extracted facts (spec §5); appends their edges to ``edges``."""
        nodes: list[dict[str, Any]] = []
        task_id = issue["name"]

        def add(kind: str, node_type: str, ordinal: int, name: str, properties: dict[str, Any]) -> str:
            node_id = f"vgar:{self._document['repo_key']}:task:{task_hash}:{kind}:{ordinal}"
            nodes.append({
                "id": node_id, "type": node_type, "repo_key": self._document["repo_key"], "name": name,
                "qualified_name": f"{task_id}::{kind}:{ordinal}", "path": None, "language": None, "range": None,
                "graph_version": grounding.graph_version, "content_hash": _digest(properties), "properties": properties,
            })
            return node_id

        def mention(target: str, confidence: float) -> None:
            edges.append(self._edge("MENTIONS", issue["id"], target, confidence, [], overlay_id, {}))

        bug_report = None
        if facts.bug_signals:
            bug_report = add("bug_report", "BugReport", 0, task_id, {"signals": list(facts.bug_signals)})
            mention(bug_report, 0.7)
        for frame in facts.frames:
            mention(add("stack_frame", "StackTraceFrame", frame.order, f"{frame.file}:{frame.line}",
                        {"file": frame.file, "line": frame.line, "function": frame.function, "order": frame.order}), 0.95)
        for ordinal, error in enumerate(facts.errors):
            mention(add("error", "ErrorMessage", ordinal, error.exception_type.rsplit(".", 1)[-1],
                        {"exception_type": error.exception_type, "message": error.message,
                         "occurrences": error.occurrences}), 0.9)
        for ordinal, criterion in enumerate(facts.criteria):
            mention(add("acceptance", "AcceptanceCriterion", ordinal, criterion.text[:80],
                        {"text": criterion.text, "checked": criterion.checked}), 0.7)
        for ordinal, selector in enumerate(facts.failing_tests):
            test_ids = sorted({
                anchor.node_id for anchor in grounding.anchors if self._nodes[anchor.node_id]["type"] == "Test"
                and any(item.source == "failing_test" and re.search(rf"(?<!\w){re.escape(item.matched_text)}(?!\w)", selector)
                        for item in anchor.evidence)
            })
            failing = add("failing_test", "FailingTest", ordinal, selector, {"selector": selector, "test_node_ids": test_ids})
            edges.append(self._edge("REPRODUCES", failing, bug_report, 0.8, [], overlay_id,
                                    {"input_reported_failure": True, "execution_verified": False}))
        for route_id, confidence in sorted(self._mentioned_routes(issue["properties"]["issue_text"]).items()):
            mention(route_id, confidence)
        self._add_traces(grounding, issue["id"], overlay_id, edges, ambiguous)
        return nodes

    def _mentioned_routes(self, issue_text: str) -> dict[str, float]:
        """Route node id -> confidence for paths named in the issue (spec §5.5)."""
        routes = [node for node in self._document["nodes"] if node["type"] == "Route"]
        found: dict[str, float] = {}
        for match in _ROUTE.finditer(issue_text) if routes else ():
            method = match.group("method")
            if match.group("route") == "/" and method is None:  # a bare slash in prose is not a path
                continue
            for route in routes:
                if route["properties"]["route_path"] == match.group("route") and (method is None or method in route["properties"]["methods"]):
                    found[route["id"]] = max(found.get(route["id"], 0.0), 0.8 if method else 0.6)
        return found

    def _add_traces(
        self, grounding: AnchorResult, issue_id: str, overlay_id: str, edges: list[dict[str, Any]],
        ambiguous: set[tuple[str, str]],
    ) -> None:
        """Issue -> Component for every Component holding an anchor that is not purely ambiguous (spec §5.6)."""
        owners = {path: node["id"] for node in self._document["nodes"] if node["type"] == "Component"
                  for path in node["properties"]["files"]}
        anchors: dict[str, list[Any]] = defaultdict(list)
        for anchor in grounding.anchors:
            if anchor.path in owners and not all((item.matched_text, anchor.node_id) in ambiguous for item in anchor.evidence):
                anchors[owners[anchor.path]].append(anchor)
        for component_id, members in anchors.items():
            evidence = [{"kind": "anchor", "node_id": node_id} for node_id in sorted(member.node_id for member in members)[:_MAX_TRACE_EVIDENCE]]
            edges.append(self._edge("TRACES_TO", issue_id, component_id, max(member.score for member in members), evidence,
                                    overlay_id, {"anchor_count": len(members)}))

    def _edge(
        self, edge_type: str, source: str, target: str, confidence: float,
        evidence: list[dict[str, str]], overlay_id: str, properties: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": _digest({"overlay_id": overlay_id, "type": edge_type,
                           "source_id": source, "target_id": target}),
            "type": edge_type, "source_id": source, "target_id": target,
            "confidence": confidence, "resolution": "heuristic",
            "graph_version": self._document["graph_version"],
            "properties": {"overlay_id": overlay_id, **properties},
            "provenance": {
                "source_tool": "vgar-m1-task-overlay", "source_tool_version": "0.1.0",
                "rule_id": f"task.{edge_type.lower()}.v1",
                "source_revision": self._document["repository_revision"], "evidence": evidence,
            },
        }


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
