# Sửa lỗi cleanup workspace trên Windows — 15/10/2026

## 1. Phạm vi và chẩn đoán

Chỉ sửa quản lý workspace tạm trong `M2_week_7_8`. Không sửa VGAR, prompt,
model, budgets, parser/verifier, tests/source của ba fixture, campaign hoặc
evidence cũ; không cài dependencies, không chạy LLM, không commit/push.

Hai lỗi khác nhau đã xuất hiện khi người dùng tự nghiệm thu:

| Lỗi | Evidence / ý nghĩa |
|---|---|
| WinError 5 khi pytest truy cập `C:\Users\pc\AppData\Local\Temp\pytest-of-pc` | Run `20261015T042920768688Z-31255477b47b`: 14 PASS, 9 setup ERROR. Chuyển TEMP/TMP sang thư mục mới có quyền ghi trong Terminal giải quyết lượt lỗi setup này; không sửa ACL hoặc chạy Administrator. |
| WinError 32 khi xóa thư mục `seed` của workspace riêng | Full suite `20261015T043124130465Z-5d29fa02946a`: 174 PASS/1 FAIL; chạy riêng `20261015T043442648176Z-c9ff6f0e7d37` vẫn FAIL. Collection/baseline assertions hoàn tất, lỗi ở `WorkspaceLease.__exit__` → `_remove_owned` → `rmdir`. |

Nguyên nhân trực tiếp của WinError32 là Windows còn một handle không cho xóa.
Chưa xác định được **process giữ handle trong hai lượt của người dùng**; không
quy kết cho Git, VS Code hay antivirus. Lọc command line không thay thế truy
tìm handle. Test mới tái hiện đúng WinError32 bằng handle Windows thật, nhưng
owner do test tạo không phải bằng chứng owner của lỗi cũ.

Code cũ đổi thuộc tính ghi rồi thử xóa ngay cả với sharing violation. Chmod
không giải phóng handle. Bản sửa xử lý khóa ngắn hạn có giới hạn; không hứa
chữa được khóa kéo dài hoặc xác định mọi chương trình bên ngoài.

## 2. Đã thay đổi gì?

| File | Thay đổi |
|---|---|
| `src/vgar_m2_w78/workspace.py` | `_remove_owned` chỉ backoff với WinError32/33; tối đa 6 lần, đợi lần lượt 50/100/200/400/800ms; tổng thời gian đợi chủ động tối đa 1.550ms. Giữ xử lý read-only, lỗi khác không được retry theo chính sách sharing lock. Kiểm tra lại quyền sở hữu trước mỗi lần xóa. |
| `src/vgar_m2_w78/workspace.py` | Ghi report cleanup trước các lần xóa, khi retry và lúc kết thúc. Khi hết giới hạn vẫn raise exception, thêm đường dẫn report vào traceback; không coi workspace còn khóa là thành công. |
| `src/vgar_m2_w78/pipeline.py` | Chép diagnostics vào `run_record.json → stages.cleanup` trước khi publish terminal record/bundle. Cleanup thất bại vẫn `ERROR / FINALIZATION_ERROR`; hash bundle khớp canonical sau cập nhật. |
| `tests/test_workspace_cleanup.py` | Regression tests cho sharing lock32/33, khóa kéo dài, lỗi I/O khác, ownership guard, handle Windows thật và canonical/bundle liên kết cleanup. Không thay tests fixture để làm repair PASS. |

**Giới hạn thời gian trên là thời gian sleep được lên lịch**, không phải cam kết
wall-clock của mọi thao tác filesystem. Không kill process ngoài, không tắt
antivirus, không sửa quyền toàn máy, không xóa thư mục tạm lịch sử của người dùng.

## 3. Log nằm ở đâu và đọc thế nào?

Với mỗi workspace được cleanup:

```text
<temp_root>/.cleanup-records/<m2-w78-private-name>.json
```

Chạy CLI bình thường thì `temp_root` là `M2_week_7_8/.workspaces`. Report nằm
ngoài thư mục private bị xóa nên không bị cleanup đó xóa theo. Khi tự chạy tests,
temp_root nằm trong pytest tmp_path; pytest có thể tự dọn các thư mục test cũ.
Evidence repair canonical có bản chép `stages.cleanup` độc lập với report tạm.

Các field chính:

- `status`: PASS hoặc ERROR sau khi cleanup thực sự kết thúc; `complete=true`
  chỉ có nghĩa thao tác đã kết thúc, không tự có nghĩa xóa thành công.
- `private_path`, `diagnostics_path`: đúng target do M2 tạo và nơi lưu report.
- `cleanup_process_id`: PID **thực hiện cleanup**, không phải PID giữ khóa.
- `lock_owner=not_identified`: chưa có bằng chứng xác định chương trình giữ khóa.
- `started_utc`, `ended_utc`, `duration_ms`: thời gian UTC và thời lượng monotonic.
- `attempts[]`: số lần, trạng thái, thời điểm; khi lỗi có `winerror`, `errno`,
  `operation`, `failed_path`, exception type/message, full chained `traceback`
  và thời gian đợi trước lần tiếp theo (`retry_wait_ms`, nếu có).

