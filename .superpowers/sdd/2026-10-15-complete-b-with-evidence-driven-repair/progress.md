# SDD ledger — plan: docs/superpowers/plans/2026-10-15-complete-b-with-evidence-driven-repair.md

Ruling: M2 là package độc lập non-Git do user chỉ định; dùng snapshot119files
ở results/b-repair-preflight/20261015-evidence-driven/baseline thay git/worktree
scripts. Không initGit/commit/push/xóa ledger; mất record sẽ không khôi phục quaGit.
Pre-flight: tokenizer flag -> feedback budget -> promptfullcount -> generator
input hash phải đồng nhất; request optional flag defaultTrue giữ legacy.
Pre-flight: runtime fixes -> store chỉ freeze security/task/model campaign-wide,
runtime per-revision; không đổi old adaptive store vì old frozen hash immutable.
Pre-flight: pipeline runtime hash -> attempt bound; fresh process và postrun audit.
Task1 complete: checkpoint/source pin/assets/process scan,119scoped baseline copies;
RTX4050 6141MiB/280MiB used, no Python/Git process observed, no generation launched.
Task2 in progress: tokenizer RED -> GREEN. Task3/4/5 pending. Realattempts0of8.

Task2 complete: RED3FAIL/1PASS at063401380978Z-281950c2d92f -> GREEN10 at
063426430770Z-f4a220f2b907 (tokenizer+generationdiagnostics). True/False request/cache
fix, generate stillTrue; no claim this caused old B malformed outputs.
Task3 complete engineering: RED5FAIL/9PASS at063537851535Z-97c4bfbb77f9 ->
GREEN32 at063633796190Z-e1d256f99888 (V10/V9/V3-V4 neutral/legacy). Source permissions,
replacement metadata, no partial-line expansion, snippets unchanged.
Task4 engineering tests: RED missing bmodule at064001718527Z-a7c3d06fe833,
initial GREEN controller at064241532141Z-a024922fedfd. Acceptance/hook RED at
064427604167Z-a78cef2cca74; CLI RED at064556239423Z-02204e7734bd. First combined
run15PASS/1FAIL at064750883360Z-67f5d58d6b41: test incorrectly excluded old
historical worker artifacts; corrected expectation, not protected production.
Gate routing RED3 at064922490535Z-53b0a64e19dd -> GREEN19 at064928448983Z-486d7f1c0d19.
RuffPASS. Current fullsuite running output full-before-review, session62383.
Fresh read-only reviewer b_experiment_preinference_review working, no inference0/8.
Ruling: record_tests adds exact runtime_before/after fingerprints so full-suite
qualification is bound to code, not an unrelated old green report; existing
pytest selectors/commands/acceptance unchanged. Cost if wrong: suite must rerun.
Ruling: freeze old worker artifacts too; they are historical evidence, unlike
new B workers. Input freeze includes old parser/verifier/fixtures/old tests and
old campaigns; new test files may be added but old tests are not changed.
Ruling: actual model revision is pinned local-cache ID/config/tokenizer assets,
not a new independent full weight attestation; no GPU load/weights copy/download.
Next: read fullsuite/reviewer, one justified TDD fix pass, fullsuite then register
initial runtime/prompt and launch B only. Do not init/reset old campaigns.

Final review: one fresh reviewer found six Important lifecycle/integrity issues;
all accepted after inspecting code. No additional review loop. TDD RED10 at
065636559766Z-bcef44425975 -> GREEN29 at065738423959Z-65ed65e1ff31.
Fixed canonical re-assessment and independent immutable outcome receipt/time;
post-reservation protected checks; resume-safe identical orphan registrations;
durable reservation before mkdir; structured integrity STOP; absolute reservation
deadline through preflight/pipeline. Added expired-deadline regression too.
Ruling: reject CRLF prompt templates BEFORE registering/reserving, rather than
change V1-V9 normalization/hash semantics. Neutral context CRLF remains supported.
Cost if wrong: author must save a new prompt as UTF-8 LF before registration.
Reviewer declined actual inference/unknown lock holder/weight-byte attestation:
no unsupported claims; real generation remains pending, never kill unknown PID.
Full baseline220PASS128.12s before review; final fullsuite pending fixes qualification.

Final fix verification fullsuite231PASS120.82s (recorder121.609s), exit0 at
full-qualified/20261015T065821488334Z-8d31dfbd21e5/run_record.json; fingerprint
before/after exact. RuffPASS archived on initial runtime registration.
Task4 complete engineering; campaign initialized, r001/V10 registered append-only.
Task5 started attempt1 B; inspect campaign/canonical for pending ownership, never
repeat a launch after observing timeout. Realattemptbudget max8/14400seconds.

Attempt1 V10/r001 FAIL parser line1 BEGIN FORMAT DIFF; raw18lines164tokens EOS,
no truncation. Generation147.141s, reservation169.220641s. Sourceunchanged and
cleanupPASS; currentremaining14230.779359s. Effective actual greedy/mask observed;
18layers GPU, laterlayersCPU. Prompt delimiter copying is directly observed.
New runtime bug evidenced: diagnosis scans stage command timeout_seconds and
calls any FAIL runtime. Reproduced RED in test_b_failure_routing then GREEN.
Ruling: keep original r001 diagnosis/receipt immutable; r002 reconstructs feedback
category from canonical using fixed classifier, no rewriting history. Cost if
wrong: feedback omitted; no acceptance guard relaxed. V11 removes wrapperlabels,
adds literal first/last output contract; no host stripping/corrected/gold patch.
Focused GREEN3 at070540730947Z-85738af68f0b. Fullsuite qualification next.

Full r002234PASS124.45s, RuffPASS; proof full-r002-v11/
20261015T070616016658Z-306d4603f3b7/run_record.json. Registered r002+V11 against
attempt1 trigger, fresh host/worker attempt2 now running session79673. No A/C.

Task5 complete: attempt2 V11/r002 **PASS**, no gate errors, originalsourceunchanged;
required2FAIL→PASS/regressionPASS, actual2fileschanged, parser/apply/signatures/
syntax/mypy/Ruff/cleanup/bundle/provenance allPASS. No furthergeneration.
Canonicalattempts/02/20261015T070916546459Z-29b6c2d320ff/run_record.json.
input1905/output157/EOS, actualmaskallones[1,1905], greedy/maxnew1536 observed;
generation163.079s, canonical185.094s, reservation185.845466s.
Finalused2slots/355.066107s; newcampaignterminalPASS. Scope auditPASS at
closeout/20261015T071410556116Z-462218813a53 (119baselinefiles, expected7existing
modified, frozenprotectedset and r002fingerprint intact, RuffPASS).
Final minor (deferred): PASS diagnosis fallbackunknown/STOP remains generic;
no effect on PASS/nextNone/stop_reasonNone/gates[], originalreceipt preserved.
Task6 complete: Vietnamese report KET_QUA_B_EVIDENCE_DRIVEN_2026_10_15.md and
guide CHAY_B_EVIDENCE_DRIVEN_POWERSHELL.md, PROGRESS updated. No Git/push/delete.
No whole-M2/3cases/independent/SWEbench claim. Keep ledger/snapshots per user.

Finish: finishing-a-development-branch adapted to explicit non-Git/no commit/
push request: keep standalone project as-is, no integration menu or deletion.
Current production fingerprint equals r002 fullsuite234PASS proof (rechecked in
closeout); only docs/checkpoint edited afterward. No duplicate unchanged fullsuite
or inference solely to re-verify the same runtime. Rulings remain enumerated in
Vietnamese report section7; deferred PASS diagnosis cosmetic explicitly recorded.
