from __future__ import annotations

import ast
import hashlib
import json
import symtable
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from vgar.graph.jedi_resolver import JediResolution, JediSymbolResolver
from vgar.contracts.schema import validate_graph_document
from vgar.source_scope import IGNORED_DIRECTORY_NAMES, SourceScope


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
    ambiguous_names: set[str] = field(default_factory=set)


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
    binding: _ModuleState


class PythonGraphBuilder:
    """Build documents that follow the frozen VGAR graph contract."""

    def __init__(
        self,
        *,
        repo_key: str,
        repository_revision: str,
        source_roots: tuple[str, ...] = ("src",),
        use_jedi: bool = True,
        source_scope: SourceScope | None = None,
    ) -> None:
        if not repo_key.strip():
            raise ValueError("repo_key must not be empty")
        if not repository_revision.strip():
            raise ValueError("repository_revision must not be empty")

        self.repo_key = repo_key.strip()
        self.repository_revision = repository_revision.strip()
        self.source_roots = source_roots
        self.use_jedi = use_jedi
        self.source_scope = source_scope
        self.parser = Parser(Language(tree_sitter_python.language()))
        self.repository_root: Path | None = None
        self.jedi_resolver: JediSymbolResolver | None = None

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
        self.scope_locations: dict[tuple[str, int], symtable.SymbolTable] = {}
        self.scope_nodes: dict[str, symtable.SymbolTable | None] = {}
        self.scope_parent_ids: dict[str, str] = {}
        self.source_inventory: dict[str, str] = {}
        self.unresolved_bases: list[dict[str, str]] = []
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
        self.source_scope = self.source_scope or SourceScope.for_repository(root)
        self.jedi_resolver = JediSymbolResolver(
            root,
            source_roots=self.source_roots,
            enabled=self.use_jedi,
        )

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
        return self.source_scope.python_files(root)

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
        digest.update(b"jedi" if self.use_jedi else b"tree-sitter-only")
        digest.update(b"\0resolver-profile:transaction-bindings-v3")
        digest.update(json.dumps(self.source_scope.metadata(), sort_keys=True).encode("utf-8"))
        for path in files:
            digest.update(b"\0")
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            source = path.read_bytes()
            digest.update(source)
            self.source_inventory[path.relative_to(root).as_posix()] = self._hash_bytes(source)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _is_setter_decorator(decorators: list[str]) -> bool:
        """Check whether any decorator is a property-setter pattern like @x.setter."""
        for dec in decorators:
            stripped = dec.lstrip("@").strip()
            try:
                expression = ast.parse(stripped, mode="eval").body
            except SyntaxError:
                continue
            if isinstance(expression, ast.Attribute) and expression.attr == "setter":
                return True
        return False

    @staticmethod
    def _is_overload_decorator(decorators: list[str]) -> bool:
        """Return True when any decorator resolves to the typing.overload builtin."""
        for dec in decorators:
            name = dec.lstrip("@").strip().rsplit(".", 1)[-1].split("(", 1)[0]
            if name == "overload":
                return True
        return False

    def _extract_file(
        self,
        root: Path,
        file_path: Path,
        repository_id: str,
    ) -> None:
        """Isolate the entire extraction, including scope indexing, as one transaction."""
        relative_path = file_path.relative_to(root).as_posix()
        module_name = self._module_name(relative_path)
        previous_module = self.modules.get(module_name)
        lengths = tuple(len(items) for items in (self.nodes, self.edges, self.calls, self.classes))
        counters = (self.skipped_overload_count, self.renamed_duplicate_count)
        scoped = lambda name: name == module_name or name.startswith(module_name + ".")
        # Only this module's overwritten entries need a journal; no whole-graph deepcopy.
        symbols = {k: v for k, v in self.symbols_by_qualified_name.items() if scoped(k)}
        tables = {k: v for k, v in self.scope_tables.items() if scoped(k)}
        parents = {k: v for k, v in self.scope_parents.items() if scoped(k)}
        locations = {k: v for k, v in self.scope_locations.items() if scoped(k[0])}
        try:
            self._extract_file_contents(root, file_path, repository_id)
        except Exception as exc:  # noqa: BLE001 - isolate file errors, never suppress process interrupts
            removed = {n["id"] for n in self.nodes[lengths[0]:]}
            for items, length in zip((self.nodes, self.edges, self.calls, self.classes), lengths):
                del items[length:]
            for node_id in removed:
                self.nodes_by_id.pop(node_id, None)
                self.scope_nodes.pop(node_id, None)
                self.scope_parent_ids.pop(node_id, None)
            for mapping, old in ((self.symbols_by_qualified_name, symbols),
                                 (self.scope_tables, tables), (self.scope_parents, parents)):
                for key in list(mapping):
                    if scoped(key):
                        del mapping[key]
                mapping.update(old)
            for key in list(self.scope_locations):
                if scoped(key[0]):
                    del self.scope_locations[key]
            self.scope_locations.update(locations)
            self.modules.pop(module_name, None)
            if previous_module is not None:
                self.modules[module_name] = previous_module
            self.skipped_overload_count, self.renamed_duplicate_count = counters
            self.skipped_failed_files.append({"path": relative_path, "error_type": type(exc).__name__, "error": str(exc)})

    def _extract_file_contents(
        self,
        root: Path,
        file_path: Path,
        repository_id: str,
    ) -> None:
        relative_path = file_path.relative_to(root).as_posix()
        source = file_path.read_bytes()
        tree = self.parser.parse(source)
        root_node = tree.root_node

        file_id = f"vgar:{self.repo_key}:python:file:{relative_path}"
        file_range = self._range(root_node)
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
        self.modules[module_name] = module
        self._index_scopes(source, module)
        self.scope_nodes[module_id] = self.scope_tables.get(module_name)
        self._walk_scope(
            root_node, source, module, parent_id=module_id, parent_type="Module",
            parent_qualified_name=module_name, owner_class_name=None,
        )

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
        if scope_node.type in {"except_clause", "elif_clause", "else_clause", "finally_clause", "case_clause"}:
            body = next((child for child in scope_node.named_children if child.type == "block"), body)
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
                    owner_class_name=class_name,
                )
                ordinal += 1
                continue

            # Compound statements do not introduce a Python lexical scope. Traverse
            # their blocks/clauses, but never descend into a definition twice.
            if definition.type in {"if_statement", "for_statement", "while_statement",
                                   "try_statement", "with_statement", "match_statement",
                                   "elif_clause", "else_clause", "except_clause",
                                   "finally_clause", "case_clause", "block"}:
                for branch in definition.named_children:
                    if branch.type in {"block", "elif_clause", "else_clause", "except_clause",
                                       "finally_clause", "case_clause"}:
                        self._walk_scope(branch, source, module, parent_id=parent_id,
                                         parent_type=parent_type, parent_qualified_name=parent_qualified_name,
                                         owner_class_name=owner_class_name)
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
        node_id = self._definition_id("class", module.path, qualified_name, node)
        # Python evaluates bases before binding the new class name. Preserve local
        # definition IDs and imports from that point; imported modules may be built later.
        binding = _ModuleState(module.module_name, module.module_id, module.path, module.is_package,
                               definitions=dict(module.definitions),
                               imported_symbols=dict(module.imported_symbols),
                               imported_modules=dict(module.imported_modules))
        superclasses = node.child_by_field_name("superclasses")
        bases = ([self._text(child, source) for child in superclasses.named_children]
                 if superclasses is not None else [])
        if parent_qualified_name != module.module_name:
            for base in bases:
                local = self.symbols_by_qualified_name.get(f"{parent_qualified_name}.{base}")
                if local is not None:
                    binding.definitions[base] = local
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
        self.symbols_by_qualified_name[qualified_name] = node_id
        self._bind_scope(node_id, parent_id, qualified_name, node)
        self.classes.append(
            _ClassRecord(
                node_id=node_id,
                module_name=module.module_name,
                class_name=name,
                bases=bases,
                binding=binding,
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
        suffix = ".setter" if self._is_setter_decorator(decorators) else ""
        if suffix:
            self.renamed_duplicate_count += 1
        node_id = self._definition_id(id_kind, module.path, qualified_name + suffix, node)

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
        self.symbols_by_qualified_name[qualified_name] = node_id
        self._bind_scope(node_id, parent_id, qualified_name, node)
        return node_id, node_type, qualified_name

    def _definition_id(self, kind: str, path: str, qualified_name: str, node: Node) -> str:
        node_id = f"vgar:{self.repo_key}:python:{kind}:{path}:{qualified_name}"
        if node_id in self.nodes_by_id:
            self.renamed_duplicate_count += 1
            node_id += f"@definition:{node.start_byte}:{node.end_byte}"
        return node_id

    def _bind_scope(self, node_id: str, parent_id: str, qualified_name: str, node: Node) -> None:
        self.scope_nodes[node_id] = self.scope_locations.get((qualified_name, node.start_point.row + 1))
        self.scope_parent_ids[node_id] = parent_id

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
            # Imports assign the same module namespace as definitions; an earlier
            # class/function must not override a later explicit import binding.
            module.definitions.pop(local_name, None)
            module.imported_symbols.pop(local_name, None)
            module.imported_modules.pop(local_name, None)
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
            module = record.binding
            inherited_targets: set[str] = set()
            for position, base_expression in enumerate(record.bases, start=1):
                target_id = module.definitions.get(base_expression)
                if target_id is None and base_expression in module.imported_symbols:
                    imported_module, name = module.imported_symbols[base_expression]
                    target_id = self.symbols_by_qualified_name.get(f"{imported_module}.{name}")
                if target_id is None and "." in base_expression:
                    head, name = base_expression.split(".", 1)
                    imported_module = module.imported_modules.get(head)
                    if imported_module:
                        target_id = self.symbols_by_qualified_name.get(f"{imported_module}.{name}")
                target = self.nodes_by_id.get(target_id)
                if target is None or target["type"] != "Class" or target_id == record.node_id:
                    self.unresolved_bases.append({"node_id": record.node_id, "base_expression": base_expression,
                                                  "reason": "unbound_dynamic_or_ambiguous_base"})
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
                    identity_occurrence=position if target_id in inherited_targets else None,
                )
                inherited_targets.add(target_id)

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
            resolved_by_jedi = False
            if target_id is None:
                target_id = self._resolve_call_with_jedi(call)
                resolved_by_jedi = target_id is not None
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

            if resolved_by_jedi:
                binding_kind = (
                    "jedi_constructor" if target["type"] == "Class" else "jedi"
                )
                confidence = 0.85
                if target["type"] == "Class":
                    call_node["properties"]["dispatch_kind"] = "constructor"
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
                rule_id=(
                    "python.call.jedi.resolve.v1"
                    if resolved_by_jedi
                    else "python.call.resolve.v1"
                ),
                properties={
                    "binding_kind": binding_kind,
                    "argument_match": None,
                    "candidate_rank": 1,
                    "confidence_reason": (
                        "Jedi static-analysis target matched an internal graph symbol"
                        if resolved_by_jedi
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

        def visit(table: symtable.SymbolTable, qualified_name: str) -> None:
            self.scope_tables[qualified_name] = table
            self.scope_locations[(qualified_name, table.get_lineno())] = table
            for child in table.get_children():
                if child.get_name() in {"lambda", "listcomp", "setcomp", "dictcomp", "genexpr"}:
                    continue
                child_name = f"{qualified_name}.{child.get_name()}"
                self.scope_parents[child_name] = qualified_name
                visit(child, child_name)

        visit(table, module.module_name)

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
        scope_id = call.caller_id
        while scope_id in self.nodes_by_id and self.nodes_by_id[scope_id]["type"] != "Module":
            scope_name = self.nodes_by_id[scope_id]["qualified_name"]
            table = self.scope_nodes.get(scope_id)
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
                        target = self.symbols_by_qualified_name.get(f"{scope_name}.{name}")
                    return True, target
            scope_id = self.scope_parent_ids.get(scope_id, "")
        return False, None

    def _resolve_call_with_jedi(self, call: _CallRecord) -> str | None:
        if self.jedi_resolver is None:
            return None
        resolutions = self.jedi_resolver.resolve(
            call.path,
            line=call.line,
            column=call.column,
        )
        matches = {
            target_id
            for resolution in resolutions
            if (target_id := self._match_jedi_resolution(resolution)) is not None
        }
        return next(iter(matches)) if len(matches) == 1 else None

    def _match_jedi_resolution(self, resolution: JediResolution) -> str | None:
        if resolution.full_name:
            target_id = self.symbols_by_qualified_name.get(resolution.full_name)
            if target_id is not None:
                return target_id

        if (
            resolution.module_path is None
            or resolution.line is None
            or self.repository_root is None
        ):
            return None
        try:
            relative_path = resolution.module_path.relative_to(
                self.repository_root
            ).as_posix()
        except ValueError:
            return None

        candidates = [
            node["id"]
            for node in self.nodes
            if node["type"] in {"Class", "Function", "Method", "Test"}
            and node["path"] == relative_path
            and node["range"]["start_line"] == resolution.line
            and node["name"] == resolution.name
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _resolve_symbol(
        self,
        module: _ModuleState,
        expression: str,
        *,
        owner_class_name: str | None,
    ) -> str | None:
        if expression.split(".", 1)[0] in module.ambiguous_names:
            return None
        if expression == "cls" and owner_class_name:
            return self.symbols_by_qualified_name.get(
                f"{module.module_name}.{owner_class_name}"
            )

        if expression.startswith(("self.", "cls.")) and owner_class_name:
            method_name = expression.split(".", 1)[1]
            return self.symbols_by_qualified_name.get(
                f"{module.module_name}.{owner_class_name}.{method_name}"
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
        definitions = [node for node in self.nodes if node["type"] in {"Class", "Function", "Method", "Test"}]
        counts = Counter(node["qualified_name"] for node in definitions)
        for qualified_name, count in counts.items():
            if count > 1:
                self.symbols_by_qualified_name.pop(qualified_name, None)
        for module in self.modules.values():
            module.ambiguous_names = {name for name in module.definitions
                                      if counts[f"{module.module_name}.{name}"] > 1}
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
        identity_occurrence: int | None = None,
    ) -> None:
        # Repeated bases (including aliases) are separate source occurrences.
        # Keep existing IDs for ordinary edges; never silently drop duplicates.
        identity_text = f"{edge_type}\0{source_id}\0{target_id}\0{rule_id}"
        if identity_occurrence is not None:
            identity_text += f"\0occurrence:{identity_occurrence}"
        identity = self._hash_text(identity_text)
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
            "source_inventory": dict(self.source_inventory),
            "source_scope": self.source_scope.metadata(),
            "unresolved_base_count": len(self.unresolved_bases),
            "unresolved_bases": list(self.unresolved_bases),
            "build_time_ms": round((time.perf_counter() - started_at) * 1000, 3),
        }
