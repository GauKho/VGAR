from dataclasses import dataclass

from shop.cart import Cart
from shop.discounts import discount_amount
from shop.shipping import shipping_fee
from shop.tax import vat


@dataclass(frozen=True)
class Receipt:
    subtotal: int
    discount: int
    tax: int
    shipping: int
    total: int


def checkout(cart: Cart, coupon_code: str | None = None) -> Receipt:
    subtotal = cart.subtotal()
    discount = discount_amount(subtotal, coupon_code)
    tax = vat(subtotal)
    shipping = shipping_fee(subtotal)
    total = subtotal - discount + tax + shipping
    return Receipt(subtotal, discount, tax, shipping, total)
