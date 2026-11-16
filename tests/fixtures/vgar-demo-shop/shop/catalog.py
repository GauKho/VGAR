from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    unit_price: int


PRODUCTS = {
    "BOOK": Product("BOOK", "Python handbook", 200_000),
    "MUG": Product("MUG", "Coffee mug", 100_000),
    "PEN": Product("PEN", "Gel pen", 15_000),
}


def get_product(sku: str) -> Product:
    try:
        return PRODUCTS[sku]
    except KeyError:
        raise ValueError(f"Unknown SKU: {sku}") from None
