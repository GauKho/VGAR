# Kế hoạch hoàn tất M2 tuần 7–8: Repair Prompt V5+ theo evidence

User duyệt triển khai ngày 15/10/2026 (Asia/Saigon), sau khi chốt ba lựa chọn:
Codex cải thiện prompt; tối đa 4 B + 4 C + 3 final; cả ba final PASS cùng version.

**Checkpoint thực thi 15/10:** engineering và bounded experiment đã kết thúc;
campaign FAIL / TUNING_QUOTA_EXHAUSTED. B4FAIL, C1PASS(V9), finalNOT_RUN.
Các tick dưới đây chỉ xác nhận công việc/quy trình đã làm, không thay gate3/3.
152self-testsPASS; Ruff/auditPASS. Xem PROGRESS và campaignREPORT/summary.

Dành cho implementer: executing-plans, TDD, một fresh review trước inference;
không commit/push. Đây là bản lưu kế hoạch đã được duyệt trong hội thoại.

**Goal:** hoàn tất B/C real repair, khóa prompt cuối, chạy mới A/B/C cùng template,
không previous feedback và giữ repository gốc nguyên trạng.
**Architecture:** tái dùng core hiện có; Codex viết prompt giữa các lượt; script
quản lý từng generation, revisions, quotas, process ownership, evidence và resume.
**Tech stack:** Python, pytest/mypy/Ruff, Git worktree, HF Qwen pin hiện tại.
**Spec:** `../../../../New_task/project_plan_16_weeks.md`, mục M2 tuần 7–8 và các
quyết định của user trong hội thoại. Core126/fake3 và A V3/V4 PASS là baseline,
không làm lại implementation hoặc dùng fake thay real.

## Global constraints

- Chỉ M2_week_7_8; VGAR/old systems/M1 ranking/M3 MCP/tuần khác chỉ đọc.
- Qwen/Qwen3-4B-Instruct-2507 @ cdbee75f17c01a7cc42f958dc650907174af0554;
  giữ tokenizer, greedy, FP16, auto CUDA; không install/download/model OK lại.
- Input6000/output1536/reserve256; generation900s/command120s/global1800s/run.
- Native đúng ba byte-verified fixtures. Một generation/run, pristine workspace,
  baseline mới; không carry patch cũ, sửa/recount/fuzzy apply output hộ model.
- Giữ tests/gold/reference patches/parser/verifier/fixture registry.
- V3/V4 campaign terminal FAIL giữ nguyên. Phiên mới tối đa4B/4C/3final, tổng11;
  counters durable, không borrow/reset. Mọi ERROR runtime dừng, không prompt chữa OOM.
- Không commit/push. Không claim benchmark/held-out/global-optimal prompt.

## Review Focus

1. Absolute source lines vs snippet-local coordinates, counts/EOL/UTF-8 không đổi source.
2. Immutable prompt revisions + mutable append-only registration, historical runtime audit.
3. Resume/owner PID birth/concurrency/reservations không vượt quota hoặc chạy model trùng.
4. Feedback cùng case, bounded full-chat, tuyệt đối không feedback trong final.
5. Final3 cùng frozen template và canonical/public/applied evidence thật, không proxy PASS.

## Milestone 1 — Baseline/checkpoint

- [x] Đọc checkpoint/status/diff nếu có; không audit lại toàn repo. M2 hiện độc lập,
  non-Git: dùng approved isolation boundary và lưu ledger thay git commits.
- [x] Kiểm profile/source/handoff/tokenizer pins và process cũ trước inference.
- [x] Archive exact src/scripts/config/templates cùng hash mapping trước sửa runtime;
  không copy weights/cache. Hash old campaign/canonicals/raw/bundles trước thay đổi.
- [x] Historical reader dùng archive runtime hashes đối chiếu frozen manifest cũ,
  không giả định current code chính là code từng tạo old evidence.
- [x] Baseline full suite/receipt; không fake demos hoặc qualifier OK lại.

## Milestone 2 — Prompt và controller (RED → GREEN)

- [x] V5 ngắn, kiểm tất cả mệnh đề issue/helpers/units/necessary files, exact unified
  diff; absolute file coordinates, counts từ body. Không bắt sửa mọi allowed file.
- [x] Hai neutral files có hunks bắt đầu3 và6; offline strict parser và exact bind
  đối chiếu neutral originals. Không login/invoice/formatter solutions trong examples.
- [x] Metadata nhấn mạnh first shown line là original file line k, ngoài code;
  giữ nguyên M1 snippets/order/IDs/paths/hints/source bytes, không mở rộng context.
- [x] Internal registered m2-w78-vN (N>=5), không unknown-version fallback;
  legacy V1–V4 rendered defaults giữ nguyên. Optional feedback trong prompt/pipeline;
  public DTO/status unchanged, không thêm schema_version.
