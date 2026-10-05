# Graph Builder Robustness + Evaluation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the graph builder crash on missing modules (blocking all real-repo graph builds) and then complete the Week 5-6 Graph vs BM25 evaluation comparison.

**Architecture:** Two-phase plan. Phase 1 fixes `PythonGraphBuilder._link_inheritance()` and `_resolve_calls()` to guard against missing modules from rolled-back files. Phase 2 runs the full evaluation pipeline: graph arm retrieval → compare script → REPORT.md → manual inspection notes.

**Tech Stack:** Python 3.11, tree-sitter-python, pytest, stdlib only for builder; evaluation uses json/pathlib/statistics.

**Specs:**
- `docs/specs/2026-10-05-builder-robustness.md`
- `docs/specs/2026-10-05-evaluation-pipeline.md`

## Global Constraints

- Do not change graph document schema (node types, edge types, field names).
- `tokenizers>=0.22.0,<=0.23.0` and `transformers>=4.51.0,<5` (already pinned in pyproject.toml).
- All tests must pass before any task is considered done.
- Commit after each task, not after the whole plan.

## Review Focus

1. **Orphaned class from failed module:** Class record exists but module was rolled back — builder must skip without KeyError.
2. **Orphaned call from failed module:** Call record references a module that doesn't exist — builder must skip without KeyError.
3. **Partial rollback consistency:** Nodes/edges from failed file must be fully removed; no dangling references remain.
4. **Graph run produces both arms:** `run_graph_retrieval.py` must write `graph` and `graph_f2p` arms per task.
5. **Compare script validates inputs:** Passing a BM25-only run as "graph run" gives a clear error, not KeyError.

---

## Task 1: Add module-missing guard to `_link_inheritance()`

**Files:**
- Modify: `src/vgar/graph/builder.py:779-804`
- Test: `tests/test_graph_builder_robustness.py`

**Interfaces:**
- Consumes: `self.modules: dict[str, _ModuleState]`, `self.classes: list[_ClassRecord]`
- Produces: No schema change; graph builds successfully when some modules are missing

- [ ] **Step 1: Write the failing test**

Add to `tests/test_graph_builder_robustness.py`:

```python
def test_orphaned_class_from_failed_module_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "src/pkg/good.py", "class Base: pass\n")
    _write(tmp_path, "src/pkg/bad.py", "class Derived(Base): pass\n")

    original = PythonGraphBuilder._extract_file

    def flaky(self, root, file_path, repository_id):  # type: ignore[no-untyped-def]
        relative = file_path.relative_to(root)
        if relative.as_posix().endswith("bad.py"):
            raise RuntimeError("synthetic parse failure in bad.py")
        return original(self, root, file_path, repository_id)

    monkeypatch.setattr(PythonGraphBuilder, "_extract_file", flaky)
    document = _build(tmp_path)

    assert document["statistics"]["failed_file_count"] == 1
    assert any("bad.py" in f["path"] for f in document["statistics"]["failed_files"])
    # No KeyError raised above; build completed
    paths = {n["path"] for n in document["nodes"] if n.get("path")}
    assert paths == {"src/pkg/good.py"}
    classes = [n for n in document["nodes"] if n["type"] == "Class"]
    class_names = {n["name"] for n in classes}
    assert "Base" in class_names
    assert "Derived" not in class_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_builder_robustness.py::test_orphaned_class_from_failed_module_does_not_crash -v`
Expected: FAIL with `KeyError: 'pkg.bad'` (or similar) from `_link_inheritance`

- [ ] **Step 3: Write minimal implementation**

In `src/vgar/graph/builder.py`, modify `_link_inheritance()`:

```python
def _link_inheritance(self) -> None:
    for record in self.classes:
        if record.module_name not in self.modules:
            continue
        module = self.modules[record.module_name]
        # ... rest of method unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_builder_robustness.py::test_orphaned_class_from_failed_module_does_not_crash -v`
