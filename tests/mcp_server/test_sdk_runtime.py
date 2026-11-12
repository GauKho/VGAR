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


@pytest.mark.parametrize("version,module_name,class_name", [
    ("1.30.0", "mcp.server.fastmcp", "FastMCP"),
    ("2.2.0", "mcp.server", "MCPServer"),
])
def test_factory_selects_only_installed_major(monkeypatch, version, module_name, class_name):
    from vgar.mcp import server_factory
    calls = []

    class Server:
        def __init__(self, name, *, log_level):
            self.name, self.log_level = name, log_level

    def load(name):
        calls.append(name)
        assert name == module_name
        return SimpleNamespace(**{class_name: Server})

    monkeypatch.setattr(server_factory.metadata, "version", lambda name: version)
    monkeypatch.setattr(server_factory, "import_module", load)
    result = server_factory.create_server("vgar-test")
    assert (result.name, result.log_level) == ("vgar-test", "WARNING")
    assert calls == [module_name]


@pytest.mark.parametrize("version", ["0.9.0", "3.0.0", "broken", "", "2garbage"])
def test_factory_rejects_unsupported_or_malformed_without_import(monkeypatch, version):
    from vgar.mcp import server_factory
    monkeypatch.setattr(server_factory.metadata, "version", lambda name: version)
    monkeypatch.setattr(server_factory, "import_module", lambda name: pytest.fail("must not import"))
    with pytest.raises(RuntimeError, match="MCP"):
        server_factory.create_server("test")


def test_factory_missing_distribution_is_explicit(monkeypatch):
    from vgar.mcp import server_factory

    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(server_factory.metadata, "version", missing)
    with pytest.raises(RuntimeError, match="MCP"):
        server_factory.create_server("test")


def test_sdk2_import_error_never_falls_back(monkeypatch):
    from vgar.mcp import server_factory
    monkeypatch.setattr(server_factory.metadata, "version", lambda name: "2.2.0")
    calls = []

    def broken(name):
        calls.append(name)
        raise ModuleNotFoundError("SDK2 dependency absent")

    monkeypatch.setattr(server_factory, "import_module", broken)
    with pytest.raises(ModuleNotFoundError, match="SDK2 dependency absent"):
        server_factory.create_server("test")
    assert calls == ["mcp.server"]


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
