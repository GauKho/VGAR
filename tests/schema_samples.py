"""A minimal valid graph document built from the schema S itself (SC-1).

One node per node type and one edge per edge type, so a test can break exactly one rule at a time.
"""
from __future__ import annotations

import copy
from typing import Any

from vgar.contracts.schema import (
    EDGE_ENDPOINTS,
    EDGE_PROPERTIES,
    NODE_PROPERTIES,
    NODE_TYPES,
    SOURCE_BACKED_NODE_TYPES,
)

GRAPH_VERSION = "sha256:sample"
SAMPLE_VALUES = {"string": "x", "integer": 1, "number": 1.0, "boolean": True, "array": [], "object": {}, "positive_integer": 1}
# A value of another JSON type than the one the rule asks for.
WRONG_VALUES = {"string": 1, "integer": True, "number": "1", "boolean": 1, "array": "x", "object": [], "positive_integer": 0}
# Edges whose endpoints the invariants need fixed.
FIXED_ENDPOINTS = {"AST_CHILD": ("Function", "Statement"), "DEPENDS_ON": ("Component", "Component"), "TRACES_TO": ("Issue", "Component")}
REFERENCES = {
    "Port": {"owner_component_id": "n:Component", "symbol_id": "n:Function"},
    "Method": {"owner_class_id": "n:Class"},
    "FailingTest": {"test_node_ids": ["n:Test"]},
}
RANGE = {"start_line": 1, "start_col": 0, "end_line": 1, "end_col": 1, "start_byte": 0, "end_byte": 1}


def sample_value(kind: str) -> Any:
    """A valid value for one property rule, using the first non-null alternative.

    Args:
        kind: A rule such as ``string`` or ``string|null``.
    """
    return copy.deepcopy(SAMPLE_VALUES[next(part for part in kind.split("|") if part != "null")])


def wrong_value(kind: str) -> Any:
    """A value that breaks one property rule.

    Args:
        kind: A rule such as ``string`` or ``string|null``.
    """
    return WRONG_VALUES[next(part for part in kind.split("|") if part != "null")]


def node(node_type: str, node_id: str | None = None) -> dict[str, Any]:
    """A valid node of one type with every required property.

    Args:
        node_type: The node type.
        node_id: Its id; ``n:<type>`` when omitted.
    """
    properties = {key: sample_value(kind) for key, kind in NODE_PROPERTIES[node_type].items()}
    properties.update(copy.deepcopy(REFERENCES.get(node_type, {})))
    if node_type == "Module":
        properties["is_external"] = False
    if node_type == "CallSite":
        properties["candidate_count"] = 1
    result = {"id": node_id or f"n:{node_type}", "type": node_type, "repo_key": "t/sample", "name": node_type,
              "qualified_name": f"sample.{node_type}", "path": None, "range": None, "graph_version": GRAPH_VERSION,
              "properties": properties}
    if node_type in SOURCE_BACKED_NODE_TYPES or node_type == "Module":
        result.update(path="sample.py", range=dict(RANGE))
    return result


def endpoints(edge_type: str) -> tuple[str, str]:
    """The endpoint types used for one edge type: a fixed pair, else the first sorted pair of two different types."""
    if edge_type in FIXED_ENDPOINTS:
        return FIXED_ENDPOINTS[edge_type]
    pairs = sorted(EDGE_ENDPOINTS[edge_type])
    return next((pair for pair in pairs if pair[0] != pair[1]), pairs[0])


def edge(edge_type: str, source_id: str, target_id: str, source_type: str, target_type: str) -> dict[str, Any]:
    """A valid edge with every required property.

    Args:
        edge_type: The edge type.
        source_id: Id of the source node.
        target_id: Id of the target node.
        source_type: Type of the source node.
        target_type: Type of the target node.
    """
    properties = {key: sample_value(kind) for key, kind in EDGE_PROPERTIES.get((edge_type, source_type, target_type), {}).items()}
    provenance: dict[str, Any] = {"source_tool": "sample", "rule_id": f"sample.{edge_type.lower()}", "source_revision": "rev"}
    if edge_type == "MAY_CALL":
        provenance["evidence"] = ["name_match"]
    return {"id": f"e:{edge_type}", "type": edge_type, "source_id": source_id, "target_id": target_id,
            "confidence": 0.3 if edge_type == "MAY_CALL" else 1.0, "graph_version": GRAPH_VERSION,
            "properties": properties, "provenance": provenance}


def minimal_document() -> dict[str, Any]:
    """A valid document with every node type and every edge type exactly once (plus a second node where an edge needs one)."""
    nodes = {node_type: node(node_type) for node_type in sorted(NODE_TYPES)}
    extra: dict[str, dict[str, Any]] = {}
    edges = []
    for edge_type in sorted(EDGE_ENDPOINTS):
        source_type, target_type = endpoints(edge_type)
        target_id = f"n:{target_type}"
        if source_type == target_type:
            target_id = f"n:{target_type}:2"
            extra.setdefault(target_id, node(target_type, target_id))
        edges.append(edge(edge_type, f"n:{source_type}", target_id, source_type, target_type))
    return {"repo_key": "t/sample", "repository_revision": "rev", "graph_version": GRAPH_VERSION,
            "nodes": [*nodes.values(), *extra.values()], "edges": edges}
