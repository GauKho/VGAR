"""Record an actual pytest invocation without hashing unrelated caches."""
from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.contracts import safe_selector
from vgar_m2_w78.evidence import begin_run
from vgar_m2_w78.executor import run_bounded
from vgar_m2_w78.diagnostics import exception_details
from vgar_m2_w78.b_experiment import runtime_fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selectors', nargs='*', default=['tests'])
    parser.add_argument('--timeout-seconds', type=float, default=300)
    parser.add_argument('--output-root', type=Path, default=ROOT / 'results/tests')
    args = parser.parse_args()
    run = begin_run(args.output_root, 'pytest', mode='offline', task_id='M2-tests')
    try:
        run.record['reference'] = verify_reference()
        run.record['runtime_before'] = runtime_fingerprint(ROOT)
        selectors = [safe_selector(s) for s in args.selectors or ['tests']]
        if any(not s.startswith('tests') for s in selectors):
            raise ValueError('Recorder only runs this package tests')
        environment = {'PYTHONPATH': os.pathsep.join((str(ROOT / 'src'), run.record['reference']['root'] + '/src'))}
        result = run_bounded((sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '--junitxml=' + str(run.directory / 'junit.xml'), *selectors), ROOT, args.timeout_seconds,
            environment=environment)
        run.stage('pytest', result)
        run.record['runtime_after'] = runtime_fingerprint(ROOT)
        run.finish(result['status'])
        code = result['exit_code'] if result['complete'] else 2
    except Exception as error:
        run.finish('ERROR', reason=str(error), error_type=type(error).__name__, **exception_details(error))
        code = 2
    print(run.path)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
