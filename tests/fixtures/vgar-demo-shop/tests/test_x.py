from shop.cart import Cart
from shop.checkout import checkout


def test_bug() -> None:
    cart = Cart()
    cart.add("BOOK", 2)
    cart.add("MUG", 1)

    receipt = checkout(cart, "SAVE10")

    assert receipt.subtotal == 500_000
    assert receipt.shipping == 0
    assert receipt.total == 495_000
