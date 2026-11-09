"""Fixed offline probe actions. Never executes a provider chosen by tool arguments."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# A new helper process only: discard inherited credentials/client/global settings
# before importing VGAR or spawning any server. Do not alter the caller's env.
allow = {"PATH","PATHEXT","SYSTEMROOT","WINDIR","TEMP","TMP","COMSPEC","USERPROFILE","LOCALAPPDATA","APPDATA"}
clean = {key:value for key,value in os.environ.items() if key.upper() in allow}
clean.update(PYTHONUTF8="1",PYTHONDONTWRITEBYTECODE="1",PYTHONOPTIMIZE="0",PYTHON_DOTENV_DISABLED="1",
             PYTHONPATH=str(ROOT/"src"),VGAR_GRAPH_BACKEND="demo",GIT_OPTIONAL_LOCKS="0",
             HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
os.environ.clear()
os.environ.update(clean)
sys.path.insert(0,str(ROOT/"src"))


def probe():
    import importlib
    import tempfile
    import time
    from dataclasses import asdict
    from importlib import util

    import anyio

    from vgar.contracts.schema import NODE_TYPES
    from vgar.mcp.proposal import contracts as c
    from vgar.mcp.proposal.context import (
        ContextAuthority,
        bind_context,
        source_inventory_hash,
    )
    from vgar.mcp.proposal.graph_jobs import GraphJobConfig, GraphJobController
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.tools import CoreTools

    result = {"servers":{},"schema_node_types":sorted(NODE_TYPES),"implementations":{}}
    for name in ("graph","execution"):
        module = importlib.import_module("vgar.mcp.servers."+name+"_server")
        tools = module.core_tools
        result["servers"][name] = {"registry":[{"provider":type(r.provider).__module__+"."+type(r.provider).__name__,
            "capabilities":sorted(r.capabilities),"synthetic":r.synthetic,"lifecycle":r.lifecycle} for r in tools.registry.bindings],
            "graph_jobs":tools.graph_jobs is not None,"context_factory":tools.context_factory is not None,
            "backend":getattr(getattr(module,"graph_service",None),"backend_name",None)}
    for name, path in {"graph_jobs":"vgar.mcp.proposal.graph_jobs","legacy_graph":"vgar.graph.sqlite_service",
                       "storage":"vgar.graph.storage_capabilities","legacy_api_check":"vgar.repair.api_check",
                       "legacy_structural_check":"vgar.repair.structural_check"}.items():
        spec = util.find_spec(path)
        result["implementations"][name] = spec is not None
    with tempfile.TemporaryDirectory(prefix="vg-preflight-guard-") as folder:
        root = Path(folder)
        for name in ("repo","lease","output","state"):
            (root/name).mkdir()
        authority = ContextAuthority(root/"state")
        pin = c.digest("fixture-static-config")
        ctx = bind_context(authority,repo_root=root/"repo",lease_root=root/"lease",output_root=root/"output",
            request_id="offline-no-grant",run_id="fixture",task_id="fixture",snapshot_hash=c.digest("unbuilt-anchor"),
            source_hash=source_inventory_hash(root/"repo"),config_hash=pin,deadline=time.time()+60)
        cfg = GraphJobConfig(repo_root=ctx.repo_root,output_root=ctx.output_root,state_root=ctx.state_root,
                            repo_key="demo/serving",repository_revision="fixture-revision",config_hash=pin,profile_hash=pin)
        def forbidden(*_):
            raise RuntimeError("No-grant probe reached storage issuer")
        controller = GraphJobController(cfg,storage_issuer=forbidden)
        profile = controller.profile()
        result["fixture_profile"] = {key:value for key,value in asdict(profile).items() if key != "validator"}
        guarded = CoreTools(ProviderRegistry(),graph_jobs=controller)
        try:
            anyio.run(guarded.build,c.BuildRequest(repo_path=str(ctx.repo_root)),ctx)
        except ValueError as error:
            if "grant" not in str(error):
                raise
        else:
            raise RuntimeError("Missing grant accepted")
        entries = list(ctx.output_root.iterdir())
        # Denial may append adapter audit in host control output. It must not
        # create a worker, DB, snapshot, source copy or candidate operation.
        audit = [p for p in entries if p.is_file() and p.name.startswith("adapter-") and p.suffix == ".json"]
        output_entries = len(entries)-len(audit)
        if output_entries or controller._process is not None:
            raise RuntimeError("Denied build caused side effects")
        controller.close()
        absent = CoreTools(ProviderRegistry())
        try:
            absent.path(c.PathRequest(source_id="fixture-a",target_id="fixture-b"),ctx)
        except Exception as error:
            reason = getattr(error,"details",{}).get("reason")
            if reason != "CAPABILITY_UNAVAILABLE":
                raise
        else:
            raise RuntimeError("Missing path provider returned success")
        verified = absent.verify(c.DiffRequest.from_diff(""),ctx)
        if verified.status != "NOT_RUN" or verified.reasons != ("CAPABILITY_UNAVAILABLE",):
            raise RuntimeError("Missing verifier became a PASS")
        result["denials"] = {"scope":"fixture trusted context, no write grant",
            "build":"WRITE_GRANT_REQUIRED","operation_output_entries":output_entries,
            "control_audit_records":len(audit),"worker_spawned":False,
            "path":"CAPABILITY_UNAVAILABLE","verification":verified.model_dump(mode="json")}
    print(json.dumps(result))


def graph(arguments):
    import argparse
    import shutil
    import tempfile

    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from vgar.mcp.proposal.context import source_inventory_hash

    parser = argparse.ArgumentParser()
    parser.add_argument("--server-python",required=True)
    parser.add_argument("--output-root",required=True)
    args = parser.parse_args(arguments)
    output = Path(args.output_root)
    output.mkdir(exist_ok=False)
    lanes = []
    for mode in ("2026-07-28","legacy"):
        destination = output/mode
        destination.mkdir()
        with tempfile.TemporaryDirectory(prefix="vg-preflight-graph-") as folder:
            root = Path(folder)/"fixture"
            params = StdioServerParameters(command=args.server_python,args=["-B",str(ROOT/"tests/fixtures/mcp_server/graph_jobs_fixture_server.py"),"--root",str(root)],
                env={**clean,"VGAR_MCP_AUDIT_LOG":str(destination/"client-audit.jsonl")})
            receipts = []
            async def run(params=params, mode=mode, root=root, destination=destination, receipts=receipts):
                with anyio.fail_after(90):
                    async with Client(params,mode=mode) as client:
                        # Client connects lazily. Await initialization before
                        # fingerprinting source created by the fixture server.
                        await client.list_tools()
                        if not (root/"repo/src/a.py").is_file():
                            raise RuntimeError("Fixture source was not initialized")
                        for i in range(3):
                            if i == 2:
                                source = root/"repo/src/a.py"
                                source.write_text(source.read_text(encoding="utf-8")+"\ndef added():\n    return value()\n",encoding="utf-8")
                            before = source_inventory_hash(root/"repo")
                            response = await client.call_tool("build_or_update_graph",{"repo_path":str(root/"repo")})
                            payload = json.loads(response.content[0].text)
                            if payload.get("status") != "PASS" or not payload["data"].get("published"):
                                raise RuntimeError("Actual graph build did not publish")
                            data = payload["data"]
                            receipt_path = root/"output"/data["evidence"][0]["path"]
                            receipt = json.loads(receipt_path.read_bytes())
                            shutil.copy2(receipt_path,destination/(f"job-{i}.json"))
                            manifest = root/"output"/receipt["manifest"]
                            snapshot = destination/"snapshots"/manifest.parent.name
                            snapshot.mkdir(parents=True,exist_ok=True)
                            for filename in ("manifest.json","graph.db"):
                                shutil.copy2(manifest.parent/filename,snapshot/filename)
                            summary = await client.read_resource("vgar://repo/summary")
                            content = json.loads(summary.contents[0].text)
                            if content.get("graph_version") != data["result_snapshot_hash"] or source_inventory_hash(root/"repo") != before:
                                raise RuntimeError("Graph read/source binding changed")
                            receipts.append({"result":data,"receipt":f"job-{i}.json","resource":content,
                                "source_unchanged":True,"source_hash":before,
                                "manifest":snapshot.relative_to(destination).as_posix()+"/manifest.json"})
                        denied = await client.call_tool("build_or_update_graph",{"repo_path":str(root)})
                        if json.loads(denied.content[0].text).get("status") != "ERROR":
                            raise RuntimeError("Unauthorized repo accepted")
                        protocol = client.protocol_version
                return protocol
            protocol = anyio.run(run)
            # Only public receipts are exported, never ContextAuthority state.
            (destination/"wire.json").write_text(json.dumps({"status":"PASS","fixture_inputs":True,
                "provider":"real-static-builder","mode":mode,"protocol":protocol,"calls":receipts,
                "unauthorized_repo_denied":True},indent=2),encoding="utf-8")
            lanes.append({"mode":mode,"protocol":protocol,"receipt":mode+"/wire.json"})
    (output/"summary.json").write_text(json.dumps({"status":"PASS","provider":"real-static-builder",
        "fixture_inputs":True,"lanes":lanes}),encoding="utf-8")


def main():
    action = sys.argv[1]
    if action == "probe":
        probe()
    elif action == "runtime":
        sys.path.insert(0,str(Path(__file__).parent))
        import check_runtime
        return check_runtime.main(sys.argv[2:])
    elif action == "graph":
        graph(sys.argv[2:])
    elif action == "clients":
        sys.path.insert(0,str(Path(__file__).parent))
        import smoke_mcp
        print(json.dumps(smoke_mcp.inspect_clients(Path.cwd())))
    else:
        raise ValueError("Unknown offline probe action")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
