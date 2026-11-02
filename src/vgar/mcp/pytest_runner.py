"""C6 test runner for execution_server: one allow-listed pytest selector through M2's ``run_bounded``.

``run_bounded`` (vgar.repair.executor) stops the whole process tree on timeout (Windows job object, POSIX
process group) and stops the child as soon as output passes the cap (S4, S5). M2 keeps its signature (C6).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from vgar.mcp.schemas import INTERNAL_ERROR, TIMEOUT, CodedToolError
from vgar.repair.executor import run_bounded


def run_selector(root: Path, selector: str, *, timeout_seconds: int, output_cap: int) -> dict[str, Any]:
    """Run ``pytest -q <selector>`` in ``root``; the selector must already be validated by the caller."""
    record = run_bounded(
        (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", selector), Path(root), timeout_seconds,
        output_cap=output_cap,
        environment={"PYTHONPATH": f"{Path(root) / 'src'}{os.pathsep}{root}", "PYTHONIOENCODING": "utf-8"})
    if record.get("timed_out"):
        raise CodedToolError(TIMEOUT, f"pytest exceeded the server timeout of {timeout_seconds}s")
    if record["status"] == "ERROR" and not record.get("output_truncated"):
        raise CodedToolError(INTERNAL_ERROR, "pytest could not be run")
    return {"exit_code": record["exit_code"], "stdout": record["stdout"][:output_cap],
            "stderr": record["stderr"][:output_cap], "truncated": bool(record.get("output_truncated"))}
