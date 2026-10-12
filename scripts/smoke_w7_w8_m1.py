"""Graph -> SQLite -> MCP context/test selection -> M2 prompt adapter; no model or patch."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langchain_mcp_adapters.client import MultiServerMCPClient
from vgar.contracts.context import ContextPayload
from vgar.contracts.prompt_context import render_context_for_repair
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.handoff import create_context_handoff, write_context_handoff
from vgar.graph.scip_resolver import ScipConfig
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.graph.token_counter import LocalTokenizerCounter
from vgar.mcp.registry import validate_required_tools
from vgar.mcp.result_parser import parse_mcp_json_result


async def run(args) -> None:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ.update(VGAR_GRAPH_DEBUG_LOG=str(output / "debug.jsonl"), VGAR_GRAPH_DEBUG_RUN_ID=uuid.uuid4().hex)
    runtime = ROOT / "artifacts/m1/w7-w8/scip-runtime/node_modules/@sourcegraph/scip-python/index.js"
    node = shutil.which("node") or "node"
    scip = ScipConfig(command=(node, "-r", str(ROOT / "scripts/scip_windows_compat.cjs"), str(runtime)),
                      output_directory=output / "scip", strict=True) if args.resolver == "scip" else None
    document = PythonGraphBuilder(repo_key="demo/w7-w8", repository_revision="fixture-smoke", scip=scip).build(args.repository)
    (output / "graph.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    database = output / "graph.db"
    SQLiteGraphStore(database).ingest(document)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), VGAR_GRAPH_BACKEND="sqlite", VGAR_GRAPH_DATABASE=str(database),
               VGAR_REPOSITORY_ROOT=str(args.repository.resolve()), VGAR_TOKENIZER_MANIFEST=str(args.tokenizer_manifest.resolve()),
               VGAR_MCP_AUDIT_LOG=str(output / "audit.jsonl"))
    client = MultiServerMCPClient({"graph": {"transport": "stdio", "command": sys.executable,
        "args": ["-m", "vgar.mcp.servers.graph_server"], "env": env}}, tool_name_prefix=True)
    tools = await client.get_tools()
    validate_required_tools(tools, {"graph_find_task_anchors", "graph_get_related_context", "graph_get_related_tests"})
    by_name = {tool.name: tool for tool in tools}

    async def invoke(name, arguments):
        response = parse_mcp_json_result(await by_name[name].ainvoke(arguments))
        if response["status"] != "PASS":
            raise RuntimeError(response["error"])
        return response["data"]

    inputs = {"graph_version": document["graph_version"], "task_id": "w7-smoke",
              "issue_text": "login returns an incorrect result in src/auth/service.py",
              "failing_tests": ["tests/test_auth.py::test_login"]}
    found = await invoke("graph_find_task_anchors", inputs)
    context = await invoke("graph_get_related_context", {**inputs, "anchor_ids": [item["node_id"] for item in found["anchors"]], "budget_tokens": 8000})
    ContextPayload.model_validate(context["context"])
    selection = await invoke("graph_get_related_tests", {"symbol_ids": [], "graph_version": document["graph_version"],
                            "changed_paths": ["src/auth/service.py"], "failing_tests": inputs["failing_tests"]})
    assert found["overlay_id"] == context["overlay_id"]
    assert context["context"]["items"] and selection["tests"]
    (output / "context.json").write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "test-selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    (output / "repair-context.txt").write_text(render_context_for_repair(context["context"]), encoding="utf-8")
    counter = LocalTokenizerCounter(args.tokenizer_manifest)
    handoff = create_context_handoff(document, context, args.repository,
        count_tokens=counter, counter_label=counter.counter_label,
        changed_paths=["src/auth/service.py"], failing_tests=inputs["failing_tests"])
    handoff_path = write_context_handoff(handoff, output / ("handoff-" + uuid.uuid4().hex))
    record = {"status": "PASS", "scope": "fixture_no_model_no_patch", "resolver_profile": args.resolver,
              "resolver": document["statistics"]["resolver"],
              "context_format": context["context_format"], "items": len(context["context"]["items"]),
              "tokens": context["context"]["total_token_count"], "selected_tests": selection["tests"],
              "graph_version": document["graph_version"], "tool_names": sorted(by_name),
              "handoff_path": str(handoff_path), "source_digest": handoff["manifest"]["source_digest"],
              "handoff_validated": True, "test_collection_verified": False}
    (output / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT / "tests/fixtures/sample_repo")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/m1/w7-w8/smoke")
    parser.add_argument("--tokenizer-manifest", type=Path, required=True)
    parser.add_argument("--resolver", choices=("static", "scip"), default="static")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