Expected: PASS

- [ ] **Step 5: Run all robustness tests**

Run: `pytest tests/test_graph_builder_robustness.py -v`
Expected: 6 passed (5 existing + 1 new)

- [ ] **Step 6: Commit**

```bash
git add src/vgar/graph/builder.py tests/test_graph_builder_robustness.py
git commit -m "fix: guard _link_inheritance against missing modules from rolled-back files"
```

---

## Task 2: Add module-missing guard to `_resolve_calls()`

**Files:**
- Modify: `src/vgar/graph/builder.py:806+`
- Test: `tests/test_graph_builder_robustness.py`

**Interfaces:**
- Consumes: `self.modules`, `self.calls`
- Produces: Graph builds successfully when call records reference missing modules

- [ ] **Step 1: Write the failing test**

Add to `tests/test_graph_builder_robustness.py`:

```python
def test_orphaned_call_from_failed_module_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "src/pkg/good.py", "def target():\n    return 1\n\ndef caller():\n    return target()\n")
    _write(tmp_path, "src/pkg/bad.py", "def bad_caller():\n    return target()\n")

    original = PythonGraphBuilder._extract_file

    def flaky(self, root, file_path, repository_id):  # type: ignore[no-untyped-def]
        relative = file_path.relative_to(root)
        if relative.as_posix().endswith("bad.py"):
            raise RuntimeError("synthetic parse failure in bad.py")
        return original(self, root, file_path, repository_id)

    monkeypatch.setattr(PythonGraphBuilder, "_extract_file", flaky)
    document = _build(tmp_path)

    assert document["statistics"]["failed_file_count"] == 1
    paths = {n["path"] for n in document["nodes"] if n.get("path")}
    assert paths == {"src/pkg/good.py"}
    # caller -> target CALL edge should still exist
    call_edges = [e for e in document["edges"] if e["type"] == "CALLS"]
    assert len(call_edges) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_builder_robustness.py::test_orphaned_call_from_failed_module_does_not_crash -v`
Expected: FAIL with `KeyError` from `_resolve_calls`

- [ ] **Step 3: Write minimal implementation**

In `src/vgar/graph/builder.py`, at the top of the loop in `_resolve_calls()`:

```python
def _resolve_calls(self) -> None:
    test_targets: dict[tuple[str, str], float] = {}
    for call in self.calls:
        if call.module_name not in self.modules:
            continue
        module = self.modules[call.module_name]
        # ... rest of method unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_builder_robustness.py::test_orphaned_call_from_failed_module_does_not_crash -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -q`
Expected: 194 passed, 1 skipped (all tests pass)

- [ ] **Step 6: Commit**

```bash
git add src/vgar/graph/builder.py tests/test_graph_builder_robustness.py
git commit -m "fix: guard _resolve_calls against missing modules from rolled-back files"
```

---

## Task 3: Verify graph build succeeds on real repos

**Files:**
- No code changes (verification only)
- Check: `results/retrieval/`

**Interfaces:**
- Consumes: Fixed builder from Tasks 1-2
- Produces: Confirmed graph build works on astropy, django, matplotlib, etc.

- [ ] **Step 1: Re-run graph retrieval to verify fix**

```bash
rm -rf data/graphs  # clear stale cache (builder.py hash unchanged, but we want fresh verification)
python scripts/run_graph_retrieval.py . \
    data/manifests/verified-c104f840cc67-dev-25.json \
    --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json \
    --budget-tokens 8000
```

- [ ] **Step 2: Check result**

Run:
```bash
python -c "
import json
d = json.load(open('results/retrieval/20261005T090644654026Z-fcd8ac1549ac/result.json'))
succeeded = sum(1 for t in d['task_results'] if t['status'] == 'SUCCEEDED')
print(f'Succeeded: {succeeded}/{len(d[\"task_results\"])}')
if succeeded < len(d['task_results']):
    for t in d['task_results']:
        if t['status'] != 'SUCCEEDED':
            print(f'  FAIL {t[\"instance_id\"]}: {t.get(\"error_class\")}: {str(t.get(\"error\",\"\"))[:100]}')
"
```
Expected: All 25 SUCCEEDED (or ≥ 20 with documented failures)

