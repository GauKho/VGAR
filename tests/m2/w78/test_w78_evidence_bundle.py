"""The evidence bundle M2 hands to M3 separates failing vs relevant tests and carries diff + recommendation."""
import json

import pytest

from vgar.contracts import evidence as m_evidence
from vgar.models.generator import FakeGenerator
from vgar.repair.contracts import RepairPolicy
from vgar.repair.pipeline import recommendation_for, run_repair
from w78_support import CharacterChatTokenizer

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


@pytest.mark.parametrize('status,expected', [('PASS', 'ACCEPT'), ('FAIL', 'REVISE'), ('ERROR', 'REJECT')])
def test_recommendation_follows_final_status(status, expected):
    assert recommendation_for(status) == expected


def test_passing_repair_separates_failing_and_relevant_tests(m1_case, tmp_path):
    task, counter = m1_case
    run = run_repair(task, RepairPolicy(), FakeGenerator(FIX), None, tmp_path / 'runs',
                     m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    assert run.record['status'] == 'PASS'
    bundle = bundle_of(run)
    failing, relevant = bundle['verification']['failing_tests'], bundle['verification']['relevant_tests']
    assert failing['status'] == 'PASS' and [c['name'] for c in failing['cases']] == [REQUIRED]
    assert failing['baseline'] == {REQUIRED: 'FAIL'}
    assert relevant['status'] == 'PASS' and [c['name'] for c in relevant['cases']] == [REGRESSION]
    assert relevant['baseline'] == {REGRESSION: 'PASS'}
    assert bundle['diff'].encode('utf-8') == (run.directory / 'applied.diff').read_bytes()
    assert 'return bool(value.strip())' in bundle['diff']
    assert bundle['recommendation'] == 'ACCEPT'


def test_invalid_diff_bundle_recommends_revise_with_empty_diff(m1_case, tmp_path):
    task, counter = m1_case
    run = run_repair(task, RepairPolicy(), FakeGenerator('not a diff'), None, tmp_path / 'runs',
                     m1_counter=counter, tokenizer=CharacterChatTokenizer(), temp_root=tmp_path / 'temp')
    assert run.record['status'] == 'FAIL'
    bundle = bundle_of(run)
    assert bundle['recommendation'] == 'REVISE' and bundle['diff'] == ''
    assert bundle['verification']['failing_tests']['status'] == 'NOT_RUN'
    assert bundle['verification']['relevant_tests']['status'] == 'NOT_RUN'


@pytest.mark.parametrize('letter', ['A', 'B', 'C'])
def test_saved_golden_bundles_still_validate(letter):
    from w78_support import REPO
    path = REPO / 'tests/fixtures/m2/golden_v11' / letter / 'evidence_bundle.json'
    bundle = m_evidence.EvidenceBundle.model_validate(json.loads(path.read_text(encoding='utf-8')))
    assert bundle.metadata['repair_status'] == 'PASS'
