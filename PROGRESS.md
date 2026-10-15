# M2 W7–8 — Execution checkpoint

## Publication — ĐÃ PUSH nhánh riêng M2 W7–8, 15/10/2026

User yêu cầu push vào GauKho/VGAR, không main. Nhánh bàn giao độc lập dự kiến:
feat/m2-w7-w8-v11-r002-20261015; nội dung M2 ở root, không copy repo VGAR main.
Publication snapshot riêng tại D:/Project/CAPSTONES/.publish/M2_week_7_8-20261015T143704374Z-7333a2f2.
Source M2 vẫn không bị khởi tạo Git/chuyển branch; không sửa code/pins/guards.
Fresh pre-push fullsuite234PASS131.47s (recorder132.766s), RuffPASS; proof:
results/publication/20261015-v11-r002/tests/20261015T143258304123Z-e0ca889ea2ff/run_record.json.
Không generation mới. Giữ source/docs/inputs/provenance/history/final+manual
evidence; loại .venv/weights/caches/temp/workspaces/owner-locks. Bản xuất bản
thêm Git attributes giữ nguyên EOL/bytes và ghi chú PUBLICATION, không code mới.
Đã push và xác minh remote commit nội dung8441aa5bff56897cc4f813103be2bfa70500087c
trên nhánh feat/m2-w7-w8-v11-r002-20261015. Main trước/sau giữ nguyên
b39e0dbf87645d39b9a68e87b19d0655df264a05. Không PR, merge hoặc force-push.
Link: https://github.com/GauKho/VGAR/tree/feat/m2-w7-w8-v11-r002-20261015
1517files nguồn đã chọn +2Git metadata=1519tracked files; SHA256 copy và index
blob bytes khớp,36README links đủ ở bản xuất bản. .gitattributes giữ EOL/bytes.
Lần push đầu bị Git ownership guard do sandbox/user khác SID; dùng safe.directory
đúng publication path chỉ trong command, không đổi global config. Checkpoint
xác minh này được bổ sung bằng commit docs sau commit nội dung, không đổi core.

## Documentation update — Viết lại README tiếng Việt, 15/10/2026

README.md được viết lại thành entrypoint12mục: trạng thái/phạm vi, lệnh một lần,
7tasks và ranh giới M1/M3, hướng dẫn sử dụng5files, kết quả user manualRun,
flow/input/output, các modes/exit/status, đọc latestRun tự động, prerequisites
tách2venvs, cấu trúc/FAQ/bàn giao và historical references.
Primary evidence mới cho README: results/manual_abc/20261015T114826234Z-922d5c80/
summary.json PASS/Run/completeTrue/skipSelfTestsFalse, A/B/C realPASS V11/r002,
234selftests PASS117.63s, Ruffexit0, workflow429.152s. Baseline FAIL tách khỏi
post/finalPASS. Thời gian hiển thị UTC+7 Asia/Saigon18:48:26–18:55:35.
Static verification PASS:36relative links,17PowerShellblocks parse, Markdown
tables/fences,3canonical SHA bindings và137protected files không đổi (core,
tests/config/prompts/examples/runner/requirement và3docs chính). Không rerun
LLM/tests/install/commit/push, không thay old/current evidence. Chỉ README và
checkpoint này thay đổi; số liệu là saved user run, không kết quả inference mới.

## Documentation update — Chuyên đề repair prompt V11 trong File02, 15/10/2026

Đã đưa nội dung giải thích V11 trong hội thoại vào mục0.9 của
docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md, có18tiểu mục và chỉ dẫn từ Task1.
Nội dung: template/fullprompt/runtime, mục tiêu/permissions/replacement/hunks/
coords/counts/newline/neutral example/checklist, system-user/tokenization/budget,
liên kết M1→HF→parse/apply→verify→M3, instruction vs hard checks, V10→V11,
hash/version/renderer labels và actual no-feedback B evidence.
Static verification PASS: đủ18tiểu mục,31code blocks có fences cân bằng,
7local links hợp lệ. SHA256 phần kỹ thuật+phụ lục không đổi; giải thích cũ giữ
nguyên trừ chỉ dẫn sang0.9;134files code/config/tests/templates/inputs/runner/
requirement không đổi. Chỉ sửa File02 và checkpoint này, không sửa prompt,
không inference/tests rerun/install/commit/push và không sửa evidence đã lưu.

## Documentation update — Giải thích dễ hiểu trong File02, 15/10/2026

Đã thêm mục0 ở đầu docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md từ nội dung giải thích
trong hội thoại: vai trò M1/M2/M3, nguồn/consumer M1, cách làm7tasks, boundary M3,
flow12bước, ví dụ A/B/C, PowerShell theo thứ tự và cách đọc output tự động.
Người mới đọc mục0 trước, sau đó mục1–15/phụ lục để đối chiếu kỹ thuật.
Static verification PASS: đủ7tasks/8subsections,9PowerShellblocks parse hợp lệ,
local links hợp lệ/code fences cân bằng. SHA256 toàn phần kỹ thuật cũ+phụ lục
không đổi;134files code/config/tests/prompts/examples/runner/requirement không đổi.
Chỉ sửa File02 và checkpoint này; không inference, install, core-tests rerun,
commit/push hoặc thay evidence/status nghiệm thu. Số liệu tests/final3 trong
tài liệu được ghi rõ là kết quả các phiên đã lưu, không phải run mới.

