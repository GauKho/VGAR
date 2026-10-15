# SDD ledger — plan: D:/Project/CAPSTONES/New_task/2026-10-13-m2-w7-w8-brainstorm-implementation-plan.md

Ruling: Dedicated new package is the approved isolation boundary — do not create a VGAR worktree or alter its .git — cost if wrong: integration must be explicitly approved later.
Ruling: Windows/native, no project commits requested, plan lives outside this non-Git package — use this durable ledger/PROGRESS and canonical test receipts rather than Git-dependent sdd scripts — cost: no commit-based recovery, files/evidence must be retained; never delete this ledger.
Approval: User chose HF Qwen3-4B pinned prototype and Native on the three trusted M1 fixtures, not external repos/benchmark.
Pre-flight M0→M1: pinned boundary + RepairTask bundle/identity → shared consumer; use revision→repository_revision explicitly.
Pre-flight M1→M4: retain original source + frozen hints/manifest → diagnose_changed_paths; never patched source.
Pre-flight M3→M4/M5: attested actual changed paths + lease → selection/verification; not fixture expected paths.
Pre-flight M2→M6: raw generation/finish reason → parser; never silently retry/repair truncated text.
Pre-flight M4/M5→M6: exact IDs/outcomes + command evidence → canonical JSON/public DTO projection; NOT_RUN cannot become PASS.
Task M0: complete — bootstrap/contracts/limits/recorder RED→GREEN, 19 passed, receipt results/tests/20261014T082310875781Z-69aa78e82e50/run_record.json; no commit requested.
Setup: isolated core/dev venv installation initially blocked by sandbox socket; approved elevated install succeeded. No old venv modified, no weights/Torch installed here.
Task M1: in progress — RED 10 failures due missing consumer/prompt; implementing thin API reuse.
Task M1: complete — 29 passed in isolated venv, receipt results/tests/20261014T082655437932Z-7d3f3a475e32/run_record.json; retains genuine Qwen snippet counter and consumer diagnostics.
Task M2: offline in progress; RED two missing generator/worker tests at 20261014T082814063252Z-d5edabbec1c6; real qualification deferred until patch/verifier can consume output.
Task M2 offline: 31 full-suite tests passed at 20261014T082942572945Z-a791b7ab2ccd; real adapter/qualification remain pending.
Task M3: RED 12 tests at 20261014T083227882300Z-f390ec2a689b.
Ruling M3: bind logical model diff lines to existing LF/CRLF for Git transport, keeping raw output, unchanged hunk counts/content and before/after byte predictions — satisfies CRLF preservation without --ignore-whitespace/fuzzy matching — cost if wrong: stricter transport fixtures needed; never report transport as raw model bytes.
Ruling M3: attribute transforms are unsupported in this trusted fixture profile; reject .gitattributes rather than weaken byte attestation — cost: such targets require explicit future profile, not needed for three M1 fixtures.
M3 first GREEN failed 2/12: Native git apply inherited host core.autocrlf=true because factory only used invocation-local false. Probe confirmed LF source became CRLF after apply and byte attestation correctly rejected it. Fix: persist false only in disposable seed repo; do not change global or original Git config. Receipt 20261014T083507819545Z-93001d8645af keeps failures.
Task M3: complete — full 43 passed, 20261014T083655347153Z-c10c7067028a. Multi-file strict preflight, CRLF/UTF-8/spaces/no-final-newline and original Git metadata guarded.
Task M4: RED seven missing selection/runner cases at 20261014T083857192816Z-d329d6851d65; implementing exact reporting.
Task M4: complete — full 50 passed, receipt 20261014T084051393924Z-219c4b7011ba. Exact node IDs/call outcomes/JUnit; missing/partial/unlinked fallback; all-skip is ERROR.
Task M5: RED five missing verifier cases at 20261014T084237121032Z-3dad4b2eb531.
Task M5: complete — full 55 passed, receipt 20261014T084414314865Z-4cadbe3b126b. Trusted baseline assertion failure, mypy/Ruff/syntax, exact required/regression guards.
Task M6: RED two missing pipeline tests at 20261014T084631003426Z-865bc0d8bbc2.
Task M6 core: GREEN 57 tests at 20261014T085103495518Z-13a314586ca8; CLI/reuse inputs RED then full61 GREEN at 20261014T090037438820Z-0f0ebc9e3292. Final evidence/cleanup review still required.
Task M2 real: short invocation PASS (OK), 20261014T085555586866Z-7c81bac709ad, 35.234s. Model GPU/CPU auto placement recorded; no quantization or old factory edits. Actual A repair doubles as format qualification after this short call, avoiding an unrelated extra generation.
Task M7: source copies/bundles/tasks frozen, results/setup/20261014T090036830162Z-219fc0463385. Offline CLI full chat needs lightweight Jinja2, not a Torch dependency.
Real A v1 FAIL at 20261014T090352481580Z-8f8da9b4cddd: model emitted SEARCH/REPLACE, not unified diff. Parser rejected before apply; original unchanged; no semantic/test acceptance attempted.
Ruling: perform one explicit prompt-v2 format correction after diagnosed v1 failure, with a neutral syntax example and forbidden SEARCH/REPLACE, no fixture solution/gold. Preserve v1/logs, record supersedes/reason, freeze v2 across the three planned demos. Model/SHA/budgets/parser/verifier unchanged — cost: v1/v2 results must never be merged as one fixed-prompt success rate. If format method fails again, stop rather than retry unchanged.

