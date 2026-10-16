# M2 tuần 5–6 — Protocol đã được duyệt

Plan: `D:/Project/CAPSTONES/New_task/2026-10-13-hoan-thien-m2-w5-w6-cx-mp-ct.md`.
Người dùng đã yêu cầu triển khai ngày13/10/2026. Chỉ hai task M2-03/CX và M2-04/MP.

## Identity và scope

- Baseline HEAD: `73814b8f89666c71b1911e42e98b8ecc7f6e3e99`.
- Branch: `integration/main-m1-w5-w6-20261013` (không main).
- Giữ docs untracked cũ; không commit/push. Thực thi trong VGAR đúng target đã được duyệt, không tạo worktree khác.
- Không sửa graph/MCP/model/repair; giữ BM25/gold đã HT. Chỉ consumer/scorer/compare M2 có RED regression.

## Frozen evaluation

| Field | Giá trị |
|---|---|
| Dataset | princeton-nlp/SWE-bench_Verified |
| Revision | c104f840cc67f8b6eec6f759ebc8b2693d585d4a |
| Selection | current deterministic dev splitter, round-robin,25tasks, >=2production Python files |
| Query | problem_statement_only_no_hints_or_gold |
| BM25 | k1=1.2,b=0.75, current AST/code chunk policy |
| Graph | existing static resolver,2hops,100candidates,current weights/confidence |
| Context budget |8000, same verified LocalTokenizerCounter |
| Tokenizer | Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554, tokenizer-only |
| Scoring | current scoring_version;80lines/header/overlap policy from runs |
| Runtime | one Graph worker,300s/task; BM25/Graph sequential |
| Primary | BM25 full vs Graph issue-only |
| Diagnostics | graph_f2p and bm25_capped, not main comparison |
| Acceptance | attempted25, >=20validpairs; per-metric eligible N and all failures visible |

Core changes/tests are frozen before pilot. Input/config/source/counter/test hashes in receipts.
Final profile freeze: after malformed-source-range review fix; qualified preflight command
`20261013T120018413619Z-4b721297e455`. Source digest
`sha256:f00423af0725e1539b89e00c9f7ab46588e37cb0810f8c6f44e7da005b8c8284`.
Earlier pilot and BM25full25 are pre-fix historical only. No scoring-version string
change was made; use source digest and raw run IDs to distinguish implementations.
No-anchor/misses are valid outcomes; labels incomplete are ineligible, not zero.
Task M2-04 requires actual M1 output and M1-owner confirmation; no self sign-off.

## Evidence conventions

- Test invocations: existing `scripts/record_m2_test.py`, unique JSON under artifacts/m2/test-runs.
- Commands/preflight: existing `retrieval.evidence.record_command`, unique receipt under artifacts/m2/w5-w6.
- Runs: results/retrieval/<run-id>/result.json, tasks/*.json, REPORT.md; never overwritten by another run.
- Durations use monotonic end-start; UTC start/end also recorded.
- Test hashes include nested tests/m2 separately; do not alter global M1 fingerprint/cache policy.
- Failures retained. Same method unexpected failure twice -> stop method; no third unchanged attempt.

## Implementation decisions/rulings

1. Work in current VGAR checkout, as the approved plan specifies, on existing integration branch. No worktree/helper auto-commits: user prohibits commit and requires current paths. Cost if wrong: no branch isolation; limited allowlist + preserved dirty state mitigate it.
2. Use actual available Python3.13 interpreter at `D:/Project/CAPSTONES/.venv/Scripts/python.exe` if retrieval dependency/counter checks pass. This is inside >=3.11,<3.14, not a model-runtime choice. Do not create/install a new environment unless needed.
3. Keep progress ledger here and PROGRESS.md rather than shell skill helpers that assume plan is in repo/commit per task. Persistent evidence is retained because there are no commits to recover from.

## Pre-flight interface scan

- R0→R1: source/counter identity consumed by handoff tests; test fixture counters are explicitly non-primary.
- R1→R2: comparison includes patch_hash before any accepted paired report.
- R2→R3: same manifest25 used with limit3, then full25; pilot not added to final denominator.
- R3→R4: report generated from artifacts, >=20validpairs checked independently of exit0.
- No interface change to M1 shared DTOs or producer ranking.
