from app import answer


def test_required():
    assert answer() == 2


def test_regression():
    assert isinstance(answer(), int)
