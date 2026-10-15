# M2 tuần 7–8 — Diagnostics parser, traceback và inference

Ngày triển khai: 15/10/2026. Chỉ bổ sung log trong `M2_week_7_8`.
Không chạy lại B, không đổi prompt/model/greedy/FP16/device-map/budgets, không sửa
VGAR hoặc source/tests của ba fixture. Campaign V5+ vẫn B BLOCKED, C V9 PASS,
final3 chưa nghiệm thu. Logging mới không tự làm B PASS.

## 1. Parser: đọc lỗi ngay tại vị trí nào?

Trong run mới, xem `run_record.json`:

```text
error_detail.type / message / stage / traceback
error_detail.parser_diagnostics
stages.parse_patch.parser_diagnostics
stages.parse_patch.traceback
```

| Field diagnostics | Ý nghĩa |
|---|---|
| raw_line | Dòng raw output làm parser báo lỗi, bắt đầu từ1; len+1 là EOF |
| raw_line_text | Nội dung nguyên dòng, còn indentation; null khi EOF |
| raw_line_count | Tổng số dòng raw; có tính markdown fence nếu model xuất fence |
| path | Path đang parse; có thể là path bị cấm, không có nghĩa được phép apply |
| hunk_index | Hunk thứ mấy trong file, bắt đầu1; null nếu chưa đọc được hunk |
| hunk_raw_line / hunk_header | Dòng header @@ và nguyên văn header |
| expected_counts | old/new counts được header khai báo |
| actual_counts | Counts từ các dòng có prefix hợp lệ trong body được quan sát |
| counts_complete | Có thể coi phép đếm toàn body là đầy đủ/không mơ hồ hay không; không phải patch hợp lệ |
| invalid_body_lines | Những dòng body không có prefix hợp lệ, với raw line/text |
| ambiguous_body_boundary | Boundary có thể là header file tiếp theo trong hunk chưa đủ counts; không đoán hộ model |

`counts_complete=false` nghĩa không dùng actual_counts làm khẳng định model chỉ
thiếu/thừa đúng X dòng: có thể thiếu context marker hoặc ranh giới mơ hồ.
Không thêm dấu cách, sửa @@, fuzzy apply hay tái tạo diff. Parser giữ nguyên
acceptance rules, exception class và message; chỉ thêm thuộc tính diagnostics.

## 2. Traceback: đã ghi ở những ranh giới nào?

`diagnostics.exception_details` lưu type/message và full chained traceback,
không capture locals hoặc toàn bộ environment. Ví dụ `raise RuntimeError from
ValueError` giữ cả hai exception và các frame liên quan.

| Nơi xảy ra lỗi | Nơi xem |
|---|---|
| Pipeline stage | `stages.<stage>.traceback`, top-level `error_detail.traceback` khi exception đi tới pipeline |
| Apply bắt exception rồi trả DTO FAIL/ERROR | `stages.apply.exception.traceback` |
| Syntax/type artifact/test report/mapping | `syntax.exception`, `tests/collection.exception` hoặc baseline `exception` trong stage tương ứng |
| Integrity/cleanup/bundle/finalization | `integrity_exception`, `finalization_errors[].traceback` |
| Không launch được command | Command record `traceback`, `error_type`, stdout/stderr |
| Python exception trong model worker | Worker `response.json`: traceback; host giữ cả error response kể cả worker exit2 |
| Worker response không parse được | `worker.exception.traceback` và command stdout/stderr |
| CLI/config/setup/qualification/record-tests/adaptive runner | Error run JSON hoặc JSON stderr có traceback |

Subprocess báo lỗi bằng exit code thì xem stdout/stderr; host không bịa traceback
Python nếu lỗi không phải exception Python của host. StopRun là control flow,
không phải exception fault mới. SIGKILL, OOM kill, mất điện hoặc ổ đĩa không ghi
được không thể bảo đảm có full Python traceback; timeout/partial metadata vẫn
được đánh dấu đúng, không chuyển thành PASS. Stdout/stderr vẫn có output cap.
Traceback/message có thể chứa paths/source; không publish toàn bộ log tùy tiện.

## 3. Effective generation configuration và attention mask

Mỗi generation mới có file worker:

```text
<run-root>/model-workers/<worker-id>/generation_diagnostics.json
```

