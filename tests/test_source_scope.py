from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.contracts.error import GraphError
from vgar.contracts.evidence import TestRunResult as RunResult
from vgar.repair.workspace import create_workspace, fingerprint_source


def write(root, path, text="def ok(): return 1\n"):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def vgar_source(root):
    write(root, "pyproject.toml", '[project]\nname = "vgar-mcp"\n')
    write(root, "src/vgar/__init__.py", "")
    write(root, "src/vgar/app.py")
    write(root, "tests/test_app.py", "def test_app(): pass\n")
    for directory in ("data/downloads", "data/repositories", "data/graphs", "data/gold", "results", "artifacts", "logs"):
        write(root, f"{directory}/cached.py", "raise RuntimeError('must not index/copy/hash')\n")


def graph(root):
    return PythonGraphBuilder(repo_key="scope/test", repository_revision="fixture", use_jedi=False).build(root)


def test_vgar_cache_is_not_source_but_tests_are_kept(tmp_path):
    vgar_source(tmp_path)
    document = graph(tmp_path)
    assert set(document["statistics"]["source_inventory"]) == {"src/vgar/__init__.py", "src/vgar/app.py", "tests/test_app.py"}
    before = fingerprint_source(tmp_path)
    write(tmp_path, "data/repositories/new_source.py")
    write(tmp_path, "artifacts/changed.json", "{}")
    assert fingerprint_source(tmp_path) == before
    anchor = next(n["id"] for n in document["nodes"] if n["type"] == "Function")
    assert GraphContextRetriever(document, tmp_path, count_tokens=lambda s: len(s.split()), counter_label="test").retrieve([anchor], 1000).context.items
    write(tmp_path, "src/vgar/app.py", "def ok(): return 2\n")
    with pytest.raises(GraphError):
        GraphContextRetriever(document, tmp_path, count_tokens=lambda s: len(s.split()), counter_label="test").retrieve([anchor], 1000)


def test_workspace_matches_graph_scope_and_preserves_size_limits(tmp_path):
    source = tmp_path / "source"
    vgar_source(source)
    write(source, "data/repositories/huge.bin", "x" * 4096)
    expected = fingerprint_source(source)
    with create_workspace(source, tmp_path / "temp", max_file_bytes=1024) as lease:
        assert not (lease.path / "data/repositories").exists()
        assert (lease.path / "tests/test_app.py").exists()
        assert fingerprint_source(lease.path) == expected
        assert graph(source)["statistics"]["source_inventory"] == graph(lease.path)["statistics"]["source_inventory"]


def test_generic_data_results_artifacts_packages_are_not_blanket_ignored(tmp_path):
    for name in ("data", "results", "artifacts", "logs"):
        write(tmp_path / "source", f"{name}/real.py")
    source = tmp_path / "source"
    assert len(graph(source)["statistics"]["source_inventory"]) == 4
    before = fingerprint_source(source)
    write(source, "data/real.py", "def ok(): return 2\n")
    assert fingerprint_source(source) != before
    with create_workspace(source, tmp_path / "temp") as lease:
        assert all((lease.path / name / "real.py").exists() for name in ("data", "results", "artifacts", "logs"))


def test_custom_scope_and_snapshot_use_exact_relative_paths(tmp_path):
    from vgar.source_scope import SourceScope
    write(tmp_path, "data/real.py")
    write(tmp_path, "data/cache/generated.py")
    scope = SourceScope(excluded_paths=("data/cache",))
    document = PythonGraphBuilder(repo_key="scope/test", repository_revision="fixture", use_jedi=False,
                                  source_scope=scope).build(tmp_path)
    assert set(document["statistics"]["source_inventory"]) == {"data/real.py"}
    anchor = next(n["id"] for n in document["nodes"] if n["type"] == "Function")
    retriever = GraphContextRetriever(document, tmp_path, count_tokens=lambda s: len(s.split()), counter_label="test")
    assert retriever.retrieve([anchor], 1000).context.items
    write(tmp_path, "data/cache/new.py")
    assert retriever.retrieve([anchor], 1000).context.items
    write(tmp_path, "data/extra.py")
    with pytest.raises(GraphError):
        retriever.retrieve([anchor], 1000)


