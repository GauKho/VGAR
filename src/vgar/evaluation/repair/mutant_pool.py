"""Frozen evaluation-only gold/mutant pool; never imports or calls a verifier.

Labels describe the synthetic operator's expectation, not a proved behavioral
failure. Candidate eligibility is static and independent of evaluation results.
Only existing production-file changes are supported; unavailable slots remain
in the ledger. Source repositories and their Git metadata are read-only.
"""
from __future__ import annotations

import ast
from bisect import bisect_left
import copy
from dataclasses import dataclass
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import tokenize
from typing import Sequence

from vgar.repair.admission import base_inventory
from vgar.repair.contracts import safe_path
from vgar.repair.patch import PatchPolicy, _bind, parse_unified_diff
from vgar.repair.workspace import inventory

SCHEMA = 'vgar-mutant-pool-v1'
OPERATORS = ('condition_flip', 'public_function_delete', 'signature_change', 'import_cycle', 'test_skip')
ROOT = Path(__file__).resolve().parents[4]
W10_MANIFEST_HASH = 'sha256:11e0b7b1168236e246dc8334db45ad932223a16ae7af0de149f30f25585f4177'
W10_IDS = (
    'astropy__astropy-13033', 'django__django-10914', 'matplotlib__matplotlib-13989',
    'mwaskom__seaborn-3069', 'pallets__flask-5014', 'psf__requests-1724', 'pydata__xarray-3993',
    'pylint-dev__pylint-4604', 'pytest-dev__pytest-5631', 'scikit-learn__scikit-learn-10297',
    'sphinx-doc__sphinx-10673', 'sympy__sympy-11618', 'astropy__astropy-13453',
    'django__django-10973', 'matplotlib__matplotlib-20488', 'psf__requests-1766',
    'pydata__xarray-4629', 'pylint-dev__pylint-4970', 'pytest-dev__pytest-7205',
    'scikit-learn__scikit-learn-10844', 'sphinx-doc__sphinx-11510', 'sympy__sympy-12481',
    'astropy__astropy-13977', 'django__django-11087', 'matplotlib__matplotlib-20676')


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _hash(raw: bytes) -> str:
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class PoolTask:
    task_id: str
    repo: str
    base_commit: str
    source_repo: Path
    gold_patch: str
    allowed_paths: tuple[str, ...]
    protected_paths: tuple[str, ...] = ('tests', 'pytest.ini')
    source_inventory: dict[str, str] | None = None
    fixture: bool = False
    unavailable_reason: str | None = None


def _production(path: str) -> bool:
    return (path.endswith('.py') and not any(p.lower() in ('tests', 'test', 'testing') for p in path.split('/')[:-1])
            and not Path(path).name.startswith(('test_', 'conftest')))


def _validate_tasks(tasks, seed):
    if type(seed) is not int or seed < 0:
        raise ValueError('Seed must be a nonnegative integer')
    if not tasks or isinstance(tasks, (str, bytes)):
        raise ValueError('Nonempty ordered tasks required')
    ids = []
    for task in tasks:
        if not isinstance(task, PoolTask) or not re.fullmatch(r'[A-Za-z0-9_.-]+', task.task_id):
            raise ValueError('PoolTask with a safe task ID required')
        if not task.repo or not task.base_commit or type(task.fixture) is not bool:
            raise ValueError('Task repo/base/fixture identity required')
        if not task.fixture and not re.fullmatch(r'[0-9a-f]{40}', task.base_commit):
            raise ValueError('Real source requires a pinned base commit')
        if not isinstance(task.gold_patch, str) or not isinstance(task.allowed_paths, (list, tuple)):
            raise ValueError('Gold patch text and explicit allowed production paths required')
        if (not task.allowed_paths and not task.unavailable_reason) or len(set(task.allowed_paths)) != len(task.allowed_paths):
            raise ValueError('Nonempty unique production scope required')
        for path in (*task.allowed_paths, *task.protected_paths):
            safe_path(path)
        if any(not _production(p) for p in task.allowed_paths):
            raise ValueError('Pool mutations may only target production Python paths')
        if any(p == q or p.startswith(q + '/') for p in task.allowed_paths for q in task.protected_paths):
            raise ValueError('Production scope overlaps protected paths')
        ids.append(task.task_id)
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate pool task ID')
    if not all(t.fixture for t in tasks):
        if any(t.fixture for t in tasks) or tuple(ids) != W10_IDS or seed != 0:
            raise ValueError('Real pools require the exact ordered 25 W10 tasks and seed 0, with no fixtures')