## Current — Bộ bàn giao 5 file tiếng Việt, 15/10/2026

Yêu cầu mới: docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md (handoff),
docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md (report + exhaustive as-of path inventory),
docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md (each-line explanation + exact script),
requirement.txt (core pins / separate HF prerequisites), test_abc_v11_r002.ps1.
Runner root không nằm trong qualified core fingerprint; src/scripts/config/
prompts/tests/fixtures/VGAR và mọi old campaign/final records giữ nguyên.

Fresh verification: full core **234 PASS117.32s**, recorder118.157s, exit0:
results/delivery-validation/final-full-suite/20261015T090448960637Z-611d502a76ad/run_record.json.
Runner **8 PASS25.90s**: results/delivery-validation/green-review-all.xml.
Ruff E9,F PASS (src/scripts/tests + runner test); PowerShell AST syntax PASS.
ReadSaved actually re-audits 3 final real records and prints all artifact families;
Check probes CUDA/dependencies without loading weights. Forced failing selftest
proves pytest errors printed and no A/B/C launched. **NO new LLM generations.**
One independent review, then Important fix pass: optimization rejected, core
pins enforced, failed/missing-artifact diagnostics preserved, each-line docs
specific; SkipSelfTests recorded. RED5/3PASS -> GREEN8; old failures retained.
No re-review/repeated inference/install/commit/push. Final appendix lists exactly
10874 files and3661 subdirectories (hidden/vendor/cache/history included), each
with path/role. Coverage/5deliverables/exact-doc3-script-mirror/each-line/corepins/
r002/historicalfinal3/proofs/Ruff/PSsyntax allPASS, receipt:
results/delivery-validation/delivery_check.json. Snapshot time explicitly bounded;
future generated files are not claimed included. File03 has ONLY testing/view
commands, provisioning instructions separated into requirement.txt comments.
All five requested deliverables completed; no pending implementation for this
delivery task. Do not rerun models merely to view the handoff/inventory.

Use one command after prerequisites: powershell -NoProfile -ExecutionPolicy
Bypass -File .\test_abc_v11_r002.ps1. Run creates NEW evidence, stops first error;
Check/ReadSaved are not fresh 3-case repairs. Teammate independent reproduction
and M3 integrated MCP acceptance remain external gates, not signed by M2.

## Current — FINAL A/B/C V11/r002 COMPLETE PASS, 15/10/2026

**3/3 fresh real repairs PASS under same V11/r002/model/policy, feedbackNone.**
No product/runtime/prompt/test/fixture edits in this final validation. Three new
runs exactly; all terminal, no pending model, no retry or old PASS pooling.
Final root: results/final_acceptance/2026-10-15-v11-r002; run_manifest.json PASS.
A: A/20261015T072711985584Z-dc47a96417ee/run_record.json — 68.828s/1299in43out.
B: B/20261015T072938917449Z-a0075c35e2ee/run_record.json — 157.282s/1769in157out.
C: C/20261015T073254806383Z-68a9a593f8d6/run_record.json — 64.031s/1169in43out.
All raw parse/exactapply/requiredFAIL→PASS/regression/collection/static/signatures/
cleanup/source/bundle/actual-generation-diagnostics/fingerprint gatesPASS.
B actually changes invoice.py and pricing.py; C fallback_requiredTrue, unlinked,
tests scope collected and executed. Combined auditPASS:
audits/20261015T073438247626Z-8ce2a58ef084/run_record.json.
Current core equals r002 qualified234PASS; same templateSHA ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8.
Total pipeline290.141s, generation246.906s, input4237/output243; not including
engineering/offline/observation time. Development fixtures only, NOT independent
teammate acceptance, M3 MCP integration, SWE-bench or held-out performance.
Guide/report docs/NGHIEM_THU_FINAL_A_B_C_V11_R002.md. final_profile.json in final
results must be passed explicitly: config/demo.json remains historicalV2 unchanged.
No commit/push, no VGAR/M1/M3/old-system modifications. No further inference needed.

### Execution history — final A/B/C (completed, do not resume old sessions)

User now explicitly requests final same-prompt/runtime gate. New verification-only
job results/final_acceptance/2026-10-15-v11-r002; old B/campaigns remain closed.
Existing run_demo CLI, no src/scripts/config/tests/prompts edits; current r002
exact qualified fingerprint, V11 template locked. Fresh A→B→C, NO feedback,
one generation per case/max3 new runs, original model/caps/guards/native fixtures.
PreflightPASS: audits/20261015T072637124438Z-0bf2845b2734/run_record.json.
run_manifest.json reserves A before launch, B/C NOT_RUN. Audit job/ledger:
.superpowers/sdd/2026-10-15-final-abc-v11-r002/. Inspect before resume, no duplicate
reserved case, no auto-reset/retry/prompt tuning. Current A launching; no claims
of final3 acceptance until three fresh records/core+additional audit allPASS.

