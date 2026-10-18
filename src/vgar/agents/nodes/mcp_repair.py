"""Fixed repair flow over the MCP repair server: only `generate` runs the model in this process."""
from __future__ import annotations

import time
from typing import Any

from vgar.agents.runtime import Runtime
from vgar.agents.state import VGARState
from vgar.mcp.result_parser import parse_mcp_json_result
from vgar.observability.instrumentation import instrument_node


async def _call(runtime: Runtime, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """One MCP tool call; transport/tool failures become an ERROR result instead of an exception."""
    try:
        tools = await runtime.repair_tools()
        return parse_mcp_json_result(await tools[tool].ainvoke(args))
    except Exception as exc:
        return {"status": "ERROR", "reason": "TOOL_ERROR", "detail": f"{type(exc).__name__}: {exc}"}


def _reason(result: dict[str, Any]) -> str:
    reason = result.get("reason") or result.get("status") or "ERROR"
    if result.get("status") == "ERROR" and result.get("detail"):
        return f"{reason}: {result['detail']}"
    return reason


@instrument_node("retrieve")
async def retrieve(state: VGARState, runtime: Runtime) -> dict:
    result = await _call(runtime, "repair_get_task_context", {
        "task_path": state["task_path"], "mode": runtime.mode, "output_root": str(runtime.output_root),
        "work_root": state["work_dir"], "config_path": str(runtime.config_path),
        "keep_workspace": runtime.keep_workspace})
    if result.get("status") == "PASS":
        return {"run_dir": result["run_dir"], "prompt": result["prompt"], "failure_reason": None}
    return {"run_dir": result.get("run_dir"), "run_record_path": result.get("run_record_path"),
            "repair_status": "ERROR", "recommendation": result.get("recommendation", "REJECT"),
            "failure_reason": _reason(result)}


def run_generation(generator, prompt: dict[str, Any], mode: str, profile, policy) -> tuple[str, dict[str, Any]]:
    """One V11 generation -> (diff text, generation meta for apply_patch); failures become ERROR meta."""
    from vgar.repair.executor import utc_now
    from vgar.repair.prompt import PromptArtifact

    started_utc, start = utc_now(), time.monotonic()
    try:
        generated = generator.generate(PromptArtifact(**prompt), profile if mode == "real" else None,
                                       policy.generation_timeout)
    except Exception as exc:  # recorded by apply_patch as a failed generation, then verify rejects
        generated = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}", "raw_text": "", "truncated": False}
    meta = {k: v for k, v in generated.items() if k != "raw_text"}
    meta.update(started_utc=started_utc, duration_ms=round((time.monotonic() - start) * 1000))
    return generated.get("raw_text") or "", meta


@instrument_node("generate")
async def generate(state: VGARState, runtime: Runtime) -> dict:
    """The only model call: the V11 prompt returned by retrieve -> unified diff text."""
    from vgar.repair.config import load_config, load_task
    from vgar.repair.executor import utc_now
    from vgar.repair.pipeline import build_generation

    started_utc, start = utc_now(), time.monotonic()
    try:
        policy, profile = load_config(runtime.config_path)
        generator = runtime.generator or build_generation(
            runtime.mode, load_task(state["task_path"]), policy, profile, runtime.output_root)[0]
    except Exception as exc:  # recorded by apply_patch as a failed generation, then verify rejects
        meta = {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}", "truncated": False,
                "started_utc": started_utc, "duration_ms": round((time.monotonic() - start) * 1000)}
        return {"attempts": 1, "diff": "", "generation": meta}
    diff, meta = run_generation(generator, state["prompt"], runtime.mode, profile, policy)
    return {"attempts": 1, "diff": diff, "generation": meta}


@instrument_node("apply")
async def apply(state: VGARState, runtime: Runtime) -> dict:
    result = await _call(runtime, "repair_apply_patch", {
        "run_dir": state["run_dir"], "diff": state["diff"], "generation": state["generation"]})
    return {"apply_status": result.get("status", "ERROR"),
            "failure_reason": None if result.get("status") == "PASS" else _reason(result)}


@instrument_node("test")
async def test(state: VGARState, runtime: Runtime) -> dict:
    result = await _call(runtime, "repair_run_relevant_tests", {"run_dir": state["run_dir"]})
    return {"failure_reason": None if result.get("status") == "PASS" else _reason(result)}


@instrument_node("verify")
async def verify(state: VGARState, runtime: Runtime) -> dict:
    """Always the last tool of a run: it cleans the worktree and returns the evidence bundle."""
    result = await _call(runtime, "repair_verify_patch", {"run_dir": state["run_dir"]})
    recommendation = result.get("recommendation", "REJECT")
    return {"repair_status": result.get("status", "ERROR"), "recommendation": recommendation,
            "evidence": result.get("evidence") or {}, "run_record_path": result.get("run_record_path"),
            "failure_reason": None if recommendation == "ACCEPT" else _reason(result)}
