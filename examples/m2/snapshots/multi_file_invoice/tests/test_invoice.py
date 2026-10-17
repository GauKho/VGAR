from invoice import invoice_total
from pricing import discounted_price


def test_discount_percentage():
    assert discounted_price(200, 10) == 180


def test_invoice_percentage_tax():
    assert invoice_total(200, 10, 5) == 189


def test_invoice_without_adjustments():
    assert invoice_total(200, 0, 0) == 200
