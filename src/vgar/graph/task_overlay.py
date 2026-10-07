"""M1 task-local links over an unchanged repository graph snapshot."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from vgar.contracts.schema import GraphValidationError, validate_graph_document
from vgar.graph.grounding import AnchorResult, TaskAnchorFinder


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
        # Finder validates the complete base once and owns only grounding records.
        # Do not copy all callsites/edges/cold statistics for every task overlay.
        self._finder = TaskAnchorFinder(document)
        self._document = {key: document[key] for key in
                          ("repo_key", "graph_version", "repository_revision")}
        self._nodes = {node["id"]: node for node in self._finder.nodes}
        self._base_ids = {node["id"] for node in document["nodes"]}
        self._base_edge_ids = {edge["id"] for edge in document["edges"]}
        self._repository = copy.deepcopy(next(
            node for node in document["nodes"] if node["type"] == "Repository"
        ))

    def build(
        self, task_id: str, issue_text: str, failing_tests: list[str] | None = None,
    ) -> TaskOverlay:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        grounding = self._finder.find_task_anchors(issue_text, failing_tests)
        reports = sorted(set(failing_tests or []))
        task_hash = _digest({"task_id": task_id})
        overlay_id = _digest({
            "graph_version": grounding.graph_version, "task_id": task_id,
            "issue_text": issue_text, "failing_tests": reports,
            "profile": "task-overlay-v1",
        })
        issue_id = f"vgar:{self._document['repo_key']}:issue:{task_hash}"
        if issue_id in self._base_ids:
            raise ValueError("base graph already contains this task Issue; use a repository snapshot")
        issue = {
            "id": issue_id, "type": "Issue", "repo_key": self._document["repo_key"],
            "name": task_id, "qualified_name": task_id, "path": None,
            "language": None, "range": None, "graph_version": grounding.graph_version,
            "content_hash": _digest({"issue_text": issue_text, "failing_tests": reports}),
            "properties": {"task_id": task_id, "issue_text": issue_text,
                           "failing_tests": reports, "overlay_id": overlay_id},
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
        edges.sort(key=lambda edge: (edge["type"], edge["source_id"], edge["target_id"]))
        # The unchanged base has already been validated. Validate the delta and
        # its owned endpoints, including collisions with every original edge ID.
        collisions = sorted({edge["id"] for edge in edges} & self._base_edge_ids)
        if collisions:
            raise GraphValidationError([f"duplicate edge id: {edge_id}" for edge_id in collisions])
        endpoints = sorted({anchor.node_id for anchor in grounding.anchors})
        validate_graph_document({
            **self._document,
            "nodes": [self._repository, issue] + [self._nodes[node_id] for node_id in endpoints],
            "edges": edges,
        })
        return TaskOverlay(grounding.graph_version, overlay_id, task_id, [issue], edges, grounding)

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
