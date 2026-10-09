"""Small, dependency-free phase logging helpers for VGAR."""
from __future__ import annotations

import json
import time
import traceback
import uuid
from contextlib import contextmanager
from typing import Any, Iterator


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def summarize(value: Any, *, depth: int = 0, max_string: int = 240) -> Any:
    """Bound log volume; this is not a secrets redactor."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:max_string] + ("..." if len(value) > max_string else "")
    if depth >= 3:
        return f"<{type(value).__name__}>"
    if isinstance(value, dict):
        return {
            str(k): summarize(v, depth=depth + 1, max_string=max_string)
            for k, v in list(value.items())[:30]
        }
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return {
            "type": type(value).__name__,
            "count": len(items),
            "sample": [
                summarize(v, depth=depth + 1, max_string=max_string)
                for v in items[:3]
            ],
        }
    # Avoid serializing arbitrary objects, tensors, model instances, etc.
    return f"<{type(value).__module__}.{type(value).__name__}>"


def emit(event: str, *, run_id: str, phase: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "run_id": run_id,
        "phase": phase,
        **{key: summarize(value) for key, value in fields.items()},
    }
    print("[VGAR] " + json.dumps(payload, ensure_ascii=False, default=str), flush=True)


@contextmanager
def phase(name: str, run_id: str, input_contract: Any = None) -> Iterator[callable]:
    started = time.perf_counter()
    emit("PHASE_START", run_id=run_id, phase=name, input_contract=input_contract)
    try:
        yield lambda output: emit(
            "PHASE_OUTPUT", run_id=run_id, phase=name, output_contract=output
        )
    except Exception as exc:
        emit(
            "PHASE_ERROR",
            run_id=run_id,
            phase=name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback=traceback.format_exc(),
        )
        raise
    else:
        emit(
            "PHASE_END",
            run_id=run_id,
            phase=name,
            status="OK",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