def _provenance(value, *, fixture):
    if fixture:
        if value.get('kind') != 'fixture':
            raise ValueError('Fixture pool must be explicitly marked fixture')
        return
    from vgar.evaluation.harness.gold_inputs import PARQUET_HASH
    from vgar.evaluation.retrieval.pilot_manifest import DATASET_REVISION
    if (value.get('kind') != 'pinned_w10' or value.get('dataset_revision') != DATASET_REVISION
            or value.get('parquet_hash') != PARQUET_HASH or value.get('manifest_hash') != W10_MANIFEST_HASH):
        raise ValueError('Real pool dataset/manifest pins differ from approved inputs')
    configs, inputs = value.get('config_hashes'), value.get('task_input_hashes')
    if (not isinstance(configs, dict) or set(configs) != {'w10_dev_stage1.json', 'w10_dev_stage2.json'}
            or not isinstance(inputs, dict) or not set(inputs) <= set(W10_IDS)
            or any(not isinstance(h, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', h)
                   for h in [*configs.values(), *inputs.values()])):
        raise ValueError('Real pool config/input hash pins missing or malformed')
    status, actual = value.get('dataset_status'), value.get('dataset_actual_hash')
    if status == 'READY':
        if actual != PARQUET_HASH:
            raise ValueError('Ready dataset bytes do not match pinned Parquet hash')
    elif status == 'PARQUET_NOT_READY':
        if actual is not None:
            raise ValueError('Unavailable dataset cannot have actual bytes hash')
    elif status == 'PARQUET_HASH_MISMATCH':
        if not isinstance(actual, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', actual) or actual == PARQUET_HASH:
            raise ValueError('Dataset integrity error evidence missing')
    else:
        raise ValueError('Unknown dataset readiness status')


def _snapshot(task):
    if not Path(task.source_repo).is_dir():
        raise ValueError('Source checkout unavailable')
    current = inventory(Path(task.source_repo)) if task.fixture else base_inventory(Path(task.source_repo), task.base_commit)
    if task.source_inventory is not None and current != task.source_inventory:
        raise ValueError('Pinned source inventory differs')
    return current


def _policy(task):
    # Pool preparation does not filter by repair outcomes or silently relabel
    # larger patches. The evaluator still applies its actual repair policy.
    return PatchPolicy(tuple(task.allowed_paths), tuple(task.protected_paths),
                       max_bytes=16 * 1024 * 1024, max_files=1000, max_changed_lines=1_000_000)


def _apply_memory(base, patch, policy):
    with tempfile.TemporaryDirectory(prefix='vg-pool-bind-') as private:
        root = Path(private)
        for path, raw in base.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        predicted, _ = _bind(parse_unified_diff(patch, policy), root)
    return base | predicted


def _net_patch(base, candidate):
    result = []
    for path in sorted(base):
        if base[path] == candidate[path]:
            continue
        before = base[path].decode('utf-8').splitlines(keepends=True)
        after = candidate[path].decode('utf-8').splitlines(keepends=True)
        # Canonical diff uses LF; _bind restores the file's original EOL bytes.
        for line in difflib.unified_diff(before, after, fromfile='a/' + path, tofile='b/' + path, lineterm='\n'):
            if line.endswith('\n'):
                result.append(line.rstrip('\r\n') + '\n')
            else:
                result.append(line + '\n\\ No newline at end of file\n')
    return ''.join(result)


def _offset(raw, line, column):
    return sum(len(s) for s in raw.splitlines(keepends=True)[:line - 1]) + column


def _char_offset(raw, position):
    line, column = position
    lines = raw.splitlines(keepends=True)
    return sum(map(len, lines[:line - 1])) + len(lines[line - 1].decode('utf-8')[:column].encode('utf-8'))


def _span(raw, node):
    return _offset(raw, node.lineno, node.col_offset), _offset(raw, node.end_lineno, node.end_col_offset)


def _public_functions(tree):
    exports = None
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == '__all__'):
            return []
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == '__all__' for t in targets):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                return []
            if not isinstance(value, (list, tuple, set)) or any(not isinstance(v, str) for v in value):
                return []
            exports = set(value)
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == '__all__':
            return []
    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and (n.name in exports if exports is not None else not n.name.startswith('_'))]
    return [n for n in functions if sum(v.name == n.name for v in functions) == 1]


