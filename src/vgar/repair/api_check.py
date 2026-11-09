"""M2-W11-1: compare static public Python APIs without importing target code.

``check_api`` consumes complete before/after bytes for the caller's selected
source scope. Absence of a path on one side means addition/deletion, not a
failed read. The caller owns snapshot/patch binding and source-scope selection.
Only AST declarations are analyzed; dynamic exports, imported re-exports and
ambiguous public bindings are explicitly unavailable. No runtime/MRO/type
inference is attempted. ``callers_in_repo`` is diagnostic only.

``changed_only=True`` checks the affected static public bindings and local
dependencies instead of letting unrelated unsupported bindings gate a patch.
It records excluded diagnostics; COMPLETE then covers only that patch scope.

The risk adapter is opt-in. It does not change the graph producer or any W9
default payload, and cannot attest that arbitrary snapshots belong to a report.
M1/M2 integration must bind snapshots to the same baseline and applied patch.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import PurePosixPath
import symtable
from typing import Any

from vgar.contracts.impact import ImpactReport
from vgar.repair.check_result import CheckAnalysis

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class _Symbol:
    kind: str
    line: int
    args: ast.arguments | None = None
    returns: ast.expr | None = None
    binding: str = 'function'
    is_async: bool = False

    def signature(self) -> dict[str, Any] | None:
        if self.args is None:
            return None
        return {'arguments': ast.dump(self.args, include_attributes=False),
                'returns': ast.dump(self.returns, include_attributes=False) if self.returns else None,
                'binding': self.binding, 'async': self.is_async}


def _snapshot(value: Mapping[str, bytes]) -> dict[str, bytes]:
    if not isinstance(value, Mapping):
        raise ValueError('Source snapshot must be a mapping of normalized paths to bytes')
    result = {}
    for path, raw in value.items():
        if not isinstance(path, str) or not path:
            raise ValueError('Source path must be a nonempty string')
        pure = PurePosixPath(path)
        if (pure.is_absolute() or pure.as_posix() != path or '..' in pure.parts
                or '.git' in pure.parts or pure.suffix != '.py' or path.startswith('-')
                or any(c in path for c in ('\\', ':', '\0', '\r', '\n'))):
            raise ValueError('Expected normalized repository-relative POSIX Python path')
        if type(raw) is not bytes:
            raise ValueError('Source content must be immutable bytes')
        result[path] = raw
    return dict(sorted(result.items()))


def _scope_nodes(body):
    """Walk statements/expressions of one namespace, excluding function/class bodies."""
    for node in body:
        yield node
        if not isinstance(node, (*_FUNCTIONS, ast.ClassDef, ast.Lambda)):
            yield from _scope_nodes(ast.iter_child_nodes(node))


def _targets(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in _targets(item)]
    return []


def _bindings(body):
    bindings: dict[str, list[ast.AST]] = {}
    conditional = set()
    for node in body:
        names = []
        if isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [name for target in node.targets for name in _targets(target)]
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            names = _targets(node.target)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.asname or alias.name.split('.')[0] for alias in node.names]
        else:
            for child in _scope_nodes([node]):
                if isinstance(child, (*_FUNCTIONS, ast.ClassDef)):
                    conditional.add(child.name)
                elif isinstance(child, (ast.Import, ast.ImportFrom)):
                    conditional.update(alias.asname or alias.name.split('.')[0] for alias in child.names)
                elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                    conditional.add(child.id)
        for name in names:
            bindings.setdefault(name, []).append(node)
    return bindings, conditional


def _exports(tree: ast.Module, bindings, conditional):
    assignments = []
    dynamic = '__all__' in conditional
    for node in _scope_nodes(tree.body):
        if isinstance(node, ast.Name) and node.id == '__all__':
            # Every use other than the single literal declaration is conservative unknown.
            if not isinstance(node.ctx, ast.Store):
                dynamic = True
        if isinstance(node, ast.Assign) and any('__all__' in _targets(t) for t in node.targets):
            assignments.append(node.value)
            if len(node.targets) != 1:
                dynamic = True
        elif isinstance(node, ast.AnnAssign) and '__all__' in _targets(node.target):
            assignments.append(node.value)
        elif isinstance(node, ast.AugAssign) and '__all__' in _targets(node.target):
            dynamic = True
    if len(assignments) > 1:
        dynamic = True
    if '__all__' in bindings and (not assignments or len(bindings['__all__']) != 1):
        dynamic = True  # Imported/aliased exports are not a local literal declaration.
    if assignments:
        value = assignments[0]
        if not isinstance(value, (ast.List, ast.Tuple)) or not all(
                isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts):
            dynamic = True
        if not dynamic:
            return sorted({item.value for item in value.elts}), None
    if dynamic:
        return [], 'API_DYNAMIC_EXPORTS'
    return sorted(name for name in set(bindings) | conditional if not name.startswith('_')), None


def _function(node, *, method=False):
    decorators = [ast.unparse(item) for item in node.decorator_list]
    if any(item not in ('staticmethod', 'classmethod', 'property') for item in decorators):
        return None
    binding = next((item for item in decorators if item in ('staticmethod', 'classmethod', 'property')),
                   'method' if method else 'function')
    args = node.args
    if method and binding != 'staticmethod':
        # Bound methods/constructors expose calls without their implicit receiver.
        args = ast.arguments(posonlyargs=list(args.posonlyargs), args=list(args.args),
            vararg=args.vararg, kwonlyargs=list(args.kwonlyargs), kw_defaults=list(args.kw_defaults),
            kwarg=args.kwarg, defaults=list(args.defaults))
        positional = args.posonlyargs + args.args
        if not positional:
            return None
        # A default on the receiver is uncommon but must not misalign remaining defaults.
        if len(args.defaults) == len(positional):
            args.defaults = args.defaults[1:]
        if args.posonlyargs:
            args.posonlyargs = args.posonlyargs[1:]
        else:
            args.args = args.args[1:]
    return _Symbol('function', node.lineno, args, node.returns, binding,
                   isinstance(node, ast.AsyncFunctionDef))


def _surface(tree, path, side, diagnostics):
    bindings, conditional = _bindings(tree.body)
    names, error = _exports(tree, bindings, conditional)
    symbols = {}

    def unknown(name, reason):
        diagnostics.append({'path': path, 'side': side, 'symbol': name, 'reason': reason})

    if error:
        unknown('__all__', error)
        return symbols
    if '*' in bindings:
        unknown('*', 'API_UNSUPPORTED_EXPORT')
    for name in names:
        candidates = bindings.get(name, [])
        if name in conditional or len(candidates) != 1:
            unknown(name, 'API_AMBIGUOUS_BINDING' if candidates or name in conditional else 'API_UNSUPPORTED_EXPORT')
            continue
        node = candidates[0]
        if isinstance(node, _FUNCTIONS):
            symbol = _function(node)
            if symbol is None:
                unknown(name, 'API_UNSUPPORTED_DECLARATION')
            else:
                symbols[name] = symbol
        elif isinstance(node, ast.ClassDef):
            if node.decorator_list or node.keywords:
                unknown(name, 'API_UNSUPPORTED_DECLARATION')
                continue
            members, ambiguous = _bindings(node.body)
            init = members.get('__init__', [])
            if '__init__' in ambiguous or len(init) > 1 or '__new__' in members or '__new__' in ambiguous:
                unknown(name, 'API_UNSUPPORTED_DECLARATION')
                continue
            ctor = _function(init[0], method=True) if init and isinstance(init[0], _FUNCTIONS) else None
            if init and (ctor is None or ctor.is_async or ctor.binding != 'method'):
                unknown(name, 'API_UNSUPPORTED_DECLARATION')
                continue
            if ctor:
                symbols[name] = _Symbol('class', node.lineno, ctor.args, ctor.returns, 'constructor')
            elif node.bases:
                # Local methods remain analyzable; inherited constructor is not inferred.
                unknown(name, 'API_INHERITED_CONSTRUCTOR')
                symbols[name] = _Symbol('class', node.lineno)
            else:
                symbols[name] = _Symbol('class', node.lineno, ast.arguments(
                    posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), binding='constructor')
            for member in sorted(set(members) | ambiguous):
                if member.startswith('_'):
                    continue
                declarations = members.get(member, [])
                qualified = name + '.' + member
                if member in ambiguous or len(declarations) != 1:
                    unknown(qualified, 'API_AMBIGUOUS_BINDING')
                elif isinstance(declarations[0], _FUNCTIONS):
                    symbol = _function(declarations[0], method=True)
                    if symbol is None:
                        unknown(qualified, 'API_UNSUPPORTED_DECLARATION')
                    else:
                        symbols[qualified] = symbol
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            unknown(name, 'API_UNSUPPORTED_EXPORT')
        else:
            try:
                # A name/lambda/call can be an exported callable. Never pretend
                # its missing signature is a measured compatible value.
                ast.literal_eval(node.value)
            except (ValueError, TypeError):
                unknown(name, 'API_UNSUPPORTED_DECLARATION')
            else:
                symbols[name] = _Symbol('value', node.lineno)
    return symbols


def _incompatibilities(old: _Symbol, new: _Symbol) -> list[str]:
    if old.kind != new.kind or old.binding != new.binding or old.is_async != new.is_async:
        return ['callable_kind_changed']
    if old.args is None or new.args is None:
        return []
    a, b = old.args, new.args
    apos, bpos = a.posonlyargs + a.args, b.posonlyargs + b.args
    names_a, names_b = [x.arg for x in apos], [x.arg for x in bpos]
    changes = []
    if names_b[:len(names_a)] != names_a:
        changes.append('positional_removed_renamed_or_reordered')
    if any(item.arg in {v.arg for v in a.args} for item in b.posonlyargs):
        changes.append('keyword_callability_removed')
    reserved = {v.arg for v in b.args} - {v.arg for v in a.args}
    if a.kwarg and (reserved & {v.arg for v in a.posonlyargs} or (a.vararg and reserved - set(names_a))):
        changes.append('kwargs_keyword_collision_introduced')
    old_optional = {item.arg for item in apos[len(apos)-len(a.defaults):]} if a.defaults else set()
    new_required = {item.arg for item in bpos[:len(bpos)-len(b.defaults)]}
    if old_optional & new_required:
        changes.append('default_removed')
    if new_required - set(names_a):
        changes.append('required_positional_added')
    akw, bkw = {v.arg: default for v, default in zip(a.kwonlyargs, a.kw_defaults)}, {
        v.arg: default for v, default in zip(b.kwonlyargs, b.kw_defaults)}
    if set(akw) - set(bkw):
        changes.append('keyword_only_removed')
    if any(default is None and (name not in akw or akw[name] is not None) for name, default in bkw.items()):
        changes.append('required_keyword_only_added_or_default_removed')
    if a.vararg and not b.vararg:
        changes.append('varargs_removed')
    if a.kwarg and not b.kwarg:
        changes.append('kwargs_removed')
    return changes


def _caller_evidence(value):
    if value is None:
        return {'available': False, 'reason': 'NOT_PROVIDED', 'by_symbol': {}}
    if not isinstance(value, Mapping):
        raise ValueError('callers_in_repo must be a mapping')
    detached = {}
    for name, callers in value.items():
        if (not isinstance(name, str) or not isinstance(callers, Sequence) or isinstance(callers, (str, bytes))
                or not all(isinstance(caller, str) for caller in callers)):
            raise ValueError('Expected symbol names mapped to sequences of caller references')
        detached[name] = sorted(set(callers))
    return {'available': True, 'by_symbol': dict(sorted(detached.items()))}


def _binding_loads(nodes):
    """Separate definition-time namespace loads from function-body globals."""
    definition, globals_ = set(), set()
    for node in nodes:
        expression = node.value if isinstance(node, ast.keyword) else node
        table = symtable.symtable(ast.unparse(expression), '<api-scope>', 'exec')
        definition.update(s.get_name() for s in table.get_symbols() if s.is_referenced())

        def walk(child):
            globals_.update(s.get_name() for s in child.get_symbols()
                            if s.is_referenced() and s.is_global())
            for nested in child.get_children():
                walk(nested)

        for child in table.get_children():
            walk(child)
    return definition, globals_


def _conditional_units(body):
    """Bind each declaration to its own statement and enclosing guards, never siblings."""
    records, loads, globals_by_name = {}, {}, {}

    def visit(node, context=(), guards=frozenset()):
        bindings, _ = _bindings([node]) if isinstance(node, ast.stmt) else ({}, set())
        names = set(bindings)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        if names:
            definition, globals_ = _binding_loads([node]) if isinstance(node, ast.stmt) else (set(), set())
            for name in names:
                records.setdefault(name, []).append((context, ast.dump(node, include_attributes=False)))
                loads.setdefault(name, set()).update(definition | guards)
                globals_by_name.setdefault(name, set()).update(globals_)
            return
        # Remove statement blocks from the header. Keep conditions/iterables,
        # handler types and branch identity, including nested if/try/with scopes.
        fields = dict(ast.iter_fields(node))
        blocks = {'body', 'orelse', 'finalbody', 'handlers', 'cases'}
        header = type(node)(**{key: [] if key in blocks else value for key, value in fields.items()})
        guard_names = {n.id for n in ast.walk(header)
                       if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        marker = ast.dump(header, include_attributes=False)
        for field, value in fields.items():
            children = value if isinstance(value, list) else [value]
            for child in children:
                if isinstance(child, ast.AST):
                    visit(child, context + ((marker, field),), guards | guard_names)

    for node in body:
        visit(node)
    return records, loads, globals_by_name


def _scope_units(tree):
    """Namespace bindings without locations; class headers/ctors are separate from methods."""
    units, dependencies = {}, {}

    def add_scope(body, prefix=''):
        bindings, conditional = _bindings(body)
        controls = [n for n in body if not isinstance(n, (*_FUNCTIONS, ast.ClassDef,
                    ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Import, ast.ImportFrom))]
        records, control_loads, control_globals = _conditional_units(controls)
        for name in sorted(set(bindings) | conditional):
            nodes = list(bindings.get(name, []))
            key = prefix + name
            extra = []
            extra_dependencies = set()
            load_nodes = nodes
            if len(nodes) == 1 and isinstance(nodes[0], ast.ClassDef) and not prefix:
                cls = nodes[0]
                members, ambiguous = _bindings(cls.body)
                # Include constructor definitions and conditional constructor ownership.
                load_nodes = [*cls.bases, *cls.keywords, *cls.decorator_list]
                nodes = [*load_nodes,
                         *(n for ctor in ('__init__', '__new__') for n in members.get(ctor, []))]
                ctor_records, ctor_loads, ctor_globals = _conditional_units(cls.body)
                for ctor in ('__init__', '__new__'):
                    extra_dependencies |= {key + '.' + n if n in (set(members) | ambiguous) else n
                                           for n in ctor_loads.get(ctor, set())}
                    extra_dependencies |= ctor_globals.get(ctor, set())
                if {'__init__', '__new__'} & ambiguous:
                    extra = [record for ctor in ('__init__', '__new__')
                             for record in ctor_records.get(ctor, [])]
                add_scope(cls.body, key + '.')
            units[key] = (tuple(ast.dump(n, include_attributes=False) for n in nodes),
                          tuple(records.get(name, [])), tuple(extra))
            definition, globals_ = _binding_loads(load_nodes)
            definition |= control_loads.get(name, set())
            dependencies[key] = {prefix + n if prefix and n in (set(bindings) | conditional)
                                 else n for n in definition} | globals_ | control_globals.get(name, set()) | extra_dependencies

    add_scope(tree.body)
    bindings, conditional = _bindings(tree.body)
    names, _ = _exports(tree, bindings, conditional)
    public = {name for name in units if name.split('.')[0] in names
              and ('.' not in name or not name.split('.', 1)[1].startswith('_'))}
    return units, dependencies, public


def _changed_scope(trees):
    """Select affected bindings, including transitive local dependencies and export membership."""
    selected, changed_paths = {}, set()
    for path in sorted(set(trees['baseline']) | set(trees['candidate'])):
        sides = [trees[side].get(path) for side in ('baseline', 'candidate')]
        projections = [_scope_units(tree) if tree else ({}, {}, set()) for tree in sides]
        old, new = projections
        affected = {name for name in set(old[0]) | set(new[0]) if old[0].get(name) != new[0].get(name)}
        affected |= old[2] ^ new[2]
        dependencies = {name: old[1].get(name, set()) | new[1].get(name, set())
                        for name in set(old[1]) | set(new[1])}
        while True:
            expanded = affected | {name for name, deps in dependencies.items()
                                   if any(dependency == item or item.startswith(dependency + '.')
                                          for dependency in deps for item in affected)}
            if expanded == affected:
                break
            affected = expanded
        selected[path] = sorted(affected & (old[2] | new[2]))
        dumps = [ast.dump(tree, include_attributes=False) if tree else None for tree in sides]
        if dumps[0] != dumps[1]:
            changed_paths.add(path)
    return selected, changed_paths


def _filter_scope(surfaces, trees, diagnostics):
    selected, changed_paths = _changed_scope(trees)
    included, excluded = [], []
    for diagnostic in diagnostics:
        path, name = diagnostic['path'], diagnostic.get('symbol', '')
        affected = set(selected.get(path, []))
        reason = diagnostic['reason']
        # Unknown export membership and parse failure cannot establish a safe scope.
        relevant = (reason == 'API_PARSE_ERROR' or name in affected
                    or name == '__all__' or (name == '*' and path in changed_paths)
                    or (reason == 'API_UNSUPPORTED_DECLARATION'
                        and any(item.startswith(name + '.') for item in affected)))
        (included if relevant else excluded).append(diagnostic)
    for side, paths in surfaces.items():
        for path, symbols in paths.items():
            affected = set(selected.get(path, []))
            _, _, public = _scope_units(trees[side][path])
            paths[path] = {name: symbol for name, symbol in symbols.items() if name in affected}
            # Some class attributes/nested declarations are outside the original
            # surface implementation. Selected does not mean supported.
            for name in sorted(affected):
                if (name not in symbols and name in public
                        and not any(d['path'] == path and d['side'] == side
                                    and (d.get('symbol') == name or name.startswith(d.get('symbol', '') + '.'))
                                    for d in included)):
                    included.append(dict(path=path, side=side, symbol=name,
                                         reason='API_UNSUPPORTED_DECLARATION'))
    return included, dict(mode='changed-public-symbols', algorithm='ast-binding-dependencies-v1',
                          selected=selected, excluded_diagnostics=excluded)


def check_api(before: Mapping[str, bytes], after: Mapping[str, bytes], *,
              callers_in_repo: Mapping[str, Sequence[str]] | None = None,
              changed_only: bool = False) -> CheckAnalysis:
    """Compare selected public declarations; unknown/error outranks a partial FAIL.

    Reasons are stable codes, with per-symbol evidence and raw source SHA256s in
    ``details``. Signature change is available only for a completely analyzed
    scope. This is a static compatibility check, not a claim about runtime API
    behavior, callers' coverage, or an entire repository outside the supplied maps.
    ``changed_only`` is opt-in for source-bound verification; legacy callers keep
    the full selected-file surface check. Dynamic export membership remains unknown.
    """
    if type(changed_only) is not bool:
        raise ValueError('changed_only must be a bool')
    snapshots = {'baseline': _snapshot(before), 'candidate': _snapshot(after)}
    diagnostics: list[dict[str, Any]] = []
    changes = []
    surfaces, trees = {}, {}
    for side, sources in snapshots.items():
        surfaces[side] = {}
        trees[side] = {}
        for path, raw in sources.items():
            try:
                tree = ast.parse(raw, filename=path)
                # ast.parse accepts duplicate arguments and break/return in
                # invalid scopes. Compile for validation only: never execute.
                compile(tree, path, 'exec', dont_inherit=True)
                trees[side][path] = tree
                surfaces[side][path] = _surface(tree, path, side, diagnostics)
            except (SyntaxError, ValueError, RecursionError) as error:
                diagnostics.append({'path': path, 'side': side, 'reason': 'API_PARSE_ERROR',
                                    'line': getattr(error, 'lineno', None), 'message': str(error)})
    scope = None
    if changed_only:
        diagnostics, scope = _filter_scope(surfaces, trees, diagnostics)
    signature_changed = False
    for path in sorted(set(snapshots['baseline']) | set(snapshots['candidate'])):
        old, new = surfaces['baseline'].get(path, {}), surfaces['candidate'].get(path, {})
        for name in sorted(set(old) | set(new)):
            previous, current = old.get(name), new.get(name)
            reason, incompatibilities = None, []
            if previous is None:
                reason = 'API_SYMBOL_ADDED'
            elif current is None:
                reason = 'API_SYMBOL_REMOVED'
            else:
                incompatibilities = _incompatibilities(previous, current)
                if incompatibilities:
                    reason = 'API_SIGNATURE_INCOMPATIBLE'
                elif previous.signature() != current.signature():
                    reason = 'API_SIGNATURE_CHANGED'
            if reason:
                signature_changed |= bool((previous and previous.args is not None)
                                          or (current and current.args is not None))
                changes.append({'path': path, 'symbol': name, 'reason': reason,
                    'baseline_line': previous.line if previous else None,
                    'candidate_line': current.line if current else None,
                    'before': previous.signature() if previous else None,
                    'after': current.signature() if current else None,
                    'incompatibilities': incompatibilities})
    reasons = {item['reason'] for item in changes
               if item['reason'] in ('API_SYMBOL_REMOVED', 'API_SIGNATURE_INCOMPATIBLE')}
    reasons.update(item['reason'] for item in diagnostics)
    if not snapshots['baseline'] and not snapshots['candidate']:
        reasons.add('API_EMPTY_SCOPE')
    status = ('ERROR' if 'API_PARSE_ERROR' in reasons else 'NOT_RUN' if diagnostics or 'API_EMPTY_SCOPE' in reasons
              else 'FAIL' if reasons else 'PASS')
    available = status in ('PASS', 'FAIL')
    feature = {'available': available, 'value': signature_changed if available else None}
    if not available:
        feature['reason'] = 'API_ANALYSIS_INCOMPLETE'
    details = {'scope': 'static-python-public-api', 'paths': sorted(set(before) | set(after)),
        'coverage': 'COMPLETE' if available else 'PARTIAL', 'signature_changed': feature,
        'source_hashes': {side: {p: 'sha256:' + hashlib.sha256(raw).hexdigest() for p, raw in sources.items()}
                          for side, sources in snapshots.items()},
        'changes': changes, 'diagnostics': diagnostics, 'callers_in_repo': _caller_evidence(callers_in_repo)}
    if scope is not None:
        details['scope'] = 'static-python-changed-public-api'
        details['analysis_scope'] = scope
    return CheckAnalysis(status, tuple(sorted(reasons)), details)


def with_api_risk(report: ImpactReport, analysis: CheckAnalysis) -> ImpactReport:
    """Return a validated detached report with only the signature risk enriched.

    The existing impact contract permits only NOT_COMPUTED/NO_CHANGED_NODES for
    unavailable reasons; richer API failure/coverage evidence stays in analysis.
    The caller must bind ``analysis`` to this report's source and patch first.
    """
    data = report.model_dump(mode='python')
    feature = analysis.details['signature_changed']
    measured = feature['available'] is True and analysis.status in ('PASS', 'FAIL')
    value = ({'name': 'signature_changed', 'available': True, 'value': feature['value']} if measured
             else {'name': 'signature_changed', 'available': False, 'reason': 'NOT_COMPUTED'})
    data['risk']['features'] = [item for item in data['risk']['features'] if item['name'] != 'signature_changed'] + [value]
    if measured:
        data['risk']['status'] = 'COMPLETE'
    return ImpactReport.model_validate(data)
