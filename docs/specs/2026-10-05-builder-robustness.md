# Graph Builder Robustness — Spec

**Date:** 2026-10-05
**Owner:** M1
**Status:** Draft — blocks Week 5-6 evaluation

---

## Problem

`PythonGraphBuilder._link_inheritance()` and `_resolve_calls()` both do `self.modules[module_name]` without checking whether the module exists. When a file fails to parse (encoding error, unsupported syntax, file-too-large skip), the module is removed from `self.modules` via the rollback in `_extract_file`, but class records and call records referencing that module remain in `self.classes` and `self.calls`. This causes an unrecoverable `KeyError` that kills the entire graph build for any repository containing even one problematic module.

All 9/25 tasks in the graph run `20261005T090644654026Z-fcd8ac1549ac` failed with this same pattern:
```
astropy__astropy-13398: KeyError: 'astropy.io.fits.card'
django__django-11138:   KeyError: 'tests.admin_utils.tests'
matplotlib__matplotlib-14623: KeyError: 'lib.matplotlib.backends.backend_qt5'
```

---

## Goal

Graph builder must never crash on a missing module. It should skip the orphaned class/call record and continue building the rest of the graph. Failed-file statistics must remain accurate.

---

## Non-Goals

- Do not fix the underlying cause of module parse failures (out of scope for this spec).
- Do not change the `_extract_file` rollback logic.
- Do not modify the graph document schema or output format.

---

## Design

### Fix 1: `_link_inheritance()` — guard module lookup

**File:** `src/vgar/graph/builder.py:779-804`

Before accessing `self.modules[record.module_name]`, check membership. If the module is missing, log a warning via `skipped_failed_files` and `continue` to the next record.

```python
def _link_inheritance(self) -> None:
    for record in self.classes:
        if record.module_name not in self.modules:
            continue  # module was rolled back; skip this class record
        module = self.modules[record.module_name]
        # ... rest unchanged
```

### Fix 2: `_resolve_calls()` — guard module lookup

**File:** `src/vgar/graph/builder.py:806-...`

Same pattern at line 809: guard the `self.modules[call.module_name]` access.

```python
def _resolve_calls(self) -> None:
    test_targets: dict[tuple[str, str], float] = {}
    for call in self.calls:
        if call.module_name not in self.modules:
            continue  # module was rolled back; skip this call record
        module = self.modules[call.module_name]
        # ... rest unchanged
```

---

## Test Requirements

### Unit test: builder survives missing module during inheritance link

**File:** `tests/test_graph_builder_robustness.py`

Create a repo where:
- `pkg/good.py` defines `class Base: pass`
- `pkg/bad.py` defines `class Derived(Base): pass` but `bad.py` is flagged as a "failed file" (using monkeypatch to raise during `_extract_file`)

After build:
- `document["statistics"]["failed_file_count"] == 1`
- No `KeyError` raised
- `Derived` class node is absent (rolled back with its module)
- `Base` class node is present

### Unit test: builder survives missing module during call resolution

**File:** `tests/test_graph_builder_robustness.py`

Create a repo where:
- `pkg/good.py` defines `def good_func(): return 1` and `def caller(): good_func()`
- `pkg/bad.py` defines `def bad_caller(): good_func()` but `bad.py` fails during extraction

After build:
- `document["statistics"]["failed_file_count"] == 1`
- No `KeyError` raised
- `caller` → `good_func` CALL edge exists
- No CALL edges reference nodes from `bad.py`

---

## Definition of Done

- [ ] `_link_inheritance()` guards missing module
- [ ] `_resolve_calls()` guards missing module
- [ ] 2 new unit tests in `tests/test_graph_builder_robustness.py` pass
- [ ] Existing 5 robustness tests still pass
- [ ] `run_graph_retrieval.py` succeeds on all 25 tasks in the dev manifest
- [ ] Git commit includes all changes

---

## Impact on Other Teams

- **M2/M3:** Graph build success rate improves from ~36% (9/25) to ~100%. Evaluation pipeline unblocked.
- **No contract changes:** Output schema, node types, edge types are unchanged.
