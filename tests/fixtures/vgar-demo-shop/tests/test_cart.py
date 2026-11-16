import pytest

from shop.cart import Cart


def test_subtotal_sums_quantities() -> None:
    cart = Cart()
    cart.add("PEN", 2)
    cart.add("PEN", 1)
    cart.add("MUG")
    assert cart.subtotal() == 145_000


def test_rejects_unknown_sku_and_bad_quantity() -> None:
    cart = Cart()
    with pytest.raises(ValueError):
        cart.add("NOPE")
    with pytest.raises(ValueError):
        cart.add("PEN", 0)
