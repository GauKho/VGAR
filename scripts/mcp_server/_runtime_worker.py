"""Scripted official SDK client for one legacy server. No generator or agent loop."""
from __future__ import annotations

import argparse
import json
import os
import sys
from importlib import metadata
from pathlib import Path
from urllib.parse import quote

import anyio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def require(condition, message):
    """Executable admission checks must survive PYTHONOPTIMIZE/-O."""
    if not condition:
        raise RuntimeError(message)


def field(obj, snake, camel=None):
    return getattr(obj, snake, getattr(obj, camel or snake, None))


def payload(result):
    require(not field(result, "is_error", "isError"), str(result))
    data = field(result, "structured_content", "structuredContent")
    texts = [json.loads(x.text) for x in result.content if getattr(x, "type", None) == "text"]
    if data is None:
        require(len(texts) == 1, "Expected one JSON text payload")
        data = texts[0]
    elif texts:
        require(data == texts[0], "Structured/text payload mismatch")
    require(set(data) == {"status", "data", "error", "metadata"}, "Envelope keys changed")
    require(isinstance(data["metadata"]["request_id"], str), "Missing request ID")
    require(data["metadata"]["duration_ms"] >= 0, "Invalid duration")
    return data


async def exercise(client, args, report):
    oracle = json.loads((ROOT / "tests/fixtures/mcp_server/expected_contract.json").read_text(encoding="utf-8"))
    listed = await client.list_tools()
    expected = [x for x in oracle["legacy_surface"] if x["server"] == args.server]
    additions = {"graph": {"build_or_update_graph", "explain_dependency_path", "verify_patch_graph_constraints", "rank_patch_candidates"},
                 "execution": {"run_relevant_tests"}}
    require({x.name for x in listed.tools} == {x["name"] for x in expected} | additions.get(args.server, set()), "Legacy/core tool names changed")
    report["tools"] = [x.model_dump(mode="json", by_alias=True) for x in listed.tools]
    import ast
    for item in listed.tools:
        if item.name in additions.get(args.server, set()):
            require(field(item, "input_schema", "inputSchema").get("type") == "object", "Missing core input schema")
            continue
        signature = next(x["signature"] for x in expected if x["name"] == item.name)
        fn = ast.parse(f"def f({signature}): pass").body[0]
        schema = field(item, "input_schema", "inputSchema")
        require(set(schema["properties"]) == {a.arg for a in fn.args.args}, "Input properties changed: "+item.name)
        required = [a.arg for a in fn.args.args[:len(fn.args.args)-len(fn.args.defaults)]]
        require(set(schema.get("required", [])) == set(required), "Required inputs changed: "+item.name)
    resources = await client.list_resources()
    templates = await client.list_resource_templates()
    uris = [str(x.uri) for x in resources.resources]
    uris += [str(field(x, "uri_template", "uriTemplate")) for x in templates.resourceTemplates] if hasattr(templates, "resourceTemplates") else [str(x.uri_template) for x in templates.resource_templates]
    resource_oracle = json.loads((ROOT / "tests/fixtures/mcp_server/resource_contract.json").read_text(encoding="utf-8"))
    expected_uris = set(resource_oracle["canonical"] + resource_oracle["legacy_aliases"]) if args.server == "graph" else set()
    require(set(uris) == expected_uris, "Legacy/canonical resource inventory changed")
    report["resources"] = uris
    prompts = await client.list_prompts()
    if args.server == "graph":
        prompt_oracle = json.loads((ROOT / "tests/fixtures/mcp_server/prompt_contract.json").read_text(encoding="utf-8"))
        require([p.name for p in prompts.prompts] == [prompt_oracle["name"]], "Prompt inventory mismatch")
        require([a.name for a in prompts.prompts[0].arguments] == prompt_oracle["arguments"]
                and all(a.required for a in prompts.prompts[0].arguments), "Prompt argument schema changed")
        rendered = await client.get_prompt(prompt_oracle["name"], prompt_oracle["input"])
        require(len(rendered.messages) == 2 and all(msg.role == "user" for msg in rendered.messages), "Prompt messages invalid")
        require(rendered.messages[0].content.text == prompt_oracle["instructions"]
                and rendered.messages[1].content.text == prompt_oracle["expected_data_text"], "Prompt oracle mismatch")
        report["rendered_prompt"] = rendered.model_dump(mode="json", by_alias=True)
        report["prompt_gate"] = "PASS"
    else:
        require(not prompts.prompts, "Unexpected prompt on non-graph server")
        report["prompt_gate"] = "NOT_APPLICABLE"

    async def call(name, arguments, *, status="PASS", error=None):
        with anyio.fail_after(90):
            result = payload(await client.call_tool(name, arguments))
        report["calls"].append({"tool": name, "response": result})
        require(result["status"] == status, result)
        if error:
            require(result["error"]["code"] == error, result)
        else:
            require(result["error"] is None, "Success response has error")
        return result["data"]

    if args.server == "graph":
        found = await call("search_symbols", {"query": "login", "limit": 10})
        symbol = found["symbols"][0]["symbol_id"]
        await call("get_callers", {"symbol_id": symbol})
        await call("get_callees", {"symbol_id": symbol})
        await call("get_callers", {"symbol_id": "missing:symbol"}, status="ERROR", error="NODE_NOT_FOUND")
        await call("search_symbols", {"query": ""}, status="ERROR", error="INVALID_QUERY")
        for uri in ("vgar://repo/summary", "vgar://graph/node/"+quote(symbol, safe=""), "vgar://graph/subgraph/"+quote(symbol, safe="")):
            result = await client.read_resource(uri)
            require(field(result.contents[0], "mime_type", "mimeType") == "text/plain", "Legacy resource MIME changed")
            content = json.loads(result.contents[0].text)
            require(isinstance(content, dict) and content, "Empty or malformed resource")
            report.setdefault("resource_reads", []).append({"uri": uri, "data": content})
    elif args.server == "repository":
        await call("health", {})
        data = await call("read_file", {"path": "auth.py"})
        require("def login" in data["content"], "Unexpected repository content")
        await call("read_file", {"path": "../secret.txt"}, status="ERROR", error="PATH_OUTSIDE_ROOT")
    elif args.server == "execution":
        await call("health", {})
        data = await call("run_pytest", {"selector": "tests/test_auth.py::test_ok"})
        require(data["verdict"] == "PASS" and data["exit_code"] == 0, "Execution fixture did not pass")
        await call("run_pytest", {"selector": "forbidden.py"}, status="ERROR", error="SELECTOR_REJECTED")


