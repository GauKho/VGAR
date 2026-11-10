from __future__ import annotations

import hashlib
import json
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

# One schema S (proposal §8.4); a built document records this profile name in statistics.schema_profile.
SCHEMA_VERSION = "vgar-schema-full-v5"
PROFILE_FULL_VGAR_MCP = "full_vgar_mcp"

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

# delta (proposal line 865, plan SC-1): keys the builder or overlay always writes and other code reads, with their JSON type.
# A type in "a|null" may be null. Types without such keys need only the common node fields.
NODE_PROPERTIES: dict[str, dict[str, str]] = {
    "Repository": {},
    "File": {"is_test_file": "boolean", "parse_status": "string"},
    # is_package is read but not required: graphs saved by earlier builders (tests/fixtures, artifacts/) lack it.
    "Module": {"is_external": "boolean", "module_name": "string", "resolution_status": "string"},
    "Class": {"bases": "array"},
    "Function": {"decorators": "array", "visibility": "string"},
    "Method": {"decorators": "array", "visibility": "string", "method_kind": "string", "owner_class_id": "string"},
    "Import": {"imported_module": "string", "imported_name": "string|null", "level": "integer", "resolution_status": "string"},
    "CallSite": {"candidate_count": "integer", "resolution_status": "string"},
    "Test": {},
    "Issue": {"issue_text": "string"},
    "Field": {},
    "GlobalVariable": {},
    "Identifier": {},
    "ConfigEntry": {},
    "Route": {"route_path": "string", "methods": "array"},
    "Schema": {},
    "Component": {"files": "array"},
    "Port": {"export": "string", "owner_component_id": "string", "symbol_id": "string"},
    "Connector": {},
    "Service": {},
    "DeploymentUnit": {},
    "ExternalSystem": {},
    "BugReport": {},
    "Requirement": {},
    "UserStory": {},
    "AcceptanceCriterion": {},
    "FailingTest": {"selector": "string", "test_node_ids": "array"},
    "ErrorMessage": {"exception_type": "string"},
    "StackTraceFrame": {"file": "string", "line": "integer", "function": "string|null"},
    "Constraint": {},
    "Actor": {},
    "Statement": {},
}

# Required edge properties by (edge type, source type, target type); "positive_integer" is an integer >= 1.
EDGE_PROPERTIES: dict[tuple[str, str, str], dict[str, str]] = {
    ("DEPENDS_ON", "Component", "Component"): {"weight": "positive_integer"},
    ("TRACES_TO", "Issue", "Component"): {"anchor_count": "positive_integer"},
}

# Gamma (proposal lines 866, 878): every invariant is a type, property, endpoint or cycle check over one pass.
# Architecture rules compared with a baseline (no new DEPENDS_ON cycle, no lost port) belong to EV-2 (proposal lines 285-293).
INVARIANTS: tuple[tuple[str, str], ...] = (
    ("single_repository", "Exactly one Repository node."),
    ("unique_node_ids", "No two nodes share an id."),
    ("unique_edge_ids", "No two edges share an id."),
    ("same_graph_version", "Every node and edge carries the document graph_version."),
    ("endpoints_exist", "Both ends of every edge are nodes of the document."),
    ("no_self_loop", "No edge goes from a node to itself."),
    ("contains_acyclic", "CONTAINS edges form no cycle."),
    ("callsite_candidate_count", "A CallSite's candidate_count equals its outgoing CALLS edges."),
    ("may_call_bounded", "A MAY_CALL edge has string evidence and confidence at most 0.50."),
    ("port_owner", "A Port's owner_component_id is a Component."),
    ("port_symbol", "A Port's symbol_id is a node of the document."),
    ("method_owner", "A Method's owner_class_id is a Class."),
    ("failing_test_targets", "Every id in a FailingTest's test_node_ids is a Test."),
    ("ast_single_parent", "A node has at most one incoming AST_CHILD edge."),
)

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict,
}


def _matches(value: Any, rule: str) -> bool:
    """Whether a property value fits a rule such as ``string`` or ``string|null``; booleans are never numbers."""
    for part in rule.split("|"):
        if part == "null":
            if value is None:
                return True
        elif part == "positive_integer":
            if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
                return True
        elif isinstance(value, _JSON_TYPES[part]) and not (part in {"integer", "number"} and isinstance(value, bool)):
            return True
    return False


