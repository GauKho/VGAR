"""Readable summaries of an agent trace (spec 2026-11-03-m3-w12-trace §3–§4): attempt funnel (E2), outcome class
(E3), time breakdown (E4) and the run header (E5, E6). Pure functions over the trace calls and run records,
so the console and trace v2 never compute numbers the records do not hold."""
from __future__ import annotations

from typing import Any

from vgar.evaluation.failure_class import classify, refine_code

DOCKER_STAGES = ("workspace", "baseline", "apply", "selection", "verification")
CLOSED_BY_HOST = "VERIFICATION_INCOMPLETE"
NOT_A_CAUSE = (None, CLOSED_BY_HOST, "HOST_REFUSED")


def _run_ids(calls: list[dict]) -> list[str]:
    seen: list[str] = []
    for call in calls:
        if call.get("run_id") and call["run_id"] not in seen:
            seen.append(call["run_id"])
    return seen


def _of(calls: list[dict], run_id: str, tool: str) -> list[dict]:
    return [c for c in calls if c.get("run_id") == run_id and c["tool"] == tool]


def _mark(items: list[dict]) -> str:
    if not items:
        return "–"
    return "✓" if items[-1]["status"] == "PASS" else "✗"


def _static(record: dict) -> str:
    checks = ((record.get("stages") or {}).get("verification") or {}).get("policy_checks") or {}
    statuses = {k: v.get("status") for k, v in checks.items() if k != "tests" and isinstance(v, dict)}
    if not statuses:
        return "–"
    if any(s not in ("PASS", "SKIPPED", "NOT_RUN", "UNAVAILABLE") for s in statuses.values()):
        return "✗"
    # UNAVAILABLE (e.g. mypy on a Python 3.6 testbed, D12) does not fail verification (verification.py).
    unavailable = [k for k, s in statuses.items() if s == "UNAVAILABLE"]
    return f"✓ ({', '.join(unavailable)} n/a)" if unavailable else "✓"


def attempt_funnel(calls: list[dict], records: dict[str, dict]) -> list[dict]:
    rows = []
    for run_id in _run_ids(calls):
        record = records.get(run_id) or {}
        generated = _of(calls, run_id, "generate_patch")
        tests = [c for c in _of(calls, run_id, "run_relevant_tests") if "passed" in (c.get("metrics") or {})]
        last_tests = tests[-1]["metrics"] if tests else None
        rows.append({
            "run_id": run_id,
            "generated": _mark(generated),
            "generation_reason": generated[-1]["reason"] if generated and generated[-1]["status"] != "PASS" else None,
            "applied": _mark(_of(calls, run_id, "apply_patch")),
            "tests": f"{last_tests['passed']}/{last_tests['passed'] + last_tests['failed']}" if last_tests else "–",
            "static": _static(record),
            "verdict": "ACCEPT" if record.get("status") == "PASS" else "REJECT",
        })
    return rows


def failure_class(calls: list[dict], records: dict[str, dict], result: dict) -> dict:
    """Class of the last attempt; an attempt the host closed takes the reason of the step that failed before."""
    if result.get("status") == "COMPLETED":
        return {"class": "VERIFIED", "code": None}
    runs = _run_ids(calls)
    if not runs:
        return {"class": classify("ERROR", None, result.get("failure_reason")), "code": None}
    run_id = runs[-1]
    record = records.get(run_id) or {}
    code, evidence = refine_code(record.get("reason"), record)
    if code in NOT_A_CAUSE:
        cause = next((c["reason"] for c in reversed(calls)
                      if c.get("run_id") == run_id and c["status"] not in ("PASS", "OK")
                      and c["reason"] not in NOT_A_CAUSE), None)
        code = cause or code
    detail = (record.get("error_detail") or {}).get("message")
    applied = any(c["status"] == "PASS" for c in _of(calls, run_id, "apply_patch"))
    out = {"class": classify(record.get("status", "ERROR"), code, detail, applied=applied), "code": code}
    return out | ({"evidence": evidence} if evidence else {})


