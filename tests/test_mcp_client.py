from vgar.mcp.servers.graph_server import get_callees, get_callers, search_symbols


def test_graph_search_uses_configured_graph_service():
    result = search_symbols("auth")
    assert result["status"] == "PASS"
    assert result["metadata"]["backend"] in {"demo", "sqlite"}
    assert result["data"]["symbols"]


def test_graph_relation_tools_return_stable_shape():
    search = search_symbols("login", limit=10)
    symbol_id = search["data"]["symbols"][0]["symbol_id"]
    callers = get_callers(symbol_id)
    callees = get_callees(symbol_id)
    assert callers["status"] == "PASS"
    assert callees["status"] == "PASS"
    assert callers["data"]["symbol_id"] == symbol_id
    assert callees["data"]["symbol_id"] == symbol_id
