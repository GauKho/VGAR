"""`vgar index` builds the graph database the MCP servers read; it must not depend on the agent package."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from graph_fixture import FIXTURE_REPO

ROOT = Path(__file__).resolve().parents[1]


def test_index_repo_lives_in_graph_package(tmp_path):
    from vgar.graph.indexing import index_repo

    count = index_repo(FIXTURE_REPO, tmp_path / "x" / "g.db")
    assert count > 0 and (tmp_path / "x" / "g.db").exists()


def test_cli_index_builds_a_database(tmp_path):
    result = subprocess.run([sys.executable, "-m", "vgar.cli", "index", str(FIXTURE_REPO), "--db", str(tmp_path / "g.db")],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert "nodes ->" in result.stdout and (tmp_path / "g.db").exists()