def time_breakdown(duration_ms: int, calls: list[dict], model_calls: list[dict], records: dict[str, dict]) -> dict:
    generation = sum(c["duration_ms"] for c in calls if c["tool"] == "generate_patch")
    turns = sum(t.get("duration_ms") or 0 for t in model_calls)
    docker = sum(((r.get("stages") or {}).get(name) or {}).get("duration_ms") or 0
                 for r in records.values() for name in DOCKER_STAGES)
    rest = duration_ms - generation - turns - docker
    return {"total_ms": duration_ms, "generation_ms": generation, "agent_turns_ms": turns, "docker_ms": docker,
            "other_ms": max(0, rest), "overlap_ms": max(0, -rest)}


def trace_header(host, runtime, hf_model) -> dict[str, Any]:
    """Run identity for console and trace v2: hashes only, never the inventory itself."""
    from vgar.observability.code_state import code_state
    from vgar.observability.machine import machine_info
    from vgar.repair.config import REPO_ROOT
    from vgar.agents.tool_agent import generator_path

    args = host.run_args or {}
    experiment, admission = args.get("experiment") or {}, args.get("admission") or {}
    bundle = (admission.get("bundle_hashes") or {}).get("context.json")
    return {
        "task_id": host.task.task_id,
        "variant": (experiment.get("variant_policy") or {}).get("variant_id"),
        "arm": experiment.get("arm"),
        "experiment_id": getattr(runtime, "experiment_id", None) or args.get("experiment_id"),
        "model": f"{host.profile.model_id}@{str(host.profile.revision)[:8]}",
        "generator": generator_path(host.generator),
        "input_cap": host.policy.input_cap,
        "output_cap": host.policy.output_cap,
        "generation_timeout": host.policy.generation_timeout,
        "admission_hash": admission.get("admission_hash"),
        "inventory_hash": admission.get("inventory_hash"),
        "bundle_hash": bundle,
        "code": code_state(REPO_ROOT),
        "machine": machine_info(hf_model),
        "mode": runtime.mode,
    }


# ---- console (spec §3.1) -------------------------------------------------------------------------------------

DASH = "—"
COLUMNS = f"{'time':<9} {'try':<4} {'by':<6} {'step':<24} {'result':<8} {'time':>8}  detail"


def _short(value: str | None, n: int = 8) -> str:
    return str(value).split(":")[-1][:n] if value else DASH


def _or_dash(value: Any) -> str:
    return DASH if value in (None, "") else str(value)


def render_header(header: dict, title: str = "solve --agent") -> list[str]:
    from vgar.observability.code_state import code_label
    h = header or {}
    machine = h.get("machine") or {}
    placement = machine.get("placement")
    place = (f"GPU {placement['gpu_pct']}% / offload {placement['offload_pct']}%" if placement else DASH)
    variant = f"{_or_dash(h.get('variant'))} ({_or_dash(h.get('arm'))})"
    timeout = h.get("generation_timeout")
    return [
        f"== {title} · {_or_dash(h.get('task_id'))} · {variant} · exp {_short(h.get('experiment_id'))} · "
        f"commit {code_label(h.get('code'))}",
        f"   model {_or_dash(h.get('model'))} · generator {_or_dash(h.get('generator'))} · "
        f"cap in {_or_dash(h.get('input_cap'))} / out {_or_dash(h.get('output_cap'))} tok · "
        f"gen timeout {DASH if timeout is None else f'{timeout:.0f}'} s",
        f"   machine GPU {_or_dash(machine.get('gpu'))} {_or_dash(machine.get('vram_mib'))} MiB · "
        f"RAM {_or_dash(machine.get('ram_gib'))} GiB · model placement {place}",
        f"   admission {_short(h.get('admission_hash'))} · bundle {_short(h.get('bundle_hash'))}",
        COLUMNS,
    ]


def _step_name(call: dict) -> str:
    if call.get("by") == "host" and call["tool"] == "verify_patch":
        return "verify_patch (close)"
    if call.get("by") == "host" and call["tool"] == "get_task_context":
        return "reopen with feedback"
    return call["tool"]


