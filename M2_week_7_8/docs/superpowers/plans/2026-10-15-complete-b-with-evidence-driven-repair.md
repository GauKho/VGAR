# Hoàn tất B — M2 tuần 7–8, kế hoạch được duyệt 15/10/2026

> Implementer: executing-plans, TDD, một fresh review trước inference. Không
> commit/push. Căn cứ: project_plan_16_weeks.md mục M2 tuần7–8 và bản kế hoạch
> user đã duyệt trong hội thoại. Chỉ B, không mở rộng A/C hoặc tuần9–16.

## Mục tiêu và ràng buộc

Real `multi_file_invoice`: model tự sinh unified diff, sửa thực tế cả pricing.py
và invoice.py, parser/apply/verification PASS, source gốc không đổi. Dừng tại
PASS đầy đủ đầu tiên sau audit, không thêm run xác nhận. Tối đa8 reservation
mới/14.400s tổng global run budget, kể cả ERROR/interruption. Không tự reset.
Không bảo đảm prompt sẽ PASS; hết budget/blocker ngoài phạm vi phải báo UNMET.

- Chỉ M2_week_7_8. VGAR/M1/M3/old systems chỉ đọc; không fine-tune, model switch,
  cài/tải dependencies/weights, mua tài nguyên, SWE-bench hoặc commit/push.
- Qwen/Qwen3-4B-Instruct-2507 @ cdbee75f17c01a7cc42f958dc650907174af0554;
  tokenizer hiện có, greedy, FP16, device_map=auto (có thể CPU offload).
- Input6000/output1536/reserve256; generation900s/command120s/global<=1800s/run.
- Parser/verifier/tests/registry/source fixtures/gold/reference patch giữ nguyên.
  Không sửa raw/recount/fuzzyapply/đổi unified diff thành JSON để làm PASS.
- Baseline gần nhất183offlinePASS104.62s sau cleanup fix. Không làm lại core.

## Nguyên nhân và thiết kế đã chốt

| B history | Bằng chứng | Hướng xử lý |
|---|---|---|
| V3 | Chỉ sửa pricing, invoice còn lỗi | Đủ issue clauses |
| V4 | Invoice hunk line1 thay vì4 | Absolute original coordinates |
| V5 | Count2 nhưng body3 | Whole-snippet replacement/counts |
| V6 | Count toàn file6; raw còn sửa tests | Read-only/editable metadata tách rõ |
| V7 | Thiếu context markers | Kế thừa replacement styleV9 |
| V8 | Bịa host_path_policy.json | Permission không phải source/file |
| Cleanup | Win32 seed rmdir | Giữ bounded retry/log đã kiểm chứng |

V5–V8 EOS/not truncated, không chứng minh thiếu output tokens. V9 chỉ C PASS,
chưa B-tested. Warning generation/mask không tự là nguyên nhân B thất bại.

### Milestone 1: baseline và bảo toàn

- [x] Đọc checkpoint/current diff nếu có; scoped snapshot/hash, không audit lại repo.
- [x] Kiểm B/handoff/source/model/tokenizer/process; private TEMP/TMP.
- [x] Bảo toàn old terminal campaigns/evidence, không reset frozen hashes.

### Milestone 2: tokenizer (RED → GREEN)

- [x] HFChatTokenizer truyền add_generation_prompt vào tokenize request/cache key.
- [x] Backend tokenize giữ đúng True/False, defaultTrue; generate luônTrue.
- [x] Test cache separation/render/tokens/full input hash/budget.

Lỗi này làm sai count riêng của feedback; không gán là B root cause.

### Milestone 3: V10 trước B

- [x] Full-snippet replacement -/+; một hunk/range không overlap; absolute starts,
  counts riêng; chỉ necessary production files, đủ issue, giữ signatures/behavior.
- [x] Edit_permission + Patch_old_start/count derived từ validated source/ranges;
  tách read-only tests, editable source và permission metadata, không mở rộng source.
- [x] Giữ snippet bytes/order/IDs/paths/provenance/M1 payload. Không nhầm snippet
  thiếu newline với EOF file; partial-line range không đủ phải chặn trước generation.
- [x] Hai neutral files, starts/counts khác nhau; không invoice/percentage/gold solution.
- [x] Offline parser/exactbind/Git apply cho LF/CRLF/EOF/2–3lines/partial ranges;
  legacyV1–V9 không đổi; full suite và Ruff trước inference, hash templateV10.

### Milestone 4: BExperimentStore + scripts/run_b_experiment.py

