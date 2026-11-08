"""Circular import with cycle_b (module-level, both directions)."""
from . import cycle_b


def ping_a(n):
    if n <= 0:
        return "a"
    return cycle_b.ping_b(n - 1)  # expect: cg_cases.g07_imports.cycle_b.ping_b
