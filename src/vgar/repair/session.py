"""One repair run as persisted steps, so each step can run in a fresh process (e.g. one MCP tool call).

The steps are run_repair's body cut at its natural boundaries. State that a later step needs lives in
<run_dir>/session.json next to run_record.json; the worktree lease, baseline and applied patch are rebuilt
from it. A step returns None once the run has an outcome; finish() always completes the record and
cleans the worktree.
"""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import time

from vgar.repair.admission import check_session_admission, prepare_admitted_workspace, validate_admission
from vgar.repair.config import REPO_ROOT
from vgar.repair.context_adapter import load_handoff
from vgar.repair.contracts import ModelProfile, RepairPolicy, RepairTask
from vgar.repair.diagnostics import exception_details
from vgar.repair.evidence import atomic_json, begin_run, digest, encode_json, load_run
from vgar.repair.experiment import check_session_experiment, validate_experiment
from vgar.repair.executor import remaining_timeout, utc_now
from vgar.repair.patch import PatchPolicy, apply_patch, parse_unified_diff
from vgar.repair import pipeline
from vgar.repair.pipeline import DeadlineExecutor, StopRun, recommendation_for, require_trusted_fixture
from vgar.repair.prompt import build_repair_prompt
from vgar.repair.test_selection import select_relevant_tests
from vgar.repair.verification import capture_baseline, complete_verification, run_patch_tests
from vgar.repair.workspace import WorkspaceLease, create_workspace

STAGES = ('context', 'workspace', 'baseline', 'prompt', 'generation', 'parse_patch', 'apply', 'selection', 'verification')


class RepairSession:
    def __init__(self, run, state):
        self.run, self.state = run, state

    @classmethod
    def load(cls, run_dir):
        run_dir = Path(run_dir).resolve()
        path = run_dir / 'session.json'
        if not path.is_file() or not (run_dir / 'run_record.json').is_file():
            raise ValueError('Not a repair run directory: ' + str(run_dir))
        state = json.loads(path.read_text(encoding='utf-8'))
        record = json.loads((run_dir / 'run_record.json').read_text(encoding='utf-8'))
        check_session_experiment(state, record)  # load_run writes, so validate BOTH files first.
        admission = check_session_admission(state, record)
        if admission is not None:
            validate_admission(RepairTask.model_validate(state['task']), admission)
        return cls(load_run(run_dir), state)

    def save(self):
        self.assert_experiment()
        self.assert_admission()
        atomic_json(self.run.directory / 'session.json', self.state)

    def assert_experiment(self):
        return check_session_experiment(self.state, self.run.record)

    def assert_admission(self):
        return check_session_admission(self.state, self.run.record)

    @property
    def experiment(self):
        return self.assert_experiment()

    def variant_kwargs(self):
        value = self.experiment
        return {'variant': value.variant_policy} if value is not None else {}

    def handoff_kwargs(self):
        value = self.experiment
        if value is None:
            return {}
        snapshot = self.state['experiment']
        return {'arm': value.arm, 'expected_hashes': snapshot['bundle_hashes'] or value.expected_hashes}

    @property
    def phase(self):
        return self.state['phase']

    @property
    def outcome(self):
        return tuple(self.state['outcome']) if self.state['outcome'] else None

    @property
    def deadline(self):
        return time.monotonic() + (self.state['deadline_utc'] - time.time())

    @property
    def task(self):
        return RepairTask.model_validate(self.state['task'])

    @property
    def policy(self):
        return RepairPolicy.model_validate(self.state['policy'])

    @property
    def profile(self):
        return ModelProfile.model_validate(self.state['profile']) if self.state['profile'] else None

    def lease(self):
        data = self.state['lease']
        if data is None:
            return None
        lease = WorkspaceLease(Path(data['path']), Path(data['private']), Path(data['temp_root']),
                               Path(data['source_repo']), data['before'], data['worktree_id'])
        lease.keep = data['keep']
        if 'execution_before' in data:
            lease.execution_before = data['execution_before']
        return lease

    def applied(self):
        from vgar.contracts.repair import PatchApplyResult
        return PatchApplyResult.model_validate(self.state['applied']) if self.state['applied'] else None

    def executor(self, lease):
        admission = self.assert_admission()
        if admission is not None:
            from vgar.repair.docker_executor import DockerExecutor
            return DockerExecutor(lease, self.task, admission, self.deadline, self.policy.max_output_bytes,
                                  evidence_root=self.run.directory/'docker')
        return DeadlineExecutor(lease, self.deadline, self.policy.max_output_bytes)

    def observe(self, name, action, summary=lambda x: x):
        run, start = self.run, time.monotonic()
        self.state['current'] = name
        run.stage(name, dict(status='NOT_RUN', complete=False, started_utc=utc_now()))
        try:
            remaining_timeout(self.deadline)
            value = action()
            remaining_timeout(self.deadline)
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