- [x] New adaptive_campaign.py/run_adaptive_acceptance.py, một next generation/lệnh.
  Runtime/model/tasks/source/handoff/tokenizer freeze riêng; prompt revisions append-only
  có hash/parent version/failed run/reason/change. Không đổi template đã dùng.
- [x] Feedback data cùng case tối đa300 tokenizer tokens; lưu full original log ngoài
  prompt, count full chat <=6000; không cắt source để fit. Final feedback=None.
- [x] Codex đọc logs/ghi hypothesis/sửa instruction có lý do sau FAIL, không cosmetic
  rename/retry y nguyên. Script không gọi thêm prompt-designer/planner/model.
- [x] TDD legacy/offset/EOL/feedback/registry/transitions/quota/resume/tamper gates;
  full suite + Ruff trước runtime freeze/model. Một fresh review và một TDD fix pass.

## Milestone 3 — Adaptive tuning B rồi C

- [x] Phiên cố định mới `results/adaptive_acceptance/2026-10-15-v5-plus`;
  reserve trước launch, counters survive resume, một generation/attempt.
- [x] B bắt đầuV5. FAIL parser/apply hoặc semantic/type/lint do patch: Codex chẩn
  đoán, đăng ký Vn+1, offline verify, chạy lại B nếu còn trong4lượt. PASS thì dừng B.
- [x] C bắt đầu template hiện tại; không feedback B. C FAIL cải thiện tương tự,
  tối đa4lượt. Không slots dư/undo old result/automatic undeclared new campaign.
- [x] Nếu B FAIL đủ4lượt: B blocked; vì C còn quota, Codex tạo revision mới từ
  lỗi cuối, offline validate và dùng revision đó cho C (không chạy B lượt5).
  Nếu không còn authorized tuning step sau FAIL thì không tạo revision vô ích.
- [x] ERROR/OOM/timeout/source/hash/môi trường/evidence incomplete: dừng phiên;
  không đổi model/resources/prompt để che runtime error. Confirmed interruption
  tiêu thụ reserved slot rồi terminal ERROR; live/unknown process không launch lại.
- [x] Nếu B hoặc C không PASS trong quota, không chạy final; ghi blocker đúng.

## Milestone 4 — Final validation

**Chưa đủ điều kiện chạy:** B tuning không PASS, nên cả ba final chưa chạy;
không đánh tick chỉ vì controller có unit tests cho nhánh này.

- [ ] Chỉ khi B,C tuning đều PASS: khóa template mới nhất C đã PASS.
- [ ] A→B→C fresh worktree/baseline, không feedback, cùng fixed template; 1run/case.
- [ ] Không adapt prompt trong final; dù FAIL vẫn chạy cases còn lại lấy evidence,
  trừ ERROR runtime dừng. Không quay về tuning hoặc dùng unused slots để retry final.
- [ ] Chỉ3realPASS cùng frozen version với parser/apply/tests/syntax/mypy/Ruff,
  canonical-public hash/applied export/source guards đúng mới nghiệm thu.
  B phải sửa2sourcefiles; C collection và fallback actual execution. Không pool old/fake/OK.

## Milestone 5 — Evidence, review, handoff

- [x] Mỗi attempt lưu prompt/version/hash/feedback parent/raw/patch artifacts,
  baseline/post commands/stdout/stderr/exit codes, token/time/resources/bundle/source.
- [x] Tuning/final reports tách riêng; failures nêu nguyên nhân/phương pháp tránh lặp.
- [x] Full suite/Ruff cuối, protected original/runtime/old evidence audit.
- [x] Update PROGRESS/failures/completion/Vietnamese guide; chuẩn bị quy trình replay.
- [ ] Teammate replay một fixture giữ config/pin/output riêng: chưa có xác nhận
  độc lập; chưa có final profile. Không ký thay teammate/M3 integration gates.
- [x] Có checkpoint WAIT_PROMPT/pending để tiếp tục khi usage gián đoạn.

## Tests và giới hạn kết luận

New TDD: neutraloffset3/6 exactbind; file vs snippet line; LF/CRLF/blank/UTF8/partial;
oldV1–V4 unchanged; invalid/missing/tampered revisions; feedback wrong case/budget/final;
B4 exhausted still C; C4 stop; all11maximum; final no mixing/adaption; process PID birth,
interruption/concurrency/tamperedledger; oldV2 malformed still reject; actualB2files/Cfallback;
canonical/public artifacts/source protection. Test harness doubles không tính real acceptance.

Tối đa11×1800s=5.5h global run budget + engineering/prompt authoring/finalization, không
cam kết thời gian. Không API bill nhưng điện/local compute/Codex usage vẫn có chi phí.
Ba development fixtures và adaptive feedback có overfit risk; không phải SWE-bench rate,
không bảo đảm luôn PASS hoặc prompt tối ưu toàn cục. Nếu hết quota, báo UNMET chứ không
hạ guard/tiêu chí. Human reproduction và M3 transport là external gates.
