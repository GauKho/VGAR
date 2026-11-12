"""Run one host-allowed pytest selector inside the leased root (D7, M3-W11-2; S3-S5 of M3-W11-1).

The root comes from ``VGAR_LEASE_ROOT`` and the allowed selectors from ``VGAR_ALLOWED_SELECTORS`` (JSON list),
both set by the host. Timeout and output cap are server constants; argv is fixed and never goes through a shell.
"""
from __future__ import annotations

import hashlib
import logging

import anyio
import json
import os
from pathlib import Path
from typing import Any

from vgar.mcp import pytest_runner
from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.contracts import DiffRequest
from vgar.mcp.proposal.ports import ProviderRegistry
from vgar.mcp.proposal.tools import CoreTools
from vgar.mcp.schemas import SELECTOR_REJECTED, CodedToolError
from vgar.mcp.logging_setup import configure_server_logging, server_log_level
from vgar.mcp.server_factory import create_server
from vgar.mcp.tooling import (
    PYTEST_OUTPUT_CAP,
    PYTEST_TIMEOUT_SECONDS,
    inside,
    leased_root,
    run_tool,
    run_tool_async,
)
from vgar.observability.instrumentation import instrument_mcp_tool

# Run as `python -m`, __name__ is "__main__"; keep the module name so the vgar log handler applies.
logger = logging.getLogger("vgar.mcp.servers.execution_server" if __name__ == "__main__" else __name__)

mcp = create_server("vgar-execution", log_level=server_log_level())  # default WARNING (trace spec P8)
core_tools = CoreTools(ProviderRegistry())
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))
_graph_service = None  # created on first use, so importing this server needs no graph


def _service():
    """The graph service for guide-style test runs, created lazily from the environment."""
    global _graph_service
    if _graph_service is None:
        from vgar.graph.factory import create_graph_service
        _graph_service = create_graph_service()
    return _graph_service
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


@mcp.tool()
@instrument_mcp_tool("run_relevant_tests")
async def run_relevant_tests(diff: str) -> dict[str, Any]:
    """Run the tests related to a patch on a temporary copy, before and after applying it.

    The repository is never modified. Tests are chosen from the graph (TESTS edges and callers).

    Args:
        diff: Unified diff against the served snapshot's source.
    """
    if core_tools.registry.get("tests") is None:
        def call() -> dict[str, Any]:
            from vgar.repair.patch_evidence import run_patch_tests
            service = _service()
            version = service.get_repository_summary().graph_version
            return run_patch_tests(service, diff, graph_version=version, timeout_seconds=PYTEST_TIMEOUT_SECONDS,
                                   output_cap=PYTEST_OUTPUT_CAP)

        # pytest runs can take minutes: run them off the event loop (build-server guide: stay responsive).
        return await run_tool_async(server="execution", tool="run_relevant_tests", backend="pytest", audit=_audit_logger,
                        call=lambda: anyio.to_thread.run_sync(call), audit_fields={"diff_sha256": "sha256:" + hashlib.sha256(diff.encode("utf-8")).hexdigest()},
                        summarize=lambda data: {"verdict": data["status"], "test_count": len(data["selectors"])},
                        untrusted=True)
    return await core_tools.respond_async("run_relevant_tests", lambda: DiffRequest.from_diff(diff),
                                          server="execution", audit=_audit_logger, invoke=core_tools.tests)


def main() -> None:
    if core_tools.registry.test_only:
        raise ValueError("Synthetic registry is forbidden in production entrypoint")
    configure_server_logging()
    from importlib.metadata import version
    logger.info("server=vgar-execution mcp=%s backend=%s database=%s repository_root=%s lease_root=%s",
                version("mcp"), os.getenv("VGAR_GRAPH_BACKEND", "sqlite"), os.getenv("VGAR_GRAPH_DATABASE"),
                os.getenv("VGAR_REPOSITORY_ROOT"), os.getenv("VGAR_LEASE_ROOT"))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
