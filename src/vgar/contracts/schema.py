from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any


NODE_TYPES = {
    "Repository",
    "File",
    "Module",
    "Class",
    "Function",
    "Method",
    "Import",
    "CallSite",
    "Test",
    "Issue",
}

SOURCE_BACKED_NODE_TYPES = {
    "File",
    "Class",
    "Function",
    "Method",
    "Import",
    "CallSite",
    "Test",
}

EDGE_ENDPOINTS: dict[str, set[tuple[str, str]]] = {
    "CONTAINS": {
        ("Repository", "File"),
        ("File", "Module"),
        ("Module", "Class"),
        ("Module", "Function"),
        ("Module", "Import"),
        ("Module", "Test"),
        ("Class", "Method"),
        ("Class", "Test"),
        ("Class", "Class"),
        ("Function", "Function"),
        ("Function", "Class"),
        ("Function", "CallSite"),
        ("Method", "Function"),
        ("Method", "Class"),
        ("Method", "CallSite"),
        ("Test", "CallSite"),
    },
    "IMPORTS": {("Import", "Module")},
    "INHERITS": {("Class", "Class")},
    "CALLS": {
        ("CallSite", "Function"),
        ("CallSite", "Method"),
        ("CallSite", "Class"),
    },
    "REFERENCES": {
        (source, target)
        for source in {
            "Module",
            "Class",
            "Function",
            "Method",
            "Test",
            "Import",
            "CallSite",
        }
        for target in {
            "File",
            "Module",
            "Class",
            "Function",
            "Method",
        }
    },
    "TESTS": {
        ("Test", target)
        for target in {
            "File",
            "Module",
            "Class",
            "Function",
            "Method",
        }
    },
    "MENTIONS": {
        ("Issue", target)
        for target in {
            "File",
            "Module",
            "Class",
            "Function",
            "Method",
            "Test",
        }
    },
    "REPRODUCES": {("Test", "Issue")},
}


