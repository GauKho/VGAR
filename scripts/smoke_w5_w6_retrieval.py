"""LangChain/MCP issue -> anchors -> budgeted context, with no repair or model call."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langchain_mcp_adapters.client import MultiServerMCPClient
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.registry import W5_W6_REQUIRED_GRAPH_TOOLS, validate_required_tools
from vgar.mcp.result_parser import parse_mcp_json_result


async def run(args):
    document = PythonGraphBuilder(repo_key="demo/w5-w6", repository_revision="smoke").build(args.repository)
    store = SQLiteGraphStore(args.database)
    try:
        store.load_document(document["graph_version"])
    except LookupError:
        store.ingest(document)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), VGAR_GRAPH_BACKEND="sqlite",
               VGAR_GRAPH_DATABASE=str(args.database.resolve()), VGAR_GRAPH_VERSION=document["graph_version"],
               VGAR_REPOSITORY_ROOT=str(args.repository.resolve()),
               VGAR_TOKENIZER_MANIFEST=str(args.tokenizer_manifest.resolve()),
               VGAR_MCP_AUDIT_LOG=str(args.database.with_suffix(".audit.jsonl").resolve()))
    client = MultiServerMCPClient({"graph": {"transport": "stdio", "command": sys.executable,
        "args": ["-m", "vgar.mcp.servers.graph_server"], "env": env}}, tool_name_prefix=True)
    tools = await client.get_tools()
    validate_required_tools(tools, W5_W6_REQUIRED_GRAPH_TOOLS)
    by_name = {tool.name: tool for tool in tools}
    inputs = {"graph_version": document["graph_version"], "task_id": "w5-smoke",
              "issue_text": args.issue_text, "failing_tests": args.failing_test}
    anchors = parse_mcp_json_result(await by_name["graph_find_task_anchors"].ainvoke(inputs))
    if anchors["status"] != "PASS":
        raise RuntimeError(anchors["error"])
    result = parse_mcp_json_result(await by_name["graph_get_related_context"].ainvoke({**inputs,
        "anchor_ids": [item["node_id"] for item in anchors["data"]["anchors"]], "budget_tokens": args.budget_tokens}))
    if result["status"] != "PASS":
        raise RuntimeError(result["error"])
    assert result["data"]["overlay_id"] == anchors["data"]["overlay_id"]
    print(json.dumps({"anchors": anchors["data"], **result["data"]}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT / "tests/fixtures/sample_repo")
    parser.add_argument("--database", type=Path, default=ROOT / "artifacts/m1/w5-w6/smoke.db")
    parser.add_argument("--tokenizer-manifest", type=Path, required=True)
    parser.add_argument("--issue-text", default="POST /login fails in src/web/routes.py")
    parser.add_argument("--failing-test", action="append", default=[])
    parser.add_argument("--budget-tokens", type=int, default=8000)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
