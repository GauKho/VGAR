from shop.money import round_vnd

VAT_PERCENT = 10


def vat(taxable_amount: int) -> int:
    return round_vnd(taxable_amount * VAT_PERCENT / 100)
