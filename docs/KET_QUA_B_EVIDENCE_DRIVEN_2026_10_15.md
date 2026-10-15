# Kết quả triển khai B — M2 tuần 7–8 (15/10/2026)

## 1. Phạm vi và cách đọc kết quả

Chỉ hoàn tất `multi_file_invoice` (B), theo plan đã duyệt
`docs/superpowers/plans/2026-10-15-complete-b-with-evidence-driven-repair.md`.
Không triển khai A/C, SWE-bench, fine-tuning, model khác hoặc hệ thống VGAR/M1/M3.
Giữ parser/verifier/tests cũ/fixtures/registry/gold nguyên trạng; không chỉnh raw
output, recount, fuzzy apply hoặc viết patch thay model.

Đây là **development repair có thể dùng feedback**. Không suy ra prompt tối ưu
toàn cục, tái lập độc lập, nghiệm thu ba cases cùng version hoặc SWE-bench resolved rate.
Ngân sách tối đa 8 reservation / 14.400 giây real-run. Dừng ở PASS đã audit đầu tiên.

## 2. Các thay đổi implementation

| Phần | Trước | Sau | File |
|---|---|---|---|
| Feedback tokenization | Bỏ qua `add_generation_prompt=False`; cache chưa tách cờ | Request/worker/cache truyền đúng cờ; generate vẫn True | `src/vgar_m2_w78/generator_hf.py`, `hf_backend.py` |
| Prompt V10 | Chưa có replacement metadata/permission của phiên này | Original-file start/count, whole-snippet `-/+`, allowed/read-only; ví dụ trung tính | `prompts/repair_v10.txt`, `context_presentation.py`, `prompt.py` |
| Prompt V11 | V10 bị model sao chép format delimiters | Bỏ delimiter, nêu rõ first header/last body line, giữ format và hạn chế cũ | `prompts/repair_v11.txt` |
| Điều phối | Chưa có B-only quota 8/4h riêng | Exclusive owner, immutable prompt/runtime revisions, reservation trước launch, resume không reset, dừng first PASS | `src/vgar_m2_w78/b_experiment.py`, `scripts/run_b_experiment.py` |
| Provenance | Chưa bind runtime vào qualification/attempt | Snapshot/diff/hash/test proof, input identity, immutable outcome receipt và re-assess canonical | `b_experiment.py`, `scripts/record_tests.py` |
| Trusted inputs | Chưa freeze riêng phiên B | B/handoff, old campaigns, old tests/fixtures/guards, tokenizer/model metadata được hash | `src/vgar_m2_w78/b_inputs.py` |
| Nghiệm thu | Có gate core | Core gate giữ nguyên, thêm model/policy/task/runtime/prompt/raw/signature/diagnostic audit | `src/vgar_m2_w78/b_acceptance.py` |
| Pipeline | Deadline bắt đầu khi vào pipeline | Hook trước generation và optional absolute reservation deadline; legacy callers không đổi | `src/vgar_m2_w78/pipeline.py` |
| Phân loại lỗi r002 | r001 nhầm metadata `timeout_seconds` thành timeout exception | Tách exception text với structured stage metadata, integrity vẫn ưu tiên STOP | `b_experiment.py`, feedback trong `run_b_experiment.py` |

Tên module rút gọn trong bảng nằm dưới `src/vgar_m2_w78` nếu không ghi khác.
Không khẳng định lỗi tokenizer là nguyên nhân các raw diff lịch sử sai counts.
Không thêm attention mask/chỉnh sampling chỉ vì warning.

## 3. Review và offline evidence

Snapshot trước chỉnh: `results/b-repair-preflight/20261015-evidence-driven/baseline/`
(119 scoped files, không copy weights). M2 là package non-Git; không init Git,
không commit/push; snapshot và ledger được giữ lại để phục hồi.

