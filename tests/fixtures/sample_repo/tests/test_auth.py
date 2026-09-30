from auth.service import login


def test_login() -> None:
    assert login("alice", "secret")