def _detail(call: dict) -> str:
    m = call.get("metrics") or {}
    if call.get("status") not in ("PASS", None) or call.get("reason"):
        return " · ".join(str(x) for x in (call.get("reason"), m.get("detail")) if x)
    parts = []
    if call["tool"] == "get_task_context" and call.get("run_id"):
        parts.append(f"run …{call['run_id'][-8:]}")
    if "input_tokens" in m:
        parts.append(f"prompt {m['input_tokens']}/{m.get('input_cap', DASH)} tok")
    if "context_items" in m:
        parts.append(f"{m['context_items']} items" + (" (truncated)" if m.get("truncated") else ""))
    if "failing_tests" in m:
        parts.append(f"{m['failing_tests']} failing tests")
    if m.get("files"):
        parts.append(", ".join(dict.fromkeys(m["files"])))
    if m.get("output_truncated"):
        parts.append("output cut at output cap")
    if "passed" in m:
        parts.append(f"{m['passed']} passed / {m['failed']} failed")
    return " · ".join(parts)


def render_step(kind: str, call: dict, max_attempts: int) -> str:
    when = (call.get("t") or "")[11:19] or DASH
    tried = f"{max(1, call.get('attempt') or 0)}/{max_attempts}"
    if kind == "start":
        result, took, detail = "running", "…", ""
    else:
        result = (call.get("metrics") or {}).get("recommendation") or call.get("status") or DASH
        took, detail = f"{(call.get('duration_ms') or 0) / 1000:.1f} s", _detail(call)
    return f"{when:<9} {tried:<4} {call.get('by', 'agent'):<6} {_step_name(call):<24} {result:<8} {took:>8}  {detail}".rstrip()


def render_turn(turn: dict) -> str:
    tools = turn.get("tool_calls") or []
    followed = {True: "followed", False: "not followed", None: "n/a" if tools else "ended"}[turn.get("followed")]
    tokens = (f"in {turn['input_tokens']} / out {turn['output_tokens']} tok · "
              if turn.get("input_tokens") is not None else "")
    step = f"model turn {turn.get('turn')}"
    took = f"{(turn.get('duration_ms') or 0) / 1000:.1f} s"
    return (f"{'':<9} {'':<4} {'agent':<6} {step:<24} {'→' + (tools[0] if tools else 'end'):<8} {took:>8}  "
            f"{tokens}NEXT {_or_dash(turn.get('next_hint'))} · {followed}")


def _minutes(ms: int) -> str:
    return f"{ms / 60000:.1f}"


def render_result(trace: dict, audit: dict | None = None) -> list[str]:
    """`audit` is the task's audit completeness (agent_metrics.audit_completeness); None prints a dash."""
    from vgar.agents.tool_agent import MAX_ATTEMPTS
    from vgar.evaluation.agent_metrics import INVALID_REASONS
    result = trace.get("result") or {}
    klass = trace.get("failure_class") or {}
    label = f"class {klass.get('class', DASH)}" + (f" ({klass['code']})" if klass.get("code") else "")
    funnel = trace.get("attempts") or []
    attempts = result.get("attempts", 0)
    # An attempt is one generated patch; a run is one engine run. A reopen that fails before generating is a run
    # without an attempt (X2b matplotlib 03/11), so both counts are shown when they differ.
    runs = f" · {len(funnel)} runs" if funnel and len(funnel) != attempts else ""
    lines = [f"== RESULT {result.get('status', DASH)} · {label} · {attempts}/{MAX_ATTEMPTS} attempts{runs}"]
    if klass.get("evidence"):
        lines.append(f"   cause {klass['evidence']}")
    for i, row in enumerate(funnel, start=1):
        generated = row["generated"] + (f" {row['generation_reason']}" if row.get("generation_reason") else "")
        lines.append(f"   run {i}/{len(funnel)}: generated {generated} → applied {row['applied']} → "
                     f"tests {row['tests']} → static {row['static']} → verdict {row['verdict']}")
    t = trace.get("time_breakdown")
    if t and t.get("total_ms"):
        share = round(100 * t["generation_ms"] / t["total_ms"])
        line = (f"   time {_minutes(t['total_ms'])} min = generation {_minutes(t['generation_ms'])} ({share}%) · "
                f"agent turns {_minutes(t['agent_turns_ms'])} · docker {_minutes(t['docker_ms'])} · "
                f"other {_minutes(t['other_ms'])}")
        lines.append(line + (f" · overlap {_minutes(t['overlap_ms'])}" if t.get("overlap_ms") else ""))
    agent_calls = [c for c in trace.get("calls") or [] if c.get("by") == "agent"]
    turns = [m for m in trace.get("model_calls") or [] if m.get("followed") is not None]
    followed = f"{sum(m['followed'] for m in turns)}/{len(turns)}" if turns else "n/a"
    invalid = sum(c.get("reason") in INVALID_REASONS for c in agent_calls)  # the same count as table M1
    audited = f"{audit['matched']}/{audit['expected']}" if audit else DASH
    lines.append(f"   agent: {len(agent_calls)} calls · invalid {invalid} · followed NEXT {followed} · audit {audited}")
    return lines


