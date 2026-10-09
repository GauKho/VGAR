from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vgar.observability.instrumentation import instrument_mcp_tool

from vgar.repair.workspace import safe_relative_path

mcp = FastMCP("vgar-repository")


def _root(repo_path: str) -> Path:
    root = Path(repo_path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a repository directory: {repo_path}")
    return root


@mcp.tool()
@instrument_mcp_tool("health")
def health() -> dict[str, Any]:
    return {"status": "OK", "server": "repository", "phase": "W3-W4-repair"}


@mcp.tool()
@instrument_mcp_tool("read_file")
def read_file(repo_path: str, path: str) -> dict[str, Any]:
    root = _root(repo_path)
    relative = safe_relative_path(path)
    target = (root / relative).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Path escapes repository")
    if not target.is_file():
        raise FileNotFoundError(path)
    return {"status": "OK", "path": relative.as_posix(), "content": target.read_text(encoding="utf-8")}


@mcp.tool()
@instrument_mcp_tool("apply_patch")
def apply_patch(repo_path: str, path: str, old_text: str, new_text: str) -> dict[str, Any]:
    """Apply one exact textual edit. This is intentionally narrower than arbitrary shell editing."""
    root = _root(repo_path)
    relative = safe_relative_path(path)
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError("Path escapes repository")
    if not target.is_file():
        raise FileNotFoundError(path)

    before = target.read_text(encoding="utf-8")
    if old_text not in before:
        return {"status": "FAIL", "path": relative.as_posix(), "error": "old_text not found; patch rejected"}
    if before.count(old_text) != 1:
        return {"status": "FAIL", "path": relative.as_posix(), "error": "old_text is not unique; patch rejected"}

    after = before.replace(old_text, new_text, 1)
    target.write_text(after, encoding="utf-8")
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=relative.as_posix(),
        tofile=relative.as_posix(),
    ))
    return {"status": "PASS", "path": relative.as_posix(), "patch_diff": diff, "changed_files": [relative.as_posix()]}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
