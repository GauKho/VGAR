FREE_SHIPPING_FROM = 300_000
SHIPPING_FEE = 30_000


def shipping_fee(subtotal: int) -> int:
    return 0 if subtotal >= FREE_SHIPPING_FROM else SHIPPING_FEE
