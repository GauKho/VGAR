from shop.cart import Cart
from shop.checkout import checkout


def test_checkout_without_coupon() -> None:
    cart = Cart()
    cart.add("BOOK", 1)
    receipt = checkout(cart)
    assert (receipt.discount, receipt.tax, receipt.shipping, receipt.total) == (0, 20_000, 30_000, 250_000)


def test_tax_is_charged_after_coupon_discount() -> None:
    cart = Cart()
    cart.add("BOOK", 3)
    receipt = checkout(cart, "SAVE10")
    assert (receipt.subtotal, receipt.discount, receipt.tax, receipt.shipping, receipt.total) == (600_000, 60_000, 54_000, 0, 594_000)


def test_coupon_below_minimum_changes_nothing() -> None:
    cart = Cart()
    cart.add("BOOK", 2)
    assert checkout(cart, "SAVE10") == checkout(cart)
