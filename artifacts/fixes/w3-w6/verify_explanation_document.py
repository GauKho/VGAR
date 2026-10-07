"""Read-only structural/evidence checks of the Vietnamese handoff document."""
import ast
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, utc_now, write_json

DOC = ROOT / 'docs/GIAI_THICH_VGAR_TRUOC_SAU_FIX_TUAN_3_6_VA_CACH_KIEM_THU.md'


def main():
    directory, record = new_run(ROOT / 'artifacts/fixes/w3-w6/explanation-doc-checks', 'explanation-structure-and-saved-evidence')
    started = time.perf_counter()
    original = DOC.read_bytes()
    content = original.decode('utf-8')
    checks = []

    def check(name, valid, detail):
        checks.append(dict(name=name, passed=bool(valid), detail=detail))

    headings = re.findall(r'^## (\d+)\.', content, flags=re.M)
    check('13 requested sections', headings == [str(n) for n in range(1, 14)], headings)
    check('no unfinished placeholders', not re.search(r'CONTINUES|TODO|TBD', content), 'Not a content-quality proof')
    check('all audit identifiers explained', all(re.search(rf'\| {tag}\b', content) for tag in
          [f'F{n:02}' for n in range(1, 13)] + [f'R{n:02}' for n in range(1, 7)]), 'F01-F12 / R01-R06')
    check('unfinished before completed', content.index('### 6.1.') < content.index('### 6.2.'), 'Status table order')
    for number, code in enumerate(re.findall(r'& \$python(?: -B)? -c "([^"\n]+)"', content), 1):
        try:
            ast.parse(code)
            valid, detail = True, 'Python inline source parses; not executed'
        except SyntaxError as exc:
            valid, detail = False, str(exc)
        check(f'inline Python {number}', valid, detail)
    referenced = sorted(set(re.findall(r'`((?:artifacts|results)/[^`\n]+\.json)`', content)))
    for relative in referenced:
        if any(marker in relative for marker in ('<', '>', '*', '{', '}')):
            continue
        path = ROOT / relative
        check('saved evidence exists', path.is_file(), relative)
        if path.is_file():
            try:
                json.loads(path.read_text(encoding='utf-8'))
                valid = True
            except (UnicodeError, json.JSONDecodeError):
                valid = False
            check('saved evidence parses', valid, relative)
    full = json.loads((ROOT / 'artifacts/fixes/w3-w6/host-source-binding/full-suite/20261007T022934073929Z-4a8c5e505aa4487993dca0fd82a2607f.json').read_text(encoding='utf-8'))
    check('historical suite claim', full['test_result']['case_counts'] == dict(passed=359, failed=0, error=0, skipped=4)
          and full['test_result']['exit_code'] == 0 and full['source_hash_before'] == full['source_hash_after'],
          full['test_result']['case_counts'])
    graph = json.loads((ROOT / 'results/retrieval/20261007T014445273889Z-664d06a6c1c0/result.json').read_text(encoding='utf-8'))
    counts = {status: sum(row['status'] == status for row in graph['task_results']) for status in ('SUCCEEDED', 'FAILED', 'ERROR', 'NOT_RUN')}
    check('historical dev25 claim', counts == dict(SUCCEEDED=19, FAILED=3, ERROR=3, NOT_RUN=0)
          and graph['complete'] and not graph['config']['graph']['use_jedi'], counts)
    comparison = json.loads((ROOT / 'results/retrieval/20261007T022806825449Z-7e61dc92fe7b/result.json').read_text(encoding='utf-8'))
    check('historical comparison claim', comparison['paired_tasks'] == 19
          and comparison['status'] == 'COMPARED_PARTIAL' and comparison['exit_code'] == 1,
          dict(paired_tasks=comparison['paired_tasks'], status=comparison['status'], exit_code=comparison['exit_code']))
    current = json.loads((ROOT / 'results/retrieval/20261007T114731162059Z-f27e07ec6a8b/result.json').read_text(encoding='utf-8'))
    paired = json.loads((ROOT / 'results/retrieval/20261007T122342844612Z-12c751a0b3f6/result.json').read_text(encoding='utf-8'))
    current_suite = json.loads((ROOT / 'artifacts/fixes/w3-w6/reopened/snapshot-full-suite/20261007T112734572936Z-da791aaa6072446ca8b9184e92a80a7d.json').read_text(encoding='utf-8'))
    check('current suite claim', current_suite['status'] == 'PASS'
          and current_suite['test_result']['case_counts'] == dict(passed=365, failed=0, error=0, skipped=4)
          and current_suite['source_hash_before'] == current_suite['source_hash_after'],
          current_suite['test_result']['case_counts'])
    check('current comparison remains partial', paired['paired_tasks'] == 23
          and paired['status'] == 'COMPARED_PARTIAL' and paired['exit_code'] == 1
          and current['complete'] and len(current['task_results']) == 25,
          '23 pairs, 25 attempts, not 25 completed pairs')
    journal = content.split('#### Nhật ký run paired25 mới (không trộn run cũ)', 1)[1].split('<!-- PAIRED25_REOPENED_ROWS -->', 1)[0]
    for row in current['task_results']:
        matches = re.findall(rf'^\| {re.escape(row["instance_id"])} \| ([A-Z_]+) \|', journal, flags=re.M)
        check('task journal matches evidence', matches == [row['status']], row['instance_id'])
    check('current unfinished table', 'Django13212,13344' in content
          and 'Chưa đảm bảo; warm verified-cache đã PASS' in content,
          'Windows failures and cold-start limits remain explicit')
    check('document unchanged during validation', original == DOC.read_bytes(), sha256(original))
    failed = [item for item in checks if not item['passed']]
    record.update(status='PASS' if not failed else 'FAIL', exit_code=0 if not failed else 1,
                  complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                  document=str(DOC), document_hash=sha256(original), checks=checks, failures=failed,
                  limitations='Read-only saved evidence/structure/syntax; no test/benchmark/model command executed or independently reproduced.')
    write_json(directory / 'result.json', record)
    print(json.dumps(dict(evidence=str(directory / 'result.json'), status=record['status'], checks=len(checks), failures=failed), ensure_ascii=False))
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
