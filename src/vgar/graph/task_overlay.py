"""M1 task-local links over an unchanged repository graph snapshot."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from vgar.contracts.schema import validate_graph_document
from vgar.graph.grounding import (
    _ROUTE,
    AnchorEvidence,
    AnchorResult,
    TaskAnchor,
    TaskAnchorFinder,
    issue_symbol_text,
)
from vgar.graph.source_evidence import (
    SourceEvidence, diagnostic_lines, message_matches, quoted_message_matches, quoted_phrases,
)
from vgar.graph.task_graph import TaskFacts, extract_task_facts
from vgar.graph.trace_links import TraceLink, build_trace_links


@dataclass
class TaskOverlay:
    """Internal M1 sidecar; not a standalone portable graph or MCP DTO."""

    graph_version: str
    overlay_id: str
    task_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    grounding: AnchorResult


# G4 constants, fixed before measuring R1 (plan 2026-11-23 Task 10).
_TEXT_MATCH_MIN = 0.1
_TEXT_MATCH_LIMIT = 3
_TEXT_MATCH_SCORE = 0.2


class TaskOverlayBuilder:
    def __init__(self, document: dict[str, Any]) -> None:
        validate_graph_document(document)
        # Own a snapshot copy so later caller mutations cannot change this task view.
        self._document = copy.deepcopy(document)
        self._finder = TaskAnchorFinder(self._document)
        self._nodes = {node["id"]: node for node in self._document["nodes"]}

    def build(
        self, task_id: str, issue_text: str, failing_tests: list[str] | None = None,
        *, labels: list[str] | None = None, sources: Mapping[str, str] | None = None,
        evidence: Callable[[], SourceEvidence] | None = None,
    ) -> TaskOverlay:
        """The task overlay: anchors, G_task nodes, trace links.

        Args:
            task_id: Task identifier.
            issue_text: The task's issue text.
            failing_tests: Reported failing test selectors.
            labels: Issue labels.
            sources: Source text by path; when given, code whose message literal the issue quotes in a labelled
                log line becomes an ``error_message`` anchor, and one it quotes in prose a ``quoted_message`` anchor
                (proposal §6.6).
            evidence: Optional factory of a cached ``SourceEvidence`` over ``sources`` (with messages), called only
                when the issue has a labelled line or a quoted phrase.
        """
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        evidence_factory = evidence   # the name ``evidence`` is reused below for anchor evidence lists
        grounding = self._finder.find_task_anchors(issue_text, failing_tests)
        reports = sorted(set(failing_tests or []))
        facts = extract_task_facts(issue_text, failing_tests=failing_tests or (), labels=labels or ())
        task_hash = _digest({"task_id": task_id})
        overlay_id = _digest({
            "graph_version": grounding.graph_version, "task_id": task_id,
            "issue_text": issue_text, "failing_tests": reports, "labels": facts.labels,
            "profile": "task-overlay-v14-batch4-grounding",
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
        task_nodes = self._add_task_facts(facts, grounding, issue, task_hash, overlay_id, edges)
        links = build_trace_links(issue_id, task_nodes, grounding, self._document["nodes"])
        for link in links:
            edges.append(self._edge(link.edge_type, link.source_id, link.target_id, link.confidence, link.evidence,
                                    overlay_id, link.properties, link.rule_id))
        self._add_error_anchors(grounding, links, task_nodes, issue_text, sources, issue_id, overlay_id, edges,
                                evidence_factory)
        self._add_text_fallback(grounding, issue_text, sources, evidence_factory, issue_id, overlay_id, edges)
        edges.sort(key=lambda edge: (edge["type"], edge["source_id"], edge["target_id"]))
        # Validate existing endpoints/provenance without changing the shared contract.
        validate_graph_document({
            **self._document, "nodes": self._document["nodes"] + [issue, *task_nodes],
            "edges": self._document["edges"] + edges,
        })
        return TaskOverlay(grounding.graph_version, overlay_id, task_id, [issue, *task_nodes], edges, grounding)

    def _add_error_anchors(
        self, grounding: AnchorResult, links: list[TraceLink], task_nodes: list[dict[str, Any]], issue_text: str,
        sources: Mapping[str, str] | None, issue_id: str, overlay_id: str, edges: list[dict[str, Any]],
        evidence: Callable[[], SourceEvidence] | None = None,
    ) -> None:
        """Error messages as anchors (proposal §6.6, spec 2026-11-20 §5.3), each with a MENTIONS edge.

        The exception class an ErrorMessage resolves to scores its trace-link confidence; code whose message literal
        the issue quotes scores 0.85 when it is the only match and 0.5 for a shared template (the retrieval values).
        """
        task_types = {node["id"]: node["type"] for node in task_nodes}
        found: dict[str, list[tuple[float, AnchorEvidence]]] = {}
        for link in links:
            if link.edge_type == "RESOLVES_TO" and task_types.get(link.source_id) == "ErrorMessage":
                name = link.evidence[0].get("name", "") if link.evidence else ""
                found.setdefault(link.target_id, []).append((link.confidence, AnchorEvidence("error", name, "issue")))
        visible = issue_symbol_text(issue_text)
        if sources is not None and (diagnostic_lines(visible) or quoted_phrases(visible)):
            built = evidence() if evidence is not None else None
            labelled = message_matches(self._document["nodes"], sources, issue_text, evidence=built)
            quoted = quoted_message_matches(self._document["nodes"], sources, issue_text, evidence=built)
            # G3 (spec 2026-11-23 §4.5): a message quoted in prose scores like one in a labelled log line.
            for kind, matches in (("error_message", labelled), ("quoted_message", quoted)):
                for node_id, fragments in matches.items():
                    score = 0.5 if len(matches) > 1 else 0.85
                    found.setdefault(node_id, []).append((score, AnchorEvidence(kind, fragments[0], "issue")))
        anchors = {anchor.node_id: anchor for anchor in grounding.anchors}
        for node_id in sorted(found):
            score = max(value for value, _ in found[node_id])
            evidence = [item for _, item in found[node_id]]
            anchor = anchors.get(node_id)
            if anchor is None:
                node = self._nodes[node_id]
                anchor = TaskAnchor(node_id, node["path"], node["qualified_name"], score, evidence)
                grounding.anchors.append(anchor)
            else:
                anchor.score = max(anchor.score, score)
                anchor.evidence.extend(evidence)
            old = next((edge for edge in edges if edge["type"] == "MENTIONS" and edge["target_id"] == node_id), None)
            properties = ({key: value for key, value in old["properties"].items() if key != "overlay_id"}
                          if old is not None else {"has_ambiguous_evidence": False})
            if old is not None:
                edges.remove(old)
            edges.append(self._edge("MENTIONS", issue_id, node_id, anchor.score,
                                    [asdict(item) for item in anchor.evidence], overlay_id, properties))
        if found:
            grounding.anchors.sort(key=lambda item: (-item.score, item.path, item.symbol, item.node_id))

    def _add_text_fallback(
        self, grounding: AnchorResult, issue_text: str, sources: Mapping[str, str] | None,
        evidence: Callable[[], SourceEvidence] | None, issue_id: str, overlay_id: str, edges: list[dict[str, Any]],
    ) -> None:
        """G4 (spec 2026-11-23 §4.5, proposal §15 "fallback to text"): with no anchor at all, the functions whose body
        shares the most issue words become low-score ``text_match`` anchors."""
        if grounding.anchors or sources is None:
            return
        if evidence is not None:
            built = evidence()
        else:
            from vgar.graph.retrieval import _words   # here: retrieval imports this module

            present = [node for node in self._document["nodes"] if node.get("path") in sources]
            built = SourceEvidence(present, sources, _words)
        words = frozenset(built.tokenize(issue_symbol_text(issue_text)))
        ranked = []
        for node_id in built.terms:
            node = self._nodes[node_id]
            if node["type"] not in {"Function", "Method"} or node["qualified_name"].startswith("tests."):
                continue
            similarity = built.similarity(node_id, words)
            if similarity >= _TEXT_MATCH_MIN:
                ranked.append((similarity, node))
        ranked.sort(key=lambda item: (-item[0], item[1]["qualified_name"], item[1]["id"]))
        for _, node in ranked[:_TEXT_MATCH_LIMIT]:
            shared = sorted(built.terms[node["id"]] & words, key=lambda term: (-built.idf[term], term))[:3]
            evidence_item = AnchorEvidence("text_match", " ".join(shared), "issue")
            grounding.anchors.append(TaskAnchor(node["id"], node["path"], node["qualified_name"], _TEXT_MATCH_SCORE,
                                                [evidence_item]))
            edges.append(self._edge("MENTIONS", issue_id, node["id"], _TEXT_MATCH_SCORE, [asdict(evidence_item)],
                                    overlay_id, {"has_ambiguous_evidence": False}))

    def _add_task_facts(
        self, facts: TaskFacts, grounding: AnchorResult, issue: dict[str, Any], task_hash: str, overlay_id: str,
        edges: list[dict[str, Any]],
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
        # Requirement family (spec 2026-11-17-tv2-gt-1-requirements-design §2-§3).
        requirement_ids = []
        for ordinal, requirement in enumerate(facts.requirements):
            requirement_ids.append(add("requirement", "Requirement", ordinal, requirement.text[:80],
                                       {"text": requirement.text, "source": requirement.source}))
            mention(requirement_ids[-1], 0.6)
        for source, target, kind in facts.requirement_links:
            edges.append(self._edge(kind, requirement_ids[source], requirement_ids[target], 0.5, [], overlay_id, {},
                                    f"task.{kind.lower()}.requirement.v1"))
        for ordinal, constraint in enumerate(facts.constraints):
            mention(add("constraint", "Constraint", ordinal, constraint.text[:80],
                        {"text": constraint.text, "kind": constraint.kind}), 0.6)
        actors: dict[str, int] = {}
        for ordinal, story in enumerate(facts.stories):
            mention(add("user_story", "UserStory", ordinal, story.text[:80], {"text": story.text, "actor": story.actor}), 0.7)
            actors.setdefault(story.actor, len(actors))
        for actor, ordinal in actors.items():
            mention(add("actor", "Actor", ordinal, actor, {"name": actor}), 0.5)
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

    def _edge(
        self, edge_type: str, source: str, target: str, confidence: float,
        evidence: list[dict[str, str]], overlay_id: str, properties: dict[str, Any],
        rule_id: str | None = None,
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
                "rule_id": rule_id or f"task.{edge_type.lower()}.v1",
                "source_revision": self._document["repository_revision"], "evidence": evidence,
            },
        }


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
