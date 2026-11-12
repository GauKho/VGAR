"""The MCP graph backend serves real graphs only (spec §7.8, H8)."""
from __future__ import annotations

import importlib.util

import pytest

from graph_fixture import build_fixture_database
from vgar.config import settings as settings_module
from vgar.graph.factory import create_graph_service


def test_demo_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "demo")
    with pytest.raises(RuntimeError, match="vgar index"):
        create_graph_service()


def test_default_backend_is_sqlite_and_needs_a_database(monkeypatch):
    monkeypatch.delenv("VGAR_GRAPH_BACKEND", raising=False)
    monkeypatch.delenv("VGAR_GRAPH_DATABASE", raising=False)
    with pytest.raises(RuntimeError, match="VGAR_GRAPH_DATABASE"):
        create_graph_service()


def test_missing_database_file_fails_at_startup(monkeypatch, tmp_path):
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(tmp_path / "absent.db"))
    with pytest.raises(RuntimeError, match="absent.db"):
        create_graph_service()
    assert not (tmp_path / "absent.db").exists()


def test_fixture_database_serves_real_symbols(monkeypatch, tmp_path):
    database, version = build_fixture_database(tmp_path)
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", str(database))
    monkeypatch.delenv("VGAR_GRAPH_VERSION", raising=False)
    service = create_graph_service()
    assert service.backend_name == "sqlite"
    assert service.get_repository_summary().graph_version == version
    assert any(symbol.path.startswith("app/") for symbol in service.search_symbols("service").symbols)


def test_settings_default_backend_is_sqlite(monkeypatch):
    # _build() reads os.environ only; reload_settings() would also load the repo's .env.
    monkeypatch.delenv("VGAR_GRAPH_BACKEND", raising=False)
    assert settings_module._build().graph.backend == "sqlite"


def test_no_module_provides_the_demo_service():
    assert importlib.util.find_spec("vgar.graph.demo_service") is None