Real A v2 FAIL: 20261014T091104527173Z-8e59e14c75c7, 62.453s; header declares 3 lines but body has 2. Source unchanged, apply/verification NOT_RUN. Method stopped after two real format failures; no B/C real attempt or third prompt.
Final whole-package review: one fresh-context gpt-6-astra read-only reviewer; no child reviewer or GPU action. Four Important findings, no Critical. Report docs/FINAL_REVIEW.md.
Final: fixed terminal/export/cleanup/artifact linkage — tests/test_finalization.py four RED at 20261014T092414173775Z-11cf41314bf1 → four GREEN at 20261014T092541735569Z-e703c9592ee6; bundle points to exact terminal bytes; final full76 GREEN.
Final: fixed assessed public test status/reasons, subprocess/stage deadlines, applied diff export — tests/test_review_guards.py five RED at 20261014T092655109032Z-594cc738633a → combined9 GREEN at 20261014T092804983040Z-297a1b66c7ae; final full76 GREEN.
Final coverage: descendant-kill after parent exit + missing mypy/Ruff acceptance tests added; existing behavior GREEN, not claimed RED bugfix. Summary separation test GREEN. Mechanical unused-import cleanup after Ruff receipt 20261014T093406966457Z-6c093479e493; E9/F now PASS.
Final: minor (deferred): JUnit counters/testcase reconciliation — exact reporter guards remain primary; XML syntax checked, no additional coverage claim.
Final: Ruling: real three-case acceptance is blocked, not replaced by fake — stop profile after two failures — cost: owner must approve a new method before closing gate.
Final: Ruling: external repos/OS sandbox/benchmark/Linux remain excluded — approved byte-verified Windows fixture profile only — cost: no acceptance claim for those targets.
Final: Ruling: M1/M3/API/structural and dirty VGAR stay read-only/out of scope — respect ownership — cost: integrated MCP/system gate still pending.
Final: Ruling: author finalized guide/checkpoint against observed evidence, not independent human reproduction — cost: teammate rerun still required.
Final: Ruling: model claims limited to pinned local invocation/retained outputs, not full weight-cache audit or model quality — cost: no benchmark/generalized claim.
M7 offline after-fix demos PASS3 with source unchanged, proper bundle hashes: A 20261014T093356677872Z-16526a595667; B 20261014T093404983613Z-af38288e6594 (two production files); C 20261014T093412525344Z-f1913b231c8a. Real B/C remain NOT_RUN.
Final fresh verification: full76 PASS 20261014T093529864005Z-9dc514964a36; Ruff E9/F + protected309 manifest files PASS 20261014T093651139400Z-ace940916093. Earlier baseline audit 20261014T093504765885Z-db0b19d3897d flagged only PROGRESS because its approved M1 append at07:27:40 predates M2; corrected receipt explicitly records exception/provenance, no source restoration/edit made.
Task M6: complete with review fixes and fresh suite. Task M7: docs/offline/handoff complete; real acceptance BLOCKED. Keep ledger/evidence (no project commits to recover from). No plan completion claim, no commit/push, no process running at handoff.

