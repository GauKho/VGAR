"""Give every test process a real graph by default.

``vgar.mcp.servers.graph_server`` builds its graph service when imported, and the
server only serves real graphs. Build the architecture fixture once and point the
test environment at it; tests that need another graph set their own values.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_fixture import FIXTURE_REPO, build_fixture_database  # noqa: E402

_DATABASE, _VERSION = build_fixture_database(Path(tempfile.mkdtemp(prefix="vgar-test-graph-")))
# Assign, not setdefault: importing vgar may already have loaded the developer's .env,
# whose relative database path breaks subprocesses started in another working directory.
os.environ["VGAR_GRAPH_BACKEND"] = "sqlite"
os.environ["VGAR_GRAPH_DATABASE"] = str(_DATABASE)
os.environ["VGAR_REPOSITORY_ROOT"] = str(FIXTURE_REPO)
os.environ.pop("VGAR_GRAPH_VERSION", None)
