# Chạy và đọc evidence của phiên sửa lỗi B

Phạm vi: **development repair `multi_file_invoice`**, không phải benchmark,
không phải nghiệm thu cả A/B/C. Chỉ dùng fixture tin cậy đã khóa hashes.
Phiên này tối đa **8 reservation / 14.400 giây real-run**, dừng ở PASS đã audit đầu tiên.
Không xóa, đổi tên hoặc tạo campaign khác để lấy lại quota.

**Trạng thái 15/10/2026:** phiên đã terminal **PASS ở lượt 2, V11/r002**.
Hiện chỉ cần mục 1–2 và 6–7 để đọc evidence. **Không chạy lại mục 4–5**;
chúng được giữ để giải thích workflow, không phải yêu cầu inference thêm.
Báo cáo: `docs/KET_QUA_B_EVIDENCE_DRIVEN_2026_10_15.md`.

## 1. Mở PowerShell trong VS Code — mỗi terminal mới

Không cần cài lại dependencies, tải model hoặc chạy qualifier `OK`.

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path (Get-Location) 'results\b-repair-preflight\20261015-evidence-driven\temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$campaign = Join-Path (Get-Location) 'results\b_repair\2026-10-15-evidence-driven-b'
```

`$python` phải được khai báo lại ở terminal mới; dấu `(.venv)` không tự tạo biến này.
Model worker sử dụng interpreter HF hiện hữu được pin trong `config/demo.json`;
đường dẫn interpreter thuộc `vgar_mcp_mvp` chỉ là môi trường dependencies,
không chạy source hệ thống cũ. Model có thể offload CPU, không bảo đảm nằm toàn GPU.

## 2. Xem trạng thái trước — chỉ đọc, không chạy model

```powershell
& $python '.\scripts\run_b_experiment.py' --status --campaign $campaign
& $python '.\scripts\run_b_experiment.py' --history --campaign $campaign
```

Nếu PASS/complete: **không chạy thêm**. Nếu pending/LIVE: không mở lượt thứ hai,
không kill PID chưa xác định. Read-only status không tự tạo campaign hay reset.

## 3. Offline qualification — chỉ khi runtime thay đổi/chưa được qualify

```powershell
$qualificationRoot = '.\results\b-repair-preflight\20261015-evidence-driven\manual-full'
& $python '.\scripts\record_tests.py' tests --timeout-seconds 240 --output-root $qualificationRoot
$suiteExit = $LASTEXITCODE
if ($suiteExit -ne 0) { throw "Offline suite FAIL: exit $suiteExit; đọc run_record.json trước khi chạy model." }
& $python -m ruff check --select E9,F src scripts tests
if ($LASTEXITCODE -ne 0) { throw 'Ruff FAIL; không inference.' }
$testFile = Get-ChildItem -LiteralPath $qualificationRoot -Directory |
    ForEach-Object { Join-Path $_.FullName 'run_record.json' } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Sort-Object { (Get-Item -LiteralPath $_).LastWriteTimeUtc } -Descending |
    Select-Object -First 1
