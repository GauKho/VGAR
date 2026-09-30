from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore


SAMPLE_REPOSITORY = Path(__file__).parent / "fixtures" / "sample_repo"
LOGIN_ID = "vgar:demo/vgar-fixture:python:function:src/auth/service.py:auth.service.login"
HANDLER_ID = "vgar:demo/vgar-fixture:python:function:src/web/routes.py:web.routes.login_handler"
TEST_LOGIN_ID = "vgar:demo/vgar-fixture:python:test:tests/test_auth.py:tests.test_auth.test_login"
AUTH_MODULE_ID = "vgar:demo/vgar-fixture:python:module:src/auth/service.py:auth.service"
WEB_MODULE_ID = "vgar:demo/vgar-fixture:python:module:src/web/routes.py:web.routes"
TEST_MODULE_ID = "vgar:demo/vgar-fixture:python:module:tests/test_auth.py:tests.test_auth"


class EndToEndGraphPipelineTests(unittest.TestCase):
    def test_source_to_sqlite_to_m3_contract(self) -> None:
        document = PythonGraphBuilder(
            repo_key="demo/vgar-fixture",
            repository_revision="fixture-revision",
        ).build(SAMPLE_REPOSITORY)

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteGraphStore(Path(directory) / "graph.db")
            store.ingest(document)
            service = SQLiteGraphService(store)

            search = service.search_symbols("login", limit=10)
            callers = service.get_callers(LOGIN_ID)
            callees = service.get_callees(HANDLER_ID)
            importers = service.get_importers(AUTH_MODULE_ID)

        self.assertEqual(
            [symbol.symbol_id for symbol in search.symbols],
            [LOGIN_ID, TEST_LOGIN_ID, HANDLER_ID],
        )
        self.assertEqual(
            [symbol.symbol_id for symbol in callers.symbols],
            [TEST_LOGIN_ID, HANDLER_ID],
        )
        self.assertEqual(
            [symbol.symbol_id for symbol in callees.symbols],
            [LOGIN_ID],
        )
        self.assertEqual(
            [symbol.symbol_id for symbol in importers.symbols],
            [TEST_MODULE_ID, WEB_MODULE_ID],
        )


if __name__ == "__main__":
    unittest.main()
