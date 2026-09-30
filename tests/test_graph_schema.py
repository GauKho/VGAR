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


if __name__ == "__main__":
    unittest.main()
