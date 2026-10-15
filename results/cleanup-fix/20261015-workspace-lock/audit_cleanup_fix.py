"""Read-only checks of code/history; writes only a fresh audit evidence directory."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from vgar_m2_w78.adaptive_campaign import audit_archive
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.diagnostics import exception_details
from vgar_m2_w78.evidence import begin_run, digest
from vgar_m2_w78.executor import run_bounded


def main():
    run = begin_run(BASE / 'audit', 'cleanup-preservation-audit', mode='offline', task_id='M2-cleanup-fix')
    try:
        changes = []
        copies = {}
        for old in (BASE / 'baseline').rglob('*'):
            if old.is_file():
                relative = old.relative_to(BASE / 'baseline').as_posix()
                current = ROOT / relative
                copies[relative] = dict(before=digest(old.read_bytes()), after=digest(current.read_bytes()))
                if copies[relative]['before'] != copies[relative]['after']:
                    changes.append(relative)
        expected = {'src/vgar_m2_w78/workspace.py', 'src/vgar_m2_w78/pipeline.py',
                    'PROGRESS.md', 'README.md', 'docs/LOG_DIAGNOSTICS_VA_CACH_DOC_LOI.md'}
        assert len(copies) == 9 and set(changes) == expected, changes
        run.stage('scoped_preedit_copies', dict(status='PASS', changed=changes, copies=copies,
            added_files=['tests/test_workspace_cleanup.py', 'docs/CLEANUP_WINDOWS_VA_CACH_KIEM_THU.md'],
            scope_note='Nine pre-edit copies, not a new Git/whole-repository audit'))
        run.stage('reference_read_only', dict(status='PASS', reference=verify_reference()))
        history = audit_archive(ROOT / 'results/diagnostics-preflight/20261015T012505328670Z-d98793260a4a/archive_manifest.json')
        assert history['status'] == 'PASS'
        run.stage('historical_archive', history)
        campaign = json.loads((ROOT / 'results/adaptive_acceptance/2026-10-15-v5-plus/campaign.json').read_text(encoding='utf-8'))
        assert len(campaign['attempts']) == 5
        assert campaign['status'] == 'FAIL' and campaign['reason'] == 'TUNING_QUOTA_EXHAUSTED'
        run.stage('no_new_campaign_inference', dict(status='PASS', attempts=5, campaign_status='FAIL',
            reason=campaign['reason'], acceptance='B BLOCKED; C historical V9 PASS; final3 NOT_RUN'))
        path = next((BASE / 'full').glob('*/run_record.json'))
        result = json.loads(path.read_text(encoding='utf-8'))
        suite = ET.parse(path.parent / 'junit.xml').getroot().find('testsuite')
        assert result['status'] == 'PASS' and result['complete'] and result['stages']['pytest']['exit_code'] == 0
        assert suite.attrib['tests'] == '183' and suite.attrib['failures'] == suite.attrib['errors'] == '0'
        run.stage('full_suite', dict(status='PASS', record=str(path), tests=183,
            duration_ms=result['duration_ms'], stdout=result['stages']['pytest']['stdout']))
        lint = run_bounded((sys.executable, '-m', 'ruff', 'check', '--select', 'E9,F', 'src', 'scripts', 'tests'), ROOT, 30)
        run.stage('ruff', lint)
        assert lint['status'] == 'PASS'
        run.finish('PASS', scope='cleanup fix only; no real repair acceptance claim')
    except Exception as error:
        run.finish('ERROR', **exception_details(error))
        print(run.path)
        return 1
    print(run.path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