Một review độc lập phát hiện sáu vấn đề Important trước inference: tin outcome/
elapsed của ledger; chưa kiểm lại protected inputs cuối run; crash registration/
reservation; integrity ERROR bị phân loại runtime; deadline bị bắt đầu lại;
CRLF template lệch hash. Đã tái hiện RED rồi sửa: canonical re-assessment/receipt,
protected checks, identical-orphan adoption không overwrite archive, lưu reservation
trước mkdir, structured integrity STOP, absolute deadline và chặn CRLF template
trước registration. Không nới parser hoặc verifier.

| Test/check | Kết quả | Evidence dưới `results/b-repair-preflight/20261015-evidence-driven/` |
|---|---|---|
| Tokenizer RED → GREEN | 3 FAIL/1 PASS → 10 PASS (cùng diagnostics tests) | `red-tokenizer/20261015T063401380978Z-281950c2d92f`, `green-tokenizer/20261015T063426430770Z-f4a220f2b907` |
| V10/legacy/neutral | 32 PASS | `green-v10/20261015T063633796190Z-e1d256f99888` |
| Controller/CLI/audit focused | 19 PASS | `green-b-integration/20261015T064928448983Z-486d7f1c0d19` |
| Review regressions | RED 10 FAIL → nhóm GREEN 29 PASS | `red-review/20261015T065636559766Z-bcef44425975`, `green-review/20261015T065738423959Z-65ed65e1ff31` |
| Full suite r001 | **231 PASS, 120,82s**, recorder 121,609s | `full-qualified/20261015T065821488334Z-8d31dfbd21e5` |
| r002 routing + V11 | RED 2 FAIL/1 PASS → **3 PASS** | `red-r002-v11/20261015T070504726517Z-1766694ad35d`, `green-r002-v11/20261015T070540730947Z-85738af68f0b` |
| Full suite r002 | **234 PASS, 124,45s**; Ruff PASS khi register | `full-r002-v11/20261015T070616016658Z-306d4603f3b7` |

Mỗi test evidence folder có `run_record.json`, command, stdout/stderr, timestamps,
exit code và JUnit. Offline/fake tests không tính thành real repair PASS.

## 4. Lịch sử phiên B mới — không trộn với campaigns cũ

Manifest: `results/b_repair/2026-10-15-evidence-driven-b/campaign.json`.

| Lượt | Prompt/runtime | Kết quả | Nguyên nhân/evidence | Thay đổi và bước tiếp |
|---|---|---|---|---|
| 1 | V10/r001 | **FAIL — PATCH_PARSE_ERROR** | Raw dòng 1 `BEGIN FORMAT DIFF`; 18 dòng, EOS, không truncated, 164 output tokens. Parser từ chối trước apply | V11 bỏ literal wrapper; r002 sửa bug phân loại timeout metadata; test rồi đăng ký revision mới |
| 2 | V11/r002 | **PASS — audit gate errors rỗng** | Raw tự parse/exact bind/apply; hai production files đổi; baseline 2 FAIL → post 3 PASS; static/cleanup/bundle/integrity PASS | Dừng ngay, không lượt xác nhận thêm |

Lượt 1 canonical:
`results/b_repair/2026-10-15-evidence-driven-b/attempts/01/20261015T070104677647Z-57e15f34010f/run_record.json`.
Không strip wrapper để apply và không công bố semantics PASS vì chưa chạy post-tests.
Receipt r001 ban đầu ghi category runtime là bug classifier; giữ receipt nguyên bản,
giải thích tại đây và ghi reason của r002, không sửa lịch sử cho đẹp.

Lượt 1: input 1.740, output 164; generation 147,141s; reservation 169,220641s.
Actual effective config: `do_sample=false`, `max_new_tokens=1536`;
mask `[1,1740]`, binary, toàn ones; host không tự thêm mask. Device map có layers
GPU và CPU. Không có bằng chứng token cap/generation timeout gây FAIL lần này.
Cleanup PASS, repository gốc không đổi. Baseline đúng hai required FAIL và một
regression PASS. Post-tests NOT_RUN vì parser fail, không được tính PASS.

