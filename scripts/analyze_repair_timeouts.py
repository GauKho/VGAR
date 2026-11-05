#!/usr/bin/env python3
"""Offline D15 analysis of exported batch records. Standard library only.

No model/profile/source loader, policy mutation, repair execution or directory search
outside the supplied exports. Synthetic records can demonstrate the tool, never close
experimental acceptance. See docs/m2_d15_timeout_analysis.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import stat
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = {'A0': 'bm25', 'A1': 'graph', 'A2': 'graph', 'A3': 'graph'}
TOKEN_FIELDS = ('input_tokens', 'output_tokens')
METRICS = (*TOKEN_FIELDS, 'generation_ms', 'model_load_ms', 'generation_stage_ms', 'wall_ms')
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path):
    """Check lexical ancestors *before* resolve; Windows junctions are reparse points."""
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError(f'Path traversal: {path}')
    for part in [*reversed(path.parents), path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'Symlink/reparse point rejected: {part}')
    return path.resolve()


def identifier(value):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value) or value in ('.', '..'):
        raise ValueError(f'Invalid identifier: {value!r}')
    return value


def read_json(path, files):
    path = safe_path(path)
    if not path.is_file():
        files[str(path)] = None
        raise ValueError(f'Missing record: {path}')
    raw = path.read_bytes()
    files[str(path)] = sha(raw)
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f'Invalid JSON: {path}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return value


def ledger_files(root):
    """Only the batch ledger; never recurse into exported source/workspaces."""
    folder = safe_path(root / 'attempts')
    paths = []
    if folder.exists():
        for pair in sorted(folder.iterdir()):
            pair = safe_path(pair)
            if not pair.is_dir():
                raise ValueError(f'Unexpected ledger entry: {pair}')
            for path in sorted(pair.iterdir()):
                path = safe_path(path)
                if not path.is_file() or not re.fullmatch(r'attempt-\d+\.json', path.name):
                    raise ValueError(f'Unexpected attempt entry: {path}')
                paths.append(path)
    return paths


def verify_inputs(inventory):
    for name, expected in inventory['files'].items():
        path = safe_path(name)
        actual = sha(path.read_bytes()) if path.is_file() else None
        if actual != expected:
            raise ValueError(f'Input changed/hash drift: {name}')
    for root, expected in inventory['ledgers'].items():
        if [str(p) for p in ledger_files(Path(root))] != expected:
            raise ValueError(f'Input ledger changed: {root}')
    for root, expected in inventory['engine_roots'].items():
        if engine_children(Path(root)) != expected:
            raise ValueError(f'Input engine directory changed: {root}')


def engine_children(root):
    root = safe_path(root)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError(f'Invalid engine output root: {root}')
    return [str(safe_path(p)) for p in sorted(root.iterdir())]


def populations(files):
    stages = []
    for i, size in ((1, 11), (2, 14)):
        obj = read_json(ROOT / f'configs/m3/w10_dev_stage{i}.json', files)
        tasks = obj['source']['task_ids']
        if not isinstance(tasks, list) or len(tasks) != size:
            raise ValueError('W10 population drift: expected 11+14 task IDs')
        stages.append([identifier(t) for t in tasks])
    if len(set(sum(stages, []))) != 25:
        raise ValueError('W10 population must contain 25 unique IDs')
    return stages


def number(value, *, integer=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if valid and (not integer or isinstance(value, int)):
        return value, 'MEASURED'
    return None, 'MISSING' if value is None else 'INVALID_NUMBER'


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(count=0, min=None, median=None, p95=None, max=None)
    index = (len(values) - 1) * 0.95
    low = int(index)
    frac = index - low
    p95 = values[low] * (1 - frac) + values[min(low + 1, len(values) - 1)] * frac
    middle = len(values) // 2
    median = values[middle] if len(values) % 2 else values[middle - 1] / 2 + values[middle] / 2
    return dict(count=len(values), min=values[0], median=median,
                p95=p95, max=values[-1])


def ranks(values):
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and values[ordered[j]] == values[ordered[i]]:
            j += 1
        for k in ordered[i:j]:
            result[k] = (i + j - 1) / 2 + 1
        i = j
    return result


def pearson(x, y):
    # Scaling before covariance avoids overflow for large, finite measurements.
    x = [v / max(max(map(abs, x)), 1) for v in x]
    y = [v / max(max(map(abs, y)), 1) for v in y]
    dx = [v - statistics.mean(x) for v in x]
    dy = [v - statistics.mean(y) for v in y]
    xx, yy = sum(v*v for v in dx), sum(v*v for v in dy)
    if xx == 0 or yy == 0:
        return None
    return max(-1.0, min(1.0, sum(a*b for a, b in zip(dx, dy)) / math.sqrt(xx*yy)))


def correlations(pairs):
    result = dict(count=len(pairs), pearson=None, spearman=None, reason=None)
    if len(pairs) < 3:
        result['reason'] = 'FEWER_THAN_THREE_PAIRS'
        return result
    x, y = map(list, zip(*pairs))
    result['pearson'] = pearson(x, y)
    result['spearman'] = pearson(ranks(x), ranks(y))
    if result['pearson'] is None or result['spearman'] is None:
        result['reason'] = 'ZERO_VARIANCE'
    return result


def group_stats(rows):
    completed = [r for r in rows if r['generation_completed']]
    pairs = [(r['input_tokens'], r['generation_ms']) for r in completed
             if r['input_tokens'] is not None and r['generation_ms'] is not None]
    return {
        'slots': len(rows), 'selection': dict(sorted(Counter(r['selection'] for r in rows).items())),
        'events': dict(sorted(Counter(e for r in rows for e in r['events']).items())),
        'completed_generations': len(completed),
        'metrics': {k: distribution([r[k] for r in
                    (completed if k == 'generation_ms' else rows)
                    if r[k] is not None and not (k == 'wall_ms' and r['wall_censored'])])
                    for k in METRICS},
        'censored_wall_ms': distribution([r['wall_ms'] for r in rows
                                        if r['wall_censored'] and r['wall_ms'] is not None]),
        'correlations': correlations(pairs),
    }


def binding(record):
    policy, model = record.get('policy') or {}, record.get('model') or {}
    if not isinstance(policy, dict) or not isinstance(model, dict):
        return None
    keys = ('prompt_version', 'input_cap', 'output_cap', 'reserved_margin',
            'generation_timeout', 'global_timeout', 'command_timeout')
    model_keys = ('model_id', 'revision', 'dtype', 'device_map')
    code = record.get('source_fingerprint')
    prompt = record.get('stages', {}).get('prompt') or {}
    if (any(policy.get(k) is None for k in keys)
            or any(model.get(k) is None for k in model_keys)
            or not isinstance(code, dict) or not code
            or not isinstance(prompt, dict) or not prompt.get('template_hash')
            or not prompt.get('tokenizer_label')):
        return None
    # Per-task prompt/source hashes must not be mistaken for shared configuration.
    value = {'policy': {k: policy[k] for k in keys},
             'model': model, 'code': code,
             'prompt': {k: prompt[k] for k in ('template_hash', 'tokenizer_label')}}
    try:
        return sha(encoded(value))
    except (TypeError, ValueError):
        return None


def empty_row(cohort, exp_id, task, variant, selection='INPUT_MISSING'):
    return dict(cohort=cohort, experiment_id=exp_id, task_id=task, variant=variant,
                arm=ARMS[variant], attempt=None, run_id=None, selection=selection,
                raw_status=None, raw_reason=None, raw_failure=None, evidence_refs=[],
                raw_failure_invalid=None, metric_refs={},
                events=[], generation_completed=False, wall_censored=False,
                truncated=None, binding=None, synthetic=False, issues=[],
                availability={k: 'NOT_AVAILABLE' for k in METRICS},
                **dict.fromkeys(METRICS))


def command_timeouts(stages):
    """Only an explicit command object can establish a command timeout."""
    refs = []

    def walk(value, ref):
        if isinstance(value, dict):
            if value.get('timed_out') is True and any(k in value for k in ('argv', 'command', 'cmd')):
                refs.append(ref)
            for key, item in sorted(value.items()):
                walk(item, f'{ref}/{key}')
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, f'{ref}/{i}')
    for key, value in sorted(stages.items()):
        if key != 'generation':
            walk(value, f'/stages/{key}')
    return refs


def measurements(row, entry, record, ref):
    stages = record.get('stages') or {}
    if not isinstance(stages, dict):
        raise ValueError('Invalid stages')
    generation = stages.get('generation') or {}
    if not isinstance(generation, dict):
        raise ValueError('Invalid generation stage')
    failure = record.get('failure') or entry.get('failure')
    try:
        encoded(failure)
        if failure is not None and (not isinstance(failure, dict) or any(
                failure.get(k) is not None and not isinstance(failure[k], str)
                for k in ('code', 'stage', 'cause', 'evidence_ref'))):
            raise ValueError('Malformed failure fields')
    except (TypeError, ValueError) as exc:
        row['raw_failure_invalid'] = json.dumps(failure, sort_keys=True, ensure_ascii=False)
        raise ValueError('Malformed/nonfinite failure metadata; see raw_failure_invalid') from exc
    row.update(raw_status=entry.get('status'), raw_reason=entry.get('reason'),
               raw_failure=failure,
               binding=binding(record), synthetic=record.get('mode') != 'real')
    reasons = {entry.get('reason'), record.get('reason')}
    if isinstance(failure, dict):
        reasons.add(failure.get('code'))
    gen_timeout = 'GENERATION_TIMEOUT' in reasons or generation.get('timed_out') is True
    global_timeout = ('RUN_TIMEOUT' in reasons or entry.get('timed_out') is True
                      or 'Global run deadline exhausted' in str(record.get('detail', '')))
    events = []
    if gen_timeout:
        events.append('GENERATION_TIMEOUT')
    if global_timeout:
        events.append('RUN_TIMEOUT')
    commands = command_timeouts(stages)
    if commands:
        events.append('COMMAND_TIMEOUT')
        row['evidence_refs'].extend(f'{ref}#{p}' for p in commands)
    if generation.get('truncated') is True:
        events.append('OUTPUT_CAP')
    infra = {'RUNNER_INFRA_ERROR', 'MCP_TRANSPORT_ERROR', 'TOOL_TIMEOUT', 'DOCKER_ERROR'}
    model_errors = {'GENERATION_ERROR', 'MODEL_ERROR'}
    if reasons & infra:
        events.append('INFRASTRUCTURE_ERROR')
    if reasons & model_errors:
        events.append('MODEL_ERROR')
    elif generation.get('status') == 'ERROR' and not gen_timeout and not global_timeout:
        if not reasons & infra:
            events.append('MODEL_ERROR')
    row.update(events=events, wall_censored=global_timeout,
               truncated=generation.get('truncated') if type(generation.get('truncated')) is bool else None,
               generation_completed=(generation.get('status') == 'PASS' and not gen_timeout
                                     and generation.get('complete', True) is True))
    for key in METRICS:
        if key == 'wall_ms':
            value = entry.get('wall_ms')
            if value is None:
                value = record.get('duration_ms')
        elif key == 'generation_stage_ms':
            value = generation.get('duration_ms')
        else:
            value = generation.get(key)
        row[key], row['availability'][key] = number(value, integer=key in TOKEN_FIELDS)
        if row['availability'][key] == 'MEASURED':
            pointer = ('/duration_ms' if key == 'wall_ms' else
                       '/stages/generation/duration_ms' if key == 'generation_stage_ms'
                       else f'/stages/generation/{key}')
            row['metric_refs'][key] = f'{ref}#{pointer}'
    prompt = stages.get('prompt') or {}
    if isinstance(prompt, dict):
        tokens, available = number(prompt.get('input_tokens'), integer=True)
        if available == 'MEASURED':
            if row['availability']['input_tokens'] == 'MISSING':
                row['input_tokens'], row['availability']['input_tokens'] = tokens, available
                row['metric_refs']['input_tokens'] = f'{ref}#/stages/prompt/input_tokens'
            elif row['input_tokens'] is not None and row['input_tokens'] != tokens:
                row['input_tokens'] = None
                row['availability']['input_tokens'] = 'CONFLICT'
                row['issues'].append('Prompt/generation input-token measurements disagree')
                row['metric_refs']['input_tokens'] = [f'{ref}#/stages/prompt/input_tokens',
                                                       f'{ref}#/stages/generation/input_tokens']
    if not row['generation_completed']:
        row['availability']['generation_ms'] = (
            'CENSORED' if gen_timeout and row['generation_ms'] is not None else 'NOT_COMPLETED')


def linked_record(root, entry, inventory):
    link = entry.get('engine_run_dir')
    expected_root = ['engine', f"{entry['task_id']}__{entry['variant_id']}",
                     f"attempt-{entry['attempt']}"]
    output_link = entry.get('engine_output_root')
    if output_link is not None:
        if not isinstance(output_link, str):
            raise ValueError('Invalid engine_output_root')
        root_parts = output_link.replace('\\', '/').rstrip('/').split('/')
        if '..' in root_parts:
            raise ValueError('Path traversal in engine_output_root')
        if root_parts[-3:] != expected_root:
            raise ValueError('Engine output root binding mismatch')
    if not link and output_link:
        # Producer-supported interruption: ledger never received engine_run_dir.
        # Read only immediate run directories of the exact local attempt root.
        local_root = root.joinpath(*expected_root)
        children = engine_children(local_root)
        inventory['engine_roots'][str(local_root)] = children
        candidates = [Path(p) for p in children
                      if safe_path(Path(p) / 'run_record.json').is_file()]
        if len(candidates) > 1:
            raise ValueError('Ambiguous interrupted engine records')
        if candidates:
            link = '/'.join([*expected_root, identifier(candidates[0].name)])
    if not link:
        return None, None
    if not isinstance(link, str):
        raise ValueError('Invalid engine_run_dir')
    parts = link.replace('\\', '/').rstrip('/').split('/')
    if '..' in parts:
        raise ValueError('Path traversal in engine_run_dir')
    run_id = identifier(parts[-1])
    expected = [*expected_root, run_id]
    if parts[-4:] != expected:
        raise ValueError('Engine path binding mismatch')
    # Ignore the old machine's prefix; read only the exact relative export path.
    path = root.joinpath(*expected, 'run_record.json')
    record = read_json(path, inventory['files'])
    if (record.get('kind') != 'repair' or record.get('run_id') != run_id
            or record.get('task_id') != entry['task_id']):
        raise ValueError('Engine task/run/kind binding mismatch')
    exp = record.get('experiment')
    if not isinstance(exp, dict) or any(exp.get(k) != entry[k] for k in ('variant_id', 'arm')):
        raise ValueError('Engine variant/arm binding mismatch')
    if 'experiment_id' in exp and exp['experiment_id'] != entry['experiment_id']:
        raise ValueError('Engine experiment binding mismatch')
    if entry['state'] == 'TERMINAL' and record.get('complete') is not True:
        raise ValueError('Terminal linked engine is incomplete')
    if entry['state'] == 'TERMINAL' and (
            entry.get('engine_complete') is not True
            or record.get('status') != entry.get('status')
            or record.get('reason') != entry.get('reason')):
        raise ValueError('Terminal ledger/engine status/reason/completion mismatch')
    if 'attempt' in record and record['attempt'] != entry['attempt']:
        raise ValueError('Engine attempt binding mismatch')
    if entry.get('run_id') is not None and entry['run_id'] != run_id:
        raise ValueError('Ledger run_id binding mismatch')
    return record, f'{root.as_posix()}/{path.relative_to(root).as_posix()}'


def select(root, exp_id, task, variant, entries, inventory, cohort):
    row = empty_row(cohort, exp_id, task, variant)
    audit = dict(cohort=cohort, experiment_id=exp_id, task_id=task, variant=variant,
                 attempts=[], selected=None, previous_terminal=None, issues=[])
    if not entries:
        return row, audit
    try:
        seen, runs, ledger_refs = {}, {}, {}
        for path in entries:
            item = read_json(path, inventory['files'])
            n = item.get('attempt')
            if (type(n) is not int or n < 1 or n in seen or path.name != f'attempt-{n}.json'
                    or any(item.get(k) != v for k, v in
                           [('experiment_id', exp_id), ('task_id', task),
                            ('variant_id', variant), ('arm', ARMS[variant])])
                    or item.get('state') not in ('RESERVED', 'INTERRUPTED', 'TERMINAL')):
                raise ValueError('Duplicate or invalid attempt/binding')
            if (item.get('reason') is not None and not isinstance(item['reason'], str)
                    or item['state'] == 'TERMINAL' and item.get('status') not in ('PASS', 'FAIL', 'ERROR')):
                raise ValueError('Malformed terminal status/reason')
            record, ref = linked_record(root, item, inventory)
            if record:
                if record['run_id'] in runs:
                    raise ValueError('Duplicate run_id')
                runs[record['run_id']] = n
            seen[n] = (item, record, ref)
            ledger_refs[n] = str(path)
            audit['attempts'].append(dict(attempt=n, state=item['state'],
                                          parent_attempt=item.get('parent_attempt'),
                                          run_id=record.get('run_id') if record else None,
                                          supersedes_run_id=record.get('supersedes_run_id') if record else None,
                                          ledger_ref=str(path), engine_ref=ref))
        for n, (item, record, _) in seen.items():
            parent = item.get('parent_attempt')
            if parent is not None and (type(parent) is not int or parent not in seen or parent >= n):
                raise ValueError('Invalid/cyclic parent_attempt')
            supersedes = record.get('supersedes_run_id') if record else None
            if supersedes is not None:
                if supersedes not in runs or runs[supersedes] >= n:
                    raise ValueError('Invalid/cyclic supersedes_run_id')
                if parent is not None and parent != runs[supersedes]:
                    raise ValueError('parent_attempt/supersedes_run_id mismatch')
        latest = max(seen)
        item, record, ref = seen[latest]
        audit['attempts'].sort(key=lambda a: a['attempt'])
        terminals = [n for n, (a, _, _) in seen.items() if a['state'] == 'TERMINAL']
        audit['previous_terminal'] = max(terminals) if terminals else None
        row.update(attempt=latest, raw_status=item.get('status'), raw_reason=item.get('reason'))
        if item['state'] != 'TERMINAL':
            row['selection'] = 'RERUN_PENDING'
        elif record is None:
            if item.get('source') != 'runner' or not item.get('reason'):
                raise ValueError('Terminal engine record missing')
            row['selection'] = 'RUNNER_TERMINAL'
            row['evidence_refs'] = [ledger_refs[latest]]
            if item['reason'] in ('RUNNER_INFRA_ERROR', 'MCP_TRANSPORT_ERROR', 'TOOL_TIMEOUT'):
                row['events'] = ['INFRASTRUCTURE_ERROR']
            row['wall_ms'], row['availability']['wall_ms'] = number(item.get('wall_ms'))
        else:
            row.update(selection='SELECTED', run_id=record['run_id'], evidence_refs=[ref])
            measurements(row, item, record, ref)
            if row['metric_refs'].get('wall_ms'):
                if item.get('wall_ms') is not None:
                    row['metric_refs']['wall_ms'] = f'{ledger_refs[latest]}#/wall_ms'
            audit['selected'] = latest
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        if any(x in str(exc).lower() for x in ('traversal', 'symlink', 'reparse')):
            raise
        row['selection'] = 'INVALID'
        row['issues'].append(str(exc))
        audit['issues'].append(str(exc))
    return row, audit


def analyze(*, w10=(), w12=()):
    inventory = {'files': {}, 'ledgers': {}, 'engine_roots': {},
                 'parameters': {'w10': [], 'w12': []}}
    stages = populations(inventory['files'])
    all_tasks = sum(stages, [])
    rows, audits, experiments, issues, roots = [], [], [], [], []
    supplied = {'w10': list(w10), 'w12': list(w12)}
    seen_ids, supplied_tasks = set(), {'w10': set(), 'w12': set()}
    for cohort in ('w10', 'w12'):
        for given in sorted(supplied[cohort], key=str):
            root = safe_path(given)
            if not root.is_dir() or root in roots:
                raise ValueError('Experiment directory missing or supplied twice')
            roots.append(root)
            inventory['parameters'][cohort].append(str(root))
            paths = ledger_files(root)
            inventory['ledgers'][str(root)] = [str(p) for p in paths]
            try:
                config = read_json(root / 'experiment.json', inventory['files'])
                exp_id = identifier(config.get('experiment_id'))
                if exp_id in seen_ids:
                    raise ValueError('Duplicate experiment_id')
                seen_ids.add(exp_id)
                tasks = config.get('source', {}).get('task_ids')
                if (config.get('schema') != 'vgar-m3-experiment-v1' or not isinstance(tasks, list)
                        or not tasks or len(set(tasks)) != len(tasks)
                        or any(t not in all_tasks for t in tasks)):
                    raise ValueError('Invalid experiment schema/population')
                if cohort == 'w10' and tasks not in stages:
                    raise ValueError('W10 experiment must keep exact stage1/stage2 population')
                variants = {}
                for value in config.get('variants', []):
                    variant = Path(value['path'].replace('\\', '/')).stem
                    if variant not in ARMS or variant in variants or value['arm'] != ARMS[variant]:
                        raise ValueError('Invalid variant/arm declaration')
                    variants[variant] = value['arm']
                expected = {'A0', 'A1', 'A2'} if cohort == 'w10' else {'A3'}
                if set(variants) != expected:
                    raise ValueError('Unexpected cohort variant population')
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                issues.append(f'{root}: {exc}')
                continue
            if supplied_tasks[cohort].intersection(tasks):
                issues.append(f'{root}: overlapping task population between {cohort} exports')
            supplied_tasks[cohort].update(tasks)
            synthetic = config.get('generation') != 'real' or config.get('source', {}).get('type') != 'swebench'
            experiments.append(dict(cohort=cohort, experiment_id=exp_id, root=str(root),
                                    tasks=len(tasks), synthetic=synthetic))
            grouped = defaultdict(list)
            for path in paths:
                pair = path.parent.name.rsplit('__', 1)
                if len(pair) != 2 or pair[0] not in tasks or pair[1] not in variants:
                    issues.append(f'Unexpected ledger task/variant: {path}')
                    # Seal malformed/unexpected ledger bytes as well.
                    try:
                        read_json(path, inventory['files'])
                    except ValueError:
                        pass
                    continue
                grouped[tuple(pair)].append(path)
            for task in tasks:
                for variant in sorted(variants):
                    row, audit = select(root, exp_id, task, variant, grouped[(task, variant)],
                                        inventory, cohort)
                    row['synthetic'] = row['synthetic'] or synthetic
                    rows.append(row)
                    audits.append(audit)
    for cohort in ('w10', 'w12'):
        variants = ('A0', 'A1', 'A2') if cohort == 'w10' else ('A3',)
        for task in all_tasks:
            if task not in supplied_tasks[cohort]:
                rows.extend(empty_row(cohort, 'MISSING_EXPORT', task, v) for v in variants)
    rows.sort(key=lambda r: (r['cohort'], r['experiment_id'], r['task_id'], r['variant']))
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r['cohort'], r['experiment_id'], r['variant'], r['binding'] or 'UNKNOWN')].append(r)
    groups = [dict(cohort=c, experiment_id=e, variant=v, binding=b, **group_stats(rs))
              for (c, e, v, b), rs in sorted(grouped.items())]
    warnings, combined = [], []
    for c, e, v in sorted({key[:3] for key in grouped}):
        bs = {key[3] for key in grouped if key[:3] == (c, e, v)}
        if 'UNKNOWN' in bs or len(bs) > 1:
            warnings.append(f'{c}/{e}/{v}: unknown/mixed binding; split summary groups')
    for v in ('A0', 'A1', 'A2'):
        rs = [r for r in rows if r['cohort'] == 'w10' and r['variant'] == v]
        measured = [r for r in rs if r['selection'] == 'SELECTED']
        bindings = {r['binding'] for r in measured}
        if (len({r['task_id'] for r in measured}) == 25 and len(measured) == 25
                and None not in bindings and len(bindings) == 1):
            combined.append(dict(variant=v, binding=next(iter(bindings)), **group_stats(rs)))
        else:
            warnings.append(f'{v}: W10 stages not pooled: missing, unknown or mixed binding/coverage')
    coverage = {}
    for c in ('w10', 'w12'):
        rs = [r for r in rows if r['cohort'] == c]
        coverage[c] = dict(expected=75 if c == 'w10' else 25, rows=len(rs),
                           selected=sum(r['selection'] == 'SELECTED' for r in rs),
                           unique_resolved=len({(r['task_id'], r['variant']) for r in rs
                                                if r['selection'] in ('SELECTED', 'RUNNER_TERMINAL')}),
                           selections=dict(sorted(Counter(r['selection'] for r in rs).items())))
    synthetic = any(r['synthetic'] for r in rows)
    quality = []
    for r in rows:
        problems = []
        if r['selection'] == 'SELECTED':
            if r['binding'] is None:
                problems.append('UNKNOWN_BINDING')
            problems += [f'{k}:{v}' for k, v in r['availability'].items()
                         if v in ('INVALID_NUMBER', 'CONFLICT')]
            if r['generation_completed']:
                problems += [f'{k}:MISSING_COMPLETED_MEASUREMENT' for k in ('input_tokens', 'generation_ms')
                             if r[k] is None]
            problems += r['issues']
        if problems:
            quality.append(dict(cohort=r['cohort'], experiment_id=r['experiment_id'],
                                task_id=r['task_id'], variant=r['variant'], reasons=problems))
    complete = (not issues and not quality and not synthetic and all(
        r['selection'] in ('SELECTED', 'RUNNER_TERMINAL') for r in rows)
        and coverage['w10']['unique_resolved'] == 75 and coverage['w12']['unique_resolved'] == 25)
    state = 'WAITING_DATA' if not roots else 'READY_FOR_REVIEW' if complete else 'PARTIAL'
    summary = dict(state=state, synthetic=synthetic, expected_slots={'w10': 75, 'w12': 25},
                   coverage=coverage, groups=groups, combined_w10=combined,
                   warnings=warnings, issues=issues, data_quality_issues=quality, experiments=experiments,
                   recommendation=dict(current_seconds={'generation': 900, 'global': 1800},
                                       m3_candidate_seconds={'generation': 1500, 'global': 2700},
                                       selected_seconds=None,
                                       reason='Await real-data analysis and group review; no configuration changed.'))
    return dict(rows=rows, selection_audit=audits, summary=summary, inputs=inventory,
                exit_code=0 if state == 'READY_FOR_REVIEW' else 2)


def report(summary):
    lines = ['# D15 — phân tích timeout offline', '', f"Trạng thái dữ liệu: **{summary['state']}**.",
             '', 'SYNTHETIC / FIXTURE: không phải kết quả W10/A3 thật.' if summary['synthetic']
             else 'Chỉ phân tích record batch được export; không chạy campaign.', '',
             '## Coverage', '', '| Cohort | Expected slots | Rows | Selected engine | Resolved unique |',
             '|---|---:|---:|---:|---:|']
    for c, data in summary['coverage'].items():
        lines.append(f"| {c} | {data['expected']} | {data['rows']} | {data['selected']} | {data['unique_resolved']} |")
    lines += ['', '## Thống kê theo experiment/variant', '',
              '| Cohort / experiment / variant | Completed n | Generation ms min / median / p95 / max | Paired n | Pearson | Spearman |',
              '|---|---:|---|---:|---:|---:|']
    for g in summary['groups']:
        d, corr = g['metrics']['generation_ms'], g['correlations']
        values = ' / '.join(str(d[k]) if d[k] is not None else 'N/A'
                            for k in ('min', 'median', 'p95', 'max'))
        label = f"{g['cohort']} / {g['experiment_id']} / {g['variant']} / {g['binding']}"
        lines.append(f"| {label} | {d['count']} | {values} | {corr['count']} | {corr['pearson']} | {corr['spearman']} |")
    lines += ['', '## Cách diễn giải và giới hạn', '',
              '- Unknown khác measured zero. availability và evidence nằm trong rows.csv.',
              '- Generation timeout không thuộc phân phối thời gian hoàn tất. RUN_TIMEOUT kiểm duyệt wall time;',
              '  generation đã hoàn tất trước global timeout vẫn được dùng. Output cap được đếm riêng.',
              '- p95 nội suy tuyến tính tại (n−1)×0,95. Spearman dùng average rank cho ties.',
              '- Tương quan cần ≥3 cặp hợp lệ và phương sai khác 0; N/A không phải 0.',
              '- Không suy quan hệ nhân quả. Không gộp stage có binding unknown/mixed hoặc thiếu coverage.',
              '- Count, phân phối từng metric và event counts đầy đủ: summary.json.',
              '', '## Timeout và bàn giao', '',
              'Hiện hành: generation **900s**, global **1800s**. Ứng viên M3: **1500s/2700s**, chưa áp dụng.',
              'Đề xuất cuối: **chưa chọn** — cần raw W10/A3 và nhóm review. READY_FOR_REVIEW chỉ nói về',
              'readiness dữ liệu, không tự nghiệm thu D15. Không thay đổi timeout/config.', '',
              '## Cảnh báo', '']
    lines += [f'- {s}' for s in [*summary['warnings'], *summary['issues']]] or ['- Không có.']
    return '\n'.join(lines) + '\n'


def run_analysis(*, w10=(), w12=(), output_root):
    w10, w12 = list(w10), list(w12)
    out = safe_path(output_root)
    for root in [*w10, *w12]:
        root = safe_path(root)
        if out == root or out in root.parents or root in out.parents:
            raise ValueError('Output/input overlap rejected')
    if out.exists():
        raise ValueError('Output directory must be new')
    result = analyze(w10=w10, w12=w12)
    verify_inputs(result['inputs'])
    out.mkdir(parents=True)
    for name, data in [('inputs.json', result['inputs']),
                       ('selection_audit.json', result['selection_audit']),
                       ('summary.json', result['summary'])]:
        (out / name).write_bytes(encoded(data))
    with (out / 'rows.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result['rows'][0]), lineterminator='\n')
        writer.writeheader()
        for row in result['rows']:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True, allow_nan=False)
                             if isinstance(v, (dict, list)) else v for k, v in row.items()})
    (out / 'report.md').write_bytes(report(result['summary']).encode('utf-8'))
    verify_inputs(result['inputs'])
    hashes = {p.name: sha(p.read_bytes()) for p in sorted(out.iterdir())}
    (out / 'artifact_hashes.json').write_bytes(encoded(hashes))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--w10-experiment', action='append', default=[], type=Path)
    parser.add_argument('--w12-experiment', action='append', default=[], type=Path)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_analysis(w10=args.w10_experiment, w12=args.w12_experiment,
                              output_root=args.output_root)
    except (ValueError, OSError) as exc:
        print(f'D15 input/output error: {exc}', file=sys.stderr)
        return 2
    print(result['summary']['state'])
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
