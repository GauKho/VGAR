"""Read direct class-namespace method aliases without executing target code."""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path


def _scope_nodes(node):
    yield node
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    for child in ast.iter_child_nodes(node):
        yield from _scope_nodes(child)


def _writes(statement):
    for node in _scope_nodes(statement):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            yield node.id
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name
        elif isinstance(node, ast.alias):
            yield node.asname or node.name.split('.')[0]
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            yield node.name
        elif isinstance(node, ast.MatchMapping) and node.rest:
            yield node.rest


def annotate_method_aliases(root: Path, nodes: list[dict]) -> list[tuple[str, str]]:
    """Attach final, unambiguous local aliases to their implementation node.

    Only a direct assignment from an earlier callable in the same class qualifies.
    Conditional writes, deletion, imports and reassignment invalidate that name.
    Inherited/global values, properties and dynamic namespace manipulation are
    deliberately unsupported. An alias never creates another implementation node.
    """
    by_path = defaultdict(list)
    existing = {node['qualified_name'] for node in nodes if node['type'] in {'Class', 'Function', 'Method', 'Test'}}
    for node in nodes:
        if node['type'] in {'Class', 'Method'}:
            by_path[node['path']].append(node)
    exports = defaultdict(list)
    for path, symbols in by_path.items():
        try:
            tree = ast.parse((root / path).read_bytes(), filename=path)
        except (SyntaxError, UnicodeError):
            continue
        locations = defaultdict(list)
        for node in symbols:
            locations[(node['range']['start_line'], node['name'])].append(node)
        for cls in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
            owners = locations.get((cls.lineno, cls.name), [])
            if len(owners) != 1 or owners[0]['type'] != 'Class':
                continue
            owner = owners[0]
            scope = [n for statement in cls.body for n in _scope_nodes(statement)]
            if any(isinstance(n, (ast.Global, ast.Nonlocal)) or
                   (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id in {'exec', 'eval', 'locals', 'globals', 'vars'}) for n in scope):
                continue
            bindings = {}
            for statement in cls.body:
                value = None
                target = None
                if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                    target, value = statement.targets[0], statement.value
                elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                    target, value = statement.target, statement.value
                copied = bindings.get(value.id) if isinstance(value, ast.Name) else None
                for name in _writes(statement):
                    bindings.pop(name, None)
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    candidates = locations.get((statement.lineno, statement.name), [])
                    if (len(candidates) == 1 and candidates[0]['type'] == 'Method'
                            and candidates[0]['qualified_name'] == owner['qualified_name']+'.'+statement.name
                            and candidates[0]['properties'].get('method_kind') != 'property'):
                        bindings[statement.name] = (candidates[0], None)
                elif isinstance(target, ast.Name) and copied:
                    span = {'start_line': target.lineno, 'start_col': target.col_offset,
                            'end_line': target.end_lineno, 'end_col': target.end_col_offset}
                    bindings[target.id] = (copied[0], span)
            for name, (implementation, span) in bindings.items():
                qualified = owner['qualified_name']+'.'+name
                if span is not None and qualified not in existing:
                    exports[qualified].append((implementation, {'name': name, 'qualified_name': qualified, 'range': span}))
    aliases = []
    for qualified, values in sorted(exports.items()):
        if len(values) != 1:
            continue
        implementation, evidence = values[0]
        implementation['properties'].setdefault('symbol_aliases', []).append(evidence)
        aliases.append((qualified, implementation['id']))
    return aliases