async def connect(args, report):
    from mcp.client.stdio import StdioServerParameters
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(ROOT/"src"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONOPTIMIZE": "0",
                "VGAR_MCP_AUDIT_LOG": str(Path(args.output)/"audit.jsonl"), "VGAR_TRACE": "",
                "VGAR_GRAPH_BACKEND": "sqlite", "VGAR_GRAPH_DATABASE": str(Path(args.output)/"sample_graph.db"),
                "VGAR_LEASE_ROOT": str(Path(args.output)/"lease"), "VGAR_ALLOWED_SELECTORS": '["tests/test_auth.py"]',
                "VGAR_RUN_ROOT": args.output, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    params = StdioServerParameters(command=args.server_python, args=["-B", "-m", f"vgar.mcp.servers.{args.server}_server"], env=env, cwd=args.output)
    major = int(metadata.version("mcp").split(".")[0])
    report["client_sdk"] = metadata.version("mcp")
    if major == 2:
        from mcp import Client
        async with Client(params, mode=args.mode, read_timeout_seconds=90) as client:
            report["protocol"] = client.protocol_version
            await exercise(client, args, report)
    else:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        require(args.mode == "legacy", "SDK1 client only supports legacy mode")
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            initialized = await client.initialize()
            report["protocol"] = initialized.protocolVersion
            await exercise(client, args, report)
    if args.mode != "legacy":
        require(report["protocol"] == args.mode, "Negotiated protocol differs from requested mode")
    report["cleanup"] = "SDK context exited; controller process-tree boundary also enforced"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True, choices=("graph", "repository", "execution"))
    parser.add_argument("--mode", required=True)
    parser.add_argument("--server-python", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = {"server": args.server, "requested_mode": args.mode, "status": "FAIL", "calls": [], "synthetic": True}
    try:
        anyio.run(connect, args, report)
        report["status"] = "PASS"
    except Exception as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        (Path(args.output)/"wire.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("server", "status", "protocol", "client_sdk")}))


if __name__ == "__main__":
    main()