def _step(session, action):
    """Run one step unless the run already has an outcome; map failures exactly like run_repair did."""
    session.assert_experiment()
    session.assert_admission()
    if session.phase == 'finished':
        raise ValueError('Run already finished')
    if session.outcome:
        return None
    try:
        return action()
    except StopRun as error:
        session.state['outcome'] = [error.status, error.code]
    except BaseException as error:
        current = session.state['current']
        status = 'FAIL' if current == 'parse_patch' and isinstance(error, ValueError) else 'ERROR'
        reason = 'PATCH_PARSE_ERROR' if status == 'FAIL' else 'WORKTREE_ERROR' if current == 'workspace' else 'INTERNAL_ERROR'
        session.state['outcome'] = [status, reason]
        session.run.record['error_detail'] = dict(exception_details(error), stage=current)
        session.run.save()
    finally:
        session.save()
    return None


def start_session(task, policy, mode, output_root, *, profile=None, temp_root=None, keep_workspace=False,
                  supersedes_run_id=None, rerun_reason=None, feedback=None, deadline=None,
                  mcp_scope='standalone_not_executed', experiment=None, admission=None):
    if policy.runtime == 'docker_admitted':
        task = RepairTask.model_validate(task.model_dump())
        admission = validate_admission(task, admission)
        if experiment is None:
            # Docker must use the explicit W9 required-check policy, never legacy strict host static.
            raise ValueError('Docker admission requires an explicit W9 experiment policy')
    elif admission is not None:
        raise ValueError('Admission cannot redirect native fixture execution')
    admission_meta = {'admission_required': True, 'admission': admission.snapshot()} if admission is not None else {}
    experiment = validate_experiment(experiment)
    experiment_meta = {'experiment_required': True, 'experiment': experiment.snapshot()} if experiment is not None else {}
    deadline = min(time.monotonic() + policy.global_timeout, deadline) if deadline is not None else time.monotonic() + policy.global_timeout
    run = begin_run(output_root, 'repair', task_id=task.task_id, mode=mode,
        context_origin='m1-retrieval', task=task.model_dump(mode='json'), policy=policy.model_dump(),
        model=profile.model_dump(mode='json') if profile else None, mcp_calls=[], mcp_scope=mcp_scope,
        artifacts={'raw_output': None, 'candidate': None, 'applied': None, 'bundle': None}, original_source_unchanged=None,
        **copy.deepcopy(experiment_meta), **copy.deepcopy(admission_meta))
    run.record.update(supersedes_run_id=supersedes_run_id, rerun_reason=rerun_reason)
    if feedback is not None:
        run.record.update(prompt_feedback=feedback)
    for name in STAGES:
        run.record['stages'][name] = dict(status='NOT_RUN')
    run.save()
    run.record['source_fingerprint'] = {
        p.relative_to(REPO_ROOT).as_posix(): digest(p.read_bytes())
        for folder in ('src/vgar/repair', 'src/vgar/models', 'src/vgar/contracts', 'src/vgar/agents/prompts', 'configs/m2')
        for p in sorted((REPO_ROOT/folder).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py', '.txt', '.json', '.ini', '.toml')}
    run.save()
    session = RepairSession(run, dict(
        task=task.model_dump(mode='json'), policy=policy.model_dump(),
        profile=profile.model_dump(mode='json') if profile else None, mode=mode,
        deadline_utc=time.time() + (deadline - time.monotonic()), phase='started', outcome=None, current='context',
        temp_root=str(temp_root or REPO_ROOT / '.workspaces'), keep_workspace=keep_workspace, feedback=feedback,
        lease=None, baseline=None, applied=None, verification=None, **copy.deepcopy(experiment_meta), **copy.deepcopy(admission_meta)))
    session.save()
    return session


def prepare(session, m1_counter, tokenizer, *, executor=None):
    """Trusted-fixture gate, M1 context, private worktree, baseline and the V11 prompt (prompt.txt)."""
    def action():
        task = session.task
        admission = session.assert_admission()
        if admission is None:
            require_trusted_fixture(task)
        handoff_kwargs = session.handoff_kwargs()
        handoff = session.observe('context', lambda: load_handoff(task, m1_counter, m1_counter.counter_label, **handoff_kwargs),
            lambda h: dict(status='PASS', metadata=h.metadata, inputs=h.inputs, hashes=h.hashes,
                           context=h.context.model_dump(mode='json')))
        if 'experiment' in session.state:
            snapshot = {**session.state['experiment'], 'bundle_hashes': handoff.hashes.copy()}
            session.state['experiment'] = copy.deepcopy(snapshot)
            session.run.record['experiment'] = copy.deepcopy(snapshot)
            session.run.save()
            session.save()
        task = task.model_copy(update={'failing_selectors': tuple(sorted(set(task.failing_selectors) | set(handoff.inputs['failing_selectors'])))})
        if admission is not None:
            validate_admission(task, admission)
        session.state['task'] = task.model_dump(mode='json')
        lease = session.observe('workspace', lambda: (prepare_admitted_workspace(task, admission, Path(session.state['temp_root']), deadline=session.deadline)
                       if admission is not None else create_workspace(task.source_repo, Path(session.state['temp_root']), deadline=session.deadline)),
            lambda w: dict(status='PASS', lease=w.worktree_id, path=str(w.path), original_hashes=w.before))
        lease.keep = session.state['keep_workspace']
        session.state['lease'] = dict(path=str(lease.path), private=str(lease.private), temp_root=str(lease.temp_root),
                                      source_repo=str(lease.source_repo), before=lease.before,
                                      worktree_id=lease.worktree_id, keep=lease.keep)
        if admission is not None:
            session.state['lease']['execution_before'] = lease.execution_before
        session.save()
        # A caller cannot redirect execution to a different root/interpreter.
        if executor is not None:
            raise ValueError('External executor requires an approved integration adapter; Native owns this lease')
        baseline = session.observe('baseline', lambda: capture_baseline(task, lease, session.executor(lease), session.policy,
                                                                      **session.variant_kwargs()))
        session.state['baseline'] = baseline
        if baseline['status'] != 'PASS':
            raise StopRun('ERROR', 'VERIFICATION_INCOMPLETE')
        if hasattr(tokenizer, 'deadline'):
            tokenizer.deadline = session.deadline
        prompt = session.observe('prompt', lambda: build_repair_prompt(task, handoff, baseline, tokenizer, session.policy,
                                                                      feedback=session.state['feedback']),
                                 lambda p: dict(status='PASS', **asdict(p)))
        (session.run.directory / 'prompt.txt').write_bytes(prompt.rendered.encode('utf-8'))
        session.state['phase'] = 'prepared'
        return prompt
    return _step(session, action)


def record_generation(session, generated, *, started_utc, duration_ms, error=None):
    """Record a generation that ran elsewhere (in-process or in an MCP client); return the raw diff text."""
    def action():
        run = session.run
        session.state['current'] = 'generation'
        if error is not None:
            run.stage('generation', dict(status='ERROR', complete=False, error_type=type(error).__name__,
                reason=str(error), **exception_details(error), started_utc=started_utc, ended_utc=utc_now(),
                duration_ms=duration_ms))
            raise error
        remaining_timeout(session.deadline)
        run.stage('generation', dict(generated, complete=True, started_utc=started_utc, ended_utc=utc_now(),
                                     duration_ms=duration_ms))
        if generated['status'] != 'PASS':
            raise StopRun('ERROR', 'INTERNAL_ERROR')
        raw = generated['raw_text']
        (run.directory / 'raw_model_output.txt').write_bytes(raw.encode('utf-8'))
        run.record['artifacts']['raw_output'] = 'raw_model_output.txt'
        run.save()
        if generated['truncated']:
            raise StopRun('ERROR', 'VERIFICATION_INCOMPLETE')
        session.state['phase'] = 'generated'
        return raw
    return _step(session, action)


def apply_candidate(session, raw):
    """Strict unified-diff parse, then git apply into the private worktree."""
    def action():
        run, task, policy, lease = session.run, session.task, session.policy, session.lease()
        pp = PatchPolicy(task.allowed_source_paths, task.protected_paths, policy.max_diff_bytes,
                         policy.max_files, policy.max_changed_lines)
        parsed = session.observe('parse_patch', lambda: parse_unified_diff(raw, pp),
                                 lambda p: dict(status='PASS', files=p.files, raw_sha256=digest(raw)))
        (run.directory / 'candidate.diff').write_bytes(raw.encode('utf-8'))
        run.record['artifacts']['candidate'] = 'candidate.diff'
        applied = session.observe('apply', lambda: apply_patch(lease, parsed, session.executor(lease)),
                                  lambda a: dict(a.model_dump(), commands=lease.patch_evidence,
                                                 exception=getattr(lease, 'patch_exception', None)))
        session.state['applied'] = applied.model_dump(mode='json')
        if applied.status != 'PASS':
            raise StopRun(applied.status, applied.error.code)
        (run.directory / 'transport.diff').write_bytes((lease.private / 'candidate.diff').read_bytes())
        (run.directory / 'applied.diff').write_bytes(lease.applied_diff['stdout'].encode('utf-8'))
        run.record['artifacts']['applied'] = 'applied.diff'
        run.save()
        session.state['phase'] = 'applied'
        return applied
    return _step(session, action)


def run_selected_tests(session, m1_counter):
    """Relevant-test selection and the test half of verification (stored as the verification stage)."""
    def action():
        task, lease, applied = session.task, session.lease(), session.applied()
        handoff = load_handoff(task, m1_counter, m1_counter.counter_label, **session.handoff_kwargs())
        selection = session.observe('selection', lambda: select_relevant_tests(tuple(applied.changed_files), handoff, task))
        partial = session.observe('verification', lambda: run_patch_tests(task, lease, applied, session.state['baseline'],
                                                                         selection, session.executor(lease), session.policy))
        session.state['verification'] = partial
        session.state['phase'] = 'tested'
        return partial
    return _step(session, action)


def _complete_verification(session):
    run, task, lease, applied = session.run, session.task, session.lease(), session.applied()
    first = run.record['stages']['verification']
    verification = session.observe('verification', lambda: complete_verification(
        session.state['verification'], task, lease, applied, session.state['baseline'], session.executor(lease), session.policy,
        **session.variant_kwargs()))
    stage = run.record['stages']['verification']
    stage.update(started_utc=first['started_utc'], duration_ms=first['duration_ms'] + stage['duration_ms'])
    run.save()
    session.state['verification'] = verification
    status = verification['status']
    reason = None if status == 'PASS' else (verification.get('reason') or
                next(iter(verification.get('reasons', [])), 'VERIFICATION_INCOMPLETE'))
    session.state['outcome'] = [status, reason]


def finish(session, *, on_record=None):
    """Complete verification if tests ran, then integrity check, evidence bundle, cleanup and the final record."""
    session.assert_experiment()
    if session.phase == 'finished':
        raise ValueError('Run already finished')
    if not session.outcome:
        if session.phase == 'tested':
            _step(session, lambda: _complete_verification(session))
        if not session.outcome:
            session.state['outcome'] = ['ERROR', 'VERIFICATION_INCOMPLETE']
    status, reason = session.outcome
    run, task, lease, applied = session.run, session.task, session.lease(), session.applied()
    verification = session.state['verification'] or {}
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
            bundle = pipeline._project_bundle(run, task, lease, applied, verification)  # module lookup: patchable
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
            if 'experiment' in record:
                bundle.metadata['experiment'] = copy.deepcopy(record['experiment'])
            if 'admission' in record:
                bundle.metadata['admission'] = copy.deepcopy(record['admission'])
            bundle.metadata.update(repair_status=status, canonical_sha256=digest(encode_json(record)))
            bundle.recommendation = recommendation_for(status)
            atomic_json(run.directory / 'evidence_bundle.json', bundle)
    if on_record is not None:
        on_record(status)  # last chance to add to the record before it is hashed and published
    try:
        # A terminal PASS is published only after cleanup and bundle persistence.
        run.finish(status, reason=reason, before_publish=publish_bundle)
    except Exception as error:
        finalization_failure('bundle_publish', error)
        run.record.update(complete=False)
        run.record['artifacts']['bundle'] = None
        run.finish(status, reason=reason)
    session.state.update(phase='finished', outcome=[status, reason])
    session.save()
    return run
