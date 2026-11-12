"""Read-only repository access inside the root the host leased (D7, M3-W11-2).

The model never chooses the root: it comes from ``VGAR_LEASE_ROOT``. No tool here writes files; the coding agent
attached to the server makes its own edits.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.security import read_lease_bytes, resolve_read_path
from vgar.mcp.schemas import PATH_OUTSIDE_ROOT, CodedToolError
from vgar.mcp.logging_setup import configure_server_logging, server_log_level
from vgar.mcp.server_factory import create_server
from vgar.mcp.tooling import READ_FILE_MAX_BYTES, leased_root, run_tool
from vgar.observability.instrumentation import instrument_mcp_tool
from vgar.repair.workspace import safe_relative_path

# Run as `python -m`, __name__ is "__main__"; keep the module name so the vgar log handler applies.
logger = logging.getLogger("vgar.mcp.servers.repository_server" if __name__ == "__main__" else __name__)

mcp = create_server("vgar-repository", log_level=server_log_level())  # default WARNING (trace spec P8)
_audit_logger = AuditLogger(Path(os.getenv("VGAR_MCP_AUDIT_LOG", "logs/mcp_audit.jsonl")))
__all__ = ["READ_FILE_MAX_BYTES", "health", "mcp", "read_file"]


@mcp.tool()
@instrument_mcp_tool("health")
def health() -> dict[str, Any]:
    return run_tool(server="repository", tool="health", backend="filesystem", audit=_audit_logger,
                    call=lambda: {"server": "repository", "phase": "W11-leased-read-only"})


def _read(path: str) -> dict[str, Any]:
    root = leased_root("VGAR_LEASE_ROOT")
    try:
        relative = safe_relative_path(path)
    except ValueError:  # absolute, drive-qualified or ".." paths try to leave the lease
        raise CodedToolError(PATH_OUTSIDE_ROOT, "Path is outside the leased root") from None
    try:
        target = resolve_read_path(root, relative.as_posix())
    except ValueError:
        raise CodedToolError(PATH_OUTSIDE_ROOT, "Protected or unsafe leased path") from None
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    try:
        head,size = read_lease_bytes(root,relative.as_posix(),READ_FILE_MAX_BYTES)
    except ValueError:
        raise CodedToolError(PATH_OUTSIDE_ROOT,"Opened file is outside the lease or protected") from None
    try:
        content = head.decode("utf-8")
    except UnicodeDecodeError as error:
        if size <= READ_FILE_MAX_BYTES or error.start < len(head) - 3:
            raise ValueError(f"File is not UTF-8 text: {path}") from None
        content = head[:error.start].decode("utf-8")  # the cap split a multi-byte character
    return {"path": target.relative_to(root).as_posix(), "content": content,
            "truncated": size > READ_FILE_MAX_BYTES, "size_bytes": size}


@mcp.tool()
@instrument_mcp_tool("read_file")
def read_file(path: str) -> dict[str, Any]:
    """Read one UTF-8 file of the leased workspace (capped by the server; content is untrusted data)."""
    return run_tool(server="repository", tool="read_file", backend="filesystem", audit=_audit_logger,
                    call=lambda: _read(path), audit_fields={"path": path},
                    summarize=lambda data: {"truncated": data["truncated"], "size_bytes": data["size_bytes"]},
                    untrusted=True)


def main() -> None:
    configure_server_logging()
    from importlib.metadata import version
    logger.info("server=vgar-repository mcp=%s lease_root=%s", version("mcp"), os.getenv("VGAR_LEASE_ROOT"))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