- [x] init/status/register-prompt/register-runtime/run-next/recover/history; no reset.
- [x] Campaign freeze model/task/context/policy/protected files; prompt/runtime
  revisions immutable riêng. Runtime revision có parent, defect/hypothesis,
  triggering record, diff/hash/snapshot và offline test evidence.
- [x] Reserve trước launch, max8 cả ERROR/interruption; elapsed budget gồm pending.
  Fresh host/worker + workspace/baseline,1generation/attempt, không carrypatch.
- [x] Check pre/post runtime fingerprints/canonical provenance; reject unchanged
  runtime+prompt+rendered input; không parallel/live/unknown-owner restart.
- [x] Không chạy khi hết quota/time; effective deadline không vượt remaining cap.
  Safe finalization xong và log thời gian thực, không ngắt cleanup để che số liệu.

### Milestone 5: chạy B, chẩn đoán và sửa tiếp

- [x] V10 feedbackNone. Sau fail, Codex đọc evidence, ghi hypothesis/change/proof;
  sửa prompt hoặc bug M2 có bằng chứng rồi register và chạy tiếp trong quota.
- [x] Candidate parser/apply/tests/type/lint fail -> prompt/context improvement;
  tokenizer/serialization/log/workspace bug -> regression RED/GREEN + runtime revision.
- [x] OOM/timeout/worker/IO/Win32 -> runtime investigation, không prompt chữa hạ tầng.
  Hash/protected mismatch -> hard stop. Không phân loại được -> pause diagnosis.
- [x] Feedback cùngB<=300tokens, diagnostic actual/counts_complete đúng; không gold,
  corrected diff, tự viết patch hoặc thay tests. V11/V12 append-only nếu prompt đổi;
  runtime-only fix không bắt buộc đổi prompt; không retry cosmetic/unchanged tuple.
- [x] Không đổi generation/mask chỉ vì warnings. Model/resource/M1/M3/contract
  expansion cần approval mới. Không kill unknown external process/tắt antivirus.

Codex đang thực thi là người sửa prompt/code; runner không tự gọi thêm designer
model hay tự viết source. Engineering/offline time báo riêng với real run time.

## Tests, gate và bàn giao

- [x] TDD tokenizer/flags/cache/input binding; neutral examples/budget/legacy rendering.
- [x] Classifier đúng precedence, OOM/IO không buộc prompt đổi; immutability/runtime
  mismatch/quota/time/resume/live/dead/PID birth/duplicate; B-only, old history intact.
- [x] Cleanup short lock PASS, persistent lock ERROR; fullsuite/Ruff before inference.
- [x] B PASS chỉ khi raw parse nguyên bản; apply byteattested cả2files; required2
  baselineFAIL->PASS/regression+collection thực thi; syntax/mypy/Ruff/signatures giữ;
  cleanupPASS/source/tests/config intact; bundle/canonical/applied hashes đúng.
- [x] Actual config/attention mask/tokens/placement diagnostics, không điền hồi tố;
  existing assess_record + provenance gates, không chỉ top-levelPASS.
- [x] Dừng sau first auditedPASS; development feedback result, không claim independent
  reproduction/3of3/SWEbench/global optimal. Không extra confirmation run.
- [x] Mỗi attempt đủ prompt/runtime/raw/parser/patch/baseline/post/commands/stdout/
  stderr/exit/traceback/tokens/time/mask/placement/cleanup/source/bundle evidence.
- [x] Update PROGRESS, failures table, REPORT và hướng dẫn PowerShell sau mỗi task/run.
  Hết8/4h, không có hypothesis có căn cứ, ngoài phạm vi -> UNMET/BLOCKED, không reset.

## Kết quả thực thi — 15/10/2026

B đạt PASS ở attempt2 V11/r002; dừng ngay, không confirmation run. Dùng2/8 slots,
355,066107 giây/14.400 giây real-run. Full suite hiện tại234PASS và RuffPASS.
Evidence/giải thích: docs/KET_QUA_B_EVIDENCE_DRIVEN_2026_10_15.md.
Hướng dẫn: docs/CHAY_B_EVIDENCE_DRIVEN_POWERSHELL.md. Checkpoint: PROGRESS.md.
Minor log PASS diagnosis fallback được ghi rõ, không ảnh hưởng acceptance.
Các checkboxes là kết quả triển khai trong phạm vi B, không phải xác nhận A/C,
reproduction độc lập, benchmark hoặc weight-byte attestation.