class GraphValidationError(ValueError):
    """Raised when a graph document violates the frozen graph contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid graph document:\n- " + "\n- ".join(errors))


def validate_graph_document(document: Mapping[str, Any]) -> None:
    """Validate the portable JSON graph document used by M1 and M3."""

    errors: list[str] = []

    graph_version = document.get("graph_version")
    if not isinstance(graph_version, str) or not graph_version:
        errors.append("graph_version must be a non-empty string")

    nodes = document.get("nodes")
    edges = document.get("edges")

    if not isinstance(nodes, list):
        errors.append("nodes must be a list")
        nodes = []
    if not isinstance(edges, list):
        errors.append("edges must be a list")
        edges = []

    nodes_by_id: dict[str, Mapping[str, Any]] = {}
    repository_count = 0

    for index, node in enumerate(nodes):
        prefix = f"nodes[{index}]"
        if not isinstance(node, Mapping):
            errors.append(f"{prefix} must be an object")
            continue

        node_id = node.get("id")
        node_type = node.get("type")

        if not isinstance(node_id, str) or not node_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif node_id in nodes_by_id:
            errors.append(f"duplicate node id: {node_id}")
        else:
            nodes_by_id[node_id] = node

        if node_type not in NODE_TYPES:
            errors.append(f"{prefix}.type is unsupported: {node_type!r}")
        if node_type == "Repository":
            repository_count += 1

        for field in ("repo_key", "name", "qualified_name"):
            if not isinstance(node.get(field), str) or not node[field]:
                errors.append(f"{prefix}.{field} must be a non-empty string")

        if node.get("graph_version") != graph_version:
            errors.append(f"{prefix}.graph_version must match document graph_version")

        if not isinstance(node.get("properties"), Mapping):
            errors.append(f"{prefix}.properties must be an object")

        if node_type in SOURCE_BACKED_NODE_TYPES:
            if not isinstance(node.get("path"), str) or not node["path"]:
                errors.append(f"{prefix}.path is required for {node_type}")
            if not _valid_range(node.get("range")):
                errors.append(f"{prefix}.range is invalid for {node_type}")
        elif node_type == "Module":
            properties = node.get("properties") or {}
            if not properties.get("is_external"):
                if not isinstance(node.get("path"), str) or not node["path"]:
                    errors.append(f"{prefix}.path is required for internal Module")
                if not _valid_range(node.get("range")):
                    errors.append(f"{prefix}.range is invalid for internal Module")

    if repository_count != 1:
        errors.append(f"exactly one Repository node is required, got {repository_count}")

    edge_ids: set[str] = set()
    contains_adjacency: dict[str, list[str]] = defaultdict(list)
    call_counts: dict[str, int] = defaultdict(int)

    for index, edge in enumerate(edges):
        prefix = f"edges[{index}]"
        if not isinstance(edge, Mapping):
            errors.append(f"{prefix} must be an object")
            continue

        edge_id = edge.get("id")
        edge_type = edge.get("type")
        source_id = edge.get("source_id")
        target_id = edge.get("target_id")

        if not isinstance(edge_id, str) or not edge_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif edge_id in edge_ids:
            errors.append(f"duplicate edge id: {edge_id}")
        else:
            edge_ids.add(edge_id)

        if edge_type not in EDGE_ENDPOINTS:
            errors.append(f"{prefix}.type is unsupported: {edge_type!r}")

        source = nodes_by_id.get(source_id)
        target = nodes_by_id.get(target_id)
        if source is None:
            errors.append(f"{prefix}.source_id does not exist: {source_id!r}")
        if target is None:
            errors.append(f"{prefix}.target_id does not exist: {target_id!r}")

        if source_id == target_id:
            errors.append(f"{prefix} must not be a self-loop")

        if source is not None and target is not None and edge_type in EDGE_ENDPOINTS:
            endpoint = (source.get("type"), target.get("type"))
            if endpoint not in EDGE_ENDPOINTS[edge_type]:
                errors.append(
                    f"{prefix} has invalid endpoints for {edge_type}: "
                    f"{endpoint[0]} -> {endpoint[1]}"
                )

        confidence = edge.get("confidence")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.0 <= confidence <= 1.0
        ):
            errors.append(f"{prefix}.confidence must be within [0, 1]")

        if edge.get("graph_version") != graph_version:
            errors.append(f"{prefix}.graph_version must match document graph_version")

        provenance = edge.get("provenance")
        if not isinstance(provenance, Mapping):
            errors.append(f"{prefix}.provenance must be an object")
        else:
            for field in ("source_tool", "rule_id", "source_revision"):
                if not isinstance(provenance.get(field), str) or not provenance[field]:
                    errors.append(f"{prefix}.provenance.{field} is required")

        if not isinstance(edge.get("properties"), Mapping):
            errors.append(f"{prefix}.properties must be an object")

        if edge_type == "CONTAINS" and source_id and target_id:
            contains_adjacency[source_id].append(target_id)
        if edge_type == "CALLS" and source_id:
            call_counts[source_id] += 1

    errors.extend(_containment_cycle_errors(contains_adjacency))

    for node_id, node in nodes_by_id.items():
        if node.get("type") != "CallSite":
            continue
        properties = node.get("properties") or {}
        candidate_count = properties.get("candidate_count")
        if candidate_count != call_counts[node_id]:
            errors.append(
                f"CallSite {node_id!r} candidate_count={candidate_count!r} "
                f"but has {call_counts[node_id]} outgoing CALLS edges"
            )

    if errors:
        raise GraphValidationError(errors)


def _valid_range(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    required = (
        "start_line",
        "start_col",
        "end_line",
        "end_col",
        "start_byte",
        "end_byte",
    )
    if any(isinstance(value.get(field), bool) for field in required):
        return False
    if any(not isinstance(value.get(field), int) for field in required):
        return False
    return (
        value["start_line"] >= 1
        and value["start_col"] >= 0
        and value["end_line"] >= value["start_line"]
        and value["end_col"] >= 0
        and value["start_byte"] >= 0
        and value["end_byte"] >= value["start_byte"]
    )


def _containment_cycle_errors(
    adjacency: Mapping[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            errors.append(f"CONTAINS cycle detected at {node_id!r}")
            return
        if node_id in visited:
            return

        visiting.add(node_id)
        for child_id in adjacency.get(node_id, []):
            visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in adjacency:
        visit(node_id)

    return errors
