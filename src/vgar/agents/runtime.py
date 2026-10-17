"""Per-run dependencies shared by workflow nodes (not part of graph state).

State must stay serializable; settings and other per-run objects live here.
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vgar.config.settings import Settings, get_settings
from vgar.repair.config import CONFIG_DIR, REPO_ROOT


def index_repo(repo: Path, db: Path) -> int:
    """Build the graph snapshot for `repo` into SQLite `db`; return node count."""
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_store import SQLiteGraphStore

    doc = PythonGraphBuilder(repo_key=repo.name, repository_revision="cli").build(repo)
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteGraphStore(db).ingest(doc)
    return len(doc["nodes"])


@dataclass
class Runtime:
    settings: Settings | None = None
    keep_workspace: bool = False
    mode: Literal["fake", "real"] = "fake"
    config_path: Path = CONFIG_DIR / "demo.json"
    output_root: Path = REPO_ROOT / "results/solve"
    generator: Any = None  # test override for the generator build_generation selects
    tools: dict[str, Any] | None = None  # MCP repair tools, built once per runtime

    def base_settings(self) -> Settings:
        return self.settings or get_settings()

    async def repair_tools(self) -> dict[str, Any]:
        """The four repair_* MCP tools; only the repair server is connected."""
        if self.tools is None:
            from vgar.mcp.client import create_mcp_client
            client = create_mcp_client(self.base_settings(), servers=("repair",))
            self.tools = {tool.name: tool for tool in await client.get_tools()}
        return self.tools


def new_work_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="vgar-wf-"))


def cleanup_work_dir(work_dir: Path, keep: bool) -> None:
    if not keep:
        shutil.rmtree(work_dir, ignore_errors=True)