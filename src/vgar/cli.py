"""VGAR command line: one entry point for settings, MCP tools and the agent.

    vgar doctor                      # resolved settings, no model loaded
    vgar tools                       # spawn MCP servers, list tools
    vgar index REPO --db graph.db    # build graph snapshot
    vgar run "Fix ..." --repo REPO --selector tests/test_x.py::test_y
    vgar solve "Fix ..." --repo REPO --selector tests/test_x.py::test_y   # workflow with verify/retry
    vgar chat --repo REPO            # interactive session on a disposable copy

Agent commands never touch REPO: they index it, copy it to a temp workspace
and let the agent edit only the copy.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from vgar.observability.phase_logger import emit, new_run_id, phase, summarize

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.callbacks import BaseCallbackHandler

from vgar.agents.runtime import index_repo
from vgar.config.settings import Settings, get_settings


# ----------------------------------------------------------------- shared helpers
@contextmanager
def sandbox(
    repo: Path,
    settings: Settings,
    keep: bool = False,
    *,
    run_id: str | None = None,
):
    """Index `repo`, copy it to a disposable workspace, yield (settings, lease)."""
    from vgar.repair.workspace import create_workspace

    run_id = run_id or new_run_id()
    work = Path(tempfile.mkdtemp(prefix="vgar-cli-"))
    try:
        with phase(
            "index_repository",
            run_id,
            {"repo": str(repo), "graph_db": str(work / "graph.db")},
        ) as log_output:
            nodes = index_repo(repo, work / "graph.db")
            print(f"[index] {nodes} nodes -> {work / 'graph.db'}", flush=True)
            log_output({"node_count": nodes, "graph_db": str(work / "graph.db")})

        sandboxed = replace(settings, graph=replace(settings.graph, backend="sqlite", database=work / "graph.db"))
        with phase(
            "create_workspace",
            run_id,
            {"source_repo": str(repo), "workspace_root": str(work / "ws")},
        ) as log_output:
            with create_workspace(repo, work / "ws") as lease:
                print(f"[workspace] {lease.path}", flush=True)
                log_output({
                    "workspace": str(lease.path),
                    "source_hash_before": getattr(lease, "source_hash_before", None),
                })
                yield sandboxed, lease
    finally:
        if keep:
            print(f"[kept] {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


async def build_agent(settings: Settings, *, run_id: str | None = None):
    from vgar.agents.core import create_core_agent
    run_id = run_id or new_run_id()
    with phase("build_agent", run_id, {"settings_type": type(settings).__name__}) as log_output:
        agent = await create_core_agent(settings, run_id=run_id)
        log_output({"agent_type": type(agent).__name__})
        return agent


class AgentDebugCallback(BaseCallbackHandler):
    """Duck-typed LangChain callback handler; logs LLM/tool lifecycle live."""
    def __init__(self, run_id: str):
        self.run_id = run_id

    def on_llm_start(self, serialized, prompts, **kwargs):
        emit(
            "LLM_START",
            run_id=self.run_id,
            phase="model_call",
            model=(serialized or {}).get("name") or (serialized or {}).get("id"),
            prompt_count=len(prompts or []),
            prompt_chars=[len(p) for p in (prompts or [])],
        )

    def on_chat_model_start(self, serialized, messages, **kwargs):
        emit(
            "LLM_START",
            run_id=self.run_id,
            phase="model_call",
            model=(serialized or {}).get("name") or (serialized or {}).get("id"),
            message_batches=len(messages or []),
            message_counts=[len(batch) for batch in (messages or [])],
        )

    def on_llm_end(self, response, **kwargs):
        emit("LLM_END", run_id=self.run_id, phase="model_call", status="OK")

    def on_llm_error(self, error, **kwargs):
        emit(
            "LLM_ERROR", run_id=self.run_id, phase="model_call",
            error_type=type(error).__name__, error_message=str(error),
        )

    def on_tool_start(self, serialized, input_str, **kwargs):
        emit(
            "TOOL_START",
            run_id=self.run_id,
            phase=(serialized or {}).get("name", "tool"),
            input_contract={"input": input_str[:500]},
        )

    def on_tool_end(self, output, **kwargs):
        emit(
            "TOOL_END",
            run_id=self.run_id,
            phase="tool",
            output_contract={"output": str(output)[:500]},
        )

    def on_tool_error(self, error, **kwargs):
        emit(
            "TOOL_ERROR", run_id=self.run_id, phase="tool",
            error_type=type(error).__name__, error_message=str(error),
        )


def task_prompt(query: str, workspace: Path, selector: str | None) -> str:
    lines = [query, "", f"Repository working copy (use this exact value as `repo_path` in repository_* and execution_* tools): {workspace}"]
    if selector:
        lines.append(f"Test selector: {selector}")
    lines.append("Never claim success without execution_run_pytest evidence.")
    return "\n".join(lines)


def print_trace(messages: list[BaseMessage], start: int = 0) -> int:
    calls = 0
    for m in messages[start:]:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls or []:
                calls += 1
                print(f"  -> {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:140]})")
        elif isinstance(m, ToolMessage):
            print(f"  <- {m.name} [{m.status}] {str(m.content)[:110]!r}")
    return calls


def final_text(messages: list[BaseMessage]) -> str:
    return next((str(m.content) for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), "")


# --------------------------------------------------------------------- commands
async def cmd_doctor(args: argparse.Namespace) -> int:
    s = get_settings()
    print(json.dumps({
        "model": vars(s.model), "agent": vars(s.agent),
        "graph": {k: str(v) for k, v in vars(s.graph).items()}, "audit_log": str(s.audit_log),
    }, indent=2, ensure_ascii=False))
    print(f"HF_TOKEN set: {bool(os.environ.get('HF_TOKEN'))}")
    return 0


async def cmd_tools(args: argparse.Namespace) -> int:
    from vgar.mcp import create_mcp_client

    tools = await create_mcp_client(get_settings()).get_tools()
    for t in sorted(tools, key=lambda t: t.name):
        print(f"  {t.name}")
    print(f"{len(tools)} tools")
    return 0 if tools else 1


async def cmd_index(args: argparse.Namespace) -> int:
    print(f"{index_repo(Path(args.repo).resolve(), Path(args.db))} nodes -> {args.db}")
    return 0


async def cmd_run(args: argparse.Namespace) -> int:
    from vgar.repair.test_runner import run_tests
    from vgar.repair.workspace import fingerprint_source

    run_id = new_run_id()
    repo = Path(args.repo).resolve()
    settings = get_settings()
    with phase("fingerprint_source_before", run_id, {"repo": str(repo)}) as log_output:
        before = fingerprint_source(repo)
        log_output({"fingerprint_available": before is not None})

    with sandbox(repo, settings, args.keep, run_id=run_id) as (s, lease):
        agent = await build_agent(s, run_id=run_id)
        callback = AgentDebugCallback(run_id)
        prompt = task_prompt(args.query, lease.path, args.selector)
        with phase(
            "agent_ainvoke",
            run_id,
            {
                "query": args.query,
                "repo": str(lease.path),
                "selector": args.selector,
                "prompt_chars": len(prompt),
                "recursion_limit": s.agent.recursion_limit,
            },
        ) as log_output:
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=prompt)]},
                config={
                    "recursion_limit": s.agent.recursion_limit,
                    "callbacks": [callback],
                    "metadata": {"vgar_run_id": run_id},
                },
            )
            messages = result["messages"]
            log_output({
                "message_count": len(messages),
                "message_types": [type(m).__name__ for m in messages],
                "final_answer_chars": len(final_text(messages)),
            })

        print("\n--- tool trace ---", flush=True)
        calls = print_trace(messages)
        print(f"\nagent says: {final_text(messages)[:500]}", flush=True)

        ok = True
        if calls > s.agent.max_tool_calls:
            print(f"[WARN] {calls} tool calls > budget {s.agent.max_tool_calls}", flush=True)
        if args.selector:  # never trust the agent's own claim
            with phase(
                "independent_verification",
                run_id,
                {"workspace": str(lease.path), "selectors": [args.selector], "timeout_seconds": 120},
            ) as log_output:
                verdict = run_tests(lease.path, (args.selector,), 120)
                ok = verdict.status == "PASS"
                log_output({
                    "status": verdict.status,
                    "passed": getattr(verdict, "passed", None),
                    "failed": getattr(verdict, "failed", None),
                    "exit_code": getattr(verdict, "returncode", None),
                })
                print(f"[verify] independent pytest: {verdict.status}", flush=True)

        with phase("workspace_change_check", run_id, {"workspace": str(lease.path)}) as log_output:
            changed = fingerprint_source(lease.path) != lease.source_hash_before
            log_output({"workspace_modified": changed})
            print(f"[verify] workspace modified: {changed}", flush=True)

    with phase("source_repo_integrity_check", run_id, {"repo": str(repo)}) as log_output:
        untouched = fingerprint_source(repo) == before
        log_output({"source_repo_untouched": untouched})
        print(f"[verify] source repo untouched: {untouched}", flush=True)
    emit(
        "RUN_END",
        run_id=run_id,
        phase="run",
        status="OK" if ok and untouched else "FAILED",
        verified=ok,
        source_repo_untouched=untouched,
    )
    return 0 if ok and untouched else 1


async def cmd_solve(args: argparse.Namespace) -> int:
    """Full outer workflow: index -> repair -> independent verify -> retry."""
    from vgar.agents.runtime import Runtime
    from vgar.agents.workflow import run_task

    run_id = new_run_id()
    with phase(
        "solve_workflow",
        run_id,
        {
            "repo": str(Path(args.repo).resolve()),
            "query": args.query,
            "selectors": args.selector,
            "keep_workspace": args.keep,
        },
    ) as log_output:
        state = await run_task(
            repo=Path(args.repo).resolve(),
            issue_text=args.query,
            selectors=args.selector,
            runtime=Runtime(keep_workspace=args.keep),
        )
        log_output({
            "status": state.get("status"),
            "attempts": state.get("attempts", 0),
            "tool_call_count": state.get("tool_call_count", 0),
            "evidence_keys": list((state.get("evidence") or {}).keys()),
            "failure_reason": state.get("failure_reason"),
        })
    print(f"[status] {state['status']} after {state.get('attempts', 0)} attempt(s), "
          f"{state.get('tool_call_count', 0)} tool call(s)", flush=True)
    print(json.dumps(state.get("evidence", {}), indent=2, ensure_ascii=False, default=str))
    if state.get("failure_reason"):
        print(f"[reason] {state['failure_reason']}")
    return 0 if state["status"] == "COMPLETED" else 1


async def cmd_chat(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    with sandbox(repo, get_settings(), args.keep) as (s, lease):
        agent = await build_agent(s)
        history: list[BaseMessage] = []
        print("Type a task (empty line or Ctrl-D to quit).")
        while True:
            try:
                text = input("\nyou> ").strip()
            except EOFError:
                break
            if not text:
                break
            if not history:
                text = task_prompt(text, lease.path, args.selector)
            start = len(history) + 1
            history = (await agent.ainvoke(
                {"messages": [*history, HumanMessage(content=text)]},
                config={"recursion_limit": s.agent.recursion_limit},
            ))["messages"]
            print_trace(history, start)
            print(f"\nvgar> {final_text(history)}")
    return 0


# -------------------------------------------------------------------------- main
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vgar", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="print resolved settings").set_defaults(fn=cmd_doctor)
    sub.add_parser("tools", help="list MCP tools").set_defaults(fn=cmd_tools)

    ix = sub.add_parser("index", help="build graph snapshot")
    ix.add_argument("repo")
    ix.add_argument("--db", default="artifacts/graph.db")
    ix.set_defaults(fn=cmd_index)

    sv = sub.add_parser("solve", help="run the verified repair workflow (retries until tests pass)")
    sv.add_argument("query")
    sv.add_argument("--repo", required=True)
    sv.add_argument("--selector", action="append", required=True, help="pytest selector; repeatable")
    sv.add_argument("--keep", action="store_true", help="keep temp dir")
    sv.set_defaults(fn=cmd_solve)

    for name, fn in (("run", cmd_run), ("chat", cmd_chat)):
        sp = sub.add_parser(name, help=f"{name} the agent on a disposable copy of --repo")
        if name == "run":
            sp.add_argument("query")
        sp.add_argument("--repo", required=True)
        sp.add_argument("--selector", help="pytest selector, e.g. tests/test_x.py::test_y")
        sp.add_argument("--keep", action="store_true", help="keep temp dir")
        sp.set_defaults(fn=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())