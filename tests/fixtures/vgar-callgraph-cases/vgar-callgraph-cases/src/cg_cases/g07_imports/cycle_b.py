from . import cycle_a


def ping_b(n):
    return cycle_a.ping_a(n)  # expect: cg_cases.g07_imports.cycle_a.ping_a
