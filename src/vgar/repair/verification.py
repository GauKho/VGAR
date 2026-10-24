"""Trusted-fixture baseline/post checks, with no exit-zero shortcut."""
from vgar.repair.static_checks import run_static_checks
from vgar.repair.test_runner import collect_tests, run_tests
from vgar.repair.workspace import inventory
from vgar.repair.diagnostics import exception_details


def expand_required(selectors, node_ids):
    required = set()
    for selector in selectors:
        matches = {n for n in node_ids if n == selector or n.startswith(selector + '::')
                   or n.startswith(selector + '[') or n.startswith(selector + '/')}
        if not matches:
            raise ValueError('Required selector not collected: ' + selector)
        required.update(matches)
    return sorted(required)


def capture_baseline(task, lease, executor, policy, *, variant=None):
    collection = collect_tests(lease, task.fallback_scope, executor, policy.command_timeout)
    result = dict(status='ERROR', collection=collection, reason='VERIFICATION_INCOMPLETE')
    if collection['status'] != 'PASS':
        return result
    try:
        required = expand_required(task.failing_selectors, collection['node_ids'])
    except ValueError as error:
        result['reason'] = str(error)
        result['exception'] = exception_details(error)
        return result
    tests = run_tests(lease, task.fallback_scope, executor, policy.command_timeout)
    static = run_static_checks(lease, task.allowed_source_paths, policy, executor,
                               **({'variant': variant} if variant is not None else {}))
    result.update(tests=tests, static=static, required_ids=required,
        failed_cases=[n for n, value in tests['outcomes'].items() if value == 'FAIL'])
    static_ready = all(static[k]['status'] == 'PASS' for k in ('syntax', 'mypy', 'ruff'))
    if variant is not None:
        from vgar.repair.policy import policy_hash, required_checks
        from vgar.repair.static_diagnostics import DiagnosticReport
        checks = required_checks(variant) - {'tests'}
        static_ready = (set(static['source_snapshot']) == set(task.allowed_source_paths)
            and all(DiagnosticReport.model_validate(static[k]['report']).execution_status == 'COMPLETE' for k in checks))
        result.update(variant_policy_hash=policy_hash(variant), variant_id=variant.variant_id)
    ready = (tests['status'] == 'FAIL' and any(tests['outcomes'].get(n) == 'FAIL' for n in required)
             and all(tests['outcomes'].get(n) in ('FAIL', 'PASS') for n in required)
             and not any(v == 'ERROR' for v in tests['outcomes'].values())
             and static_ready)
    result.update(status='PASS' if ready else 'ERROR', reason=None if ready else 'BASELINE_NOT_QUALIFIED')
    return result


def assess_transition(baseline, post):
    required = baseline['required_ids']
    outcomes = post['outcomes']
    missing = [n for n in required if outcomes.get(n) not in ('PASS', 'FAIL')]
    regression = [n for n, status in baseline['tests']['outcomes'].items()
                  if status == 'PASS' and outcomes.get(n) != 'PASS']
    incomplete_regression = [n for n in regression if outcomes.get(n) != 'FAIL']
    if post['status'] == 'ERROR' or missing or incomplete_regression:
        return 'ERROR', ['VERIFICATION_INCOMPLETE'] + missing + incomplete_regression
    if post['status'] == 'FAIL' or regression or any(outcomes.get(n) == 'FAIL' for n in required):
        return 'FAIL', ['TEST_FAILED'] + regression
    return 'PASS', []


def run_patch_tests(task, lease, apply_result, baseline, selection, executor, policy):
    """First half of verification: collection and the selected tests (no static checks yet)."""
    if apply_result.status != 'PASS' or baseline['status'] != 'PASS':
        return dict(status='ERROR', reason='VERIFICATION_INCOMPLETE')
    related = (collect_tests(lease, selection['related_selectors'], executor, policy.command_timeout)
               if selection['related_selectors'] else {'status': 'NOT_RUN', 'reason': 'no_graph_candidates'})
    collection = collect_tests(lease, selection['selected'], executor, policy.command_timeout)
    if collection['status'] != 'PASS':
        return dict(status='ERROR', reason='VERIFICATION_INCOMPLETE', related_collection=related, collection=collection)
    tests = run_tests(lease, selection['selected'], executor, policy.command_timeout)
    return dict(status='TESTED', tests=tests, collection=collection, related_collection=related)