def _property_errors(prefix: str, owner: str, properties: Mapping[str, Any], rules: Mapping[str, str]) -> list[str]:
    errors = []
    for key, rule in rules.items():
        if key not in properties:
            errors.append(f"{prefix}.properties.{key} is required for {owner}")
        elif not _matches(properties[key], rule):
            errors.append(f"{prefix}.properties.{key} must be {rule} for {owner}")
    return errors


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


# Layer of each type, after the graphs of proposal §4 (4.1 G_code, 4.2 G_repo, 4.4 G_arch, 4.5 G_task); metadata only.
LAYERS: dict[str, str] = {
    **{name: "G_repo" for name in (
        "Repository", "File", "Module", "Class", "Function", "Method", "Import", "CallSite", "Test",
        "Field", "GlobalVariable", "ConfigEntry", "Route", "Schema",
        "CONTAINS", "HAS_METHOD", "HAS_CALLSITE", "IMPORTS", "INHERITS", "IMPLEMENTS", "CALLS", "MAY_CALL",
        "REFERENCES", "TESTS", "CONFIGURES")},
    **{name: "G_code" for name in ("Statement", "Identifier", *sorted(G_CODE_EDGE_TYPES))},
    **{name: "G_arch" for name in (
        "Component", "Port", "Connector", "Service", "DeploymentUnit", "ExternalSystem",
        "DEPENDS_ON", "EXPOSES_PORT", "CONSUMES_PORT", "COMMUNICATES_WITH", "CONTAINS_COMPONENT", "DEPLOYS_TO")},
    **{name: "G_task" for name in (
        "Issue", "BugReport", "Requirement", "UserStory", "AcceptanceCriterion", "FailingTest", "ErrorMessage",
        "StackTraceFrame", "Constraint", "Actor", "MENTIONS", "REPRODUCES", "TRACES_TO", "RESOLVES_TO", "CONFLICTS_WITH")},
}
# DEPENDS_ON joins Components (proposal line 264) and Requirements (line 320).
_EXTRA_LAYERS = {"DEPENDS_ON": ["G_arch", "G_task"]}
_PRODUCERS = {
    **{name: "overlay" for name in ("Issue", "BugReport", "AcceptanceCriterion", "FailingTest", "ErrorMessage", "StackTraceFrame")},
    **{name: "builder (tree-sitter-graph)" for name in ("Field", "GlobalVariable", "ConfigEntry", "Route", "Schema")},
    "Identifier": "builder (tree-sitter-graph or joern)",
    "Statement": "builder (joern)",
    **{name: None for name in ("Requirement", "UserStory", "Constraint", "Actor", "Connector", "ExternalSystem")},
}
_COMMON_FIELDS = {
    "node": ["id", "type", "repo_key", "name", "qualified_name", "graph_version", "properties"],
    "edge": ["id", "type", "source_id", "target_id", "confidence", "graph_version", "properties", "provenance"],
}


def schema_description() -> dict[str, Any]:
    """The schema S as plain data, for the ``vgar://repo/schema`` resource; lists are sorted so the output is stable."""
    node_types = {
        name: {"layer": LAYERS[name], "producer": _PRODUCERS.get(name, "builder"),
               "properties": dict(sorted(NODE_PROPERTIES[name].items())), "source_backed": name in SOURCE_BACKED_NODE_TYPES}
        for name in sorted(NODE_TYPES)
    }
    edge_types = {}
    for name in sorted(EDGE_ENDPOINTS):
        entry: dict[str, Any] = {
            "layer": LAYERS[name], "endpoints": [list(pair) for pair in sorted(EDGE_ENDPOINTS[name])],
            "properties": [{"source": source, "target": target, "properties": dict(sorted(rules.items()))}
                           for (edge_type, source, target), rules in sorted(EDGE_PROPERTIES.items()) if edge_type == name],
        }
        if name in _EXTRA_LAYERS:
            entry["layers"] = _EXTRA_LAYERS[name]
        edge_types[name] = entry
    return {"schema_version": SCHEMA_VERSION, "node_types": node_types, "edge_types": edge_types,
            "common": _COMMON_FIELDS, "invariants": [{"name": name, "description": text} for name, text in INVARIANTS]}


