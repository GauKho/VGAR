"""The new surface adds tools; it must retain every legacy tool and signature."""
import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEW = {
    "graph": {"build_or_update_graph", "explain_dependency_path", "verify_patch_graph_constraints", "rank_patch_candidates"},
    "execution": {"run_relevant_tests"},
}


def test_core_inventory_adds_five_without_removing_legacy():
    oracle = json.loads((ROOT / "tests/fixtures/mcp_server/expected_contract.json").read_text(encoding="utf-8"))
    total = 0
    for server in ("graph", "repository", "execution", "repair"):
        tree = ast.parse((ROOT / f"src/vgar/mcp/servers/{server}_server.py").read_text(encoding="utf-8"))
        names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool" for d in n.decorator_list)}
        legacy = {x["name"] for x in oracle["legacy_surface"] if x["server"] == server}
        assert names == legacy | NEW.get(server, set())
        total += len(names)
    assert total == 20


def test_depth_one_payload_is_legacy_but_depth_two_cannot_lie(monkeypatch, tmp_path):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import graph_server as graph
    monkeypatch.setattr(graph, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    symbol = graph.search_symbols("login")["data"]["symbols"][0]["symbol_id"]
    for name, key in (("get_callers", "callers"), ("get_callees", "callees")):
        method = getattr(graph, name)
        direct = method(symbol)
        assert direct["status"] == "PASS" and set(direct["data"]) == {"symbol_id", "depth", key}
        multi = method(symbol, depth=2)  # spec §7.2: served by graph_service when no traversal provider
        assert multi["status"] == "PASS" and {"symbol_id", "depth", key, "may_call", "truncated"} == set(multi["data"])
        assert all(item["hop"] in {1, 2} for item in multi["data"][key])
        assert method(symbol, depth=True)["status"] == "ERROR"


def test_bound_legacy_queries_reject_actual_backend_snapshot_mismatch(bound, monkeypatch):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.context import request_scope
    from vgar.mcp.servers import graph_server as graph
    _, ctx = bound
    monkeypatch.setattr(graph, "_audit_logger", AuditLogger(ctx.output_root / "audit.jsonl"))
    with request_scope(ctx):
        response = graph.search_symbols("login")
    assert response["status"] == "ERROR", "Must not answer from an unrelated demo/backend snapshot"


def test_multihop_uses_host_context_factory(bound, monkeypatch):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal import contracts as c
    from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    from vgar.mcp.servers import graph_server as graph
    _, ctx = bound
    class Provider:
        def traverse(self, request, context):
            assert context is ctx and request.depth == 2
            return c.TraversalResult(binding=c.SnapshotBinding.from_context(context), examined_edges=0)
    record = ProviderBinding(Provider(), c.SnapshotBinding.from_context(ctx), frozenset({"traversal"}), synthetic=True)
    tools = CoreTools(ProviderRegistry((record,), test_only=True), context_factory=lambda op, req: ctx)
    monkeypatch.setattr(graph, "core_tools", tools)
    monkeypatch.setattr(graph, "_audit_logger", AuditLogger(ctx.output_root / "audit.jsonl"))
    result = graph.get_callers("a", depth=2)
    assert result["status"] == "PASS" and result["data"]["callers"] == []


def test_legacy_queries_honor_configured_host_context_factory(bound, monkeypatch):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    from vgar.mcp.servers import graph_server as graph
    _, ctx = bound
    calls = []
    def context_factory(operation, request):
        calls.append(operation)
        return ctx
    monkeypatch.setattr(graph, "core_tools", CoreTools(ProviderRegistry(), context_factory=context_factory))
    monkeypatch.setattr(graph, "_audit_logger", AuditLogger(ctx.output_root / "audit.jsonl"))
    result = graph.search_symbols("login")
    assert calls == ["search_symbols"]
    assert result["status"] == "ERROR" and result["metadata"]["task_id"] == ctx.task_id


@pytest.mark.parametrize("server", ["graph", "execution"])
def test_production_main_refuses_synthetic_registry(bound, server, monkeypatch):
    import importlib

    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools
    module = importlib.import_module("vgar.mcp.servers." + server + "_server")
    monkeypatch.setattr(module, "core_tools", CoreTools(ProviderRegistry(test_only=True)))
    monkeypatch.setattr(module.mcp, "run", lambda **kwargs: pytest.fail("Must not start production with synthetic registry"))
    with pytest.raises(ValueError, match="Synthetic"):
        module.main()


def test_core_dto_schemas_are_closed_and_have_binding():
    from vgar.mcp.proposal import contracts as c
    for name in ("BuildRequest", "PathRequest", "DiffRequest", "RankRequest", "BuildResult", "PathResult", "TraversalResult",
                 "CheckEvidence", "TestEvidence", "RankResult"):
        schema = getattr(c, name).model_json_schema()
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        if name.endswith(("Result", "Evidence")):
            assert "binding" in schema["required"]


def test_bound_legacy_store_must_pin_version_not_select_latest(bound, monkeypatch):
    from types import SimpleNamespace

    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.context import request_scope
    from vgar.mcp.servers import graph_server as graph
    _, ctx = bound
    class Backend:
        backend_name = "sqlite"
        store = SimpleNamespace(requested_graph_version=None)
        def get_repository_summary(self): return SimpleNamespace(graph_version=ctx.snapshot_hash)
        def search_symbols(self, **kwargs):
            return SimpleNamespace(query="login", symbols=[])
    monkeypatch.setattr(graph, "graph_service", Backend())
    monkeypatch.setattr(graph, "_audit_logger", AuditLogger(ctx.output_root / "audit.jsonl"))
    with request_scope(ctx):
        response = graph.search_symbols("login")
    assert response["status"] == "ERROR", "Bound query must not use latest-version store"
