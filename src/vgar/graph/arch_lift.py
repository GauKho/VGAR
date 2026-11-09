"""GA-1, GA-2: lift the repository graph to the architecture layer G_arch (proposal §4.4, §6.5).

Pure rules over G_repo nodes and edges; ``PythonGraphBuilder._lift_architecture`` adds the result to the graph.
Design: docs/superpowers/specs/2026-11-09-tv2-ga-g-arch-design.md
"""
from __future__ import annotations

import ast
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

import yaml

RULE_VERSION = "arch-lift-v1"
SOURCE_TOOL = "vgar-arch-lift"

_ENTITY_TYPES = {"Class", "Function", "Method"}
_EPSILON = 1e-9
_MAX_EVIDENCE = 5


@dataclass(frozen=True)
class EdgeSpec:
    type: str
    source_id: str
    target_id: str
    confidence: float
    resolution: str
    rule: str
    properties: dict[str, Any]
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeploymentFile:
    path: str
    data: bytes
    read_error: str | None = None


@dataclass
class LiftResult:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Component:
    key: str
    kind: str
    module: dict[str, Any]
    files: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"vgar:{self.module['repo_key']}:python:component:{self.key}"


def _partition(modules: Mapping[str, dict[str, Any]], is_test: Callable[[str], bool],
               has_entities: Callable[[str], bool]) -> tuple[str, dict[str, _Component]]:
    """Spec §5.1: path -> Component, by package when the repo has at least two non-test packages, else by module."""
    sources = sorted(path for path in modules if not is_test(path))
    packages = {str(PurePosixPath(path).parent) for path in sources if PurePosixPath(path).name == "__init__.py"} - {"."}
    by_file: dict[str, _Component] = {}
    if len(packages) >= 2:
        components = {key: _Component(key, "package", modules[f"{key}/__init__.py"]) for key in sorted(packages)}
        for path in sources:
            owner = next((str(parent) for parent in PurePosixPath(path).parents if str(parent) in packages), None)
            if owner is not None:
                components[owner].files.append(path)
                by_file[path] = components[owner]
        return "package", by_file
    for path in sources:
        if PurePosixPath(path).name != "__init__.py" or has_entities(path):
            by_file[path] = _Component(path.removesuffix(".py"), "module", modules[path], [path])
    return "module", by_file


