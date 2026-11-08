from app.service import login


def test_login():
    assert login("x")