Final A PASS + additiveauditPASS; canonical A/20261015T072711985584Z-dc47a96417ee.
Final B running session75898/canonical B/20261015T072938917449Z-a0075c35e2ee,
input1769 feedbackNone, baselinePASS. C NOT_RUN. Do not repeat A or launch B twice.

Final B PASS without feedback, canonical157.282s/gen142.406s; two files truly
changed, auditPASS at audits/20261015T073226931714Z-986411624f02. C now reserved
before launch, same V11/r002. New guide docs/NGHIEM_THU_FINAL_A_B_C_V11_R002.md.

Final C running session90968, canonical C/20261015T073254806383Z-68a9a593f8d6,
baseline/context/promptPASS; generation pending. A/B terminalPASS, no retries.

## Completed — finish B only, approved 15/10/2026

Plan: docs/superpowers/plans/2026-10-15-complete-b-with-evidence-driven-repair.md.
Limit8new reservations/14400s real-run budget; stopfirst auditedPASS, no extra
confirmation. Keep old campaigns terminal/noreset, model/SHA/greedyFP16auto/caps,
parser/verifier/tests/fixtures/VGAR unchanged. Runtime bugfixes onlyM2 allowed
with RED/GREEN + versioned archives. Non-Git; no init/commit/push.
Baseline119files: results/b-repair-preflight/20261015-evidence-driven/baseline.
Ledger: .superpowers/sdd/2026-10-15-complete-b-with-evidence-driven-repair/progress.md.
**CLOSED B development repair PASS**: attempt2 V11/r002; no pending process/attempt.
Stop at first audited PASS; no further A/C/confirmation runs authorized here.
2/8 slots, 355.066107s total reservation time of14400s; no reset/newcampaign.
Accepted canonical: results/b_repair/2026-10-15-evidence-driven-b/attempts/02/
20261015T070916546459Z-29b6c2d320ff/run_record.json.
Required2 baselineFAIL→postPASS + regressionPASS; bothproductionfileschanged;
syntax/mypy/Ruff/signatures/cleanup/source/bundle/provenance gatesPASS.
Full offline suite234PASS124.45s for current r002, RuffPASS.
Final report docs/KET_QUA_B_EVIDENCE_DRIVEN_2026_10_15.md; manual guide
docs/CHAY_B_EVIDENCE_DRIVEN_POWERSHELL.md. Closeout auditPASS:
results/b-repair-preflight/20261015-evidence-driven/closeout/
20261015T071410556116Z-462218813a53/run_record.json.
No commit/push, no VGAR/M1/M3/fixture/oldtest/guard modifications.
Minor deferred: PASS diagnosis fallbackunknown/STOP is not a failure/latch;
actualstatusPASS/completeTrue/gate_errors[]/stop_reasonNone/nextNone. Receipt kept.
This does NOT close independent reproduction/threecasesfinalversion/SWEbench.

Engineering update: tokenizer GREEN10, V10/legacy/neutral GREEN32, B controller/
CLI/acceptance focused GREEN19, RuffPASS. New scripts/run_b_experiment.py and
b_experiment/b_inputs/b_acceptance internal modules; record_tests binds runtime
hashes; pipeline optional pre-generation hook rejects duplicate generation.
Fullsuite after review **231PASS120.82s**, recorder121.609s:
results/b-repair-preflight/20261015-evidence-driven/full-qualified/
20261015T065821488334Z-8d31dfbd21e5/run_record.json. RuffPASS on registration.
One fresh review: six Important lifecycle/integrity issues reproduced RED10,
fixed with GREEN29 plus expired absolute-deadline integration test; no minors.
Runtime r001 + V10 registered under results/b_repair/2026-10-15-evidence-driven-b.
Attempt1 real B launching now; inspect durable campaign/canonical before any
new launch. Do not reset/re-init. Guide docs/CHAY_B_EVIDENCE_DRIVEN_POWERSHELL.md.

Attempt1 finished FAIL PATCH_PARSE_ERROR; no apply/verification attempted.
Record: results/b_repair/2026-10-15-evidence-driven-b/attempts/01/
20261015T070104677647Z-57e15f34010f/run_record.json.
Raw has BEGIN/END FORMAT DIFF wrappers; raw164tokens EOS/nontruncated,
input1740, generation147.141s, reservation169.221s; cleanupPASS/sourceunchanged.
Observed greedyFalse-sampling/maxnew1536, mask[1,1740] allones, GPU/CPUoffload.
Controller r001 diagnosis wrongly says runtime because timeout_seconds metadata
matched substring timeout. Preserve immutable receipt; r002 narrows exception
classification and reconstructs feedback from canonical. RED2/1PASS -> GREEN3
at070540730947Z-85738af68f0b; V11 removes wrapper strings, first/last-line contract.
Next fullsuite/Ruff r002 qualification, register r002/V11 linked attempt1 then run2.

