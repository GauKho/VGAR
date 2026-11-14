"""Run the demo-shop fixture (buggy base) or an edited copy under the L5-1 trace plugin."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_SHOP = ROOT / "tests" / "fixtures" / "invariants" / "demo_shop"

# Variants of the 14/11 spike (scripts/invariant_spike/spike.py): (kind, [(file, old, new)]).
VARIANTS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "base": ("base", []),
    "gold_fix": ("fix", [("shop/discounts.py", "subtotal > coupon.min_order", "subtotal >= coupon.min_order"),
                         ("shop/checkout.py", "tax = vat(subtotal)", "tax = vat(subtotal - discount)")]),
    "R1_shipping_if_else": ("refactor", [("shop/shipping.py",
        "    return 0 if subtotal >= FREE_SHIPPING_FROM else SHIPPING_FEE",
        "    if subtotal >= FREE_SHIPPING_FROM:\n        return 0\n    return SHIPPING_FEE")]),
    "R2_checkout_rename_reorder": ("refactor", [("shop/checkout.py",
        ("    subtotal = cart.subtotal()\n    discount = discount_amount(subtotal, coupon_code)\n"
        "    tax = vat(subtotal)\n    shipping = shipping_fee(subtotal)\n    total = subtotal - discount + tax + shipping\n"
        "    return Receipt(subtotal, discount, tax, shipping, total)"),
        ("    gross = cart.subtotal()\n    delivery = shipping_fee(gross)\n    off = discount_amount(gross, coupon_code)\n"
        "    vat_due = vat(gross)\n    return Receipt(gross, off, vat_due, delivery, gross - off + vat_due + delivery)"))]),
    "R3_round_with_floor": ("refactor", [("shop/money.py", "    return int(amount + 0.5)",
                                          "    import math\n\n    return math.floor(amount + 0.5)")]),
    "R4_subtotal_loop": ("refactor", [("shop/cart.py",
        "        return sum(get_product(sku).unit_price * quantity for sku, quantity in self._quantities.items())",
        ("        total = 0\n        for sku, quantity in self._quantities.items():\n"
        "            total += get_product(sku).unit_price * quantity\n        return total"))]),
    "M1_shipping_boundary": ("miss", [("shop/shipping.py", "subtotal >= FREE_SHIPPING_FROM", "subtotal > FREE_SHIPPING_FROM")]),
    "M2_discount_no_rounding": ("miss", [("shop/discounts.py", "return round_vnd(subtotal * coupon.percent / 100)",
                                          "return int(subtotal * coupon.percent / 100)")]),
    "M3_total_without_shipping": ("mutant", [("shop/checkout.py", "total = subtotal - discount + tax + shipping",
                                              "total = subtotal - discount + tax")]),
    "M4_vat_floor_division": ("mutant", [("shop/tax.py", "taxable_amount * VAT_PERCENT / 100",
                                          "taxable_amount * VAT_PERCENT // 100")]),
    "M5_product_name_upper": ("mutant", [("shop/catalog.py", "        return PRODUCTS[sku]",
        "        product = PRODUCTS[sku]\n        return Product(product.sku, product.name.upper(), product.unit_price)")]),
    "M6_default_coupon": ("mutant", [("shop/checkout.py", "discount_amount(subtotal, coupon_code)",
                                      "discount_amount(subtotal, coupon_code or \"SAVE10\")")]),
    "M7_zero_quantity_allowed": ("mutant", [("shop/cart.py", "if quantity <= 0:", "if quantity < 0:")]),
    "M8_eligible_ignores_minimum": ("miss", [("shop/discounts.py", "return subtotal > coupon.min_order",
                                              "return subtotal > coupon.min_order or coupon.percent >= 20")]),
}


def run_variant(name: str, work: Path) -> tuple[Path, dict[str, str]]:
    """Copy the demo shop, apply the variant, run its tests traced; return (trace folder, outcomes by nodeid)."""
    repo, trace = work / name / "repo", work / name / "trace"
    shutil.copytree(DEMO_SHOP, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for path, old, new in VARIANTS[name][1]:
        file = repo / path
        text = file.read_text(encoding="utf-8")
        assert text.count(old) == 1, (name, path)
        file.write_text(text.replace(old, new), encoding="utf-8")
    junit = work / name / "junit.xml"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "-p", "vgar.repair.invariant_trace_plugin", f"--vgar-trace-dir={trace}", f"--junitxml={junit}"],
                   cwd=repo, env=env, capture_output=True, check=False)
    outcomes = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        nodeid = case.get("classname").replace(".", "/") + ".py::" + case.get("name")
        outcomes[nodeid] = "FAIL" if case.find("failure") is not None or case.find("error") is not None else "PASS"
    return trace, outcomes
