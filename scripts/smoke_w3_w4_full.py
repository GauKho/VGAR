"""W3-W4 full-system smoke test (deterministic, NO LLM).

Flow:
  [1] M1  build graph (tree-sitter + Python static bindings) -> JSON -> SQLite
  [2] M3  MCP client loads graph/repository/execution tools
  [3] M1->M3  graph tools + resources (search / callers / callees / summary / node / subgraph)
  [4] M2  disposable workspace + baseline pytest (must FAIL) + source hash
  [5] M3->M2  MCP apply_patch -> MCP run_pytest (must PASS) + path-escape rejected
  [6] M2  EvidenceBundle written, source repo untouched
  [7] M3  audit log contains the graph tool calls

Run (from repo root, after `pip install -e '.[dev]'`):
    python scripts/smoke_w3_w4_full.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SAMPLE_REPO = ROOT / "tests" / "fixtures" / "sample_repo"
FAILING_REPO = ROOT / "tests" / "fixtures" / "m2" / "failing_repo"
SELECTOR = "tests/test_demo.py::test_answer"

_results: list[tuple[str, bool, str]] = []
_warnings: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record one assertion; fail fast so the first broken stage is obvious."""
    _results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise SystemExit(f"SMOKE FAILED at: {name} {detail}")


def soft_check(name: str, ok: bool, detail: str, strict: bool) -> None:
    """Known-gap check: WARN by default, hard FAIL with --strict-resources."""
    if ok or strict:
        check(name, ok, detail)
    else:
        _warnings.append(name)
        print(f"  [WARN] {name} - KNOWN GAP: {detail}")


def stage(title: str) -> None:
    print(f"\n== {title}")


