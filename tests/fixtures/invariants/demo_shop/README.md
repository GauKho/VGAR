# vgar-demo-shop

Small checkout library. Amounts are integer VND.

## Business rules

1. A coupon applies when the cart subtotal reaches the coupon's minimum order value.
2. Percent coupons take a percentage off the subtotal.
3. VAT is charged on the amount the customer pays after the discount.
4. Shipping is free from `FREE_SHIPPING_FROM`, otherwise `SHIPPING_FEE`. It is based on the
   subtotal before discount and is not subject to VAT.

Run the tests with `python -m pytest`.
