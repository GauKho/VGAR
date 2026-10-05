# Retrieval Evaluation Pipeline — Spec

**Date:** 2026-10-05
**Owner:** M2 + M3
**Status:** Draft — depends on Builder Robustness spec being complete
**Blocks:** Week 5-6 Definition of Done

---

## Problem

Week 5-6 DoD requires:
> "Có bảng `Graph vs BM25` với Recall@3, Recall@5, Recall@10 và token cost."

Current state:
- BM25 baseline run exists (`20261005T045625580136Z-7fa20ac5dd80`, 25 tasks, SUCCEEDED)
- Graph run attempted (`20261005T090644654026Z-fcd8ac1549ac`) but **all 9 tasks failed** due to builder bug
- `compare_graph_vs_bm25.py` was crashing with `KeyError: 'arms'` when fed a BM25 run as the "graph run" — now fixed with validation
- No comparison report has been generated yet

---

## Goal

Produce a valid `Graph vs BM25` comparison table on the 25-task dev manifest, satisfying the Week 5-6 DoD.

---

## Pipeline Flow

```
Step 1: Run BM25 baseline            ← DONE (20261005T045625580136Z)
Step 2: Run Graph arm                 ← BLOCKED by builder bug
Step 3: Run compare script            ← Needs both runs from Steps 1 & 2
Step 4: Generate REPORT.md            ← Produced by compare script
Step 5: Manual inspect 10 tasks       ← Post-processing, human verification
```

---

## Step 1: BM25 Baseline (Already Done)

- **Run directory:** `results/retrieval/20261005T045625580136Z-7fa20ac5dd80`
- **Command:** `scripts/run_bm25_retrieval.py . data/manifests/verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json`
- **Result:** 25/25 SUCCEEDED
- **Config:** budget_tokens=8000, counter_label=local-hf:Qwen..., scoring_version=retrieval-scoring-v1

## Step 2: Graph Arm (Needs Builder Fix First)

- **Command:**
  ```bash
  python scripts/run_graph_retrieval.py . \
      data/manifests/verified-c104f840cc67-dev-25.json \
      --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json \
      --budget-tokens 8000
  ```
- **Expected output:** `results/retrieval/<timestamp>-<hash>/` with `kind=retrieval_graph`
- **Required arms in task results:** `graph` and `graph_f2p`
- **Success criteria:** ≥ 20/25 tasks SUCCEEDED (some may still fail for unrelated reasons)

### Config to match BM25 run (fairness rules):
- Same `budget_tokens` = 8000
- Same `counter_label` (use tokenizer manifest)
- Same `scoring_version` (auto-set by code)
- Same `snippet_policy` (auto-set by code)

## Step 3: Compare Script

- **Command:**
  ```bash
  python scripts/compare_graph_vs_bm25.py \
      . \
      results/retrieval/20261005T045625580136Z-7fa20ac5dd80 \
      results/retrieval/<graph_run_dir>
  ```
- **Output:** `results/retrieval/<cmp_dir>/result.json` + `REPORT.md`
- **Validation:** `compare_runs()` now rejects BM25-only runs with clear error

## Step 4: Output Artifacts

The compare script produces:
- `result.json`: structured comparison data
- `REPORT.md`: human-readable table with:
  - Graph vs BM25 Recall@3/5/10 (file + function)
  - MRR scores
  - Packed gold-in-context rates
  - Token cost comparison
  - Paired delta with 95% CI
  - Manual inspection recommendations (top 3 wins/losses per arm)

## Step 5: Manual Inspection

- Select 10 tasks (mix of wins and losses from comparison)
- For each task:
  - Print top-5 candidates from both BM25 and Graph
  - Check if gold files/functions appear in top-5
  - Note why Graph missed or BM25 missed
- Record findings in `docs/m5_m6_retrieval_evaluation.md`

---

## Success Criteria (Week 5-6 DoD)

- [ ] Graph run completes with ≥ 20/25 SUCCEEDED tasks
- [ ] `compare_graph_vs_bm25.py` produces `REPORT.md` without errors
- [ ] REPORT.md contains table with Recall@3/5/10 for both file and function
- [ ] At least 10 tasks manually inspected
- [ ] Findings documented in `docs/m5_m6_retrieval_evaluation.md`

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Graph build still fails on some repos | After builder fix, re-run; individual task failures don't block comparison |
| Graph recall worse than BM25 | Document as finding; triggers weight tuning in Week 7 |
| Tokenizer manifest mismatch | Reuse same `--tokenizer-manifest` flag for both runs |
| Different corpus between runs | Both reads from same `data/repositories/trees/` — deterministic |

---

## Files Affected

- **Read-only (no changes):** `scripts/run_graph_retrieval.py`, `scripts/run_bm25_retrieval.py`, `scripts/compare_graph_vs_bm25.py`
- **Create:** `docs/m5_m6_retrieval_evaluation.md` (manual inspection notes)
- **Depends on:** Builder Robustness spec (this spec cannot proceed until that is merged)
