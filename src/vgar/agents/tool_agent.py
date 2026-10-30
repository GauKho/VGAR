"""Agent mode of `vgar solve`: a LangChain agent chooses which repair tool to call and when to stop.

The agent sees six tools without arguments. Four forward to the MCP `repair` server with the
current run bound by the host; generate_patch runs the V11 single-turn generator in this process
and the host holds the diff, so the agent never writes a diff, a path or feedback. The optional
analyze_patch_impact sends the failed attempt's applied diff to the MCP `graph` server. A failed attempt
is closed (verified) and the next attempt is a new run with host-built feedback. Every run the host
opens ends with repair_verify_patch, called by the agent or, as a safety net, by the host.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from vgar.agents.fakes import ScriptedPatchGenerator, ScriptedRepairAgent, break_diff
from vgar.agents.feedback import build_feedback, impact_message
from vgar.agents.nodes.mcp_repair import _call, _reason, run_generation
from vgar.agents.runtime import Runtime, cleanup_work_dir, impact_graph_tool, new_work_dir
from vgar.mcp.result_parser import parse_mcp_json_result
from vgar.repair.config import REPO_ROOT

MAX_ATTEMPTS = 3
MAX_TOOL_CALLS = 15
RECURSION_LIMIT = 3 * MAX_TOOL_CALLS + 10  # ~3 graph steps per tool call, so the tool-call limit ends the run first
PROMPT_PATH = Path(__file__).parent / "prompts" / "repair_agent.md"
REFERENCE_PATCHES = REPO_ROOT / "tests/fixtures/m2/reference_patches"


class NoArgs(BaseModel):
    """The tools take no arguments; anything a model passes is dropped."""


def _line(text: Any) -> str:
    return " ".join(str(text).split())[:300]


def _reply(status: str, fields: list[tuple[str, Any]], next_step: str) -> str:
    """Plain-text tool reply: STATUS first, optional one-line fields, NEXT last."""
    lines = [f"STATUS: {status}"]
    lines += [f"{label}: {_line(value)}" for label, value in fields if value not in (None, "")]
    return "\n".join(lines + [f"NEXT: {next_step}"])


def _diff_files(diff: str) -> str:
    return ", ".join(line[6:].strip() for line in diff.splitlines() if line.startswith("+++ b/"))


def generator_path(generator) -> str:
    return getattr(generator, "generator_path", "fake" if generator.mode == "fake" else "worker")


class AgentRepairHost:
    """Owns the current run, the held diff, the attempt counter and the trace of one agent solve."""

    def __init__(self, runtime: Runtime, task_path: Path, work_dir: Path, generator):
        from vgar.repair.config import load_config, load_task
        self.runtime, self.task_path, self.work_dir, self.generator = runtime, Path(task_path), Path(work_dir), generator
        self.task = load_task(task_path)
        self.policy, self.profile = load_config(runtime.config_path)
        self.trace: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.last_verify: dict[str, Any] | None = None
        self.attempts = 0
        self.prompt: dict[str, Any] | None = None
        self.diff: tuple[str, dict[str, Any]] | None = None
        self.graph: tuple[Any, str] | None = None
        self.context_called = False

    @property
    def run(self) -> dict[str, Any] | None:
        return self.runs[-1] if self.runs else None

    def _log(self, tool: str, by: str, status: str, reason: str | None, start: float) -> None:
        self.trace.append({"tool": tool, "by": by, "status": status, "reason": reason,
                           "duration_ms": round((time.monotonic() - start) * 1000),
                           "run_dir": self.run["run_dir"] if self.run else None})

    def _left(self) -> int:
        return MAX_ATTEMPTS - self.attempts

    def _next(self) -> str:
        """The usual next tool for the current state."""
        run = self.run
        if run is None:
            return "get_task_context"
        if run["failed"] and self.prompt is not None and self._left() > 0:
            return "generate_patch to retry with feedback, or verify_patch to finish" if not run["verified"] else (
                "generate_patch to retry with feedback, or stop")
        if run["verified"]:
            return "stop"
        if run["failed"]:
            return "verify_patch"
        if self.diff is not None:
            return "apply_patch"
        if not run["generated"]:
            return "generate_patch"
        return "run_relevant_tests" if run["applied"] and not run["tested"] else "verify_patch"

    def _refuse(self, tool: str, message: str) -> str:
        self._log(tool, "agent", "ERROR", "HOST_REFUSED", time.monotonic())
        return _reply("ERROR", [("DETAIL", message)], self._next())

    def _record(self) -> dict[str, Any]:
        return json.loads((Path(self.run["run_dir"]) / "run_record.json").read_text(encoding="utf-8"))

    async def _mcp(self, tool: str, args: dict[str, Any], by: str) -> dict[str, Any]:
        start = time.monotonic()
        result = await _call(self.runtime, f"repair_{tool}", args)
        self._log(tool, by, result.get("status", "ERROR"), result.get("reason"), start)
        return result

    async def _open_run(self, by: str, **rerun: Any) -> dict[str, Any]:
        start = time.monotonic()
        result = await _call(self.runtime, "repair_get_task_context", {
            "task_path": str(self.task_path), "mode": self.runtime.mode, "output_root": str(self.runtime.output_root),
            "work_root": str(self.work_dir), "config_path": str(self.runtime.config_path),
            "keep_workspace": self.runtime.keep_workspace, **rerun})
        self.prompt = result.get("prompt") if result.get("status") == "PASS" else None
        if result.get("run_dir"):
            self.runs.append({"run_dir": result["run_dir"], "generated": False, "applied": False, "tested": False,
                              "failed": False, "verified": False, "recommendation": None,
                              "applied_diff": None, "impact_called": False, "impact": None})
            if "recommendation" in result:  # the server already finished a run it could not start
                self._verified(result)
        self._log("get_task_context", by, result.get("status", "ERROR"), result.get("reason"), start)
        return result

    def _verified(self, result: dict[str, Any]) -> None:
        recommendation = result["recommendation"]
        self.run.update(verified=True, recommendation=recommendation, failed=self.run["failed"] or recommendation != "ACCEPT")
        self.last_verify = result
        self.diff = None

    async def _verify(self, by: str) -> dict[str, Any]:
        result = await self._mcp("verify_patch", {"run_dir": self.run["run_dir"]}, by)
        if "recommendation" in result:
            self._verified(result)
        return result

    async def get_task_context(self) -> str:
        if self.context_called:
            return self._refuse("get_task_context", "get_task_context was already called.")
        self.context_called = True
        result = await self._open_run("agent")
        if result.get("status") != "PASS":
            return _reply(result.get("status", "ERROR"), [("REASON", result.get("reason")),
                                                          ("DETAIL", result.get("detail"))], "stop")
        return _reply("PASS", [("ISSUE", self.task.issue_text), ("FAILING TESTS", ", ".join(result["failed_cases"])),
                               ("FILES", ", ".join(self.task.allowed_source_paths))], self._next())

    async def generate_patch(self) -> str:
        start, run = time.monotonic(), self.run
        if run is None:
            return self._refuse("generate_patch", "No task yet; call get_task_context first.")
        if self.prompt is None:  # opening the run failed; the server already closed it
            return self._refuse("generate_patch", "The task could not start; stop.")
        if self.diff is not None:
            return self._refuse("generate_patch", "A generated patch has not been applied yet; call apply_patch.")
        if run["failed"]:
            if self._left() <= 0:
                return self._refuse("generate_patch", "No attempts left; call verify_patch.")
            if not run["verified"] and "recommendation" not in await self._verify("host"):
                return self._refuse("generate_patch", "The failed attempt could not be closed; call verify_patch.")
            feedback = build_feedback(self._record(), impact=run["impact"])
            opened = await self._open_run("host", feedback=feedback, supersedes_run_id=feedback["source_run_id"],
                                          rerun_reason=feedback["category"])
            if opened.get("status") != "PASS":
                self._log("generate_patch", "agent", "ERROR", opened.get("reason"), start)
                return _reply("ERROR", [("REASON", opened.get("reason")), ("DETAIL", opened.get("detail"))], "stop")
            run = self.run
        elif run["generated"]:
            return self._refuse("generate_patch", "The current attempt has not failed; continue it.")
        diff, meta = run_generation(self.generator, self.prompt, self.runtime.mode, self.profile, self.policy)
        meta.setdefault("generator_path", generator_path(self.generator))
        self.attempts += 1
        run["generated"] = True
        attempt = [("ATTEMPT", f"{self.attempts} of {MAX_ATTEMPTS}"), ("ATTEMPTS LEFT", self._left())]
        if meta.get("status") != "PASS":
            run["failed"] = True
            self._log("generate_patch", "agent", "ERROR", meta.get("reason"), start)
            return _reply("ERROR", [("REASON", "GENERATION_ERROR"), ("DETAIL", meta.get("reason"))] + attempt, self._next())
        self.diff = (diff, meta)
        self._log("generate_patch", "agent", "PASS", None, start)
        return _reply("PASS", attempt + [("FILES", _diff_files(diff))], self._next())

    async def apply_patch(self) -> str:
        if self.diff is None:
            return self._refuse("apply_patch", "No generated patch is waiting; call generate_patch.")
        (diff, meta), self.diff = self.diff, None
        result = await self._mcp("apply_patch", {"run_dir": self.run["run_dir"], "diff": diff, "generation": meta}, "agent")
        status = result.get("status", "ERROR")
        if status == "PASS":
            self.run.update(applied=True, applied_diff=diff)
            return _reply("PASS", [("FILES", ", ".join(result.get("changed_files") or []))], self._next())
        self.run["failed"] = True
        detail = result.get("detail") or (self._record().get("error_detail") or {}).get("message")
        return _reply(status, [("REASON", result.get("reason")), ("DETAIL", detail), ("ATTEMPTS LEFT", self._left())],
                      self._next())

    async def run_relevant_tests(self) -> str:
        if self.run is None:
            return self._refuse("run_relevant_tests", "No task yet; call get_task_context first.")
        result = await self._mcp("run_relevant_tests", {"run_dir": self.run["run_dir"]}, "agent")
        status = result.get("status", "ERROR")
        self.run["tested"] = self.run["tested"] or status != "ERROR"
        if status == "PASS":
            return _reply("PASS", [], self._next())
        if self.run["applied"]:
            self.run["failed"] = True
        failing = [case["name"] for group in ("failing_tests", "relevant_tests")
                   for case in (result.get(group) or {}).get("cases", []) if case["status"] != "PASS"]
        return _reply(status, [("REASON", result.get("reason")), ("DETAIL", result.get("detail")),
                               ("FAILING TESTS", ", ".join(failing)),
                               ("ATTEMPTS LEFT", self._left() if self.run["failed"] else None)], self._next())

    async def verify_patch(self) -> str:
        if self.run is None:
            return self._refuse("verify_patch", "No task yet; call get_task_context first.")
        result = await self._verify("agent")
        accepted = result.get("recommendation") == "ACCEPT"
        return _reply(result.get("status", "ERROR"), [
            ("RECOMMENDATION", result.get("recommendation")), ("REASON", result.get("reason")),
            ("DETAIL", result.get("detail")), ("ATTEMPTS LEFT", None if accepted else self._left())], self._next())

    async def analyze_patch_impact(self) -> str:
        start, run = time.monotonic(), self.run
        if run is None:
            return self._refuse("analyze_patch_impact", "No task yet; call get_task_context first.")
        if not (run["applied"] and run["failed"]):
            return self._refuse("analyze_patch_impact", "Impact needs an applied patch that failed its tests.")
        if run["impact_called"]:
            return self._refuse("analyze_patch_impact", "Impact was already analyzed for this attempt.")
        if self._left() <= 0:
            return self._refuse("analyze_patch_impact", "No attempts left; call verify_patch.")
        run["impact_called"] = True
        try:
            if self.graph is None:
                self.graph = await impact_graph_tool(self.runtime.base_settings(), Path(self.task.source_repo),
                                                     self.work_dir / "impact-graph.db")
            tool, version = self.graph
            result = parse_mcp_json_result(await tool.ainvoke({"diff": run["applied_diff"], "graph_version": version}))
        except Exception as exc:  # index or transport failure: the retry goes on without impact
            result = {"status": "ERROR", "reason": "TOOL_ERROR", "detail": f"{type(exc).__name__}: {exc}"}
        if result.get("status") == "PASS":
            run["impact"] = result["data"]
            self._log("analyze_patch_impact", "agent", "PASS", None, start)
            line = impact_message(result["data"]) or "No dependent code was computed for this patch."
            return _reply("PASS", [("IMPACT", line)], self._next())
        error = result.get("error") or {}
        code, detail = error.get("code") or result.get("reason") or "ERROR", error.get("message") or result.get("detail")
        self._log("analyze_patch_impact", "agent", "ERROR", code, start)
        return _reply("ERROR", [("REASON", code), ("DETAIL", detail)], self._next())

    def langchain_tools(self) -> list[BaseTool]:
        specs = [
            ("get_task_context", self.get_task_context,
             "Start the task: issue, failing tests and the files that may change. Call first, once."),
            ("generate_patch", self.generate_patch,
             "Ask the generator for a patch (kept by the host). After a failed attempt it retries with feedback."),
            ("apply_patch", self.apply_patch, "Apply the patch the generator just wrote."),
            ("run_relevant_tests", self.run_relevant_tests, "Run the relevant tests after apply_patch passed."),
            ("verify_patch", self.verify_patch, "Final checks; closes the current attempt. Always call it last."),
            ("analyze_patch_impact", self.analyze_patch_impact,
             "After an applied patch failed its tests, show which callers, importers and tests depend on the code "
             "it changed. Optional; call before generate_patch."),
        ]
        return [StructuredTool.from_function(coroutine=fn, name=name, description=description, args_schema=NoArgs)
                for name, fn, description in specs]

    async def close(self) -> None:
        """Safety net: a run the agent left open is verified by the host."""
        if self.run is not None and not self.run["verified"]:
            await self._verify("host")


def select_generator(runtime: Runtime, task, policy, profile, model):
    if runtime.generator is not None:
        return runtime.generator
    if runtime.mode == "fake":
        reference = (REFERENCE_PATCHES / f"{task.task_id}.diff").read_text(encoding="utf-8")
        return ScriptedPatchGenerator([break_diff(reference), reference])
    if runtime.generator_choice == "agent":
        from vgar.agents.agent_generator import AgentModelGenerator
        return AgentModelGenerator(model, profile, policy)
    from vgar.repair.pipeline import build_generation
    return build_generation("real", task, policy, profile, runtime.output_root)[0]


def default_agent_model(runtime: Runtime, profile) -> BaseChatModel:
    """Scripted agent in fake mode; in real mode the pinned snapshot, for both --generator values."""
    if runtime.mode == "fake":
        return ScriptedRepairAgent()
    from vgar.agents.agent_generator import load_pinned_agent_model
    return load_pinned_agent_model(profile, runtime.base_settings().model.max_new_tokens)


class ModelTurns(BaseCallbackHandler):
    """Latency and token usage of each agent model call, in call order."""
    run_inline = True

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.started: dict[Any, float] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        self.started[run_id] = time.monotonic()

    def _record(self, run_id, status: str, message: BaseMessage | None) -> None:
        if run_id not in self.started:  # e.g. the inner HuggingFacePipeline run of LocalChatModel
            return
        usage = getattr(message, "usage_metadata", None) or {}
        self.calls.append({"turn": len(self.calls) + 1, "status": status,
                           "duration_ms": round((time.monotonic() - self.started.pop(run_id)) * 1000),
                           "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                           "tool_calls": [call["name"] for call in getattr(message, "tool_calls", None) or []]})

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        self._record(run_id, "PASS", getattr(response.generations[0][0], "message", None))

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        self._record(run_id, "ERROR", None)


def _message(message: BaseMessage) -> dict[str, Any]:
    content = message.content if isinstance(message.content, str) else json.dumps(message.content, default=str)
    return {"type": message.type, "name": getattr(message, "name", None), "content": content,
            "tool_calls": getattr(message, "tool_calls", None) or []}


def _write_trace(host: AgentRepairHost, runtime: Runtime, duration_ms: int, messages: list[BaseMessage],
                 model_calls: list[dict[str, Any]], result: dict[str, Any]) -> Path:
    runs = []
    for run in host.runs:
        record = json.loads((Path(run["run_dir"]) / "run_record.json").read_text(encoding="utf-8"))
        runs.append({"run_dir": run["run_dir"], **{k: record.get(k) for k in ("run_id", "supersedes_run_id",
                                                                                 "status", "reason")}})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = Path(runtime.output_root) / "agent-traces" / f"{stamp}-{host.task.task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    trace = {"task_id": host.task.task_id, "mode": runtime.mode, "generator": generator_path(host.generator),
             "duration_ms": duration_ms, "calls": host.trace, "model_calls": model_calls, "runs": runs,
             "messages": [_message(m) for m in messages], "result": result}
    path.write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")
    return path


def _result(host: AgentRepairHost, error: str | None, source_unchanged: bool) -> dict[str, Any]:
    """PASS only when the last run's verify returned ACCEPT and the source repo is untouched."""
    run = host.run
    verify = host.last_verify if run is not None and run["verified"] else None
    recommendation = (verify or {}).get("recommendation", "REJECT")
    passed = recommendation == "ACCEPT" and source_unchanged
    if passed:
        failure = None
    elif not source_unchanged:
        failure = "Source repository changed during the run"
    elif error:
        failure = error
    elif verify is not None:
        failure = _reason(verify)
    else:
        failure = next((f"{c['tool']}: {c['reason'] or c['status']}" for c in reversed(host.trace)), "Agent made no tool call")
    return {"status": "COMPLETED" if passed else "FAILED", "repair_status": (verify or {}).get("status", "ERROR"),
            "recommendation": recommendation, "attempts": host.attempts,
            "run_record_path": (verify or {}).get("run_record_path"), "evidence": (verify or {}).get("evidence") or {},
            "failure_reason": failure}