def read_dunder_all(source: bytes) -> frozenset[str]:
    """Names in the module's last ``__all__ = [...]`` when it is all string literals; empty otherwise (spec §5.4)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return frozenset()
    names: frozenset[str] = frozenset()
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in statement.targets):
            value = statement.value
            items = value.elts if isinstance(value, (ast.List, ast.Tuple)) else [None]
            literal = all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in items)
            names = frozenset(item.value for item in items) if literal else frozenset()
    return names


def _routes(nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    """Symbol id -> names of the Routes that point at it."""
    by_id = {node["id"]: node for node in nodes}
    routes: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge["type"] == "REFERENCES" and by_id[edge["source_id"]]["type"] == "Route":
            routes[edge["target_id"]].append(by_id[edge["source_id"]]["name"])
    return routes


def select_ports(nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]],
                 exports: Mapping[str, frozenset[str]]) -> list[tuple[dict[str, Any], str]]:
    """infer_public_ports (proposal line 606) without Components: (symbol, how it is exported), in node order."""
    by_id = {node["id"]: node for node in nodes}
    parents = {edge["target_id"]: edge["source_id"] for edge in edges if edge["type"] == "CONTAINS"}
    routes = _routes(nodes, edges)

    def hidden(node_id: str) -> bool:
        ancestor = parents.get(node_id)
        while ancestor in by_id:  # a graph of a few files has no Repository node above its Files
            node = by_id[ancestor]
            if node["type"] in {"Function", "Method", "Test"} or (node["type"] == "Class" and node["name"].startswith("_")):
                return True
            ancestor = parents.get(ancestor)
        return False

    selected: list[tuple[dict[str, Any], str]] = []
    for node in nodes:
        if node["type"] not in {"Function", "Method"} or hidden(node["id"]):
            continue
        name = node["name"]
        export = ("public_name" if not name.startswith("_") else
                  "dunder_all" if name in exports.get(node["path"], frozenset()) else
                  "route" if routes[node["id"]] else None)
        if export is not None:
            selected.append((node, export))
    return selected


def _ports(repo_key: str, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]], by_file: Mapping[str, _Component],
           exports: Mapping[str, frozenset[str]]) -> dict[str, dict[str, Any]]:
    """Symbol id -> Port node (spec §5.4)."""
    routes = _routes(nodes, edges)
    ports: dict[str, dict[str, Any]] = {}
    taken: set[str] = set()
    for node, export in select_ports(nodes, edges, exports):
        owner = by_file.get(node["path"])
        if owner is None:
            continue
        name = node["name"]
        port_id = f"vgar:{repo_key}:python:port:{node['path']}:{node['qualified_name']}"
        if port_id in taken:
            port_id += f"@definition:{node['range']['start_line']}:{node['range']['start_col']}"
        taken.add(port_id)
        ports[node["id"]] = {
            "id": port_id, "type": "Port", "repo_key": repo_key, "name": name, "qualified_name": node["qualified_name"],
            "path": node["path"], "language": "python", "range": dict(node["range"]), "content_hash": node["content_hash"],
            "properties": {"symbol_id": node["id"], "signature": node["properties"]["signature"], "owner_component_id": owner.id,
                           "kind": node["type"].lower(), "export": export, "routes": sorted(routes[node["id"]])},
        }
    return ports


def _signal(present: Any) -> str:
    return "used" if present else "absent"


def _is_dockerfile(name: str) -> bool:
    return name == "Dockerfile" or name.startswith("Dockerfile.") or name.endswith(".Dockerfile")


def _is_compose(name: str) -> bool:
    return name in {"compose.yml", "compose.yaml"} or (name.startswith("docker-compose") and name.endswith((".yml", ".yaml")))


def find_deployment_files(root: Path, ignored: Collection[str]) -> list[DeploymentFile]:
    """Dockerfiles and compose files under ``root``, ordered by path; same directory policy as the source inventory."""
    found = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in ignored and not (Path(directory) / name).is_symlink())
        for name in filenames:
            path = Path(directory) / name
            if (_is_dockerfile(name) or _is_compose(name)) and not path.is_symlink():
                relative = path.relative_to(root).as_posix()
                try:
                    found.append(DeploymentFile(relative, path.read_bytes()))
                except OSError as error:
                    found.append(DeploymentFile(relative, b"", type(error).__name__))
    return sorted(found, key=lambda item: item.path)


def parse_copy_sources(text: str) -> list[str]:
    """Literal local sources of COPY/ADD, without ``--from=`` stages, ``..``, wildcards or URLs (spec §5.5)."""
    sources: list[str] = []
    for line in re.sub(r"\\\r?\n", " ", text).splitlines():
        words = line.split(None, 1)
        if len(words) < 2 or words[0].upper() not in {"COPY", "ADD"}:
            continue
        rest = words[1].strip()
        flags = re.match(r"(?:--\S+\s+)*", rest)
        if "--from=" in flags.group(0):
            continue
        rest = rest[flags.end():]
        try:
            arguments = json.loads(rest) if rest.startswith("[") else rest.split()
        except json.JSONDecodeError:
            continue
        for source in arguments[:-1]:
            if not isinstance(source, str) or "://" in source or re.search(r"[*?\[]", source) or ".." in PurePosixPath(source).parts:
                continue
            sources.append(str(PurePosixPath(source.lstrip("/") or ".")))
    return sources


def _lift_dockerfile(repo_key: str, item: DeploymentFile, components: Sequence[_Component], result: LiftResult,
                     errors: list[dict[str, str]]) -> None:
    unit_id = f"vgar:{repo_key}:deployment_unit:{item.path}"
    result.nodes.append({"id": unit_id, "type": "DeploymentUnit", "repo_key": repo_key, "name": PurePosixPath(item.path).name,
                         "qualified_name": item.path, "path": item.path, "language": None, "range": None, "properties": {}})
    try:
        text = item.data.decode("utf-8")
    except UnicodeDecodeError as error:
        errors.append({"path": item.path, "reason": type(error).__name__})
        return
    home = PurePosixPath(item.path).parent
    bases = {str(home / source) for source in parse_copy_sources(text)}
    for component in components:
        location = component.key if component.kind == "package" else component.files[0]
        if any(base == "." or location == base or location.startswith(f"{base}/") for base in bases):
            result.edges.append(EdgeSpec("DEPLOYS_TO", component.id, unit_id, 0.6, "heuristic", "deploys_to", {}))


def _lift_compose(repo_key: str, item: DeploymentFile, result: LiftResult, errors: list[dict[str, str]]) -> None:
    try:
        document = yaml.safe_load(item.data)
    except (yaml.YAMLError, ValueError, RecursionError) as error:  # safe_load raises ValueError on an impossible date
        errors.append({"path": item.path, "reason": type(error).__name__})
        return
    services = document.get("services") if isinstance(document, dict) else None
    if services is None:
        return
    if not isinstance(services, dict):
        errors.append({"path": item.path, "reason": "services is not a mapping"})
        return
    declared = {name: body if isinstance(body, dict) else {} for name, body in services.items() if isinstance(name, str) and name}
    identifiers = {name: f"vgar:{repo_key}:service:{item.path}:{name}" for name in declared}
    for name, body in sorted(declared.items()):
        build = body.get("build")
        context = build.get("context") if isinstance(build, dict) else build
        image = body.get("image")
        result.nodes.append({
            "id": identifiers[name], "type": "Service", "repo_key": repo_key, "name": name,
            "qualified_name": f"{item.path}:{name}", "path": item.path, "language": None, "range": None,
            "properties": {"image": image if isinstance(image, str) else None,
                           "build_context": context if isinstance(context, str) else None, "compose_file": item.path},
        })
    for name, body in sorted(declared.items()):
        needs = body.get("depends_on") or ()
        for dependency in sorted({need for need in needs if isinstance(need, str)}) if isinstance(needs, (list, dict)) else ():
            if dependency in declared and dependency != name:
                result.edges.append(EdgeSpec("COMMUNICATES_WITH", identifiers[name], identifiers[dependency], 0.7, "heuristic",
                                             "communicates_with", {}))


def lift(repo_key: str, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]], *,
         is_test: Callable[[str], bool], exports: Mapping[str, frozenset[str]] = MappingProxyType({}),
         deployment: Sequence[DeploymentFile] = ()) -> LiftResult:
    by_id = {node["id"]: node for node in nodes}
    modules = {node["path"]: node for node in nodes
               if node["type"] == "Module" and node.get("path") and not node["properties"].get("is_external")}
    entities_by_file: Counter[str] = Counter(node["path"] for node in nodes if node["type"] in _ENTITY_TYPES)
    mode, by_file = _partition(modules, is_test, lambda path: entities_by_file[path] > 0)
    components = sorted({component.key: component for component in by_file.values()}.values(), key=lambda c: c.key)

    internal: Counter[str] = Counter()
    external: Counter[str] = Counter()
    crossing: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        if edge["type"] not in {"CALLS", "IMPORTS"}:
            continue
        source = by_file.get(by_id[edge["source_id"]].get("path"))
        target = by_file.get(by_id[edge["target_id"]].get("path"))
        if source is None or target is None:
            continue
        if source.key == target.key:
            internal[source.key] += 1
        else:
            crossing[source.key, target.key].append(edge)
            external[source.key] += 1
            external[target.key] += 1

    tests: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge["type"] == "TESTS":
            owner = by_file.get(by_id[edge["target_id"]].get("path"))
            if owner is not None:
                tests[owner.key].add(by_id[edge["source_id"]]["path"])

    result = LiftResult()
    for component in components:
        entity_count = sum(entities_by_file[path] for path in component.files)
        inside, outside = internal[component.key], external[component.key]
        qualified_name = component.module["qualified_name"]
        result.nodes.append({
            "id": component.id, "type": "Component", "repo_key": repo_key, "name": qualified_name.rsplit(".", 1)[-1],
            "qualified_name": qualified_name, "path": None, "language": "python", "range": None,
            "properties": {
                "kind": component.kind, "files": component.files, "tests": sorted(tests[component.key]),
                "entity_count": entity_count, "internal_dependency_weight": inside, "external_dependency_weight": outside,
                "cohesion": round(inside / (inside + outside + _EPSILON), 6),
                "coupling": round(outside / max(1, entity_count), 6),
            },
        })
        result.edges.append(EdgeSpec("CONTAINS_COMPONENT", component.module["id"], component.id, 1.0, "exact",
                                     "contains_component", {}))

    identifiers = {component.key: component.id for component in components}
    for (source_key, target_key), counted in sorted(crossing.items()):
        calls = sum(edge["type"] == "CALLS" for edge in counted)
        result.edges.append(EdgeSpec(
            "DEPENDS_ON", identifiers[source_key], identifiers[target_key],
            round(sum(edge["confidence"] for edge in counted) / len(counted), 4), "heuristic", "depends_on",
            {"weight": len(counted), "call_count": calls, "import_count": len(counted) - calls},
            tuple(sorted(edge["id"] for edge in counted)[:_MAX_EVIDENCE])))

    ports = _ports(repo_key, nodes, edges, by_file, exports)
    for port in ports.values():
        result.nodes.append(port)
        result.edges.append(EdgeSpec("EXPOSES_PORT", port["properties"]["owner_component_id"], port["id"], 1.0, "exact",
                                     "exposes_port", {}))
    consumed: dict[tuple[str, str], list[float]] = defaultdict(list)
    for edge in edges:
        port = ports.get(edge["target_id"]) if edge["type"] == "CALLS" else None
        caller = by_file.get(by_id[edge["source_id"]].get("path")) if port is not None else None
        if caller is not None and caller.id != port["properties"]["owner_component_id"]:
            consumed[caller.id, port["id"]].append(edge["confidence"])
    for (component_id, port_id), confidences in sorted(consumed.items()):
        result.edges.append(EdgeSpec("CONSUMES_PORT", component_id, port_id, max(confidences), "heuristic", "consumes_port",
                                     {"call_count": len(confidences)}))

    readers: Counter[tuple[str, str]] = Counter()
    for edge in edges:
        if edge["type"] == "REFERENCES" and by_id[edge["target_id"]]["type"] == "ConfigEntry":
            reader = by_file.get(by_id[edge["source_id"]].get("path"))
            if reader is not None:
                readers[edge["target_id"], reader.id] += 1
    for (config_id, component_id), count in sorted(readers.items()):
        result.edges.append(EdgeSpec("CONFIGURES", config_id, component_id, 0.8, "heuristic", "configures", {"reader_count": count}))

    errors = [{"path": item.path, "reason": item.read_error} for item in deployment if item.read_error is not None]
    dockerfiles = [item for item in deployment if _is_dockerfile(PurePosixPath(item.path).name)]
    compose_files = [item for item in deployment if _is_compose(PurePosixPath(item.path).name)]
    for item in dockerfiles:
        if item.read_error is None:
            _lift_dockerfile(repo_key, item, components, result, errors)
    for item in compose_files:
        if item.read_error is None:
            _lift_compose(repo_key, item, result, errors)

    sources = {node["path"] for node in nodes if node["type"] == "File" and not is_test(node["path"])}
    result.report = {"mode": mode, "component_count": len(components), "port_count": len(ports),
                     "unassigned_source_files": len(sources - set(by_file)),
                     "signals": {
                         "package_path": _signal(components),
                         "density": _signal(internal or crossing),
                         "class_ownership": _signal(any(entities_by_file[path] for path in by_file)),
                         "naming": _signal(any(node["type"] == "File" and is_test(node["path"]) for node in nodes)),
                         "route_config": _signal(any(node["type"] in {"Route", "ConfigEntry"} for node in nodes)),
                         "co_change": "unavailable",
                         "deployment": _signal(deployment),
                         "test_grouping": _signal(any(tests.values())),
                     },
                     "deployment": {"dockerfiles": len(dockerfiles), "compose_files": len(compose_files),
                                    "errors": sorted(errors, key=lambda error: error["path"])}}
    return result
