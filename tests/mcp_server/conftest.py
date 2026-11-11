"""Host-only security fixture; no implicit mock mode or production provider registration."""
import time

import pytest


@pytest.fixture
def bound(tmp_path):
    from vgar.mcp.proposal.context import (
        ContextAuthority,
        bind_context,
        source_inventory_hash,
    )
    for name in ("repo", "lease", "output", "state"):
        (tmp_path/name).mkdir()
    authority=ContextAuthority(tmp_path/"state")
    digest="sha256:"+"a"*64
    ctx=bind_context(authority,repo_root=tmp_path/"repo",lease_root=tmp_path/"lease",output_root=tmp_path/"output",
                     request_id="request",run_id="run",task_id="task",snapshot_hash=digest,source_hash=source_inventory_hash(tmp_path/"repo"),
                     config_hash=digest,deadline=time.time()+120,secrets=("synthetic-unshaped-value",))
    return authority,ctx
