from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vgar-execution")


def _root(repo_path: str) -> Path:
    root = Path(repo_path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a repository directory: {repo_path}")
    return root


@mcp.tool()
def health() -> dict[str, Any]:
    return {"status": "OK", "server": "execution", "phase": "W3-W4-repair"}


@mcp.tool()
def run_pytest(repo_path: str, selector: str, timeout_seconds: int = 30) -> dict[str, Any]:
    """Run one bounded pytest selector inside the supplied disposable workspace."""
    if not selector or selector.startswith("-") or "\n" in selector or "\r" in selector:
        raise ValueError("Invalid pytest selector")
    root = _root(repo_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", selector]
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            env=env,
            # The MCP stdio pipe is this process's stdin/stdout: the child must
            # never inherit stdin (hangs/handle errors on Windows).
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # Windows default cp1252 would raise on pytest's UTF-8 output
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "exit_code": None, "selector": selector, "stdout": "", "stderr": "",
                "error": {"code": "TEST_TIMEOUT", "message": f"pytest exceeded {timeout_seconds}s"}}
    except OSError as exc:
        return {"status": "ERROR", "exit_code": None, "selector": selector, "stdout": "", "stderr": "",
                "error": {"code": "INTERNAL_ERROR", "message": f"cannot start pytest: {exc}"}}
    return {
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "selector": selector,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()