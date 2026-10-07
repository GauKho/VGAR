"""Read-only checks for the affected handoff docs; not an environment check."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, utc_now, write_json

DOCUMENTS = [
    'README.md', 'PROGRESS.md', 'docs/w5_w6_completion.md',
    'docs/BAO_CAO_TASK_CHUA_HOAN_THANH_W3_W6.md', 'docs/m5_m6_retrieval_evaluation.md',
    'docs/reviews/2026-10-07-manual-retrieval-audit-10.md',
    'docs/reviews/2026-10-07-affected-files-review-w3-w6.md',
    'docs/reviews/2026-10-07-dev25-no-jedi-results.md',
    'docs/superpowers/plans/2026-10-06-fix-vgar-integration-week-1-6.md',
]


def main():
    directory, record = new_run(ROOT / 'artifacts/fixes/w3-w6/doc-checks', 'affected-doc-links-and-powershell-syntax')
    started = time.perf_counter()
    links, blocks, failures = [], [], []
    originals = {}
    for relative in DOCUMENTS:
        path = ROOT / relative
        raw = path.read_bytes()
        originals[relative] = sha256(raw)
        content = raw.decode('utf-8')
        # Non-fenced human prose only; illustrative JSON/commands aren't links.
        prose = re.sub(r'```.*?```', '', content, flags=re.S)
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', prose):
            if target.startswith(('http:', 'https:', '#')):
                continue
            target = target.split('#', 1)[0].strip('<>')
            resolved = (path.parent / target).resolve()
            valid = resolved.exists()
            links.append(dict(document=relative, target=target, exists=valid))
            if not valid:
                failures.append(dict(document=relative, error='missing local link', target=target))
        for index, body in enumerate(re.findall(r'```powershell\s*\n(.*?)```', content, flags=re.S), 1):
            # Windows text stdin translates LF to CRLF. Feeding already-CRLF
            # text creates CRCRLF and breaks backtick continuation artificially.
            body = body.replace('\r\n', '\n')
            # Parse stdin as PowerShell, never execute document instructions.
            parser = ('$code=[Console]::In.ReadToEnd(); $tokens=$null; $errors=$null; '
                      '[void][System.Management.Automation.Language.Parser]::ParseInput($code,[ref]$tokens,[ref]$errors); '
                      'if($errors.Count){$errors | ForEach-Object {$_.Message}; exit 1}; exit 0')
            argv = ['powershell', '-NoProfile', '-NonInteractive', '-Command', parser]
            outcome = subprocess.run(argv, input=body, capture_output=True, text=True, encoding='utf-8',
                                     errors='replace', timeout=15, cwd=ROOT)
            item = dict(document=relative, block=index, command_argv=argv, input_sha256=sha256(body),
                        exit_code=outcome.returncode, stdout=outcome.stdout, stderr=outcome.stderr)
            blocks.append(item)
            if outcome.returncode:
                failures.append(dict(document=relative, block=index, error='PowerShell syntax'))
    preserved = all(sha256((ROOT / path).read_bytes()) == digest for path, digest in originals.items())
    if not preserved:
        failures.append(dict(error='document changed during check'))
    record.update(status='PASS' if not failures else 'FAIL', exit_code=0 if not failures else 1,
                  complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                  links=links, powershell_blocks=blocks, failures=failures,
                  document_hashes=originals, documents_preserved=preserved,
                  limitations='Syntax/local existence only; no command execution, remote links or semantic proof.')
    write_json(directory / 'result.json', record)
    print(json.dumps(dict(evidence=str(directory / 'result.json'), status=record['status'],
                          links=len(links), powershell_blocks=len(blocks), failures=failures), ensure_ascii=False))
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
