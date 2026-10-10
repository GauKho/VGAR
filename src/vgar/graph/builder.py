from __future__ import annotations

import ast
import hashlib
import os
import re
import symtable
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from vgar.contracts.schema import validate_graph_document


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

    def __init__(
        self,
        *,
        repo_key: str,
        repository_revision: str,
        source_roots: tuple[str, ...] = ("src",),
    ) -> None:
        if not repo_key.strip():
            raise ValueError("repo_key must not be empty")
        if not repository_revision.strip():
            raise ValueError("repository_revision must not be empty")

        self.repo_key = repo_key.strip()
        self.repository_revision = repository_revision.strip()
        self.source_roots = source_roots
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
        self._index_changes: list[tuple[dict, str, Any]] | None = None
        self.graph_version = ""
        self.skipped_overload_count: int = 0
        self.renamed_duplicate_count: int = 0
        self.skipped_failed_files: list[dict[str, str]] = []

    def build(self, repository_root: str | Path) -> dict[str, Any]:
        started_at = time.perf_counter()
        root = Path(repository_root).resolve()
        if not root.is_dir():
            raise ValueError(f"repository root does not exist: {root}")
        self.repository_root = root
        if self.nodes:
            raise ValueError("Use a new PythonGraphBuilder for each graph snapshot")

        python_files = self._discover_python_files(root)
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

        self._build_unique_symbol_index()
        self._link_imports()
        self._link_inheritance()
        self._resolve_calls()

        document = {
            "graph_version": self.graph_version,
            "repo_key": self.repo_key,
            "repository_revision": self.repository_revision,
            "nodes": self.nodes,
            "edges": self.edges,
            "statistics": self._statistics(started_at),
        }
        validate_graph_document(document)
        return document

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
        digest.update(b"tree-sitter+python-static-v2")
        digest.update(b"\0file-range:full-bytes-v1")
        digest.update(b"\0source-roots:")
        digest.update(repr(self.source_roots).encode("utf-8"))
        for path in files:
            digest.update(b"\0")
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
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
        relative_path = file_path.relative_to(root).as_posix()
        source = file_path.read_bytes()
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
                "name": file_path.name,
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
                    "is_package": file_path.name == "__init__.py",
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
            is_package=file_path.name == "__init__.py",
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

    def _resolve_calls(self) -> None:
        test_targets: dict[tuple[str, str], float] = {}
        for call in self.calls:
            if call.module_name not in self.modules:
                continue
            module = self.modules[call.module_name]
            has_lexical_binding, target_id = self._resolve_lexical_binding(call)
            if not has_lexical_binding:
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

            if typed_target is not None:
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
                rule_id="python.call.static.resolve.v1",
                properties={
                    "binding_kind": binding_kind,
                    "argument_match": None,
                    "candidate_rank": 1,
                    "confidence_reason": (
                        "Explicit parameter annotation matched an internal class method"
                        if typed_target is not None
                        else "Unique deterministic symbol match"
                    ),
                },
            )
            call_node["properties"]["resolution_status"] = "resolved"
            call_node["properties"]["candidate_count"] = 1

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
                    "source_tool": "vgar-python-graph-builder",
                    "source_tool_version": "0.1.0",
                    "rule_id": rule_id,
                    "source_revision": self.repository_revision,
                    "evidence": [],
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
            "build_time_ms": round((time.perf_counter() - started_at) * 1000, 3),
        }