if (-not $testFile) { throw 'Không tìm thấy qualification record.' }
```

Record chứa `runtime_before` và `runtime_after`. Sửa code sau suite khiến proof cũ
không còn đủ điều kiện đăng ký runtime mới. Không sửa tests cũ để làm PASS.

## 4. Khởi tạo/đăng ký — Codex đã làm thì không làm lại

Đây là lệnh giải thích workflow, **không phải các bước bắt buộc mỗi lần chạy**.
`--init` chỉ dùng đúng một lần khi campaign chưa có. Initial runtime/prompt chỉ
đăng ký một lần. Mỗi revision sau phải có reason và record kích hoạt lỗi.

```powershell
# CHỈ LẦN ĐẦU, KHI CHƯA CÓ campaign.json:
& $python '.\scripts\run_b_experiment.py' --init --campaign $campaign
if ($LASTEXITCODE -ne 0) { throw 'Khởi tạo thất bại; không tiếp tục.' }
# $testFile phải là full-suite PASS tại đúng code hiện tại (mục 3).
& $python '.\scripts\run_b_experiment.py' --register-runtime --campaign $campaign --tests-record $testFile --reason 'Initial qualified B runtime'
if ($LASTEXITCODE -ne 0) { throw 'Runtime chưa được qualify/register.' }
& $python '.\scripts\run_b_experiment.py' --register-prompt m2-w78-v10 --campaign $campaign --reason 'Approved neutral full-snippet replacement; explicit production permissions and original-file coordinates'
if ($LASTEXITCODE -ne 0) { throw 'Prompt chưa được register.' }
```

Template revision phải UTF-8 **LF**. Archive giữ raw bytes; CRLF template bị chặn
trước reservation để tránh lệch hash so với renderer cũ. Source/context CRLF vẫn
được kiểm thử riêng, không bị đổi bytes. Không sửa lại template đã dùng.

## 5. Chạy đúng một lượt B — chỉ khi phiên chưa terminal

```powershell
& $python '.\scripts\run_b_experiment.py' --run-next --campaign $campaign
$runExit = $LASTEXITCODE
Write-Host "B attempt exit: $runExit"
& $python '.\scripts\run_b_experiment.py' --status --campaign $campaign
```

Exit `0`: attempt PASS sau audit; dừng. `1`: candidate FAIL. `2`: ERROR hoặc
chặn readiness/resume. Không mặc định ERROR là lỗi prompt; đọc diagnosis/raw.
Mỗi reservation tiêu thụ quota kể cả ERROR/interruption. Một run chỉ có một generation.

Runner không tự gọi model để viết prompt. Codex đọc evidence, sửa có căn cứ,
test offline, đăng ký revision tiếp theo V11/V12… rồi mới chạy lượt khác.
Runtime fix cần full-suite proof mới và worker/host process mới.
Không recount, sửa `@@`, fuzzy apply, sửa tests/gold, đổi model/caps để đạt PASS.

## 6. Tự chọn canonical mới nhất từ manifest, không dán tên thư mục

```powershell
$state = Get-Content -Raw -Encoding UTF8 (Join-Path $campaign 'campaign.json') | ConvertFrom-Json
$state.attempts | Select-Object number,version,runtime_revision,status,complete,elapsed_seconds,record
$attempt = @($state.attempts | Where-Object { $_.record }) | Select-Object -Last 1
if (-not $attempt) { throw 'Chưa có terminal canonical record; không suy luận PASS.' }
$recordPath = $attempt.record
$runDirectory = Split-Path -Parent $recordPath
$record = Get-Content -Raw -Encoding UTF8 $recordPath | ConvertFrom-Json
$record | Select-Object run_id,task_id,status,reason,complete,started_utc,ended_utc,duration_ms,original_source_unchanged
$attempt.diagnosis | ConvertTo-Json -Depth 10
$attempt.gate_errors
$record.stages | ConvertTo-Json -Depth 35
```

`duration_ms` là canonical pipeline time; `elapsed_seconds` của reservation tính
cả setup và finalization, dùng cho budget phiên. Tổng budget thực tế có thể vượt
deadline một ít do safe finalization/cleanup: phải báo thực tế, không cắt cleanup
hoặc sửa thời gian. Offline engineering/test time không nhập thành inference time.

## 7. Xem prompt/raw/diff và baseline → post

```powershell
Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory 'prompt.txt')
if ($record.artifacts.raw_output) { Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $record.artifacts.raw_output) }
if ($record.artifacts.candidate) { Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $record.artifacts.candidate) }
if ($record.artifacts.applied) { Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $record.artifacts.applied) }
$record.error_detail | ConvertTo-Json -Depth 25
$record.stages.parse_patch | ConvertTo-Json -Depth 25
$record.stages.baseline | ConvertTo-Json -Depth 25
$record.stages.verification | ConvertTo-Json -Depth 25
$record.stages.generation | ConvertTo-Json -Depth 25
$record.stages.cleanup | ConvertTo-Json -Depth 25
if ($record.artifacts.bundle) { Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $record.artifacts.bundle) }
Get-Content -Encoding UTF8 (Join-Path $campaign 'REPORT.md')
```

Không chỉ đọc PASS ngoài cùng. B cần hai required tests baseline FAIL → post PASS,
regression/collection thực thi, cả hai production files thực sự đổi, raw tự parse,
exact bind/apply, static PASS, signatures giữ nguyên, cleanup PASS, bundle đúng hash
và source/tests/config gốc không đổi. `generation_diagnostics` phải là quan sát thật
effective config, mask và placement; không điền hồi tố từ defaults.

## 8. Sau interruption — chỉ recovery, không khởi chạy trùng

```powershell
& $python '.\scripts\run_b_experiment.py' --recover --campaign $campaign
& $python '.\scripts\run_b_experiment.py' --status --campaign $campaign
```

LIVE/không xác định ownership: không launch. Owner đã xác nhận chết: nhận terminal
canonical có sẵn hoặc chốt ERROR, giữ slot/thời gian. Hash mismatch: dừng, không
âm thầm chấp nhận input mới. Không có lệnh reset quota.

## 9. Vị trí implementation/evidence

| Thành phần | File/thư mục | Vai trò |
|---|---|---|
| Controller | `src/vgar_m2_w78/b_experiment.py` | Ownership, revision archives, quota, receipts, resume và audit |
| Trusted inputs | `src/vgar_m2_w78/b_inputs.py` | Freeze B/model/tokenizer/history/fixtures/guards |
| Audit bổ sung | `src/vgar_m2_w78/b_acceptance.py` | Raw/prompt/runtime binding, diagnostics, signatures |
| CLI | `scripts/run_b_experiment.py` | Một command/một attempt; không autonomous prompt model |
| Prompt V10 | `prompts/repair_v10.txt` | Ví dụ format trung tính, replacement và permissions |
| Context presentation | `src/vgar_m2_w78/context_presentation.py` | Số dòng source thật, permission metadata; không sửa M1 payload |
| Tokenization | `generator_hf.py`, `hf_backend.py` trong `src/vgar_m2_w78` | Truyền cờ/cache True–False; generation giữ True |
| Pipeline | `src/vgar_m2_w78/pipeline.py` | Private workspace/baseline/gen/parse/apply/verify/cleanup; hook/deadline bổ sung |
| Qualification | `results/b-repair-preflight/20261015-evidence-driven` | Baseline119files, RED/GREEN/full suite có stdout/stderr/timing |
| Phiên B | `results/b_repair/2026-10-15-evidence-driven-b` | Manifest, immutable prompt/runtime revisions, attempts/canonical/bundle |
| Checkpoint | `PROGRESS.md` | Điểm dừng/bước tiếp; không xóa failures cũ |

Plan: `docs/superpowers/plans/2026-10-15-complete-b-with-evidence-driven-repair.md`.
Kết quả inference thực tế được ghi riêng khi run hoàn tất, không suy ra từ test offline.
