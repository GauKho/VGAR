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
    # Proposed for the plan's day-1 schema contract, pending team review (plan L1-3, SC-1;
    # proposal §4.3 lines 212-224). Only emitted when tree-sitter-graph is enabled.
    "Field",
    "GlobalVariable",
    # Proposed, pending team review (plan L1-2; proposal line 185 IDENTIFIER[name, type],
    # lines 530-531 "Identifier: username"). Def parameters only; tree-sitter-graph only.
    "Identifier",
    # Proposed, pending team review (plan L1-3; proposal line 221 ConfigEntry, line 806 config in F*).
    # One node per environment key for the whole repo, so not source-backed (like Issue).
    "ConfigEntry",
    # Proposed, pending team review (plan L1-3; proposal line 222 Route, line 336 "Route: POST /login",
    # line 1237 "route path/method changed?"). Static route decorators only.
    "Route",
    # Proposed, pending team review (plan L1-3; proposal line 223 Schema, line 1238 "schema field removed?").
    # dataclass / pydantic / TypedDict classes confirmed through imports.
    "Schema",
    # Proposed, pending team review (plan GA-2; proposal lines 251-259). Module is shared with G_repo.
    "Component",
    "Port",
    "Connector",
    "Service",
    "DeploymentUnit",
    "ExternalSystem",
    # Proposed, pending team review (plan GT-1; proposal lines 301-312). Issue is the existing node type.
    "BugReport",
    "Requirement",
    "UserStory",
    "AcceptanceCriterion",
    "FailingTest",
    "ErrorMessage",
    "StackTraceFrame",
    "Constraint",
    "Actor",
    # Proposed, pending team review (plan L3-1; proposal lines 193-197). Only emitted when Joern is enabled.
    # Not source-backed, like Port: it hangs off its function through AST_CHILD, not the CONTAINS chain.
    "Statement",
}

# Proposed, pending team review (plan GA-2, L1-3; proposal lines 236, 263-270).
G_ARCH_EDGE_TYPES = frozenset({
    "DEPENDS_ON", "EXPOSES_PORT", "CONSUMES_PORT", "COMMUNICATES_WITH", "CONTAINS_COMPONENT", "DEPLOYS_TO", "CONFIGURES",
})

# Proposed, pending team review (plan L3-1; proposal lines 193-197).
G_CODE_EDGE_TYPES = frozenset({"AST_CHILD", "CFG_NEXT", "DATA_DEPENDS_ON", "CONTROL_DEPENDS_ON"})

# One schema S (proposal §8.4) validated under two profiles; decided by TV2 on 08/11 for the MCP contract.
SCHEMA_VERSION = "vgar-schema-full-v5"
PROFILE_FULL_VGAR_MCP = "full_vgar_mcp"
PROFILE_LEGACY_W10 = "legacy_w10"
LEGACY_W10_NODE_TYPES = {
    "Repository", "File", "Module", "Class", "Function", "Method", "Import", "CallSite", "Test", "Issue",
}
LEGACY_W10_EDGE_TYPES = {"CONTAINS", "IMPORTS", "INHERITS", "CALLS", "REFERENCES", "TESTS", "MENTIONS", "REPRODUCES"}

