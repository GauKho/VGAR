"""Offline T2 audit of GOOD slots; never executes target code or changes campaign evidence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import io
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vgar.evaluation.repair.mutant_pool import load_pool  # noqa: E402
from vgar.evaluation.repair.verifier_eval import (  # noqa: E402
    _read_vector, _validate_source_proof, _validated_policies, canonical_hash,
)
from vgar.repair.contracts import safe_path  # noqa: E402
from vgar.repair.evidence import digest  # noqa: E402
from vgar.repair.policy import VariantPolicy  # noqa: E402
from vgar.repair import static_diagnostics as diagnostics  # noqa: E402
from vgar.repair.static_diagnostics import (  # noqa: E402
    DiagnosticReport, _build_unique_line_map, _identity, _unchanged_declarations,
    build_line_map, compare_diagnostics, parse_tool_report, scope_digest,
)

REPORTED_TASKS = (
    'matplotlib__matplotlib-13989', 'matplotlib__matplotlib-20488', 'matplotlib__matplotlib-20676',
    'pydata__xarray-3993', 'pydata__xarray-4629', 'pylint-dev__pylint-4604',
    'sympy__sympy-11618', 'astropy__astropy-13453', 'astropy__astropy-13977', 'sphinx-doc__sphinx-11510',
)


def _guard(path):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Input/output path contains a link/reparse point')
    return path


class _Inputs:
    def __init__(self, pool, campaign):
        self.roots = {'pool': pool, 'campaign': campaign}
        self.files = {}

    def read(self, group, ref):
        path = _guard(self.roots[group] / safe_path(ref))
        if not path.resolve().is_relative_to(self.roots[group].resolve()):
            raise ValueError('Input reference escapes export')
        key = group + '/' + ref
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            self.files.setdefault(key, None)
            raise
        checksum = digest(raw)
        if key in self.files and self.files[key] != checksum:
            raise ValueError('Input changed during repeated read')
        self.files.setdefault(key, checksum)
        return raw

    def unchanged(self):
        for key, expected in self.files.items():
            group, ref = key.split('/', 1)
            try:
                actual = digest(_guard(self.roots[group] / ref).read_bytes())
            except FileNotFoundError:
                actual = None
            except (OSError, ValueError):
                return False
            if actual != expected:
                return False
        return True


def _campaign(pool, record):
    if (record.get('schema') != 'vgar-verifier-campaign-v1' or record.get('pool_hash') != pool['pool_hash']
            or record.get('campaign_hash') != canonical_hash({k: v for k, v in record.items() if k != 'campaign_hash'})
            or [r['slot_id'] for r in record['slots']] != [s['slot_id'] for s in pool['slots']]):
        raise ValueError('Campaign hash/population mismatch')
    _validated_policies({name: VariantPolicy.model_validate_json(json.dumps(value))
                         for name, value in record['variants'].items()})
    for slot, row in zip(pool['slots'], record['slots']):
        if any(row[k] != slot[k] for k in ('task_id', 'operator', 'label')):
            raise ValueError('Campaign slot identity mismatch')
        if slot['status'] != 'CREATED':
            if row['status'] != slot['status'] or row.get('vector_ref') or row.get('vector_file_hash'):
                raise ValueError('Unavailable slot cannot claim a vector')
        elif row['status'] == 'NOT_RUN':
            if row.get('vector_ref') or row.get('vector_file_hash'):
                raise ValueError('Pending slot cannot claim a vector')
        elif row['status'] not in ('EVALUATED', 'ERROR') or not row.get('vector_ref') or not row.get('vector_file_hash'):
            raise ValueError('Invalid terminal campaign state')


def _read_good(inputs, row, task, slot, record):
    ref = safe_path(row['vector_ref'])
    raw = json.loads(inputs.read('campaign', ref))
    parent = Path(ref).parent
    refs = []
    snapshot = raw.get('binding', {}).get('analysis_baseline')
    if snapshot:
        refs.append(snapshot['details_ref'])
    for half in ('baseline', 'post'):
        for check in raw.get(half, {}).get('compatibility', {}).values():
            if isinstance(check, dict) and check.get('details_ref'):
                refs.append(check['details_ref'])
    for relative in refs:
        inputs.read('campaign', (parent / safe_path(relative)).as_posix())
    vector = _read_vector(inputs.roots['campaign'], row)
    if vector['task_id'] != slot['task_id']:
        raise ValueError('Vector task differs from GOOD slot')
    if row['status'] == 'ERROR' and vector['integrity']['status'] != 'ERROR':
        raise ValueError('ERROR row cannot claim successful vector')
    binding = vector['binding'].get('pool', {})
    if any(binding.get(k) != v for k, v in dict(pool_hash=record['pool_hash'], slot_id=slot['slot_id'],
                                               patch_hash=slot['patch_hash']).items()):
        raise ValueError('Vector pool/slot/patch binding mismatch')
    _validate_source_proof(vector, task, slot, record, inputs.roots['campaign'] / parent)
    return vector


def _mypy(vector, half, root, scope):
    static = vector[half]['static']
    sources = static['source_snapshot']
    if not isinstance(sources, dict) or set(sources) != set(scope) or any(not isinstance(v, str) for v in sources.values()):
        raise ValueError('Missing/incomplete static source snapshot')
    command = static['mypy']
    report = DiagnosticReport.model_validate(command['report'])
    binding = static['binding']
    if (report.tool != 'mypy' or report.scope != tuple(scope) or report.scope_hash != scope_digest(scope)
            or binding['scope'] != scope or binding['scope_hash'] != report.scope_hash
            or binding['interpreter_ref'] != report.interpreter_ref
            or static['config_hashes']['mypy'] != report.config_hash):
        raise ValueError('Static report/context binding mismatch')
    # Old cwd is a string prefix only. Never resolve/read the old Linux/Windows source directory.
    parse_command = dict(command, cwd=str(root))
    parse_command['target_cwd'] = command.get('target_cwd') or command['cwd'].replace('\\', '/').rstrip('/')
    parsed = parse_tool_report('mypy', parse_command, report.tool_version)
    if parsed != report:
        raise ValueError('Saved mypy report differs from raw command output/context')
    if report.execution_status != 'COMPLETE':
        raise ValueError('Mypy tool incomplete/unavailable: ' + str(report.reason))
    if any(d.line > len(sources[d.path].splitlines()) for d in report.diagnostics):
        raise ValueError('Diagnostic source context missing')
    return report, sources


def _context(text, line):
    return [dict(line=n, text=value) for n, value in enumerate(text.splitlines(), 1) if abs(n - line) <= 2]


def _audit_vector(vector, root, scope):
    if vector['integrity']['status'] != 'PASS' or vector['apply']['status'] != 'PASS':
        raise ValueError('Vector integrity/apply not qualified for source comparison')
    before, old_sources = _mypy(vector, 'baseline', root, scope)
    after, new_sources = _mypy(vector, 'post', root, scope)
    old_map = _build_unique_line_map(old_sources, new_sources)
    new_map = build_line_map(old_sources, new_sources)
    old_delta = compare_diagnostics(before, after, old_map)
    new_delta = compare_diagnostics(before, after, new_map)
    if not old_delta.complete or not new_delta.complete:
        raise ValueError(new_delta.reason or old_delta.reason)
    introduced = Counter(d.model_dump_json() for d in new_delta.introduced)
    unmatched = Counter(d.model_dump_json() for d in new_delta.unmatched)
    old_introduced = Counter(d.model_dump_json() for d in old_delta.introduced)
    available = defaultdict(list)
    for d in before.diagnostics:
        mapped = new_map.get(d.path, {}).get(d.line)
        if mapped is not None:
            available[(_identity(d), mapped)].append(d)
    evidence = []
    for item in after.diagnostics:
        key = item.model_dump_json()
        mapping = dict(kind='UNMAPPED')
        if introduced[key]:
            introduced[key] -= 1
            category = 'UNRESOLVED' if unmatched[key] else 'INTRODUCED_BY_RULE'
            if unmatched[key]:
                unmatched[key] -= 1
        else:
            old = available[(_identity(item), item.line)].pop()
            category = 'MAPPING_RECOVERED' if old_introduced[key] else 'PERSISTING'
            if old_introduced[key]:
                old_introduced[key] -= 1
            mapping = dict(kind='UNIQUE_LINE' if old_map[item.path].get(old.line) == item.line
                           else 'UNCHANGED_DECLARATION', before_line=old.line, after_line=item.line,
                           before_context=_context(old_sources[item.path], old.line))
            if mapping['kind'] == 'UNCHANGED_DECLARATION':
                matches = [m for m in _unchanged_declarations(old_sources[item.path], new_sources[item.path])
                           if m['before'][0] <= old.line <= m['before'][1]
                           and m['after'][0] + old.line - m['before'][0] == item.line]
                mapping['declaration'] = max(matches, key=lambda m: len(m['scope']))
        evidence.append(dict(diagnostic=item.model_dump(mode='json'), category=category, mapping=mapping,
                             after_context=_context(new_sources[item.path], item.line)))
    classification = ('FALSE_REJECT_CONFIRMED' if old_delta.status == 'FAIL' and new_delta.status == 'PASS'
                      else 'NO_NEW_DIAGNOSTICS' if new_delta.status == 'PASS'
                      else 'UNRESOLVED' if new_delta.unmatched else 'INTRODUCED_BY_RULE')
    return dict(classification=classification, data_complete=True, reason=None,
                old_delta=old_delta.model_dump(mode='json'), new_delta=new_delta.model_dump(mode='json'),
                baseline_diagnostics=[dict(diagnostic=d.model_dump(mode='json'),
                                           context=_context(old_sources[d.path], d.line)) for d in before.diagnostics],
                diagnostics=evidence, tool_binding={k: getattr(before, k) for k in (
                    'tool_version', 'config_hash', 'scope_hash', 'interpreter_ref')})


def run_audit(pool_root, campaign_root, expected_pool_hash, output_root):
    pool_root, campaign_root, output = (_guard(Path(p)) for p in (pool_root, campaign_root, output_root))
    if output.exists():
        raise ValueError('Audit output already exists')
    if any(output == root or output.is_relative_to(root) or root.is_relative_to(output)
           for root in (pool_root, campaign_root)):
        raise ValueError('Audit output/input overlap')
    inputs = _Inputs(pool_root, campaign_root)
    pool, rows, errors = None, [], []
    try:
        index = json.loads(inputs.read('pool', 'pool.json'))
        for slot in index['slots']:
            if slot.get('patch_ref'):
                inputs.read('pool', slot['patch_ref'])
        pool = load_pool(pool_root, expected_pool_hash=expected_pool_hash)
        rows = [dict(slot_id=s['slot_id'], task_id=s['task_id'], pool_status=s['status'],
                     reported_problem_task=s['task_id'] in REPORTED_TASKS,
                     classification='MISSING_EVIDENCE', data_complete=False, reason='CAMPAIGN_NOT_READY')
                for s in pool['slots'] if s['label'] == 'GOOD']
        record = json.loads(inputs.read('campaign', 'campaign.json'))
        _campaign(pool, record)
        tasks = {t['task_id']: t for t in pool['tasks']}
        gold = [(s, r) for s, r in zip(pool['slots'], record['slots']) if s['label'] == 'GOOD']
        for item, (slot, row) in zip(rows, gold):
            if slot['status'] != 'CREATED' or row['status'] == 'NOT_RUN':
                item['reason'] = slot['reason'] or 'NOT_RUN'
                continue
            try:
                vector = _read_good(inputs, row, tasks[slot['task_id']], slot, record)
                item.update(_audit_vector(vector, campaign_root, tasks[slot['task_id']]['allowed_paths']))
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                item['reason'] = type(error).__name__ + ': ' + str(error)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(type(error).__name__ + ': ' + str(error))
    unchanged = inputs.unchanged()
    if not unchanged:
        errors.append('INPUT_CHANGED_DURING_AUDIT')
        for item in rows:
            item.update(classification='MISSING_EVIDENCE', data_complete=False, reason='INPUT_CHANGED_DURING_AUDIT')
    ready = bool(rows) and not errors and all(r['data_complete'] for r in rows)
    complete_ids = {r['task_id'] for r in rows if r['data_complete']}
    result = dict(schema='vgar-mypy-audit-v1', status='READY_FOR_REVIEW' if ready else 'PARTIAL',
                  synthetic=all(t['fixture'] for t in pool['tasks']) if pool else None,
                  expected_good_slots=len(rows), rows=rows, errors=errors, input_unchanged=unchanged,
                  unverified_reported_task_ids=[t for t in REPORTED_TASKS if t not in complete_ids],
                  matcher=dict(old='unique-lines-v1', new='unique-lines-and-unchanged-declarations-v2',
                               source_sha256=digest(Path(diagnostics.__file__).read_bytes()),
                               identity_version='m2-static-delta-v1'))
    output.mkdir(parents=True, exist_ok=False)
    inventory = dict(roots={k: str(v) for k, v in inputs.roots.items()}, expected_pool_hash=expected_pool_hash,
                     files=inputs.files, input_unchanged=unchanged,
                     audit_script_sha256=digest(Path(__file__).read_bytes()))
    (output / 'inputs.json').write_text(json.dumps(inventory, sort_keys=True, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'audit.json').write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(['task_id', 'slot_id', 'pool_status', 'classification', 'data_complete', 'old_status', 'new_status',
                     'introduced', 'persisting', 'resolved', 'unmatched', 'reason'])
    lines = ['# T2 mypy audit', '', 'Status: ' + result['status'], '',
             'Synthetic: ' + str(result['synthetic']), '',
             'FALSE_REJECT_CONFIRMED concerns the mypy delta only, not patch correctness or final ACCEPT. '
             'INTRODUCED_BY_RULE is not proof that a gold patch is behaviorally wrong. '
             'UNRESOLVED is not waived. READY_FOR_REVIEW does not mean group acceptance.', '',
             '| Task | Classification | Old mypy | New mypy | Reason |', '|---|---|---|---|---|']
    for item in rows:
        old, new = item.get('old_delta', {}), item.get('new_delta', {})
        writer.writerow([item['task_id'], item['slot_id'], item['pool_status'], item['classification'],
                         item['data_complete'], old.get('status'), new.get('status'),
                         *(len(new[k]) if k in new else '' for k in ('introduced', 'persisting', 'resolved', 'unmatched')),
                         item['reason']])
        reason = (item['reason'] or '').replace('|', '\\|').replace('\n', ' ')
        lines.append('| ' + ' | '.join([item['task_id'], item['classification'], old.get('status', 'N/A'),
                                        new.get('status', 'N/A'), reason]) + ' |')
    lines += ['', 'Unverified reported task IDs: ' + ', '.join(result['unverified_reported_task_ids']),
              '', 'Errors: ' + json.dumps(errors, ensure_ascii=False), '']
    (output / 'rows.csv').write_text(buffer.getvalue(), encoding='utf-8', newline='\n')
    (output / 'report.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    hashes = {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
    (output / 'artifact_hashes.json').write_text(json.dumps(hashes, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--expected-pool-hash', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_audit(args.pool, args.campaign, args.expected_pool_hash, args.output_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(dict(status=result['status'], good_slots=result['expected_good_slots'],
                          synthetic=result['synthetic']), sort_keys=True))
    return 0 if result['status'] == 'READY_FOR_REVIEW' else 2


if __name__ == '__main__':
    raise SystemExit(main())
