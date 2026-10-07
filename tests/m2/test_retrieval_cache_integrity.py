from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

from vgar.evaluation.retrieval.evidence import sha256, source_fingerprint
from vgar.evaluation.retrieval.graph_arm import extract_python_tree

SHA = "a" * 40


def tree_fixture(tmp_path):
    archive = tmp_path / "archive.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        data = b"def f(): return 1\n"
        member = tarfile.TarInfo(f"r-{SHA}/src/app.py")
        member.size = len(data)
        bundle.addfile(member, io.BytesIO(data))
    tree = tmp_path / "tree"
    extract_python_tree(archive, "o/r", SHA, tree)
    return archive, tree


@pytest.mark.parametrize("change", ["same_size", "add", "delete"])
def test_cached_tree_checks_current_file_set_and_raw_bytes(tmp_path, change):
    archive, tree = tree_fixture(tmp_path)
    if change == "same_size":
        (tree / "src/app.py").write_bytes(b"def f(): return 2\n")
    elif change == "add":
        (tree / "added.py").write_bytes(b"pass\n")
    else:
        (tree / "src/app.py").unlink()
    with pytest.raises(ValueError, match="integrity|hash|file set"):
        extract_python_tree(archive, "o/r", SHA, tree)


def test_marker_is_not_enough_when_tree_has_no_valid_inventory(tmp_path):
    archive, tree = tree_fixture(tmp_path)
    marker = tree / ".vgar_tree.json"
    meta = json.loads(marker.read_text(encoding="utf-8"))
    meta["tree_hash"] = "sha256:" + "0" * 64
    marker.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity|hash"):
        extract_python_tree(archive, "o/r", SHA, tree)


def test_unowned_existing_tree_and_interrupted_partial_are_not_deleted(tmp_path):
    archive, _ = tree_fixture(tmp_path)
    destination = tmp_path / "unowned"
    destination.mkdir()
    (destination / "keep.txt").write_text("user content", encoding="utf-8")
    partial = destination.with_name(destination.name + ".partial")
    partial.mkdir()
    (partial / "keep.txt").write_text("checkpoint", encoding="utf-8")
    with pytest.raises(ValueError, match="existing|marker|unowned"):
        extract_python_tree(archive, "o/r", SHA, destination)
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "user content"
    assert (partial / "keep.txt").read_text(encoding="utf-8") == "checkpoint"


def runner():
    path = Path(__file__).resolve().parents[2] / "scripts/run_graph_retrieval.py"
    spec = importlib.util.spec_from_file_location("graph_runner_cache_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_cache(tmp_path):
    archive, tree = tree_fixture(tmp_path)
    module = runner()
    row = {"repo": "o/r", "base_commit": SHA}
    document, meta = module.load_or_build_graph(tmp_path, row, tree, use_jedi=False, rebuild=False, builder_hash="test-builder")
    return module, tree, row, document, meta


@pytest.mark.parametrize("change", ["graph", "meta", "missing_meta"])
def test_graph_cache_pair_integrity_is_verified(tmp_path, change):
    module, tree, row, _, _ = build_cache(tmp_path)
    graph_path = next(path for path in (tmp_path / "data/graphs").glob("*.json") if not path.name.endswith(".meta.json"))
    meta_path = graph_path.with_suffix(".meta.json")
    if change == "graph":
        document = json.loads(graph_path.read_text(encoding="utf-8"))
        document["nodes"][0]["name"] = "tampered"
        graph_path.write_text(json.dumps(document), encoding="utf-8")
    elif change == "meta":
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["graph_version"] = "sha256:" + "0" * 64
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    else:
        meta_path.unlink()
    with pytest.raises(ValueError, match="cache|integrity|hash|pair"):
        module.load_or_build_graph(tmp_path, row, tree, use_jedi=False, rebuild=False, builder_hash="test-builder")


def test_graph_cache_implementation_identity_covers_resolver_schema_scope_and_parser(tmp_path):
    _, _, _, _, meta = build_cache(tmp_path)
    identity = meta["cache_identity"]
    assert {"graph/builder.py", "graph/jedi_resolver.py", "contracts/schema.py", "source_scope.py"} <= set(identity["implementation_hashes"])
    assert {"tree-sitter", "tree-sitter-python", "jedi"} <= set(identity["package_versions"])
    assert identity["tree_hash"].startswith("sha256:")
    assert meta["graph_hash"].startswith("sha256:")


def test_graph_cache_reuse_has_validated_pair_and_unchanged_bytes(tmp_path):
    module, tree, row, document, meta = build_cache(tmp_path)
    paths = list((tmp_path / "data/graphs").glob("*.json"))
    before = {path.name: sha256(path.read_bytes()) for path in paths}
    cached, cache_meta = module.load_or_build_graph(tmp_path, row, tree, use_jedi=False, rebuild=False, builder_hash="test-builder")
    assert cached == document and cache_meta["cached"]
    assert before == {path.name: sha256(path.read_bytes()) for path in paths}


def test_graph_cache_accepts_relative_cli_root_and_tree(tmp_path, monkeypatch):
    _, tree = tree_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    module = runner()
    row = {"repo": "o/r", "base_commit": SHA}
    built, _ = module.load_or_build_graph(Path("."), row, Path("tree"), use_jedi=False, rebuild=False, builder_hash="relative")
    reused, meta = module.load_or_build_graph(Path("."), row, Path("tree"), use_jedi=False, rebuild=False, builder_hash="relative")
    assert built == reused and meta["cached"]


def test_cached_tree_rejects_root_reparse_metadata(tmp_path, monkeypatch):
    from types import SimpleNamespace
    archive, tree = tree_fixture(tmp_path)
    original = Path.lstat

    def lstat(path):
        stat = original(path)
        return SimpleNamespace(st_mode=stat.st_mode, st_file_attributes=0x400) if path == tree else stat

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError, match="root|junction|link"):
        extract_python_tree(archive, "o/r", SHA, tree)


def test_fingerprint_includes_nested_tests_fixtures_and_config_not_data_cache(tmp_path):
    paths = ["src/vgar/app.py", "tests/m2/test_nested.py", "tests/unit/test_unit.py",
             "tests/fixtures/gold.json", "config/retrieval.json", "pyproject.toml", "uv.lock"]
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="utf-8")
    (tmp_path / "data/repositories").mkdir(parents=True)
    (tmp_path / "data/repositories/ignore.py").write_text("must not hash", encoding="utf-8")
    before = source_fingerprint(tmp_path)
    assert set(paths) <= set(before["files"])
    assert not any(path.startswith("data/") for path in before["files"])
    (tmp_path / "tests/m2/test_nested.py").write_text("changed", encoding="utf-8")
    assert source_fingerprint(tmp_path)["digest"] != before["digest"]