SOURCE_BACKED_NODE_TYPES = {
    "File",
    "Class",
    "Function",
    "Method",
    "Import",
    "CallSite",
    "Test",
    "Field",
    "GlobalVariable",
    "Identifier",
    "Route",
    "Schema",
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
        ("Test", "Function"),
        ("Test", "Class"),
        # Proposed, pending team review (see NODE_TYPES).
        ("Class", "Field"),
        ("Module", "GlobalVariable"),
        # Proposed, pending team review (plan L1-2; proposal lines 185, 530-531).
        ("Function", "Identifier"),
        ("Method", "Identifier"),
        ("Test", "Identifier"),
        # Proposed, pending team review (plan L1-3; proposal lines 222, 336, 1237).
        ("Module", "Route"),
        # Proposed, pending team review (plan L1-3; proposal lines 223, 1238).
        ("Module", "Schema"),
    },
    # Proposed, pending team review (plan L1-2, SC-1; proposal §6.3 lines 536-540).
    # Emitted by tree-sitter-graph alongside the builder's CONTAINS edges.
    "HAS_METHOD": {("Class", "Method"), ("Class", "Test")},
    "HAS_CALLSITE": {("Function", "CallSite"), ("Method", "CallSite"), ("Test", "CallSite")},
    "IMPORTS": {("Import", "Module")},
    "INHERITS": {("Class", "Class")},
    # Proposed, pending team review (plan L1-3; proposal line 32 "Class C implements Interface I",
    # line 233 IMPLEMENTS: Class -> Interface). The interface is an in-repo ABC/Protocol class.
    "IMPLEMENTS": {("Class", "Class")},
    "CALLS": {
        ("CallSite", "Function"),
        ("CallSite", "Method"),
        ("CallSite", "Class"),
    },
    # Proposed, pending team review (plan L2-2; proposal lines 551-567). A low-confidence candidate of an unresolved call.
    "MAY_CALL": {("CallSite", "Function"), ("CallSite", "Method")},
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
    } | {
        # Proposed, pending team review (plan L1-3; proposal lines 221, 806): code reading an env key.
        (source, "ConfigEntry") for source in {"Module", "Function", "Method", "Test"}
    } | {
        # Proposed, pending team review (plan L1-3; proposal lines 222, 336, 1237): route -> handler.
        ("Route", target) for target in {"Function", "Method", "Test"}
    } | {
        # Proposed, pending team review (plan L1-3; proposal lines 223, 1238): schema -> its class.
        ("Schema", "Class"),
    },
    "TESTS": {
        ("Test", target)
        for target in {
            "File",
            "Module",
            "Class",
            "Function",
            "Method",
            # Proposed, pending team review (plan GT-1; proposal line 319).
            "Requirement",
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
            # Proposed, pending team review (plan GT-1; proposal lines 336, 649, spec §6).
            "StackTraceFrame",
            "ErrorMessage",
            "AcceptanceCriterion",
            "BugReport",
            "Route",
        }
    },
    # FailingTest -> BugReport is proposed, pending team review (plan GT-1; proposal line 322).
    "REPRODUCES": {("Test", "Issue"), ("FailingTest", "BugReport")},
    # Proposed, pending team review (plan GA-2, GT-1; proposal lines 264, 320).
    "DEPENDS_ON": {("Component", "Component"), ("Requirement", "Requirement")},
    "EXPOSES_PORT": {("Component", "Port")},
    "CONSUMES_PORT": {("Component", "Port")},
    "COMMUNICATES_WITH": {("Service", "Service")},
    "CONTAINS_COMPONENT": {("Module", "Component")},
    "DEPLOYS_TO": {("Component", "DeploymentUnit")},
    # Proposed, pending team review (plan L1-3; proposal line 236).
    "CONFIGURES": {("ConfigEntry", "Component"), ("ConfigEntry", "Service")},
    # Proposed, pending team review (plan GT-1; proposal lines 318, 321).
    "TRACES_TO": {("Issue", "Component"), ("Requirement", "Component")},
    "CONFLICTS_WITH": {("Requirement", "Requirement")},
    # Proposed, pending team review (plan TR-1; proposal line 548 uses this name for a reference resolved to its definition).
    "RESOLVES_TO": {
        ("StackTraceFrame", "File"),
        ("StackTraceFrame", "Class"),
        ("StackTraceFrame", "Function"),
        ("StackTraceFrame", "Method"),
        ("StackTraceFrame", "Test"),
        ("FailingTest", "Test"),
        ("ErrorMessage", "Class"),
    },
    # Proposed, pending team review (plan L3-1; proposal lines 193-197).
    "AST_CHILD": {
        ("Function", "Statement"),
        ("Method", "Statement"),
        ("Statement", "Statement"),
        ("Statement", "CallSite"),
        ("Statement", "Identifier"),
    },
    "CFG_NEXT": {("Statement", "Statement")},
    # The target is the function itself when the data is one of its parameters.
    "DATA_DEPENDS_ON": {("Statement", "Statement"), ("Statement", "Function"), ("Statement", "Method")},
    "CONTROL_DEPENDS_ON": {("Statement", "Statement")},
}


