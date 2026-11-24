"""Text sent to the host is compact JSON for every tool of the three servers (spec 2026-11-24 §4.1)."""
from __future__ import annotations

from typing import Any

import anyio
import pytest
from mcp import Client

from vgar.mcp.agent_output import compact_json
from vgar.mcp.audit import AuditLogger
from vgar.mcp.server_factory import create_resource_server, create_server
from vgar.mcp.servers import execution_server, graph_server, repository_server

COMPACT = '{"a":[1,2],"b":"café"}'


@pytest.mark.parametrize("make", [lambda: create_server("t"), lambda: create_resource_server("t", lambda uri: "")])
def test_factory_servers_send_compact_text_and_keep_structured_content(make):
    server = make()

    @server.tool()
    def sample() -> dict[str, Any]:
        return {"a": [1, 2], "b": "café"}

    async def run():
        async with Client(server, mode="2026-07-28") as client:
            return await client.call_tool("sample", {})
    result = anyio.run(run)
    assert result.content[0].text == COMPACT
    assert result.structured_content == {"a": [1, 2], "b": "café"}


@pytest.mark.parametrize("module,tool,args", [(graph_server, "get_callers", {"symbol_id": "x", "depth": 0}),
                                              (execution_server, "health", {}), (repository_server, "health", {})])
def test_every_vgar_server_sends_compact_text(module, tool, args, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    result = anyio.run(module.mcp.call_tool, tool, args)
    text = result.content[0].text
    assert "\n" not in text and text == compact_json(result.structured_content)


def test_calling_the_tool_function_still_returns_a_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(execution_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    assert execution_server.health()["status"] == "PASS"
