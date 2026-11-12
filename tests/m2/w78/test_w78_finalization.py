from vgar.repair import verification as m_verification


def test_regression_disappearing_or_skipping_is_incomplete():
    baseline = {'required_ids': ['fix'], 'tests': {'outcomes': {'fix': 'FAIL', 'regression': 'PASS'}}}
    for state in (None, 'SKIP', 'XFAIL', 'XPASS', 'ERROR'):
        post = {'status': 'PASS', 'outcomes': {'fix': 'PASS', 'regression': state}}
        status, reasons = m_verification.assess_transition(baseline, post)
        assert status == 'ERROR' and 'VERIFICATION_INCOMPLETE' in reasons
