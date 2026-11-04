"""Run one host-allowed pytest selector inside the leased root (D7, M3-W11-2; S3-S5 of M3-W11-1).

The root comes from ``VGAR_LEASE_ROOT`` and the allowed selectors from ``VGAR_ALLOWED_SELECTORS`` (JSON list),
both set by the host. Timeout and output cap are server constants; argv is fixed and never goes through a shell.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.mcp import pytest_runner
from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import SELECTOR_REJECTED, CodedToolError
from vgar.mcp.tooling import PYTEST_OUTPUT_CAP, PYTEST_TIMEOUT_SECONDS, inside, leased_root, run_tool
from vgar.observability.instrumentation import instrument_mcp_tool

mcp = FastMCP("vgar-execution", log_level="WARNING")  # no per-request INFO lines (trace spec P8)
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))
__all__ = ["PYTEST_OUTPUT_CAP", "PYTEST_TIMEOUT_SECONDS", "health", "mcp", "run_pytest"]


@mcp.tool()
@instrument_mcp_tool("health")
def health() -> dict[str, Any]:
    return run_tool(server="execution", tool="health", backend="pytest", audit=_audit_logger,
                    call=lambda: {"server": "execution", "phase": "W11-leased-allow-listed"})


def _check_selector(root: Path, selector: str) -> None:
    allowed = json.loads(os.environ.get("VGAR_ALLOWED_SELECTORS", "[]"))
    if (not isinstance(selector, str) or not selector or selector.startswith("-")
            or any(char.isspace() for char in selector) or ".." in selector):
        raise CodedToolError(SELECTOR_REJECTED, "Selector is not a plain pytest node id or path")
    if not any(selector == entry or selector.startswith((entry + "/", entry + "::")) for entry in allowed):
        raise CodedToolError(SELECTOR_REJECTED, "Selector is not allowed for this task")
    try:
        inside(root, root / selector.split("::", 1)[0])
    except CodedToolError:
        raise CodedToolError(SELECTOR_REJECTED, "Selector path leaves the leased root") from None


def _run(selector: str) -> dict[str, Any]:
    root = leased_root("VGAR_LEASE_ROOT")
    _check_selector(root, selector)
    result = pytest_runner.run_selector(root, selector, timeout_seconds=PYTEST_TIMEOUT_SECONDS,
                                        output_cap=PYTEST_OUTPUT_CAP)
    return {"selector": selector, "verdict": "PASS" if result["exit_code"] == 0 else "FAIL", **result}


@mcp.tool()
@instrument_mcp_tool("run_pytest")
def run_pytest(selector: str) -> dict[str, Any]:
    """Run one allowed pytest selector in the leased workspace (server-set timeout and output cap)."""
    return run_tool(server="execution", tool="run_pytest", backend="pytest", audit=_audit_logger,
                    call=lambda: _run(selector), audit_fields={"selector": selector},
                    summarize=lambda data: {"verdict": data["verdict"], "truncated": data["truncated"]},
                    untrusted=True)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
