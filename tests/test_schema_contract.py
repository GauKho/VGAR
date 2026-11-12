"""SC-1: the schema S = (TN, TE, beta, delta, Gamma) and its validator.

Every rule is checked by breaking it once in a minimal valid document built from S.
Spec: docs/superpowers/specs/2026-11-10-tv2-sc-1-schema-design.md
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from schema_samples import minimal_document, node, wrong_value

from vgar.contracts.schema import (
    EDGE_ENDPOINTS,
    EDGE_PROPERTIES,
    INVARIANTS,
    NODE_PROPERTIES,
    NODE_TYPES,
    SCHEMA_HASH,
    SCHEMA_VERSION,
    GraphValidationError,
    schema_description,
    validate_graph_document,
)
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.task_overlay import TaskOverlayBuilder


def _node(document: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(item for item in document["nodes"] if item["id"] == node_id)


def _rejected(document: dict[str, Any], *fragments: str) -> None:
    with pytest.raises(GraphValidationError) as raised:
        validate_graph_document(document)
    message = str(raised.value)
    assert all(fragment in message for fragment in fragments), message


def _node_keys() -> list[tuple[str, str]]:
    return [(node_type, key) for node_type in sorted(NODE_PROPERTIES) for key in sorted(NODE_PROPERTIES[node_type])]


def test_minimal_document_covers_every_type() -> None:
    document = minimal_document()
    assert {item["type"] for item in document["nodes"]} == NODE_TYPES
    assert {item["type"] for item in document["edges"]} == set(EDGE_ENDPOINTS)
    validate_graph_document(document)


def test_node_properties_cover_every_node_type() -> None:
    assert set(NODE_PROPERTIES) == NODE_TYPES


@pytest.mark.parametrize(("node_type", "key"), _node_keys())
def test_missing_node_property_is_rejected(node_type: str, key: str) -> None:
    document = minimal_document()
    del _node(document, f"n:{node_type}")["properties"][key]
    _rejected(document, f"properties.{key} is required for {node_type}")


@pytest.mark.parametrize(("node_type", "key"), _node_keys())
def test_wrong_type_node_property_is_rejected(node_type: str, key: str) -> None:
    document = minimal_document()
    _node(document, f"n:{node_type}")["properties"][key] = wrong_value(NODE_PROPERTIES[node_type][key])
    _rejected(document, f"properties.{key} must be {NODE_PROPERTIES[node_type][key]} for {node_type}")


def test_nullable_property_accepts_null() -> None:
    document = minimal_document()
    _node(document, "n:Import")["properties"]["imported_name"] = None
    _node(document, "n:StackTraceFrame")["properties"]["function"] = None
    validate_graph_document(document)


@pytest.mark.parametrize("rule", sorted(EDGE_PROPERTIES))
def test_missing_or_bad_edge_property_is_rejected(rule: tuple[str, str, str]) -> None:
    edge_type = rule[0]
    for key, kind in EDGE_PROPERTIES[rule].items():
        document = minimal_document()
        edge = next(item for item in document["edges"] if item["type"] == edge_type)
        del edge["properties"][key]
        _rejected(document, f"properties.{key} is required for {edge_type}")
        for bad in (wrong_value(kind), True, "1"):
            document = minimal_document()
            next(item for item in document["edges"] if item["type"] == edge_type)["properties"][key] = bad
            _rejected(document, f"properties.{key} must be {kind} for {edge_type}")


def test_trusted_ids_skip_property_checks() -> None:
    document = minimal_document()
    del _node(document, "n:File")["properties"]["parse_status"]
    validate_graph_document(document, trusted_ids=frozenset({"n:File"}))


def _edge(document: dict[str, Any], edge_type: str) -> dict[str, Any]:
    return next(item for item in document["edges"] if item["type"] == edge_type)


def _break_port_owner(document: dict[str, Any]) -> None:
    _node(document, "n:Port")["properties"]["owner_component_id"] = "n:Missing"


def _break_port_owner_type(document: dict[str, Any]) -> None:
    _node(document, "n:Port")["properties"]["owner_component_id"] = "n:Function"


def _break_port_symbol(document: dict[str, Any]) -> None:
    _node(document, "n:Port")["properties"]["symbol_id"] = "n:Missing"


def _break_method_owner(document: dict[str, Any]) -> None:
    _node(document, "n:Method")["properties"]["owner_class_id"] = "n:Function"


def _break_failing_test_targets(document: dict[str, Any]) -> None:
    _node(document, "n:FailingTest")["properties"]["test_node_ids"] = ["n:Test", "n:Function"]


def _break_ast_single_parent(document: dict[str, Any]) -> None:
    second = copy.deepcopy(_edge(document, "AST_CHILD"))
    second.update(id="e:AST_CHILD:2", source_id="n:Method")
    document["edges"].append(second)


def _break_single_repository(document: dict[str, Any]) -> None:
    document["nodes"].append({**copy.deepcopy(_node(document, "n:Repository")), "id": "n:Repository:2"})


def _break_unique_node_ids(document: dict[str, Any]) -> None:
    document["nodes"].append(copy.deepcopy(_node(document, "n:Function")))


def _break_unique_edge_ids(document: dict[str, Any]) -> None:
    document["edges"].append(copy.deepcopy(_edge(document, "IMPORTS")))


def _break_same_graph_version(document: dict[str, Any]) -> None:
    _node(document, "n:Function")["graph_version"] = "sha256:other"


def _break_endpoints_exist(document: dict[str, Any]) -> None:
    _edge(document, "IMPORTS")["target_id"] = "n:Missing"


def _break_no_self_loop(document: dict[str, Any]) -> None:
    _edge(document, "INHERITS")["target_id"] = "n:Class"


def _break_contains_acyclic(document: dict[str, Any]) -> None:
    # Class -> Class is an allowed CONTAINS pair, so two such edges make a cycle without any other error.
    first, second = copy.deepcopy(_edge(document, "CONTAINS")), copy.deepcopy(_edge(document, "CONTAINS"))
    first.update(id="e:cycle:1", source_id="n:Class", target_id="n:Class:2")
    second.update(id="e:cycle:2", source_id="n:Class:2", target_id="n:Class")
    document["edges"] += [first, second]


def _break_callsite_candidate_count(document: dict[str, Any]) -> None:
    _node(document, "n:CallSite")["properties"]["candidate_count"] = 2


def _break_may_call_bounded(document: dict[str, Any]) -> None:
    _edge(document, "MAY_CALL")["confidence"] = 0.9


INVARIANT_MUTANTS = {
    "port_owner": [(_break_port_owner, "port_owner"), (_break_port_owner_type, "port_owner")],
    "port_symbol": [(_break_port_symbol, "port_symbol")],
    "method_owner": [(_break_method_owner, "method_owner")],
    "failing_test_targets": [(_break_failing_test_targets, "failing_test_targets")],
    "ast_single_parent": [(_break_ast_single_parent, "ast_single_parent")],
    "single_repository": [(_break_single_repository, "exactly one Repository node is required")],
    "unique_node_ids": [(_break_unique_node_ids, "duplicate node id")],
    "unique_edge_ids": [(_break_unique_edge_ids, "duplicate edge id")],
    "same_graph_version": [(_break_same_graph_version, "graph_version must match document graph_version")],
    "endpoints_exist": [(_break_endpoints_exist, "target_id does not exist")],
    "no_self_loop": [(_break_no_self_loop, "must not be a self-loop")],
    "contains_acyclic": [(_break_contains_acyclic, "CONTAINS cycle: ")],
    "callsite_candidate_count": [(_break_callsite_candidate_count, "candidate_count=2")],
    "may_call_bounded": [(_break_may_call_bounded, "must be at most 0.50 for MAY_CALL")],
}


@pytest.mark.parametrize("name", ["port_owner", "port_symbol", "method_owner", "failing_test_targets", "ast_single_parent"])
def test_new_invariant_is_enforced(name: str) -> None:
    for mutate, fragment in INVARIANT_MUTANTS[name]:
        document = minimal_document()
        mutate(document)
        _rejected(document, fragment)


def _disallowed_target(edge_type: str, source_type: str) -> str:
    return next(node_type for node_type in sorted(NODE_TYPES) if (source_type, node_type) not in EDGE_ENDPOINTS[edge_type])


@pytest.mark.parametrize("edge_type", sorted(EDGE_ENDPOINTS))
def test_wrong_endpoint_is_rejected(edge_type: str) -> None:
    document = minimal_document()
    edge = _edge(document, edge_type)
    source_type = _node(document, edge["source_id"])["type"]
    edge["target_id"] = f"n:{_disallowed_target(edge_type, source_type)}"
    _rejected(document, f"invalid endpoints for {edge_type}")


@pytest.mark.parametrize("name", [name for name, _ in INVARIANTS])
def test_every_invariant_has_a_mutant(name: str) -> None:
    assert name in INVARIANT_MUTANTS
    for mutate, fragment in INVARIANT_MUTANTS[name]:
        document = minimal_document()
        mutate(document)
        _rejected(document, fragment)


def _all_mutants() -> list[dict[str, Any]]:
    mutants = []
    for node_type, key in _node_keys():
        missing = minimal_document()
        del _node(missing, f"n:{node_type}")["properties"][key]
        wrong = minimal_document()
        _node(wrong, f"n:{node_type}")["properties"][key] = wrong_value(NODE_PROPERTIES[node_type][key])
        mutants += [missing, wrong]
    for edge_type in sorted(EDGE_ENDPOINTS):
        document = minimal_document()
        edge = _edge(document, edge_type)
        edge["target_id"] = f"n:{_disallowed_target(edge_type, _node(document, edge['source_id'])['type'])}"
        mutants.append(document)
    for cases in INVARIANT_MUTANTS.values():
        for mutate, _ in cases:
            document = minimal_document()
            mutate(document)
            mutants.append(document)
    return mutants


def test_mutation_score_is_complete() -> None:
    mutants = _all_mutants()
    killed = 0
    for document in mutants:
        try:
            validate_graph_document(document)
        except GraphValidationError:
            killed += 1
    assert len(mutants) > 100 and killed == len(mutants)


def _class_chain(depth: int) -> dict[str, Any]:
    document = minimal_document()
    previous = "n:Class"
    for level in range(depth):
        node_id = f"n:chain:{level}"
        document["nodes"].append(node("Class", node_id))
        edge = copy.deepcopy(_edge(document, "INHERITS"))
        edge.update(id=f"e:chain:{level}", type="CONTAINS", source_id=previous, target_id=node_id)
        document["edges"].append(edge)
        previous = node_id
    return document


def test_deep_contains_chain_is_accepted() -> None:
    validate_graph_document(_class_chain(5000))


def test_contains_cycle_reports_its_path() -> None:
    document = _class_chain(3000)
    for index, (source, target) in enumerate([("n:a", "n:b"), ("n:b", "n:c"), ("n:c", "n:a"), ("n:chain:2999", "n:a")]):
        for node_id in (source, target):
            if not any(item["id"] == node_id for item in document["nodes"]):
                document["nodes"].append(node("Class", node_id))
        edge = copy.deepcopy(_edge(document, "INHERITS"))
        edge.update(id=f"e:loop:{index}", type="CONTAINS", source_id=source, target_id=target)
        document["edges"].append(edge)
    _rejected(document, "CONTAINS cycle: n:a -> n:b -> n:c -> n:a")


def test_overlay_failing_test_points_into_base_graph() -> None:
    cases = Path(__file__).parent / "fixtures" / "vgar-arch-cases" / "multi_package"
    document = PythonGraphBuilder(repo_key="t/arch", repository_revision="rev").build(cases)
    overlay = TaskOverlayBuilder(document).build("t1", "x", ["tests/test_service.py::test_login"])
    failing = next(item for item in overlay.nodes if item["type"] == "FailingTest")
    assert failing["properties"]["test_node_ids"]
    validate_graph_document({**document, "nodes": document["nodes"] + overlay.nodes, "edges": document["edges"] + overlay.edges})


def test_document_without_edges_keeps_valid_ports() -> None:
    # A view that drops edges (a subgraph, or the BM25 check that strips every edge) still names real owners.
    document = minimal_document()
    document["edges"] = [item for item in document["edges"] if item["type"] != "EXPOSES_PORT"]
    validate_graph_document(document)


def test_gamma_runs_for_trusted_ids() -> None:
    document = minimal_document()
    _break_port_owner(document)
    with pytest.raises(GraphValidationError, match="port_owner"):
        validate_graph_document(document, trusted_ids=frozenset({"n:Port"}))


LAYER_NAMES = {"G_repo", "G_code", "G_arch", "G_task"}
NO_PRODUCER = {"Requirement", "UserStory", "Constraint", "Actor", "Connector", "ExternalSystem"}


def _hash(description: dict[str, Any]) -> str:
    encoded = json.dumps(description, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_description_lists_every_type() -> None:
    description = schema_description()
    assert set(description["node_types"]) == NODE_TYPES and set(description["edge_types"]) == set(EDGE_ENDPOINTS)
    assert {entry["layer"] for entry in [*description["node_types"].values(), *description["edge_types"].values()]} <= LAYER_NAMES
    assert description["edge_types"]["DEPENDS_ON"]["layers"] == ["G_arch", "G_task"]
    assert description["node_types"]["Port"]["properties"] == NODE_PROPERTIES["Port"]
    assert [item["name"] for item in description["invariants"]] == [name for name, _ in INVARIANTS]
    assert description["schema_version"] == SCHEMA_VERSION


def test_description_marks_types_without_producer() -> None:
    node_types = schema_description()["node_types"]
    assert {name for name, entry in node_types.items() if entry["producer"] is None} == NO_PRODUCER
    assert node_types["Port"]["producer"] == "builder" and node_types["StackTraceFrame"]["producer"] == "overlay"


def test_description_is_json_round_trip() -> None:
    description = schema_description()
    assert json.loads(json.dumps(description)) == description
    endpoints = description["edge_types"]["CALLS"]["endpoints"]
    assert endpoints == sorted(endpoints) and all(isinstance(pair, list) for pair in endpoints)
    assert description["edge_types"]["DEPENDS_ON"]["properties"] == [
        {"source": "Component", "target": "Component", "properties": {"weight": "positive_integer"}}]


def test_schema_hash_is_stable() -> None:
    assert SCHEMA_HASH.startswith("sha256:") and SCHEMA_HASH == _hash(schema_description())


def test_schema_hash_changes_with_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    before = _hash(schema_description())
    monkeypatch.setitem(NODE_PROPERTIES["Port"], "extra", "string")
    assert _hash(schema_description()) != before


def test_external_module_still_needs_module_keys() -> None:
    document = minimal_document()
    module = _node(document, "n:Module")
    module["properties"]["is_external"] = True
    module.update(path=None, range=None)
    validate_graph_document(document)
    broken = copy.deepcopy(document)
    del _node(broken, "n:Module")["properties"]["module_name"]
    _rejected(broken, "properties.module_name is required for Module")


def test_description_is_a_fresh_copy_each_call() -> None:
    first = schema_description()
    first["common"]["node"].append("extra")
    first["edge_types"]["DEPENDS_ON"]["layers"].append("G_other")
    first["node_types"]["Port"]["properties"]["extra"] = "string"
    second = schema_description()
    assert "extra" not in second["common"]["node"] and second["edge_types"]["DEPENDS_ON"]["layers"] == ["G_arch", "G_task"]
    assert "extra" not in second["node_types"]["Port"]["properties"] and _hash(second) == SCHEMA_HASH
