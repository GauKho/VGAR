"""Offline W6: M1 fixture -> SQLite -> stateless MCP tools -> LangChain context display.

No model inference or gold labels. Each tool invocation creates a new server
session, exercising the persistent task_handle binding rather than globals.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.config.settings import GraphSettings, Settings
from vgar.contracts.context import ContextPayload
from vgar.evaluation.retrieval.evidence import new_run, utc_now, write_json
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.client import create_mcp_client
from vgar.mcp.registry import W5_W6_REQUIRED_GRAPH_TOOLS, validate_required_tools
from vgar.mcp.result_parser import parse_mcp_json_result
from vgar.repair.workspace import fingerprint_source


async def run(directory: Path, record: dict, tokenizer_manifest: Path | None, diagnostic: bool):
    original = ROOT / "tests/fixtures/m2/failing_repo"
    before = fingerprint_source(original)
    source = directory / "fixture"
    shutil.copytree(original, source)
    source_before = fingerprint_source(source)
    document = PythonGraphBuilder(repo_key="smoke/w6", repository_revision="synthetic-fixture", use_jedi=False).build(source)
    write_json(directory / "graph.json", document)
    database = directory / "graph.db"
    SQLiteGraphStore(database).ingest(document)
    settings = Settings(graph=GraphSettings(backend="sqlite", database=database, version=document["graph_version"],
                        source_root=source, tokenizer_manifest=tokenizer_manifest, allow_fallback_counter=diagnostic),
                        audit_log=directory / "mcp_audit.jsonl")
    client = create_mcp_client(settings)
    tools = await client.get_tools(server_name="graph")
    validate_required_tools(tools, W5_W6_REQUIRED_GRAPH_TOOLS)
    by_name = {tool.name: tool for tool in tools}
    record["tool_names"] = sorted(by_name)
    record["calls"] = []

    async def call(name, arguments, expected="PASS"):
        response = parse_mcp_json_result(await by_name[name].ainvoke(arguments))
        record["calls"].append({"tool": name, "arguments": arguments, "response": response})
        write_json(directory / "result.json", record)
        if response["status"] != expected:
            raise AssertionError(f"{name}: expected {expected}, got {response}")
        return response

    first = await call("graph_find_task_anchors", {"issue_text": "demo.answer returns a wrong value"})
    second = await call("graph_find_task_anchors", {"issue_text": "demo.answer should return a different number"})
    a, b = first["data"], second["data"]
    assert a["anchor_ids"] == b["anchor_ids"] and a["task_handle"] != b["task_handle"]
    contexts = []
    for found in (a, b, a):
        response = await call("graph_get_related_context", {"anchor_ids": found["anchor_ids"],
                             "budget_tokens": 8000, "task_handle": found["task_handle"]})
        payload = ContextPayload.model_validate(response["data"])
        assert payload.items and payload.graph_version == document["graph_version"]
        assert response["metadata"]["task_handle"] == found["task_handle"]
        contexts.append(response)
    assert contexts[0]["data"] == contexts[2]["data"]
    assert contexts[0]["metadata"]["overlay_id"] != contexts[1]["metadata"]["overlay_id"]
    await call("graph_get_related_context", {"anchor_ids": a["anchor_ids"], "budget_tokens": 8000,
                                           "task_handle": "unknown"}, expected="ERROR")
    content = "# W6 context display — synthetic fixture; inference NOT_RUN\n\n"
    for item in contexts[0]["data"]["items"]:
        content += f"## {item['path']} — {item['symbol']} ({item['token_count']} snippet tokens)\n\n```python\n{item['snippet']}\n```\n\n"
    (directory / "CONTEXT.md").write_text(content, encoding="utf-8")
    write_json(directory / "context.json", contexts[0])
    record.update(source_hash_before=before, source_hash_after=fingerprint_source(original),
                  fixture_hash_before=source_before, fixture_hash_after=fingerprint_source(source),
                  graph_version=document["graph_version"], counter_label=contexts[0]["metadata"]["counter_label"],
                  official_benchmark=False, counter_is_fallback=diagnostic, inference="NOT_RUN")
    assert before == record["source_hash_after"] and source_before == record["fixture_hash_after"]
    print(content, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tokenizer-manifest", type=Path)
    group.add_argument("--allow-fallback-counter", action="store_true", help="diagnostic fixtures only")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fixes/w3-w6")
    args = parser.parse_args()
    directory, record = new_run(args.output_root, "milestone-6-stdio-context")
    print(f"run: {directory}", flush=True)
    started = time.perf_counter()
    try:
        asyncio.run(asyncio.wait_for(run(directory, record,
                    args.tokenizer_manifest.resolve() if args.tokenizer_manifest else None, args.allow_fallback_counter), 90))
        record.update(status="PASS", exit_code=0)
    except (Exception, KeyboardInterrupt) as exc:
        record.update(status="ERROR", exit_code=1, error_class=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
    finally:
        record.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
        write_json(directory / "result.json", record)
    print(f"W5-W6 MCP CONTEXT {record['status']}", flush=True)
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
