"""SDK selection and framework-free server imports; no model or target execution."""
from __future__ import annotations

from graph_fixture import real_graph_env
import importlib
import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_create_server_is_the_sdk2_mcpserver():
    from mcp.server import MCPServer

    from vgar.mcp.server_factory import create_server
    server = create_server("vgar-test")
    assert isinstance(server, MCPServer) and server.name == "vgar-test"


def test_framework_free_imports_in_fresh_process(tmp_path):
    code = r'''
import importlib, importlib.abc, json, sys
blocked = ('langchain', 'langchain_core', 'langchain_mcp_adapters', 'langgraph', 'torch', 'transformers')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            raise ImportError('forbidden import: '+fullname)
sys.meta_path.insert(0, Guard())
import vgar.mcp
assert 'vgar.mcp.client' not in sys.modules
from vgar.mcp import registry
for name in ('graph','repository','execution'):
    importlib.import_module('vgar.mcp.servers.'+name+'_server')
assert not any(k.split('.')[0] in blocked for k in sys.modules)
print(json.dumps({'imported':3,'forbidden':False}))
'''
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), **real_graph_env(),
           "VGAR_MCP_AUDIT_LOG": str(tmp_path / "audit.jsonl"), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-c", code], env=env, cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"imported": 3, "forbidden": False}


def test_registry_accepts_structural_named_tools_and_preserves_guards():
    registry = importlib.import_module("vgar.mcp.registry")
    tools = [SimpleNamespace(name="graph_search_symbols")]
    assert registry.get_tool_names(tools) == {"graph_search_symbols"}
    registry.validate_public_tools(tools)
    with pytest.raises(RuntimeError, match="Missing required"):
        registry.validate_required_tools(tools, {"graph_get_callers"})
    with pytest.raises(RuntimeError, match="Unguarded"):
        registry.validate_public_tools([SimpleNamespace(name="unsafe")])