Nếu script qualification dùng `workers` thay `model-workers`, tìm file theo
`diagnostics_artifact.path` trong worker result. Tokenize-only không gọi decoding.

Trong canonical của run PASS:
`stages.generation.generation_diagnostics`; khi worker FAIL:
`stages.generation.worker.generation_diagnostics` nếu sidecar đã được ghi.
`diagnostics_artifact` có path và SHA256; request/response/command JSON vẫn giữ.

| Field | Nội dung |
|---|---|
| checkpoint_generation_config | Toàn bộ GenerationConfig của model trước override |
| supplied_generation_config | Config mà backend đưa vào generate |
| generate_overrides | Các kwargs tường minh, ví dụ do_sample=false/max_new_tokens |
| effective_generation_config | Toàn bộ config đã được HF chuẩn bị tại pre-decode, không chỉ defaults |
| effective_observed | true chỉ khi observer thực sự thấy config tại boundary |
| attention_mask_supplied_by_host | Host có truyền mask tường minh trong kwargs hay không |
| attention_mask | Shape/dtype/device/elements/zeros/ones/binary/SHA256 của mask thực tế tại boundary |
| input_ids | Shape/dtype/device và SHA256; không dump toàn bộ token IDs |
| phase/status/exception | before_generate → pre_decode → complete hoặc error; lỗi giữ traceback |

Observer dùng **instance `_get_logits_processor`** trong Transformers4.57.6:
HF gọi điểm này sau khi chuẩn bị mask, max_length và cache, trước decoding.
Không hook instance `_sample`: runtime này dispatch decoder qua `type(self)`
nên hook đó sẽ bị bỏ qua. Test đã mô phỏng đúng class dispatch.

Observer chuyển nguyên args/return value của framework, khôi phục method trên
success/error; không monkeypatch class/global, không truyền mask mới và không
tắt warning để che vấn đề. File sidecar được ghi trước generate và trước decode,
không đợi model hoàn tất. Nếu fail trước boundary thì effective_observed=false,
config/mask thực tế có thể null; không suy diễn chúng từ defaults.

Mask là summary/hash, không phải toàn bộ ma trận số. Field effective config được
serialize đầy đủ, tensor config values có giá trị/dtype/device; kiểu không chuẩn
được ghi type/repr thay vì âm thầm bỏ field. Capture dùng API nội bộ của phiên bản
HF đã pin: nâng Transformers cần test lại; không claim hỗ trợ mọi decoder/version.

## 4. Chạy kiểm thử log — không chạy LLM

Không cài lại dependencies. Dùng venv M2 hiện có:

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# OFFLINE: kiểm parser/traceback/observer, không load weights và không generation thật.
& $python .\scripts\record_tests.py tests/test_diagnostic_logging.py tests/test_generation_diagnostics.py --timeout-seconds 120
$LASTEXITCODE
# FULL PACKAGE: cũng không gọi real LLM.
& $python .\scripts\record_tests.py tests --timeout-seconds 240
$LASTEXITCODE
```

Hai file tests dùng parser/command/pipeline thực; phần GPU/model dùng doubles rõ
ràng để kiểm truyền dữ liệu, observer và lưu log. PASS offline không phải nghiệm
thu diagnostics trên GPU thật hoặc chứng minh B có thể repair thành công.

## 5. Tự mở log mới nhất, không gõ run ID

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
# CHỈ ĐỌC: tìm canonical mới nhất dưới results/repair khi bạn được duyệt chạy phiên mới.
$latest = Get-ChildItem -LiteralPath '.\results\repair' -Filter run_record.json -Recurse -File |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $latest) { throw 'Chưa có repair run. Không lấy self-test thay real repair.' }
$record = Get-Content -Raw -Encoding UTF8 -LiteralPath $latest.FullName | ConvertFrom-Json
$latest.FullName
$record | Select-Object run_id,mode,status,reason,started_utc,ended_utc,duration_ms
$record.error_detail | ConvertTo-Json -Depth 12
$record.stages.parse_patch | ConvertTo-Json -Depth 12
$diag = $record.stages.generation.generation_diagnostics
if (-not $diag) { $diag = $record.stages.generation.worker.generation_diagnostics }
if ($diag) { $diag | ConvertTo-Json -Depth 30 }
else { Write-Warning 'Run cũ/chưa tới generate: không có diagnostics mới. Không tự điền log hồi tố.' }
$record.stages.generation.worker.command.stderr
```

