"""VGAR command line: one entry point for settings, MCP tools and the agent.

    vgar doctor                      # resolved settings, no model loaded
    vgar tools                       # spawn MCP servers, list tools
    vgar index REPO --db graph.db    # build graph snapshot
    vgar run "Fix ..." --repo REPO --selector tests/test_x.py::test_y
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

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from vgar.config.settings import Settings, get_settings


# ----------------------------------------------------------------- shared helpers
def index_repo(repo: Path, db: Path) -> int:
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_store import SQLiteGraphStore

    doc = PythonGraphBuilder(repo_key=repo.name, repository_revision="cli", use_jedi=True).build(repo)
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteGraphStore(db).ingest(doc)
    return len(doc["nodes"])


@contextmanager
def sandbox(repo: Path, settings: Settings, keep: bool = False):
    """Index `repo`, copy it to a disposable workspace, yield (settings, lease)."""
    from vgar.repair.workspace import create_workspace

    work = Path(tempfile.mkdtemp(prefix="vgar-cli-"))
    try:
        nodes = index_repo(repo, work / "graph.db")
        print(f"[index] {nodes} nodes -> {work / 'graph.db'}")
        sandboxed = replace(settings, graph=replace(settings.graph, backend="sqlite", database=work / "graph.db"))
        with create_workspace(repo, work / "ws") as lease:
            print(f"[workspace] {lease.path}")
            yield sandboxed, lease
    finally:
        if keep:
            print(f"[kept] {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


async def build_agent(engine: str, settings: Settings):
    if engine == "langgraph":
        from vgar.agents.graph import create_agent
        return await create_agent(settings)
    from vgar.agents.core import create_core_agent
    return await create_core_agent(settings)


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

    repo = Path(args.repo).resolve()
    settings = get_settings()
    before = fingerprint_source(repo)
    with sandbox(repo, settings, args.keep) as (s, lease):
        agent = await build_agent(args.engine, s)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=task_prompt(args.query, lease.path, args.selector))]},
            config={"recursion_limit": s.agent.recursion_limit},
        )
        messages = result["messages"]
        print("\n--- tool trace ---")
        calls = print_trace(messages)
        print(f"\nagent says: {final_text(messages)[:500]}")

        ok = True
        if calls > s.agent.max_tool_calls:
            print(f"[WARN] {calls} tool calls > budget {s.agent.max_tool_calls}")
        if args.selector:  # never trust the agent's own claim
            verdict = run_tests(lease.path, (args.selector,), 120)
            ok = verdict.status == "PASS"
            print(f"[verify] independent pytest: {verdict.status}")
        changed = fingerprint_source(lease.path) != lease.source_hash_before
        print(f"[verify] workspace modified: {changed}")
    untouched = fingerprint_source(repo) == before
    print(f"[verify] source repo untouched: {untouched}")
    return 0 if ok and untouched else 1


async def cmd_chat(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    with sandbox(repo, get_settings(), args.keep) as (s, lease):
        agent = await build_agent(args.engine, s)
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

    for name, fn in (("run", cmd_run), ("chat", cmd_chat)):
        sp = sub.add_parser(name, help=f"{name} the agent on a disposable copy of --repo")
        if name == "run":
            sp.add_argument("query")
        sp.add_argument("--repo", required=True)
        sp.add_argument("--selector", help="pytest selector, e.g. tests/test_x.py::test_y")
        sp.add_argument("--engine", choices=["langchain", "langgraph"], default="langchain")
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
