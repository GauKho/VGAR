"""Read-only grouped summaries; never rerun inference or mix fake/real/prompt versions."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('results/repair'))
    parser.add_argument('--mode', choices=('fake', 'real'), required=True)
    parser.add_argument('--task-id')
    parser.add_argument('--prompt-version')
    args = parser.parse_args()
    groups = defaultdict(list)
    for path in sorted(args.root.glob('*/run_record.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        version = record.get('policy', {}).get('prompt_version', 'unqualified-config')
        if record.get('mode') != args.mode or (args.task_id and record.get('task_id') != args.task_id):
            continue
        if args.prompt_version and version != args.prompt_version:
            continue
        groups[version].append((path, record))
    output = {}
    for version, entries in groups.items():
        output[version] = {'attempts': len(entries), 'statuses': dict(Counter(r['status'] for _, r in entries)),
            'complete': sum(bool(r['complete']) for _, r in entries),
            'valid_diff': sum(r.get('stages', {}).get('parse_patch', {}).get('status') == 'PASS' for _, r in entries),
            'runs': [{'task_id':r.get('task_id'), 'status':r['status'], 'duration_ms':r.get('duration_ms'),
                      'record':str(p.resolve())} for p,r in entries]}
    print(json.dumps({'mode':args.mode, 'scope':'small-fixture prototype, not benchmark', 'groups':output}, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

