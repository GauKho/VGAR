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


def capture_baseline(task, lease, executor, policy):
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
    static = run_static_checks(lease, task.allowed_source_paths, policy, executor)
    result.update(tests=tests, static=static, required_ids=required,
        failed_cases=[n for n, value in tests['outcomes'].items() if value == 'FAIL'])
    ready = (tests['status'] == 'FAIL' and any(tests['outcomes'].get(n) == 'FAIL' for n in required)
             and all(tests['outcomes'].get(n) in ('FAIL', 'PASS') for n in required)
             and not any(v == 'ERROR' for v in tests['outcomes'].values())
             and all(static[k]['status'] == 'PASS' for k in ('syntax', 'mypy', 'ruff')))
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


def complete_verification(partial, task, lease, apply_result, baseline, executor, policy):
    """Second half: static checks, assessment and source protection; early ERRORs pass through."""
    if partial['status'] != 'TESTED':
        return partial
    tests, collection, related = partial['tests'], partial['collection'], partial['related_collection']
    static = run_static_checks(lease, task.allowed_source_paths, policy, executor)
    status, reasons = assess_transition(baseline, tests)
    for name, code in (('syntax', 'VERIFICATION_INCOMPLETE'), ('mypy', 'TYPECHECK_FAILED'), ('ruff', 'LINT_FAILED')):
        if static[name]['status'] != 'PASS':
            reasons.append(code)
            status = 'ERROR' if static[name]['status'] == 'ERROR' or status == 'ERROR' else 'FAIL'
    if static['config_hashes'] != baseline['static']['config_hashes']:
        status, reasons = 'ERROR', reasons + ['STATIC_CONFIG_CHANGED']
    lease.assert_original()
    after = inventory(lease.path)
    unexpected = [p for p in set(lease.before) | set(after)
                  if lease.before.get(p) != after.get(p) and p not in apply_result.changed_files]
    if unexpected:
        status, reasons = 'ERROR', reasons + ['PROTECTED_SOURCE_CHANGED'] + unexpected
    return dict(status=status, reasons=reasons, tests=tests, static=static,
                collection=collection, related_collection=related,
                related_fallback_reason='graph_collection_failed' if related['status'] == 'ERROR' else None)


def verify_patch(task, lease, apply_result, baseline, selection, executor, policy):
    return complete_verification(run_patch_tests(task, lease, apply_result, baseline, selection, executor, policy),
                                 task, lease, apply_result, baseline, executor, policy)
