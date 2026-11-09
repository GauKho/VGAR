from __future__ import annotations

import ast
import hashlib
import os
import re
import symtable
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from vgar.contracts.schema import EDGE_ENDPOINTS, G_CODE_EDGE_TYPES, PROFILE_FULL_VGAR_MCP, SCHEMA_VERSION, validate_graph_document
from vgar.graph import arch_lift, code_graph, jarvis_merge, jarvis_runner, joern_runner, layer1_rules, may_call, tsg_extractor
from vgar.graph.code_graph import JoernMethod
from vgar.graph.jarvis_merge import Site, Target
from vgar.graph.jarvis_runner import JarvisConfig, JarvisResult
from vgar.graph.joern_runner import JoernConfig, JoernResult
from vgar.graph.tsg_extractor import TsgConfig, TsgError, TsgFileFacts
from vgar.graph.scip_resolver import ScipConfig, ScipResolver, prepare_scip, current_fingerprint
from vgar.graph.lsp_resolver import LspConfig, resolve_lsp_calls
from vgar.graph.method_aliases import annotate_method_aliases, file_alias_candidates
from vgar.observability.graph_trace import GraphTrace


IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    ".venv-win",
    ".venv-m1",
    ".m1-test-tmp",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
_MISSING = object()
# Bump whenever call/import resolution changes (B10 -> v4). Recorded in statistics.resolver.profile and bound
# to the context sidecar at handoff; NOT part of graph_version (E5 option (iii), docs/m3_w11_decisions.md).
RESOLVER_PROFILE = "tree-sitter+python-static-v4-external-import"
BUILDER_VERSION = f"vgar-python-graph-builder-0.1.0+{may_call.RULE_VERSION}+{arch_lift.RULE_VERSION}"
# Frozen resolver label inside graph_version. graph_version is printed in every repair prompt, so keeping it
# stable lets W10 cells whose context is unchanged be reused (E5). Never bump this; bump RESOLVER_PROFILE.
GRAPH_VERSION_RESOLVER_LABEL = "tree-sitter+python-static-v3-method-aliases"


def discover_python_files(root: Path) -> list[Path]:
    """One source inventory policy shared by building and snapshot validation."""
    files = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in IGNORED_DIRECTORY_NAMES
                          and not (Path(directory) / name).is_symlink())
        files.extend(Path(directory) / name for name in filenames
                     if name.endswith(".py") and not (Path(directory) / name).is_symlink())
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


@dataclass
class _ModuleState:
    module_name: str
    module_id: str
    path: str
    is_package: bool
    definitions: dict[str, str] = field(default_factory=dict)
    imported_symbols: dict[str, tuple[str, str]] = field(default_factory=dict)
    imported_modules: dict[str, str] = field(default_factory=dict)
    import_records: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _CallRecord:
    node_id: str
    module_name: str
    path: str
    line: int
    column: int
    callee_text: str
    owner_class_name: str | None
    caller_id: str
    caller_type: str


@dataclass
class _ClassRecord:
    node_id: str
    module_name: str
    class_name: str
    bases: list[str]


