from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from vgar.contracts.schema import GraphValidationError, validate_graph_document


FIXTURE = Path(__file__).parent / "fixtures" / "graph_contract_fixture.json"


class GraphSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_contract_fixture_is_valid(self) -> None:
        validate_graph_document(self.document)

    def test_public_schema_version_is_not_required(self) -> None:
        self.assertNotIn("schema_version", self.document)
        validate_graph_document(self.document)

    def test_missing_endpoint_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.document)
        invalid["edges"][-1]["target_id"] = "missing:symbol"

        with self.assertRaises(GraphValidationError):
            validate_graph_document(invalid)

    def test_callsite_candidate_count_must_match_calls(self) -> None:
        invalid = copy.deepcopy(self.document)
        callsite = next(
            node for node in invalid["nodes"] if node["type"] == "CallSite"
        )
        callsite["properties"]["candidate_count"] = 2

        with self.assertRaises(GraphValidationError):
            validate_graph_document(invalid)

    def _first(self, kind: str) -> dict:
        return next(node for node in self.document["nodes"] if node["type"] == kind)

    def test_trusted_node_skips_field_checks(self) -> None:
        # Incremental Task 1: items replayed from cache skip per-item field checks.
        node = self._first("Function")
        node["name"] = ""

        validate_graph_document(self.document, trusted_ids=frozenset({node["id"]}))
        with self.assertRaisesRegex(GraphValidationError, r"\.name must be a non-empty string"):
            validate_graph_document(self.document)

    def test_trusted_edge_to_missing_node_still_fails(self) -> None:
        # Structural checks run for trusted items too: a dangling edge is caught.
        edge = self.document["edges"][-1]
        edge["target_id"] = "missing:symbol"

        with self.assertRaisesRegex(GraphValidationError, "target_id does not exist"):
            validate_graph_document(self.document, trusted_ids=frozenset({edge["id"]}))

    def test_trusted_items_still_need_matching_graph_version(self) -> None:
        node = self._first("Function")
        node["graph_version"] = "sha256:other"

        with self.assertRaisesRegex(GraphValidationError, "graph_version must match"):
            validate_graph_document(self.document, trusted_ids=frozenset({node["id"]}))


if __name__ == "__main__":
    unittest.main()