- [ ] **Step 3: Note any remaining failures**

If any tasks still fail, record the error and decide: skip for now (document as known limitation) or investigate further. Do NOT block evaluation on this — proceed to Task 4 with whatever tasks succeeded.

- [ ] **Step 4: Commit any documentation of findings**

```bash
git add docs/
git commit -m "docs: record graph build verification results on real repos"
```

---

## Task 4: Run BM25 baseline (reuse existing run)

**Files:**
- No changes needed — run already exists

**Known-good run:** `results/retrieval/20261005T045625580136Z-7fa20ac5dd80`

- [ ] **Step 1: Verify BM25 run is valid for comparison**

Run:
```bash
python -c "
import json
d = json.load(open('results/retrieval/20261005T045625580136Z-7fa20ac5dd80/result.json'))
assert d['complete']
assert d['kind'] == 'retrieval'
arms = set(t.get('arm') for t in d['task_results'] if t['status'] == 'SUCCEEDED')
print(f'BM25 run OK: {len(d[\"task_results\"])} tasks, arms={arms}')
print(f'Config: budget={d[\"config\"][\"budget_tokens\"]}, counter={d[\"config\"][\"counter_label\"][:40]}...')
"
```
Expected: `BM25 run OK: 25 tasks, arms={'bm25'}`

- [ ] **Step 2: Note the run ID for use in Task 6**

Save: `BM25_RUN=20261005T045625580136Z-7fa20ac5dd80`

---

## Task 5: Run Graph arm retrieval

**Files:**
- No code changes (uses fixed builder)

- [ ] **Step 1: Run graph retrieval**

```bash
python scripts/run_graph_retrieval.py . \
    data/manifests/verified-c104f840cc67-dev-25.json \
    --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json \
    --budget-tokens 8000
```

- [ ] **Step 2: Capture the new run directory**

Run:
```bash
python -c "
import json, glob, os
runs = sorted(glob.glob('results/retrieval/*/result.json'))
latest = max(runs, key=lambda p: os.path.getmtime(p))
d = json.load(open(latest))
print(os.path.basename(os.path.dirname(latest)))
print(f'kind={d[\"kind\"]} tasks={len(d[\"task_results\"])} arms={set(t.get(\"arm\") for t in d[\"task_results\"])}')
"
```
Save the run ID as `GRAPH_RUN`.

- [ ] **Step 3: Verify graph run has both arms**

Run:
```bash
python -c "
import json, glob, os
runs = sorted(glob.glob('results/retrieval/*/result.json'))
latest = max(runs, key=lambda p: os.path.getmtime(p))
d = json.load(open(latest))
arms = set(t.get('arm') for t in d['task_results'] if t['status'] == 'SUCCEEDED')
print(f'Arms found: {arms}')
assert arms >= {'graph', 'graph_f2p'}, f'Expected both arms, got {arms}'
print('Graph run valid for comparison')
"
```
Expected: `Arms found: {'graph', 'graph_f2p'}`

---

## Task 6: Run comparison and generate REPORT.md

**Files:**
- No code changes (compare script already fixed in previous session)

- [ ] **Step 1: Run the comparison script**

```bash
python scripts/compare_graph_vs_bm25.py . \
    results/retrieval/<BM25_RUN> \
    results/retrieval/<GRAPH_RUN>
```

- [ ] **Step 2: Verify output**

Run:
```bash
ls results/retrieval/*/REPORT.md | tail -1 | xargs head -80
```
Expected: REPORT.md with tables showing Recall@3/5/10 for both graph and bm25

- [ ] **Step 3: Verify result.json structure**

