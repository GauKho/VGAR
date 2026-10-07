from __future__ import annotations

import difflib
import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.config.settings import get_settings
from vgar.mcp.audit import AuditLogger
from vgar.mcp.tooling import run_tool
from vgar.mcp.workspace_guard import leased_root, leased_path

mcp = FastMCP("vgar-repository")
_settings = get_settings()
_audit_logger = AuditLogger(_settings.audit_log)
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_EDIT_BYTES = 1024 * 1024


def _tool(name, call, fields=None, *, verification=False):
    return run_tool(server="repository", tool=name, backend="filesystem", audit=_audit_logger,
                    call=call, audit_fields=fields, verification=verification)


def _read(target: Path) -> bytes:
    if not target.is_file():
        raise FileNotFoundError(target.name)
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File size limit exceeded")
    with target.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("File size limit exceeded")
    return data


@mcp.tool()
def health() -> dict[str, Any]:
    return _tool("health", lambda: {"server": "repository", "phase": "W3-W6",
                                   "workspace_bound": _settings.workspace_root is not None})


@mcp.tool()
def read_file(repo_path: str, path: str) -> dict[str, Any]:
    def call():
        root = leased_root(repo_path, _settings.workspace_root)
        target = leased_path(root, path)
        return {"path": target.relative_to(root).as_posix(), "content": _read(target).decode("utf-8")}

    return _tool("read_file", call, {"repo_path": repo_path, "path": path})


@mcp.tool()
def apply_patch(repo_path: str, path: str, old_text: str, new_text: str) -> dict[str, Any]:
    """Apply one exact edit atomically, only within the host-granted workspace."""
    def call():
        root = leased_root(repo_path, _settings.workspace_root)
        target = leased_path(root, path)
        if any(len(text.encode("utf-8")) > MAX_EDIT_BYTES for text in (old_text, new_text)):
            raise ValueError("Edit size limit exceeded")
        raw = _read(target)
        before = raw.decode("utf-8")
        if not old_text or before.count(old_text) != 1:
            return {"status": "FAIL", "path": path,
                    "reason": {"code": "PATCH_APPLY_FAILED",
                               "message": "old_text is missing, empty or not unique; patch rejected"}}
        after = before.replace(old_text, new_text, 1)
        data = after.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Patched file size limit exceeded")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".vgar-edit-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if _read(leased_path(root, path)) != raw:
                raise ValueError("Source changed during exact edit; patch rejected")
            os.chmod(temporary, target.stat().st_mode)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        diff = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                           fromfile=path, tofile=path))
        return {"status": "PASS", "path": path, "patch_diff": diff, "changed_files": [path]}

    return _tool("apply_patch", call, {"repo_path": repo_path, "path": path}, verification=True)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
