from dataclasses import dataclass

from shop.money import round_vnd


@dataclass(frozen=True)
class Coupon:
    code: str
    percent: int
    min_order: int


COUPONS = {
    "SAVE10": Coupon("SAVE10", 10, 500_000),
    "SAVE20": Coupon("SAVE20", 20, 2_000_000),
}


def get_coupon(code: str) -> Coupon:
    try:
        return COUPONS[code]
    except KeyError:
        raise ValueError(f"Unknown coupon: {code}") from None


def is_eligible(coupon: Coupon, subtotal: int) -> bool:
    return subtotal > coupon.min_order


def discount_amount(subtotal: int, code: str | None) -> int:
    if code is None:
        return 0
    coupon = get_coupon(code)
    if not is_eligible(coupon, subtotal):
        return 0
    return round_vnd(subtotal * coupon.percent / 100)
