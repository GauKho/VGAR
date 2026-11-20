"""SPIKE (throwaway): Daikon (A) vs a Python Daikon-style miner (B) on vgar-demo-shop.

  python spike.py trace   <demo-shop> <work>   copy each variant, run its tests under the tracer
  python spike.py b       <work>               approach B: learn on base, check every variant
  python spike.py daikon  <work> <daikon.jar> <java>   approach A (the user runs it: Java)
  python spike.py report  <work>               table for both approaches

Variants: base (seeded bugs as shipped), the gold fix, behaviour-preserving refactors (should raise no
invariant violation) and mutants (behaviour changes; some are missed by the tests).
"""
from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

VARIANTS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "base": ("base", []),
    "gold_fix": ("fix", [("shop/discounts.py", "subtotal > coupon.min_order", "subtotal >= coupon.min_order"),
                         ("shop/checkout.py", "tax = vat(subtotal)", "tax = vat(subtotal - discount)")]),
    "R1_shipping_if_else": ("refactor", [("shop/shipping.py",
        "    return 0 if subtotal >= FREE_SHIPPING_FROM else SHIPPING_FEE",
        "    if subtotal >= FREE_SHIPPING_FROM:\n        return 0\n    return SHIPPING_FEE")]),
    "R2_checkout_rename_reorder": ("refactor", [("shop/checkout.py",
        "    subtotal = cart.subtotal()\n    discount = discount_amount(subtotal, coupon_code)\n"
        "    tax = vat(subtotal)\n    shipping = shipping_fee(subtotal)\n    total = subtotal - discount + tax + shipping\n"
        "    return Receipt(subtotal, discount, tax, shipping, total)",
        "    gross = cart.subtotal()\n    delivery = shipping_fee(gross)\n    off = discount_amount(gross, coupon_code)\n"
        "    vat_due = vat(gross)\n    return Receipt(gross, off, vat_due, delivery, gross - off + vat_due + delivery)")]),
    "R3_round_with_floor": ("refactor", [("shop/money.py", "    return int(amount + 0.5)",
                                          "    import math\n\n    return math.floor(amount + 0.5)")]),
    "R4_subtotal_loop": ("refactor", [("shop/cart.py",
        "        return sum(get_product(sku).unit_price * quantity for sku, quantity in self._quantities.items())",
        "        total = 0\n        for sku, quantity in self._quantities.items():\n"
        "            total += get_product(sku).unit_price * quantity\n        return total")]),
    "M1_shipping_boundary": ("mutant", [("shop/shipping.py", "subtotal >= FREE_SHIPPING_FROM", "subtotal > FREE_SHIPPING_FROM")]),
    "M2_discount_no_rounding": ("mutant", [("shop/discounts.py", "return round_vnd(subtotal * coupon.percent / 100)",
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
    "M8_eligible_ignores_minimum": ("mutant", [("shop/discounts.py", "return subtotal > coupon.min_order",
                                                "return subtotal > coupon.min_order or coupon.percent >= 20")]),
}


# ---------------------------------------------------------------- trace
def trace(shop: Path, work: Path) -> None:
    for name, (_, edits) in VARIANTS.items():
        target = work / "variants" / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(shop, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        for path, old, new in edits:
            file = target / path
            text = file.read_text(encoding="utf-8")
            assert text.count(old) == 1, (name, path, old)
            file.write_text(text.replace(old, new), encoding="utf-8")
        out = work / "traces" / name
        env = {**os.environ, "INV_PACKAGE": "shop", "INV_OUT": str(out), "PYTHONPATH": f"{HERE}{os.pathsep}{target}"}
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "tracer", "-p", "no:cacheprovider",
                        f"--junitxml={out / 'junit.xml'}"], cwd=target, env=env, capture_output=True, check=False)
        print(name, "traced")
    write_dtraces(work)


def _records(work: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in (work / "traces" / name / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def _prepare(records: list[dict], none_vars: set[tuple[str, str]]) -> list[dict]:
    """Stable object ids (from field values, equal across runs) and ``x_is_none`` flags for Daikon."""
    import zlib

    out = []
    for record in records:
        values = dict(record["vars"])
        for name, value in record["vars"].items():
            if isinstance(value, dict):
                fields = sorted((k, v) for k, v in record["vars"].items() if k.startswith(name + "."))
                values[name] = {**value, "__id__": zlib.crc32(json.dumps([value["__object__"], fields]).encode()) + 1}
        for ppt, name in none_vars:
            if ppt == record["ppt"] and name in record["vars"]:
                values[f"{name}_is_none"] = record["vars"][name] is None
        out.append(dict(record, vars=values))
    return out


def write_dtraces(work: Path) -> None:
    """Rewrite every variant's dtrace with the base run's declarations (Daikon checks need equal declarations)."""
    sys.path.insert(0, str(HERE))
    import tracer

    base = _records(work, "base")
    none_vars = {(r["ppt"], k) for r in base if r["kind"] != "raise" for k, v in r["vars"].items() if v is None
                 and k != "return"}
    types = tracer.daikon_types(_prepare(base, none_vars))
    for name in VARIANTS:
        tracer.write_daikon(_prepare(_records(work, name), none_vars), work / "traces" / name / "trace.dtrace", types)


def outcomes(work: Path, name: str) -> dict[str, str]:
    root = ET.parse(work / "traces" / name / "junit.xml").getroot()
    result = {}
    for case in root.iter("testcase"):
        key = f"{case.get('classname')}::{case.get('name')}"
        result[key] = "FAIL" if case.find("failure") is not None or case.find("error") is not None else "PASS"
    return result


# ---------------------------------------------------------------- approach B
def samples(work: Path, name: str) -> dict[str, list[dict]]:
    """Per program point (``ppt:::ENTER`` / ``ppt:::EXIT``), the primitive variables of each call."""
    points: dict[str, list[dict]] = defaultdict(list)
    for line in (work / "traces" / name / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["kind"] == "raise":
            continue
        values = {k: v for k, v in record["vars"].items() if not isinstance(v, dict)}
        points[f"{record['ppt']}:::{'ENTER' if record['kind'] == 'enter' else 'EXIT'}"].append(values)
    return points


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def learn(points: dict[str, list[dict]]) -> list[dict]:
    """Daikon-style templates: constant, one-of (<= 3 values), bounds, ==/</<= between numbers, y = a*x + b."""
    found = []
    for ppt, rows in sorted(points.items()):
        if len(rows) < 2:
            continue
        names = sorted({k for row in rows for k in row})
        columns = {n: [row.get(n, "__missing__") for row in rows] for n in names}
        numeric = [n for n in names if all(_number(v) for v in columns[n])]
        for n in names:
            values = columns[n]
            if "__missing__" in values:
                continue
            distinct = sorted(set(map(json.dumps, values)))
            if len(distinct) == 1:
                found.append({"ppt": ppt, "kind": "const", "var": n, "value": json.loads(distinct[0])})
            elif len(distinct) <= 3:
                found.append({"ppt": ppt, "kind": "one_of", "var": n, "values": [json.loads(d) for d in distinct]})
            if n in numeric and len(distinct) > 3:
                found.append({"ppt": ppt, "kind": "range", "var": n, "min": min(values), "max": max(values)})
            if n in numeric and len(distinct) > 1 and min(values) >= 0:
                found.append({"ppt": ppt, "kind": "nonneg", "var": n})
        if len(rows) < 3:
            continue
        for x, y in itertools.combinations(numeric, 2):
            xs, ys = columns[x], columns[y]
            if len(set(xs)) == 1 and len(set(ys)) == 1:
                continue  # both constant: already reported
            for op, test in (("==", lambda a, b: a == b), ("<", lambda a, b: a < b), ("<=", lambda a, b: a <= b),
                             (">", lambda a, b: a > b), (">=", lambda a, b: a >= b)):
                if all(test(a, b) for a, b in zip(xs, ys)):
                    found.append({"ppt": ppt, "kind": "cmp", "var": x, "op": op, "other": y})
                    break
            points_xy = sorted(set(zip(xs, ys)))
            if len({a for a, _ in points_xy}) >= 3:
                (x1, y1), (x2, y2) = points_xy[0], points_xy[-1]
                if x2 != x1:
                    a = (y2 - y1) / (x2 - x1)
                    b = y1 - a * x1
                    if a != 0 and all(abs(a * px + b - py) <= 1e-6 * max(1, abs(py)) for px, py in points_xy) \
                            and not (a == 1 and b == 0):
                        found.append({"ppt": ppt, "kind": "linear", "var": y, "other": x, "a": a, "b": b})
    return found


def holds(inv: dict, row: dict) -> bool | None:
    if inv["var"] not in row or ("other" in inv and inv["other"] not in row):
        return None
    v = row[inv["var"]]
    kind = inv["kind"]
    if kind == "const":
        return v == inv["value"]
    if kind == "one_of":
        return v in inv["values"]
    if not _number(v):
        return False
    if kind == "range":
        return inv["min"] <= v <= inv["max"]
    if kind == "nonneg":
        return v >= 0
    w = row[inv["other"]]
    if not _number(w):
        return False
    if kind == "cmp":
        return {"==": v == w, "<": v < w, "<=": v <= w, ">": v > w, ">=": v >= w}[inv["op"]]
    return abs(inv["a"] * w + inv["b"] - v) <= 1e-6 * max(1, abs(v))


def describe(inv: dict) -> str:
    kind = inv["kind"]
    if kind == "const":
        return f"{inv['var']} == {inv['value']!r}"
    if kind == "one_of":
        return f"{inv['var']} one of {inv['values']!r}"
    if kind == "range":
        return f"{inv['min']} <= {inv['var']} <= {inv['max']}"
    if kind == "nonneg":
        return f"{inv['var']} >= 0"
    if kind == "cmp":
        return f"{inv['var']} {inv['op']} {inv['other']}"
    return f"{inv['var']} == {inv['a']:g} * {inv['other']} + {inv['b']:g}"


def approach_b(work: Path) -> None:
    base = samples(work, "base")
    invariants = learn(base)
    out = work / "b"
    out.mkdir(parents=True, exist_ok=True)
    by_ppt = defaultdict(list)
    for inv in invariants:
        by_ppt[inv["ppt"]].append(describe(inv))
    (out / "base_invariants.txt").write_text(
        "\n".join(f"=== {ppt}\n" + "\n".join(lines) for ppt, lines in by_ppt.items()) + "\n", encoding="utf-8")
    result = {"invariants": len(invariants), "variants": {}}
    for name in VARIANTS:
        points = samples(work, name)
        violated = sorted({f"{inv['ppt']}  {describe(inv)}" for inv in invariants
                           for row in points.get(inv["ppt"], []) if holds(inv, row) is False})
        result["variants"][name] = {"violations": violated,
                                    "new_points": sorted(set(points) - set(base)),
                                    "unexercised_points": sorted(set(base) - set(points))}
    (out / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("B invariants:", len(invariants))


# ---------------------------------------------------------------- approach A (Java, run by the user)
def approach_a(work: Path, jar: Path, java: str) -> None:
    out = work / "a"
    out.mkdir(parents=True, exist_ok=True)

    def run(args: list[str], target: Path) -> None:
        process = subprocess.run([java, "-cp", str(jar), *args], capture_output=True, text=True, check=False)
        target.write_text(process.stdout + "\n--- stderr ---\n" + process.stderr, encoding="utf-8")
        print(" ".join(args[:1]), "->", target.name, "rc", process.returncode)

    inv = out / "base.inv.gz"
    run(["daikon.Daikon", "--no_text_output", "-o", str(inv), str(work / "traces" / "base" / "trace.dtrace")],
        out / "daikon_base.log")
    run(["daikon.PrintInvariants", str(inv)], out / "base_invariants.txt")
    for name in VARIANTS:
        run(["daikon.tools.InvariantChecker", "--verbose", str(inv), str(work / "traces" / name / "trace.dtrace")],
            out / f"check_{name}.txt")


def daikon_counts(work: Path) -> tuple[int | None, dict[str, list[str]]]:
    out = work / "a"
    printed = out / "base_invariants.txt"
    if not printed.exists():
        return None, {}
    lines = printed.read_text(encoding="utf-8").split("--- stderr ---")[0].splitlines()
    count = sum(1 for line in lines if line.strip() and not line.startswith(("====", "Daikon", "shop.")))
    checks = {}
    for name in VARIANTS:
        file = out / f"check_{name}.txt"
        if file.exists():
            text = file.read_text(encoding="utf-8").split("--- stderr ---")[0]
            found = set()
            for match in re.finditer(r"At ppt (\S.*?):::(ENTER|EXIT)\d*, Invariant '(.*?)' invalidated", text):
                found.add(f"{match.group(1)}:::{match.group(2)}  {match.group(3)}")
            if "Unexpected end of dtrace record" in file.read_text(encoding="utf-8"):
                found.add("READ ERROR")
            checks[name] = sorted(found)
    return count, checks


# ---------------------------------------------------------------- report
def report(work: Path) -> None:
    b = json.loads((work / "b" / "result.json").read_text(encoding="utf-8"))
    a_count, a_checks = daikon_counts(work)
    base_tests = outcomes(work, "base")
    lines = ["# Invariant spike: Daikon (A) vs Python Daikon-style miner (B) on vgar-demo-shop", "",
             f"Invariants learned on base: A = {a_count if a_count is not None else 'not run'}, B = {b['invariants']}", "",
             "| Variant | Kind | Tests changed vs base | A violations | B violations |", "|---|---|---|---:|---:|"]
    for name, (kind, _) in VARIANTS.items():
        tests = outcomes(work, name)
        changed = sorted(t.split("::")[-1] for t in tests if tests[t] != base_tests.get(t))
        a = len(a_checks[name]) if name in a_checks else "n/a"
        lines.append(f"| {name} | {kind} | {', '.join(changed) or '-'} | {a} | {len(b['variants'][name]['violations'])} |")
    lines += ["", "## A violations per variant", ""]
    for name, found in a_checks.items():
        if found:
            lines.append(f"- **{name}**: " + "; ".join(found[:8]) + (f" (+{len(found) - 8} more)" if len(found) > 8 else ""))
    lines += ["", "## B violations per variant", ""]
    for name, data in b["variants"].items():
        if data["violations"]:
            lines.append(f"- **{name}**: " + "; ".join(data["violations"][:8])
                         + (f" (+{len(data['violations']) - 8} more)" if len(data["violations"]) > 8 else ""))
    (work / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    if command == "trace":
        trace(Path(rest[0]), Path(rest[1]))
    elif command == "b":
        approach_b(Path(rest[0]))
    elif command == "daikon":
        approach_a(Path(rest[0]), Path(rest[1]), rest[2])
    elif command == "report":
        report(Path(rest[0]))
