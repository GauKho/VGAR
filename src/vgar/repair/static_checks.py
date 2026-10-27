"""Syntax, mypy and Ruff evidence with tool-owned configuration the target repository cannot weaken."""
import ast
import re
import sys
import time

from vgar.repair.config import CONFIG_DIR
from vgar.repair.contracts import safe_path
from vgar.repair.evidence import digest
from vgar.repair.diagnostics import exception_details
from vgar.repair.executor import utc_now


def run_static_checks(lease, targets, policy, executor, *, variant=None):
    if variant is not None:
        return _run_w9_static_checks(lease, targets, policy, executor, variant)
    targets = tuple(safe_path(t) for t in targets)
    if not targets:
        raise ValueError('Static checks need approved source targets')
    result = {'syntax': {'status': 'PASS'}}
    try:
        for target in targets:
            ast.parse((lease.path / target).read_bytes(), filename=target)
    except (OSError, SyntaxError) as error:
        result['syntax'] = dict(status='FAIL', reason=str(error), exception=exception_details(error))
    configs = {'mypy': CONFIG_DIR / 'static/mypy.ini', 'ruff': CONFIG_DIR / 'static/ruff.toml'}
    before = {key: digest(path.read_bytes()) for key, path in configs.items()}
    for name, config in configs.items():
        args = ((sys.executable, '-m', 'mypy', '--config-file', str(config), '--no-incremental',
                 '--cache-dir', str(lease.private / 'mypy-cache'), *targets) if name == 'mypy' else
                (sys.executable, '-m', 'ruff', 'check', '--config', str(config), '--no-cache', *targets))
        result[name] = executor.run(args, lease.path, policy.command_timeout)
    result['config_hashes'] = before
    if before != {key: digest(path.read_bytes()) for key, path in configs.items()}:
        raise ValueError('Static configuration changed during checks')
    return result


def _run_w9_static_checks(lease, targets, policy, executor, variant):
    """Opt-in native-fixture path. Environment bridging remains a later task."""
    from vgar.repair.policy import VariantPolicy, policy_hash
    from vgar.repair.static_diagnostics import Diagnostic, DiagnosticReport, parse_tool_report, scope_digest
    VariantPolicy.model_validate(variant)
    targets = tuple(sorted(safe_path(t) for t in targets))
    if not targets or len(targets) != len(set(targets)):
        raise ValueError('Static checks need unique approved source targets')
    configs = {'mypy': CONFIG_DIR / 'static/mypy.ini', 'ruff': CONFIG_DIR / 'static/ruff.toml'}
    hashes = {name: digest(path.read_bytes()) for name, path in configs.items()}
    interpreter = getattr(executor, 'interpreter_ref', sys.executable + '|' + sys.version)
    binding = dict(scope=list(targets), scope_hash=scope_digest(targets), interpreter_ref=interpreter)
    result = dict(config_hashes=hashes, binding=binding, source_snapshot={},
                  variant_policy_hash=policy_hash(variant))
    diagnostics, syntax_error = [], None
    started = time.monotonic()
    for target in targets:
        try:
            path = lease.path / target
            if not path.resolve().is_relative_to(lease.path.resolve()) or path.is_symlink():
                raise ValueError('Static source escapes private workspace')
            raw = path.read_bytes()
            result['source_snapshot'][target] = raw.decode('utf-8-sig')
            try:
                if not hasattr(executor, 'syntax_report'):
                    ast.parse(raw, filename=target)
            except SyntaxError as error:
                diagnostics.append(Diagnostic(tool='syntax', path=target, line=error.lineno or 1,
                    column=error.offset or 1, code='SyntaxError', severity='error', message=error.msg))
        except (OSError, ValueError) as error:
            syntax_error = exception_details(error)
    syntax_version = sys.version.split()[0]
    if hasattr(executor, 'syntax_report'):
        target_syntax = executor.syntax_report(targets, policy.command_timeout)
        if not target_syntax.get('complete') or not target_syntax.get('target_result', {}).get('syntax'):
            syntax_error = {'reason': 'Target syntax execution incomplete'}
        else:
            target_report = target_syntax['target_result']['syntax']
            syntax_version = target_report['tool_version']
            diagnostics = [Diagnostic.model_validate(d) for d in target_report['diagnostics']]
    report = DiagnosticReport(tool='syntax', tool_version=syntax_version,
        config_hash=digest('python-ast.parse-v1'), diagnostics=tuple(diagnostics),
        execution_status='ERROR' if syntax_error else 'COMPLETE',
        reason='SOURCE_SNAPSHOT_INCOMPLETE' if syntax_error else None, **binding)
    result['syntax'] = dict(status='ERROR' if syntax_error else 'FAIL' if diagnostics else 'PASS',
        operation='target ast.parse via Docker' if hasattr(executor, 'syntax_report') else 'in-process ast.parse on native interpreter', report=report.model_dump(mode='json'),
        exception=syntax_error, **({'command': target_syntax} if hasattr(executor, 'syntax_report') else {}), duration_ms=round((time.monotonic()-started)*1000))
    unavailable = getattr(executor, 'unavailable_checks', {})
    for name, config in configs.items():
        if name in unavailable:
            # Decided from the pinned profile, never from a failed run; not a PASS.
            report = DiagnosticReport(tool=name, tool_version='', config_hash=hashes[name],
                execution_status='UNAVAILABLE', reason=unavailable[name], **binding)
            result[name] = dict(status='UNAVAILABLE', reason=unavailable[name], report=report.model_dump(mode='json'))
            continue
        version_command = _invoke_static(executor, (sys.executable, '-m', name, '--version'), lease, policy.command_timeout)
        match = (re.match(r'^' + name + r' (\S+)', version_command.get('stdout', '').strip())
                 if version_command.get('complete') and version_command.get('exit_code') == 0 else None)
        version = match[1] if match else ''
        args = ((sys.executable, '-m', 'mypy', '--config-file', str(config), '--no-incremental',
                 '--cache-dir', str(lease.private / 'mypy-cache'), '--output', 'json', '--no-error-summary', *targets)
                if name == 'mypy' else (sys.executable, '-m', 'ruff', 'check', '--config', str(config),
                    '--no-cache', '--no-fix', '--output-format', 'json', *targets))
        command = _invoke_static(executor, args, lease, policy.command_timeout)
        command['diagnostic_context'] = dict(binding, config_hash=hashes[name])
        parsed = parse_tool_report(name, command, version)
        command.update(report=parsed.model_dump(mode='json'), version_command=version_command)
        result[name] = command
    if hashes != {name: digest(path.read_bytes()) for name, path in configs.items()}:
        raise ValueError('Static configuration changed during checks')
    return result


def _invoke_static(executor, argv, lease, timeout):
    started, tick = utc_now(), time.monotonic()
    try:
        return executor.run(argv, lease.path, timeout)
    except TimeoutError:
        raise
    except OSError as error:
        # IO loss is tool evidence; a global DeadlineExecutor TimeoutError must
        # propagate instead of being downgraded to an optional static failure.
        return dict(argv=list(argv), cwd=str(lease.path), status='ERROR', exit_code=None,
                    complete=False, stdout='', stderr=str(error), timed_out=False,
                    output_truncated=False, exception=exception_details(error),
                    timeout_seconds=timeout, started_utc=started, ended_utc=utc_now(),
                    duration_ms=round((time.monotonic()-tick)*1000))