### Lượt 2 — B đã nghiệm thu development repair

Canonical:
`results/b_repair/2026-10-15-evidence-driven-b/attempts/02/20261015T070916546459Z-29b6c2d320ff/run_record.json`.

| Gate | Evidence thực tế |
|---|---|
| Real generation | Qwen/SHA/profile pin giữ nguyên; một generation; EOS, không truncated |
| Prompt/feedback | V11, 1.905 input tokens; feedback B 131 tokens ≤ 300 |
| Output | 157 tokens; raw nguyên bản bằng candidate bytes, không strip/recount/sửa nội dung |
| Parser/exact bind/apply | PASS; Git export `applied.diff` có cả `invoice.py`, `pricing.py` |
| Required baseline | `test_discount_percentage` FAIL; `test_invoice_percentage_tax` FAIL |
| Regression baseline | `test_invoice_without_adjustments` PASS |
| Post-tests | Cả ba tests trên PASS; collection chạy thật, không chỉ suy từ test links |
| Static/signatures | syntax, mypy, Ruff PASS; signature AST đối chiếu không đổi |
| Actual generation diagnostics | effective_observed=true; do_sample=false; max_new_tokens=1536; mask `[1,1905]` binary, zero=0 |
| Device placement | GPU/CPU auto offload; không phải toàn GPU |
| Cleanup/source | Cleanup PASS (16ms); original_source_unchanged=true; protected inputs đúng hash |
| Bundle/provenance | Core audit + B audit PASS; canonical, bundle, prompt/runtime/input/applied bindings đúng |
| Thời gian | Generation **163,079s**; canonical pipeline **185,094s**; reservation **185,845466s** |

Raw model sửa phép trừ flat discount thành phần trăm giá gốc, và tax flat thành
phần trăm net sau discount. Các thay đổi này chỉ được áp dụng trong private
worktree; fixture gốc vẫn cố ý chứa lỗi để tái lập baseline. Để xem bản sửa, mở
`applied.diff`, không nhìn fixture gốc rồi kết luận agent chưa sửa.

Cùng folder canonical có `prompt.txt`, `raw_model_output.txt`, `candidate.diff`,
`applied.diff`, `evidence_bundle.json` và `REPORT.md`. Canonical SHA256:
`56af0a0e48b5dee0e35eba345a08862a245fe269eea6daf5f98aeeecefc51e07`.

**Tổng phiên mới:** 2/8 slots; **355,066107 giây** reservation (~5 phút 55 giây),
310,220 giây generation; 3.645 input / 321 output tokens của hai generations.
Không tính các lượt lịch sử cũ vào hai lượt mới, nhưng giữ chúng trong evidence.
Thời gian tokenizer workers, baseline và finalization nằm trong reservation;
offline tests/engineering tách riêng. Tổng engineering wall time chưa được đo
độc lập, không suy ra bằng cách cộng các test duration đang chạy xen kẽ.

**Log nhỏ còn lại, không phải blocker:** `attempt2.diagnosis` giữ fallback
`unknown/STOP` của classifier dùng cho failures, vì PASS không có nguyên nhân lỗi.
Đây không phải integrity STOP: `status=PASS`, `complete=true`, `reason=null`,
`gate_errors=[]`, `stop_reason=null`, `next=null`. Không sửa receipt sau nghiệm thu.
Đọc outcome/gates thay vì coi diagnosis của PASS là một failure mới. Cosmetic này
được ghi lại cho lần chỉnh UI/log sau; không chạy model thêm để làm đẹp nhãn.

## 5. Đầu vào → xử lý → đầu ra

