"""The evidence bundle M2 hands to M3 separates failing vs relevant tests and carries diff + recommendation."""
import json

import pytest

from vgar.contracts import evidence as m_evidence

FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'
REQUIRED = 'tests/test_auth.py::test_login_rejects_whitespace'
REGRESSION = 'tests/test_auth.py::test_login_accepts_name'


def bundle_of(run):
    return json.loads((run.directory / 'evidence_bundle.json').read_text(encoding='utf-8'))


def test_old_bundles_without_new_fields_still_validate():
    tests = m_evidence.TestRunResult(status='NOT_RUN', command='', argv=[], exit_code=None, duration_ms=0, stdout='', stderr='')
    bundle = m_evidence.EvidenceBundle(run_id='r', source_repo='x', source_hash_before='a', source_hash_after='a',
                            worktree_id='wt', verification=m_evidence.VerificationResult(tests=tests))
    assert bundle.diff == '' and bundle.recommendation == 'REJECT'
    assert bundle.verification.failing_tests == m_evidence.TestGroupResult()
    assert bundle.verification.relevant_tests.status == 'NOT_RUN'


@pytest.mark.parametrize('letter', ['A', 'B', 'C'])
def test_saved_golden_bundles_still_validate(letter):
    from w78_support import REPO
    path = REPO / 'tests/fixtures/m2/golden_v11' / letter / 'evidence_bundle.json'
    bundle = m_evidence.EvidenceBundle.model_validate(json.loads(path.read_text(encoding='utf-8')))
    assert bundle.metadata['repair_status'] == 'PASS'
