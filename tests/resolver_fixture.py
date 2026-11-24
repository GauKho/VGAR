"""Shared fixtures for tests that run the real SCIP/LSP resolvers (spec 2026-11-24)."""
from __future__ import annotations

import shutil

import pytest

from vgar.graph.layer_config import LSP_RUNTIME, SCIP_RUNTIME

needs_resolvers = pytest.mark.skipif(not (SCIP_RUNTIME.exists() and LSP_RUNTIME.exists() and shutil.which("node")),
                                     reason="SCIP/LSP runtimes or node not installed")

# `r.check()` has no annotation: the static resolver cannot bind it, pyright (SCIP or LSP) can.
CHAIN = {
    "shop/__init__.py": "",
    "shop/repo.py": "class Repo:\n    def check(self):\n        return 1\n",
    "shop/service.py": "from shop.repo import Repo\n\n\ndef make():\n    return Repo()\n\n\n"
                       "def run():\n    r = make()\n    return r.check()\n",
}