```text
examples/tasks/multi_file_invoice.json
  + examples/snapshots/multi_file_invoice (source/test nguyên gốc)
  + examples/handoffs/multi_file_invoice (M1 ContextPayload đã validate)
  + pinned Qwen/tokenizer + registered prompt/runtime
      → reserve slot / private workspace
      → collection + baseline thật
      → context presentation M2 + full-chat token budget
      → một generation Qwen thật, lưu raw nguyên bản
      → strict parser → exact bind/Git apply → byte attestation
      → post collection/tests + syntax/mypy/Ruff
      → cleanup + original-source integrity
      → EvidenceBundle/canonical → core audit + B provenance audit
      → immutable outcome + campaign REPORT/checkpoint
```

Mỗi attempt mới dùng baseline/workspace mới; không mang patch cũ sang.
Prompt, raw, candidate/applied diff và bundle nằm cùng terminal canonical folder
(tham chiếu bằng `record.artifacts`). Failed stage chưa có artifact thì để null/
NOT_RUN, không chế tạo output. Worker request/response/diagnostic nằm trong
`attempts/<NN>/model-workers`, snapshot revisions nằm `runtime-archives` /
`prompt-archives`; manifest hashes nằm `revisions`.

## 6. Hướng dẫn chạy/đọc và giới hạn

Hướng dẫn chi tiết: `docs/CHAY_B_EVIDENCE_DRIVEN_POWERSHELL.md`.
Không cần tự dán run folder; đọc đúng `attempt.record` trong manifest. Khi PASS,
không chạy thêm lệnh `--run-next`. Khi process pending/LIVE, chỉ quan sát/recover,
không mở worker khác. Hash mismatch phải dừng, không chấp nhận snapshot mới âm thầm.

API bill: không gọi API trả phí/model khác. Compute local/điện vẫn có chi phí,
không có phép đo điện để quy thành số tiền. Engineering và offline tests không
được cộng nhầm vào token/latency generation của real run.

## 7. Trạng thái cuối

**Hoàn tất mục tiêu B đã duyệt**: lượt 2 V11/r002 PASS, dừng first audited PASS.
Không còn pending attempt; không chạy thêm A/C hoặc confirmation.

Scoped closeout audit đã chạy read-only lại canonical/core/B/protected inputs,
kiểm tra đúng 7 existing files được phép thay đổi trong 119 baseline copies,
runtime r002 còn khớp và Ruff PASS:
`results/b-repair-preflight/20261015-evidence-driven/closeout/20261015T071410556116Z-462218813a53/run_record.json`.
Không sửa code production sau full suite r002. Không commit/push.

### Các quyết định kỹ thuật và giới hạn bàn giao

1. M2 non-Git: dùng snapshot/ledger thay worktree và giữ chúng; nếu mất thì không
   có Git history để phục hồi. Không tự init/commit trái yêu cầu.
2. Qualification phải khớp runtime trước/sau tests; đổi code phải chạy suite lại
   (chi phí là một lần suite), không lấy report xanh không liên quan.
3. Freeze cả old worker artifacts vì đó là history; không freeze new worker output
   như input bất biến. Sai phân loại có thể chặn resume, không âm thầm sửa hashes.
4. Model pin là revision/cache metadata và tokenizer assets, không phải chứng nhận
   độc lập toàn bộ weight bytes. Muốn chứng nhận mạnh hơn cần audit weights riêng.
5. Prompt revisions chỉ nhận UTF-8 LF; dùng CRLF bị chặn trước reservation. Giữ
   legacy rendering/hashes; tác giả phải lưu LF, không đổi V1–V9 để xử lý hậu quả.
6. Receipt diagnosis r001 được giữ nguyên dù classifier sau đó được sửa; feedback
   dùng reclassification canonical. Nếu phân loại thiếu, phải dừng chẩn đoán chứ
   không sửa receipt hoặc chạy lại vô căn cứ.

Không có claim xác nhận độc lập của đồng đội/M3. Không coi B PASS là hoàn tất mọi
task M2 tuần 7–8 hoặc ba cases cùng một final prompt version.
