import pytest

from vgar.config import get_settings, reload_settings
from vgar.config import settings as settings_module


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module, "load_env", lambda *_a, **_k: None)  # ignore real .env
    for key in ("VGAR_GRAPH_BACKEND", "VGAR_GRAPH_DATABASE", "VGAR_GRAPH_VERSION", "VGAR_MCP_AUDIT_LOG"):
        monkeypatch.delenv(key, raising=False)
    yield
    get_settings.cache_clear()


def test_defaults():
    s = reload_settings()
    assert s.graph.backend == "sqlite" and s.graph.database is None and s.graph.version is None


def test_env_overrides_and_blank_means_default(monkeypatch):
    monkeypatch.setenv("VGAR_GRAPH_VERSION", "")
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "SQLite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", "artifacts/x.db")
    s = reload_settings()
    assert s.graph.version is None
    assert s.graph.backend == "sqlite" and s.graph.database.is_absolute()