def _candidate(path, raw, start, end, replacement, node, **details):
    return dict(path=path, start_byte=start, end_byte=end, replacement=replacement,
        start_line=node.lineno, start_col=node.col_offset, end_line=node.end_lineno, end_col=node.end_col_offset,
        **details)


def _ordinary_candidates(sources, operator):
    candidates = []
    for path, raw in sorted(sources.items()):
        try:
            tree = ast.parse(raw.decode('utf-8'))
        except (SyntaxError, UnicodeError, ValueError):
            continue
        if operator == 'condition_flip':
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While)):
                    start, end = _span(raw, node.test)
                    candidates.append(_candidate(path, raw, start, end, b'not (' + raw[start:end] + b')', node.test))
            continue
        tokens = list(tokenize.tokenize(io.BytesIO(raw).readline)) if operator == 'signature_change' else []
        token_lines = [token.start[0] for token in tokens]
        for node in _public_functions(tree):
            if operator == 'public_function_delete':
                line = min([node.lineno, *[d.lineno for d in node.decorator_list]])
                start = _offset(raw, line, 0)
                end = sum(map(len, raw.splitlines(keepends=True)[:node.end_lineno]))
                candidates.append(_candidate(path, raw, start, end, b'', node, symbol=node.name))
            elif operator == 'signature_change':
                seen_def, depth, opening = False, 0, None
                for token in tokens[bisect_left(token_lines, node.lineno):]:
                    if not seen_def:
                        seen_def = token.type == tokenize.NAME and token.string == 'def'
                        continue
                    if token.string == '(':
                        if opening is None:
                            opening = token
                        depth += 1
                    elif token.string == ')' and opening is not None:
                        depth -= 1
                        if depth == 0:
                            args = copy.deepcopy(node.args)
                            names = {n.arg for n in [*args.posonlyargs, *args.args, *args.kwonlyargs,
                                *([args.vararg] if args.vararg else []), *([args.kwarg] if args.kwarg else [])]}
                            name = '_vgar_required'
                            while name in names:
                                name += '_'
                            args.kwonlyargs.append(ast.arg(arg=name))
                            args.kw_defaults.append(None)
                            start, end = _char_offset(raw, opening.end), _char_offset(raw, token.start)
                            candidates.append(_candidate(path, raw, start, end, ast.unparse(args).encode('utf-8'),
                                                         node, symbol=node.name, added_required_parameter=name))
                            break
            elif operator == 'test_skip':
                first = node.body[0]
                start, _ = _span(raw, first)
                statement = b'raise __import__("unittest").SkipTest("VGAR synthetic skip mutant")'
                if first.lineno == node.lineno:
                    insert = statement + b'; '
                else:
                    indent = raw.splitlines()[first.lineno - 1][:first.col_offset]
                    insert = statement + (b'\r\n' if b'\r\n' in raw else b'\n') + indent
                candidates.append(_candidate(path, raw, start, start, insert, first, symbol=node.name))
    return candidates


def _module(path):
    parts = path.removesuffix('.py').split('/')
    if parts[0] == 'src':
        parts = parts[1:]
    if parts and parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts) if parts and all(p.isidentifier() for p in parts) else None


