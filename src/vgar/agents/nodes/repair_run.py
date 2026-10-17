from __future__ import annotations

import json
from pathlib import Path

from vgar.agents.runtime import Runtime
from vgar.agents.state import VGARState
from vgar.observability.instrumentation import instrument_node


@instrument_node("repair_run")
def repair_run(state: VGARState, runtime: Runtime) -> dict:
    """The only generation: one M2 pipeline run (prompt -> diff -> worktree -> verification)."""
    from vgar.repair.config import load_config, load_task
    from vgar.repair.pipeline import build_generation, run_repair

    try:
        task = load_task(state["task_path"])
        policy, profile = load_config(runtime.config_path)
        generator, tokenizer, counter = build_generation(runtime.mode, task, policy, profile, runtime.output_root)
    except Exception as exc:  # bad task/config/generator setup ends the run FAILED, like cmd_repair's ERROR record
        return {"attempts": 0, "repair_status": "ERROR", "failure_reason": f"{type(exc).__name__}: {exc}"}
    if runtime.generator is not None:
        generator = runtime.generator
    run = run_repair(task, policy, generator, None, runtime.output_root,
                     m1_counter=counter, tokenizer=tokenizer,
                     profile=profile if runtime.mode == "real" else None,
                     temp_root=Path(state["work_dir"]), keep_workspace=runtime.keep_workspace)
    bundle = run.directory / "evidence_bundle.json"
    status = run.record["status"]
    reason = None if status == "PASS" else run.record.get("reason") or status
    detail = (run.record.get("error_detail") or {}).get("message")
    if status == "ERROR" and detail:
        reason = f"{reason}: {detail}"  # the bare code alone does not say what went wrong
    return {
        "attempts": 1,
        "run_record_path": str(run.path),
        "evidence": json.loads(bundle.read_text(encoding="utf-8")) if bundle.is_file() else {},
        "repair_status": status,
        "failure_reason": reason,
    }