Update: fullsuite r002 **234PASS124.45s**, RuffPASS; proof:
results/b-repair-preflight/20261015-evidence-driven/full-r002-v11/
20261015T070616016658Z-306d4603f3b7/run_record.json.
r002/V11 registered with attempt1 canonical trigger. Attempt2 running now,
session79673 (inspect durable campaign before resume; don't launch duplicate).

Terminal update: session79673 finished exit0. Attempt2 PASS audited, then stopped.
Generation163.079s/input1905/output157/EOS; feedback131tokens, actual mask[1,1905]
allones, effectivegreedyFalse-sampling/maxnew1536, GPU/CPUplacementlogged.
Canonical185.094s; reservation185.845466s. Both helpers fixed in privateworktree;
original fixtures intentionally remain broken and byte-identical. Inspect applied.diff.

## Completed owned cleanup fix — 15/10/2026

**Full suite183PASS104.62s (recorder105.281s), exit0**, after owned cleanup fix:
`results/cleanup-fix/20261015-workspace-lock/full/20261015T061228986192Z-ccfc40626b7e/run_record.json`.
Original failing test PASS; actual Windows short-handle lock test PASS; permanent
lock remains ERROR in production, tested; RuffPASS. No model/prompt/fixture/VGAR
changes, no real generation, no commit/push, no deletion of old user workspaces.
Unknown historical lock holder remains unknown; fix is bounded transient-lock
handling, not a claim that external long-lived locks are solved. New reports:
`<temp_root>/.cleanup-records/<private-name>.json` and canonical `stages.cleanup`.
New guide: docs/CLEANUP_WINDOWS_VA_CACH_KIEM_THU.md.
History archive86files/76historical PASS, old5attempt quota unchanged.
Final scoped audit PASS (9pre-edit copies, expected5modified existing files;
only2production modules; added cleanup tests and Vietnamese guide):
`results/cleanup-fix/20261015-workspace-lock/audit/20261015T061553537404Z-dd9eb5b9b5bb/run_record.json`.
No pending process/task for this approved cleanup fix. Next user step: rerun
offline full suite in VS Code with private TEMP/TMP per guide; if persistent
locks remain, inspect new cleanup report/actual handles, do not repeatedly run
full suite or relax verifier. Real repair B/final3 remain separately unaccepted.

### Implementation history — owned Windows cleanup fix

User approved ONLY investigation/fix for cleanup WinError32 after full suite
174PASS/1FAIL and isolated repeat FAIL. No LLM/prompt/model/fixture/VGAR changes.
M2 and CAPSTONES have no Git repository; no init/commit/push. Pre-edit copies:
`results/cleanup-fix/20261015-workspace-lock/baseline/` (9 scoped files).
User evidence: manual_acceptance/temp-retry-4a468a5de2d8443dbf664be4a62f1002/tests/
20261015T043124130465Z-5d29fa02946a and 20261015T043442648176Z-c9ff6f0e7d37.
Confirmed sharing lock at seed rmdir during __exit__, not a model/test assertion
failure. Exact holder UNKNOWN; command-line filtering does not identify handles.
Plan: RED cleanup regression tests incl actual Windows sharing handle; bounded
32/33-only retry (6 attempts, total scheduled waits1.55s), retain failure/traceback
and ownership guards; durable cleanup report and canonical linkage; focused,
full suite, Ruff and scoped preservation audit. Do not rerun real campaign/reset.

Implemented workspace bounded retry/durable reports + canonical cleanup stage.
RED5/1 at060831473742Z-d4954aaab60b; native fixture access0 did not create the
intended lock, corrected toFILE_LIST_DIRECTORY while production still unchanged;
native RED correctWin32 at060854269913Z-87bf5bac30d9. GREEN10 at060942461137Z-a98cc0467b0f.
Pipeline linkage RED2 at061059731977Z-c36a4c4c3cf4 -> GREEN14/40.78s
at061132193393Z-b316e5077d10. RuffPASS. Full suite completed183PASS at
061228986192Z-ccfc40626b7e, execsession51882 ended. Earlier steps are history.
Read docs/CLEANUP_WINDOWS_VA_CACH_KIEM_THU.md. No model launched.

## Completed logging-only task — 15/10/2026

**Logging implementation COMPLETE, not real repair acceptance.** Final full suite
175PASS92.28s (recorder92.922s), exit0:
results/tests/20261015T014057460231Z-bae22e94edc3/run_record.json.
Session27241 ended; no model/repair process launched. RuffPASS. Offline replay
4B +19 archived/new parser compatibility cases + both history archives PASS:
results/diagnostics/20261015T014155215724Z-fb7147b392bf/run_record.json.
Final Ruff/scope/history/no-new-repair/documentation audit PASS:
results/checks/20261015T014449437742Z-0b8fbfdea946/run_record.json
(5 Markdown files,9 PowerShell blocks,13 tables;17 modified existing runtime
files limited to diagnostic handling; no changed protected files).
Quoted-header SyntaxError location RED014046447327Z-3caba67f403c -> GREEN014056192189Z-ecfef23a96ea.
Read docs/LOG_DIAGNOSTICS_VA_CACH_DOC_LOI.md for fields/PowerShell/history commands.
One fresh review,3findings fixed (HF class dispatch, header-like body, locations).
No public DTO/model/prompt/budget/source-fixture/VGAR change, no commit/push.
Effective observer uses pre-decode _get_logits_processor, unchanged args/return;
offline/doubles only, real GPU behavior/performance not newly qualified.
No deferred review findings; old static-feedback/JUnit minors remain outside
this logging task. B stillBLOCKED, C historicalV9PASS, finalNOT_RUN. Do not B5/reset.
Earlier in-progress entries below are history, not resume instructions.

User requests parser location/count diagnostics, full traceback and effective HF
config/attention-mask logs. No new repair generation authorized. B stays BLOCKED.
Snapshot before edits: results/diagnostics-preflight/20261015T012505328670Z-d98793260a4a/archive_manifest.json
(86 runtime/tests files,76 historical campaign files). Existing V3/V4 archive
and protected VGAR files retained. Fresh baseline152PASS87.40s at
results/tests/20261015T012507127206Z-d101c4b6f2b1/run_record.json; session17162 ended.
Parser/traceback RED9 at012653015518Z-4c824bd3c34e -> GREEN23 at012802495071Z-5320439dd95c.
Generation RED5 at012922164367Z-9b74123fb736 -> GREEN7 at013019096514Z-56babdb039b2.
Propagation RED4/14PASS at013135278926Z-d37f02c1f3d9 -> GREEN24 at013304543956Z-3ec4ff6780c6.
Initial full170PASS90.04s at013330347715Z-7461e561d08c (before review fixes; historical).
Fresh review identified instance _sample bypass by class dispatch, ambiguous
header-like body counts and header location gaps. All fixed through RED->GREEN;
focused32PASS at013810640202Z-39ea8e309fcb, RuffPASS. Fullsuite after first fixes
174PASS96.04s at013819704699Z-03fa3b9e5665; session26335 ended. Added quoted-header
exception case then final175PASS as recorded above. Guide/review/plan/docs and
offline replay/archive/doc audit complete; no pending work or model run here.
Plan:
docs/superpowers/plans/2026-10-15-m2-diagnostic-logging.md.
After runtime changes, old frozen campaign --status must reject new code;
use archive-based history, never rewrite frozen fingerprints/evidence.

## Authoritative terminal checkpoint — 15/10/2026

Approved adaptive V5+ implementation and bounded experiment are finished.
**Acceptance UNMET: campaign FAIL / TUNING_QUOTA_EXHAUSTED.** No inference is
running, no pending attempt, no final_profile.json. Do not resume generations
or create/reset a campaign to bypass the cap without new user approval.

- B: four FAILs, V5/V6 wrong counts; V7 missing context markers; V8 invented
  host_path_policy.json. All stopped at the existing strict parser. B BLOCKED;
  no B5, and unused C/final slots cannot be borrowed.
- C: first run V9 real PASS, no B feedback. Actual formatter.py repair;
  collection/fallback executed, baseline one FAIL/one PASS -> post two PASS;
  syntax, mypy, Ruff PASS; original source unchanged.
  Canonical: results/adaptive_acceptance/2026-10-15-v5-plus/attempts/05/20261015T005816855246Z-a997178dc2f5/run_record.json.
- Final A/B/C: NOT_RUN because B tuning never passed. Old A V3/V4 and new C V9
  are not pooled into same-template acceptance. No further C run after C PASS.
- Full suite **152 passed in 88.51s**, recorder 89.203s, exit0:
  results/tests/20261015T005945598043Z-a4f4d47f3d8d/run_record.json.
- Ruff + frozen runtime/source/profile/revisions + all five canonical/public
  bundles/caps/dead owners + historical archive audit PASS:
  results/checks/20261015T010114900109Z-cfbffe5811a9/run_record.json.
  This audit PASS is NOT experiment PASS. All five originals unchanged;
  69 archived runtime files,69 historical files,4 protected VGAR files preserved.
- New code: adaptive_campaign.py and run_adaptive_acceptance.py; only four
  existing modules changed: contracts/context_presentation/prompt/pipeline.
  Templates V5–V9 append-only, new unit tests and docs. Parser/verifier/fixture
  tests/config/model/budgets/registry untouched. No commit/push.
- Read results/adaptive_acceptance/2026-10-15-v5-plus/{REPORT.md,summary.json}
  and docs/ADAPTIVE_V5_PLUS_VA_CACH_DOC_EVIDENCE.md. Core offline work complete;
  real 3/3 and teammate reproduction/M3 integration are NOT accepted.
- Documentation handoff audit PASS: five Markdown files, six PowerShell blocks,
  thirteen tables; read-only VGAR Git status/diff recorded with command-scoped
  ownership exception (no global config):
  results/checks/20261015T010602134092Z-5a277ccd02b2/run_record.json.
  Earlier inline Python-c quoting error occurred before any write; corrected
  orchestration only, no campaign attempt or runtime change.

## Execution history — extension approved 15/10/2026 (not resume instructions)

Plan `docs/superpowers/plans/2026-10-14-adaptive-m2-w7-w8-repair-prompt-v5-plus.md`.
New campaign quota4B+4C+3final, same final template/no previous feedback for3realPASS.
Codex authors revisions; no prompt-designer model. Old campaign stays terminalFAIL.
Milestone1 archive/pins + fresh126PASS baseline complete. Prompt group RED4→GREEN22;
controller RED9→GREEN9; CLI/history/pending RED→combinedGREEN18. Full suite **144PASS**
90.19s at `results/tests/20261015T002457111204Z-87340a8f70c8/run_record.json`.
Ruff/genuine-tokenizer V5/history preservation PASS at
`results/checks/20261015T002833577904Z-40869529560c/run_record.json`.
Fresh review complete,3Important fixed with RED4→GREEN22. Full suite afterfix
**148PASS91.55s** at `results/tests/20261015T003431000678Z-2ed7f5d46960/run_record.json`.
Ruff/history PASS at `results/checks/20261015T003520341923Z-7c7ed0acbfac/run_record.json`.
Runtime frozen. B-V5 attempt01 terminalFAIL PATCH_PARSE_ERROR: counts2 vs body3;
source unchanged. Session54898 ended exit1, do not poll/relaunch it.
Canonical `results/adaptive_acceptance/2026-10-15-v5-plus/attempts/01/20261015T003703727090Z-e62648364844/run_record.json`.
V6 authored from observed counts error; neutral3-line hunk/unchanged assignment
context, no actual fixture solution. V6 test RED at20261015T004131406711Z-49ed91250767;
Focused GREEN23 at `results/tests/20261015T004212433083Z-207198c7cbfb/run_record.json`.
V6 B attempt02 terminalFAIL PATCH_PARSE_ERROR: declaredcount6 forbody3 and
emitted unauthorized testdiff; original source unchanged. Session47679 endedexit1.
Canonical attempts/02/20261015T004240341955Z-b5e07ce0a4e0/run_record.json.
V7 genericcompactinstruction maps fullsnippet start/count directly, testsreadonly,
no examples/numeric copying; newtestRED at20261015T004840664848Z-b296dcd224df.
FocusedGREEN7 at `results/tests/20261015T004924428681Z-ab4950e84c9f/run_record.json`;
V7 B3 terminalFAIL PATCH_PARSE_ERROR: correct paths/starts/counts, but missing
context-prefix spaces before def/unchanged assignment. Source unchanged;
session7596 ended exit1. Canonical attempts/03/20261015T004931535482Z-daa3ae13e75e/run_record.json.
V8 adds a neutral BODY-ONLY whitespace example, no numeric header or fixture answer.
New test RED at results/tests/20261015T005301742703Z-ab04aa6193bf/run_record.json;
focused GREEN8 at results/tests/20261015T005528142073Z-e80d98b5b5f9/run_record.json,
Ruff PASS. V8 B4 terminalFAIL PATCH_PARSE_ERROR (Protected or unapproved path):
model invented host_path_policy.json from permission metadata, no source patch.
Canonical attempts/04/20261015T005533899467Z-16d544650f34/run_record.json;
75.734s/input1655/output49/EOS/sourceunchanged. Session96365 ended exit1.
**B BLOCKED, quota4 exhausted; NEVER B5.** V9 explicitly separates metadata/source
and uses whole-snippet -/+ replacement, neutral Git-apply example only.
RED results/tests/20261015T005748137182Z-4ed713425863/run_record.json;
focusedGREEN8 results/tests/20261015T005810022680Z-43a7262e9a84/run_record.json,
RuffPASS. V9 registered; C1 (attempt05) running execsession79482, no B feedback.
Only poll existinghandle; runtime unchanged; final NOT_RUN because B notPASS.
No old campaign reset. Minor static feedback diagnostic selection deferred;
Codex must read full failed-check canonical stage, not only feedback summary.
Archive: `results/adaptive-preflight/20261015T001508430263Z-6296d566fd2e/archive_manifest.json`.
69original runtime/test/config/template files +69historical evidence files and4VGAR
dirty files protected. Use new `scripts/run_adaptive_acceptance.py --history` because
approved new runtime intentionally differs from old campaign code fingerprints.
Ledger `.superpowers/sdd/2026-10-14-adaptive-m2-w7-w8-repair-prompt-v5-plus/progress.md`.
Earlier14/10 sections below describe history, not current authorization.
Vietnamese adaptive guide: `docs/ADAPTIVE_V5_PLUS_VA_CACH_DOC_EVIDENCE.md`.

**Authoritative checkpoint, 14/10/2026:** the V3/V4 extension is terminal
**FAIL / FAILURE_LIMIT**, with four attempts and two failures. A passed under
both V3 and V4; B failed under both; C was not run. No inference is running.
Final self-test: **126 passed**, 87.16s, exit 0. See the terminal extension
checkpoint at the end. Earlier live entries below are historical, not resume instructions.

Plan: `../New_task/2026-10-13-m2-w7-w8-brainstorm-implementation-plan.md`.
User approved implementation on 14/10/2026 (Asia/Saigon).

## Scope and approvals

- Independent package here; VGAR is read-only at `b8e2461635b81d1ae790445efea5c9757d91700a`.
- User selected pinned HF Qwen3-4B prototype, Native on ONLY the three trusted fixtures.
- No benchmark, fine-tuning, M1 ranking changes, MCP transport changes, commit/push.
- One generation per run; two real failures/profile stop that method; keep raw evidence.
- Runtime worktree seed commits are private disposable data, not project commits.

## Milestones

- [x] M0 bootstrap/contracts/bounded executor/recorder
- [x] M1 consumer/fixed prompt
- [x] M2 generator/worker implementation + offline checks + real invocation
  - [ ] Real unified-diff format qualification: blocked after two failures
- [x] M3 private worktree/unified diff
- [x] M4 selection/collection/exact outcomes
- [x] M5 baseline/post syntax/type/lint
- [x] M6 pipeline/canonical evidence/CLI + final review fixes
- [ ] M7 real demos acceptance (blocked); offline demos/docs/handoff completed

## Current point

**Offline core complete; real repair gate BLOCKED. Not 100% plan acceptance.**

- Fresh full suite: **76 passed**, 70.42s; recorder 71.031s.
  `results/tests/20261014T093529864005Z-9dc514964a36/run_record.json`.
- Ruff E9/F PASS and reference/protected-file audit PASS:
  `results/checks/20261014T093651139400Z-ace940916093/run_record.json`.
  309 prior-manifest files unchanged. The older baseline's PROGRESS mismatch
  came from approved M1 checkpoint append at 07:27:40 UTC BEFORE M2 work;
  exception explicit, not an M2 edit. Source HEAD/pinned boundary intact.
- One fresh-context final reviewer; four Important fixes RED→GREEN: terminal
  export/cleanup, assessed public tests, stage/subprocess deadline, diff export.
  Details `docs/FINAL_REVIEW.md`; no second review/inference after fixes.
- New core/dev venv only; no Torch/model weights installed here. HF worker
  reuses an existing interpreter, does not import/edit old project source.

## Latest offline demo receipts (after review fixes)

| Case / mode | Status | Changed source files | Source unchanged | Receipt |
|---|---|---|---|---|
| single_file_login / fake | PASS | auth.py | true | `results/repair/20261014T093356677872Z-16526a595667/run_record.json` |
| multi_file_invoice / fake | PASS | invoice.py, pricing.py | true | `results/repair/20261014T093404983613Z-af38288e6594/run_record.json` |
| missing_links / fake | PASS | formatter.py | true | `results/repair/20261014T093412525344Z-f1913b231c8a/run_record.json` |

Each has applied.diff, public EvidenceBundle, matching terminal canonical hash,
actual pytest outcomes and syntax/mypy/Ruff checks. **Fake does not prove LLM repair.**

## Real model results and stop point

- Short invocation PASS, raw OK, 35.234s:
  `results/qualification/20261014T085555586866Z-7c81bac709ad/run_record.json`.
- A v1 FAIL, SEARCH/REPLACE, source unchanged:
  `results/repair/20261014T090352481580Z-8f8da9b4cddd/run_record.json`.
  Historical policy lacked explicit version field; read source/prompt hash.
  Summarizer correctly labels it unqualified-config, not a newly inferred version.
- A v2 FAIL, unified diff incorrect hunk counts (3 declared, 2 actual), source unchanged:
  `results/repair/20261014T091104527173Z-8e59e14c75c7/run_record.json`.
- **Do not rerun unchanged v1/v2 method.** Both outputs stopped before apply/post
  verification. Real B/C NOT_RUN because A format qualification failed twice.
- No process/model test is being kept running. No commit/push or VGAR edits.

## Resume without repeating completed work

1. Read this checkpoint, ledger, `docs/FAILURES.md` and `docs/FINAL_REVIEW.md`.
2. Do not rebuild/retest all milestones as implementation work or redo fake demos.
3. Next real step requires owner decision on a justified format/backend method;
   keep source/model budgets/guards unless explicitly approved to change.
4. Then run a new identifiable A with supersedes/reason; B/C only after A gate;
   never count fake/invocation as real repair. M3/human gates remain separate.

Vietnamese input→flow→output/self-test guide:
`docs/GIAI_THICH_M2_W7_W8_VA_CACH_KIEM_THU.md`.
Full historical milestone/RED receipts retained in `.superpowers/progress.md`.

## Extension approved 14/10/2026 — prompt V3/V4 and bounded real acceptance

User approved `docs/superpowers/plans/2026-10-14-close-m2-w7-w8-real-repair-and-prompt.md`.
Current point: source/profile preflight PASS, fresh baseline76 PASS; Milestone2 TDD in progress.
No new real repair launched. Caps6 new attempts/2 failures, samefinalprompt real3PASS required.
New ledger `.superpowers/sdd/2026-10-14-close-m2-w7-w8-real-repair-and-prompt/progress.md`.
Existing core/old real failures remain historical; do not reset/redesign M0–M6.

Latest extension checkpoint: Milestones1–3 implemented/offlineGREEN. Full117 PASS,
82.79s: `results/tests/20261014T142257272482Z-33e1efc5c889/run_record.json`.
Ruff E9/F and offline genuine-tokenizer V3/V4 prompts PASS:
`results/checks/20261014T142519151159Z-0490292ebed1/run_record.json`.
One fresh review in progress BEFORE freeze/inference; no new real model launched.
CLI `scripts/run_acceptance.py --status` readonly; --run defaults to the SAME
`results/acceptance/2026-10-14-prompt-v3-v4` campaign, no implicit counter reset.
Next: resolve Important review findings via one TDD pass, fullsuite/Ruff, then realcampaign.

Review fix pass complete: frozen taskJSON/DTO + canonical-ledger revalidation +
actualcollection/fallback/export evidence guards. Full126 PASS at
`results/tests/20261014T143340455463Z-3177af8ceb35/run_record.json`,85.36s.
Ruff/protected baseline PASS at `results/checks/20261014T143514929124Z-1034fc623cad/run_record.json`.
Now starting bounded realcampaign; inspect its live campaign.json and reserved
attempt root before resuming. Never re-create/reset to bypass6attempt/2failurecap.

Live extension: realA V3 PASS at
`results/acceptance/2026-10-14-prompt-v3-v4/attempts/01/20261014T143611380216Z-4cfb6e98732e/run_record.json`.
Controller execsession52814 running nextB V3; DO NOT start another --run process.
Use campaign.json/currentattemptcanonical for actual stage. V4 unused,0failures.

Latest: B-V3 FAIL at attempts/02/20261014T143724950165Z-28712948b7fb/run_record.json.
Controller switched presetV4 and restartedA (attempt03); do NOT poolA-V3PASS.
1failure/3reservedattempts; existing execsession52814 remainslive.

Observed B-V3 failure is semantic: pricing fix alone, invoice.py omitted,
parser/applyPASS but invoice testsFAIL. A-V4 PASS at
attempts/03/20261014T143844748488Z-ca62ce11f2d2/run_record.json;
B-V4 attempt04 running,1failure/4reserved. Frozen templates/code unchanged.

## Terminal extension checkpoint — do not restart inference

- Approved extension implementation: prompt presentation, V3/V4 templates,
  bounded/resumable controller, optional campaign metadata, TDD and review fixes complete.
  No parser/verifier/model/registry or M1 public DTO changes.
- Campaign `results/acceptance/2026-10-14-prompt-v3-v4/campaign.json` is
  complete, status **FAIL**, reason **FAILURE_LIMIT**, final_version **null**.
  Four attempts consumed, two failures. The failure cap takes precedence over
  the two unused attempt slots; do not reset or create another campaign to bypass it.
- Attempt 01: A/V3 PASS; attempt 02: B/V3 FAIL TEST_FAILED (invoice.py omitted).
  Attempt 03: A/V4 PASS after restarting A; attempt 04: B/V4 FAIL PATCH_APPLY_FAILED
  (invoice hunk starts at line 1 instead of 4). C **NOT_RUN** after the second failure.
  A passes across versions must not be pooled into a same-version three-case success.
- Actual runs retain raw output, prompts, token/timing/resource metadata,
  commands/results, patches where stages reached, and canonical/public evidence.
  All four report original_source_unchanged=true. No timeout/OOM was observed.
  Controller session 52814 completed with exit 1; no live repair/pending attempt remains.
- Final full self-test **126 passed in 87.16s**, recorder 87.766s, exit 0:
  `results/tests/20261014T144408789514Z-d6a80718ea70/run_record.json`.
  Its exec session 5082 has finished; do not poll or rerun either completed session.
- Terminal canonical/bundle/hash/cap/source audit PASS (this is not campaign PASS):
  `results/checks/20261014T144408183059Z-6b877af302ba/run_record.json`.
  Final Ruff E9/F + six PowerShell-block syntax checks + preservation audit PASS:
  `results/checks/20261014T145443813152Z-5f5c0a54d7d1/run_record.json`.
  Twenty unchanged existing core modules, protected VGAR files, old failure evidence
  and 72 frozen input/code files checked; no mismatch. All attempts terminal,
  original source unchanged and campaign controller confirmed no longer live.
- Milestones 1–3 implemented and verified. Milestone 4 finished the approved bounded
  experiment, **but real 3/3 acceptance is unmet**. Milestone 5 reporting/handoff
  prepared; teammate reproduction and M3 integration remain external gates.
- Do not redo M0–M6, fake demos, V1/V2, qualification OK, dependencies or weights.
  Further real attempts or a different prompt/backend require new owner authority;
  no V5, host diff repair, guard relaxation or unapproved resource change.
- No commit/push; VGAR and the old system remain unchanged by this task.

Read `docs/PROMPT_V3_V4_VA_NGHIEM_THU_REAL.md` for safe read-only commands and
`results/acceptance/2026-10-14-prompt-v3-v4/REPORT.md` for actual results.

