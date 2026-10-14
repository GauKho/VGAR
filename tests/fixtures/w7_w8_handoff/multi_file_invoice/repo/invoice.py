from pricing import discounted_price


def invoice_total(price, discount_percent, tax_percent):
    net = discounted_price(price, discount_percent)
    return net + tax_percent