async def run_agent_task(*, task_path: Path, runtime: Runtime, model: BaseChatModel | None = None) -> dict:
    """Solve one M2 task with the agent choosing the tools. Owns the temp dir like run_task."""
    from langchain.agents import create_agent
    from langchain.agents.middleware import ToolCallLimitMiddleware
    from langchain_core.messages import HumanMessage
    from vgar.repair.config import load_config, load_task
    from vgar.repair.workspace import fingerprint_source

    task_path = Path(task_path).resolve()
    task = load_task(task_path)
    source_before = fingerprint_source(task.source_repo)
    work_dir = new_work_dir()
    started = time.perf_counter()
    try:
        policy, profile = load_config(runtime.config_path)
        model = model or default_agent_model(runtime, profile)
        host = AgentRepairHost(runtime, task_path, work_dir, select_generator(runtime, task, policy, profile, model))
        agent = create_agent(model=model, tools=host.langchain_tools(),
                             system_prompt=PROMPT_PATH.read_text(encoding="utf-8"),
                             middleware=[ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="end")])
        request = {"messages": [HumanMessage(f"Repair task {task.task_id}. Start with get_task_context.")]}
        messages: list[BaseMessage] = []
        turns, error = ModelTurns(), None
        config = {"recursion_limit": RECURSION_LIMIT, "callbacks": [turns]}
        try:
            async for state in agent.astream(request, config=config, stream_mode="values"):
                messages = state["messages"]
        except Exception as exc:  # recursion limit, unparseable model output: the host still closes the run
            error = f"{type(exc).__name__}: {exc}"
        await host.close()
        result = _result(host, error, fingerprint_source(task.source_repo) == source_before)
        duration_ms = round((time.perf_counter() - started) * 1000)
        result["trace_path"] = str(_write_trace(host, runtime, duration_ms, messages, turns.calls, result))
        return result
    finally:
        cleanup_work_dir(work_dir, runtime.keep_workspace)
