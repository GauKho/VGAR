"""Materialize a separate, hash-verified copy of a committed historical run.

Never repairs/normalizes the dirty checkout in place. Never recomputes hashes
inside the saved run. Only original Git blob bytes matching the recorded task
hash are accepted; no retrieval is executed.
"""
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, write_json, utc_now


def main():
    directory, result = new_run(Path(__file__).parent / 'baseline-recovery', 'git-blob-baseline-recovery')
    started = time.perf_counter()
    git = ['git', '-c', 'safe.directory=' + ROOT.as_posix()]
    original = 'results/retrieval/20261005T082810770056Z-7a3ad261d8e4'
    recovered = directory / 'recovered-run'
    result.update(complete=False, source_run=original, recovered_run=str(recovered), files=[],
                  inference='NOT_RUN', bm25_reexecuted=False, old_files_modified=False,
                  stdout='', stderr='')
    write_json(directory / 'result.json', result)
    try:
        commit = subprocess.run([*git, 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                                capture_output=True).stdout.decode('ascii').strip()
        result['git_commit'] = commit
        def blob(relative):
            proc = subprocess.run([*git, 'show', commit + ':' + relative], cwd=ROOT,
                                  capture_output=True, check=True)
            return proc.stdout
        raw_record = blob(original + '/result.json')
        record = json.loads(raw_record)
        assert record['kind'] == 'retrieval' and record['complete'] and record['status'] == 'SUCCEEDED'
        assert len(record['task_results']) == 25
        recovered.mkdir(exist_ok=False)
        (recovered / 'tasks').mkdir()
        for row in record['task_results']:
            iid = row['instance_id']
            assert iid.replace('_', '').replace('-', '').isalnum()
            relative = original + '/tasks/' + iid + '.json'
            raw = blob(relative)
            digest = sha256(raw)
            assert digest == row['artifact_hash'], (iid, digest, row['artifact_hash'])
            current_raw = (ROOT / relative).read_bytes()
            current_hash = sha256(current_raw)
            newline_only = current_hash != digest and sha256(current_raw.replace(b'\r\n', b'\n')) == digest
            # This is an export of an original object, not an authored source edit.
            (recovered / 'tasks' / (iid + '.json')).write_bytes(raw)
            assert sha256((ROOT / relative).read_bytes()) == current_hash
            result['files'].append(dict(instance_id=iid, expected_hash=row['artifact_hash'],
                                        git_blob_hash=digest, current_checkout_hash=current_hash,
                                        checkout_lf_to_crlf_only=newline_only, bytes=len(raw)))
            line = iid + ': original Git blob matches recorded hash; checkout preserved'
            result['stdout'] += line + '\n'
            print(line, flush=True)
            write_json(directory / 'result.json', result)
        (recovered / 'result.json').write_bytes(raw_record)
        result.update(status='PASS', exit_code=0, recovered_tasks=len(result['files']),
                      recovered_result_hash=sha256(raw_record),
                      checkout_newline_only_tasks=sum(row['checkout_lf_to_crlf_only'] for row in result['files']))
    except Exception as exc:
        result.update(status='ERROR', exit_code=1, error_class=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc())
        result['stderr'] = result['traceback']
    finally:
        result.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
        write_json(directory / 'result.json', result)
    print('evidence: ' + str(directory), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