def complete_verification(partial, task, lease, apply_result, baseline, executor, policy, *, variant=None):
    """Static checks, assessment and source protection; early ERRORs pass through.

    Session.observe owns the before/after global-deadline guard. A direct caller
    must retain that guard: clipping an optional command alone is insufficient.
    """
    if partial['status'] != 'TESTED':
        return partial
    tests, collection, related = partial['tests'], partial['collection'], partial['related_collection']
    if variant is not None:
        from vgar.repair.policy import policy_hash
        if baseline.get('variant_policy_hash') != policy_hash(variant):
            return dict(partial, status='ERROR', reasons=['VARIANT_POLICY_CHANGED'])
    elif baseline.get('variant_policy_hash'):
        return dict(partial, status='ERROR', reasons=['VARIANT_POLICY_MISSING'])
    static = run_static_checks(lease, task.allowed_source_paths, policy, executor,
                               **({'variant': variant} if variant is not None else {}))
    status, reasons = assess_transition(baseline, tests)
    policy_checks = None
    if variant is None:
        for name, code in (('syntax', 'VERIFICATION_INCOMPLETE'), ('mypy', 'TYPECHECK_FAILED'), ('ruff', 'LINT_FAILED')):
            if static[name]['status'] != 'PASS':
                reasons.append(code)
                status = 'ERROR' if static[name]['status'] == 'ERROR' or status == 'ERROR' else 'FAIL'
    else:
        status, reasons, policy_checks = _assess_w9_static(baseline, static, variant, status, reasons)
    if static['config_hashes'] != baseline['static']['config_hashes']:
        status, reasons = 'ERROR', reasons + ['STATIC_CONFIG_CHANGED']
    lease.assert_original()
    after = inventory(lease.path)
    execution_before = getattr(lease, 'execution_before', lease.before)
    unexpected = [p for p in set(execution_before) | set(after)
                  if execution_before.get(p) != after.get(p) and p not in apply_result.changed_files]
    if unexpected:
        status, reasons = 'ERROR', reasons + ['PROTECTED_SOURCE_CHANGED'] + unexpected
    result = dict(status=status, reasons=reasons, tests=tests, static=static,
                collection=collection, related_collection=related,
                related_fallback_reason='graph_collection_failed' if related['status'] == 'ERROR' else None)
    if policy_checks is not None:
        result.update(policy_checks=policy_checks, variant_policy_hash=baseline['variant_policy_hash'],
                      variant_id=variant.variant_id)
    return result


def verify_patch(task, lease, apply_result, baseline, selection, executor, policy, *, variant=None):
    return complete_verification(run_patch_tests(task, lease, apply_result, baseline, selection, executor, policy),
                                 task, lease, apply_result, baseline, executor, policy, variant=variant)


def _assess_w9_static(baseline, static, variant, status, reasons):
    from vgar.repair.policy import required_checks
    from vgar.repair.static_diagnostics import DiagnosticReport, build_line_map, compare_diagnostics
    required = required_checks(variant)
    before = baseline['static']
    checks = {'tests': dict(status=status, required=True)}
    if before['binding'] != static['binding']:
        status, reasons = 'ERROR', reasons + ['STATIC_BINDING_CHANGED']
    if set(static['source_snapshot']) != set(before['binding']['scope']):
        status, reasons = 'ERROR', reasons + ['SOURCE_SNAPSHOT_INCOMPLETE']
    line_map = build_line_map(before['source_snapshot'], static['source_snapshot'])
    for name, code in (('syntax', 'VERIFICATION_INCOMPLETE'), ('mypy', 'TYPECHECK_FAILED'), ('ruff', 'LINT_FAILED')):
        old = DiagnosticReport.model_validate(before[name]['report'])
        new = DiagnosticReport.model_validate(static[name]['report'])
        if old.tool_version and new.tool_version and old.tool_version != new.tool_version:
            status, reasons = 'ERROR', reasons + ['STATIC_TOOL_VERSION_CHANGED']
        delta = compare_diagnostics(old, new, line_map)
        checks[name] = dict(status=delta.status, raw_status=static[name]['status'],
                            required=name in required, delta=delta.model_dump(mode='json'))
        static[name].update(required=name in required, delta=delta.model_dump(mode='json'))
        if name in required and delta.status != 'PASS':
            reasons.append(code)
            status = 'ERROR' if delta.status == 'ERROR' or status == 'ERROR' else 'FAIL'
    return status, reasons, checks
