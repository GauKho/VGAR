"""One generation, isolated patch, deterministic verification, durable evidence."""
from dataclasses import asdict
import json
from pathlib import Path
import time

from vgar.repair.config import CONFIG_DIR, REPO_ROOT
from vgar.repair.context_adapter import load_handoff
from vgar.repair.evidence import atomic_json, begin_run, digest, encode_json
from vgar.repair.executor import NativeExecutor, remaining_timeout, utc_now
from vgar.repair.patch import PatchPolicy, parse_unified_diff, apply_patch
from vgar.repair.prompt import build_repair_prompt
from vgar.repair.test_selection import select_relevant_tests
from vgar.repair.verification import assess_transition, capture_baseline, verify_patch
from vgar.repair.workspace import create_workspace, inventory
from vgar.repair.diagnostics import exception_details


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
    deadline = min(time.monotonic() + policy.global_timeout, deadline) if deadline is not None else time.monotonic() + policy.global_timeout
    run = begin_run(output_root, 'repair', task_id=task.task_id, mode=generator.mode,
        context_origin='m1-retrieval', task=task.model_dump(mode='json'), policy=policy.model_dump(),
        model=profile.model_dump(mode='json') if profile else None, mcp_calls=[], mcp_scope='standalone_not_executed',
        artifacts={'raw_output': None, 'candidate': None, 'applied': None, 'bundle': None}, original_source_unchanged=None)
    run.record.update(supersedes_run_id=supersedes_run_id, rerun_reason=rerun_reason)
    if feedback is not None:
        run.record.update(prompt_feedback=feedback)
    for name in ('context', 'workspace', 'baseline', 'prompt', 'generation', 'parse_patch', 'apply', 'selection', 'verification'):
        run.record['stages'][name] = dict(status='NOT_RUN')
    run.save()
    run.record['source_fingerprint'] = {
        p.relative_to(REPO_ROOT).as_posix(): digest(p.read_bytes())
        for folder in ('src/vgar/repair', 'src/vgar/models', 'src/vgar/contracts', 'configs/m2')
        for p in sorted((REPO_ROOT/folder).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py', '.txt', '.json', '.ini', '.toml')}
    run.save()
    lease, applied, verification, current = None, None, {}, 'context'

    def observe(name, action, summary=lambda x: x):
        nonlocal current
        current, start = name, time.monotonic()
        run.stage(name, dict(status='NOT_RUN', complete=False, started_utc=utc_now()))
        try:
            remaining_timeout(deadline)
            value = action()
            remaining_timeout(deadline)
            entry = summary(value)
            run.stage(name, dict(entry, complete=True, started_utc=run.record['stages'][name]['started_utc'],
                ended_utc=utc_now(), duration_ms=round((time.monotonic()-start)*1000)))
            return value
        except BaseException as error:
            run.stage(name, dict(status='ERROR', complete=False, error_type=type(error).__name__, reason=str(error),
                **exception_details(error),
                started_utc=run.record['stages'][name]['started_utc'], ended_utc=utc_now(),
                duration_ms=round((time.monotonic()-start)*1000)))
            raise

    try:
        require_trusted_fixture(task)
        handoff = observe('context', lambda: load_handoff(task, m1_counter, m1_counter.counter_label),
            lambda h: dict(status='PASS', metadata=h.metadata, inputs=h.inputs, hashes=h.hashes,
                           context=h.context.model_dump(mode='json')))
        task = task.model_copy(update={'failing_selectors': tuple(sorted(set(task.failing_selectors) | set(handoff.inputs['failing_selectors'])))})
        lease = observe('workspace', lambda: create_workspace(task.source_repo, temp_root or REPO_ROOT / '.workspaces', deadline=deadline),
            lambda w: dict(status='PASS', lease=w.worktree_id, path=str(w.path), original_hashes=w.before))
        lease.keep = keep_workspace
        owned_executor = DeadlineExecutor(lease, deadline, policy.max_output_bytes)
        # A caller cannot redirect execution to a different root/interpreter.
        if executor is not None:
            raise ValueError('External executor requires an approved integration adapter; Native owns this lease')
        baseline = observe('baseline', lambda: capture_baseline(task, lease, owned_executor, policy))
        if baseline['status'] != 'PASS':
            raise StopRun('ERROR', 'VERIFICATION_INCOMPLETE')
        if hasattr(tokenizer, 'deadline'):
            tokenizer.deadline = deadline
        prompt = observe('prompt', lambda: build_repair_prompt(task, handoff, baseline, tokenizer, policy, feedback=feedback),
                         lambda p: dict(status='PASS', **asdict(p)))
        (run.directory / 'prompt.txt').write_bytes(prompt.rendered.encode('utf-8'))
        generated = observe('generation', lambda: generator.generate(prompt, profile,
                            remaining_timeout(deadline, policy.generation_timeout)))
        if generated['status'] != 'PASS':
            raise StopRun('ERROR', 'INTERNAL_ERROR')
        raw = generated['raw_text']
        (run.directory / 'raw_model_output.txt').write_bytes(raw.encode('utf-8'))
        run.record['artifacts']['raw_output'] = 'raw_model_output.txt'
        if generated['truncated']:
            raise StopRun('ERROR', 'VERIFICATION_INCOMPLETE')
        pp = PatchPolicy(task.allowed_source_paths, task.protected_paths, policy.max_diff_bytes,
                         policy.max_files, policy.max_changed_lines)
        parsed = observe('parse_patch', lambda: parse_unified_diff(raw, pp),
                         lambda p: dict(status='PASS', files=p.files, raw_sha256=digest(raw)))
        (run.directory / 'candidate.diff').write_bytes(raw.encode('utf-8'))
        run.record['artifacts']['candidate'] = 'candidate.diff'
        applied = observe('apply', lambda: apply_patch(lease, parsed, owned_executor),
                          lambda a: dict(a.model_dump(), commands=lease.patch_evidence,
                                         exception=getattr(lease, 'patch_exception', None)))
        if applied.status != 'PASS':
            raise StopRun(applied.status, applied.error.code)
        (run.directory / 'transport.diff').write_bytes((lease.private / 'candidate.diff').read_bytes())
        (run.directory / 'applied.diff').write_bytes(lease.applied_diff['stdout'].encode('utf-8'))
        run.record['artifacts']['applied'] = 'applied.diff'
        selection = observe('selection', lambda: select_relevant_tests(tuple(applied.changed_files), handoff, task))
        verification = observe('verification', lambda: verify_patch(task, lease, applied, baseline, selection, owned_executor, policy))
        status = verification['status']
        reason = None if status == 'PASS' else (verification.get('reason') or
                    next(iter(verification.get('reasons', [])), 'VERIFICATION_INCOMPLETE'))
    except StopRun as error:
        status, reason = error.status, error.code
    except BaseException as error:
        status = 'FAIL' if current == 'parse_patch' and isinstance(error, ValueError) else 'ERROR'
        reason = 'PATCH_PARSE_ERROR' if status == 'FAIL' else 'WORKTREE_ERROR' if current == 'workspace' else 'INTERNAL_ERROR'
        run.record['error_detail'] = dict(exception_details(error), stage=current)
    finally:
        bundle = None
        run.record['finalization_errors'] = []
        def finalization_failure(stage, error):
            nonlocal status, reason
            status, reason = 'ERROR', 'FINALIZATION_ERROR'
            run.record['finalization_errors'].append(dict(exception_details(error), stage=stage))
        if lease:
            try:
                lease.assert_original()
                run.record['original_source_unchanged'] = True
            except Exception as error:
                status, reason = 'ERROR', 'WORKTREE_ERROR'
                run.record.update(original_source_unchanged=False, integrity_error=str(error),
                                  integrity_exception=exception_details(error))
            try:
                bundle = _project_bundle(run, task, lease, applied, verification)
            except Exception as error:
                finalization_failure('bundle', error)
            finally:
                try:
                    lease.__exit__()
                except Exception as error:
                    finalization_failure('cleanup', error)
                finally:
                    if lease.cleanup_diagnostics:
                        run.stage('cleanup', lease.cleanup_diagnostics)
        if bundle:
            run.record['artifacts']['bundle'] = 'evidence_bundle.json'
        def publish_bundle(record):
            if bundle:
                bundle.metadata.update(repair_status=status, canonical_sha256=digest(encode_json(record)))
                bundle.recommendation = recommendation_for(status)
                atomic_json(run.directory / 'evidence_bundle.json', bundle)
        try:
            # A terminal PASS is published only after cleanup and bundle persistence.
            run.finish(status, reason=reason, before_publish=publish_bundle)
        except Exception as error:
            finalization_failure('bundle_publish', error)
            run.record.update(complete=False)
            run.record['artifacts']['bundle'] = None
            run.finish(status, reason=reason)
    return run



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
