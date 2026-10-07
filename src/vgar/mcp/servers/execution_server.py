from __future__ import annotations

import math
import sys
import time
import traceback
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.config.settings import get_settings
from vgar.contracts.evidence import TestRunResult
from vgar.contracts.repair import FailureReason
from vgar.mcp.audit import AuditLogger
from vgar.mcp.tooling import run_tool
from vgar.mcp.workspace_guard import leased_root, leased_path
from vgar.repair.evidence_writer import begin_run, finish_run
from vgar.repair.test_runner import run_tests, _validate_selector
from vgar.repair.workspace import fingerprint_source

mcp = FastMCP("vgar-execution")
_settings = get_settings()
_audit_logger = AuditLogger(_settings.audit_log)


def _tool(name, call, fields=None, *, verification=False):
    return run_tool(server="execution", tool=name, backend="pytest", audit=_audit_logger,
                    call=call, audit_fields=fields, verification=verification)


@mcp.tool()
def health() -> dict[str, Any]:
    return _tool("health", lambda: {"server": "execution", "phase": "W3-W6",
                                   "workspace_bound": _settings.workspace_root is not None})


@mcp.tool()
def run_pytest(repo_path: str, selector: str, timeout_seconds: int = 30) -> dict[str, Any]:
    """Run the shared bounded M2 pytest wrapper and persist its complete evidence."""
    def call():
        root = leased_root(repo_path, _settings.workspace_root)
        _validate_selector(selector)
        leased_path(root, selector.split("::", 1)[0])
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 240:
            raise ValueError("timeout_seconds must be positive and at most 240")
        before = fingerprint_source(root)
        handle = begin_run(_settings.audit_log.parent / "m2-tool-runs", task_id="mcp-run-pytest",
                           source_repo=root, source_hash_before=before, worktree_id="host-workspace",
                           argv=[sys.executable, "-m", "pytest", selector], cwd=root,
                           timeout_seconds=timeout_seconds)
        started = time.monotonic()
        after = ""
        result = None
        try:
            result = run_tests(root, (selector,), timeout_seconds)
            after = fingerprint_source(root)
        except Exception as exc:
            payload = result.model_dump(mode="json") if result is not None else dict(
                command="pytest invocation failed", argv=[sys.executable, "-m", "pytest", selector],
                exit_code=None, duration_ms=round((time.monotonic() - started) * 1000), stdout="", stderr="")
            payload.update(status="ERROR", complete=False, stderr=payload["stderr"] + "\n" + traceback.format_exc(),
                           reason=FailureReason(code="INTERNAL_ERROR", message=str(exc)), timeout_seconds=timeout_seconds)
            result = TestRunResult(**payload)
        artifact = finish_run(handle, result, source_hash_after=after)
        return {"status": result.status, "selector": selector, "test_result": result.model_dump(mode="json"),
                "artifact_path": str(artifact), "exit_code": result.exit_code,
                "stdout": result.stdout, "stderr": result.stderr,
                "reason": result.reason.model_dump(mode="json") if result.reason else None}

    return _tool("run_pytest", call, {"repo_path": repo_path, "selector": selector,
                                    "timeout_seconds": timeout_seconds}, verification=True)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
