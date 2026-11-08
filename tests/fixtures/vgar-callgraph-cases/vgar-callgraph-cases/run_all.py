"""Run every group. Usage: PYTHONPATH=src python run_all.py"""
from cg_cases import (
    g01_direct,
    g02_polymorphism,
    g03_same_name,
    g04_higher_order,
    g05_inheritance,
    g06_class_calls,
    g08_noise,
    g09_threshold,
    g10_dynamic,
    g11_conflict,
)
from cg_cases.g07_imports import runner as g07_imports

MODULES = (
    g01_direct,
    g02_polymorphism,
    g03_same_name,
    g04_higher_order,
    g05_inheritance,
    g06_class_calls,
    g07_imports,
    g08_noise,
    g09_threshold,
    g10_dynamic,
    g11_conflict,
)

if __name__ == "__main__":
    for module in MODULES:
        module.main()
    print(f"ok: {len(MODULES)} groups ran")