Nếu cần xác định owner trong lúc khóa còn tồn tại, mở **Resource Monitor → CPU
→ Associated Handles**, tìm tên private workspace trong `failed_path`.
Chưa tìm thấy handle không chứng minh chưa từng có khóa (process có thể đã nhả).
Không dừng process chưa xác định hoặc xóa folder để che kết quả lỗi.

## 4. Tự chạy lại trên PowerShell trong VS Code

Không cài lại packages. Chạy cùng Terminal; mỗi Terminal mới cần khai báo lại:

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'

# Mỗi phiên dùng thư mục tạm mới, không xóa hoặc dùng lại folder đang bị khóa.
$checkId = [guid]::NewGuid().ToString('N')
$env:TEMP = Join-Path (Get-Location).Path ('results\runtime_tmp\' + $checkId)
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -ErrorAction Stop | Out-Null
$testRoot = Join-Path (Get-Location).Path ('results\manual_acceptance\cleanup-' + $checkId + '\tests')

# Kiểm thử bản sửa và test gốc từng bị lỗi; không chạy LLM.
& $python .\scripts\record_tests.py tests/test_workspace_cleanup.py tests/test_test_runner.py --timeout-seconds 120 --output-root $testRoot
$focusedExit = $LASTEXITCODE
Write-Host "Focused exit code: $focusedExit"
if ($focusedExit -ne 0) { throw 'Dừng: đọc evidence mới, không chạy lặp hoặc chạy LLM.' }

# Chỉ chạy full suite khi nhóm kiểm tra trên PASS.
& $python .\scripts\record_tests.py tests --timeout-seconds 240 --output-root $testRoot
$suiteExit = $LASTEXITCODE
Write-Host "Full suite exit code: $suiteExit"
if ($suiteExit -ne 0) { throw 'Full suite chưa đạt; không chuyển sang inference.' }

& $python -m ruff check --select E9,F src scripts tests
$ruffExit = $LASTEXITCODE
Write-Host "Ruff exit code: $ruffExit"
```

Đọc evidence mới nhất **trong phiên vừa chạy**, không nhập folder thủ công:

```powershell
$latest = Get-ChildItem -LiteralPath $testRoot -Filter run_record.json -Recurse -File |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $latest) { throw 'Không tìm thấy evidence.' }
$result = Get-Content -Raw -Encoding UTF8 -LiteralPath $latest.FullName | ConvertFrom-Json
$latest.FullName
$result | Select-Object status,complete,started_utc,ended_utc,duration_ms
$result.stages.pytest.stdout
$result.stages.pytest.stderr
```

Với một repair run mới đã được duyệt, chọn canonical qua manifest hoặc output
CLI, không lấy fake/self-test làm real repair. Sau khi có `$recordPath`:

```powershell
$record = Get-Content -Raw -Encoding UTF8 -LiteralPath $recordPath | ConvertFrom-Json
$record.stages.cleanup | ConvertTo-Json -Depth 20
$record.finalization_errors | ConvertTo-Json -Depth 20
```

Code đã thay runtime fingerprint. Không reset frozen hashes/campaign để chạy
tiếp B hoặc biến lịch sử thành PASS. Offline cleanup PASS không thay đổi trạng
thái B BLOCKED / C historical V9 PASS / final3 chưa nghiệm thu.

## 5. Evidence của lần sửa này

Thư mục chung: `results/cleanup-fix/20261015-workspace-lock/`.

- `baseline/`: 9 file có sẵn được sao lưu trước sửa; M2 không có Git.
- `red/20261015T060831473742Z-d4954aaab60b/`: code cũ, 5 FAIL/1 PASS.
  Lượt đầu test native dùng access0 chưa tạo sharing lock đúng; đã sửa test
  sang FILE_LIST_DIRECTORY trước khi triển khai production, không giấu lượt này.
- `red-native/20261015T060854269913Z-87bf5bac30d9/`: code cũ, handle thật
  không share-delete, FAIL đúng WinError32.
- `green/20261015T060942461137Z-a98cc0467b0f/`: 10 PASS, gồm test gốc.
- `red-linkage/20261015T061059731977Z-c36a4c4c3cf4/`: 2 FAIL đúng thiếu
  canonical `stages.cleanup`, trước khi thêm liên kết pipeline.
- `green-linkage/20261015T061132193393Z-b316e5077d10/`: 14 PASS trong40.78s,
  bao gồm khóa kéo dài phải ERROR và bundle/canonical binding.
- `full/20261015T061228986192Z-ccfc40626b7e/`: **183 PASS trong104.62s**,
  recorder105.281s, exit0. Không còn test lỗi trong lượt full suite này.
- `audit_cleanup_fix.py`: kiểm tra read-only baseline9files, VGAR reference,
  archive lịch sử, quota campaign, fullsuite/JUnit và Ruff; output ở `audit/`.
  Lượt `audit/20261015T061553537404Z-dd9eb5b9b5bb/` PASS: đúng 5 file có sẵn
  thay đổi trong9copies (2 module production +3 tài liệu), 86 file archive/
  76 file lịch sử nguyên vẹn, campaign vẫn5attempts, không inference mới.

Tests khóa kéo dài được kỳ vọng **bắt exception và PASS test**, không phải
production cleanup được phép trả PASS. Ví dụ parser, raw model và failures cũ
không bị chỉnh sửa; không có repair inference mới trong công việc này.
