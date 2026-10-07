"""Verified tree-bound graph caches; never trust an unpaired graph/meta artifact."""
from __future__ import annotations

import json
import sys
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from vgar.contracts.schema import validate_graph_document
from vgar.source_scope import SourceScope
from .evidence import sha256, write_json
from .graph_arm import file_hash, verify_python_tree

PACKAGE = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FILES = ("graph/builder.py", "graph/jedi_resolver.py", "contracts/schema.py",
                        "source_scope.py", "evaluation/retrieval/graph_cache.py")


def cache_identity(row: dict, tree: Path, *, use_jedi: bool, builder_hash: str) -> dict:
    meta = verify_python_tree(tree)
    if meta.get("repo") != row["repo"] or meta.get("commit") != row["base_commit"]:
        raise ValueError("Source tree cache belongs to a different repository/commit")
    return {"repository": row["repo"], "commit": row["base_commit"], "tree_hash": meta["tree_hash"],
            "use_jedi": use_jedi, "builder_hash": builder_hash, "source_roots": ["src"],
            "source_scope": SourceScope.for_repository(tree).metadata(),
            "implementation_hashes": {path: file_hash(PACKAGE / path) for path in IMPLEMENTATION_FILES},
            "package_versions": {name: version(name) for name in ("tree-sitter", "tree-sitter-python", "jedi")},
            "python": f"{sys.version_info.major}.{sys.version_info.minor}"}


def load_or_build_graph(root: Path, row: dict, tree: Path, *, use_jedi: bool, rebuild: bool, builder_hash: str):
    from vgar.graph.builder import PythonGraphBuilder

    identity = cache_identity(row, tree, use_jedi=use_jedi, builder_hash=builder_hash)
    root, tree = Path(root).resolve(), Path(tree).resolve()
    key = sha256(json.dumps(identity, sort_keys=True)).removeprefix("sha256:")
    name = f"{row['repo'].replace('/', '__')}-{row['base_commit']}-{key}"
    graph_path = Path(root) / "data/graphs" / f"{name}.json"
    meta_path = graph_path.with_suffix(".meta.json")
    if graph_path.exists() or meta_path.exists():
        if rebuild:
            # Explicit rebuild creates a new pair, not an overwrite of saved evidence.
            graph_path = graph_path.with_name(f"{name}-rebuilt-{uuid.uuid4().hex[:12]}.json")
            meta_path = graph_path.with_suffix(".meta.json")
        else:
            if not graph_path.is_file() or not meta_path.is_file():
                raise ValueError("Incomplete graph cache pair; explicit rebuild required")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("cache_identity") != identity or meta.get("graph_hash") != file_hash(graph_path):
                raise ValueError("Graph cache integrity hash/identity mismatch")
            document = json.loads(graph_path.read_text(encoding="utf-8"))
            _validate_pair(document, meta, row, tree)
            return document, meta | {"cached": True}
    started = time.perf_counter()
    builder = PythonGraphBuilder(repo_key=row["repo"].replace("/", "__"), repository_revision=row["base_commit"], use_jedi=use_jedi)
    document = builder.build(tree)
    meta = {"build_seconds": time.perf_counter() - started, "nodes": len(document["nodes"]), "edges": len(document["edges"]),
            "graph_version": document["graph_version"], "use_jedi": use_jedi, "builder_hash": builder_hash,
            "skipped_failed_files": len(builder.skipped_failed_files), "cache_identity": identity,
            "cache_key": key, "graph_path": str(graph_path.resolve())}
    _validate_pair(document, meta, row, tree)
    write_json(graph_path, document)
    meta["graph_hash"] = file_hash(graph_path)
    write_json(meta_path, meta)
    return document, meta | {"cached": False}


def _validate_pair(document: dict, meta: dict, row: dict, tree: Path) -> None:
    validate_graph_document(document)
    if (document["graph_version"] != meta.get("graph_version")
            or document["repository_revision"] != row["base_commit"]
            or document["repo_key"] != row["repo"].replace("/", "__")
            or len(document["nodes"]) != meta.get("nodes") or len(document["edges"]) != meta.get("edges")):
        raise ValueError("Graph cache pair metadata mismatch")
    scope = SourceScope.for_repository(tree)
    inventory = {path.relative_to(tree).as_posix(): file_hash(path) for path in scope.python_files(tree)}
    if document.get("statistics", {}).get("source_inventory") != inventory:
        raise ValueError("Graph cache source inventory mismatch")
    if document.get("statistics", {}).get("source_scope") != scope.metadata():
        raise ValueError("Graph cache source scope mismatch")
