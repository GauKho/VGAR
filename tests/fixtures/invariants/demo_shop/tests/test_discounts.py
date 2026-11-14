import pytest

from shop.discounts import discount_amount


def test_no_coupon_gives_no_discount() -> None:
    assert discount_amount(900_000, None) == 0


def test_percent_discount_above_minimum() -> None:
    assert discount_amount(900_000, "SAVE10") == 90_000


def test_no_discount_below_minimum() -> None:
    assert discount_amount(499_999, "SAVE10") == 0


def test_unknown_coupon_is_rejected() -> None:
    with pytest.raises(ValueError):
        discount_amount(900_000, "NOPE")