@pytest.mark.parametrize("path", ["../source", "C:/source", "/source", "", ".", "data/../src"])
def test_invalid_scope_rejected(path):
    from vgar.source_scope import SourceScope
    with pytest.raises(ValueError):
        SourceScope(excluded_paths=(path,))


def test_exclusions_are_pruned_before_scandir_descent(tmp_path, monkeypatch):
    import os
    from vgar.source_scope import SourceScope
    write(tmp_path, "keep.py")
    write(tmp_path, "cache/deep/ignored.py")
    real = os.scandir

    def guarded(path):
        assert Path(path).name != "cache", "excluded subtree was entered"
        return real(path)

    monkeypatch.setattr(os, "scandir", guarded)
    assert [relative for relative, _ in SourceScope(excluded_paths=("cache",)).files(tmp_path)] == ["keep.py"]


def recorder_module():
    script = Path(__file__).resolve().parents[1] / "scripts/record_m2_test.py"
    spec = importlib.util.spec_from_file_location("m2_recorder_scope_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("error", [TimeoutError("preflight timeout"), OSError("cannot read source")])
def test_recorder_pending_exists_before_preflight_and_error_is_finalized(tmp_path, monkeypatch, error):
    module = recorder_module()
    records = tmp_path / "records"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["record", "tests", "--artifact-dir", str(records)])
    monkeypatch.setenv("VGAR_M2_TEMP_ROOT", str(tmp_path / "temp"))
    invoked = []

    def failing(root, timeout_seconds):
        saved = list(records.glob("*.json"))
        assert len(saved) == 1
        pending = json.loads(saved[0].read_text(encoding="utf-8"))
        assert pending["status"] == "NOT_RUN" and not pending["complete"]
        invoked.append(True)
        raise error

    monkeypatch.setattr(module, "snapshot_source", failing)
    monkeypatch.setattr(module, "run_tests", lambda *args: pytest.fail("pytest must not run after preflight error"))
    assert module.main() != 0
    result = json.loads(next(records.glob("*.json")).read_text(encoding="utf-8"))
    assert invoked and result["complete"] and result["status"] == "ERROR"
    assert result["test_result"]["exit_code"] is None
    assert result["phase"] == "PREFLIGHT_BEFORE"
    assert str(error) in result["test_result"]["stderr"]


def test_postflight_error_preserves_pytest_output_but_never_returns_pass(tmp_path, monkeypatch):
    module = recorder_module()
    records = tmp_path / "records"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["record", "tests", "--artifact-dir", str(records)])
    monkeypatch.setenv("VGAR_M2_TEMP_ROOT", str(tmp_path / "temp"))
    attempts = []

    def snapshot(root, timeout_seconds):
        attempts.append(True)
        if len(attempts) > 1:
            raise TimeoutError("postflight timeout")
        return {"fingerprint": "abc", "scope": {"excluded_paths": []}, "duration_seconds": 0.01}

    monkeypatch.setattr(module, "snapshot_source", snapshot)
    monkeypatch.setattr(module, "run_tests", lambda *args: RunResult(
        status="PASS", command="python -m pytest", argv=["python", "-m", "pytest"],
        exit_code=0, duration_ms=1, stdout="1 passed", stderr=""))
    assert module.main() != 0
    saved = json.loads(next(records.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["status"] == "ERROR" and saved["phase"] == "PREFLIGHT_AFTER"
    assert saved["test_result"]["stdout"] == "1 passed"
    assert saved["source_hash_after"] == ""


def test_source_snapshot_worker_has_real_timeout(tmp_path):
    from vgar.repair.source_preflight import snapshot_source
    write(tmp_path, "ok.py")
    with pytest.raises(TimeoutError):
        snapshot_source(tmp_path, 0.001)
    actual = snapshot_source(tmp_path, 10)
    assert actual["fingerprint"] == fingerprint_source(tmp_path)
    assert actual["duration_seconds"] >= 0


@pytest.mark.parametrize("metadata", [{"excluded_paths": "cache"}, {"excluded_paths": None}, {"excluded_paths": ["../src"]}])
def test_malformed_snapshot_scope_rejected(tmp_path, metadata):
    write(tmp_path, "ok.py")
    document = graph(tmp_path)
    document["statistics"]["source_scope"] = metadata
    with pytest.raises(GraphError):
        GraphContextRetriever(document, tmp_path, count_tokens=lambda s: len(s.split()), counter_label="test")
