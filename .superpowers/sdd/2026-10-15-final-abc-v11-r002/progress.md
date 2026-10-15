# Final A/B/C V11/r002 — user authorized 15/10/2026

Verification-only execution of existing final3 requirement. No new product feature,
no edits src/scripts/config/tests/prompts, no install, model switch, commit/push.
Use existing scripts/run_demo.py with final_profile.json in results, same core
r002 fingerprint qualified234PASS. Fresh A→B→C, feedbackNone, one generation/case,
max3 new runs, 1800s/run/900gen/120command/6000input/1536output/reserve256.
No old PASS pooling. Prior B is closed and not reopened to bypass quota.
New request explicitly authorizes final3, not another B tuning campaign.
Ruling: use existing CLI, operator reservations and read-only audit job rather
than add another controller/change qualified runtime. If interrupted, inspect
manifest/process/canonical; never blindly rerun reserved case. No automatic retry.
Source M2 non-Git confirmed; no AGENTS files found in scoped project paths.
Plan: preflight/runtime/frozen proof, run A audit, run B audit, run C audit,
final combined audit + current status/Vietnamese report/guide. Stop on any failed
case for diagnosis, no changing template within final run set.
A reservation saved before launch at results/final_acceptance/2026-10-15-v11-r002/
run_manifest.json. B/C not yet reserved. No model launched yet.

PreflightPASS at audits/20261015T072637124438Z-0bf2845b2734. A fresh V11/r002
PASS: A/20261015T072711985584Z-dc47a96417ee/run_record.json (68.828s, gen53.250s,
input1299/output43, originalsourceunchanged). Additive auditPASS at
audits/20261015T072910452391Z-6bc45ef93046. Core/template/diagnostics/raw/bundle/
signatures/required transition checked; no feedback. B reserved before launch,
C NOT_RUN. Do not repeat A. Old B tuning PASS not pooled.

Final B fresh PASS: B/20261015T072938917449Z-a0075c35e2ee/run_record.json,
157.282s/gen142.406s, input1769, no feedback. Partial auditPASS at
audits/20261015T073226931714Z-986411624f02. Both invoice.py/pricing.py changed;
core/static/transition/cleanup/bundle/additional gatesPASS. C reserved next.

COMPLETE: fresh C PASS at C/20261015T073254806383Z-68a9a593f8d6/run_record.json,
64.031s/gen51.250s, input1169/output43, originalsourceunchanged. C fallback tests
scope/unlinked and actual collection/execution verified. Combined audit A/B/C
PASS at audits/20261015T073438247626Z-8ce2a58ef084/run_record.json (scope3/3).
All three same V11/r002/model/policy, no feedback, original raw=candidate bytes,
requiredFAIL→PASS/regressions/signatures/static/cleanup/source/bundle/diagnostics.
No corefileschanged, no rerun same234tests merely for timestamps. No retries or
oldcampaignresets;3newgenerationsexact. No pending owned process; STOP inference.
Manifest terminalPASS. Docs guide/results + COMPLETION_REPORT/PROGRESS updated.
Total pipeline290.141s, generation246.906s,input4237/output243. No teammate/M3/
benchmark claims. Keep ledger/frozenfile/audit evidence, no commit/push/delete.