```bash
python -c "
import json
import glob, os
cmp_runs = sorted(glob.glob('results/retrieval/*/result.json'))
cmp_runs = [r for r in cmp_runs if 'graph_vs_bm25' in r or True]
# Find the latest comparison run
latest_cmp = max((r for r in cmp_runs if 'graph_vs_bm25' in r or True),
                 key=lambda p: os.path.getmtime(p))
# Actually find the one with 'COMPARED' status
for r in sorted(cmp_runs, key=lambda p: os.path.getmtime(p)):
    d = json.load(open(r))
    if d.get('status') == 'COMPARED':
        latest_cmp = r
        break
d = json.load(open(latest_cmp))
print(f'Status: {d[\"status\"]}')
print(f'Paired tasks: {d[\"paired_tasks\"]}')
print(f'Summaries: {list(d.get(\"summaries\", {}).keys())}')
for arm, metrics in d.get('summaries', {}).items():
    m = metrics.get('metrics', {})
    print(f'  {arm}: file_recall@5={m.get(\"file_recall@5\"):.3f} func_recall@5={m.get(\"function_recall@5\"):.3f}')
"
```

---

## Task 7: Manual inspection of 10 tasks

**Files:**
- Create: `docs/m5_m6_retrieval_evaluation.md`

- [ ] **Step 1: Identify top wins and losses from comparison**

The comparison REPORT.md includes an `inspection` section listing top 3 graph-wins and top 3 graph-losses by delta. Pick 5 from wins and 5 from losses (10 total).

- [ ] **Step 2: For each task, inspect the actual candidates**

For each selected task ID, run:
```bash
python -c "
import json
# Get BM25 top-5
bm_task = json.load(open('results/retrieval/<BM25_RUN>/tasks/<instance_id>.json'))
print('=== BM25 Top-5 ===')
for i, chunk_id in enumerate(bm_task['rank_order'][:5]):
    chunk = bm_task['candidate_map'][chunk_id]
    print(f'  {i+1}. {chunk[\"path\"]}::{chunk.get(\"symbol\",\"\")} (kind={chunk[\"kind\"]})')

# Get Graph top-5 from graph task
gr_task = json.load(open('results/retrieval/<GRAPH_RUN>/tasks/<instance_id>.json'))
print('=== Graph Top-5 ===')
for item in gr_task['arms']['graph']['ranked'][:5]:
    print(f'  {item[\"item_id\"]} (score={item.get(\"relevance_score\",0):.3f})')
"
```

- [ ] **Step 3: Write findings to docs/m5_m6_retrieval_evaluation.md**

Format:
```markdown
# Week 5-6 Retrieval Evaluation — Manual Inspection

## Overview
- BM25 run: <id>
- Graph run: <id>
- Paired tasks: N
- Manifest: verified-c104f840cc67-dev-25

## Summary Table
| Metric | BM25 | Graph | Delta |
|--------|------|-------|-------|
| file_recall@5 | ... | ... | ... |
| function_recall@5 | ... | ... | ... |

## Task-by-Task Notes
### <instance_id> (Graph WINS)
- BM25 top-5: ...
- Graph top-5: ...
- Why graph won: ...

### <instance_id> (BM25 WINS)
- ...
```

- [ ] **Step 4: Commit**

```bash
git add docs/m5_m6_retrieval_evaluation.md
git commit -m "docs: Week 5-6 retrieval evaluation manual inspection"
```

---

## Definition of Done

- [ ] `_link_inheritance()` and `_resolve_calls()` both guard missing modules
- [ ] 7 new/modified tests in `tests/test_graph_builder_robustness.py` all pass
- [ ] Full test suite: 194+ passed, 0 failed
- [ ] Graph run completes on ≥ 20/25 real repos
- [ ] `compare_graph_vs_bm25.py` produces `REPORT.md` with Recall@3/5/10 tables
- [ ] `docs/m5_m6_retrieval_evaluation.md` has 10 task-level manual inspection notes
