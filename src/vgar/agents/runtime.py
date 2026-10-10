"""Per-run dependencies shared by workflow nodes (not part of graph state).

State must stay serializable; settings, the sandboxed settings that point the
MCP graph server at this run's graph.db, and the agent object live here.
"""
from __future__ import annotations

import shutil
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgar.config.settings import Settings, get_settings

AgentFactory = Callable[[Settings], Awaitable[Any]]


def index_repo(repo: Path, db: Path) -> int:
    """Build the graph snapshot for `repo` into SQLite `db`; return node count."""
    from vgar.graph.builder import PythonGraphBuilder
    from vgar.graph.sqlite_store import SQLiteGraphStore

    doc = PythonGraphBuilder(repo_key=repo.name, repository_revision="cli").build(repo)
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteGraphStore(db).ingest(doc)
    return len(doc["nodes"])


async def default_agent_factory(settings: Settings) -> Any:
    from vgar.agents.core import create_core_agent
    return await create_core_agent(settings)


@dataclass
class Runtime:
    settings: Settings | None = None
    keep_workspace: bool = False
    test_timeout: float = 120.0
    agent_factory: AgentFactory | None = None  # injectable for tests
    sandboxed: Settings | None = None  # set by prepare_workspace
    agent: Any = None  # built lazily by the repair node, reused across retries

    def base_settings(self) -> Settings:
        return self.settings or get_settings()

    async def make_agent(self) -> Any:
        if self.sandboxed is None:
            raise RuntimeError("prepare_workspace must run before the agent is created")
        if self.agent is None:
            if self.agent_factory is not None:
                self.agent = await self.agent_factory(self.sandboxed)
            else:
                self.agent = await default_agent_factory(self.sandboxed)
        return self.agent


def new_work_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="vgar-wf-"))


def cleanup_work_dir(work_dir: Path, keep: bool) -> None:
    if not keep:
        shutil.rmtree(work_dir, ignore_errors=True)