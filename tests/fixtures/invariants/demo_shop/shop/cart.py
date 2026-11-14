from shop.catalog import get_product


class Cart:
    def __init__(self) -> None:
        self._quantities: dict[str, int] = {}

    def add(self, sku: str, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        get_product(sku)
        self._quantities[sku] = self._quantities.get(sku, 0) + quantity

    def subtotal(self) -> int:
        return sum(get_product(sku).unit_price * quantity for sku, quantity in self._quantities.items())
