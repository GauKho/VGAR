"""Guide rules for STDIO servers: nothing but JSON-RPC on stdout (spec §9; build-server guide)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_fixture import fixture_service
from vgar.contracts.schema import validate_graph_document
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server

ROOT = Path(__file__).resolve().parents[2]
LOGIN_REPO = ROOT / "tests" / "fixtures" / "w7_w8_handoff" / "single_file_login" / "repo"
REF = (ROOT / "tests" / "fixtures" / "m2" / "reference_patches" / "single_file_login.diff").read_text(encoding="utf-8")


def test_new_modules_never_print():
    for path in ("src/vgar/repair/patch_evidence.py", "src/vgar/graph/sqlite_service.py", "src/vgar/graph/factory.py",
                 "src/vgar/mcp/tooling.py", "src/vgar/mcp/logging_setup.py", "src/vgar/mcp/server_factory.py",
                 "src/vgar/mcp/servers/graph_server.py", "src/vgar/mcp/servers/execution_server.py",
                 "src/vgar/mcp/servers/repository_server.py"):
        assert "print(" not in (ROOT / path).read_text(encoding="utf-8"), path


def test_fixture_graph_passes_schema_validation(tmp_path):
    service = fixture_service(tmp_path / "graph")
    validate_graph_document(service._document(service.get_repository_summary().graph_version))


@pytest.fixture
def served(tmp_path, monkeypatch):
    def use(repo=None):
        service = fixture_service(tmp_path / f"graph-{len(list(tmp_path.iterdir()))}", **({"repo": repo} if repo else {}))
        monkeypatch.setattr(graph_server, "graph_service", service)
        monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
        version = service.get_repository_summary().graph_version
        return {node["qualified_name"]: node["id"] for node in service._document(version)["nodes"]
                if node["type"] in {"Function", "Method", "Class", "Test"}}
    return use


def test_guide_tools_write_nothing_to_stdout_and_report_the_real_backend(served, capsys):
    ids = served()
    responses = [graph_server.get_callers(ids["app.parser.normalize"], depth=2),
                 graph_server.explain_dependency_path(ids["app.service.login"], ids["db.store.save_user"])]
    for uri in ("vgar://repo/schema", "vgar://component/app", "vgar://evidence/baseline"):
        json.loads(graph_server._read_resource(uri))
    served(LOGIN_REPO)
    import asyncio
    responses.append(asyncio.run(graph_server.verify_patch_graph_constraints(REF)))
    assert capsys.readouterr().out == ""
    assert all(response["status"] == "PASS" for response in responses), responses
    assert all(response["metadata"]["backend"] == "sqlite" for response in responses)
