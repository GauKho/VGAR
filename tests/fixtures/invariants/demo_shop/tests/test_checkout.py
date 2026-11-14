from shop.cart import Cart
from shop.checkout import checkout


def test_checkout_without_coupon() -> None:
    cart = Cart()
    cart.add("BOOK", 1)
    receipt = checkout(cart)
    assert (receipt.discount, receipt.tax, receipt.shipping, receipt.total) == (0, 20_000, 30_000, 250_000)


def test_coupon_below_minimum_changes_nothing() -> None:
    cart = Cart()
    cart.add("BOOK", 2)
    assert checkout(cart, "SAVE10") == checkout(cart)
