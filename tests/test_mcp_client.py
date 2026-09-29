from vgar.mcp.servers.graph_server import search_symbols


def test_graph_search_uses_demo_graph_service():
    result = search_symbols("auth")

    assert result["status"] == "OK"
    assert result["metadata"]["backend"] == "demo"
    assert [symbol["name"] for symbol in result["symbols"]] == [
        "login",
        "validate_token",
    ]
