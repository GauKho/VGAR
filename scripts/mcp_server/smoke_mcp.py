"""Offline L6-8 preflight, never an installer, agent, or production auto-grant host."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vgar.mcp.proposal.locking import no_links
from vgar.mcp.proposal.security import read_lease_bytes, resolve_read_path
from vgar.repair.executor import run_bounded


def _graph_env(name):
    value = os.environ.get(name, "")
    return str(ROOT / value) if value and not os.path.isabs(value) else value

def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_receipt(root, relative, *, expected_hash=None):
    raw, size = read_lease_bytes(root, relative, 16*1024*1024)
    require(size <= 16*1024*1024, "Receipt exceeds cap")
    if expected_hash is not None:
        require(sha(raw) == expected_hash, "Receipt hash mismatch")
    def finite(value):
        raise ValueError("Non-finite JSON")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    result = json.loads(raw, parse_constant=finite, object_pairs_hook=unique)
    require(isinstance(result, dict), "JSON object receipt required")
    return result


def validate_output(path, *, inputs=()):
    output = no_links(Path(path)).resolve()
    require(not output.exists(), "Preflight output already exists; choose a new directory")
    for item in inputs:
        source = no_links(item).resolve()
        require(not (output == source or output.is_relative_to(source) or source.is_relative_to(output)),
                "Preflight output must not overlap input")
    if output.is_relative_to(ROOT):
        require(output.is_relative_to(ROOT / "results/mcp_server/preflight"), "Output inside repository must use preflight results")
    require(not ROOT.is_relative_to(output), "Output must not overlap repository")
    return output


def client_probe_commands(claude):
    return [(str(claude), "--version"), (str(claude), "--help")]


# Ownership comes from Final_Task, not the older M1/M2/M3 roles.
# status is observation-specific; implementation existence never implies binding.
CATALOG = (
    ("bootstrap", ("all core tools/resources",), "TV1", ("L6-2","L6-3","L6-6","L6-8"), "bootstrap",
     "Trusted request context, fixed providers, explicit snapshot/tokenizer/lease and per-operation grants", "Configure immutable per-request bindings and explicit readers", "Real calls with correct binding, denied unauthorized writes and cleanup"),
    ("build", ("build_or_update_graph",), "TV1", ("L6-6","L6-7"), "build",
     "Legacy GraphJobController exists; configure host and storage issuer", "Bind existing legacy controller; do not auto-grant from model input", "Cold/reuse/warm and source/snapshot publication evidence"),
    ("schema", ("vgar://repo/schema",), "TV2", ("SC-1",), "resource_schema",
     "New node/edge types, endpoints, IDs, validator and fingerprint; valid/invalid fixtures", "Register actual profile and adapt storage projection without widening legacy", "Round-trip rich schema and reject invalid endpoints/IDs"),
    ("rich_build", ("build_or_update_graph",), "TV2", ("Layer 1-3","GA-1","GA-2","GT-1","TR-1"), "rich_build",
     "Real graph builder/update capability, coverage and full-rebuild oracle for each layer", "Orchestrate new capabilities and invalidation in controller/storage", "Warm/full semantic equality, no stale layer relabeling"),
    ("queries", ("search_symbols","get_callers","get_callees","vgar://graph/node/{node_id}","vgar://graph/subgraph/{node_id}?k=2","vgar://repo/summary"), "TV2", ("Layer 1-3",), "legacy_graph",
     "Legacy SQL queries exist; richer traversal semantics need bound graph provider", "Select explicit real snapshot and source binding; preserve depth1 payload", "Query oracle on real provider, source/DB immutable"),
    ("traversal", ("get_callers","get_callees"), "TV2", ("Layer 1-3",), "traversal",
     "Multi-hop provider with direction/confidence/provenance/caps", "Bind traversal provider; no depth echo or fake edges", "Cycles/diamonds/ownership/hop and cap oracle"),
    ("path", ("explain_dependency_path",), "TV2", ("Layer 1-3",), "path",
     "Dependency path provider with original witness edges and availability", "Bind existing adapter, source/snapshot checks", "Witness connectivity, directions, confidence, truncation"),
    ("context", ("find_task_anchors","get_related_context"), "TV2", ("GT-1","TR-1","RT-1"), "legacy_graph",
     "Legacy grounding/retrieval exists; real source snapshot and pinned tokenizer plus richer ranking provider needed", "Bind source/tokenizer/task; do not inherit experiment budget", "Context under explicit budget, source hashes/token accounting verified"),
    ("impact", ("analyze_patch_impact",), "TV2", ("IM-1",), "legacy_graph",
     "Legacy impact exists; architecture/port impact capability and coverage needed", "Bind extended provider without changing legacy defaults", "Impact oracle with measured zero distinct from unknown"),
    ("component", ("vgar://component/{component_id}",), "TV2", ("GA-1","GA-2"), "resource_component",
     "Component/Port/Lift facts and schema-bound resource view", "Bind resource provider with evidence and bounded serialization", "Component view from exact selected snapshot"),
    ("task", ("vgar://task/{task_id}",), "TV2", ("GT-1","TR-1"), "resource_task",
     "Task/trace facts, identifiers and task-scoped resource view", "Bind task provider, reject cross-task reads", "Task/trace oracle with correct snapshot/task binding"),
    ("verification", ("verify_patch_graph_constraints",), "TV3", ("EV-2","Layer 4-5"), "verification",
     "New-contract graph checks, baseline/post evidence, coverage; legacy API/structural code is reusable input", "Bind verifier; preserve incomplete/error and independent finalizer", "GOOD/BAD fixture, exact source/config hashes and real evidence refs"),
    ("ranking", ("rank_patch_candidates",), "TV3", ("EV-1",), "ranking",
     "Real evidence/score provider with candidate/diff hashes and required-check policy", "Bind rank adapter, stable ties; FAIL/ERROR/NOT_RUN cannot become eligible ACCEPT", "Rank all candidates and preserve required-check rejection"),
    ("tests", ("run_relevant_tests",), "TV3", ("EV-3",), "tests",
     "Diff-test provider with admitted private workspace, execution/apply/cleanup receipts", "Bind execution adapter; do not call repair finalizer as test shortcut", "No source mutation, apply once, real test result and cleanup"),
    ("baseline", ("vgar://evidence/baseline",), "TV3", ("EV-1","EV-2","EV-3"), "resource_baseline",
     "Public baseline evidence view tied to actual task/run/snapshot and sidecar hashes", "Bind baseline provider, no latest/session dump", "References exist/hash-match and cross-run denied"),
    ("storage", ("build_or_update_graph","vgar://repo/schema"), "TV1", ("L6-7",), "storage",
     "TV2 new schema/validator/projection contract; legacy SQLite already implemented", "Implement profile/projection for supplied schema; keep old DBs frozen", "Real new-schema round-trip and SQL query proof; synthetic profile insufficient"),
    ("audit", ("vgar://audit/log",), "TV1", ("L6-3","L6-5"), "audit",
     "Actual current run/task audit context and private audit root", "Bind existing reader and bounded cursor pages", "Redaction, complete records, cross-run denial"),
    ("prompt", ("repair_with_graph_context",), "TV1", ("L6-4",), "prompt",
     "Template implemented; external host still needs get_prompt validation", "Use existing deterministic prompt, no grant or model in renderer", "Two messages/seven steps and safe data separation"),
)


def dependency_rows(observed):
    require(isinstance(observed.get("servers"), dict) and isinstance(observed.get("implementations"), dict), "Invalid bootstrap observation")
    records = []
    for server in ("graph", "execution"):
        state = observed["servers"].get(server)
        require(isinstance(state, dict) and isinstance(state.get("registry"), list), "Invalid registry observation")
        for record in state["registry"]:
            require(isinstance(record, dict) and type(record.get("synthetic")) is bool
                    and isinstance(record.get("capabilities"), list)
                    and all(isinstance(c,str) for c in record["capabilities"]), "Invalid provider observation")
            records.append(record)
    rows = []
    for name, consumers, owner, tasks, capability, handoff, integration, gate in CATALOG:
        record = next((r for r in records if capability in r["capabilities"]), None)
        if record:
            status = "SYNTHETIC_ONLY" if record["synthetic"] else "BOUND_UNVERIFIED"
        elif name == "schema":
            status = "SCHEMA_PRESENT_UNVERIFIED" if {"Component","Port"} <= set(observed.get("schema_node_types",[])) else "WAITING_SCHEMA_PROVIDER"
        elif name == "bootstrap":
            status = "IMPLEMENTED_NOT_BOUND"
        elif name == "storage":
            status = "LEGACY_ONLY_WAITING_SCHEMA_PROVIDER"
        elif name == "prompt":
            status = "IMPLEMENTED_EXTERNAL_HOST_NOT_RUN"
        elif name in {"queries", "context", "impact", "audit"}:
            status = "LEGACY_OR_FIXTURE_ONLY_REQUIRES_BINDING"
        elif name == "build" and observed["implementations"].get("graph_jobs"):
            status = "BOUND_UNVERIFIED" if observed["servers"]["graph"].get("graph_jobs") else "IMPLEMENTED_NOT_BOUND"
        else:
            status = "WAITING_PROVIDER"
        rows.append({"id":name,"consumers":list(consumers),"capability":capability,"status":status,"owner":owner,
                     "tasks":list(tasks),"evidence":["bootstrap.json", "inputs.json"],
                     "handoff":handoff,"tv1_integration":integration,"gate":gate,
                     "scope":"legacy or unverified; rich production not accepted"})
    return rows


def client_dependencies(clients):
    return [{"id":name,"consumers":[consumer],"capability":"external_client","status":clients[name]["status"],
             "owner":"TV1","tasks":["L6-8"],"evidence":["clients.json"],"handoff":handoff,
             "tv1_integration":"Use a separate operator-rendered config; no global settings or automatic grants",
             "gate":gate,"scope":"NOT_RUN_OFFLINE"}
            for name,consumer,handoff,gate in (
                ("inspector","Inspector modern/legacy","Select/pin/install a revision supporting documented protocol eras in a separate approved step",
                 "Actual Inspector modern+legacy calls; protocol/version receipts, not SDK replacement"),
                ("claude","Claude Code tools/resources/prompt","CLI found is not auth/account/protocol/isolation acceptance; check in a separate authorized step",
                 "Real external-host discover/call/read/get_prompt and denied/authorized fixture permissions"))]


def assess(rows, clients, *, local_checks):
    require(local_checks in {"PASS", "FAIL"}, "Invalid local check state")
    blocked = any(row["status"] != "VERIFIED_PRODUCTION_SCOPE" for row in rows)
    blocked |= clients.get("inspector", {}).get("status") != "VERIFIED_FOR_EXTERNAL_VALIDATION"
    blocked |= clients.get("claude", {}).get("status") != "VERIFIED_FOR_EXTERNAL_VALIDATION"
    status = "ERROR" if local_checks == "FAIL" else "PARTIAL" if blocked else "READY_FOR_EXTERNAL_VALIDATION"
    return {"status":status,"exit_code":1 if status == "ERROR" else 2 if blocked else 0,
            "preflight_completed":True,"local_checks":local_checks,"external_host_integration":"NOT_RUN",
            "inspector_smoke":"NOT_RUN_OFFLINE","claude_session":"NOT_RUN_OFFLINE","full_chain":"NOT_RUN",
            "full_L6_8":"NOT_COMPLETE","production_provider_acceptance":False}


def render_dependencies(rows):
    text = ["# Dependency L6-8 — kết quả quan sát, không phải chữ ký nghiệm thu", "",
            "Code đã có, binding đã có và production đã kiểm chứng là ba mức riêng. TV1/TV2/TV3 theo Final_Task, không phải M1/M2/M3 cũ.", "",
            "| Capability/consumer | Trạng thái | Chủ trì / task | Cần bàn giao | TV1 tích hợp | Gate đóng |", "|---|---|---|---|---|---|"]
    for row in rows:
        fields = [", ".join(row["consumers"]),row["status"],row["owner"]+" / "+", ".join(row["tasks"]),row["handoff"],row["tv1_integration"],row["gate"]]
        text.append("| "+" | ".join(x.replace("|","/").replace("\n"," ") for x in fields)+" |")
    text += ["", "Evidence: bootstrap.json, inventory.json và wire receipts. Provider mới chưa bind không được kết luận rằng mọi code legacy của thành viên chưa tồn tại.", ""]
    return "\n".join(text)


def protected_inputs():
    names = subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=ROOT,
                                   env={**os.environ,"GIT_OPTIONAL_LOCKS":"0"}).decode().split("\0")
    files = [ROOT/name for name in names if name and (ROOT/name).is_file()]
    files.append(ROOT/".git/index")
    # Prior acceptance artifacts are intentionally Git-ignored. Protect these
    # known roots explicitly; never recurse through linked directories.
    for group in ("contract","runtime","security","tools","resources","prompts","storage","graph_jobs"):
        folder = no_links(ROOT/"results/mcp_server"/group)
        if folder.is_dir():
            for parent, directories, entries in os.walk(folder,followlinks=False):
                for name in directories+entries:
                    item = no_links(Path(parent)/name)
                    if item.is_file():
                        files.append(item)
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(set(files))}


def _run(command, output, label, timeout):
    # Fixed helper actions only. Helper clears inherited env before imports/spawn.
    record = run_bounded(tuple(command),output,timeout,output_cap=4*1024*1024,
        environment={"PYTHONPATH":str(ROOT/"src"),"PYTHONUTF8":"1","PYTHONDONTWRITEBYTECODE":"1",
                     "PYTHON_DOTENV_DISABLED":"1","GIT_OPTIONAL_LOCKS":"0","VGAR_GRAPH_BACKEND":"sqlite",
                     "VGAR_GRAPH_DATABASE":_graph_env("VGAR_GRAPH_DATABASE"),
                     "VGAR_REPOSITORY_ROOT":_graph_env("VGAR_REPOSITORY_ROOT"),
                     "VGAR_MCP_AUDIT_LOG":str(output/(label+"-audit.jsonl"))})
    dump(output/(label+"-command.json"),record)
    require(record["complete"] and record["exit_code"] == 0, "Preflight subprocess failed: "+label)
    return record


def inspect_clients(output):
    result = {"claude":{"status":"NOT_FOUND_IN_CHECKED_LOCATIONS","auth":"NOT_CHECKED_OFFLINE","session":"NOT_RUN"},
              "inspector":{"status":"NOT_FOUND_IN_CHECKED_LOCATIONS","version":"NOT_SELECTED_OFFLINE","checked":[]},
              "node":{},"npm":{}}
    for name, executable in (("node",shutil.which("node")),("npm",shutil.which("npm.cmd") or shutil.which("npm"))):
        if executable:
            record = run_bounded((executable,"--version"),output,15,output_cap=65536)
            result[name] = {"executable":executable,"version":record["stdout"].strip() if record["complete"] and record["exit_code"] == 0 else None}
        else:
            result[name] = {"executable":None,"version":None}
    candidates = [Path.home()/".local/bin/claude.exe"]
    if shutil.which("claude"):
        candidates.append(Path(shutil.which("claude")))
    result["claude"]["checked"] = [str(p) for p in candidates]
    for path in candidates:
        if path.is_file():
            checks = [run_bounded(command,output,15,output_cap=131072) for command in client_probe_commands(path)]
            require(all(r["complete"] and r["exit_code"] == 0 for r in checks), "Claude version/help probe failed")
            result["claude"].update(status="CLI_FOUND",executable=str(path),version=checks[0]["stdout"].strip(),
                flags={flag:flag in checks[1]["stdout"] for flag in ("--mcp-config","--strict-mcp-config","--permission-mode")})
            break
    packages = [ROOT/"node_modules/@modelcontextprotocol/inspector/package.json",
                Path(os.getenv("APPDATA",str(Path.home()/"AppData/Roaming")))/"npm/node_modules/@modelcontextprotocol/inspector/package.json"]
    cache = Path(os.getenv("LOCALAPPDATA",str(Path.home()/"AppData/Local")))/"npm-cache/_npx"
    if cache.is_dir():
        directories = sorted(cache.iterdir())
        result["inspector"]["search_truncated"] = len(directories)>200
        packages += [p/"node_modules/@modelcontextprotocol/inspector/package.json" for p in directories[:200] if p.is_dir()]
    for path in packages:
        result["inspector"]["checked"].append(str(path))
        no_links(path)
        if path.is_file():
            package = json.loads(path.read_text(encoding="utf-8"))
            result["inspector"].update(status="PACKAGE_FOUND_NOT_EXECUTED",version=package.get("version"),path=str(path))
            break
    return result


def _signature(schema, signature):
    if signature == "candidates: RankRequest candidates":
        # H1's sealed prose predates the implemented public list adapter. Keep
        # the oracle unchanged; recognize only this exact descriptive entry.
        require(schema.get("properties",{}).get("candidates",{}).get("type") == "array", "Rank candidates must be an array")
        signature = "candidates: list[dict]"
    function = ast.parse("def f("+signature+"): pass").body[0]
    expected = {a.arg for a in function.args.args}
    required = {a.arg for a in function.args.args[:len(function.args.args)-len(function.args.defaults)]}
    require(set(schema.get("properties",{})) == expected and set(schema.get("required",[])) == required,
            "Wire signature/schema mismatch")


def consume_runtime(root):
    summary = read_receipt(root,"summary.json")
    inventory = read_receipt(root,"runtime-inventory.json")
    require(summary.get("status") == "PASS" and inventory.get("status") == "PASS", "Runtime failed")
    require(str(inventory.get("sdk","")).startswith("2."),"SDK2 server required")
    require(not inventory.get("forbidden_packages") and not inventory.get("forbidden_imports"),"Runtime not isolated")
    oracle = json.loads((ROOT/"tests/fixtures/mcp_server/expected_contract.json").read_text(encoding="utf-8"))
    resources = json.loads((ROOT/"tests/fixtures/mcp_server/resource_contract.json").read_text(encoding="utf-8"))
    prompt = json.loads((ROOT/"tests/fixtures/mcp_server/prompt_contract.json").read_text(encoding="utf-8"))
    expected = {(s,m) for s in ("graph","repository","execution") for m in ("2026-07-28","legacy")}
    actual, observations = set(), []
    for row in summary.get("wire",[]):
        key = (row.get("server"),row.get("requested_mode"))
        require(key in expected and key not in actual,"Duplicate/unexpected runtime lane")
        actual.add(key)
        wire = read_receipt(root,row["receipt"])
        record = read_receipt(root,(Path(row["receipt"]).parent/"command.json").as_posix())
        require(record.get("complete") is True and type(record.get("exit_code")) is int
                and record["exit_code"] == 0 and wire.get("status") == "PASS", "Wire command failed")
        require(wire.get("protocol") == row.get("protocol") and wire.get("protocol"),"Protocol receipt mismatch")
        if key[1] == "2026-07-28":
            require(wire["protocol"] == "2026-07-28","Modern protocol not negotiated")
        else:
            require(wire["protocol"] in {"2025-11-25","2025-06-18","2024-11-05"},"Legacy protocol not negotiated")
        tools = wire.get("tools",[])
        relevant = [r for r in oracle["legacy_surface"]+oracle["core_tools"] if r["server"] == key[0]]
        require(len(tools) == len({t["name"] for t in tools})
                and {t["name"] for t in tools} == {r["name"] for r in relevant},"Tool inventory mismatch")
        for tool in tools:
            item = next(r for r in relevant if r["name"] == tool["name"])
            _signature(tool.get("inputSchema",tool.get("input_schema",{})),item["signature"])
        require(wire.get("calls"),"No real tool calls")
        for call in wire["calls"]:
            require(call.get("tool") in {t["name"] for t in tools},"Unregistered tool in call receipt")
            response = call["response"]
            require(response.get("status") in {"PASS","ERROR"} and isinstance(response.get("metadata"),dict),"Invalid tool envelope")
            elapsed = response["metadata"].get("duration_ms")
            require(not isinstance(elapsed,bool) and isinstance(elapsed,(int,float)) and math.isfinite(elapsed) and elapsed>=0,"Invalid duration")
            if response["status"] == "ERROR":
                require(isinstance(response.get("error"),dict),"Missing error evidence")
        require(any(c["response"]["status"] == "ERROR" for c in wire["calls"]),"No negative/denial receipt")
        def passed(name, wire=wire):
            found = [c["response"]["data"] for c in wire["calls"]
                     if c["tool"] == name and c["response"]["status"] == "PASS"]
            require(len(found) == 1 and isinstance(found[0],dict),"Missing successful "+name+" receipt")
            return found[0]
        def denied(name, code, wire=wire):
            require(any(c["tool"] == name and c["response"].get("error",{}).get("code") == code
                        for c in wire["calls"] if c["response"]["status"] == "ERROR"),"Missing denial "+code)
        if key[0] == "graph":
            symbols = passed("search_symbols").get("symbols",[])
            require(symbols and symbols[0].get("name") == "login","Missing actual graph search data")
            anchor = symbols[0]["symbol_id"]
            for relation in ("callers","callees"):
                data = passed("get_"+relation)
                require(data.get("symbol_id") == anchor and data.get("depth") == 1
                        and isinstance(data.get(relation),list),"Graph traversal data mismatch")
            denied("get_callers","NODE_NOT_FOUND")
            denied("search_symbols","INVALID_QUERY")
            require(set(wire.get("resources",[])) == set(resources["canonical"]+resources["legacy_aliases"]),"Resource inventory mismatch")
            messages = wire.get("rendered_prompt",{}).get("messages",[])
            require(wire.get("prompt_gate") == "PASS" and len(messages)==2
                    and all(message.get("role") == "user" for message in messages)
                    and messages[0]["content"]["text"] == prompt["instructions"]
                    and messages[1]["content"]["text"] == prompt["expected_data_text"],"Actual get_prompt oracle mismatch")
            validate_graph_reads(wire,anchor)
        elif key[0] == "repository":
            require(passed("health").get("server") == "repository","Repository health mismatch")
            require("def login" in passed("read_file").get("content",""),"Missing repository read data")
            denied("read_file","PATH_OUTSIDE_ROOT")
        elif key[0] == "execution":
            require(passed("health").get("server") == "execution","Execution health mismatch")
            data = passed("run_pytest")
            require(data.get("verdict") == "PASS" and type(data.get("exit_code")) is int
                    and data["exit_code"] == 0,"Fixture pytest did not pass")
            denied("run_pytest","SELECTOR_REJECTED")
        observations.append({"server":key[0],"mode":key[1],"protocol":wire["protocol"],"tool_count":len(tools),
            "calls":len(wire["calls"]),"fixture_scope":True,"receipt":row["receipt"],"receipt_hash":sha(resolve_read_path(root,row["receipt"]).read_bytes())})
    require(actual == expected,"Missing runtime lanes")
    return {"status":"PASS","tools":16,"core_tools":11,"canonical_resources":8,"resource_aliases":1,"prompts":1,
            "production_acceptance":False,"lanes":observations}


def validate_graph_reads(wire, anchor):
    from urllib.parse import quote

    reads = wire.get("resource_reads",[])
    require(len(reads) == 3 and all(isinstance(r.get("data"),dict) and r["data"] for r in reads),
            "Missing graph resource data")
    expected = {"vgar://repo/summary","vgar://graph/node/"+quote(anchor,safe=""),
                "vgar://graph/subgraph/"+quote(anchor,safe="")}
    require({r.get("uri") for r in reads} == expected,"Graph resource URI mismatch")
    payloads = {r["uri"]:r["data"] for r in reads}
    summary = payloads["vgar://repo/summary"]
    require(str(summary.get("graph_version","")).startswith("sha256:")
            and type(summary.get("node_count")) is int and summary["node_count"]>0,"Graph resource summary invalid")
    node = payloads["vgar://graph/node/"+quote(anchor,safe="")]
    subgraph = payloads["vgar://graph/subgraph/"+quote(anchor,safe="")]
    require(node.get("repo",{}).get("node_id") == anchor and subgraph.get("anchor_id") == anchor
            and subgraph.get("depth") == 2 and isinstance(subgraph.get("edges"),list)
            and any(n.get("repo",{}).get("node_id") == anchor for n in subgraph.get("nodes",[])),
            "Graph resource anchor mismatch")


def consume_graph(root, expected_profile):
    from dataclasses import asdict

    from vgar.contracts.schema import validate_graph_document
    from vgar.graph.storage_capabilities import SnapshotGraphStore, StorageProfile
    from vgar.mcp.proposal.contracts import BuildResult

    profile = StorageProfile(**expected_profile,validator=validate_graph_document)
    header = read_receipt(root,"summary.json")
    require(header.get("status") == "PASS" and header.get("provider") == "real-static-builder"
            and header.get("fixture_inputs") is True,"Graph chain header invalid")
    lanes, modes = [], set()
    for lane in header.get("lanes",[]):
        require(lane.get("mode") in {"2026-07-28","legacy"} and lane["mode"] not in modes,"Graph lane mismatch")
        modes.add(lane["mode"])
        wire = read_receipt(root,lane["receipt"])
        require(wire.get("status") == "PASS" and wire.get("provider") == "real-static-builder"
                and wire.get("fixture_inputs") is True and wire.get("unauthorized_repo_denied") is True,"Graph wire proof invalid")
        require(wire.get("mode") == lane["mode"] and wire.get("protocol") == lane.get("protocol"),"Graph protocol binding mismatch")
        base = resolve_read_path(root,lane["receipt"]).parent
        cache_modes = []
        for call in wire.get("calls",[]):
            result = BuildResult.model_validate(call["result"])
            require(result.published is True and result.capabilities == ("legacy_static_python",)
                    and len(result.evidence)==1,"Graph result capabilities/evidence invalid")
            job = read_receipt(base,call["receipt"],expected_hash=result.evidence[0].sha256)
            require(job.get("binding") == result.binding.model_dump(mode="json") and job.get("status") == "PASS"
                    and job.get("published") is True and job.get("cleanup") == "PASS","Graph job binding/status mismatch")
            require(call.get("source_unchanged") is True and call.get("source_hash") == result.binding.source_hash,"Graph source proof mismatch")
            manifest = resolve_read_path(base,call["manifest"])
            require(sha(manifest.read_bytes()) == job.get("manifest_hash"),"Graph manifest hash mismatch")
            database = manifest.parent/"graph.db"
            before = sha(database.read_bytes())
            store = SnapshotGraphStore(manifest,graph_version=result.result_snapshot_hash,profiles=(profile,))
            require(store.identity.snapshot_id == job.get("storage_snapshot_id")
                    and asdict(store.identity) == job.get("storage_identity")
                    and store.identity.source_inventory_hash == result.binding.source_hash,"Graph storage identity mismatch")
            require(call.get("resource",{}).get("graph_version") == result.result_snapshot_hash,"Graph resource binding mismatch")
            store.get_repository_summary()
            require(sha(database.read_bytes()) == before,"Graph DB mutated during consumer read")
            cache_modes.append(job.get("cache_mode"))
        require(cache_modes == ["COLD_BUILD","SNAPSHOT_REUSE","WARM_UPDATE"],"Missing actual cold/reuse/warm receipts")
        lanes.append({"mode":lane["mode"],"protocol":wire["protocol"],"cache_modes":cache_modes,"consumer":"PASS"})
    require(modes == {"2026-07-28","legacy"},"Graph sidecars/lanes missing")
    return {"status":"PASS","fixture_inputs":True,"provider":"real-static-builder","production_full_chain":False,"lanes":lanes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight",action="store_true",required=True)
    parser.add_argument("--client-python",required=True)
    parser.add_argument("--server-python",required=True)
    parser.add_argument("--output-root",required=True)
    args = parser.parse_args(argv)
    inputs = (ROOT/"src",ROOT/"scripts",ROOT/"tests",ROOT/"configs",ROOT/"artifacts")
    out = validate_output(args.output_root,inputs=inputs)
    require(Path(args.client_python).is_file() and Path(args.server_python).is_file(),"Interpreter missing")
    before = protected_inputs()
    out.mkdir(parents=True,exist_ok=False)
    env = {**os.environ,"GIT_OPTIONAL_LOCKS":"0"}
    dump(out/"inputs.json",{"hashes":before,"argv":vars(args),"offline":True})
    for name, command in (("status.txt",["status","--short"]),("unstaged.txt",["diff","--binary"]),("staged.txt",["diff","--cached","--binary"]),("head.txt",["rev-parse","HEAD"])):
        (out/name).write_bytes(subprocess.check_output(["git",*command],cwd=ROOT,env=env))
    result = None
    try:
        worker = str(Path(__file__).with_name("_preflight_worker.py"))
        probe = _run([args.server_python,"-B",worker,"probe"],out,"bootstrap",45)
        observed = json.loads(probe["stdout"])
        denied = observed.get("denials",{})
        require(denied.get("worker_spawned") is False and type(denied.get("operation_output_entries")) is int
                and denied["operation_output_entries"] == 0 and denied.get("path") == "CAPABILITY_UNAVAILABLE"
                and denied.get("verification",{}).get("status") == "NOT_RUN","Fail-closed probe inconsistent")
        dump(out/"bootstrap.json",observed)
        rows = dependency_rows(observed)
        dump(out/"dependencies.json",{"rows":rows,"local_checks":"PENDING"})
        (out/"dependencies.md").write_text(render_dependencies(rows),encoding="utf-8")
        runtime = out/"runtime"
        _run([args.server_python,"-B",worker,"runtime","--client-python",args.client_python,
              "--server-python",args.server_python,"--output-root",str(runtime),"--require-no-langchain"],out,"runtime",600)
        inventory = consume_runtime(runtime)
        dump(out/"inventory.json",inventory)
        _run([args.client_python,"-B",worker,"graph","--server-python",args.server_python,
              "--output-root",str(out/"graph-chain")],out,"graph-chain",180)
        graph = consume_graph(out/"graph-chain",observed["fixture_profile"])
        dump(out/"graph-consumer.json",graph)
        client_probe = _run([args.server_python,"-B",worker,"clients"],out,"clients",60)
        clients = json.loads(client_probe["stdout"])
        dump(out/"clients.json",clients)
        rows += client_dependencies(clients)
        dump(out/"dependencies.json",{"rows":rows,"fixture_graph_gate":"graph-chain/summary.json"})
        (out/"dependencies.md").write_text(render_dependencies(rows),encoding="utf-8")
        result = assess(rows,clients,local_checks="PASS")
        result.update(inventory="inventory.json",dependencies="dependencies.md",graph_chain="graph-chain/summary.json")
        templates = out/"config-templates"
        templates.mkdir()
        for name in ("inspector-modern.template.json","inspector-legacy.template.json","claude-code.template.json","preflight-templates.json"):
            source = no_links(ROOT/"configs/mcp_server"/name)
            json.loads(source.read_bytes())
            shutil.copy2(source,templates/name)
        (out/"report.md").write_text("# L6-8 offline preflight\n\nStatus: **"+result["status"]+"**; exit "+str(result["exit_code"])+
            ". Scripted SDK/runtime and real legacy builder on fixture are local evidence, not Inspector/Claude/full production integration.\n\n"+
            "Inventory: 20 tools (11 core), 8 canonical resources + 1 alias, 1 prompt. See inventory.json for actual protocol lanes.\n\n"+
            "Clients: Node "+str(clients["node"].get("version"))+", npm "+str(clients["npm"].get("version"))+
            ", Claude "+str(clients["claude"].get("version"))+"; Inspector "+clients["inspector"]["status"]+
            ". Authentication is NOT_CHECKED_OFFLINE. No agent/model/client session was launched.\n\n"+
            "Dependency ownership and closing gates: [dependencies.md](dependencies.md). Configs are TEMPLATE_NOT_EXECUTED; resolve only from trusted operator bindings.\n",encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - preserve safe terminal error, never hide as a missing provider
        result = {"status":"ERROR","exit_code":1,"error_type":type(exc).__name__,"preflight_completed":False,
                  "full_L6_8":"NOT_COMPLETE","external_host_integration":"NOT_RUN"}
        (out/"error.txt").write_text(type(exc).__name__+": "+str(exc)+"\n",encoding="utf-8")
    finally:
        after = protected_inputs()
        changed = [p for p,value in before.items() if after.get(p) != value]
        added = sorted(set(after)-set(before))
        if changed or added:
            result = {"status":"ERROR","exit_code":1,"error_type":"InputIntegrityError","preflight_completed":False,"full_L6_8":"NOT_COMPLETE"}
        dump(out/"preservation.json",{"status":"FAIL" if changed or added else "PASS","checked":len(before),"changed":changed,"added":added})
        dump(out/"summary.json",result)
        dump(out/"artifact_hashes.json",{p.relative_to(out).as_posix():sha(p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file() and p.name!="artifact_hashes.json"})
    print(json.dumps(result,ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
