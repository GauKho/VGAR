"""Baseline-relative cycles whose witnesses include a function/class import."""
import ast
from collections import defaultdict
from itertools import pairwise

from vgar.repair.check_result import CheckAnalysis
from vgar.repair.evidence import digest
from vgar.repair.structural_check import _normalized_import, _path

PROFILE = "python-source-local-imports-v1"


def _imports(graph, sources):
    internal = [node for node in graph["nodes"] if node["type"] == "Module" and not node["properties"]["is_external"]]
    modules = {node["properties"]["module_name"]: node for node in internal}
    if len(modules) != len(internal):
        raise ValueError("Source import module names are ambiguous")
    pairs = defaultdict(list)
    for name, module in sorted(modules.items()):
        raw = sources[module["path"]]
        tree = ast.parse(raw, filename=module["path"])
        source_hash = digest(raw)
        top_level = {id(node) for node in tree.body}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                targets = [_normalized_import(module, {"imported_module": node.module or "", "level": node.level})]
            else:
                continue
            for target in targets:
                if target in modules:
                    pairs[(name, target)].append({
                        "source": module["path"], "target": modules[target]["path"], "line": node.lineno,
                        "local": id(node) not in top_level, "source_hash": source_hash,
                    })
    return pairs


def check_source_import_cycles(baseline, candidate, before_sources, after_sources):
    try:
        before = _imports(baseline, before_sources)
        after = _imports(candidate, after_sources)
    except SyntaxError as exc:
        return CheckAnalysis("NOT_RUN", ("SOURCE_IMPORT_PARSE_UNAVAILABLE",), {"profile": PROFILE, "path": exc.filename})
    except ValueError:
        return CheckAnalysis("NOT_RUN", ("SOURCE_IMPORT_MODULES_AMBIGUOUS",), {"profile": PROFILE})
    adjacency = defaultdict(set)
    for source, target in after:
        adjacency[source].add(target)
    violations = []
    for source, target in sorted(after.keys() - before.keys()):
        back = _path(adjacency, target, source)
        if back is None:
            continue
        modules = [source, *back]
        edges = [after[pair] for pair in pairwise(modules)]
        if any(edge["local"] for group in edges for edge in group):
            violations.append({"modules": modules, "imports": edges})
    return CheckAnalysis("FAIL" if violations else "PASS",
                         ("NEW_SOURCE_IMPORT_CYCLE",) if violations else (), {
        "profile": PROFILE, "scope": "source-backed direct Python imports including local scopes",
        "violations": violations, "baseline_adjacencies": len(before), "candidate_adjacencies": len(after),
        "limitations": ["dynamic import calls are not resolved", "from-package attributes are not inferred as submodules"],
    })
