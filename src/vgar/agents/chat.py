"""`vgar chat --task`: an agent fixes a declared task; only the M2 engine edits code and decides (D19).

The host opens the repair run first, leases that run's private worktree to the repository/execution servers
(VGAR_LEASE_ROOT) with the task's selectors allowed (VGAR_ALLOWED_SELECTORS), and hides
repair_get_task_context from the agent. The printed outcome is the engine verdict: when the session ends
without a verify, the host calls repair_verify_patch itself.
Design: docs/superpowers/specs/2026-11-01-m3-w11-legacy-servers-design.md
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage

from vgar.agents.core import create_core_agent
from vgar.agents.nodes.mcp_repair import _call
from vgar.agents.runtime import Runtime, cleanup_work_dir, index_repo, new_work_dir

CHAT_SERVERS = ("graph", "repository", "execution", "repair")
HIDDEN_TOOLS = frozenset({"repair_get_task_context"})


def _first_prompt(text: str, run_dir: str, worktree: Path) -> str:
    return "\n".join([
        text, "",
        f"Run directory: {run_dir}",
        f"Workspace (repository_* and execution_* tools are already rooted here): {worktree}",
        "Edit code only with repair_apply_patch(run_dir, diff); finish with repair_verify_patch(run_dir).",
    ])


def _final_text(messages: list[BaseMessage]) -> str:
    return str(messages[-1].content) if messages else ""


async def run_chat(task_path: Path, runtime: Runtime, inputs: Iterable[str], *,
                   model: BaseChatModel | None = None) -> dict[str, Any]:
    import time

    from vgar.agents import trace_report
    from vgar.observability.code_state import code_state
    from vgar.observability.machine import machine_info
    from vgar.repair.config import REPO_ROOT, load_task
    from vgar.repair.pipeline import recommendation_for
    from vgar.repair.session import RepairSession

    def say(line: str) -> None:
        print(line, flush=True)

    started = time.monotonic()
    try:  # console header (trace spec §6.3); never blocks the chat
        say("\n".join(trace_report.render_header(
            {"task_id": load_task(task_path).task_id, "code": code_state(REPO_ROOT), "machine": machine_info(None),
             "mode": runtime.mode}, title="chat")))
    except Exception:
        pass
    steps = trace_report.chat_steps(say)
    work_dir = new_work_dir()
    try:
        opened = await _call(runtime, "repair_get_task_context", {
            "task_path": str(task_path), "mode": runtime.mode, "output_root": str(runtime.output_root),
            "work_root": str(work_dir), "config_path": str(runtime.config_path),
            "keep_workspace": runtime.keep_workspace})
        run_dir = opened.get("run_dir")
        if opened.get("status") != "PASS" or not run_dir:
            print(f"[chat] could not open the repair run: {opened.get('reason')} {opened.get('detail') or ''}")
            return {"run_dir": run_dir, "verdict": "ERROR", "recommendation": "REJECT", "verified_by": "host",
                    "lease_root": None, "allowed_selectors": []}

        task = load_task(task_path)
        worktree = RepairSession.load(Path(run_dir)).lease().path
        allowed = [*task.failing_selectors, *task.fallback_scope]
        database = work_dir / "graph.db"
        index_repo(Path(task.source_repo), database)
        base = runtime.base_settings()
        settings = replace(base, graph=replace(base.graph, backend="sqlite", database=database))
        agent = await create_core_agent(
            settings, servers=CHAT_SERVERS, exclude_tools=HIDDEN_TOOLS, model=model,
            extra_env={"VGAR_LEASE_ROOT": str(worktree), "VGAR_ALLOWED_SELECTORS": json.dumps(allowed),
                       "VGAR_REPOSITORY_ROOT": str(task.source_repo), "VGAR_RUN_ROOT": str(runtime.output_root)})

        history: list[BaseMessage] = []
        for text in inputs:
            if not history:
                text = _first_prompt(text, run_dir, worktree)
            history = (await agent.ainvoke({"messages": [*history, HumanMessage(content=text)]},
                                           config={"recursion_limit": settings.agent.recursion_limit,
                                                   "callbacks": [steps]}))["messages"]
            print(f"\nvgar> {_final_text(history)}", flush=True)

        verified_by = "agent"
        if RepairSession.load(Path(run_dir)).phase != "finished":
            verified_by = "host"
            close_start, close_wall = time.monotonic(), time.time()
            closed = await _call(runtime, "repair_verify_patch", {"run_dir": run_dir})
            say(trace_report.render_step("end", {
                "tool": "verify_patch", "by": "host", "status": closed.get("recommendation") or closed.get("status"),
                "reason": closed.get("reason"), "attempt": 1, "t": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                                   time.gmtime(close_wall)),
                "duration_ms": round((time.monotonic() - close_start) * 1000), "metrics": {}}, 1))
        record = json.loads((Path(run_dir) / "run_record.json").read_text(encoding="utf-8"))
        verdict = record["status"]
        recommendation = recommendation_for(verdict)
        try:
            say("\n".join(trace_report.render_chat_result(record, steps.steps, steps.turns.calls, verified_by=verified_by,
                                                         duration_ms=round((time.monotonic() - started) * 1000))))
        except Exception:
            pass
        print(f"[verdict] {verdict} ({recommendation}), verified by {verified_by}", flush=True)
        return {"run_dir": run_dir, "verdict": verdict, "recommendation": recommendation,
                "verified_by": verified_by, "lease_root": str(worktree), "allowed_selectors": allowed}
    finally:
        cleanup_work_dir(work_dir, runtime.keep_workspace)
