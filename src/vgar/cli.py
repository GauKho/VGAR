"""VGAR command line: one entry point for settings, MCP tools and the agent.

    vgar doctor                      # resolved settings, no model loaded
    vgar tools                       # spawn MCP servers, list tools
    vgar index REPO --db graph.db    # build graph snapshot
    vgar run "Fix ..." --repo REPO --selector tests/test_x.py::test_y
    vgar repair --task TASK.json --mode fake|real   # one-pass M2 repair, prints run record
    vgar solve --task TASK.json [--mode fake|real]  # LangGraph workflow around one M2 repair run
    vgar chat --repo REPO            # interactive session on a disposable copy

Agent commands never touch REPO: they index it, copy it to a temp workspace
and let the agent edit only the copy. repair/solve apply the model's diff in
a private worktree of the task's trusted fixture snapshot.
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
def sandbox_workspace(repo: Path, root: Path):
    """Disposable private worktree copy of `repo` under `root` (M2 workspace)."""
    from vgar.repair.workspace import create_workspace

    with create_workspace(repo, root) as lease:
        yield lease


@contextmanager
def sandbox(
    repo: Path,
    settings: Settings,
    keep: bool = False,
    *,
    run_id: str | None = None,
):
    """Index `repo`, copy it to a disposable workspace, yield (settings, lease)."""
    from vgar.repair.workspace import fingerprint_source

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
            with sandbox_workspace(repo, work / "ws") as lease:
                print(f"[workspace] {lease.path}", flush=True)
                log_output({
                    "workspace": str(lease.path),
                    "source_hash_before": fingerprint_source(lease.path),
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
    from vgar.repair.executor import NativeExecutor
    from vgar.repair.test_runner import run_tests
    from vgar.repair.workspace import fingerprint_source

    run_id = new_run_id()
    repo = Path(args.repo).resolve()
    settings = get_settings()
    with phase("fingerprint_source_before", run_id, {"repo": str(repo)}) as log_output:
        before = fingerprint_source(repo)
        log_output({"fingerprint_available": before is not None})

    with sandbox(repo, settings, args.keep, run_id=run_id) as (s, lease):
        workspace_before = fingerprint_source(lease.path)
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
                verdict = run_tests(lease, (args.selector,), NativeExecutor(lease), 120)
                ok = verdict["status"] == "PASS"
                log_output({
                    "status": verdict["status"],
                    "outcomes": verdict["outcomes"],
                    "exit_code": verdict["command"]["exit_code"],
                })
                print(f"[verify] independent pytest: {verdict['status']}", flush=True)

        with phase("workspace_change_check", run_id, {"workspace": str(lease.path)}) as log_output:
            changed = fingerprint_source(lease.path) != workspace_before
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


async def cmd_repair(args: argparse.Namespace) -> int:
    """One-pass M2 repair on a trusted fixture task; prints the run record path."""
    from vgar.repair.config import load_config, load_task
    from vgar.repair.diagnostics import exception_details
    from vgar.repair.evidence import begin_run
    from vgar.repair.pipeline import build_generation, run_repair

    try:
        if bool(args.supersedes_run_id) != bool(args.rerun_reason):
            raise ValueError("Manual rerun requires both prior run ID and reason")
        task = load_task(args.task)
        policy, profile = load_config(args.config)
        generator, tokenizer, counter = build_generation(args.mode, task, policy, profile, args.output_root)
        result = run_repair(task, policy, generator, None, args.output_root,
                            m1_counter=counter, tokenizer=tokenizer,
                            profile=profile if args.mode == "real" else None,
                            keep_workspace=args.keep_workspace, supersedes_run_id=args.supersedes_run_id,
                            rerun_reason=args.rerun_reason)
    except Exception as error:
        result = begin_run(args.output_root, "repair-config-error", mode=args.mode,
                           requested_task=str(args.task), requested_config=str(args.config))
        result.finish("ERROR", reason=str(error), error_type=type(error).__name__, **exception_details(error))
    print(result.path, flush=True)
    return {"PASS": 0, "FAIL": 1, "ERROR": 2}[result.record["status"]]


async def cmd_solve(args: argparse.Namespace) -> int:
    """LangGraph workflow: initialize -> one M2 pipeline run -> finalize/failed."""
    from vgar.agents.runtime import Runtime
    from vgar.agents.workflow import run_task

    run_id = new_run_id()
    with phase(
        "solve_workflow",
        run_id,
        {"task": str(Path(args.task).resolve()), "mode": args.mode, "keep_workspace": args.keep},
    ) as log_output:
        state = await run_task(task_path=args.task, runtime=Runtime(mode=args.mode, keep_workspace=args.keep))
        log_output({
            "status": state.get("status"),
            "attempts": state.get("attempts", 0),
            "repair_status": state.get("repair_status"),
            "run_record_path": state.get("run_record_path"),
            "failure_reason": state.get("failure_reason"),
        })
    print(f"[status] {state['status']} after {state.get('attempts', 0)} attempt(s)", flush=True)
    print(f"[run] {state.get('run_record_path')}", flush=True)
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

    from vgar.repair.config import CONFIG_DIR, REPO_ROOT

    rp = sub.add_parser("repair", help="one-pass M2 repair of a trusted fixture task (no MCP, no retry)")
    rp.add_argument("--task", type=Path, required=True)
    rp.add_argument("--config", type=Path, default=CONFIG_DIR / "demo.json")
    rp.add_argument("--mode", choices=("fake", "real"), required=True)
    rp.add_argument("--output-root", type=Path, default=REPO_ROOT / "results/repair")
    rp.add_argument("--keep-workspace", action="store_true")
    rp.add_argument("--supersedes-run-id")
    rp.add_argument("--rerun-reason")
    rp.set_defaults(fn=cmd_repair)

    sv = sub.add_parser("solve", help="LangGraph workflow running the M2 pipeline once on a task file")
    sv.add_argument("--task", type=Path, required=True)
    sv.add_argument("--mode", choices=("fake", "real"), default="fake")
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