class GraphValidationError(ValueError):
    """Raised when a graph document violates the frozen graph contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid graph document:\n- " + "\n- ".join(errors))


def validate_graph_document(
    document: Mapping[str, Any],
    *,
    trusted_ids: frozenset[str] = frozenset(),
    profile: str = PROFILE_FULL_VGAR_MCP,
) -> None:
    """Validate the portable JSON graph document used by M1 and M3.

    Items whose id is in ``trusted_ids`` (incremental replay of already-validated items) skip the per-item
    field checks; every structural check (ids, types, endpoints, graph_version, cycles, CallSite counts) still runs.
    ``PROFILE_LEGACY_W10`` additionally rejects every node and edge type outside the W10 contract.
    """

    if profile not in {PROFILE_FULL_VGAR_MCP, PROFILE_LEGACY_W10}:
        raise ValueError(f"unknown schema profile: {profile!r}")
    legacy = profile == PROFILE_LEGACY_W10
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
        elif legacy and node_type not in LEGACY_W10_NODE_TYPES:
            errors.append(f"{prefix}.type {node_type!r} is not allowed in profile {profile}")
        if node_type == "Repository":
            repository_count += 1

        if node.get("graph_version") != graph_version:
            errors.append(f"{prefix}.graph_version must match document graph_version")

        if node_id in trusted_ids:
            continue

        for field in ("repo_key", "name", "qualified_name"):
            if not isinstance(node.get(field), str) or not node[field]:
                errors.append(f"{prefix}.{field} must be a non-empty string")

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
        elif legacy and edge_type not in LEGACY_W10_EDGE_TYPES:
            errors.append(f"{prefix}.type {edge_type!r} is not allowed in profile {profile}")

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

        if edge.get("graph_version") != graph_version:
            errors.append(f"{prefix}.graph_version must match document graph_version")

        if edge_id not in trusted_ids:
            confidence = edge.get("confidence")
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0.0 <= confidence <= 1.0
            ):
                errors.append(f"{prefix}.confidence must be within [0, 1]")

            provenance = edge.get("provenance")
            if not isinstance(provenance, Mapping):
                errors.append(f"{prefix}.provenance must be an object")
            else:
                for field in ("source_tool", "rule_id", "source_revision"):
                    if not isinstance(provenance.get(field), str) or not provenance[field]:
                        errors.append(f"{prefix}.provenance.{field} is required")

            if edge_type == "MAY_CALL":
                # Proposed, pending team review (plan L2-2; proposal lines 551-567).
                evidence = provenance.get("evidence") if isinstance(provenance, Mapping) else None
                if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item for item in evidence):
                    errors.append(f"{prefix}.provenance.evidence must be a non-empty list of strings for MAY_CALL")
                if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and confidence > 0.50:
                    errors.append(f"{prefix}.confidence must be at most 0.50 for MAY_CALL")

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


def project_legacy_w10(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project a full graph onto the W10 contract, under the graph_version the same source had before the full schema."""
    version = document["statistics"]["legacy_graph_version"]
    nodes = [{**node, "graph_version": version} for node in document["nodes"] if node["type"] in LEGACY_W10_NODE_TYPES]
    kept = {node["id"] for node in nodes}
    edges = [
        {**edge, "graph_version": version}
        for edge in document["edges"]
        if edge["type"] in LEGACY_W10_EDGE_TYPES and edge["source_id"] in kept and edge["target_id"] in kept
    ]
    node_counts: dict[str, int] = defaultdict(int)
    edge_counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        node_counts[node["type"]] += 1
    for edge in edges:
        edge_counts[edge["type"]] += 1
    statistics = {
        key: value for key, value in document["statistics"].items() if key not in {"may_call", "tsg", "legacy_graph_version"}
    }
    statistics.update(
        schema_profile=PROFILE_LEGACY_W10,
        node_count=len(nodes),
        edge_count=len(edges),
        node_counts_by_type=dict(node_counts),
        edge_counts_by_type=dict(edge_counts),
    )
    return {**document, "graph_version": version, "nodes": nodes, "edges": edges, "statistics": statistics}


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