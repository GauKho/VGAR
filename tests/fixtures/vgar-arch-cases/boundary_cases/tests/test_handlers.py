from api.handlers import create_order


def test_create_order():
    assert create_order(5)