class PythonGraphBuilder:
    """Build documents that follow the frozen VGAR graph contract."""

    _emit_may_call: bool = True

    def __init__(
        self,
        *,
        repo_key: str,
        repository_revision: str,
        source_roots: tuple[str, ...] = ("src",),
        scip: ScipConfig | None = None,
        lsp: LspConfig | None = None,
        trace: GraphTrace | None = None,
        tsg: TsgConfig | None = None,
        joern: JoernConfig | None = None,
        jarvis: JarvisConfig | None = None,
    ) -> None:
        if not repo_key.strip():
            raise ValueError("repo_key must not be empty")
        if not repository_revision.strip():
            raise ValueError("repository_revision must not be empty")

        self.repo_key = repo_key.strip()
        self.repository_revision = repository_revision.strip()
        self.source_roots = source_roots
        self.scip_config = scip
        self.lsp_config = lsp
        self.tsg_config = tsg
        self.tsg_report: dict[str, Any] | None = None
        self.joern_config = joern
        self.code_graph_report: dict[str, Any] | None = None
        self.jarvis_config = jarvis
        self.jarvis_report: dict[str, Any] | None = None
        self.arch_report: dict[str, Any] = {}
        self._deployment_files: list[arch_lift.DeploymentFile] = []
        self.lsp_results: dict[str, tuple[str, list[str]]] = {}
        self.trace = trace or GraphTrace()
        self.scip_resolver: ScipResolver | None = None
        self.resolver_report = {"requested": "static", "active": "static", "status": "ready"}
        self.parser = Parser(Language(tree_sitter_python.language()))
        self.repository_root: Path | None = None

        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.nodes_by_id: dict[str, dict[str, Any]] = {}
        self.modules: dict[str, _ModuleState] = {}
        self.symbols_by_qualified_name: dict[str, str] = {}
        self.unique_symbols_by_name: dict[str, str] = {}
        self.calls: list[_CallRecord] = []
        self.classes: list[_ClassRecord] = []
        self.scope_tables: dict[str, symtable.SymbolTable] = {}
        self.scope_parents: dict[str, str] = {}
        self.typed_parameters: dict[str, dict[str, str]] = {}
        self.unmodified_parameters: dict[str, set[str]] = {}
        self._index_changes: list[tuple[dict, str, Any]] | None = None
        self.graph_version = ""
        self.legacy_graph_version = ""
        self.skipped_overload_count: int = 0
        self.renamed_duplicate_count: int = 0
        self.skipped_failed_files: list[dict[str, str]] = []
        self._may_call_by_kind: Counter[str] = Counter()
        self._may_call_callsites = 0
        self._may_call_skipped_over_cap = 0

    def build(self, repository_root: str | Path) -> dict[str, Any]:
        started_at = time.perf_counter()
        root = Path(repository_root).resolve()
        if not root.is_dir():
            raise ValueError(f"repository root does not exist: {root}")
        self.repository_root = root
        if self.nodes:
            raise ValueError("Use a new PythonGraphBuilder for each graph snapshot")

        python_files = self._discover_python_files(root)
        lsp_sources = current_fingerprint(root) if self.lsp_config is not None else None
        if self.lsp_config is not None:
            from vgar.graph.scip_profile import auxiliary_fingerprint
            lsp_inputs = auxiliary_fingerprint(root)
        self.trace.emit("build_start", repo_key=self.repo_key, source_count=len(python_files))
        scip_index = None
        if self.scip_config is not None:
            scip_index, self.resolver_report = prepare_scip(root, python_files, self.scip_config, self.trace)
        tsg_facts = self._collect_tsg_facts(root, python_files) if self.tsg_config is not None else {}
        joern_result = self._run_joern(root, python_files) if self.joern_config is not None else None
        jarvis_result = self._run_jarvis(root, python_files) if self.jarvis_config is not None else None
        self._deployment_files = arch_lift.find_deployment_files(root, IGNORED_DIRECTORY_NAMES)
        self.graph_version = self._calculate_graph_version(root, python_files)

        repository_id = f"vgar:{self.repo_key}:repository"
        self._add_node(
            {
                "id": repository_id,
                "type": "Repository",
                "repo_key": self.repo_key,
                "name": root.name,
                "qualified_name": self.repo_key,
                "path": None,
                "language": None,
                "range": None,
                "properties": {
                    "root_uri": root.as_uri(),
                    "default_language": "python",
                    "repository_revision": self.repository_revision,
                },
                "content_hash": self._hash_text(self.repository_revision),
                "graph_version": self.graph_version,
            }
        )

        for file_path in python_files:
            self._extract_file(root, file_path, repository_id)
        if tsg_facts:
            self._merge_tsg_facts(root, tsg_facts)

        for qualified, target in annotate_method_aliases(root, self.nodes, candidates=self._alias_candidates):
            self.symbols_by_qualified_name[qualified] = target
        self._build_unique_symbol_index()
        self._link_imports()
        self._link_inheritance()
        if self.tsg_report is not None and self.tsg_report["status"] in {"ready", "partial"}:
            self._derive_layer1_facts()
        if scip_index is not None:
            try:
                self.scip_resolver = ScipResolver(scip_index, root, self.nodes, trace=self.trace)
                self.resolver_report["definition_mapping"] = self.scip_resolver.statistics
            except (OSError, ValueError, UnicodeError) as error:
                self.resolver_report.update(active="static", status="fallback", reason=str(error),
                                            error_type=type(error).__name__)
                self.trace.emit("resolver_fallback", **self.resolver_report)
                if self.scip_config.strict:
                    raise
        if self.lsp_config is not None:
            if current_fingerprint(root) != lsp_sources or auxiliary_fingerprint(root) != lsp_inputs:
                raise ValueError("Repository changed before LSP resolution")
            eligible = self._lsp_eligible_calls()
            self.lsp_results, lsp_report = resolve_lsp_calls(root, self.nodes, eligible, self.lsp_config, self.trace)
            self.resolver_report["lsp"] = lsp_report
            if self.scip_config is None:
                self.resolver_report.update(requested="lsp", active=lsp_report["active"],
                    status=lsp_report["status"], reason=lsp_report["reason"])
            # LSP answers are known after extraction. IDs are source-derived;
            # update the snapshot on every existing node/edge before linking calls.
            self.graph_version = self._calculate_graph_version(root, python_files)
            for item in [*self.nodes, *self.edges]:
                item["graph_version"] = self.graph_version
        self._resolve_calls()
        if self.scip_resolver is not None:
            self._link_chain_references()
        if jarvis_result is not None and jarvis_result.status == "ready":
            self._apply_jarvis(root, jarvis_result)
        call_edges = [edge for edge in self.edges if edge["type"] == "CALLS"]
        self.resolver_report.update(scip_call_count=sum(edge["properties"]["binding_kind"] == "scip" for edge in call_edges),
                                    static_call_count=sum(edge["properties"]["binding_kind"] not in {"scip", "lsp", "jarvis"} for edge in call_edges))
        if self.jarvis_config is not None:
            self.resolver_report["jarvis_call_count"] = sum(edge["properties"]["binding_kind"] == "jarvis" for edge in call_edges)
        if self.lsp_config is not None:
            self.resolver_report["lsp_call_count"] = sum(edge["properties"]["binding_kind"] == "lsp" for edge in call_edges)
            if current_fingerprint(root) != lsp_sources or auxiliary_fingerprint(root) != lsp_inputs:
                raise ValueError("Repository changed during LSP graph construction")
        if scip_index is not None and current_fingerprint(root) != scip_index["source_fingerprint"]:
            raise ValueError("Repository changed during SCIP graph construction; rebuild the snapshot")
        if scip_index is not None:
            from vgar.graph.scip_profile import auxiliary_fingerprint
            if auxiliary_fingerprint(root) != scip_index["auxiliary_inputs"]:
                raise ValueError("SCIP config/stubs changed during graph construction")
        if joern_result is not None and joern_result.status == "ready":
            self._add_code_graph(root, joern_result)
        self._lift_architecture()

        document = {
            "graph_version": self.graph_version,
            "repo_key": self.repo_key,
            "repository_revision": self.repository_revision,
            "nodes": self.nodes,
            "edges": self.edges,
            "statistics": self._statistics(started_at),
        }
        self._validate(document)
        document["statistics"]["resolver"] = dict(self.resolver_report, profile=RESOLVER_PROFILE)
        if self.tsg_report is not None:
            document["statistics"]["tsg"] = self.tsg_report
        if self.code_graph_report is not None:
            document["statistics"]["code_graph"] = self.code_graph_report
        if self.jarvis_report is not None:
            document["statistics"]["jarvis"] = self.jarvis_report
        document["statistics"]["arch"] = self.arch_report
        self.trace.emit("build_complete", graph_version=self.graph_version, node_count=len(self.nodes),
                        edge_count=len(self.edges), unresolved_call_count=document["statistics"]["unresolved_call_count"],
                        resolver=self.resolver_report)
        return document

    def _validate(self, document: dict[str, Any]) -> None:
        """Validation hook; the incremental builder trusts items replayed from its cache."""
        validate_graph_document(document)

    def _parse_python_ast(self, root: Path, path: str) -> ast.Module:
        """AST of one repository file for method-alias annotation; a hook so it can be cached."""
        return ast.parse((root / path).read_bytes(), filename=path)

    def _alias_candidates(self, root: Path, path: str, symbols: list[dict[str, Any]]) -> list[tuple[str, str, dict]]:
        """Per-file method-alias analysis; a hook so the incremental builder can cache it per file content."""
        try:
            tree = self._parse_python_ast(root, path)
        except (SyntaxError, UnicodeError):
            return []
        return file_alias_candidates(tree, symbols)

    def _discover_python_files(self, root: Path) -> list[Path]:
        return discover_python_files(root)

    def _calculate_graph_version(
        self,
        root: Path,
        files: list[Path],
    ) -> str:
        digest = hashlib.sha256()
        digest.update(self.repo_key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(self.repository_revision.encode("utf-8"))
        digest.update(b"\0resolver:")
        digest.update(GRAPH_VERSION_RESOLVER_LABEL.encode("utf-8"))
        if self.scip_config is not None:
            digest.update(b"\0scip-enrichment-v5-subset-root:")
            digest.update(self.resolver_report.get("semantic_sha256", self.resolver_report.get("error_type", "unavailable")).encode())
        if self.lsp_config is not None:
            digest.update(b"\0lsp-definition-v1:")
            digest.update(self.resolver_report.get("lsp", {}).get("semantic_sha256", "pending").encode())
        if self.tsg_config is not None:
            report = self.tsg_report or {}
            digest.update(b"\0tsg-facts-v2:")
            digest.update(f"{report.get('rules_sha256', 'unavailable')}:{len(report.get('failed_files', []))}".encode())
        if self.joern_config is not None:
            status = (self.code_graph_report or {}).get("status", "unavailable")
            digest.update(f"\0joern-code-graph-v1:{self.joern_config.image}:{status}".encode())
        if self.jarvis_config is not None:
            status = (self.jarvis_report or {}).get("status", "unavailable")
            digest.update(f"\0jarvis-call-graph-v1:{self.jarvis_config.image}:{jarvis_runner.JARVIS_COMMIT}:{status}".encode())
        digest.update(b"\0file-range:full-bytes-v1")
        digest.update(b"\0source-roots:")
        digest.update(repr(self.source_roots).encode("utf-8"))
        for path in files:
            digest.update(b"\0")
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
        # The W10 identity stops here, so legacy projections keep the graph_version frozen by E5.
        self.legacy_graph_version = f"sha256:{digest.hexdigest()}"
        digest.update(f"\0schema:{SCHEMA_VERSION}\0builder:{BUILDER_VERSION}\0resolver-profile:{RESOLVER_PROFILE}".encode())
        for item in self._deployment_files:
            digest.update(f"\0deployment:{item.path}\0".encode())
            digest.update(item.data)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _is_setter_decorator(decorators: list[str]) -> bool:
        """Check whether any decorator is a property-setter pattern like @x.setter."""
        for dec in decorators:
            stripped = dec.lstrip("@").split("#", 1)[0].strip()
            if re.fullmatch(r"[A-Za-z_]\w*\.(setter|deleter)", stripped):
                return True
        return False

    @staticmethod
    def _is_overload_decorator(decorators: list[str]) -> bool:
        """Return True when any decorator resolves to the typing.overload builtin."""
        for dec in decorators:
            name = dec.lstrip("@").split("#", 1)[0].strip().rsplit(".", 1)[-1].split("(", 1)[0]
            if name == "overload":
                return True
        return False

    def _extract_file(
        self,
        root: Path,
        file_path: Path,
        repository_id: str,
    ) -> None:
        self.extract_source(file_path.relative_to(root).as_posix(), file_path.read_bytes(), repository_id)

    def extract_source(self, relative_path: str, source: bytes, repository_id: str) -> None:
        """Add the facts of one file given its content; reads nothing from disk."""
        file_name = PurePosixPath(relative_path).name
        tree = self.parser.parse(source)
        root_node = tree.root_node
        # Snapshot before this file so rollback removes only this file's nodes.

        file_id = f"vgar:{self.repo_key}:python:file:{relative_path}"
        # Tree-sitter may start its module after leading whitespace. File and
        # Module hashes cover the full file, so their ranges must do so too.
        file_range = {
            "start_line": 1, "start_col": 0, "start_byte": 0,
            "end_line": source.count(b"\n") + 1,
            "end_col": len(source.rsplit(b"\n", 1)[-1]), "end_byte": len(source),
        }
        self._add_node(
            {
                "id": file_id,
                "type": "File",
                "repo_key": self.repo_key,
                "name": file_name,
                "qualified_name": relative_path,
                "path": relative_path,
                "language": "python",
                "range": file_range,
                "properties": {
                    "extension": ".py",
                    "size_bytes": len(source),
                    "parse_status": "partial" if root_node.has_error else "parsed",
                    "is_test_file": self._is_test_path(relative_path),
                },
                "content_hash": self._hash_bytes(source),
                "graph_version": self.graph_version,
            }
        )
        self._add_edge(
            "CONTAINS",
            repository_id,
            file_id,
            confidence=1.0,
            resolution="exact",
            rule_id="repository.file.v1",
            properties={"ordinal": len(self.modules)},
        )

        # Keep the File inventory even if symbol extraction fails: retrieval
        # validates the complete source snapshot, including failed files.
        nodes_before, edges_before = len(self.nodes), len(self.edges)
        calls_before, classes_before = len(self.calls), len(self.classes)
        self._index_changes = []
        overload_before, duplicate_before = self.skipped_overload_count, self.renamed_duplicate_count

        module_name = self._module_name(relative_path)
        module_id = (
            f"vgar:{self.repo_key}:python:module:{relative_path}:{module_name}"
        )
        self._add_node(
            {
                "id": module_id,
                "type": "Module",
                "repo_key": self.repo_key,
                "name": module_name.rsplit(".", 1)[-1],
                "qualified_name": module_name,
                "path": relative_path,
                "language": "python",
                "range": file_range,
                "properties": {
                    "module_name": module_name,
                    "is_package": file_name == "__init__.py",
                    "is_external": False,
                    "resolution_status": "resolved",
                },
                "content_hash": self._hash_bytes(source),
                "graph_version": self.graph_version,
            }
        )
        self._add_edge(
            "CONTAINS",
            file_id,
            module_id,
            confidence=1.0,
            resolution="exact",
            rule_id="python.file.module.v1",
            properties={"ordinal": 0},
        )

        module = _ModuleState(
            module_name=module_name,
            module_id=module_id,
            path=relative_path,
            is_package=file_name == "__init__.py",
        )
        previous_module = self.modules.get(module_name)
        self.modules[module_name] = module
        try:
            self._index_scopes(source, module)
            self._walk_scope(
                root_node,
                source,
                module,
                parent_id=module_id,
                parent_type="Module",
                parent_qualified_name=module_name,
                owner_class_name=None,
            )
        except Exception as exc:  # noqa: BLE001 - isolate file errors
            # Only roll back nodes added for this specific file, plus edges referencing them.
            self.nodes[nodes_before:] = []
            self.nodes_by_id = {node["id"]: node for node in self.nodes}
            self.edges[edges_before:] = []
            self.calls[calls_before:] = []
            self.classes[classes_before:] = []
            for index, key, previous in reversed(self._index_changes):
                if previous is _MISSING:
                    index.pop(key, None)
                else:
                    index[key] = previous
            self.skipped_overload_count, self.renamed_duplicate_count = overload_before, duplicate_before
            self.nodes_by_id[file_id]["properties"]["parse_status"] = "failed"
            if previous_module is None:
                self.modules.pop(module_name, None)
            else:
                self.modules[module_name] = previous_module
            self.skipped_failed_files.append({"path": relative_path, "error_type": type(exc).__name__, "error": str(exc)})
            self.trace.emit("file_parse_error", path=relative_path, error_type=type(exc).__name__, reason=str(exc))
        finally:
            self._index_changes = None

    def _set_index(self, index: dict, key: str, value: Any) -> None:
        if self._index_changes is not None:
            self._index_changes.append((index, key, index.get(key, _MISSING)))
        index[key] = value

    def _walk_scope(
        self,
        scope_node: Node,
        source: bytes,
        module: _ModuleState,
        *,
        parent_id: str,
        parent_type: str,
        parent_qualified_name: str,
        owner_class_name: str | None,
    ) -> None:
        ordinal = 0
        body = scope_node.child_by_field_name("body") or scope_node
        for child in body.named_children:
            definition = child
            decorators: list[str] = []
            if child.type == "decorated_definition":
                decorators = [
                    self._text(item, source)
                    for item in child.named_children
                    if item.type == "decorator"
                ]
                definitions = [
                    item
                    for item in child.named_children
                    if item.type in {"class_definition", "function_definition"}
                ]
                if not definitions:
                    continue
                if self._is_overload_decorator(decorators):
                    self.skipped_overload_count += len(definitions)
                    continue
                definition = definitions[-1]

            if definition.type == "class_definition":
                class_id, class_name, qualified_name = self._extract_class(
                    definition,
                    source,
                    module,
                    parent_id,
                    parent_qualified_name,
                    decorators,
                    ordinal,
                )
                self._walk_scope(
                    definition,
                    source,
                    module,
                    parent_id=class_id,
                    parent_type="Class",
                    parent_qualified_name=qualified_name,
                    owner_class_name=qualified_name,
                )
                ordinal += 1
                continue

            if definition.type == "function_definition":
                function_id, function_type, qualified_name = self._extract_function(
                    definition,
                    source,
                    module,
                    parent_id,
                    parent_type,
                    parent_qualified_name,
                    owner_class_name,
                    decorators,
                    ordinal,
                )
                self._walk_function_body(
                    definition,
                    source,
                    module,
                    parent_id=function_id,
                    parent_type=function_type,
                    parent_qualified_name=qualified_name,
                    owner_class_name=owner_class_name,
                )
                ordinal += 1
                continue

            if parent_type == "Module" and definition.type in {
                "import_statement",
                "import_from_statement",
            }:
                self._extract_import(
                    definition,
                    source,
                    module,
                    parent_id,
                    ordinal,
                )
                ordinal += 1

            # Conditional definitions still belong to the current Python scope.
            if definition.type not in {"import_statement", "import_from_statement", "expression_statement"}:
                for nested in definition.named_children:
                    # else/elif/except/finally wrap their block in a clause node.
                    if nested.type in {"elif_clause", "else_clause", "except_clause", "finally_clause"}:
                        nested = next((item for item in nested.named_children if item.type == "block"), nested)
                    if nested.type == "block":
                        self._walk_scope(nested, source, module, parent_id=parent_id,
                                         parent_type=parent_type, parent_qualified_name=parent_qualified_name,
                                         owner_class_name=owner_class_name)

    def _walk_function_body(
        self,
        function_node: Node,
        source: bytes,
        module: _ModuleState,
        *,
        parent_id: str,
        parent_type: str,
        parent_qualified_name: str,
        owner_class_name: str | None,
    ) -> None:
        body = function_node.child_by_field_name("body")
        if body is None:
            return

        call_ordinal = 0

        def visit(node: Node) -> None:
            nonlocal call_ordinal
            if node is not body and node.type in {
                "function_definition",
                "class_definition",
            }:
                return
            if node.type == "call":
                self._extract_call(
                    node,
                    source,
                    module,
                    parent_id,
                    parent_type,
                    parent_qualified_name,
                    owner_class_name,
                    call_ordinal,
                )
                call_ordinal += 1
            for child in node.named_children:
                visit(child)

        visit(body)

        self._walk_scope(
            function_node,
            source,
            module,
            parent_id=parent_id,
            parent_type=parent_type,
            parent_qualified_name=parent_qualified_name,
            owner_class_name=owner_class_name,
        )

    def _extract_class(
        self,
        node: Node,
        source: bytes,
        module: _ModuleState,
        parent_id: str,
        parent_qualified_name: str,
        decorators: list[str],
        ordinal: int,
    ) -> tuple[str, str, str]:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            raise ValueError("class definition has no name")
        name = self._text(name_node, source)
        qualified_name = f"{parent_qualified_name}.{name}"
        node_id = f"vgar:{self.repo_key}:python:class:{module.path}:{qualified_name}"
        if node_id in self.nodes_by_id:
            node_id += f"@definition:{node.start_point.row + 1}:{node.start_point.column}"
            self.renamed_duplicate_count += 1
        superclasses = node.child_by_field_name("superclasses")
        bases = (
            [self._text(child, source) for child in superclasses.named_children]
            if superclasses is not None
            else []
        )
        self._add_node(
            self._source_node(
                node_id=node_id,
                node_type="Class",
                name=name,
                qualified_name=qualified_name,
                path=module.path,
                node=node,
                source=source,
                properties={
                    "bases": bases,
                    "decorators": decorators,
                    "is_abstract": any("abstract" in item.lower() for item in decorators),
                    "docstring_summary": None,
                },
            )
        )
        self._add_edge(
            "CONTAINS",
            parent_id,
            node_id,
            confidence=1.0,
            resolution="exact",
            rule_id="python.scope.class.v1",
            properties={"ordinal": ordinal},
        )
        if self.nodes_by_id.get(parent_id, {}).get("type") == "Module":
            module.definitions[name] = node_id
        self._set_index(self.symbols_by_qualified_name, qualified_name, node_id)
        self.classes.append(
            _ClassRecord(
                node_id=node_id,
                module_name=module.module_name,
                class_name=name,
                bases=bases,
            )
        )
        return node_id, name, qualified_name

    def _extract_function(
        self,
        node: Node,
        source: bytes,
        module: _ModuleState,
        parent_id: str,
        parent_type: str,
        parent_qualified_name: str,
        owner_class_name: str | None,
        decorators: list[str],
        ordinal: int,
    ) -> tuple[str, str, str]:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            raise ValueError("function definition has no name")
        name = self._text(name_node, source)
        qualified_name = f"{parent_qualified_name}.{name}"
        is_test = (
            name.startswith("test_")
            and parent_type in {"Module", "Class"}
            and self._is_test_path(module.path)
        )
        node_type = "Test" if is_test else ("Method" if parent_type == "Class" else "Function")
        id_kind = node_type.lower()
        accessor = self._is_setter_decorator(decorators)
        suffix = (".deleter" if any(".deleter" in dec for dec in decorators) else ".setter") if accessor else ""
        if suffix:
            self.renamed_duplicate_count += 1
        node_id = f"vgar:{self.repo_key}:python:{id_kind}:{module.path}:{qualified_name}{suffix}"
        if node_id in self.nodes_by_id:
            node_id += f"@definition:{node.start_point.row + 1}:{node.start_point.column}"
            self.renamed_duplicate_count += 1

        if node_type == "Test":
            properties: dict[str, Any] = {
                "framework": "pytest",
                "test_kind": "method" if parent_type == "Class" else "function",
                "markers": decorators,
                "test_command_hint": f"pytest {module.path}::{name}",
            }
        else:
            parameters_node = node.child_by_field_name("parameters")
            return_type = node.child_by_field_name("return_type")
            properties = {
                "signature": self._signature(node, source),
                "parameters": self._parameter_names(parameters_node, source),
                "return_annotation": (
                    self._text(return_type, source) if return_type is not None else None
                ),
                "decorators": decorators,
                "is_async": any(
                    child.type == "async" for child in node.children
                ),
                "visibility": self._visibility(name),
            }
            if node_type == "Method":
                properties.update(
                    {
                        "method_kind": self._method_kind(decorators),
                        "owner_class_id": parent_id,
                    }
                )

        self._add_node(
            self._source_node(
                node_id=node_id,
                node_type=node_type,
                name=name,
                qualified_name=qualified_name,
                path=module.path,
                node=node,
                source=source,
                properties=properties,
            )
        )
        self._add_edge(
            "CONTAINS",
            parent_id,
            node_id,
            confidence=1.0,
            resolution="exact",
            rule_id="python.scope.function.v1",
            properties={"ordinal": ordinal},
        )
        if parent_type == "Module":
            module.definitions[name] = node_id
        if not accessor:
            self._set_index(self.symbols_by_qualified_name, qualified_name, node_id)
        return node_id, node_type, qualified_name

    def _extract_import(
        self,
        node: Node,
        source: bytes,
        module: _ModuleState,
        parent_id: str,
        ordinal: int,
    ) -> None:
        raw_text = self._text(node, source)
        try:
            statement = ast.parse(raw_text).body[0]
        except (SyntaxError, IndexError) as error:
            raise ValueError(f"cannot parse import {raw_text!r}") from error

        if isinstance(statement, ast.Import):
            records = [
                (alias.name, None, alias.asname, 0)
                for alias in statement.names
            ]
        elif isinstance(statement, ast.ImportFrom):
            imported_module = "." * statement.level + (statement.module or "")
            records = [
                (imported_module, alias.name, alias.asname, statement.level)
                for alias in statement.names
            ]
        else:
            return

        for index, (imported_module, imported_name, alias, level) in enumerate(records):
            local_name = alias or imported_name or imported_module.split(".", 1)[0]
            identity = self._short_hash(
                f"{module.path}:{node.start_byte}:{index}:{imported_module}:{imported_name}:{alias}"
            )
            node_id = (
                f"vgar:{self.repo_key}:python:import:{module.path}:"
                f"{node.start_point.row + 1}:{node.start_point.column}:{identity}"
            )
            qualified_name = f"{module.module_name}::<import:{local_name}:{identity}>"
            self._add_node(
                self._source_node(
                    node_id=node_id,
                    node_type="Import",
                    name=local_name,
                    qualified_name=qualified_name,
                    path=module.path,
                    node=node,
                    source=source,
                    properties={
                        "raw_text": raw_text,
                        "imported_module": imported_module,
                        "imported_name": imported_name,
                        "alias": alias,
                        "level": level,
                        "resolution_status": "unresolved",
                    },
                )
            )
            self._add_edge(
                "CONTAINS",
                parent_id,
                node_id,
                confidence=1.0,
                resolution="exact",
                rule_id="python.module.import.v1",
                properties={"ordinal": ordinal + index},
            )
            normalized_module = self._normalize_import_module(
                module,
                imported_module,
                level,
            )
            module.import_records.append((node_id, normalized_module))
            if imported_name is not None:
                module.imported_symbols[local_name] = (
                    normalized_module,
                    imported_name,
                )
            else:
                module.imported_modules[local_name] = normalized_module

    def _extract_call(
        self,
        node: Node,
        source: bytes,
        module: _ModuleState,
        parent_id: str,
        parent_type: str,
        parent_qualified_name: str,
        owner_class_name: str | None,
        ordinal: int,
    ) -> None:
        function_node = node.child_by_field_name("function")
        arguments_node = node.child_by_field_name("arguments")
        if function_node is None:
            return
        callee_text = self._text(function_node, source)
        identity = self._short_hash(
            f"{module.path}:{node.start_byte}:{node.end_byte}:{callee_text}"
        )
        node_id = (
            f"vgar:{self.repo_key}:python:callsite:{module.path}:"
            f"{parent_qualified_name}:{identity}"
        )
        dispatch_kind = "attribute" if "." in callee_text else "direct"
        self._add_node(
            self._source_node(
                node_id=node_id,
                node_type="CallSite",
                name=callee_text,
                qualified_name=f"{parent_qualified_name}::<call:{ordinal + 1}>",
                path=module.path,
                node=node,
                source=source,
                properties={
                    "callee_text": callee_text,
                    "argument_count": (
                        arguments_node.named_child_count
                        if arguments_node is not None
                        else 0
                    ),
                    "dispatch_kind": dispatch_kind,
                    "resolution_status": "unresolved",
                    "candidate_count": 0,
                },
            )
        )
        self._add_edge(
            "CONTAINS",
            parent_id,
            node_id,
            confidence=1.0,
            resolution="exact",
            rule_id=f"python.{parent_type.lower()}.callsite.v1",
            properties={"ordinal": ordinal},
        )
        self.calls.append(
            _CallRecord(
                node_id=node_id,
                module_name=module.module_name,
                path=module.path,
                line=function_node.end_point.row + 1,
                column=function_node.end_point.column,
                callee_text=callee_text,
                owner_class_name=owner_class_name,
                caller_id=parent_id,
                caller_type=parent_type,
            )
        )

    def _link_imports(self) -> None:
        for module in self.modules.values():
            for import_id, imported_module in module.import_records:
                target_module = self.modules.get(imported_module)
                if target_module is None:
                    target_id = self._external_module(imported_module)
                    resolution = "exact"
                    status = "external"
                else:
                    target_id = target_module.module_id
                    resolution = "exact"
                    status = "resolved"

                if import_id not in self.nodes_by_id:
                    continue
                self.nodes_by_id[import_id]["properties"]["resolution_status"] = status
                properties = self.nodes_by_id[import_id]["properties"]
                self._add_edge(
                    "IMPORTS",
                    import_id,
                    target_id,
                    confidence=1.0,
                    resolution=resolution,
                    rule_id="python.import.resolve.v1",
                    properties={
                        "imported_name": properties["imported_name"],
                        "alias": properties["alias"],
                        "is_wildcard": properties["imported_name"] == "*",
                    },
                )

    def _link_inheritance(self) -> None:
        for record in self.classes:
            if record.module_name not in self.modules:
                continue
            module = self.modules[record.module_name]
            linked_bases: dict[str, dict[str, Any]] = {}
            for position, base_expression in enumerate(record.bases, start=1):
                target_id = self._resolve_symbol(
                    module,
                    base_expression,
                    owner_class_name=None,
                )
                if target_id == record.node_id:
                    # Bases are evaluated before binding the new class name.
                    # `from external import Parser; class Parser(Parser)`
                    # must never become a self inheritance edge.
                    current = self.nodes_by_id[record.node_id]
                    previous = [node["id"] for node in self.nodes
                                if node["type"] == "Class" and node["id"] != record.node_id
                                and node["qualified_name"] == current["qualified_name"]
                                and node["path"] == current["path"]
                                and node["range"]["start_line"] < current["range"]["start_line"]]
                    imported = module.imported_symbols.get(base_expression)
                    target_id = previous[0] if len(previous) == 1 else (
                        self.symbols_by_qualified_name.get(f"{imported[0]}.{imported[1]}")
                        if not previous and imported else None)
                if target_id == record.node_id:
                    continue
                if target_id is None:
                    continue
                if target_id not in self.nodes_by_id:
                    continue
                target = self.nodes_by_id[target_id]
                if target["type"] != "Class":
                    continue
                if target_id in linked_bases:
                    # Invalid-code examples can repeat a base. Preserve its
                    # occurrences on one relation instead of duplicating its ID.
                    properties = linked_bases[target_id]["properties"]
                    occurrences = properties.setdefault("base_occurrences", [{
                        "base_expression": properties["base_expression"],
                        "mro_position": properties["mro_position"],
                    }])
                    occurrences.append({"base_expression": base_expression,
                                        "mro_position": position})
                    continue
                self._add_edge(
                    "INHERITS",
                    record.node_id,
                    target_id,
                    confidence=0.9,
                    resolution="analyzer",
                    rule_id="python.inheritance.resolve.v1",
                    properties={
                        "base_expression": base_expression,
                        "mro_position": position,
                    },
                )
                linked_bases[target_id] = self.edges[-1]

    def _lsp_eligible_calls(self) -> list[_CallRecord]:
        """Use LSP for missing/weak bindings; preserve authoritative SCIP answers."""
        eligible = []
        for call in self.calls:
            if call.module_name not in self.modules:
                continue
            if self.scip_resolver is not None:
                status, _ = self.scip_resolver.resolve(call.path, call.line, call.column)
                if status in {"resolved", "ambiguous", "external_or_non_callable", "local_non_callable"}:
                    continue
            module = self.modules[call.module_name]
            bound, target = self._resolve_lexical_binding(call)
            if target is None and not bound:
                target = self._resolve_symbol(module, call.callee_text, owner_class_name=call.owner_class_name)
            if target is None:
                target = self._resolve_typed_receiver(call)
            imported = module.imported_symbols.get(call.callee_text)
            exact_import = self.symbols_by_qualified_name.get(f"{imported[0]}.{imported[1]}") if imported else None
            weak = (self.unique_symbols_by_name.get(call.callee_text) == target
                    and call.callee_text not in module.definitions and exact_import != target)
            if target is None or weak:
                eligible.append(call)
        return sorted(eligible, key=lambda c: (c.path, c.line, c.column, c.node_id))

    def _index_may_call_targets(self) -> None:
        self._may_call_by_name: dict[str, list[str]] = {}
        for node in self.nodes:
            if node["type"] in {"Function", "Method", "Class"}:
                self._may_call_by_name.setdefault(node["name"], []).append(node["id"])
        self._may_call_constructors: dict[str, list[str]] = {}
        self._may_call_owner_class: dict[str, str] = {}
        for edge in self.edges:
            if edge["type"] != "CONTAINS":
                continue
            owner, member = self.nodes_by_id[edge["source_id"]], self.nodes_by_id[edge["target_id"]]
            if owner["type"] != "Class" or member["type"] != "Method":
                continue
            self._may_call_owner_class[member["id"]] = owner["id"]
            if member["name"] in {"__init__", "__new__"}:
                self._may_call_constructors.setdefault(owner["id"], []).append(member["id"])
        self._may_call_module_by_path = {state.path: name for name, state in self.modules.items()}
        # Every internal module and its dotted parents, so a namespace package without __init__.py counts as internal.
        self._may_call_internal_modules = {
            ".".join(parts[:end]) for parts in (name.split(".") for name in self.modules) for end in range(1, len(parts) + 1)
        }

    def _may_call_imported_modules(self, module: _ModuleState) -> set[str]:
        imported = set(module.imported_modules.values())
        for source, name in module.imported_symbols.values():
            imported.update((source, f"{source}.{name}"))
        return imported

    def _is_external_import(self, module: _ModuleState, root: str) -> bool:
        if root in module.imported_modules:
            sources = {module.imported_modules[root]}
        elif root in module.imported_symbols:
            source, name = module.imported_symbols[root]
            sources = {source, f"{source}.{name}"}
        else:
            return False
        return sources.isdisjoint(self._may_call_internal_modules)

    def _may_call_name_candidates(self, call: _CallRecord, module: _ModuleState, has_lexical_binding: bool) -> list[str]:
        name = may_call.callee_name(call.callee_text)
        root = may_call.receiver_root(call.callee_text)
        if name is None or root is None or "." not in call.callee_text or self._is_external_import(module, root):
            return []
        if root in may_call.BUILTIN_RECEIVERS and not has_lexical_binding and root not in module.definitions:
            return []
        candidates = self._may_call_by_name.get(name, [])
        if root == "super":
            own_class = self._may_call_owner_class.get(call.caller_id)
            return [target for target in candidates if self._may_call_owner_class.get(target) != own_class]
        return candidates

    def _add_may_call(self, call: _CallRecord, module: _ModuleState, match_kind: str, targets: Iterable[str]) -> None:
        if not self._emit_may_call:
            return
        candidates: set[str] = set()
        for target_id in targets:
            target = self.nodes_by_id.get(target_id)
            if target is None:
                continue
            if target["type"] == "Class":
                candidates.update(self._may_call_constructors.get(target_id, ()))
            elif target["type"] in {"Function", "Method"}:
                candidates.add(target_id)
        if not candidates:
            return
        if len(candidates) > may_call.MAX_CANDIDATES:
            self._may_call_skipped_over_cap += 1
            return
        if match_kind == "name":
            tool_precision, source = may_call.NAME_TOOL_PRECISION, {"source_tool": may_call.NAME_SOURCE_TOOL}
        elif match_kind == "scip_ambiguous":
            tool_precision, source = may_call.ANALYZER_TOOL_PRECISION, {
                "source_tool": self.resolver_report["tool"], "source_tool_version": self.resolver_report["tool_version"]}
        elif match_kind.startswith("jarvis"):
            tool_precision, source = may_call.ANALYZER_TOOL_PRECISION, {
                "source_tool": "jarvis", "source_tool_version": jarvis_runner.JARVIS_COMMIT}
        else:
            info = self.resolver_report["lsp"]["server_info"]
            tool_precision, source = may_call.ANALYZER_TOOL_PRECISION, {
                "source_tool": info.get("name", "lsp"), "source_tool_version": info.get("version", "unknown")}
        imported_modules = self._may_call_imported_modules(module)
        for target_id in sorted(candidates):
            candidate_module = self._may_call_module_by_path.get(self.nodes_by_id[target_id]["path"])
            same_module = candidate_module == module.module_name
            imported = not same_module and candidate_module in imported_modules
            self._add_edge(
                "MAY_CALL",
                call.node_id,
                target_id,
                confidence=may_call.confidence(tool_precision, import_coherent=same_module or imported),
                resolution="heuristic",
                rule_id=f"python.call.may_call.{match_kind}.v1",
                properties={"match_kind": match_kind, "candidate_count": len(candidates)},
                **source,
            )
            self.edges[-1]["provenance"]["evidence"] = may_call.evidence(match_kind, same_module=same_module, imported=imported)
        self._may_call_by_kind[match_kind] += len(candidates)
        self._may_call_callsites += 1

    def _resolve_calls(self) -> None:
        self._index_may_call_targets()
        test_targets: dict[tuple[str, str], float] = {}
        statuses: dict[str, int] = {}
        self.resolver_report["call_binding_statuses"] = statuses
        for call in self.calls:
            if call.module_name not in self.modules:
                continue
            module = self.modules[call.module_name]
            target_id = None
            scip_status, scip_targets = (self.scip_resolver.resolve(call.path, call.line, call.column)
                                       if self.scip_resolver is not None else ("unavailable", []))
            statuses[scip_status] = statuses.get(scip_status, 0) + 1
            if scip_status == "resolved":
                target_id = scip_targets[0]
            elif scip_status == "local_non_callable" and call.callee_text == "cls" and call.owner_class_name:
                caller = self.nodes_by_id[call.caller_id]
                scope = self._scope_key(caller["qualified_name"], caller["range"]["start_line"])
                if caller["properties"].get("method_kind") == "class" and "cls" in self.unmodified_parameters.get(scope, set()):
                    scip_status = "classmethod_parameter"
            if scip_status in {"ambiguous", "external_or_non_callable", "local_non_callable"}:
                # An authoritative external/ambiguous binding must not become a guessed internal edge.
                self.nodes_by_id[call.node_id]["properties"]["resolution_reason"] = scip_status
                self.trace.emit("call_unresolved", node_id=call.node_id, path=call.path, reason=scip_status,
                                candidate_count=len(scip_targets), resolver="scip")
                if scip_status == "ambiguous":
                    self._add_may_call(call, module, "scip_ambiguous", scip_targets)
                continue
            lsp_status, lsp_targets = self.lsp_results.get(call.node_id, ("not_needed", []))
            if target_id is None and lsp_status == "resolved":
                target_id = lsp_targets[0]
            elif target_id is None and lsp_status in {"ambiguous", "external_or_non_callable"}:
                call_node = self.nodes_by_id[call.node_id]
                call_node["properties"].update(resolution_reason=lsp_status, resolver="lsp", lsp_candidate_count=len(lsp_targets))
                self.trace.emit("call_unresolved", node_id=call.node_id, path=call.path,
                                reason=lsp_status, candidate_count=len(lsp_targets), resolver="lsp")
                if lsp_status == "ambiguous":
                    self._add_may_call(call, module, "lsp_ambiguous", lsp_targets)
                continue
            has_lexical_binding = False
            if target_id is None:
                has_lexical_binding, target_id = self._resolve_lexical_binding(call)
            if target_id is None and not has_lexical_binding:
                target_id = self._resolve_symbol(
                    module,
                    call.callee_text,
                    owner_class_name=call.owner_class_name,
                )
            typed_target = self._resolve_typed_receiver(call) if target_id is None else None
            if typed_target is not None:
                target_id = typed_target
            if call.node_id not in self.nodes_by_id:
                continue
            call_node = self.nodes_by_id[call.node_id]
            if target_id is None:
                if self.lsp_config is not None:
                    call_node["properties"].update(resolver="static", lsp_fallback_reason=lsp_status)
                self.trace.emit("call_unresolved", node_id=call.node_id, path=call.path, reason="static_no_target",
                                resolver="static", scip_status=scip_status, lsp_status=lsp_status)
                self._add_may_call(call, module, "name", self._may_call_name_candidates(call, module, has_lexical_binding))
                continue

            if target_id not in self.nodes_by_id:
                continue
            target = self.nodes_by_id[target_id]
            if target["type"] not in {"Function", "Method", "Class"}:
                continue
            imported_symbol = module.imported_symbols.get(call.callee_text)
            exact_import_target = None
            if imported_symbol is not None:
                imported_module, imported_name = imported_symbol
                exact_import_target = self.symbols_by_qualified_name.get(
                    f"{imported_module}.{imported_name}"
                )
            is_unique_fallback = (
                self.unique_symbols_by_name.get(call.callee_text) == target_id
                and call.callee_text not in module.definitions
                and exact_import_target != target_id
            )

            if scip_status == "resolved":
                binding_kind = "scip"
                confidence = 0.98
            elif lsp_status == "resolved":
                binding_kind = "lsp"
                confidence = 0.95
            elif scip_status == "classmethod_parameter":
                binding_kind = "classmethod_constructor"
                confidence = 0.80
                call_node["properties"]["dispatch_kind"] = "constructor"
            elif typed_target is not None:
                binding_kind = "typed_parameter"
                confidence = 0.85
            elif target["type"] == "Class":
                binding_kind = "constructor"
                confidence = 0.60 if is_unique_fallback else 0.95
                call_node["properties"]["dispatch_kind"] = "constructor"
            elif call.callee_text.startswith(("self.", "cls.")):
                binding_kind = "self_method"
                confidence = 0.8
            elif exact_import_target == target_id:
                binding_kind = "imported_symbol"
                confidence = 0.95
            elif "." in call.callee_text:
                binding_kind = "imported_symbol"
                confidence = 0.9
            elif is_unique_fallback:
                binding_kind = "heuristic"
                confidence = 0.60
            else:
                binding_kind = "same_scope"
                confidence = 0.95

            self._add_edge(
                "CALLS",
                call.node_id,
                target_id,
                confidence=confidence,
                resolution="analyzer",
                rule_id="python.call.scip.resolve.v1" if scip_status == "resolved" else
                        "python.call.lsp.definition.v1" if lsp_status == "resolved" else "python.call.static.resolve.v1",
                properties={
                    "binding_kind": binding_kind,
                    "argument_match": None,
                    "candidate_rank": 1,
                    "confidence_reason": (
                        "SCIP occurrence matched one internal definition" if scip_status == "resolved" else
                        "LSP definition matched one verified internal declaration" if lsp_status == "resolved" else
                        "Explicit parameter annotation matched an internal class method"
                        if typed_target is not None
                        else "Unique deterministic symbol match"
                    ),
                },
            )
            if scip_status == "resolved":
                self.edges[-1]["provenance"].update(source_tool=self.resolver_report["tool"],
                                                    source_tool_version=self.resolver_report["tool_version"])
            if binding_kind == "lsp":
                info = self.resolver_report["lsp"]["server_info"]
                self.edges[-1]["provenance"].update(source_tool=info.get("name", "lsp"),
                                                  source_tool_version=info.get("version", "unknown"))
            active_resolver = binding_kind if binding_kind in {"scip", "lsp"} else "static"
            self.trace.emit("call_resolved", node_id=call.node_id, target_id=target_id, path=call.path,
                            resolver=active_resolver, binding_kind=binding_kind,
                            fallback_reason=scip_status if self.scip_config and scip_status != "resolved" else None,
                            lsp_fallback_reason=lsp_status if self.lsp_config and binding_kind != "lsp" else None,
                            confidence=confidence)
            call_node["properties"]["resolution_status"] = "resolved"
            call_node["properties"]["candidate_count"] = 1
            call_node["properties"]["resolver"] = active_resolver
            if self.lsp_config is not None and active_resolver == "static":
                call_node["properties"]["lsp_fallback_reason"] = lsp_status
            if self.scip_config is not None and scip_status != "resolved":
                call_node["properties"]["fallback_reason"] = scip_status

            if call.caller_type == "Test":
                key = (call.caller_id, target_id)
                test_targets[key] = max(test_targets.get(key, 0.0), confidence)

        # TESTS is one relation per test/target; CALLS keeps every call site.
        for (test_id, target_id), confidence in test_targets.items():
            self._add_edge(
                "TESTS",
                test_id,
                target_id,
                confidence=confidence,
                resolution="analyzer",
                rule_id="python.test.direct_call.v1",
                properties={"link_method": "direct_call", "coverage_count": None},
            )

    def _link_chain_references(self) -> None:
        """Keep source-supported dispatch possibilities separate from CALLS."""
        from vgar.graph.return_contracts import ReturnContracts
        contracts = ReturnContracts(self.repository_root, self.nodes, self.edges, self.modules)
        reasons: dict[str, int] = {}
        hints = 0
        for call in self.calls:
            call_node = self.nodes_by_id[call.node_id]
            if call_node["properties"]["resolution_status"] == "resolved" or "(" not in call.callee_text:
                continue
            status, _ = self.scip_resolver.resolve(call.path, call.line, call.column)
            if status != "no_occurrence":
                continue  # An authoritative external/local/ambiguous result is never overridden.
            try:
                expression = ast.parse(call.callee_text, mode="eval").body
            except (SyntaxError, ValueError):
                continue
            if not isinstance(expression, ast.Attribute) or not isinstance(expression.value, ast.Call):
                continue
            inner = expression.value.func
            span = call_node["range"]
            line = span["start_line"] + inner.end_lineno - 1
            column = inner.end_col_offset + (span["start_col"] if inner.end_lineno == 1 else 0)
            inner_status, getters = self.scip_resolver.resolve(call.path, line, column)
            if inner_status != "resolved" or self.nodes_by_id[getters[0]]["type"] not in {"Function", "Method"}:
                reason, targets, evidence = "inner_getter_not_resolved", [], {}
            else:
                targets, evidence = contracts.candidates(getters[0], expression.attr)
                reason = evidence["reason"] if targets else evidence.get("reason", "no_internal_member")
                if not targets and reason == "source_return_contract":
                    reason = "no_internal_member"
            reasons[reason] = reasons.get(reason, 0) + 1
            if not targets:
                self.trace.emit("chain_reference_skipped", node_id=call.node_id, path=call.path, reason=reason)
                continue
            call_node["properties"].update(reference_candidate_count=len(targets), reference_reason="source_return_contract")
            for target_id in targets:
                self._add_edge("REFERENCES", call.node_id, target_id, confidence=0.65,
                               resolution="heuristic", rule_id="python.call.return_contract.reference.v1",
                               properties={"binding_kind": "return_contract_hint", "runtime_dispatch_verified": False,
                                           "scip_status": status, "evidence": evidence})
                hints += 1
            self.trace.emit("call_reference_hint", node_id=call.node_id, path=call.path, candidate_ids=targets,
                            reason="source_return_contract", evidence=evidence, confidence=0.65,
                            runtime_dispatch_verified=False)
        self.resolver_report.update(chain_reference_count=hints, chain_reference_statuses=reasons)

    def _index_scopes(self, source: bytes, module: _ModuleState) -> None:
        try:
            table = symtable.symtable(source.decode("utf-8"), module.path, "exec")
        except (SyntaxError, UnicodeError):
            # Partial Tree-sitter parses still produce nodes, but no lexical guess.
            return

        def visit(table: symtable.SymbolTable, qualified_name: str, parent: str | None = None) -> None:
            key = self._scope_key(qualified_name, table.get_lineno())
            self._set_index(self.scope_tables, key, table)
            if parent is not None:
                self._set_index(self.scope_parents, key, parent)
            for child in table.get_children():
                if child.get_name() in {"lambda", "listcomp", "setcomp", "dictcomp", "genexpr"}:
                    continue
                visit(child, f"{qualified_name}.{child.get_name()}", key)

        visit(table, module.module_name)
        parsed = ast.parse(source, filename=module.path)

        def annotations(node: ast.AST, qualified_name: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f"{qualified_name}.{child.name}"
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = child.args.posonlyargs + child.args.args + child.args.kwonlyargs
                        # Any store of a parameter invalidates its annotation-based binding.
                        modified = {item.id for item in ast.walk(child) if isinstance(item, ast.Name)
                                    and isinstance(item.ctx, (ast.Store, ast.Del))}
                        types = {}
                        self._set_index(self.unmodified_parameters, self._scope_key(name, child.lineno),
                                        {arg.arg for arg in args if arg.arg not in modified})
                        for arg in args:
                            if arg.annotation is not None and arg.arg not in modified:
                                text = (arg.annotation.value if isinstance(arg.annotation, ast.Constant)
                                        and isinstance(arg.annotation.value, str) else ast.unparse(arg.annotation))
                                if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", text):
                                    types[arg.arg] = text
                        self._set_index(self.typed_parameters, self._scope_key(name, child.lineno), types)
                    annotations(child, name)
                else:
                    annotations(child, qualified_name)

        annotations(parsed, module.module_name)

    def _resolve_lexical_binding(self, call: _CallRecord) -> tuple[bool, str | None]:
        """Prevent module/global guesses from overriding Python local bindings."""
        if (
            call.callee_text == "cls"
            or call.callee_text.startswith(("self.", "cls."))
        ) and call.owner_class_name:
            return False, None
        name = call.callee_text.split(".", 1)[0]
        if not name.isidentifier():
            return False, None
        if call.caller_id not in self.nodes_by_id:
            return False, None
        caller = self.nodes_by_id[call.caller_id]
        scope_name = self._scope_key(caller["qualified_name"], caller["range"]["start_line"])
        while scope_name != self._scope_key(call.module_name, 0):
            table = self.scope_tables.get(scope_name)
            if table is None:
                return True, None
            # A method does not close over its class namespace.
            if table.get_type() == "function" and name in table.get_identifiers():
                symbol = table.lookup(name)
                if symbol.is_global():
                    return False, None
                if symbol.is_local():
                    target = None
                    if call.callee_text == name and symbol.is_namespace():
                        target = self.symbols_by_qualified_name.get(f"{scope_name.split('@scope:', 1)[0]}.{name}")
                    return True, target
            scope_name = self.scope_parents.get(scope_name, self._scope_key(call.module_name, 0))
        return False, None

    def _resolve_typed_receiver(self, call: _CallRecord) -> str | None:
        """Only explicit, unmodified parameter annotations; never execute code."""
        if call.callee_text.count(".") != 1:
            return None
        receiver, method = call.callee_text.split(".")
        caller = self.nodes_by_id.get(call.caller_id)
        if caller is None:
            return None
        scope = self._scope_key(caller["qualified_name"], caller["range"]["start_line"])
        annotation = self.typed_parameters.get(scope, {}).get(receiver)
        if annotation is None:
            return None
        module = self.modules[call.module_name]
        prefix = annotation.split(".", 1)[0]
        if prefix not in module.definitions and prefix not in module.imported_symbols and prefix not in module.imported_modules:
            return None
        class_id = self._resolve_symbol(module, annotation, owner_class_name=None)
        if class_id is None or self.nodes_by_id[class_id]["type"] != "Class":
            return None
        class_name = self.nodes_by_id[class_id]["qualified_name"]
        return self.symbols_by_qualified_name.get(f"{class_name}.{method}")

    @staticmethod
    def _scope_key(qualified_name: str, line: int) -> str:
        return f"{qualified_name}@scope:{line}"

    def _resolve_symbol(
        self,
        module: _ModuleState,
        expression: str,
        *,
        owner_class_name: str | None,
    ) -> str | None:
        if expression == "cls" and owner_class_name:
            return self.symbols_by_qualified_name.get(
                owner_class_name
            )

        if expression.startswith(("self.", "cls.")) and owner_class_name:
            method_name = expression.split(".", 1)[1]
            return self.symbols_by_qualified_name.get(
                f"{owner_class_name}.{method_name}"
            )

        if expression in module.definitions:
            return module.definitions[expression]

        imported_symbol = module.imported_symbols.get(expression)
        if imported_symbol is not None:
            imported_module, imported_name = imported_symbol
            imported_target = self.symbols_by_qualified_name.get(
                f"{imported_module}.{imported_name}"
            )
            if imported_target is not None:
                return imported_target
            if imported_module not in self.modules:
                # B10: an explicit import from outside the repository never
                # falls back to a same-named repository symbol.
                return None

        if "." in expression:
            prefix, name = expression.split(".", 1)
            imported_module = module.imported_modules.get(prefix)
            if imported_module:
                imported_target = self.symbols_by_qualified_name.get(
                    f"{imported_module}.{name}"
                )
                if imported_target is not None:
                    return imported_target
            class_method = self.symbols_by_qualified_name.get(
                f"{module.module_name}.{prefix}.{name}"
            )
            if class_method:
                return class_method

        return self.symbols_by_qualified_name.get(
            f"{module.module_name}.{expression}"
        ) or self.unique_symbols_by_name.get(expression)

    def _build_unique_symbol_index(self) -> None:
        candidates: dict[str, list[str]] = {}
        modules_by_path = {module.path: module for module in self.modules.values()}
        for node in self.nodes:
            if node["type"] not in {"Class", "Function"}:
                continue
            module = modules_by_path.get(node["path"])
            if module is None or node["qualified_name"] != f"{module.module_name}.{node['name']}":
                continue
            candidates.setdefault(node["name"], []).append(node["id"])
        self.unique_symbols_by_name = {
            name: node_ids[0]
            for name, node_ids in candidates.items()
            if len(node_ids) == 1
        }

    @staticmethod
    def _normalize_import_module(
        module: _ModuleState,
        imported_module: str,
        level: int,
    ) -> str:
        if level == 0:
            return imported_module

        package_parts = module.module_name.split(".")
        if not module.is_package and package_parts:
            package_parts.pop()
        ascend = max(level - 1, 0)
        if ascend:
            package_parts = package_parts[:-ascend] if ascend <= len(package_parts) else []

        suffix = imported_module.lstrip(".")
        if suffix:
            package_parts.extend(suffix.split("."))
        return ".".join(part for part in package_parts if part)

    def _external_module(self, module_name: str) -> str:
        safe_name = module_name or "<unknown>"
        node_id = f"vgar:{self.repo_key}:python:module:external:{safe_name}"
        if node_id in self.nodes_by_id:
            return node_id
        self._add_node(
            {
                "id": node_id,
                "type": "Module",
                "repo_key": self.repo_key,
                "name": safe_name.rsplit(".", 1)[-1],
                "qualified_name": safe_name,
                "path": None,
                "language": "python",
                "range": None,
                "properties": {
                    "module_name": safe_name,
                    "is_package": False,
                    "is_external": True,
                    "resolution_status": "external",
                },
                "content_hash": None,
                "graph_version": self.graph_version,
            }
        )
        return node_id

    def _source_node(
        self,
        *,
        node_id: str,
        node_type: str,
        name: str,
        qualified_name: str,
        path: str,
        node: Node,
        source: bytes,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": node_id,
            "type": node_type,
            "repo_key": self.repo_key,
            "name": name,
            "qualified_name": qualified_name,
            "path": path,
            "language": "python",
            "range": self._range(node),
            "properties": properties,
            "content_hash": self._hash_bytes(
                source[node.start_byte : node.end_byte]
            ),
            "graph_version": self.graph_version,
        }

    def _collect_tsg_facts(self, root: Path, python_files: list[Path]) -> dict[str, TsgFileFacts]:
        """Run tree-sitter-graph per file; an unusable CLI leaves the plain graph (status "fallback")."""
        assert self.tsg_config is not None
        reason, version = tsg_extractor.check_available(self.tsg_config)
        self.tsg_report = {"status": "fallback", "reason": reason, "version": version, "file_count": 0,
                           "failed_files": [], "added": {}, "unmatched": {}}
        if reason is not None:
            self.trace.emit("tsg_fallback", reason=reason)
            return {}
        facts: dict[str, TsgFileFacts] = {}
        for file_path in python_files:
            relative_path = file_path.relative_to(root).as_posix()
            try:
                facts[relative_path] = tsg_extractor.run_file(self.tsg_config, root, relative_path)
            except TsgError as error:
                self.tsg_report["failed_files"].append({"path": relative_path, "reason": str(error)})
        self.tsg_report.update(status="partial" if self.tsg_report["failed_files"] else "ready",
                               file_count=len(facts), rules_sha256=self._hash_bytes(self.tsg_config.rules.read_bytes()))
        return facts

    def _merge_tsg_facts(self, root: Path, facts_by_path: dict[str, TsgFileFacts]) -> None:
        """Add HAS_METHOD/HAS_CALLSITE edges and Field/GlobalVariable/Identifier nodes from tree-sitter-graph.

        Class/def/CallSite facts are matched to this builder's nodes by (path, start line, start column,
        name); facts owned by the rules' "Discard" node or by an @overload stub are dropped, and any other
        fact that cannot be matched is counted in statistics.tsg.unmatched instead of being added.
        """
        assert self.tsg_report is not None
        version = self.tsg_report["version"] or "unknown"
        anchors = {(n["path"], n["range"]["start_line"], n["range"]["start_col"], n["name"]): n
                   for n in self.nodes if n["type"] in {"Class", "Function", "Method", "Test", "CallSite"}}
        module_by_path = {state.path: self.nodes_by_id[state.module_id] for state in self.modules.values()
                          if state.module_id in self.nodes_by_id}
        added: Counter[str] = Counter()
        unmatched: Counter[str] = Counter()
        config_reads: list[tuple[str, str, str, str, int]] = []  # (reader id, key, access, path, line)
        tables = self._import_tables()

        for path, facts in facts_by_path.items():
            matched: dict[int, dict[str, Any]] = {}
            unmatched_defs: set[int] = set()
            skipped = {fact_id for fact_id, fact in facts.nodes.items()
                       if fact.get("type") == "Discard" or fact.get("overload")}
            # Calls owned by Discard (module/class level) or by an overload stub are not extracted either.
            skipped |= {target for source, target, label in facts.edges if label == "HAS_CALLSITE" and source in skipped}
            for fact_id, fact in facts.nodes.items():
                if fact_id in skipped:
                    continue
                if fact.get("type") in {"Class", "Function", "Method", "CallSite"}:
                    node = anchors.get((path, fact["line"], fact["col"], fact["name"]))
                    if node is None:
                        unmatched[fact["type"]] += 1
                        skipped.add(fact_id)
                        unmatched_defs.add(fact_id)
                    else:
                        matched[fact_id] = node

            owned: dict[str, list[dict[str, Any]]] = {}
            parameters: dict[int, list[dict[str, Any]]] = {}
            for source_fact, target_fact, label in facts.edges:
                if label == "CONTAINS" and facts.nodes[target_fact].get("type") == "Identifier":
                    if source_fact in unmatched_defs:
                        unmatched["Identifier"] += 1
                    elif source_fact in matched:
                        parameters.setdefault(source_fact, []).append(facts.nodes[target_fact])
                    continue
                if label == "REFERENCES" and facts.nodes[target_fact].get("type") == "ConfigRead":
                    read = facts.nodes[target_fact]
                    module = module_by_path.get(path)
                    table = tables.get(module["id"], {}) if module is not None else {}
                    if not layer1_rules.env_read(read["access"], read["callee"], table):
                        continue  # e.g. a local `environ` dict, or `os` not imported at module level
                    # A read at module level or in a class body hangs off Discard: the Module reads it.
                    reader = module if facts.nodes[source_fact].get("type") == "Discard" else matched.get(source_fact)
                    if source_fact in unmatched_defs or (reader is None and source_fact not in skipped):
                        unmatched["ConfigEntry"] += 1
                    elif reader is not None and not read.get("write"):
                        config_reads.append((reader["id"], read["key"], read["access"], path, read["line"]))
                    continue
                if source_fact in skipped or target_fact in skipped:
                    continue
                source, target = matched.get(source_fact), matched.get(target_fact)
                if label in {"HAS_METHOD", "HAS_CALLSITE"} and source and target:
                    if (source["type"], target["type"]) not in EDGE_ENDPOINTS[label]:
                        unmatched[label] += 1
                        continue
                    self._add_edge(label, source["id"], target["id"], confidence=1.0, resolution="exact",
                                   rule_id=f"python.tsg.{label.lower()}.v1", properties={},
                                   source_tool="tree-sitter-graph", source_tool_version=version)
                    added[label] += 1
                elif label == "CONTAINS" and source and facts.nodes[target_fact].get("type") == "Field":
                    owned.setdefault(source["id"], []).append(facts.nodes[target_fact])
                else:
                    unmatched[label] += 1
            module = module_by_path.get(path)
            if module is not None:
                owned[module["id"]] = [f for f in facts.nodes.values() if f.get("type") == "GlobalVariable"]

            source = (root / path).read_bytes()
            line_starts = [0, *(index + 1 for index, byte in enumerate(source) if byte == 0x0A)]
            for owner_id, occurrences in owned.items():
                by_name: dict[str, list[dict[str, Any]]] = {}
                for fact in occurrences:
                    by_name.setdefault(fact["name"], []).append(fact)
                for name, group in by_name.items():
                    kind = group[0]["type"]
                    node_id = self._add_tsg_symbol(self.nodes_by_id[owner_id], kind, name, group, path, source,
                                                   line_starts)
                    self._add_edge("CONTAINS", owner_id, node_id, confidence=1.0, resolution="exact",
                                   rule_id=f"python.tsg.{kind.lower()}.v1", properties={},
                                   source_tool="tree-sitter-graph", source_tool_version=version)
                    added[kind] += 1
            for def_fact, group in parameters.items():
                owner = matched[def_fact]
                ordered = sorted(group, key=lambda fact: (fact["line"], fact["col"]))
                for position, fact in enumerate(ordered):
                    if (position == 0 and facts.nodes[def_fact]["type"] == "Method"
                            and fact["name"] in {"self", "cls"}):
                        continue
                    node_id = self._add_tsg_symbol(
                        owner, "Identifier", fact["name"], [fact], path, source, line_starts,
                        qualified_name=f"{owner['qualified_name']}::<param:{fact['name']}>",
                        properties={"annotation": fact.get("annotation"), "has_default": "has_default" in fact,
                                    "position": position, "kind": fact["kind"]})
                    self._add_edge("CONTAINS", owner["id"], node_id, confidence=1.0, resolution="exact",
                                   rule_id="python.tsg.identifier.v1", properties={},
                                   source_tool="tree-sitter-graph", source_tool_version=version)
                    added["Identifier"] += 1
        if config_reads:
            added["ConfigEntry"] += self._add_config_entries(config_reads, version)
        self.tsg_report.update(added=dict(sorted(added.items())), unmatched=dict(sorted(unmatched.items())))

    def _add_config_entries(self, reads: list[tuple[str, str, str, str, int]], version: str) -> int:
        """One repo-wide ConfigEntry per environment key; one REFERENCES edge per (reader, key)."""
        by_key: dict[str, list[tuple[str, str, str, str, int]]] = {}
        for read in reads:
            by_key.setdefault(read[1], []).append(read)
        for key in sorted(by_key):
            node_id = f"vgar:{self.repo_key}:config:env:{key}"
            sites = sorted({(path, line) for _, _, _, path, line in by_key[key]})
            self._add_node({
                "id": node_id, "type": "ConfigEntry", "repo_key": self.repo_key, "name": key,
                "qualified_name": f"env:{key}", "path": None, "language": "python", "range": None,
                "properties": {"source": "environment",
                               "read_sites": [{"path": path, "line": line} for path, line in sites]},
                "content_hash": self._hash_text(f"env:{key}"),
                "graph_version": self.graph_version,
            })
            by_reader: dict[str, list[tuple[str, int]]] = {}
            for reader_id, _, access, _, line in by_key[key]:
                by_reader.setdefault(reader_id, []).append((access, line))
            for reader_id in sorted(by_reader):
                self._add_edge("REFERENCES", reader_id, node_id, confidence=1.0, resolution="exact",
                               rule_id="python.tsg.config_env.v1",
                               properties={"access": ",".join(sorted({a for a, _ in by_reader[reader_id]})),
                                           "lines": sorted({line for _, line in by_reader[reader_id]})},
                               source_tool="tree-sitter-graph", source_tool_version=version)
        return len(by_key)

    def _derive_layer1_facts(self) -> None:
        """Route and Schema nodes and IMPLEMENTS edges from the builder's decorators, bases, imports and
        INHERITS edges (spec §4.3-4.5); only runs when tree-sitter-graph ran."""
        assert self.tsg_report is not None
        module_by_path = {state.path: self.nodes_by_id[state.module_id] for state in self.modules.values()
                          if state.module_id in self.nodes_by_id}
        added: Counter[str] = Counter(self.tsg_report["added"])
        for handler in [n for n in self.nodes if n["type"] in {"Function", "Method", "Test"}]:
            decorators = handler["properties"].get("decorators", handler["properties"].get("markers", []))
            for spec in layer1_rules.route_specs(decorators):
                route_id = self._add_layer1_node(
                    module_by_path[handler["path"]], "Route", spec.name,
                    f"{handler['qualified_name']}::<route:{spec.name}>", handler["range"],
                    handler["content_hash"],
                    {"methods": spec.methods, "route_path": spec.route_path, "decorator": spec.decorator,
                     "receiver": spec.receiver})
                self._add_edge("REFERENCES", route_id, handler["id"], confidence=0.8, resolution="heuristic",
                               rule_id="python.layer1.route.v1", properties={})
                added["Route"] += 1

        tables = self._import_tables()
        classes = [n for n in self.nodes if n["type"] == "Class"]
        schema_of: dict[str, tuple[str, str]] = {}
        for node in classes:
            table = tables.get(module_by_path[node["path"]]["id"], {})
            found = layer1_rules.schema_kind(node["properties"]["decorators"], node["properties"]["bases"], table)
            if found:
                schema_of[node["id"]] = found
        # (d) subclasses of pydantic/TypedDict schemas in the repo, to a fixed point.
        inherits = [(e["source_id"], e["target_id"]) for e in self.edges if e["type"] == "INHERITS"]
        changed = True
        while changed:
            changed = False
            for child, parent in inherits:
                if child not in schema_of and parent in schema_of and schema_of[parent][0] != "dataclass":
                    schema_of[child] = (schema_of[parent][0], "inherited")
                    changed = True
        for node in classes:
            if node["id"] not in schema_of:
                continue
            kind, evidence = schema_of[node["id"]]
            schema_id = self._add_layer1_node(
                module_by_path[node["path"]], "Schema", node["name"], f"{node['qualified_name']}::<schema>",
                node["range"], node["content_hash"], {"schema_kind": kind, "evidence": evidence})
            inherited = evidence == "inherited"
            self._add_edge("REFERENCES", schema_id, node["id"], confidence=0.9 if inherited else 1.0,
                           resolution="analyzer" if inherited else "exact", rule_id="python.layer1.schema.v1",
                           properties={})
            added["Schema"] += 1

        def interface(class_id: str) -> str | None:
            node = self.nodes_by_id[class_id]
            return layer1_rules.interface_kind(node["properties"]["bases"],
                                               tables.get(module_by_path[node["path"]]["id"], {}))

        for edge in [e for e in self.edges if e["type"] == "INHERITS"]:
            # An interface extending an interface is an extension, not an implementation.
            kind = interface(edge["target_id"])
            if kind is not None and interface(edge["source_id"]) is None:
                self._add_edge("IMPLEMENTS", edge["source_id"], edge["target_id"], confidence=edge["confidence"],
                               resolution=edge["resolution"], rule_id="python.layer1.implements.v1",
                               properties={"interface_kind": kind})
                added["IMPLEMENTS"] += 1
        self.tsg_report["added"] = dict(sorted(added.items()))

    def _run_joern(self, root: Path, python_files: list[Path]) -> JoernResult:
        """Run Joern on the non-test files; a run that cannot finish leaves the graph without G_code."""
        assert self.joern_config is not None
        files = [path for path in python_files if not self._is_test_path(path.relative_to(root).as_posix())]
        result = joern_runner.run_joern(root, files, self.joern_config)
        self.code_graph_report = {"status": result.status, "reason": result.reason, "image": self.joern_config.image, "statements": 0,
                                  "identifiers": 0, "edges": {}, "raises_fixed": 0, "cannot_reach_exit": 0, "methods_matched": 0,
                                  "methods_unmatched": 0}
        if result.status != "ready":
            self.trace.emit("code_graph_fallback", status=result.status, reason=result.reason)
        return result

    def _run_jarvis(self, root: Path, python_files: list[Path]) -> JarvisResult:
        """Run JARVIS on the non-test files; a run that cannot finish leaves the calls to SCIP or the static resolver."""
        assert self.jarvis_config is not None
        files = [path for path in python_files if not self._is_test_path(path.relative_to(root).as_posix())]
        result = jarvis_runner.run_jarvis(root, files, self.source_roots, self.jarvis_config)
        self.jarvis_report = {"status": result.status, "reason": result.reason, "image": self.jarvis_config.image,
                              "skipped_files": list(result.skipped_files), "edges_total": 0, "external": 0, "ambiguous_names": 0,
                              "no_call_site": 0, "confirmed": 0, "upgraded": 0, "new_calls": 0, "new_may_call": 0, "conflicts": 0,
                              "overflow_unresolved_calls": 0}
        if result.status != "ready":
            self.trace.emit("jarvis_fallback", status=result.status, reason=result.reason)
        return result

    def _jarvis_target(self, node: dict[str, Any]) -> Target:
        if node["type"] == "Class" or "*" in node["properties"]["signature"]:
            return Target(node["id"], node["name"], None)
        parameters = node["properties"]["parameters"]
        bound = node["type"] == "Method" and parameters[:1] in (["self"], ["cls"])
        return Target(node["id"], node["name"], len(parameters) - bound)

    def _jarvis_canonical(self, target_id: str) -> str:
        """A constructor counts as its class, the way JARVIS's two names for it are merged."""
        target = self.nodes_by_id[target_id]
        return self._may_call_owner_class.get(target_id, target_id) if target["name"] in {"__init__", "__new__"} else target_id

    def _apply_jarvis(self, root: Path, result: JarvisResult) -> None:
        """Merge JARVIS's function-level call graph into the call sites, by the rules of jarvis_merge."""
        assert self.jarvis_report is not None
        report = self.jarvis_report
        report["edges_total"] = sum(map(len, result.graph.values()))
        names: dict[str, list[Target]] = defaultdict(list)
        for node in self.nodes:
            if node["type"] in {"Function", "Method", "Class"} and not self._is_test_path(node["path"]):
                module = jarvis_runner.module_name_of(jarvis_runner.staged_path(node["path"], root, self.source_roots))
                names[module + node["qualified_name"][len(self._module_name(node["path"])):]].append(self._jarvis_target(node))
        calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
        candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in self.edges:
            if edge["type"] == "CALLS":
                calls[edge["source_id"]].append(edge)
            elif edge["type"] == "MAY_CALL":
                candidates[edge["source_id"]].append(edge)
        records = defaultdict(list)
        for call in self.calls:
            if call.caller_type != "Test" and call.node_id in self.nodes_by_id:
                records[call.caller_id].append(call)
        removed: set[str] = set()
        for caller_name in sorted(result.graph):
            owners = names.get(caller_name, ())
            if len(owners) != 1 or self.nodes_by_id[owners[0].id]["type"] == "Class":
                continue
            targets, external_names, counts = jarvis_merge.resolve_callees(result.graph[caller_name], names)
            sites = [Site(call.node_id, call.callee_text, self.nodes_by_id[call.node_id]["properties"]["argument_count"],
                          frozenset(self._jarvis_canonical(edge["target_id"]) for edge in calls[call.node_id]),
                          frozenset(self._jarvis_canonical(edge["target_id"]) for edge in candidates[call.node_id]),
                          self.nodes_by_id[call.node_id]["properties"].get("resolution_reason") == "external_or_non_callable",
                          "." not in call.callee_text and self._resolve_lexical_binding(call)[0])
                     for call in records[owners[0].id]]
            outcome = jarvis_merge.merge_caller(sites, targets, external_names)
            counts.update(outcome.counts)
            for key, value in counts.items():
                report[key] += value
            for site_id, target_id in outcome.confirmed:
                for edge in calls[site_id]:
                    if self._jarvis_canonical(edge["target_id"]) == target_id:
                        edge["confidence"] = jarvis_merge.accumulate(edge["confidence"])
                        edge["provenance"]["evidence"] = [*edge["provenance"]["evidence"], "jarvis"]
                        report["confirmed"] += 1
            for site_id, target_id in outcome.supported:
                for edge in candidates[site_id]:
                    if self._jarvis_canonical(edge["target_id"]) == target_id:
                        edge["provenance"]["evidence"] = [*edge["provenance"]["evidence"], "jarvis"]
            for site_id, target_id in outcome.upgraded:
                removed.update(edge["id"] for edge in candidates[site_id])
                self._add_jarvis_call(site_id, target_id)
                report["upgraded"] += 1
            for site_id, target_id in outcome.new_calls:
                self._add_jarvis_call(site_id, target_id)
                report["new_calls"] += 1
            self._add_jarvis_may_calls(outcome.may_call, {call.node_id: call for call in records[owners[0].id]})
        self.edges = [edge for edge in self.edges if edge["id"] not in removed]
        may_call_edges = [edge for edge in self.edges if edge["type"] == "MAY_CALL"]
        per_site = Counter(edge["source_id"] for edge in may_call_edges)
        for edge in may_call_edges:
            edge["properties"]["candidate_count"] = per_site[edge["source_id"]]
        self._may_call_by_kind = Counter(edge["properties"]["match_kind"] for edge in may_call_edges)
        self._may_call_callsites = len(per_site)

    def _add_jarvis_call(self, site_id: str, target_id: str) -> None:
        self._add_edge("CALLS", site_id, target_id, confidence=jarvis_merge.CALL_CONFIDENCE, resolution="analyzer",
                       rule_id="python.call.jarvis.resolve.v1", evidence=("jarvis",), source_tool="jarvis",
                       source_tool_version=jarvis_runner.JARVIS_COMMIT,
                       properties={"binding_kind": "jarvis", "argument_match": None, "candidate_rank": 1,
                                   "confidence_reason": "JARVIS reported one target for this call site"})
        properties = self.nodes_by_id[site_id]["properties"]
        properties.update(resolution_status="resolved", candidate_count=1, resolver="jarvis")
        if self.nodes_by_id[target_id]["type"] == "Class":
            properties["dispatch_kind"] = "constructor"

    def _add_jarvis_may_calls(self, wanted: tuple[tuple[str, str, str], ...], records: dict[str, _CallRecord]) -> None:
        assert self.jarvis_report is not None
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for site_id, target_id, match_kind in wanted:
            grouped[site_id, match_kind].append(target_id)
        for (site_id, match_kind), targets in grouped.items():
            call, start = records[site_id], len(self.edges)
            self._add_may_call(call, self.modules[call.module_name], match_kind, targets)
            added = self.edges[start:]
            self.jarvis_report["new_may_call"] += len(added)
            if not added:  # a class with no constructor of its own has nothing MAY_CALL can point at
                self.jarvis_report["no_call_site"] += len(targets)
            if match_kind == "jarvis_conflict":
                for edge in added:
                    edge["confidence"] = jarvis_merge.CONFLICT_CONFIDENCE
                    edge["provenance"]["evidence"] = [*edge["provenance"]["evidence"], "conflict_with_call"]

    def _add_code_graph(self, root: Path, result: JoernResult) -> None:
        """Add G_code: statements and names from tree-sitter, flow from Joern. A function Joern did not see gets none of it."""
        assert self.code_graph_report is not None
        owners = {(node["path"], node["range"]["start_line"], node["name"]): node for node in self.nodes
                  if node["type"] in {"Function", "Method"} and not self._is_test_path(node["path"])}
        methods: dict[tuple[str, int, str], JoernMethod | None] = {}
        for method in result.methods:
            key = (method.path, method.line, method.name)
            methods[key] = None if key in methods else method  # two methods on one key cannot be told apart
        callsites: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge["type"] == "CONTAINS" and self.nodes_by_id[edge["target_id"]]["type"] == "CallSite":
                callsites[edge["source_id"]].append(edge["target_id"])
        matched = 0
        for path in sorted({key[0] for key in owners}):
            source = (root / path).read_bytes()
            stack = [self.parser.parse(source).root_node]
            while stack:
                node = stack.pop()
                stack.extend(reversed(node.named_children))
                name = node.child_by_field_name("name") if node.type == "function_definition" else None
                if name is None:
                    continue
                key = (path, node.start_point.row + 1, source[name.start_byte:name.end_byte].decode("utf-8", "replace"))
                method = methods.get(key)
                if key in owners and method is not None:
                    matched += 1
                    self._add_function_code_graph(owners[key], node, source, method, callsites[owners[key]["id"]])
        self.code_graph_report.update(
            statements=sum(node["type"] == "Statement" for node in self.nodes),
            identifiers=sum(node["type"] == "Identifier" and node["properties"].get("extractor") == "code-graph" for node in self.nodes),
            edges=dict(sorted(Counter(edge["type"] for edge in self.edges if edge["type"] in G_CODE_EDGE_TYPES).items())),
            methods_matched=matched, methods_unmatched=len(owners) - matched)

    def _add_function_code_graph(self, owner: dict[str, Any], function: Node, source: bytes, method: JoernMethod, callsites: list[str]) -> None:
        assert self.code_graph_report is not None and self.joern_config is not None
        statements = code_graph.function_statements(function, source)
        identifiers = code_graph.function_identifiers(function, source, statements)
        flow = code_graph.project_method(method, statements)
        self.code_graph_report["raises_fixed"] += flow.raises_fixed
        self.code_graph_report["cannot_reach_exit"] += flow.cannot_reach_exit
        owner_id, owner_name, path = owner["id"], owner["qualified_name"], owner["path"]
        statement_ids = [f"{owner_id}::{fact.kind}#{fact.n}" for fact in statements]
        children: dict[str, list[str]] = defaultdict(list)
        for fact, statement_id in zip(statements, statement_ids):
            properties = {"kind": fact.kind, "owner_id": owner_id}
            if fact.condition is not None:
                properties["condition"] = fact.condition
            if fact.value is not None:
                properties["value"] = fact.value
            self._add_node(self._source_node(node_id=statement_id, node_type="Statement", name=fact.kind,
                                             qualified_name=f"{owner_name}::{fact.kind}#{fact.n}", path=path, node=fact.node,
                                             source=source, properties=properties))
            children[owner_id if fact.parent is None else statement_ids[fact.parent]].append(statement_id)
        for fact in identifiers:
            identifier_id = f"{owner_id}::identifier:{fact.name}#{fact.n}"
            properties = {"extractor": "code-graph"}
            if fact.type is not None:
                properties["type"] = fact.type
            self._add_node(self._source_node(node_id=identifier_id, node_type="Identifier", name=fact.name,
                                             qualified_name=f"{owner_name}::identifier:{fact.name}#{fact.n}", path=path, node=fact.node,
                                             source=source, properties=properties))
            self._add_edge("CONTAINS", owner_id, identifier_id, confidence=1.0, resolution="exact", rule_id="python.code.contains.v1",
                           properties={"extractor": "code-graph"})
            children[statement_ids[fact.statement]].append(identifier_id)
        for callsite_id in callsites:
            span = self.nodes_by_id[callsite_id]["range"]
            statement = code_graph.statement_covering(statements, span["start_byte"], span["end_byte"])
            if statement is not None:
                children[statement_ids[statement]].append(callsite_id)
        def position(child_id: str) -> tuple[int, int, str]:
            span = self.nodes_by_id[child_id]["range"]
            return span["start_byte"], -span["end_byte"], child_id  # the outer of two nodes starting together comes first

        for parent_id, child_ids in children.items():
            for ordinal, child_id in enumerate(sorted(child_ids, key=position)):
                self._add_edge("AST_CHILD", parent_id, child_id, confidence=1.0, resolution="exact", rule_id="python.code.ast_child.v1",
                               properties={"ordinal": ordinal})
        joern = {"resolution": "heuristic", "source_tool": "joern-pysrc2cpg", "source_tool_version": self.joern_config.image}
        for source_index, target_index in sorted(flow.cfg):
            self._add_edge("CFG_NEXT", statement_ids[source_index], statement_ids[target_index], confidence=0.9,
                           rule_id="python.code.cfg_next.v1", properties={}, **joern)
        for dependent, controlling in sorted(flow.control):
            self._add_edge("CONTROL_DEPENDS_ON", statement_ids[dependent], statement_ids[controlling], confidence=0.9,
                           rule_id="python.code.control_depends_on.v1", properties={}, **joern)
        for (use, definition), names in sorted(flow.data.items(), key=lambda item: (item[0][0], -1 if item[0][1] is None else item[0][1])):
            self._add_edge("DATA_DEPENDS_ON", statement_ids[use], owner_id if definition is None else statement_ids[definition], confidence=0.8,
                           rule_id="python.code.data_depends_on.v1", properties={"variables": list(names)}, **joern)

    def _lift_architecture(self) -> None:
        """Add the G_arch layer; runs after every CALLS edge exists (spec §4)."""
        result = arch_lift.lift(self.repo_key, self.nodes, self.edges, is_test=self._is_test_path,
                                exports=self._collect_exports(), deployment=self._deployment_files)
        for node in result.nodes:
            node.setdefault("content_hash", self._hash_text(node["id"]))
            self._add_node({**node, "graph_version": self.graph_version})
        for edge in result.edges:
            self._add_edge(edge.type, edge.source_id, edge.target_id, confidence=edge.confidence,
                           resolution=edge.resolution, rule_id=f"python.arch.{edge.rule}.v1", properties=edge.properties,
                           source_tool=arch_lift.SOURCE_TOOL, evidence=edge.evidence)
        self.arch_report = result.report

    def _collect_exports(self) -> dict[str, frozenset[str]]:
        """Path -> names in ``__all__``; parses only the files that mention it."""
        assert self.repository_root is not None
        exports: dict[str, frozenset[str]] = {}
        for state in self.modules.values():
            source = (self.repository_root / state.path).read_bytes()
            if b"__all__" in source:
                exports[state.path] = arch_lift.read_dunder_all(source)
        return exports

    def _import_tables(self) -> dict[str, dict[str, str]]:
        """Module id -> local name -> dotted origin, from the module-level Import nodes."""
        imports: dict[str, list[dict[str, Any]]] = {}
        for edge in self.edges:
            if edge["type"] == "CONTAINS" and self.nodes_by_id[edge["target_id"]]["type"] == "Import":
                imports.setdefault(edge["source_id"], []).append(self.nodes_by_id[edge["target_id"]]["properties"])
        return {module_id: layer1_rules.import_table(items) for module_id, items in imports.items()}

    def _add_layer1_node(self, owner: dict[str, Any], kind: str, name: str, qualified_name: str,
                         range_: dict[str, int], content_hash: str, properties: dict[str, Any]) -> str:
        """Add a derived source-backed node under ``owner`` (CONTAINS edge included) and return its id."""
        node_id = f"vgar:{self.repo_key}:python:{kind.lower()}:{owner['path']}:{qualified_name}"
        if node_id in self.nodes_by_id:
            node_id += f"@definition:{range_['start_line']}:{range_['start_col']}"
        self._add_node({
            "id": node_id, "type": kind, "repo_key": self.repo_key, "name": name,
            "qualified_name": qualified_name, "path": owner["path"], "language": "python",
            "range": dict(range_), "properties": properties, "content_hash": content_hash,
            "graph_version": self.graph_version,
        })
        self._add_edge("CONTAINS", owner["id"], node_id, confidence=1.0, resolution="exact",
                       rule_id=f"python.layer1.{kind.lower()}.v1", properties={})
        return node_id

    def _add_tsg_symbol(self, owner: dict[str, Any], kind: str, name: str, group: list[dict[str, Any]], path: str,
                        source: bytes, line_starts: list[int], qualified_name: str | None = None,
                        properties: dict[str, Any] | None = None) -> str:
        """One Field/GlobalVariable node per (owner, name), ranged at its first assignment.

        Identifier passes its own ``qualified_name`` and ``properties`` (one fact per node).
        """
        first = min(group, key=lambda fact: (fact["line"], fact["col"]))
        start = line_starts[first["line"] - 1] + first["col"]
        end = line_starts[first["end_line"] - 1] + first["end_col"]
        qualified_name = qualified_name or f"{owner['qualified_name']}.{name}"
        node_id = f"vgar:{self.repo_key}:python:{kind.lower()}:{path}:{qualified_name}"
        if node_id in self.nodes_by_id:
            node_id += f"@definition:{first['line']}:{first['col']}"
        self._add_node({
            "id": node_id, "type": kind, "repo_key": self.repo_key, "name": name,
            "qualified_name": qualified_name, "path": path, "language": "python",
            "range": {"start_line": first["line"], "start_col": first["col"], "end_line": first["end_line"],
                      "end_col": first["end_col"], "start_byte": start, "end_byte": end},
            "properties": properties if properties is not None else {
                "assignment_lines": sorted({fact["line"] for fact in group}), "extractor": "tree-sitter-graph"},
            "content_hash": self._hash_bytes(source[start:end]),
            "graph_version": self.graph_version,
        })
        return node_id

    def _add_node(self, node: dict[str, Any]) -> None:
        node_id = node["id"]
        if node_id in self.nodes_by_id:
            raise ValueError(f"duplicate node id while building graph: {node_id}")
        self.nodes.append(node)
        self.nodes_by_id[node_id] = node

    def _add_edge(
        self,
        edge_type: str,
        source_id: str,
        target_id: str,
        *,
        confidence: float,
        resolution: str,
        rule_id: str,
        properties: dict[str, Any],
        source_tool: str = "vgar-python-graph-builder",
        source_tool_version: str = "0.1.0",
        evidence: Iterable[str] = (),
    ) -> None:
        identity = self._hash_text(
            f"{edge_type}\0{source_id}\0{target_id}\0{rule_id}"
        )
        self.edges.append(
            {
                "id": identity,
                "type": edge_type,
                "source_id": source_id,
                "target_id": target_id,
                "confidence": confidence,
                "resolution": resolution,
                "provenance": {
                    "source_tool": source_tool,
                    "source_tool_version": source_tool_version,
                    "rule_id": rule_id,
                    "source_revision": self.repository_revision,
                    "evidence": list(evidence),
                },
                "properties": properties,
                "graph_version": self.graph_version,
            }
        )

    def _module_name(self, relative_path: str) -> str:
        parts = list(Path(relative_path).with_suffix("").parts)
        if parts and parts[0] in self.source_roots:
            parts.pop(0)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts) or Path(relative_path).parent.name

    @staticmethod
    def _text(node: Node, source: bytes) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8")

    @staticmethod
    def _range(node: Node) -> dict[str, int]:
        return {
            "start_line": node.start_point.row + 1,
            "start_col": node.start_point.column,
            "end_line": node.end_point.row + 1,
            "end_col": node.end_point.column,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        }

    def _signature(self, node: Node, source: bytes) -> str:
        body = node.child_by_field_name("body")
        end = body.start_byte if body is not None else node.end_byte
        header = source[node.start_byte:end].decode("utf-8").strip()
        return header.removesuffix(":").strip()

    def _parameter_names(
        self,
        parameters_node: Node | None,
        source: bytes,
    ) -> list[str]:
        if parameters_node is None:
            return []
        names: list[str] = []
        for child in parameters_node.named_children:
            identifier = self._first_identifier(child)
            if identifier is not None:
                names.append(self._text(identifier, source))
        return names

    def _first_identifier(self, node: Node) -> Node | None:
        if node.type == "identifier":
            return node
        for child in node.named_children:
            found = self._first_identifier(child)
            if found is not None:
                return found
        return None

    @staticmethod
    def _visibility(name: str) -> str:
        if name.startswith("__") and not name.endswith("__"):
            return "private"
        if name.startswith("_"):
            return "protected"
        return "public"

    @staticmethod
    def _method_kind(decorators: list[str]) -> str:
        normalized = {item.lstrip("@").split("(", 1)[0] for item in decorators}
        if "classmethod" in normalized:
            return "class"
        if "staticmethod" in normalized:
            return "static"
        if "property" in normalized:
            return "property"
        return "instance"

    @staticmethod
    def _is_test_path(path: str) -> bool:
        name = Path(path).name
        return name.startswith("test_") or "/tests/" in f"/{path}"

    @staticmethod
    def _hash_bytes(value: bytes) -> str:
        return f"sha256:{hashlib.sha256(value).hexdigest()}"

    @classmethod
    def _hash_text(cls, value: str) -> str:
        return cls._hash_bytes(value.encode("utf-8"))

    @classmethod
    def _short_hash(cls, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    def _statistics(self, started_at: float) -> dict[str, Any]:
        node_counts: dict[str, int] = {}
        edge_counts: dict[str, int] = {}
        for node in self.nodes:
            node_counts[node["type"]] = node_counts.get(node["type"], 0) + 1
        for edge in self.edges:
            edge_counts[edge["type"]] = edge_counts.get(edge["type"], 0) + 1

        callsites = [node for node in self.nodes if node["type"] == "CallSite"]
        unresolved_calls = sum(
            1
            for node in callsites
            if node["properties"]["resolution_status"] != "resolved"
        )
        partial_files = sum(
            1
            for node in self.nodes
            if node["type"] == "File"
            and node["properties"]["parse_status"] == "partial"
        )
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_counts_by_type": node_counts,
            "edge_counts_by_type": edge_counts,
            "callsite_count": len(callsites),
            "unresolved_call_count": unresolved_calls,
            "unresolved_call_rate": (
                unresolved_calls / len(callsites) if callsites else 0.0
            ),
            "partial_file_count": partial_files,
            "skipped_overload_count": self.skipped_overload_count,
            "renamed_duplicate_count": self.renamed_duplicate_count,
            "failed_file_count": len(self.skipped_failed_files),
            "failed_files": self.skipped_failed_files,
            "schema_profile": PROFILE_FULL_VGAR_MCP,
            "legacy_graph_version": self.legacy_graph_version,
            "may_call": {
                "rule_version": may_call.RULE_VERSION,
                "edge_count": sum(self._may_call_by_kind.values()),
                "callsite_count": self._may_call_callsites,
                "skipped_over_cap": self._may_call_skipped_over_cap,
                "by_match_kind": dict(sorted(self._may_call_by_kind.items())),
            },
            "build_time_ms": round((time.perf_counter() - started_at) * 1000, 3),
        }
