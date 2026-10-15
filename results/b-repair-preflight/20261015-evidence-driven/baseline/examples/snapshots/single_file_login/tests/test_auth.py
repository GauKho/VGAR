from auth import login


def test_login_rejects_whitespace():
    assert login("   ") is False


def test_login_accepts_name():
    assert login("alice") is True