def _cycle_candidates(sources):
    owners = {}
    for path in sources:
        name = _module(path)
        if name:
            owners.setdefault(name, []).append(path)
    modules = {name: paths[0] for name, paths in owners.items() if len(paths) == 1}
    edges = set()

    def resolve(name):
        # An internal prefix does not resolve an external/unavailable suffix.
        # From-imports use their explicit module, not a guessed alias submodule.
        return name if name in modules else None

    for name, path in sorted(modules.items()):
        try:
            tree = ast.parse(sources[path].decode('utf-8'))
        except (SyntaxError, UnicodeError, ValueError):
            continue
        package = name if path.endswith('/__init__.py') else name.rpartition('.')[0]
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Import):
                targets = [resolve(alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split('.') if package else []
                    if node.level > len(parts):
                        continue
                    prefix = '.'.join(parts[:len(parts) - node.level + 1])
                    target = '.'.join(p for p in (prefix, node.module) if p)
                else:
                    target = node.module or ''
                targets = [resolve(target)]
            edges.update((name, target) for target in targets if target)
    candidates = []
    for source, target in sorted(edges):
        if source == target or (target, source) in edges:
            continue
        path, raw = modules[target], sources[modules[target]]
        eol = b'\r\n' if b'\r\n' in raw else b'\n'
        addition = (b'' if not raw or raw.endswith(b'\n') else eol)
        addition += ('import ' + source + ' as _vgar_cycle').encode('utf-8') + eol
        candidates.append(dict(path=path, start_byte=len(raw), end_byte=len(raw), replacement=addition,
            start_line=len(raw.splitlines()) + 1, start_col=0, end_line=len(raw.splitlines()) + 1, end_col=0,
            source_module=target, target_module=source, existing_edge=[source, target]))
    return candidates


def _slot(task, operator, status, reason, *, mutation=None, patch_ref=None, patch_hash=None, predicted_inventory=None):
    return dict(slot_id=task.task_id + '::' + operator, task_id=task.task_id, operator=operator,
        label='GOOD' if operator == 'gold' else 'BAD', status=status, reason=reason, mutation=mutation,
        patch_ref=patch_ref, patch_hash=patch_hash, predicted_inventory=predicted_inventory,
        predicted_inventory_hash=_hash(_canonical(predicted_inventory)) if predicted_inventory is not None else None)


def _build_task(task, ordinal, seed):
    entry = dict(task_id=task.task_id, repo=task.repo, base_commit=task.base_commit, fixture=task.fixture,
        allowed_paths=sorted(task.allowed_paths), protected_paths=sorted(task.protected_paths),
        gold_original_hash=_hash(task.gold_patch.encode('utf-8')), source_inventory=None, source_inventory_hash=None)
    before = None
    try:
        if task.unavailable_reason:
            raise ValueError(task.unavailable_reason)
        before = _snapshot(task)
        entry.update(source_inventory=before, source_inventory_hash=_hash(_canonical(before)))
        base = {p: (Path(task.source_repo) / p).read_bytes() for p in sorted(task.allowed_paths)}
        gold = _apply_memory(base, task.gold_patch, _policy(task))
    except (ValueError, OSError, RuntimeError, UnicodeError):
        reason = task.unavailable_reason or ('SOURCE_NOT_READY' if before is None else 'GOLD_PATCH_UNSUPPORTED')
        return entry, [_slot(task, op, 'ERROR', reason) for op in ('gold', *OPERATORS)], {}
    slots, patches = [], {}
    for operator in ('gold', *OPERATORS):
        mutation, candidate = None, gold
        if operator != 'gold':
            candidates = _cycle_candidates(gold) if operator == 'import_cycle' else _ordinary_candidates(gold, operator)
            candidates.sort(key=lambda c: (c['path'], c['start_byte'], c['end_byte'], c['replacement']))
            if not candidates:
                slots.append(_slot(task, operator, 'NOT_APPLICABLE', 'NO_STATIC_APPLICABLE_LOCATION'))
                continue
            pick = int.from_bytes(hashlib.sha256(_canonical([seed, task.task_id, operator])).digest(), 'big') % len(candidates)
            selected = candidates[pick]
            raw = gold[selected['path']]
            candidate = gold | {selected['path']: raw[:selected['start_byte']] + selected['replacement'] + raw[selected['end_byte']:]}
            mutation = {k: v for k, v in selected.items() if k != 'replacement'} | {
                'candidate_index': pick, 'candidate_count': len(candidates),
                'replacement_sha256': _hash(selected['replacement']), 'selection': 'sha256_seed_task_operator_mod_count_v1'}
        try:
            patch = _net_patch(base, candidate)
            actual = _apply_memory(base, patch, _policy(task))
            if actual != candidate:
                raise ValueError('Net patch bytes differ')
            if operator != 'gold':
                ast.parse(candidate[mutation['path']])
        except (ValueError, OSError, SyntaxError, UnicodeError):
            slots.append(_slot(task, operator, 'ERROR', 'MUTATION_PATCH_UNSUPPORTED', mutation=mutation))
            continue
        ref = f'patches/{ordinal:03d}/{operator}.diff'
        data = patch.encode('utf-8')
        predicted = before | {p: _hash(raw) for p, raw in candidate.items()}
        slots.append(_slot(task, operator, 'CREATED', None, mutation=mutation, patch_ref=ref,
                           patch_hash=_hash(data), predicted_inventory=predicted))
        patches[ref] = data
    try:
        source_changed = _snapshot(task) != before
    except (ValueError, RuntimeError, OSError):
        source_changed = True
    if source_changed:
        return entry, [_slot(task, op, 'ERROR', 'SOURCE_CHANGED_DURING_BUILD') for op in ('gold', *OPERATORS)], {}
    return entry, slots, patches


def build_pool(tasks: Sequence[PoolTask], output_root: Path, *, seed: int = 0, provenance=None) -> dict:
    tasks = tuple(tasks)
    _validate_tasks(tasks, seed)
    provenance = json.loads(_canonical(provenance or {'kind': 'fixture' if all(t.fixture for t in tasks) else 'pinned_w10'}))
    _provenance(provenance, fixture=all(t.fixture for t in tasks))
    output_root = Path(output_root)
    resolved_output = output_root.resolve()
    for task in tasks:
        resolved_source = Path(task.source_repo).resolve()
        if resolved_output.is_relative_to(resolved_source) or resolved_source.is_relative_to(resolved_output):
            raise ValueError('Pool output and source repositories must not overlap')
    output_root.mkdir(parents=True, exist_ok=False)
    index = dict(schema=SCHEMA, seed=seed, expected_slots=len(tasks) * 6, tasks=[], slots=[], provenance=provenance)
    for ordinal, task in enumerate(tasks):
        entry, slots, patches = _build_task(task, ordinal, seed)
        index['tasks'].append(entry)
        index['slots'].extend(slots)
        for name, raw in patches.items():
            path = output_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    index['ready'] = not any(s['status'] == 'ERROR' for s in index['slots'])
    index['pool_hash'] = _hash(_canonical(index))
    (output_root / 'pool.json').write_bytes(_canonical(index) + b'\n')
    return load_pool(output_root, expected_pool_hash=index['pool_hash'])


def _valid_inventory(value):
    if not isinstance(value, dict):
        return False
    for name, hashed in value.items():
        safe_path(name)
        if not isinstance(hashed, str) or not re.fullmatch(r'(?:symlink:)?sha256:[0-9a-f]{64}', hashed):
            return False
    return True


def load_pool(root: Path, *, expected_pool_hash: str | None = None) -> dict:
    """Verify sealed bytes/references; external expected hash supplies the pin.

    Consistency hashes alone do not authenticate a producer or prove a mutant
    is behaviorally bad. Runtime source identity is checked by the evaluator.
    """
    root = Path(root)
    if root.is_symlink() or (hasattr(root, 'is_junction') and root.is_junction()):
        raise ValueError('Pool root must not be a link')
    root = root.resolve(strict=True)
    path = root / 'pool.json'
    if path.is_symlink():
        raise ValueError('Pool index must not be a link')
    raw = path.read_bytes()
    index = json.loads(raw)
    if raw != _canonical(index) + b'\n' or index.get('schema') != SCHEMA:
        raise ValueError('Pool index bytes/schema differ from frozen canonical data')
    actual = _hash(_canonical({k: v for k, v in index.items() if k != 'pool_hash'}))
    if index.get('pool_hash') != actual or (expected_pool_hash is not None and actual != expected_pool_hash):
        raise ValueError('Pool hash mismatch')
    if type(index.get('seed')) is not int or index['seed'] < 0:
        raise ValueError('Invalid pool seed')
    tasks, slots = index['tasks'], index['slots']
    ids = [t['task_id'] for t in tasks]
    if not tasks or len(set(ids)) != len(ids) or index['expected_slots'] != len(tasks) * 6 or len(slots) != index['expected_slots']:
        raise ValueError('Pool population or slot count mismatch')
    if any(type(t.get('fixture')) is not bool for t in tasks):
        raise ValueError('Fixture identity must be explicit boolean')
    fixture = all(t['fixture'] for t in tasks)
    if not fixture and (any(t['fixture'] for t in tasks) or tuple(ids) != W10_IDS or index['seed'] != 0):
        raise ValueError('Real pool population/seed differs from approved W10 inputs')
    _provenance(index['provenance'], fixture=fixture)
    if not fixture and index['provenance']['dataset_status'] != 'READY':
        reason = index['provenance']['dataset_status']
        if any(s['status'] != 'ERROR' or s['reason'] != reason for s in slots):
            raise ValueError('Unavailable/integrity-failed dataset must preserve every slot as ERROR')
    for ordinal, task in enumerate(tasks):
        source = task['source_inventory']
        if source is None and task['source_inventory_hash'] is not None:
            raise ValueError('Missing source cannot have an inventory hash')
        if source is not None and (not _valid_inventory(source) or task['source_inventory_hash'] != _hash(_canonical(source))):
            raise ValueError('Source inventory hash/schema mismatch')
        for number, operator in enumerate(('gold', *OPERATORS)):
            slot = slots[ordinal * 6 + number]
            if (slot['task_id'] != task['task_id'] or slot['slot_id'] != task['task_id'] + '::' + operator
                    or slot['operator'] != operator or slot['label'] != ('GOOD' if operator == 'gold' else 'BAD')
                    or slot['status'] not in ('CREATED', 'NOT_APPLICABLE', 'ERROR')):
                raise ValueError('Pool slot identity/label/status mismatch')
            if slot['status'] != 'CREATED':
                if not slot['reason'] or any(slot[k] is not None for k in ('patch_ref', 'patch_hash', 'predicted_inventory', 'predicted_inventory_hash')):
                    raise ValueError('Unavailable slot cannot contain a patch')
                continue
            if source is None:
                raise ValueError('Created patch requires an independently recorded source inventory')
            predicted = slot['predicted_inventory']
            if not _valid_inventory(predicted) or slot['predicted_inventory_hash'] != _hash(_canonical(predicted)):
                raise ValueError('Predicted inventory hash/schema mismatch')
            if (set(predicted) != set(source)
                    or any(predicted[p] != value for p, value in source.items() if p not in task['allowed_paths'])):
                raise ValueError('Prediction changes protected/non-production source')
            expected_ref = f'patches/{ordinal:03d}/{operator}.diff'
            if slot['patch_ref'] != expected_ref:
                raise ValueError('Patch reference differs from frozen slot')
            relative = safe_path(slot['patch_ref'])
            patch = root / relative
            if not patch.resolve(strict=True).is_relative_to(root) or any(p.is_symlink() for p in [patch, *patch.parents] if p != root.parent):
                raise ValueError('Patch reference is linked/outside pool')
            data = patch.read_bytes()
            if _hash(data) != slot['patch_hash']:
                raise ValueError('Patch hash mismatch')
            parsed = parse_unified_diff(data.decode('utf-8'), PatchPolicy(tuple(task['allowed_paths']), tuple(task['protected_paths']),
                max_bytes=16 * 1024 * 1024, max_files=1000, max_changed_lines=1_000_000))
            if set(parsed.files) != {p for p in predicted if predicted[p] != source[p]}:
                raise ValueError('Predicted changed files differ from actual patch paths')
    if index['ready'] is not (not any(s['status'] == 'ERROR' for s in slots)):
        raise ValueError('Pool readiness differs from actual ledger')
    return index


def approved_w10_population(repo_root: Path = ROOT):
    """The locked 11+14 W10 repair tasks, never the retrieval-tuning population."""
    configs, ids = [], []
    for name, expected in [('w10_dev_stage1.json', W10_IDS[:11]), ('w10_dev_stage2.json', W10_IDS[11:])]:
        path = Path(repo_root) / 'configs/m3' / name
        data = json.loads(path.read_bytes())
        source = data['source']
        if tuple(source['task_ids']) != expected or source['manifest']['sha256'] != W10_MANIFEST_HASH:
            raise ValueError('W10 population/manifest differs from approved 11+14 tasks')
        configs.append((path, data))
        ids.extend(source['task_ids'])
    if tuple(ids) != W10_IDS or len(set(ids)) != 25:
        raise ValueError('Exactly 25 distinct ordered W10 repair tasks required')
    return configs


def load_w10_tasks(parquet: Path, data_root: Path, *, repo_root: Path = ROOT):
    """Read the existing pinned gold boundary; never import a generator/verifier.

    Missing/integrity-failed data becomes ERROR slots. No fetch, repair run,
    target import, target test or mutation-based selection occurs here.
    """
    from vgar.evaluation.harness.gold_inputs import PARQUET_HASH, select_rows
    from vgar.evaluation.retrieval.pilot_manifest import DATASET_REVISION, validate_manifest

    configs = approved_w10_population(repo_root)
    first_path, first = configs[0]
    manifest_path = first_path.parent / first['source']['manifest']['path']
    manifest = json.loads(manifest_path.read_bytes())
    validate_manifest(manifest, expected_hash=W10_MANIFEST_HASH, expected_ids=None)
    if manifest.get('parquet_hash') != PARQUET_HASH:
        raise ValueError('Manifest Parquet pin differs')
    provenance = dict(kind='pinned_w10', dataset_revision=DATASET_REVISION, parquet_hash=PARQUET_HASH,
        manifest_hash=W10_MANIFEST_HASH, config_hashes={p.name: _hash(p.read_bytes()) for p, _ in configs},
        task_input_hashes={}, dataset_status='READY', dataset_actual_hash=None)
    selected, unavailable = {}, None
    try:
        raw = Path(parquet).read_bytes()
        provenance['dataset_actual_hash'] = _hash(raw)
        if _hash(raw) != PARQUET_HASH:
            unavailable = 'PARQUET_HASH_MISMATCH'
        else:
            import pyarrow as pa
            import pyarrow.parquet as pq
            rows = select_rows(pq.read_table(pa.BufferReader(raw)).to_pylist(), manifest, W10_IDS, approved_manifest=manifest_path)
            selected = {row['instance_id']: row for row in rows}
    except OSError:
        unavailable = 'PARQUET_NOT_READY'
    if unavailable:
        provenance['dataset_status'] = unavailable
    tasks, metadata = [], {row['instance_id']: row for row in manifest['tasks']}
    for config_path, config in configs:
        source = config['source']

        def resolve(value):
            return Path(data_root) / value[6:] if value.startswith('@data/') else config_path.parent / value

        for task_id in source['task_ids']:
            row, error = metadata[task_id], unavailable
            checkout = resolve(source['checkouts'].format(task_id=task_id))
            inputs = resolve(source['task_inputs']) / (task_id + '.json')
            allowed, protected = (), ('tests', 'pytest.ini')
            if not error:
                try:
                    raw = inputs.read_bytes()
                    provenance['task_input_hashes'][task_id] = _hash(raw)
                    task_inputs = json.loads(raw)
                    roots = tuple(safe_path(p) for p in task_inputs['source_roots'])
                    if not roots or len(set(roots)) != len(roots):
                        raise ValueError('Explicit unique source roots required')
                    files = base_inventory(checkout, row['base_commit'])
                    allowed = tuple(p for p in sorted(files) if _production(p) and any(p.startswith(r + '/') for r in roots))
                    protected = tuple(task_inputs['protected_paths'])
                    if not allowed:
                        error = 'SOURCE_POLICY_UNSUPPORTED'
                except OSError:
                    error = 'TASK_INPUT_OR_SOURCE_NOT_READY'
                except (ValueError, RuntimeError, KeyError):
                    error = 'TASK_INPUT_OR_SOURCE_INVALID'
            tasks.append(PoolTask(task_id, row['repo'], row['base_commit'], checkout,
                selected.get(task_id, {}).get('patch', ''), allowed, protected,
                fixture=False, unavailable_reason=error))
    return tasks, provenance
