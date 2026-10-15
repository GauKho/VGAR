"""M2 policy over M1's native diagnostics; no new graph traversal."""
from .bootstrap import verify_reference


def select_relevant_tests(changed_files, handoff, task):
    verify_reference()
    from vgar.contracts.consumer import diagnose_changed_paths
    handoff.assert_unchanged()
    report = diagnose_changed_paths(handoff.hints, handoff.manifest, task.source_repo, list(changed_files))
    required = tuple(sorted(set(task.failing_selectors) | set(report['failing_selectors'])))
    scope = tuple(sorted(set(task.fallback_scope) | set(report['fallback_scope'])))
    if report['fallback_required'] and not scope:
        raise ValueError('Missing approved fallback scope: VERIFICATION_INCOMPLETE')
    if not required or not scope:
        raise ValueError('Trusted fixture requires failing selectors and full regression scope')
    return dict(report=report, required_selectors=required,
        related_selectors=report['graph_selectors'], fallback_scope=scope,
        selected=scope, fallback_required=report['fallback_required'],
        reasons=['small_fixture_full_regression'] + [r for x in report['targets'].values() for r in x['fallback_reasons']])

