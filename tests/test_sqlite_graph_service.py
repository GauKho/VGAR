from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.contracts.error import InvalidLimitError, InvalidQueryError, NodeNotFoundError


FIXTURE = Path(__file__).parent / "fixtures" / "graph_contract_fixture.json"
CONTRACT_FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
LOGIN_ID = "vgar:demo/vgar-fixture:python:function:src/auth/service.py:login"
HANDLER_ID = (
    "vgar:demo/vgar-fixture:python:function:src/web/routes.py:login_handler"
)


class SQLiteGraphServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "graph.db"
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        store = SQLiteGraphStore(database_path)
        store.ingest(document)
        self.service = SQLiteGraphService(store)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_search_symbols_matches_m3_contract(self) -> None:
        result = self.service.search_symbols("login", limit=10)

        self.assertEqual(result.query, "login")
        self.assertEqual(
            [symbol.symbol_id for symbol in result.symbols],
            [LOGIN_ID, HANDLER_ID],
        )
        self.assertEqual(result.symbols[0].kind, "function")
        self.assertEqual(result.symbols[0].path, "src/auth/service.py")

    def test_get_callers_matches_m3_contract(self) -> None:
        result = self.service.get_callers(LOGIN_ID)

        self.assertEqual(result.symbol_id, LOGIN_ID)
        self.assertEqual(
            [symbol.symbol_id for symbol in result.symbols],
            [HANDLER_ID],
        )

    def test_get_callees_matches_m3_contract(self) -> None:
        result = self.service.get_callees(HANDLER_ID)

        self.assertEqual(result.symbol_id, HANDLER_ID)
        self.assertEqual(
            [symbol.symbol_id for symbol in result.symbols],
            [LOGIN_ID],
        )

    def test_unknown_symbol_matches_demo_service_behavior(self) -> None:
        with self.assertRaises(NodeNotFoundError) as raised:
            self.service.get_callers("missing:symbol")
        self.assertIsInstance(raised.exception, KeyError)
        self.assertEqual(raised.exception.to_dict()["code"], "NODE_NOT_FOUND")

    def test_query_validation_has_stable_error_codes(self) -> None:
        with self.assertRaises(InvalidQueryError) as empty_query:
            self.service.search_symbols("   ")
        self.assertEqual(empty_query.exception.code, "INVALID_QUERY")

        with self.assertRaises(InvalidLimitError) as invalid_limit:
            self.service.search_symbols("login", limit=101)
        self.assertEqual(invalid_limit.exception.code, "INVALID_LIMIT")

    def test_relation_confidence_threshold_is_configurable_in_store(self) -> None:
        self.assertEqual(self.service.store.get_callers(LOGIN_ID, min_confidence=0.96), [])

        with self.assertRaises(ValueError):
            self.service.store.get_callers(LOGIN_ID, min_confidence=1.1)

    def test_get_node_returns_range_and_properties(self) -> None:
        node = self.service.store.get_node(LOGIN_ID)

        self.assertEqual(node.qualified_name, "auth.service.login")
        self.assertEqual(node.path, "src/auth/service.py")
        self.assertEqual(node.start_line, 1)
        self.assertIn("signature", node.properties)

    def test_get_importers_rejects_non_module(self) -> None:
        with self.assertRaises(ValueError):
            self.service.get_importers(LOGIN_ID)

    def test_success_results_match_frozen_json_fixtures(self) -> None:
        cases = (
            (
                self.service.search_symbols("login", limit=10),
                "search_symbols_success.json",
            ),
            (self.service.get_callers(LOGIN_ID), "get_callers_success.json"),
            (self.service.get_callees(HANDLER_ID), "get_callees_success.json"),
        )

        for result, filename in cases:
            expected = json.loads(
                (CONTRACT_FIXTURES / filename).read_text(encoding="utf-8")
            )
            self.assertEqual(result.model_dump(), expected)

    def test_error_result_matches_frozen_json_fixture(self) -> None:
        expected = json.loads(
            (CONTRACT_FIXTURES / "unknown_symbol_error.json").read_text(
                encoding="utf-8"
            )
        )

        with self.assertRaises(NodeNotFoundError) as raised:
            self.service.get_callers("missing:symbol")

        self.assertEqual(raised.exception.to_dict(), expected)


if __name__ == "__main__":
    unittest.main()