def _description_hash(description: Mapping[str, Any]) -> str:
    encoded = json.dumps(description, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class GraphValidationError(ValueError):
    """Raised when a graph document violates the frozen graph contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid graph document:\n- " + "\n- ".join(errors))


def validate_graph_document(
    document: Mapping[str, Any],
    *,
    trusted_ids: frozenset[str] = frozenset(),
) -> None:
    """Validate the portable JSON graph document used by M1 and M3.

    Items whose id is in ``trusted_ids`` (incremental replay of already-validated items) skip the per-item
    field checks; every structural check (ids, types, endpoints, graph_version, cycles, CallSite counts) still runs.
    """

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

        if node.get("graph_version") != graph_version:
            errors.append(f"{prefix}.graph_version must match document graph_version")

        if node_id in trusted_ids:
            continue

        for field in ("repo_key", "name", "qualified_name"):
            if not isinstance(node.get(field), str) or not node[field]:
                errors.append(f"{prefix}.{field} must be a non-empty string")

        if not isinstance(node.get("properties"), Mapping):
            errors.append(f"{prefix}.properties must be an object")
        elif node_type in NODE_PROPERTIES:
            errors.extend(_property_errors(prefix, node_type, node["properties"], NODE_PROPERTIES[node_type]))

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
    ast_parents: dict[str, int] = defaultdict(int)

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
            elif source is not None and target is not None:
                rules = EDGE_PROPERTIES.get((str(edge_type), str(source.get("type")), str(target.get("type"))), {})
                errors.extend(_property_errors(prefix, str(edge_type), edge["properties"], rules))

        if edge_type == "CONTAINS" and source_id and target_id:
            contains_adjacency[source_id].append(target_id)
        if edge_type == "CALLS" and source_id:
            call_counts[source_id] += 1
        if edge_type == "AST_CHILD" and isinstance(target_id, str):
            ast_parents[target_id] += 1

    errors.extend(_containment_cycle_errors(contains_adjacency))
    errors.extend(_reference_errors(nodes_by_id, ast_parents))

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
    """CONTAINS cycles with their path; an explicit stack keeps deep nesting within one linear pass."""
    errors: list[str] = []
    on_path: set[str] = set()
    done: set[str] = set()
    for root in adjacency:
        if root in done:
            continue
        path, children = [root], [iter(adjacency.get(root, []))]
        on_path.add(root)
        while children:
            child = next(children[-1], None)
            if child is None:
                finished = path.pop()
                on_path.discard(finished)
                done.add(finished)
                children.pop()
            elif child in on_path:
                cycle = path[path.index(child):] + [child]
                errors.append("CONTAINS cycle: " + " -> ".join(cycle))
            elif child not in done:
                path.append(child)
                on_path.add(child)
                children.append(iter(adjacency.get(child, [])))
    return errors


def _reference_errors(
    nodes_by_id: Mapping[str, Mapping[str, Any]], ast_parents: Mapping[str, int],
) -> list[str]:
    """The id references of the new layers (Gamma: port_owner, port_symbol, method_owner, failing_test_targets,
    ast_single_parent). A missing or mistyped property is reported by delta, so it is skipped here."""
    errors: list[str] = []

    def type_of(node_id: Any) -> Any:
        target = nodes_by_id.get(node_id) if isinstance(node_id, str) else None
        return target.get("type") if target is not None else None

    for node_id, node in nodes_by_id.items():
        node_type, properties = node.get("type"), node.get("properties")
        if not isinstance(properties, Mapping):
            continue
        if node_type == "Port":
            owner = properties.get("owner_component_id")
            # Only the node reference: a view may drop the EXPOSES_PORT edge and still be a valid document.
            if isinstance(owner, str) and type_of(owner) != "Component":
                errors.append(f"port_owner: Port {node_id!r} names {owner!r}, which is not a Component")
            symbol = properties.get("symbol_id")
            if isinstance(symbol, str) and symbol not in nodes_by_id:
                errors.append(f"port_symbol: Port {node_id!r} names missing symbol {symbol!r}")
        elif node_type == "Method":
            owner = properties.get("owner_class_id")
            if isinstance(owner, str) and type_of(owner) != "Class":
                errors.append(f"method_owner: Method {node_id!r} names {owner!r}, which is not a Class")
        elif node_type == "FailingTest":
            targets = properties.get("test_node_ids")
            for target in targets if isinstance(targets, list) else []:
                if type_of(target) != "Test":
                    errors.append(f"failing_test_targets: FailingTest {node_id!r} names {target!r}, which is not a Test")
    for target, count in ast_parents.items():
        if count > 1:
            errors.append(f"ast_single_parent: {target!r} has {count} incoming AST_CHILD edges")
    return errors


# Fingerprint of S: changes with any type, rule or invariant, not with comments or formatting.
SCHEMA_HASH = _description_hash(schema_description())