# ---- vgar chat (spec §6.3) -----------------------------------------------------------------------------------

def _tool_status(output: Any) -> tuple[str, str | None]:
    """STATUS and reason of an MCP tool result as the chat agent received it."""
    import json
    content = getattr(output, "content", output)
    if isinstance(content, list):  # MCP content blocks
        content = "".join(str(block.get("text", "")) if isinstance(block, dict) else str(block) for block in content)
    try:
        data = json.loads(content)
    except Exception:
        return "PASS", None
    if not isinstance(data, dict):
        return "PASS", None
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    return str(inner.get("verdict") or data.get("status") or "PASS"), inner.get("reason") or data.get("reason")


def chat_steps(printer):
    """LangChain callback printing one line per chat tool call and model turn; records them for the result."""
    import time
    from langchain_core.callbacks import BaseCallbackHandler
    from vgar.agents.tool_agent import ModelTurns, _utc

    class ChatSteps(BaseCallbackHandler):
        run_inline = True

        def __init__(self):
            self.steps: list[dict] = []
            self.started: dict[Any, tuple[str, float, float]] = {}
            self.turns = ModelTurns(on_turn=lambda turn: self._print(render_turn(turn)))

        def _print(self, line: str) -> None:
            try:
                printer(line)
            except Exception:
                pass

        def on_tool_start(self, serialized, input_str, *, run_id, **kwargs) -> None:
            self.started[run_id] = ((serialized or {}).get("name") or "tool", time.monotonic(), time.time())

        def _end(self, run_id, status: str, reason: str | None) -> None:
            if run_id not in self.started:
                return
            name, start, wall = self.started.pop(run_id)
            step = {"tool": name, "by": "agent", "status": status, "reason": reason, "attempt": 1,
                    "duration_ms": round((time.monotonic() - start) * 1000), "t": _utc(wall), "metrics": {}}
            self.steps.append(step)
            self._print(render_step("end", step, 1))

        def on_tool_end(self, output, *, run_id, **kwargs) -> None:
            self._end(run_id, *_tool_status(output))

        def on_tool_error(self, error, *, run_id, **kwargs) -> None:
            self._end(run_id, "ERROR", type(error).__name__)

        def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
            self.turns.on_chat_model_start(serialized, messages, run_id=run_id, **kwargs)

        def on_llm_end(self, response, *, run_id, **kwargs) -> None:
            self.turns.on_llm_end(response, run_id=run_id, **kwargs)

        def on_llm_error(self, error, *, run_id, **kwargs) -> None:
            self.turns.on_llm_error(error, run_id=run_id, **kwargs)

    return ChatSteps()


def render_chat_result(record: dict, steps: list[dict], turns: list[dict], *, verified_by: str,
                       duration_ms: int) -> list[str]:
    stages = record.get("stages") or {}
    applied = (stages.get("apply") or {}).get("status") == "PASS"
    detail = (record.get("error_detail") or {}).get("message")
    code, evidence = refine_code(record.get("reason"), record)
    klass = classify(record.get("status"), code, detail, applied=applied)
    label = f"class {klass}" + (f" ({code})" if code else "")
    trace = {"result": {}, "calls": steps, "model_calls": turns, "failure_class": {"evidence": evidence},
             "time_breakdown": time_breakdown(duration_ms, steps, turns, {"run": record})}
    lines = [f"== RESULT {record.get('status', DASH)} · {label} · verified by {verified_by}"]
    return lines + render_result(trace)[1:]
