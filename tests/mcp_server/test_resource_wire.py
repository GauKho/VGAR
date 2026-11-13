"""Real official SDK client/STDIO calls, with explicitly synthetic resource provider."""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import anyio
import pytest
from graph_fixture import real_graph_env

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("server_python,mode", [(sys.executable, "2026-07-28"), (sys.executable, "legacy")],
                         ids=["sdk2-modern", "sdk2-legacy"])
def test_resource_stdio_inventory_encoding_and_scope(server_python, mode, tmp_path):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    from mcp.shared.exceptions import MCPError
    require_python = Path(server_python)
    assert require_python.is_file(), "Required compatibility interpreter missing"
    params = StdioServerParameters(command=server_python, args=["-B", str(ROOT / "tests/fixtures/mcp_server/resource_fixture_server.py"),
        "--root", str(tmp_path / "fixture")], env={"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1", **real_graph_env()})
    receipts = []
    async def run():
        with anyio.fail_after(60):
            async with Client(params, mode=mode) as client:
                static, dynamic = await client.list_resources(), await client.list_resource_templates()
                uris = {str(row.uri) for row in static.resources} | {row.uri_template for row in dynamic.resource_templates}
                oracle = json.loads((ROOT / "tests/fixtures/mcp_server/resource_contract.json").read_text(encoding="utf-8"))
                assert uris == set(oracle["canonical"] + oracle["legacy_aliases"])
                assert len(static.resources) == 4 and len(dynamic.resource_templates) == 5
                assert len((await client.list_tools()).tools) == 11
                assert [row.name for row in (await client.list_prompts()).prompts] == ["repair_with_graph_context"]
                async def read(uri):
                    result = await client.read_resource(uri)
                    assert len(result.contents) == 1
                    assert result.contents[0].mime_type == "text/plain", "Preserve the declared/default legacy resource MIME"
                    payload = json.loads(result.contents[0].text)
                    assert len(result.contents[0].text.encode()) <= (262144 if uri.startswith("vgar://audit/") else 65536)
                    receipts.append({"uri": uri, "data": payload})
                    return payload
                await read("vgar://repo/summary")
                await read("vgar://repo/schema")
                for identifier in ("fixture:a/b:π", "fixture:a%2Fb"):
                    encoded = quote(identifier, safe="")
                    assert (await read("vgar://graph/node/"+encoded))["repo"]["node_id"] == identifier
                    assert (await read("vgar://graph/subgraph/"+encoded+"?k=2"))["anchor_id"] == identifier
                    assert (await read("vgar://graph/subgraph/"+encoded))["anchor_id"] == identifier
                    assert (await read("vgar://component/"+encoded))["id"] == identifier
                assert (await read("vgar://task/synthetic-task"))["id"] == "synthetic-task"
                assert (await read("vgar://evidence/baseline"))["public"] is True
                first = await read("vgar://audit/log")
                await read("vgar://audit/log?cursor=" + str(first["cursor"]))
                for uri in ("vgar://task/other", "vgar://graph/subgraph/fixture%3Asimple?k=3", "vgar://graph/node/missing"):
                    with pytest.raises(MCPError) as error:
                        await client.read_resource(uri)
                    receipts.append({"uri": uri, "error": error.value.code})
    anyio.run(run)
    raw = json.dumps(receipts, ensure_ascii=False)
    assert "must-hide" not in raw and "synthetic-secret-value" not in raw
    events = [json.loads(row) for row in (tmp_path / "fixture/output/audit.jsonl").read_text(encoding="utf-8").splitlines()]
    reads = [row for row in events if row["event_type"] == "resource_read"]
    assert len(reads) == len(receipts)
    assert all(row["payload"]["request_id"] == "synthetic-resource-read"
               for row in reads if not row["payload"]["resource"].startswith("invalid-resource:"))
    assert all(row["payload"]["status"] == "ERROR"
               for row in reads if row["payload"]["resource"].startswith("invalid-resource:"))
    (tmp_path / "resource-wire.json").write_text(json.dumps({"synthetic": True, "mode": mode, "server_python": server_python,
                                                            "receipts": receipts}, ensure_ascii=False, indent=2), encoding="utf-8")


def test_resource_gate_under_optimized_python(tmp_path):
    code = "from vgar.mcp.proposal.resources import parse_resource_uri; parse_resource_uri('vgar://audit/log?run_id=other')"
    result = subprocess.run([sys.executable, "-O", "-B", "-c", code], cwd=tmp_path, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}, timeout=15, check=False)
    assert result.returncode != 0 and b"Unsupported or duplicate resource query" in result.stderr
