from shop.tax import vat


def test_vat_is_ten_percent() -> None:
    assert vat(450_000) == 45_000


def test_vat_rounds_half_up() -> None:
    assert vat(15) == 2
