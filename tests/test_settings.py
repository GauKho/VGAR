import pytest

from vgar.config import get_settings, reload_settings
from vgar.config import settings as settings_module
from vgar.mcp.client import create_mcp_client
from vgar.models.factory import create_core_model


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module, "load_env", lambda *_a, **_k: None)  # ignore real .env
    for key in ("HF_MODEL_ID", "MAX_NEW_TOKENS", "VGAR_GRAPH_BACKEND", "VGAR_GRAPH_DATABASE",
                "VGAR_GRAPH_VERSION", "VGAR_TEMPERATURE", "VGAR_MODEL_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    yield
    get_settings.cache_clear()


def test_defaults():
    s = reload_settings()
    assert s.model.max_new_tokens == 512 and s.graph.backend == "demo" and s.graph.database is None


def test_env_overrides_and_blank_means_default(monkeypatch):
    monkeypatch.setenv("MAX_NEW_TOKENS", "1024")
    monkeypatch.setenv("VGAR_GRAPH_VERSION", "")
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "SQLite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", "artifacts/x.db")
    s = reload_settings()
    assert s.model.max_new_tokens == 1024 and s.graph.version is None
    assert s.graph.backend == "sqlite" and s.graph.database.is_absolute()


def test_bad_number_names_the_variable(monkeypatch):
    monkeypatch.setenv("MAX_NEW_TOKENS", "lots")
    with pytest.raises(ValueError, match="MAX_NEW_TOKENS"):
        reload_settings()


def test_factory_rejects_unsupported_before_importing_torch(monkeypatch):
    monkeypatch.setenv("VGAR_MODEL_PROVIDER", "nope")
    with pytest.raises(ValueError, match="nope"):
        create_core_model(reload_settings().model)
    monkeypatch.setenv("VGAR_MODEL_PROVIDER", "huggingface")
    monkeypatch.setenv("VGAR_TEMPERATURE", "0.7")
    with pytest.raises(ValueError, match="greedy"):
        create_core_model(reload_settings().model)


def test_mcp_children_get_vgar_env_but_no_secrets(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    monkeypatch.setenv("VGAR_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("VGAR_GRAPH_DATABASE", "artifacts/x.db")
    client = create_mcp_client(reload_settings())
    for conn in client.connections.values():
        assert "HF_TOKEN" not in conn["env"]
        assert conn["env"]["VGAR_GRAPH_BACKEND"] == "sqlite"