Nếu kết quả thuộc campaign, dùng `campaign.json -> attempts[].record` thay vì
latest toàn cây results. Đường dẫn theo manifest phân biệt được task/version và
fake/real. Các runs B cũ không tự có field mới; offline replay ghi ở output riêng.

## 6. Đọc lịch sử sau khi code logging đã thay đổi

Frozen campaign V5+ gắn hash runtime cũ. `--status` với runtime mới **phải từ chối**
hash mismatch; đó không phải B vừa chạy FAIL thêm. Không sửa frozen_inputs/counters
hoặc xóa campaign để làm command PASS. Dùng archive đã lưu trước sửa:

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$snapshot = Get-ChildItem -LiteralPath '.\results\diagnostics-preflight' -Filter archive_manifest.json -Recurse -File |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $snapshot) { throw 'Không có archive baseline diagnostics; không bypass hash guard.' }
& $python .\scripts\run_adaptive_acceptance.py --history --archive-manifest $snapshot.FullName
$LASTEXITCODE
# CHỈ ĐỌC status lịch sử, không dùng code mới để giả là runtime cũ.
$campaignPath = '.\results\adaptive_acceptance\2026-10-15-v5-plus\campaign.json'
$saved = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json
$saved | Select-Object campaign_id,status,complete,reason,final_version
$saved.attempts | Select-Object number,phase,task_id,version,status,complete,record
```

Archive V5+ bảo toàn86 source/tests files và76 historical files. Archive V3/V4
cũ vẫn riêng, không dùng mapping runtime mới đè runtime cũ. Không có real B5,
không có prompt V10 hoặc campaign mới trong task logging này. Cần approval riêng
trước lần inference tiếp theo và phải dùng runtime fingerprint/phiên mới rõ ràng.

## 7. Kết quả kiểm chứng và ví dụ đọc bốn lỗi B

Full suite **175 passed in92.28s**, recorder92.922s, exit0:
`results/tests/20261015T014057460231Z-bae22e94edc3/run_record.json`.
Đã chạy Ruff E9/F PASS, một fresh review và RED→GREEN cho các finding;
chi tiết `REVIEW_DIAGNOSTIC_LOGGING_2026_10_15.md`.

Offline replay bốn raw B cũ và audit19 trường hợp parser cũ/mới:
`results/diagnostics/20261015T014155215724Z-fb7147b392bf/run_record.json`.
Đây là evidence mới cho **việc chẩn đoán**, không phải B được repair thành công.

| Run cũ | Raw line trigger | File / expected / actual | Ý nghĩa |
|---|---|---|---|
| B1 V5 | 12 | invoice.py; expected2/2, actual3/3 | Sai counts; full body có prefix hợp lệ |
| B2 V6 | 16 | invoice.py; expected6/6, scanned3/3 | Header file tiếp theo ở line14 trong hunk chưa đủ; counts_complete=false, không giả là count chắc chắn |
| B3 V7 | 4 | pricing.py; expected2/2, valid-prefix1/1 | Dòng def không có context-prefix; invalid_body_lines chứa line4; counts_complete=false |
| B4 V8 | 1 | host_path_policy.json; chưa có hunk/counts | Path ngoài allowlist; parser dừng ngay header |

Traceback trong record replay là stack của code mới khi đọc lại raw cũ; không
phải stack đã thất lạc của lần model chạy trước. Không sửa raw/canonical/bundle
cũ. Cả19 cases giữ nguyên acceptance/exception class/message và parsed bodies
so với parser archive trước logging; kiểm source/evidence cũ được bảo toàn.

Final audit `results/checks/20261015T014449437742Z-0b8fbfdea946/run_record.json`:
RuffPASS, scope17 runtime files, source/evidence archives, no new repair,
5 Markdown files/9 PowerShell blocks/13 tables PASS. Ba finding của review đã
được sửa; không còn finding cần sửa trong task này. Hai minor cũ của campaign
(static-feedback selection/deep JUnit reconciliation) không đổi hoặc bị che bằng log.
