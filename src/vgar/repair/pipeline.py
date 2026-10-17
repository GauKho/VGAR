"""One generation, isolated patch, deterministic verification, durable evidence."""
import json
from pathlib import Path
import time

from vgar.repair.config import CONFIG_DIR, REPO_ROOT
from vgar.repair.evidence import digest
from vgar.repair.executor import NativeExecutor, remaining_timeout, utc_now
from vgar.repair.verification import assess_transition
from vgar.repair.workspace import inventory


class StopRun(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def require_trusted_fixture(task):
    registry = json.loads((CONFIG_DIR / 'trusted_fixtures.json').read_text(encoding='utf-8'))
    approved = registry.get(task.task_id)
    if (not task.trusted_fixture or not approved or sorted(task.allowed_source_paths) != sorted(approved['allowed'])
            or inventory(task.source_repo) != {p: 'sha256:' + h for p, h in approved['files'].items()}):
        raise ValueError('Native execution only allowed on byte-verified approved fixtures')


class DeadlineExecutor(NativeExecutor):
    def __init__(self, lease, deadline, output_cap):
        super().__init__(lease, output_cap)
        self.deadline = deadline

    def run(self, argv, cwd, timeout_seconds):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Global run deadline exhausted')
        return super().run(argv, cwd, min(timeout_seconds, remaining))


def recommendation_for(status):
    """PASS -> ACCEPT; FAIL (patch produced, checks rejected it) -> REVISE; ERROR (incomplete) -> REJECT."""
    return {'PASS': 'ACCEPT', 'FAIL': 'REVISE'}.get(status, 'REJECT')


def _test_groups(vector, baseline):
    """Split post-patch cases into baseline-failing (must now pass) and the other selected tests."""
    from vgar.contracts.evidence import TestCaseResult, TestGroupResult
    before = baseline['tests']['outcomes']
    required = baseline['required_ids']
    by_name = {case.name: case for case in vector}
    failing = [by_name.get(n) or TestCaseResult(name=n, status='NOT_RUN', detail='not run after patch') for n in required]
    relevant = [case for case in vector if case.name not in set(required)]

    def group(cases):
        statuses = {case.status for case in cases}
        status = ('NOT_RUN' if not cases else 'ERROR' if statuses & {'ERROR', 'NOT_RUN'}
                  else 'FAIL' if 'FAIL' in statuses else 'PASS')
        return TestGroupResult(status=status, cases=cases,
                               baseline={case.name: before.get(case.name, 'NOT_RUN') for case in cases})
    return group(failing), group(relevant)


def _project_bundle(run, task, lease, applied, verification):
    from vgar.contracts.evidence import (CheckResult, EvidenceBundle, TestCaseResult, TestGroupResult, TestRunResult,
                                         VerificationResult)
    from vgar.contracts.repair import FailureReason
    tests = verification.get('tests')
    if tests:
        command = tests['command']
        baseline = run.record['stages']['baseline']
        assessed_status, assessed_reasons = assess_transition(baseline, tests)
        reason = (None if assessed_status == 'PASS' else FailureReason(
            code='TEST_TIMEOUT' if command['timed_out'] else 'TEST_FAILED' if assessed_status == 'FAIL' else 'VERIFICATION_INCOMPLETE',
            message=tests.get('reason') or 'Test execution not accepted'))
        vector = [TestCaseResult(name=n, status=v if v in ('PASS', 'FAIL', 'ERROR') else 'NOT_RUN',
            duration_ms=tests['durations_ms'].get(n, 0), detail=v) for n, v in tests['outcomes'].items()]
        test_dto = TestRunResult(status=assessed_status, command=command['command'], argv=command['argv'],
            exit_code=command['exit_code'], duration_ms=command['duration_ms'], stdout=command['stdout'], stderr=command['stderr'],
            reason=reason, cases=vector, complete=command['complete'], output_truncated=command['output_truncated'],
            stdout_bytes=command['stdout_bytes'], stderr_bytes=command['stderr_bytes'], timeout_seconds=command['timeout_seconds'])
        failing_tests, relevant_tests = _test_groups(vector, baseline)
    else:
        test_dto = TestRunResult(status='NOT_RUN', command='', argv=[], exit_code=None,
            duration_ms=0, stdout='', stderr='', complete=False)
        failing_tests, relevant_tests = TestGroupResult(), TestGroupResult()
    static = verification.get('static', {})
    checks = {}
    for key, public, code in (('mypy', 'typecheck', 'TYPECHECK_FAILED'), ('ruff', 'lint', 'LINT_FAILED')):
        status = static.get(key, {}).get('status', 'NOT_RUN')
        checks[public] = CheckResult(status=status, reason=None if status in ('PASS', 'NOT_RUN') else
                                    FailureReason(code=code, message='See canonical stage command evidence'))
    allowed_codes = {'TEST_FAILED', 'TYPECHECK_FAILED', 'LINT_FAILED', 'VERIFICATION_INCOMPLETE'}
    public_reasons = [FailureReason(code=r if r in allowed_codes else 'VERIFICATION_INCOMPLETE', message=r)
                      for r in verification.get('reasons', [])]
    if verification.get('reason') and not public_reasons:
        public_reasons.append(FailureReason(code='VERIFICATION_INCOMPLETE', message=verification['reason']))
    applied_diff = run.directory / 'applied.diff'
    bundle = EvidenceBundle(run_id=run.record['run_id'], task_id=task.task_id, source_repo=str(task.source_repo),
        source_hash_before=digest(json.dumps(lease.before, sort_keys=True)),
        source_hash_after=digest(json.dumps(inventory(task.source_repo), sort_keys=True)), worktree_id=lease.worktree_id,
        verification=VerificationResult(patch_applied=bool(applied and applied.patch_applied), tests=test_dto,
            failing_tests=failing_tests, relevant_tests=relevant_tests, reasons=public_reasons, **checks),
        diff=applied_diff.read_bytes().decode('utf-8') if applied_diff.is_file() else '',
        recommendation=recommendation_for(run.record['status']),
        artifact_path=str(run.path), metadata={'repair_status': run.record['status'], 'mode': run.record['mode'],
            'graph_version': task.graph_version, 'canonical_sha256': digest(run.path.read_bytes()),
            'raw_pytest_status': tests.get('status') if tests else 'NOT_RUN',
            'baseline_ref': 'run_record.json#stages/baseline', 'selection_ref': 'run_record.json#stages/selection'})
    return bundle


def run_repair(task, policy, generator, executor, output_root, *, m1_counter, tokenizer,
               profile=None, temp_root=None, keep_workspace=False, supersedes_run_id=None, rerun_reason=None,
               feedback=None, deadline=None):
    """One generation, in-process: the persisted session steps run back to back."""
    from vgar.repair import session as steps
    session = steps.start_session(task, policy, generator.mode, output_root, profile=profile, temp_root=temp_root,
        keep_workspace=keep_workspace, supersedes_run_id=supersedes_run_id, rerun_reason=rerun_reason,
        feedback=feedback, deadline=deadline)
    prompt = steps.prepare(session, m1_counter, tokenizer, executor=executor)
    if prompt is not None:
        started_utc, start = utc_now(), time.monotonic()
        generated, error = None, None
        try:
            generated = generator.generate(prompt, profile, remaining_timeout(session.deadline, policy.generation_timeout))
        except BaseException as caught:
            error = caught
        raw = steps.record_generation(session, generated, started_utc=started_utc,
                                      duration_ms=round((time.monotonic()-start)*1000), error=error)
        if raw is not None and steps.apply_candidate(session, raw) is not None:
            steps.run_selected_tests(session, m1_counter)
    return steps.finish(session, m1_counter)


def build_generation(mode, task, policy, profile, output_root):
    """Explicit fake or real generation for one task; fake is never a fallback for real."""
    from vgar.graph.token_counter import LocalTokenizerCounter
    counter = LocalTokenizerCounter(profile.tokenizer_manifest)
    if mode == 'fake':
        from vgar.models.generator import FakeGenerator
        from vgar.models.huggingface.local_chat import LocalChatTokenizer
        patch = REPO_ROOT / 'tests/fixtures/m2/reference_patches' / (task.task_id + '.diff')
        return FakeGenerator(patch.read_text(encoding='utf-8')), LocalChatTokenizer(profile.tokenizer_manifest), counter
    if mode == 'real':
        from vgar.models.huggingface.generator_hf import HFChatTokenizer, HFGenerator
        generator = HFGenerator(profile, Path(output_root) / 'model-workers', policy)
        return generator, HFChatTokenizer(generator, policy), counter
    raise ValueError('Unknown generation mode: ' + str(mode))
