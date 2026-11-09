"""L2-1: JARVIS results inside the builder, with the Docker run replaced by a fixed answer."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from vgar.contracts.schema import validate_graph_document
from vgar.graph import jarvis_runner
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.jarvis_runner import JARVIS_COMMIT, JarvisConfig, JarvisResult

BUILD_GRAPH = Path(__file__).parent.parent / "scripts" / "build_graph.py"
SOURCE = '''class Box:
    def __init__(self, size):
        self.size = size

    def get(self, key):
        return key


def helper(value):
    return value


def handle(item):
    return item


def confirmed():
    return helper(1)


def direct(obj):
    return obj.get("k")


def via_param(callback):
    return callback(1)


def noise():
    data = {"k": 1}
    data.get("k")
    box = Box(1)
    return box.get("k")
'''
GRAPH = {"app.confirmed": ["app.helper"], "app.direct": ["app.Box.get"], "app.via_param": ["app.handle"],
         "app.noise": ["<map>.get", "app.Box", "app.Box.get", "app.Box.__init__"]}
READY = JarvisResult("ready", graph=GRAPH)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text(SOURCE, encoding="utf-8")
    return root


def _builder(jarvis: JarvisConfig | None = None, roots: tuple[str, ...] = (".",)) -> PythonGraphBuilder:
    return PythonGraphBuilder(repo_key="demo/jarvis", repository_revision="base", source_roots=roots, jarvis=jarvis)


def _build(repo: Path, monkeypatch: pytest.MonkeyPatch, result: JarvisResult = READY, roots: tuple[str, ...] = (".",)) -> dict[str, Any]:
    monkeypatch.setattr(jarvis_runner, "run_jarvis", lambda root, files, source_roots, config: result)
    return _builder(JarvisConfig(), roots).build(repo)


def _by_qualified(document: dict[str, Any], name: str) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["qualified_name"] == name)


def _site(document: dict[str, Any], callee_text: str) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] == "CallSite" and node["properties"]["callee_text"] == callee_text)


def _edges(document: dict[str, Any], edge_type: str, source_id: str) -> list[dict[str, Any]]:
    return [edge for edge in document["edges"] if edge["type"] == edge_type and edge["source_id"] == source_id]


def _jarvis_edges(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in document["edges"] if edge["provenance"]["source_tool"] == "jarvis"]


def _plain_edges(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [{key: value for key, value in edge.items() if key != "graph_version"} for edge in document["edges"]]


def test_off_by_default_changes_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_run(*args: object) -> JarvisResult:
        raise AssertionError("JARVIS must not run when the option is off")

    monkeypatch.setattr(jarvis_runner, "run_jarvis", must_not_run)
    document = _builder().build(repo)
    assert "jarvis" not in document["statistics"] and _jarvis_edges(document) == []
    assert "jarvis_call_count" not in document["statistics"]["resolver"]


def test_on_validates_and_reports(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    validate_graph_document(document)
    report = document["statistics"]["jarvis"]
    assert report["status"] == "ready" and report["reason"] is None and report["image"] == JarvisConfig().image
    assert report["confirmed"] == 2 and report["upgraded"] == 1 and report["external"] == 1
    assert report["new_may_call"] == 1 and report["new_calls"] == 0 and report["edges_total"] == 7 and report["skipped_files"] == []


def test_confirmed_call_gets_evidence_and_more_confidence(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _edges(_builder().build(repo), "CALLS", _site(_builder().build(repo), "helper")["id"])[0]
    document = _build(repo, monkeypatch)
    after = _edges(document, "CALLS", _site(document, "helper")["id"])[0]
    assert "jarvis" in after["provenance"]["evidence"] and after["confidence"] > before["confidence"]
    assert after["provenance"]["source_tool"] == before["provenance"]["source_tool"]


def test_upgrade_replaces_may_call_with_a_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    site = _site(document, "obj.get")
    assert _edges(document, "MAY_CALL", site["id"]) == []
    edge = _edges(document, "CALLS", site["id"])[0]
    assert edge["target_id"] == _by_qualified(document, "app.Box.get")["id"] and edge["confidence"] == 0.75 and edge["resolution"] == "analyzer"
    assert edge["properties"]["binding_kind"] == "jarvis" and edge["properties"]["candidate_rank"] == 1
    assert edge["properties"]["argument_match"] is None and edge["properties"]["confidence_reason"]
    assert edge["provenance"]["source_tool"] == "jarvis" and edge["provenance"]["source_tool_version"] == JARVIS_COMMIT
    assert edge["provenance"]["rule_id"] == "python.call.jarvis.resolve.v1"


def test_upgraded_site_properties(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    properties = _site(_build(repo, monkeypatch), "obj.get")["properties"]
    assert properties["resolution_status"] == "resolved" and properties["candidate_count"] == 1 and properties["resolver"] == "jarvis"


def test_indirect_call_is_may_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    site = _site(document, "callback")
    assert _edges(document, "CALLS", site["id"]) == []
    edge = _edges(document, "MAY_CALL", site["id"])[0]
    assert edge["target_id"] == _by_qualified(document, "app.handle")["id"] and edge["properties"]["match_kind"] == "jarvis_indirect"
    assert edge["confidence"] <= 0.50 and "jarvis_indirect" in edge["provenance"]["evidence"]
    assert edge["provenance"]["rule_id"] == "python.call.may_call.jarvis_indirect.v1"


def test_same_name_sites_stay_uncertain(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    for text in ("data.get", "box.get"):
        site = _site(document, text)
        assert _edges(document, "CALLS", site["id"]) == []
        assert "jarvis" in _edges(document, "MAY_CALL", site["id"])[0]["provenance"]["evidence"]


def test_ambiguous_name_blocks_a_confident_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "app.py").write_text(
        "class C:\n    @property\n    def value(self):\n        return 1\n\n    @value.setter\n    def value(self, v):\n        pass\n\n\n"
        "class D:\n    def value(self):\n        return 2\n\n\ndef use(x):\n    return x.value()\n", encoding="utf-8")
    document = _build(tmp_path, monkeypatch, JarvisResult("ready", graph={"app.use": ["app.C.value", "app.D.value"]}))
    assert _edges(document, "CALLS", _site(document, "x.value")["id"]) == []
    assert document["statistics"]["jarvis"]["ambiguous_names"] == 1


def test_new_constructor_call_targets_the_class(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "app.py").write_text("class Box:\n    def __init__(self):\n        pass\n\n\ndef build(Box):\n    return Box()\n", encoding="utf-8")
    document = _build(tmp_path, monkeypatch, JarvisResult("ready", graph={"app.build": ["app.Box"]}))
    site = _site(document, "Box")
    assert _edges(document, "CALLS", site["id"])[0]["target_id"] == _by_qualified(document, "app.Box")["id"]
    assert site["properties"]["dispatch_kind"] == "constructor"


def test_conflict_sets_confidence_and_evidence(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "app.py").write_text(SOURCE + "\n\nclass Other:\n    def helper(self):\n        return 1\n", encoding="utf-8")
    document = _build(repo, monkeypatch, JarvisResult("ready", graph={"app.confirmed": ["app.Other.helper"]}))
    site = _site(document, "helper")
    assert _edges(document, "CALLS", site["id"])[0]["target_id"] == _by_qualified(document, "app.helper")["id"]
    edge = _edges(document, "MAY_CALL", site["id"])[0]
    assert edge["confidence"] == 0.50 and "conflict_with_call" in edge["provenance"]["evidence"]
    assert edge["properties"]["match_kind"] == "jarvis_conflict" and document["statistics"]["jarvis"]["conflicts"] == 1
    validate_graph_document(document)


def test_external_reason_never_becomes_a_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = PythonGraphBuilder._resolve_calls

    def mark_external(self: PythonGraphBuilder) -> None:
        original(self)
        for node in self.nodes:
            if node["type"] == "CallSite" and node["properties"]["callee_text"] == "obj.get":
                node["properties"]["resolution_reason"] = "external_or_non_callable"

    monkeypatch.setattr(PythonGraphBuilder, "_resolve_calls", mark_external)
    document = _build(repo, monkeypatch)
    site = _site(document, "obj.get")
    assert _edges(document, "CALLS", site["id"]) == [] and len(_edges(document, "MAY_CALL", site["id"])) == 1


def test_class_without_constructor_gets_no_may_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "other.py").write_text("class helper:\n    pass\n", encoding="utf-8")
    document = _build(repo, monkeypatch, JarvisResult("ready", graph={"app.confirmed": ["other.helper"]}))
    assert _edges(document, "MAY_CALL", _site(document, "helper")["id"]) == []
    assert document["statistics"]["jarvis"]["no_call_site"] == 1


def test_may_call_statistics_match_edges(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    edges = [edge for edge in document["edges"] if edge["type"] == "MAY_CALL"]
    stats = document["statistics"]["may_call"]
    assert stats["edge_count"] == len(edges) and stats["callsite_count"] == len({edge["source_id"] for edge in edges})
    assert sum(stats["by_match_kind"].values()) == len(edges) and "jarvis_indirect" in stats["by_match_kind"]
    for edge in edges:
        assert edge["properties"]["candidate_count"] == len(_edges(document, "MAY_CALL", edge["source_id"]))


CALLER = "def g():\n    return 1\n\n\ndef f():\n    return g()\n"


def test_names_follow_a_src_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "a.py").write_text(CALLER, encoding="utf-8")
    document = _build(tmp_path, monkeypatch, JarvisResult("ready", graph={"pkg.a.f": ["pkg.a.g"]}), ("src",))
    assert document["statistics"]["jarvis"]["confirmed"] == 1 and document["statistics"]["jarvis"]["external"] == 0


def test_names_follow_a_package_source_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "xarray").mkdir()
    (tmp_path / "xarray" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "xarray" / "core.py").write_text(CALLER, encoding="utf-8")
    document = _build(tmp_path, monkeypatch, JarvisResult("ready", graph={"xarray.core.f": ["xarray.core.g"]}), ("xarray",))
    assert _by_qualified(document, "core.f")["type"] == "Function"
    assert document["statistics"]["jarvis"]["confirmed"] == 1 and document["statistics"]["jarvis"]["external"] == 0


def test_test_code_is_not_sent_to_jarvis(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text("def helper2():\n    return 1\n", encoding="utf-8")
    seen: list[list[Path]] = []

    def run(root: Path, files: list[Path], source_roots: tuple[str, ...], config: JarvisConfig) -> JarvisResult:
        seen.append(files)
        return READY

    monkeypatch.setattr(jarvis_runner, "run_jarvis", run)
    _builder(JarvisConfig()).build(repo)
    assert [path.name for path in seen[0]] == ["app.py"]


def test_static_count_excludes_jarvis(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = _build(repo, monkeypatch)
    calls = [edge for edge in document["edges"] if edge["type"] == "CALLS"]
    resolver = document["statistics"]["resolver"]
    assert resolver["jarvis_call_count"] == 1 and resolver["static_call_count"] == len(calls) - 1


@pytest.mark.parametrize("status", ["unavailable", "failed", "timeout"])
def test_failure_still_builds(repo: Path, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    document = _build(repo, monkeypatch, JarvisResult(status, "because"))
    validate_graph_document(document)
    assert _jarvis_edges(document) == []
    report = document["statistics"]["jarvis"]
    assert report["status"] == status and report["reason"] == "because" and report["upgraded"] == 0


def test_empty_graph_changes_no_edge(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = _plain_edges(_builder().build(repo))
    document = _build(repo, monkeypatch, JarvisResult("ready", graph={}))
    assert _plain_edges(document) == plain
    report = document["statistics"]["jarvis"]
    assert report["edges_total"] == 0 and report["confirmed"] == 0 and report["new_may_call"] == 0


def test_same_input_gives_the_same_document(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = _build(repo, monkeypatch), _build(repo, monkeypatch)
    assert first["nodes"] == second["nodes"] and first["edges"] == second["edges"]


def test_graph_version_differs_on_and_off(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    off = _builder().build(repo)["graph_version"]
    ready = _build(repo, monkeypatch)["graph_version"]
    failed = _build(repo, monkeypatch, JarvisResult("failed", "x"))["graph_version"]
    assert len({off, ready, failed}) == 3


def _build_graph_module() -> Any:
    spec = importlib.util.spec_from_file_location("build_graph_script", BUILD_GRAPH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arguments(repo: Path, output: Path, *extra: str) -> list[str]:
    return ["build_graph.py", str(repo), str(output), "--repo-key", "demo/jarvis", "--revision", "base", *extra]


def test_cli_warns_when_jarvis_is_not_ready(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(jarvis_runner, "run_jarvis", lambda root, files, source_roots, config: JarvisResult("timeout", "JARVIS_TIMEOUT: x"))
    monkeypatch.setattr(sys, "argv", _arguments(repo, tmp_path / "graph.json", "--enable-jarvis"))
    _build_graph_module().main()
    assert "WARNING: JARVIS timeout: JARVIS_TIMEOUT: x" in capsys.readouterr().err
    assert (tmp_path / "graph.json").exists()


def test_cli_passes_image_and_timeout(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[JarvisConfig] = []

    def run(root: Path, files: list[Path], source_roots: tuple[str, ...], config: JarvisConfig) -> JarvisResult:
        seen.append(config)
        return READY

    monkeypatch.setattr(jarvis_runner, "run_jarvis", run)
    monkeypatch.setattr(sys, "argv", _arguments(repo, tmp_path / "graph.json", "--enable-jarvis", "--jarvis-image", "x", "--jarvis-timeout", "12.5"))
    _build_graph_module().main()
    assert seen == [JarvisConfig(image="x", timeout_seconds=12.5)]


def test_cli_does_not_run_jarvis_without_the_flag(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_run(*args: object) -> JarvisResult:
        raise AssertionError("JARVIS must not run without --enable-jarvis")

    monkeypatch.setattr(jarvis_runner, "run_jarvis", must_not_run)
    monkeypatch.setattr(sys, "argv", _arguments(repo, tmp_path / "graph.json"))
    _build_graph_module().main()
    assert (tmp_path / "graph.json").exists()
