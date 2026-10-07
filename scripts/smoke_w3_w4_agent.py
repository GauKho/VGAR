"""W3-W4 agent smoke: query -> LLM/orchestrator -> MCP tools -> verified patch.

Unlike smoke_w3_w4_full.py (which calls MCP tools directly), here an LLM decides
which tools to call. Orchestration is the production path:
    langchain.agents.create_agent  (LangGraph model<->ToolNode loop)
      -> langchain-mcp-adapters tools -> graph / repository / execution MCP servers

Two model modes:
  --model scripted  deterministic test double (no GPU/download). Proves the ORCHESTRATOR:
                    tool binding, ToolNode dispatch, MCP round-trip, message plumbing.
  --model hf        real local model via vgar.agents.core.create_core_agent(). Proves the LLM
                    can pick tools and produce valid arguments.
If `scripted` passes but `hf` fails, the bug is in the model (prompt / tool-call format),
not in MCP or the orchestrator.

Run (repo root, after `pip install -e '.[dev]'`):
    python scripts/smoke_w3_w4_agent.py --model scripted
    python scripts/smoke_w3_w4_agent.py --model hf --query "Fix failing test tests/test_demo.py::test_answer"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import (  # noqa: E402
    AIMessage, BaseMessage, HumanMessage, ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402

FAILING_REPO = ROOT / "tests" / "fixtures" / "m2" / "failing_repo"
SELECTOR = "tests/test_demo.py::test_answer"
DEFAULT_QUERY = f"Fix the failing test {SELECTOR}. Locate the code with the graph tools first."


# --------------------------------------------------------------------------- helpers
def tool_json(msg: ToolMessage) -> dict[str, Any]:
    """ToolMessage.content may be a JSON string or a list of MCP text blocks."""
    content = msg.content
    if isinstance(content, list):
        content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else {"_raw": content}
    except (TypeError, ValueError):
        return {"_raw": str(content)}  # tool error text (handle_tool_errors=True)


def tool_calls_of(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    return [tc for m in messages if isinstance(m, AIMessage) for tc in (m.tool_calls or [])]


# --------------------------------------------------------------------------- scripted model
@dataclass
class ScriptConfig:
    """Fixture-specific knowledge lives ONLY in this test double, never in product code."""
    repo_path: str
    symbol_query: str = "answer"
    old_text: str = "return 0"
    new_text: str = "return 42"
    selector: str = SELECTOR


class ScriptedToolModel(BaseChatModel):
    """Deterministic chat model that emits tool calls like a real LLM would.

    It reads previous ToolMessages (so it reacts to real MCP output) and decides the
    next call: search -> callers -> callees -> read -> patch -> pytest -> final answer.
    """
    cfg: ScriptConfig

    @property
    def _llm_type(self) -> str:
        return "vgar-scripted-tool-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedToolModel":  # noqa: ARG002
        return self  # tools are already known to the script

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ARG002
        results = [m for m in messages if isinstance(m, ToolMessage)]
        step = len(results)
        c = self.cfg

        def call(name: str, args: dict[str, Any]) -> ChatResult:
            msg = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}])
            return ChatResult(generations=[ChatGeneration(message=msg)])

        symbols = (tool_json(results[0]).get("data") or {}).get("symbols", []) if step >= 1 else []
        target = next((s for s in symbols if str(s.get("symbol_id", "")).endswith(f".{c.symbol_query}")),
                      symbols[0] if symbols else {})
        sym_id = target.get("symbol_id", "")
        rel_path = target.get("path", "src/demo.py")

        if step == 0:
            return call("graph_search_symbols", {"query": c.symbol_query, "limit": 10})
        if step == 1:
            return call("graph_get_callers", {"symbol_id": sym_id, "depth": 1})
        if step == 2:
            return call("graph_get_callees", {"symbol_id": sym_id, "depth": 1})
        if step == 3:
            return call("repository_read_file", {"repo_path": c.repo_path, "path": rel_path})
        if step == 4:
            return call("repository_apply_patch", {"repo_path": c.repo_path, "path": rel_path,
                                                   "old_text": c.old_text, "new_text": c.new_text})
        if step == 5:
            return call("execution_run_pytest", {"repo_path": c.repo_path, "selector": c.selector,
                                                 "timeout_seconds": 60})
        final = tool_json(results[-1])
        final_data = final.get("data") or (final.get("error") or {}).get("details") or {}
        text = f"Pytest status from tool: {final.get('status')} (exit={final_data.get('exit_code')})."
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


# --------------------------------------------------------------------------- checks
_n = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _n
    _n += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise SystemExit(f"AGENT SMOKE FAILED at: {name} {detail}")


# --------------------------------------------------------------------------- main
async def run(args: argparse.Namespace) -> None:
    started = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix="vgar-smoke-agent-"))
    audit_path = work / "mcp_audit.jsonl"

    # Env must be set BEFORE MCP servers are spawned (graph server copies os.environ).
    os.environ["VGAR_GRAPH_BACKEND"] = "sqlite"
    os.environ["VGAR_GRAPH_DATABASE"] = str(work / "graph.db")
    os.environ["VGAR_MCP_AUDIT_LOG"] = str(audit_path)
    os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)

    from langchain.agents import create_agent
    from vgar.mcp import create_mcp_client
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_store import SQLiteGraphStore
    from vgar.repair.test_runner import run_tests
    from vgar.repair.workspace import create_workspace, fingerprint_source

    print("\n== 1. Index the repository (graph snapshot of the base revision)")
    doc = PythonGraphBuilder(repo_key="smoke/agent", repository_revision="smoke-rev", use_jedi=True).build(FAILING_REPO)
    SQLiteGraphStore(work / "graph.db").ingest(doc)
    check("graph indexed", len(doc["nodes"]) > 0, f"nodes={len(doc['nodes'])}")

    source_hash = fingerprint_source(FAILING_REPO)
    with create_workspace(FAILING_REPO, work / "ws") as lease:
        from vgar.config.settings import get_settings
        sandboxed = replace(get_settings(), workspace_root=lease.path)
        print("\n== 2. Baseline (must FAIL before the agent acts)")
        baseline = run_tests(lease.path, (SELECTOR,), 60)
        check("baseline FAIL", baseline.status == "FAIL")

        print(f"\n== 3. Build agent (model={args.model})")
        if args.model == "hf":
            # Lazy import: vgar.agents.core pulls torch/transformers at import time.
            from vgar.agents.core import create_core_agent
            agent = await create_core_agent(sandboxed)  # production path with host-granted workspace
        else:
            # Same wiring as create_core_agent(), minus the HF model (no torch needed).
            prompt_file = ROOT / "src" / "vgar" / "agents" / "prompts" / "system.md"
            agent = create_agent(
                model=ScriptedToolModel(cfg=ScriptConfig(repo_path=str(lease.path))),
                tools=await create_mcp_client(sandboxed).get_tools(),
                system_prompt=prompt_file.read_text(encoding="utf-8"),
            )
        check("agent created", agent is not None)

        print("\n== 4. Invoke agent with the query")
        prompt = (f"{args.query}\n\nRepository working copy (use this exact value as `repo_path` in "
                  f"repository_* and execution_* tools): {lease.path}\n"
                  f"Test selector: {SELECTOR}\nNever claim success without execution_run_pytest evidence.")
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]},
                                     config={"recursion_limit": args.max_steps})
        messages: list[BaseMessage] = result["messages"]

        print("\n   --- tool trace ---")
        for m in messages:
            if isinstance(m, AIMessage):
                for tc in m.tool_calls or []:
                    print(f"   -> {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:140]})")
            elif isinstance(m, ToolMessage):
                print(f"   <- {m.name} [{m.status}] {str(m.content)[:110]!r}")
        final_text = next((m.content for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), "")
        print(f"   final: {str(final_text)[:200]!r}\n")

        print("== 5. Orchestration checks")
        names = [tc["name"] for tc in tool_calls_of(messages)]
        check("LLM issued tool calls", len(names) > 0, f"{len(names)} calls")
        check("used graph tool", any(n.startswith("graph_") for n in names))
        check("used repository_read_file", "repository_read_file" in names)
        check("used repository_apply_patch", "repository_apply_patch" in names)
        check("used execution_run_pytest", "execution_run_pytest" in names)
        first_graph = next((i for i, n in enumerate(names) if n.startswith("graph_")), 10**9)
        check("graph used BEFORE patch", first_graph < names.index("repository_apply_patch"))
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        check("no tool returned error status", all(m.status != "error" for m in tool_msgs))
        check("every tool result is parseable JSON", all("_raw" not in tool_json(m) for m in tool_msgs))
        check("every scripted tool envelope PASS", all(tool_json(m).get("status") == "PASS" for m in tool_msgs))
        (work / "agent_messages.json").write_text(
            json.dumps([message.model_dump(mode="json") for message in messages], indent=2, ensure_ascii=False), encoding="utf-8")
        patch_tool = next(tool_json(message) for message in tool_msgs if message.name == "repository_apply_patch")
        (work / "patch.diff").write_text(patch_tool["data"]["patch_diff"], encoding="utf-8")
        check("tool-call count within budget", len(names) <= args.max_tool_calls, f"{len(names)}/{args.max_tool_calls}")

        print("\n== 6. Independent verification (agent's claim is NOT trusted)")
        final_test = run_tests(lease.path, (SELECTOR,), 60)
        check("pytest PASS in workspace", final_test.status == "PASS")
        check("workspace modified", fingerprint_source(lease.path) != lease.source_hash_before)

    check("source repo untouched", fingerprint_source(FAILING_REPO) == source_hash)

    print("\n== 7. Audit log")
    events = [json.loads(l) for l in audit_path.read_text(encoding="utf-8").splitlines() if l]
    logged = {e["payload"].get("tool") for e in events if e["event_type"] == "tool_call"}
    # Require at least one graph tool (agent may skip callers/callees when not needed).
    # The scripted model calls all three; the HF model may use a shorter path.
    graph_tools_logged = {"search_symbols", "get_callers", "get_callees"} & logged
    check(
        "graph tool calls audited",
        len(graph_tools_logged) >= 1,
        f"{sorted(logged)} (graph: {sorted(graph_tools_logged)})",
    )

    print(f"\nW3-W4 AGENT SMOKE PASS ({_n} checks, model={args.model}, {time.monotonic() - started:.1f}s)")
    if args.keep:
        print(f"artifacts: {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", choices=["scripted", "hf"], default="scripted")
    p.add_argument("--query", default=DEFAULT_QUERY, help="Task given to the agent")
    p.add_argument("--max-steps", type=int, default=40, help="LangGraph recursion_limit")
    p.add_argument("--max-tool-calls", type=int, default=30)
    p.add_argument("--keep", action="store_true")
    asyncio.run(run(p.parse_args()))
