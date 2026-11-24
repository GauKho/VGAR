"""A host that starts `python -m vgar.mcp.servers.graph_server` gets SCIP by default (spec 2026-11-24 §4.1, §5.4)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import anyio
from resolver_fixture import CHAIN, needs_resolvers

ROOT = Path(__file__).resolve().parents[2]


def _build_over_stdio(tmp_path: Path, **extra: str) -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    repo, data = tmp_path / "repo", tmp_path / "data"
    for path, text in CHAIN.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")
    data.mkdir()
    env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHON_DOTENV_DISABLED": "1", "PATH": os.environ.get("PATH", ""),
           "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "VGAR_GRAPH_BACKEND": "sqlite",
           "VGAR_REPOSITORY_ROOT": str(repo), "VGAR_GRAPH_DATABASE": str(data / "graph.db"),
           "VGAR_MCP_AUDIT_LOG": str(data / "audit.jsonl"), **extra}
    params = StdioServerParameters(command=sys.executable, args=["-B", "-m", "vgar.mcp.servers.graph_server"], env=env,
                                   cwd=str(repo))

    async def run():
        with anyio.fail_after(120):
            async with Client(params, mode="2026-07-28") as client:
                result = await client.call_tool("build_or_update_graph", {"repo_path": str(repo)})
                return result.structured_content
    envelope = anyio.run(run)
    assert envelope["status"] == "PASS", envelope
    return envelope["data"]


@needs_resolvers
def test_server_started_by_a_host_uses_scip_by_default(tmp_path):
    data = _build_over_stdio(tmp_path)
    assert data["layers"]["scip"]["status"] == "ready" and data["layers"]["lsp"]["status"] == "skipped"
    assert not (tmp_path / "repo" / "artifacts").exists() and (tmp_path / "data" / "scip-runs").is_dir()


@needs_resolvers
def test_host_can_turn_scip_off(tmp_path):
    data = _build_over_stdio(tmp_path, VGAR_SCIP="off")
    assert data["layers"]["scip"]["status"] == "off" and data["layers"]["lsp"]["status"] == "ready"
