"""Issue: per RFC 2617 the qop directive of a Digest Authorization header must be a quoted string (qop="auth")."""
from requests.auth import HTTPDigestAuth


def test_digest_header_quotes_qop():
    auth = HTTPDigestAuth('user', 'passwd')
    auth.chal = {'realm': 'me@kennethreitz.com', 'nonce': 'abc123', 'qop': 'auth', 'algorithm': 'MD5'}
    header = auth.build_digest_header('GET', 'http://example.com/digest-auth')
    assert 'qop="auth"' in header
