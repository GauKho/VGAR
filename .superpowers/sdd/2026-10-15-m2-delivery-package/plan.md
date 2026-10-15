# Bộ bàn giao M2 W7–8 — thực thi yêu cầu 5 file ngày 15/10/2026

Goal: three Vietnamese documents, requirement.txt, one-command PowerShell runner.
User explicitly requests creation, no new design approval round. Inline execution.
No existing core/templates/guards/tests/config/fixtures/evidence modified; no
install/model-download/commit/push. Root runner excluded from qualified core
src/scripts/config fingerprint, historical r002 and final3 remain valid.

Deliverables: docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md;
docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md (all-files + all-directories snapshot appendix,
including .venv/cache/results, generated mechanically, no vendor-code authorship claim);
docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md (each physical script line annotated,
entire runnable script additionally mirrored); requirement.txt; test_abc_v11_r002.ps1.

Tasks: 1 scoped code/evidence/deps/papers inventory; 2 runner RED→GREEN and ReadSaved/
Check modes, fail-closed output/source/profile/caps; 3 docs + complete inventory;
4 fullsuite/Ruff, fresh whole-change review then one Important fix pass, checkpoint.
Tests outside existing tests/ under this ledger directory to preserve old inputs.
Run wrapper ReadSaved/Check only here; no redundant three model generations merely
to demonstrate script plumbing. Actual Run-mode model outcomes cannot be promised.

Ruling: requirement.txt separates executable CORE entries and HF install comments because
host tokenizers0.22.1 and qualified HF0.22.2 differ; one unqualified combined pip
install would silently change an accepted environment. Environment markers cannot
distinguish these two Windows Python3.11 venvs; explicit separate-interpreter
comments/installation instructions are used, runner never installs. Exact policy unchanged.

Runner RED4 missing-file -> initial GREEN attempt2PASS/2FAIL due PowerShell5.1
File.Replace coerces null backup path into illegal empty path; fixed with owned
.previous backup. Tests use unique per-invocation paths, never overwrite failed
evidence. GREEN4 PASS15.49s at results/delivery-validation/green-runner-2.xml.
ReadSaved audited all3 actual final records/full artifacts; Check CUDA/versions
probe did not load weights. No real generations launched. One fresh reviewer
delivery_package_review reviewing new five-file package; no implementer agents.
Ruling: exhaustive means an as-of snapshot with one row per real path; third-party
files are identified as dependencies, not treated as M2 implementation. Generated
new files after the snapshot are explicitly time-bounded, not falsely claimed listed.
No Git in M2; preserve ledger/snapshots, no worktree initialization or cleanup.

Fresh review completed once (delivery_package_review). Accepted Important findings:
assert optimization bypass, missing diagnostics after failed selftests/artifact,
missing enforcement of core pins, nonspecific annotations. Reproduced RED5/3PASS
at results/delivery-validation/red-review.xml, fixed with GREEN8/25.90s at
green-review-all.xml. Root changes only, not r002. Core final suite234PASS117.32s
(recorder118.157s) at final-full-suite/20261015T090448960637Z-611d502a76ad.
Ruff E9,F and PS syntax PASS. No new model generations: Check/ReadSaved and forced
selftest failure verified real plumbing. COMPLETED all5deliverables. File02 lists
all10874files/3661subdirectories, verified exact path-set equality. Proof at
results/delivery-validation/delivery_check.json: mirror/eachline/pins/core unchanged/
saved3/proofs/lint/syntax/inventory allPASS. File03 install commands removed to honor
test-only requirement; optional one-time provisioning notes live in requirement.txt.
