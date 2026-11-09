"""Real STDIO transport to explicit synthetic providers; never an agent benchmark."""
import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("server,expected", [("graph", 11), ("execution", 3)])
@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
def test_core_stdio_synthetic_provider(server, expected, mode, tmp_path):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from vgar.mcp.proposal.contracts import digest
    root = tmp_path / server
    params = StdioServerParameters(command=sys.executable, args=["-B", str(ROOT / "tests/fixtures/mcp_server/core_fixture_server.py"),
        "--root", str(root), "--server", server], env={"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "VGAR_GRAPH_BACKEND": "demo", "PYTHON_DOTENV_DISABLED": "1"})
    receipts = []

    async def run():
        with anyio.fail_after(40):
            async with Client(params, mode=mode) as client:
                listed = await client.list_tools()
                assert len(listed.tools) == expected
                for item in listed.tools:
                    assert item.input_schema["type"] == "object"
                async def call(name, args):
                    result = await client.call_tool(name, args)
                    assert not result.is_error
                    data = result.structured_content or json.loads(result.content[0].text)
                    receipts.append({"tool": name, "response": data})
                    assert data["status"] == "PASS", data
                    assert data["metadata"]["task_id"] == "synthetic-task"
                    return data["data"]
                if server == "graph":
                    built = await call("build_or_update_graph", {"repo_path": str(root / "repo")})
                    assert built["published"] is False
                    path = await call("explain_dependency_path", {"source_id": "a", "target_id": "b"})
                    assert path["nodes"] == ["a", "b"] and path["edges"][0]["edge_id"] == "synthetic-call"
                    for diff, status in (("GOOD", "PASS"), ("BAD", "FAIL")):
                        assert (await call("verify_patch_graph_constraints", {"diff": diff}))["status"] == status
                    ranked = await call("rank_patch_candidates", {"candidates": [
                        {"candidate_id": value, "diff": value, "diff_hash": digest(value)} for value in ("BAD", "GOOD")]})
                    assert [x["candidate_id"] for x in ranked["candidates"]] == ["GOOD", "BAD"]
                    assert ranked["candidates"][1]["eligible"] is False
                else:
                    result = await call("run_relevant_tests", {"diff": "GOOD"})
                    assert result["receipt"]["applied_count"] == 1 and result["receipt"]["cleaned"]
                    assert result["reasons"] == ["SYNTHETIC_SIMULATED_EXECUTION"]
    anyio.run(run)
    events = [json.loads(line) for line in (root / "output/audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(events) == len(receipts)
    assert not list((root / "lease").iterdir())
    (tmp_path / "wire.json").write_text(json.dumps({"synthetic": True, "mode": mode, "server": server,
                                                   "calls": receipts}, indent=2), encoding="utf-8")


def test_optimized_context_gate_still_fails_closed(tmp_path):
    code = """
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.proposal.ports import ProviderRegistry
from vgar.mcp.proposal.contracts import PathRequest
CoreTools(ProviderRegistry()).path(PathRequest(source_id='a',target_id='b'),{})
"""
    result = subprocess.run([sys.executable, "-O", "-B", "-c", code], cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode != 0 and "Host-bound context required" in result.stderr