async def run(query: str, keep: bool, strict_resources: bool) -> None:
    started = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix="vgar-smoke-full-"))
    db_path = work / "graph.db"
    json_path = work / "graph.json"
    audit_path = work / "mcp_audit.jsonl"
    m2_temp = work / "m2-temp"
    evidence_dir = work / "evidence"

    # Env must be set BEFORE the MCP client spawns the graph server subprocess.
    os.environ["VGAR_GRAPH_BACKEND"] = "sqlite"
    os.environ["VGAR_GRAPH_DATABASE"] = str(db_path)
    os.environ["VGAR_MCP_AUDIT_LOG"] = str(audit_path)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore
    from vgar.contracts.evidence import EvidenceBundle, VerificationResult
    from vgar.mcp import create_mcp_client
    from vgar.mcp.registry import W3_W4_REQUIRED_GRAPH_TOOLS, validate_required_tools
    from vgar.mcp.result_parser import parse_mcp_json_result
    from vgar.repair.evidence_writer import begin_run, finish_run
    from vgar.repair.test_runner import run_tests
    from vgar.repair.workspace import create_workspace, fingerprint_source

    # ------------------------------------------------------------ [1] graph
    stage("1. M1 graph build -> SQLite")
    document = PythonGraphBuilder(
        repo_key="smoke/sample-repo", repository_revision="smoke-rev"
    ).build(SAMPLE_REPO)
    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    store = SQLiteGraphStore(db_path)
    store.ingest(document)
    summary = SQLiteGraphService(store).get_repository_summary()
    check("graph has nodes", summary.node_count > 0, f"nodes={summary.node_count}")
    check("graph has edges", summary.edge_count > 0, f"edges={summary.edge_count}")
    check("graph has Function nodes", summary.node_counts_by_type.get("Function", 0) > 0)
    check("graph has CONTAINS edges", summary.edge_counts_by_type.get("CONTAINS", 0) > 0)

    # ------------------------------------------------------------ [2] MCP
    stage("2. MCP client + tool discovery")
    client = create_mcp_client()
    tools = await client.get_tools()
    by_name = {t.name: t for t in tools}
    validate_required_tools(tools, W3_W4_REQUIRED_GRAPH_TOOLS)
    check("graph tools registered", True, ", ".join(sorted(W3_W4_REQUIRED_GRAPH_TOOLS)))
    for name in ("repository_read_file", "repository_apply_patch", "execution_run_pytest"):
        check(f"tool {name} registered", name in by_name)

    async def call(tool: str, args: dict) -> dict:
        raw = await by_name[tool].ainvoke(args)
        try:
            return parse_mcp_json_result(raw)
        except (ValueError, TypeError):
            # handle_tool_errors=True turns server exceptions into plain text.
            raise SystemExit(f"SMOKE FAILED: MCP tool {tool!r} returned non-JSON (server-side error?):\n{raw!r}"[:1500])

    # ------------------------------------------------------------ [3] graph via MCP
    stage("3. Graph tools + resources via MCP")
    search = await call("graph_search_symbols", {"query": query, "limit": 10})
    check("search backend is sqlite", search["metadata"]["backend"] == "sqlite")
    check(f"search {query!r} returns symbols", len(search["data"]["symbols"]) > 0)
    symbol_id = search["data"]["symbols"][0]["symbol_id"]

    callers = await call("graph_get_callers", {"symbol_id": symbol_id, "depth": 1})
    callees = await call("graph_get_callees", {"symbol_id": symbol_id, "depth": 1})
    check("callers response OK", callers["status"] == "PASS" and "callers" in callers["data"])
    check("callees response OK", callees["status"] == "PASS" and "callees" in callees["data"])
    print(f"     symbol={symbol_id} callers={len(callers['data']['callers'])} callees={len(callees['data']['callees'])}")

    # Resources (vgar://...) - read through the graph server connection.
    async def read_resource(uri: str) -> dict:
        blobs = await client.get_resources("graph", uris=[uri])
        return json.loads(blobs[0].as_string())

    res_summary = await read_resource("vgar://repo/summary")
    check("resource repo/summary matches DB", res_summary["node_count"] == summary.node_count)
    # Node IDs contain '/' and ':' -> must be percent-encoded in the URI, and the
    # server must unquote them. graph_server.py currently does NOT unquote.
    encoded = quote(symbol_id, safe="")
    try:
        res_node = await read_resource(f"vgar://graph/node/{encoded}")
        node_ok = set(res_node) == {"repo"} and res_node["repo"]["node_id"] == symbol_id
        detail = "node resource wrapped by 'repo'"
    except Exception as exc:  # noqa: BLE001 - transport errors vary by SDK version
        node_ok, detail = False, f"vgar://graph/node/{{id}} failed ({type(exc).__name__}); graph_server must unquote node_id"
    soft_check("resource node by real node_id", node_ok, detail, strict_resources)
    try:
        res_sub = await read_resource(f"vgar://graph/subgraph/{encoded}")
        sub_ok, detail = len(res_sub["nodes"]) >= 1, "subgraph has anchor node"
    except Exception as exc:  # noqa: BLE001
        sub_ok, detail = False, f"vgar://graph/subgraph/{{id}} failed ({type(exc).__name__}); graph_server must unquote node_id"
    soft_check("resource subgraph by real node_id", sub_ok, detail, strict_resources)

    # ------------------------------------------------------------ [4] M2 baseline
    stage("4. M2 disposable workspace + baseline (expected FAIL)")
    source_hash = fingerprint_source(FAILING_REPO)
    with create_workspace(FAILING_REPO, m2_temp) as lease:
        check("workspace outside source repo", FAILING_REPO.resolve() not in lease.path.parents)
        handle = begin_run(
            evidence_dir, task_id="smoke-w3w4-full", source_repo=FAILING_REPO,
            source_hash_before=lease.source_hash_before, worktree_id=lease.worktree_id,
            argv=[sys.executable, "-m", "pytest", SELECTOR], cwd=lease.path, timeout_seconds=60,
        )
        baseline = run_tests(lease.path, (SELECTOR,), 60)
        check("baseline pytest FAIL", baseline.status == "FAIL", f"exit={baseline.exit_code}")
        check("baseline reason TEST_FAILED", baseline.reason is not None and baseline.reason.code == "TEST_FAILED")

        # -------------------------------------------------------- [5] MCP patch + verify
        stage("5. MCP apply_patch -> run_pytest (expected PASS)")
        repo_arg = str(lease.path)

        read = await call("repository_read_file", {"repo_path": repo_arg, "path": "src/demo.py"})
        check("read_file returns content", "return 0" in read["content"])

        patch = await call("repository_apply_patch", {
            "repo_path": repo_arg, "path": "src/demo.py",
            "old_text": "return 0", "new_text": "return 42",
        })
        check("apply_patch PASS", patch["status"] == "PASS", patch.get("error", ""))
        check("patch diff recorded", "+    return 42" in patch["patch_diff"])

        retry = await call("repository_apply_patch", {
            "repo_path": repo_arg, "path": "src/demo.py",
            "old_text": "return 0", "new_text": "return 42",
        })
        check("stale old_text rejected", retry["status"] == "FAIL")

        escaped = False
        try:
            raw = await by_name["repository_apply_patch"].ainvoke({
                "repo_path": repo_arg, "path": "../outside.py", "old_text": "a", "new_text": "b",
            })
            text = json.dumps(raw, default=str)
            escaped = "Unsafe" not in text and "escapes" not in text and "rror" not in text
        except Exception:
            escaped = False  # raised -> rejected, which is the desired outcome
        check("path traversal rejected", not escaped)

        verify = await call("execution_run_pytest", {
            "repo_path": repo_arg, "selector": SELECTOR, "timeout_seconds": 60,
        })
        check("MCP run_pytest PASS", verify["status"] == "PASS",
              f"exit={verify.get('exit_code')} {verify.get('error') or verify.get('stdout', '')[-300:]}")

        # -------------------------------------------------------- [6] evidence
        stage("6. EvidenceBundle + source immutability")
        final = run_tests(lease.path, (SELECTOR,), 60)
        check("independent verification PASS", final.status == "PASS")
        after_hash = fingerprint_source(lease.path)
        bundle = EvidenceBundle(
            run_id=handle.run_id, task_id="smoke-w3w4-full", source_repo=str(FAILING_REPO),
            source_hash_before=lease.source_hash_before, source_hash_after=after_hash,
            worktree_id=lease.worktree_id, artifact_path=str(handle.path),
            verification=VerificationResult(patch_applied=True, tests=final),
            metadata={"stage": "W3-W4-full-smoke", "baseline_status": baseline.status,
                      "graph_symbol": symbol_id},
        )
        evidence_path = finish_run(handle, final, source_hash_after=after_hash, bundle=bundle)
        saved = json.loads(evidence_path.read_text(encoding="utf-8"))
        check("evidence complete", saved["complete"] is True and saved["status"] == "PASS")
        check("evidence has bundle", saved["evidence_bundle"]["verification"]["patch_applied"] is True)
        check("workspace hash changed (patch applied)", after_hash != lease.source_hash_before)

    check("source repo untouched", fingerprint_source(FAILING_REPO) == source_hash)
    check("workspace cleaned up", not lease.path.exists())

    # ------------------------------------------------------------ [7] audit
    stage("7. MCP audit log")
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line]
    tools_logged = {e["payload"].get("tool") for e in events if e["event_type"] == "tool_call"}
    resources_logged = {e["payload"].get("resource") for e in events if e["event_type"] == "resource_read"}
    check("audit has graph tool calls",
          {"search_symbols", "get_callers", "get_callees"} <= tools_logged, str(sorted(tools_logged)))
    check("audit has resource reads", "vgar://repo/summary" in resources_logged)
    check("audit events carry backend", all(e["payload"].get("backend") == "sqlite" for e in events))

    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\nW3-W4 FULL SMOKE PASS ({passed}/{len(_results)} checks, {len(_warnings)} known-gap warning(s), {time.monotonic() - started:.1f}s)")
    print(f"artifacts: {work}" if keep else "")
    if not keep:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--query", default="login", help="Symbol that exists in tests/fixtures/sample_repo")
    parser.add_argument("--keep", action="store_true", help="Keep graph/audit/evidence artifacts")
    parser.add_argument("--strict-resources", action="store_true",
                        help="Fail (instead of WARN) when node/subgraph resources cannot be read")
    args = parser.parse_args()
    asyncio.run(run(args.query, args.keep, args.strict_resources))
