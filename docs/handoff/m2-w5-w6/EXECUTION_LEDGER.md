# Execution ledger — plan: D:/Project/CAPSTONES/New_task/2026-10-13-hoan-thien-m2-w5-w6-cx-mp-ct.md

Baseline: 73814b8f89666c71b1911e42e98b8ecc7f6e3e99.
Approved: user requests implementation; no commit/push; current VGAR checkout.

- [x] R0: inputs/environment/receipts verified; isolated env and tokenizer assets provisioned.
- [x] R1: RED→GREEN patch hash guard + context/gold handoff tests/evidence (technical acceptance; owner review pending).
- [x] R2: final source pilot3 same manifest25/config/counter;3/3 valid paired.
- [x] R3: final25/paired report, failures/N retained;22 valid pairs satisfy >=20 gate.
- [x] R4: regression/report/task status delivered; M2-04 owner sign-off remains external/PENDING and not marked HT.

Rulings and shared-interface scan: see PROTOCOL.md. Do not execute older plans.
R0: tokenizer provisioning PASS; hashes4assets verified. Root environment tokenizers0.23.1 rejected; creating isolated .venv-m2-w5-w6 with approved retrieval pins. Existing root env unchanged.
R1 RED: test_compare_rejects_patch_hash_mismatch failed as expected, other positive comparison passed; artifacts/m2/test-runs/20261013T112504100380Z-49c006ef1b4b464fae4baa5ced28c19b.json. One-line patch_hash guard implemented; GREEN pending.
Ruling: isolated retrieval environment now required because root tokenizers incompatible; exact deps from existing requirements, no full model stack. Cost: one-time lightweight package install.
R0 complete: qualified Python3.13 isolated env/tokenizers0.22.1; assets/hash verified (command20261013T113434195579Z-9be9a3dd1804). Pinned dev25 prepared with authoritative metadata (20261013T113611704608Z-148456e0c7ae). Historical parquet reused only after sha256 match; legacy split=test manifest not reused as dev selection. New splitter yielded28eligibledev tasks,25selected. Ten source archives reused with sidecar/hash checks,15missing.
R1 second RED: single-definition wrong span falsely counted as function (20261013T113403752051Z-4960ccc60659477e91d87cd290ea4c38). Third RED: exclusive end_col0 added next function header (20261013T113744502165Z-199bc82d7a374225beacc79947aa0238). Minimal fixes in M2 scoring only; producer untouched.
R1 GREEN:48passed/0failed/0skip (20261013T113831791725Z-464d49316d304853b5755e7a671e3e91).
R1 actual M1 static producer proof PASS:2contextitems/47tokens/0unmapped; native_handoff/result.json. Owner sign-off PENDING, not auto-approved.
R2 BM25 pilot3 PASS: results/retrieval/20261013T113922544857Z-71d031a5b567. Same manifest25/counter8000. Graph pilot3 launched after source changes frozen; next read its artifact then compare pilot, proceed full25 only if gate met.
Ruling: additional range fixes are M2 consumer bugs demonstrated RED; normalize exclusive end line and require containment for single as well as duplicate definitions. Cost if wrong: valid producer ranges could lose function labels; targeted legacy/current mapping regression passed.
R2 Graph pilot3 PASS3/3 (83.6s/122.1s/50.8s), command20261013T114246047867Z-2ccc38850690; raw20261013T114247160430Z-dbbca1352e5f. All missing15source archives fetched/verified, command20261013T114600982392Z-2e0772b57c75. Compare3 and BM25final launched next; Graphfinal remains sequential after BM25 finishes.

Final review: fresh read-only reviewer found one Important: missing/invalid UTF-8 spans could still score function hits. No Critical or deferred Minor. Findings on final25/owner sign-off intentionally not asserted before evidence.
Final: fixed malformed source binding — 12 failed/12 passed RED (20261013T115802447312Z-67c7be8e7cc44e5ea4232413c35573f0), then targeted suite 121 passed (20261013T115854955079Z-65e7f223162744848886560ea140285a). Native valid UTF-8/CRLF/legacy ranges retained. No M1/schema change.
Ruling: invalid spans are omitted with item-level INVALID_SOURCE_RANGE, not retained as empty file hits. Source-name mismatch with valid span still degrades to file-level. Cost if wrong: a malformed producer record loses file recall too; this prevents unbound/empty context from inflating metrics and is observable in diagnostics.
Ruling: pre-review pilot/comparison and BM25 full25 (20261013T114849628933Z-e53bca69dacc, PASS25/25) remain historical/pre-fix evidence. Freeze new source/profile, rerun pilot and final rather than silently mixing scorer implementations. Cost: one additional bounded evaluation cycle; no dataset/weights/parameters changed.

R2 final profile PASS: BM25 pilot `20261013T120020961896Z-420d8af4121c`; Graph pilot `20261013T120150745677Z-4a1982129910` (61.1s/76.1s/30.9s); comparison `20261013T120701552389Z-9f3e066ed941`,3 valid pairs. Preflight20261013T120018413619Z-4b721297e455 and actual producer proof native_handoff_final/result.json both PASS. Product changes frozen; final BM25 launched next, Graph only after it finishes.
R3 BM25 final PASS25/25: `20261013T120702363418Z-b067d65c7d70`, receipt `commands/20261013T120701685574Z-f7a5666149f9`. Graph final launched sequentially; no source/profile changes after final pilot.
Ruling: fail budget applies to repeating a failed task/method/profile invocation, not to distinct IDs in the single approved final25 invocation. Otherwise R3's retained failures and >=20/25 gate conflict with attempting the frozen population. No task retry and no automatic full-profile rerun; distinct task timeouts keep their status/N. Cost if wrong: bounded CPU wait up to300s for another large task; no third attempt of the same failed task/profile.
R3 terminal: Graph PARTIAL_FAILURE/exit1,22succeeded/3SymPy timeouts/25attempted,2402.459s. Run20261013T121221258372Z-9ae258fd202e, command20261013T121220058318Z-8d130aa1cb78. Comparison20261013T125307312086Z-6d6b0b52b105 COMPARED22/25; no score tuning/hidden exclusions.
R3 acceptance PASS: final-verification/20261013T125343095888Z-13d9f9501ba3/result.json verified current source/manifest/counter/budget/population/task and run hashes. M2-03 CX→HT per approved gate, not25/25GraphPASS.
Ruling: final legacy recorder was interrupted after >5min whole-workspace hashing (includes large data/results/isolated env), not treated as pytest FAIL/PASS. Use existing record_command for bounded direct targeted pytest, leaving W3-4 hasher untouched. Cost: final receipt fingerprints code only and lacks JUnit/full-workspace hash; prior121-test recorder remains and final current-source receipt adds121PASS/5.47s. Interrupted owned launcher/process identity and scope preserved in command20261013T125931493926Z-ed28d248bb9f plus clarification.json.
R4 final regression PASS: commands/20261013T125931577415Z-c5e38fe74935/result.json,121passed/0fail/0skip. COMPLETION_REPORT/CONTEXT_GOLD_HANDOFF/UNFINISHED_TASKS/PROGRESS/Task Status updated only for M2 scope. No commits or pushes.
Final: Ruling: final25 metrics/owner sign-off previously declined by reviewer — receipts now prove22pairs; owner review still pending and M2-04 remains MP. Cost if wrong: premature overall completion; avoided by keeping owner gate explicit.
Final: Ruling: M1 ranking/resolver and MCP/repair were not reviewed or changed — preserve ownership/week boundary. Cost: unrelated known limitations remain; do not infer full-system qualification from this task.
