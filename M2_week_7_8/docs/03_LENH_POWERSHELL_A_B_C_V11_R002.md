# 03 — Toàn bộ lệnh PowerShell chạy A/B/C bằng V11/r002

Ngày 15/10/2026. Đọc file01 để bàn giao, file02 để hiểu repo. Mục tiêu là kiểm
thử: source/guards/tests/config/VGAR giữ nguyên, chỉ tạo logs/evidence/worktree
riêng. Ba fixtures đã PASS dưới V11/r002 nhưng lượt chạy mới có thể FAIL; script
không sửa prompt/diff/tests để ép PASS, không cài packages hoặc tải model.

## 1. Kiểm thử, không cài đặt hoặc cấu hình lại hệ thống

Tất cả lệnh thực thi trong tài liệu này phục vụ kiểm tra/chạy thử/đọc kết quả.
**Không có lệnh pip install, tạo venv, update hoặc sửa config** trong workflow.
Nếu prerequisites chưa có, dừng để provision riêng theo `requirement.txt`; không
cài lại khi readiness đã PASS. Python core và HF worker là hai môi trường khác
nhau. Việc kiểm thử vẫn cần tạo evidence/temp/private worktree dưới M2; đó không
phải áp dụng patch vào source gốc hay thay hệ thống đang dùng.

**Lệnh 1 — chọn project.** Input là thư mục M2 hiện có; output mong muốn: terminal
đứng tại đúng project. Chỉ thay working directory, không sửa file.

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
```

**Các prerequisites không tự cung cấp:** Git for Windows, PowerShell>=5.1,
NVIDIA driver, sibling VGAR đúng source pin, M1 tokenizer manifest/assets và local
Qwen snapshot. HF interpreter hiện lấy từ `config/demo.json`; xem file01/requirement
để provision venv riêng khi thiếu. Không tự đổi HF0.22.2 thành core0.22.1 hoặc dùng
CPU fallback để coi như profile đã nghiệm thu. Saved records có paths máy gốc;
không sửa chúng để che environment drift.

## 2. Chạy từ đầu đến cuối bằng MỘT lệnh

**Lệnh 2 — kiểm thử thật A→B→C.** Input script ở root và fixtures/bundles/V11/r002
hiện có; output mới tự sinh tại `results/manual_abc/<UTC-GUID>`. Chạy core readiness,
full self-tests, Ruff, ba real generations tuần tự, audit và in toàn bộ log.
Đây là compute mới, không chỉ pytest. Không ghi đè final evidence/campaign cũ.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\test_abc_v11_r002.ps1'
```

Bypass chỉ áp dụng child process này, không đổi execution policy hệ thống. Script
không cần Activate.ps1/`$python` của terminal trước; tự chọn core interpreter.
Mỗi case một generation, dừng ở lỗi đầu tiên, không tự chạy lại hoặc đổi V11.
Output directory tồn tại bị từ chối. Nếu Ctrl+C hoặc interruption, đọc
summary/canonical/process trước; không dùng lại outputroot để launch trùng.

**Lệnh 3 — readiness không model.** Output mới có `preflight.json`, profile,
command logs, summary modeCheck/PASS; không có case A/B/C và không chứng minh repairPASS.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\test_abc_v11_r002.ps1' -Mode Check
```

**Lệnh 4 — chỉ xem và audit evidence chuẩn cũ.** Không load model/generate, không
independent reproduction. Output mới có `all_logs.txt`, auditA/B/C và summary
`mode=ReadSaved`; old final records vẫn giữ nguyên.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\test_abc_v11_r002.ps1' -Mode ReadSaved
```

**Lệnh 5 — tùy chọn bỏ self-tests khi runtime đã được kiểm.** Vẫn readiness,
realA/B/C và audit đầy đủ; output phải ghi đã dùng SkipSelfTests. Không bỏ qua core
tests nếu chưa có qualification của cùng code. Không giảm verification tests của fixtures.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\test_abc_v11_r002.ps1' -SkipSelfTests
```

**Lệnh 6 — đặt outputroot mới có chủ đích.** Input là đường dẫn CHƯA tồn tại dưới
results project này; output tại đó. Nếu path ngoài results hoặc reparsepoint,
script dừng trước khi tạo thư mục. Không ghi lên `examples`, source hoặc old results.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\test_abc_v11_r002.ps1' -OutputRoot '.\results\manual_abc\my-new-independent-run'
```

## 3. Log nào được hiển thị và lưu lại?

- `all_logs.txt`: toàn bộ text script in ra, không chỉ bảng tóm tắt.
- `*.command.json`: executable/argv, exit, UTC start/end/duration; `*.console.log`
  giữ child output. Python warnings trên stderr không bị hiểu nhầm thành exitFAIL.
- Canonical đầy đủ: mọi stage, stdout/stderr/exit/JUnit/outcomes/config hashes/
  selection/fallback, timing, traceback/parser location/counts khi có.
- Prompt, raw, candidate/applied diff, EvidenceBundle nguyên bản.
- Tất cả worker JSON trong từng case: request/response, command (stdout/stderr),
  observed effective config/mask/device placement/peak CUDA/versions.
- `summary.json`: status/mode/complete/cases + canonical/audit refs. Bản
  `.previous` là revision gần trước của summary đang cập nhật, không verdict cuối.
- Trong Run mode: `self_tests` chứa recorder/JUnit; ba case ở `A|B|C/<run>`.
  Workspace temporary/cleanup reports do core ghi dưới `.workspaces`.
- `profile.json`: lấy model paths hiện tại từ config nhưng chọn V11 rõ ràng;
  `verification_job.py` là audit helper được materialize riêng vào results.
- Không có token streaming từ model: chờ generation hoàn tất mới có raw output.
  Canonical/worker sidecars cập nhật trong quá trình chạy; runner không hứa live từng token.

Exit0 là script hoàn tất theo mode; **Check/ReadSaved exit0 không phải fresh
real3PASS**. Run chỉ PASS khi ba real records qua core và audit bổ sung.
Exit2: lỗi readiness/command/audit được vùng try/catch quản lý; case còn lại chưa chạy.
Các setup guards trước try (ví dụ Python thiếu, output đã tồn tại, PYTHONOPTIMIZE)
có thể exit1 mà chưa có summary. Mọi exit khác0 đều chưa hoàn tất. Có thể thấy
baseline tests FAIL (đúng mong muốn) trước khi post PASS. Final source gốc vẫn lỗi
vì agent sửa private worktree; đọc applied.diff.

## 4. Đọc lại kết quả mới không phải nhập run ID

**Lệnh 7 — tự chọn folder manual runner mới nhất có summary.** Input root outputs;
output biến `$run`. Có thể là Check/ReadSaved, phải xem mode ở lệnh tiếp theo,
không coi “latest” mặc định là real run.

```powershell
$run = Get-ChildItem -LiteralPath '.\results\manual_abc' -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'summary.json') } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1 -ExpandProperty FullName
```

**Lệnh 8 — dừng nếu không có output.** Input biến `$run`; không sửa dữ liệu.

```powershell
if (-not $run) { throw 'Chưa có manual runner output; hãy chạy Mode Check/ReadSaved/Run trước.' }
```

**Lệnh 9 — đọc summary UTF-8.** Output là status/mode/case audit, không generation mới.

```powershell
Get-Content -Raw -Encoding UTF8 (Join-Path $run 'summary.json')
```

**Lệnh 10 — in TOÀN BỘ log đã lưu.** Có thể rất dài; output là text không cắt nested fields.

```powershell
Get-Content -Raw -Encoding UTF8 (Join-Path $run 'all_logs.txt')
```

**Lệnh 11 — mở log trong VS Code.** Không dùng khi CLI `code` chưa có; đây là
tùy chọn đọc, không cần cho script và không tác động repair.

```powershell
code (Join-Path $run 'all_logs.txt')
```

## 5. Giải thích TỪNG DÒNG của script

Mỗi dòng vật lý có nội dung được giải thích ngay phía trên, gồm cả tham số,
control flow và Python helper. **Không dán/chạy từng mảnh của function hoặc
here-string**: dùng nguyên script tại mục2. Các dòng Python bên trong here-string
được gắn nhãn Python để không nhầm với lệnh PowerShell. Mục6 chứa bản liền mạch
khớp file thực tế. Mỗi log/JSON mới thuộc OutputRoot; canonical cũ chỉ được đọc.

### Dòng 1

Khai báo script nâng cao để PowerShell bind tham số chuẩn; không đọc/ghi dữ liệu.

```powershell
[CmdletBinding()]
```

### Dòng 2

Mở danh sách tham số chạy; các giá trị quyết định mode, Python và nơi lưu evidence, chưa thực thi repair.

```powershell
param(
```

### Dòng 3

Chỉ nhận Run (mặc định: ba inference mới), Check (readiness) hoặc ReadSaved (audit hồ sơ cũ); giá trị khác bị từ chối trước chạy.

```powershell
    [ValidateSet('Run','Check','ReadSaved')][string]$Mode = 'Run',
```

### Dòng 4

Tham số interpreter core; rỗng sẽ chọn .venv/Scripts/python.exe trong M2, không dùng biến $python của phiên terminal khác.

```powershell
    [string]$Python = '',
```

### Dòng 5

Tham số output mới dưới results của M2; rỗng tự sinh UTC–GUID, không nhập tay run ID.

```powershell
    [string]$OutputRoot = '',
```

### Dòng 6

Tham số root chứa evidence A/B/C để đọc lại trong ReadSaved; không phải nơi ghi patch.

```powershell
    [string]$SavedRoot = '',
```

### Dòng 7

Switch tùy chọn bỏ self-tests của engine khi đã qualified cùng code; không bỏ baseline/post/static của A/B/C. Giá trị được ghi summary.

```powershell
    [switch]$SkipSelfTests
```

### Dòng 8

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
)
```

### Dòng 9

Bật strict mode để biến thiếu/thuộc tính không tồn tại gây lỗi rõ ràng, tránh âm thầm dùng giá trị null.

```powershell
Set-StrictMode -Version Latest
```

### Dòng 10

Cho lỗi PowerShell kết thúc flow và đi vào catch khi đã vào vùng được quản lý; child exit được kiểm riêng.

```powershell
$ErrorActionPreference = 'Stop'
```

### Dòng 11

Từ chối PYTHONOPTIMIZE khác rỗng/0 trước tạo output: -O có thể vô hiệu hóa assert trong audit. Mong đợi không có biến optimization.

```powershell
if ($env:PYTHONOPTIMIZE -and $env:PYTHONOPTIMIZE -ne '0') { throw 'Unset PYTHONOPTIMIZE: acceptance checks must not be disabled.' }
```

### Dòng 12

Lấy đường dẫn project từ vị trí chính file PS1, không phụ thuộc working directory caller.

```powershell
$root = [IO.Path]::GetFullPath($PSScriptRoot)
```

### Dòng 13

Chọn core Python của M2 khi người dùng không truyền -Python; chỉ xây đường dẫn, không cài môi trường.

```powershell
if (-not $Python) { $Python = Join-Path $root '.venv\Scripts\python.exe' }
```

### Dòng 14

Kiểm interpreter core tồn tại; nếu thiếu thì dừng, không tự install/fallback.

```powershell
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Core Python missing; install prerequisites first.' }
```

### Dòng 15

Sinh root mới results/manual_abc/<UTC-GUID>; mỗi lần chạy có evidence riêng, không ghi đè kết quả trước.

```powershell
if (-not $OutputRoot) { $OutputRoot = Join-Path $root ('results\manual_abc\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)) }
```

### Dòng 16

Chuẩn hóa output thành đường dẫn tuyệt đối để kiểm ranh giới chính xác.

```powershell
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
```

### Dòng 17

Tạo boundary tuyệt đối có dấu phân cách của results project, tránh nhầm thư mục có tiền tố tương tự.

```powershell
$resultsBoundary = [IO.Path]::GetFullPath((Join-Path $root 'results')) + [IO.Path]::DirectorySeparatorChar
```

### Dòng 18

Reject output ngoài results của M2 trước mutation; source/examples/VGAR không được dùng làm output.

```powershell
if (-not $OutputRoot.StartsWith($resultsBoundary,[StringComparison]::OrdinalIgnoreCase)) { throw 'OutputRoot must be a new directory below this project results.' }
```

### Dòng 19

Reject root đã tồn tại thay vì ghi đè/resume nhầm evidence. Muốn chạy lại dùng root mới, không xóa root cũ.

```powershell
if (Test-Path -LiteralPath $OutputRoot) { throw 'OutputRoot already exists; evidence is never overwritten. Use a NEW path.' }
```

### Dòng 20

Bắt đầu hoặc lùi một cấp để kiểm các thư mục cha của output; không di chuyển/xóa thư mục.

```powershell
$ancestor = [IO.Path]::GetDirectoryName($OutputRoot)
```

### Dòng 21

Duyệt tổ tiên thuộc project để kiểm reparse points trước khi tạo output.

```powershell
while ($ancestor -and $ancestor.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) {
```

### Dòng 22

Chặn junction/symlink tổ tiên nhằm không ghi theo đường dẫn chuyển hướng ra ngoài project.

```powershell
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse-point output ancestors are not allowed.' }
```

### Dòng 23

Bắt đầu hoặc lùi một cấp để kiểm các thư mục cha của output; không di chuyển/xóa thư mục.

```powershell
    $ancestor = [IO.Path]::GetDirectoryName($ancestor)
```

### Dòng 24

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
}
```

### Dòng 25

Mặc định ReadSaved dùng results/final_acceptance/2026-10-15-v11-r002; hồ sơ lịch sử chỉ đọc.

```powershell
if (-not $SavedRoot) { $SavedRoot = Join-Path $root 'results\final_acceptance\2026-10-15-v11-r002' }
```

### Dòng 26

Tạo bộ mã UTF-8 không BOM cho log/helper/JSON do runner sinh.

```powershell
$utf8 = New-Object Text.UTF8Encoding($false)
```

### Dòng 27

Đặt encoding console để tiếng Việt/worker output không bị sai mã; chỉ áp dụng phiên child PowerShell.

```powershell
[Console]::OutputEncoding = $utf8
```

### Dòng 28

Đặt encoding khi truyền output sang native commands trong phiên script.

```powershell
$OutputEncoding = $utf8
```

### Dòng 29

Tạo duy nhất outputroot đã qua boundary/existence checks; chưa tạo A/B/C hoặc chạy model.

```powershell
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
```

### Dòng 30

Chọn <OutputRoot>/all_logs.txt làm transcript đầy đủ cho mọi lệnh và artifacts được in.

```powershell
$logPath = Join-Path $OutputRoot 'all_logs.txt'
```

### Dòng 31

Định nghĩa hàm ghi đồng thời text ra console và all_logs.txt; đây là định nghĩa, không launch task.

```powershell
function Write-Log([string]$Text) {
```

### Dòng 32

Append một đoạn UTF-8 vào all_logs.txt, giữ cả nội dung dài thay vì Format-Table cắt bớt.

```powershell
    [IO.File]::AppendAllText($logPath,$Text + [Environment]::NewLine,$utf8)
```

### Dòng 33

Hiển thị cùng text trên terminal; terminal có thể cuộn/cắt hiển thị nhưng bản file vẫn đầy đủ.

```powershell
    Write-Output $Text
```

### Dòng 34

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
}
```

### Dòng 35

Định nghĩa bộ ghi JSON nguyên tử trong outputroot; dùng cho summary và command receipts.

```powershell
function Write-Json([string]$Path,$Value) {
```

### Dòng 36

Sinh filename tạm cùng thư mục với JSON đích để chuẩn bị atomic move/replace, không ghi file source.

```powershell
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
```

### Dòng 37

Serialize giá trị JSON sâu tối đa100 vào file tạm UTF-8; đầu vào là object summary/command metadata.

```powershell
    [IO.File]::WriteAllText($temporary,($Value | ConvertTo-Json -Depth 100),$utf8)
```

### Dòng 38

Atomically replace JSON đã có, giữ bản gần trước .previous; JSON mới thì Move file tạm. Chỉ thao tác output của lần chạy.

```powershell
    if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary,$Path,($Path + '.previous')) } else { [IO.File]::Move($temporary,$Path) }
```

### Dòng 39

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
}
```

### Dòng 40

Định nghĩa wrapper gọi child executable với argv, lưu stdout/stderr, exit và thời gian; không tự retry.

```powershell
function Invoke-Logged([string]$Name,[string]$Executable,[string[]]$Arguments) {
```

### Dòng 41

Lấy UTC bắt đầu child command để ghi receipt; không dùng đồng hồ này thay stopwatch đo elapsed.

```powershell
    $start = [DateTime]::UtcNow
```

### Dòng 42

Khởi động monotonic stopwatch đo duration của command, đơn vị ms.

```powershell
    $timer = [Diagnostics.Stopwatch]::StartNew()
```

### Dòng 43

In tên bước và command dễ đọc; argv có cấu trúc chính xác được lưu thêm trong .command.json.

```powershell
    Write-Log ("COMMAND {0}: {1} {2}" -f $Name,$Executable,($Arguments -join ' '))
```

### Dòng 44

Giữ error preference hiện hành trước khi xử lý stderr native trên Windows PowerShell.

```powershell
    $previousPreference = $ErrorActionPreference
```

### Dòng 45

Mở vùng bảo vệ để finally/catch ghi diagnostics và khôi phục state đúng; bản thân không launch command.

```powershell
    try {
```

### Dòng 46

Tạm nhận stderr dưới dạng output để warning không tự biến thành terminating PowerShell error; exit code vẫn quyết định PASS/FAIL.

```powershell
        $ErrorActionPreference = 'Continue'
```

### Dòng 47

Chạy đúng executable+argv, thu đầy đủ stdout và stderr; không chạy bằng chuỗi shell ghép lại, không stream từng token model.

```powershell
        $lines = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
```

### Dòng 48

Chụp $LASTEXITCODE ngay sau child, trước khi lệnh khác có thể thay đổi.

```powershell
        $nativeExit = $LASTEXITCODE
```

### Dòng 49

Khôi phục error preference dù child phát sinh lỗi; không thay preference của phần script còn lại.

```powershell
    } finally { $ErrorActionPreference = $previousPreference }
```

### Dòng 50

Dừng đo elapsed của child command sau khi command kết thúc.

```powershell
    $timer.Stop()
```

### Dòng 51

Ghép toàn bộ output đã thu thành text nhiều dòng, không chỉ giữ dòng cuối.

```powershell
    $text = $lines -join [Environment]::NewLine
```

### Dòng 52

Ghi <step>.console.log trong outputroot; chứa toàn bộ stdout/stderr của child step.

```powershell
    [IO.File]::WriteAllText((Join-Path $OutputRoot ($Name + '.console.log')),$text,$utf8)
```

### Dòng 53

Ghi <step>.command.json với argv, exit_code, started_utc, ended_utc và duration_ms.

```powershell
    Write-Json (Join-Path $OutputRoot ($Name + '.command.json')) ([ordered]@{argv=@($Executable)+$Arguments;exit_code=$nativeExit;started_utc=$start.ToString('o');ended_utc=[DateTime]::UtcNow.ToString('o');duration_ms=$timer.ElapsedMilliseconds})
```

### Dòng 54

In và lưu nguyên text child vào all_logs.txt; lỗi pytest chứa trong canonical sẽ được dump riêng ở finally.

```powershell
    Write-Log $text
```

### Dòng 55

In exit/duration của bước vừa kết thúc để đối chiếu receipt.

```powershell
    Write-Log ("END {0}; exit={1}; duration_ms={2}" -f $Name,$nativeExit,$timer.ElapsedMilliseconds)
```

### Dòng 56

Dừng flow khi child exit khác0; các cases phía sau không được launch, không sửa patch để che lỗi.

```powershell
    if ($nativeExit -ne 0) { throw "Command failed: $Name (exit $nativeExit); inspect its console log and canonical evidence." }
```

### Dòng 57

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
}
```

### Dòng 58

Bắt đầu here-string chứa Python helper. Các dòng Python bên dưới là dữ liệu cho helper, không phải lệnh gõ riêng trong PowerShell.

```powershell
$helper = @'
```

### Dòng 59

Helper nhập AST/JSON/sys/version metadata/subprocess: phân tích signatures, đọc evidence và probe HF mà không load weights.

```python
import ast,json,sys,importlib.metadata as md,subprocess
```

### Dòng 60

Nhập Path và PureWindowsPath để chuẩn hóa đường dẫn hiện tại và rebase root lịch sử Windows.

```python
from pathlib import Path,PureWindowsPath
```

### Dòng 61

Chặn cả helper được gọi bằng Python -O; các assert audit phải luôn có hiệu lực, không cho báo PASS giả.

```python
if sys.flags.optimize:raise RuntimeError('Optimized Python is not allowed for acceptance checks')
```

### Dòng 62

Lấy root từ argv[2], thêm root/src cho import M2; không sửa PYTHONPATH hay code của VGAR.

```python
root=Path(sys.argv[2]).resolve();sys.path.insert(0,str(root/'src'))
```

### Dòng 63

Import verifier của source pin VGAR; lát nữa sẽ kiểm HEAD,12boundary files và import origin.

```python
from vgar_m2_w78.bootstrap import verify_reference
```

### Dòng 64

Import hàm fingerprint qualified core src/scripts/config, không sửa/reset controller B.

```python
from vgar_m2_w78.b_experiment import runtime_fingerprint
```

### Dòng 65

Import gate assess_record để audit canonical thực tế; không lấy nhãn PASS ngoài cùng làm đủ điều kiện.

```python
from vgar_m2_w78.campaign import assess_record
```

### Dòng 66

Import strict config loader cho model/policy hiện có.

```python
from vgar_m2_w78.config import load_config
```

### Dòng 67

Import RepairTask DTO để validate tasks và đường dẫn của fixtures.

```python
from vgar_m2_w78.contracts import RepairTask
```

### Dòng 68

Import atomic JSON và SHA256 digest để ghi output/bind artifacts.

```python
from vgar_m2_w78.evidence import atomic_json,digest
```

### Dòng 69

Import trusted-fixture byte guard; không gọi generation tại đây.

```python
from vgar_m2_w78.pipeline import require_trusted_fixture
```

### Dòng 70

Import parser/exact binder hiện tại để tái dựng expected source và kiểm signatures; không sửa parser/patch.

```python
from vgar_m2_w78.patch import PatchPolicy,parse_unified_diff,_bind
```

### Dòng 71

Lấy outputroot từ argv[3] và action từ argv[1]; chỉ cho phép preflight hoặc audit.

```python
output=Path(sys.argv[3]).resolve();action=sys.argv[1]
```

### Dòng 72

Kiểm sibling VGAR đúng approved HEAD/12hashes/import origin; output reference metadata, không reset các dirty paths khác.

```python
reference=verify_reference()
```

### Dòng 73

Chọn campaign B lịch sử chứa frozen r002 provenance; chỉ đọc, không mở lại quota.

```python
prior=root/'results/b_repair/2026-10-15-evidence-driven-b'
```

### Dòng 74

Đọc frozen_inputs.json: policy và runtime_root gốc để đối chiếu; không cập nhật frozen hashes.

```python
old=json.loads((prior/'frozen_inputs.json').read_text(encoding='utf-8'))
```

### Dòng 75

Đọc immutable revisions/r002.json: danh sách file và SHA của runtime đã qualified.

```python
registered=json.loads((prior/'revisions/r002.json').read_text(encoding='utf-8'))
```

### Dòng 76

Biểu diễn root Windows lịch sử để bỏ prefix khi so map relative paths.

```python
oldroot=PureWindowsPath(old['runtime_root'])
```

### Dòng 77

Chuyển map registered hashes thành relative paths; tránh coi đường dẫn tuyệt đối máy gốc là nội dung runtime.

```python
expected={PureWindowsPath(p).relative_to(oldroot).as_posix():h for p,h in registered['files'].items()}
```

### Dòng 78

Hash core hiện tại rồi chuẩn hóa relative paths cùng cách với r002; root PS1/docs không nằm trong map core.

```python
current={Path(p).relative_to(root).as_posix():h for p,h in runtime_fingerprint(root).items()}
```

### Dòng 79

Gate: core hiện tại phải khớp r002 byte-for-byte; khác thì dừng, không âm thầm gọi runtime mới là r002.

```python
assert expected==current,'Qualified core r002 changed; do not silently accept a new runtime'
```

### Dòng 80

Gate V11 template đúng SHA đã nghiệm thu; không sửa/rewrite template.

```python
assert digest((root/'prompts/repair_v11.txt').read_bytes())=='sha256:ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8','V11 changed'
```

### Dòng 81

Load config/demo.json và tạo bản policy trong bộ nhớ chọn V11; file defaultV2 giữ nguyên.

```python
policy,profile=load_config(root/'config/demo.json');policy=policy.model_copy(update={'prompt_version':'m2-w78-v11'})
```

### Dòng 82

Gate policy chỉ khác frozen policy ở prompt_version=V11; token/time/path/security caps không được nới.

```python
assert policy.model_dump()==dict(old['policy'],prompt_version='m2-w78-v11'),'Policy changed'
```

### Dòng 83

Khởi tạo map task A/B/C sau validate; không lấy task ngoài ba fixtures.

```python
tasks={}
```

### Dòng 84

Gắn A=single_file_login, B=multi_file_invoice, C=missing_links theo thứ tự cố định.

```python
for letter,case in zip('ABC',('single_file_login','multi_file_invoice','missing_links')):
```

### Dòng 85

Đọc examples/tasks/<case>.json chứa issue/selectors/source/bundle/permissions, không dùng gold patch.

```python
    path=root/'examples/tasks'/f'{case}.json';data=json.loads(path.read_text(encoding='utf-8'))
```

### Dòng 86

Resolve source_repo và bundle_directory theo thư mục task JSON, không theo cwd terminal.

```python
    for key in ('source_repo','bundle_directory'):data[key]=(path.parent/data[key]).resolve()
```

### Dòng 87

Validate RepairTask, kiểm hashes trusted fixture rồi đưa vào tasks map; source/tests/config gốc phải đúng bytes.

```python
    task=RepairTask.model_validate(data);require_trusted_fixture(task);tasks[letter]=task
```

### Dòng 88

Nhánh readiness: kiểm dependencies/model/policy; kết quả PASS ở đây chưa chứng minh repair thành công.

```python
if action=='preflight':
```

### Dòng 89

Đọc version thực tế của7core packages từ interpreter đang chạy, không suy đoán theo requirement.txt.

```python
    core={name:md.version(name) for name in ('pydantic','python-dotenv','tokenizers','jinja2','pytest','mypy','ruff')}
```

### Dòng 90

So đúng7pins trong requirement.txt; mismatch raises RuntimeError và chưa ghi preflight PASS.

```python
    if core!={'pydantic':'2.13.5','python-dotenv':'1.2.3','tokenizers':'0.22.1','jinja2':'3.1.6','pytest':'8.4.2','mypy':'1.20.2','ruff':'0.16.7'}:raise RuntimeError('Core version pins differ from the qualified environment: '+str(core))
```

### Dòng 91

Profile qualified yêu cầu Python3.11; không tự fallback sang3.12/3.13.

```python
    assert sys.version_info[:2]==(3,11),'Qualified profile uses Python 3.11'
```

### Dòng 92

Chuẩn bị readiness result: version/reference/r002/profile/policy; chỉ ghi khi các gates đã qua.

```python
    result={'status':'PASS','scope':'preflight, NOT repair acceptance','core_versions':core,'reference':reference,'runtime_revision':'r002','profile':profile.model_dump(mode='json'),'policy':policy.model_dump()}
```

### Dòng 93

Check/Run cần kiểm HF interpreter và CUDA; ReadSaved chỉ audit hồ sơ nên không probe model environment.

```python
    if sys.argv[4]!='ReadSaved':
```

### Dòng 94

Kiểm snapshot folder đúng revision và tồn tại, cùng HF interpreter; không tải weights/network.

```python
        assert profile.snapshot.name==profile.revision and profile.snapshot.is_dir() and profile.interpreter.is_file()
```

### Dòng 95

Soạn probe metadata/Torch CUDA trong interpreter HF; chỉ import, không AutoModel.from_pretrained/generate.

```python
        code="import json,torch,importlib.metadata as m;print(json.dumps({'cuda':torch.cuda.is_available(),'versions':{n:m.version(n) for n in ('torch','transformers','tokenizers','accelerate','safetensors')},'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"
```

### Dòng 96

Chạy HF probe với stdout/stderr được capture và timeout60s; dùng interpreter trong profile.

```python
        probe=subprocess.run([str(profile.interpreter),'-c',code],capture_output=True,text=True,timeout=60)
```

### Dòng 97

HF probe exit phải0; lỗi import/CUDA được lộ stderr, không chuyển sang fake hoặc CPU.

```python
        assert probe.returncode==0,probe.stderr
```

### Dòng 98

Đọc probe và yêu cầu CUDA available; thông tin gpu là thiết bị quan sát, không khẳng định mọi layer nằm trên GPU.

```python
        gpu=json.loads(probe.stdout);assert gpu['cuda'],'No CUDA; no CPU fallback allowed'
```

### Dòng 99

Kiểm HF stack đúng Torch2.11.0+cu128/Transformers4.57.6/tokenizers0.22.2/accelerate1.15.0/safetensors0.8.0.

```python
        assert gpu['versions']=={'torch':'2.11.0+cu128','transformers':'4.57.6','tokenizers':'0.22.2','accelerate':'1.15.0','safetensors':'0.8.0'},'HF environment differs from qualified profile'
```

### Dòng 100

Lưu probe CUDA/device/versions vào readiness result để đối chiếu hai venv.

```python
        result['hf']=gpu
```

### Dòng 101

Ghi profile V11 riêng trong outputroot; các run thật dùng file này, không ghi config/demo.json.

```python
    atomic_json(output/'profile.json',{'policy':policy.model_dump(),'model':profile.model_dump(mode='json')})
```

### Dòng 102

Ghi preflight.json, in readiness đầy đủ rồi kết thúc helper exit0; không generation.

```python
    atomic_json(output/'preflight.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0)
```

### Dòng 103

Reject helper action lạ; ngoài preflight chỉ chấp nhận audit.

```python
assert action=='audit'
```

### Dòng 104

Chọn root chứa A/B/C và task của letter; trong Run là output mới, trong ReadSaved là SavedRoot.

```python
case_root=Path(sys.argv[4]).resolve();letter=sys.argv[5];task=tasks[letter]
```

### Dòng 105

Tìm chính xác một */run_record.json dưới case letter; thiếu hoặc nhiều canonical đều dừng thay vì chọn nhầm latest.

```python
paths=list((case_root/letter).glob('*/run_record.json'));assert len(paths)==1,'Exactly one canonical per case is required'
```

### Dòng 106

Đọc canonical duy nhất và chạy assess_record; giữ gate_errors để không nhầm outer status với acceptance.

```python
path=paths[0];record=json.loads(path.read_text(encoding='utf-8'));assessment=assess_record(path)
```

### Dòng 107

In đường dẫn và toàn bộ canonical gồm stage/command/stdout/stderr/duration/traceback; không Format-Table.

```python
print('CANONICAL '+str(path));print(path.read_text(encoding='utf-8'))
```

### Dòng 108

Duyệt prompt/raw/candidate/applied/EvidenceBundle từ canonical refs; các labels chỉ để trình bày log.

```python
for label,key in (('PROMPT','prompt.txt'),('RAW OUTPUT',record.get('artifacts',{}).get('raw_output')),('CANDIDATE',record.get('artifacts',{}).get('candidate')),('APPLIED',record.get('artifacts',{}).get('applied')),('EVIDENCE BUNDLE',record.get('artifacts',{}).get('bundle'))):
```

### Dòng 109

Chỉ đọc artifact có reference; stage chưa tới có thể chưa có candidate/applied, không bịa artifact.

```python
    if key:
```

### Dòng 110

Resolve artifact phải ở cùng run directory và không symlink; reject path escape trước khi đọc.

```python
        artifact=(path.parent/key).resolve();assert artifact.parent==path.parent.resolve() and not artifact.is_symlink()
```

### Dòng 111

In label+đường dẫn artifact giúp biết input/output cụ thể khi xem log.

```python
        print(label+' '+str(artifact))
```

### Dòng 112

In toàn bộ artifact UTF-8; một file thiếu không được làm mất log của artifacts/worker còn lại.

```python
        try:print(artifact.read_text(encoding='utf-8'))
```

### Dòng 113

Ghi lỗi đọc artifact nguyên nhân thật; không coi thiếu artifact là PASS, acceptance gates phía sau vẫn reject.

```python
        except OSError as exc:print('ARTIFACT READ ERROR '+repr(exc))
```

### Dòng 114

Duyệt mọi worker JSON trong case/model-workers: request, response, command và actual generation diagnostics.

```python
for worker in sorted((case_root/letter/'model-workers').rglob('*.json')):
```

### Dòng 115

Reject worker symlink và in đường dẫn; chỉ đọc evidence trong worker tree được chọn.

```python
    assert not worker.is_symlink();print('WORKER JSON '+str(worker))
```

### Dòng 116

In nguyên worker JSON để thấy effective config, attention mask, tokens, device placement, stdout/stderr và load/gen times.

```python
    try:print(worker.read_text(encoding='utf-8'))
```

### Dòng 117

Lưu lỗi đọc riêng worker rồi tiếp tục dump; không bù dữ liệu giả hoặc điền hồi tố diagnostics.

```python
    except OSError as exc:print('WORKER READ ERROR '+repr(exc))
```

### Dòng 118

Gate core acceptance phải PASS và gate_errors rỗng, không dựa exit hoặc nhãn status đơn độc.

```python
assert assessment['status']=='PASS' and not assessment['gate_errors'],assessment
```

### Dòng 119

So task/model canonical với approved inputs hiện tại; không gộp record khác model/source/case.

```python
assert record['task']==task.model_dump(mode='json') and record['model']==profile.model_dump(mode='json')
```

### Dòng 120

So full policy với V11 fixed caps và yêu cầu prompt_feedback=None cho final no-feedback run.

```python
assert record['policy']==policy.model_dump() and record.get('prompt_feedback') is None
```

### Dòng 121

Lấy prompt và generation stages của canonical; stage thiếu gây fail chứ không mặc định PASS.

```python
stages=record['stages'];prompt=stages['prompt'];generation=stages['generation']
```

### Dòng 122

Kiểm template hash V11 và metadata.feedback=None; mỗi full prompt khác issue/context nhưng cùng template.

```python
assert prompt['template_hash']==digest((root/'prompts/repair_v11.txt').read_bytes()) and prompt.get('metadata',{}).get('feedback') is None
```

### Dòng 123

Hash prompt.txt phải bằng prompt_hash đã ghi; missing/changed prompt làm acceptance fail sau khi đã dump logs.

```python
assert digest((path.parent/'prompt.txt').read_bytes())==prompt['prompt_hash']
```

### Dòng 124

Bind bytes input thật mà worker nhận với full prompt hash của host.

```python
assert generation['input_sha256']==prompt['prompt_hash'].removeprefix('sha256:')
```

### Dòng 125

Đọc raw_model_output bytes theo canonical; đây là output nguyên bản, không phải patched/recounted diff.

```python
raw=(path.parent/record['artifacts']['raw_output']).read_bytes()
```

### Dòng 126

Yêu cầu raw bytes bằng candidate bytes và raw_text generation; host không được strip wrapper/sửa hunk giúp model.

```python
assert raw==(path.parent/record['artifacts']['candidate']).read_bytes() and raw.decode('utf-8')==generation['raw_text']
```

### Dòng 127

Lấy actual generation diagnostics và attention mask quan sát trong canonical.

```python
diagnostic=generation['generation_diagnostics'];mask=diagnostic['attention_mask']
```

### Dòng 128

Diagnostics phải PASS và effective_observed=True, không chỉ copy supplied config.

```python
assert diagnostic['status']=='PASS' and diagnostic['effective_observed'] is True
```

### Dòng 129

Yêu cầu observed do_sample=False, max_new_tokens1536, giữ generation profile đã chốt.

```python
assert diagnostic['effective_generation_config']['do_sample'] is False and diagnostic['effective_generation_config']['max_new_tokens']==1536
```

### Dòng 130

Input count host=worker trong1..6000 và có actual device_map; không sửa budget để PASS.

```python
assert 0<generation['input_tokens']==prompt['input_tokens']<=6000 and generation['device_map']
```

### Dòng 131

Mask actual có shape[1,input_tokens], binary và không paddingzeros trong single-input profile này.

```python
assert mask['shape']==[1,generation['input_tokens']] and mask['binary'] is True and mask['zeros']==0
```

### Dòng 132

Mỗi SHA trong canonical source_fingerprint phải khớp registered r002 map; không gắn nhãn r002 hồi tố.

```python
assert all(record['source_fingerprint'][p]==h for p,h in expected.items())
```

### Dòng 133

Cleanup stage phải PASS; patch/test PASS nhưng private workspace không finalize đúng vẫn chưa đạt.

```python
assert stages['cleanup']['status']=='PASS'
```

### Dòng 134

Yêu cầu baseline có2required IDs cho B và1cho A/C, không bỏ một lỗi của B để dễ PASS.

```python
required=stages['baseline']['required_ids'];assert len(required)==(2 if letter=='B' else 1)
```

### Dòng 135

Kiểm mọi required baseline thực sự FAIL trước patch; baseline.status PASS chỉ nghĩa đủ điều kiện kiểm.

```python
assert all(stages['baseline']['tests']['outcomes'][n]=='FAIL' for n in required)
```

### Dòng 136

Parse raw bằng guards hiện hành, exact-bind với original approved source để tái dựng predicted bytes; không ghi source.

```python
parsed=parse_unified_diff(raw.decode('utf-8'),PatchPolicy(task.allowed_source_paths,task.protected_paths));predicted,_=_bind(parsed,task.source_repo)
```

### Dòng 137

Định nghĩa audit AST signatures của các top-level fixture functions; không tự nhận là API verifier đầy đủ.

```python
def signatures(data):
```

### Dòng 138

Trích function name/kind/args/returns AST; không xét body là signature, dùng đối chiếu trước/sau.

```python
    return {n.name:(type(n).__name__,ast.dump(n.args),ast.dump(n.returns) if n.returns else None) for n in ast.parse(data).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
```

### Dòng 139

Yêu cầu signatures original=predicted cho từng file bị patch; không thay public function contract của fixtures.

```python
assert all(signatures((task.source_repo/p).read_bytes())==signatures(data) for p,data in predicted.items())
```

### Dòng 140

Kiểm lại byte registry original source/tests/config sau audit; fixture gốc phải còn lỗi và không bị sửa.

```python
require_trusted_fixture(task)
```

### Dòng 141

Tạo audit result có task/letter/r002/V11/tokens/duration và canonical refs/gate errors.

```python
result=dict(assessment,task_id=task.task_id,letter=letter,runtime_revision='r002',prompt_version='m2-w78-v11',input_tokens=generation['input_tokens'],output_tokens=generation['output_tokens'],duration_ms=record['duration_ms'])
```

### Dòng 142

Ghi audit_A|B|C.json vào output mới và in AUDIT <letter> PASS chỉ sau toàn bộ gates.

```python
atomic_json(output/f'audit_{letter}.json',result);print('AUDIT '+letter+' PASS')
```

### Dòng 143

Kết thúc Python here-string; từ dòng sau trở lại PowerShell, không chạy riêng nội dung helper.

```powershell
'@
```

### Dòng 144

Đặt đường dẫn outputroot/verification_job.py cho bản helper của invocation này.

```powershell
$helperPath = Join-Path $OutputRoot 'verification_job.py'
```

### Dòng 145

Materialize helper UTF-8 vào output mới, không sửa src/scripts/runtime r002.

```powershell
[IO.File]::WriteAllText($helperPath,$helper,$utf8)
```

### Dòng 146

Khởi tạo summary NOT_RUN, mode, SkipSelfTests, UTC và cases rỗng; chưa có verdict repair.

```powershell
$summary = [ordered]@{status='NOT_RUN';complete=$false;mode=$Mode;skip_self_tests=[bool]$SkipSelfTests;started_utc=[DateTime]::UtcNow.ToString('o');ended_utc=$null;cases=@();output_root=$OutputRoot;reason=$null}
```

### Dòng 147

Chọn outputroot/summary.json làm index tự động cho invocation này.

```powershell
$summaryPath = Join-Path $OutputRoot 'summary.json'
```

### Dòng 148

Cập nhật summary nguyên tử: reservation/kết quả/status, để interruption không mất trạng thái đã ghi.

```powershell
Write-Json $summaryPath $summary
```

### Dòng 149

Lưu PYTHONUTF8/TEMP/TMP của child để finally khôi phục, không ghi môi trường Windows toàn máy.

```powershell
$priorEnvironment = @{PYTHONUTF8=$env:PYTHONUTF8;TEMP=$env:TEMP;TMP=$env:TMP}
```

### Dòng 150

Đổi cwd trong script sang rootM2; dùng stack để cuối cùng quay lại vị trí ban đầu.

```powershell
Push-Location $root
```

### Dòng 151

Mở vùng bảo vệ để finally/catch ghi diagnostics và khôi phục state đúng; bản thân không launch command.

```powershell
try {
```

### Dòng 152

Bật UTF-8 cho mọi child Python của invocation; không cần người dùng đặt trước trong terminal.

```powershell
    $env:PYTHONUTF8 = '1'
```

### Dòng 153

Dùng temp riêng dưới outputroot để giảm đụng shared TEMP/Windows lock; không xóa temp ngoài ownership.

```powershell
    $env:TEMP = Join-Path $OutputRoot 'temp'
```

### Dòng 154

Cho TMP cùng temp riêng, giữ Python/subprocess thống nhất.

```powershell
    $env:TMP = $env:TEMP
```

### Dòng 155

Tạo temp riêng cho lần kiểm; thư mục là output của test workflow, không hệ thống cũ.

```powershell
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
```

### Dòng 156

In mode và outputroot ngay đầu flow; nhắc không install/source edit/automatic retry.

```powershell
    Write-Log "MODE=$Mode OUTPUT=$OutputRoot; no install, no source edits, no automatic retries."
```

### Dòng 157

Chạy helper readiness, ghi preflight.console.log/.command.json/profile.json/preflight.json; không load weights.

```powershell
    Invoke-Logged 'preflight' $Python @($helperPath,'preflight',$root,$OutputRoot,$Mode)
```

### Dòng 158

Chỉ Run mặc định mới chạy self-tests; Check/ReadSaved không rerun tests, SkipSelfTests được ghi rõ.

```powershell
    if ($Mode -eq 'Run' -and -not $SkipSelfTests) {
```

### Dòng 159

Chạy recorder toàn tests với timeout240s vào outputroot/self_tests; nếu FAIL vẫn vào finally để in canonical stdout/stderr.

```powershell
        try { Invoke-Logged 'self_tests' $Python @('scripts\record_tests.py','tests','--timeout-seconds','240','--output-root',(Join-Path $OutputRoot 'self_tests')) }
```

### Dòng 160

Bảo đảm khối dump self-test canonical chạy cả khi self-tests FAIL, trước khi chuyển lỗi ra catch.

```powershell
        finally {
```

### Dòng 161

Chỉ dump self-test canonical nếu recorder đã tạo folder; không che lỗi gốc do folder chưa sinh.

```powershell
            if (Test-Path -LiteralPath (Join-Path $OutputRoot 'self_tests')) {
```

### Dòng 162

In toàn bộ self-test run_record.json, gồm pytest stdout/stderr thật dù recorder exit khác0.

```powershell
                Get-ChildItem -LiteralPath (Join-Path $OutputRoot 'self_tests') -Filter 'run_record.json' -Recurse -File | ForEach-Object { Write-Log ([IO.File]::ReadAllText($_.FullName,$utf8)) }
```

### Dòng 163

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
            }
```

### Dòng 164

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
        }
```

### Dòng 165

Ruff read-only E9,F trên src/scripts/tests, không --fix; exit0/All checks passed mới tiếp tục.

```powershell
        Invoke-Logged 'ruff' $Python @('-m','ruff','check','--select','E9,F','src','scripts','tests')
```

### Dòng 166

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
    }
```

### Dòng 167

Check kết thúc sau readiness; chỉ Run hoặc ReadSaved đi qua A/B/C.

```powershell
    if ($Mode -ne 'Check') {
```

### Dòng 168

Cố định danh sách ba fixtures, không nhận arbitrary repos hoặc SWE-bench tasks.

```powershell
        $caseNames = @('single_file_login','multi_file_invoice','missing_links')
```

### Dòng 169

Cố định nhãn A/B/C khớp ba task IDs ở dòng trước.

```powershell
        $letters = @('A','B','C')
```

### Dòng 170

Duyệt tuần tự3cases, không nạp hai model workers đồng thời.

```powershell
        for ($index=0; $index -lt 3; $index++) {
```

### Dòng 171

Chọn nhãn case hiện tại để đặt folder/audit/receipt.

```powershell
            $letter = $letters[$index]
```

### Dòng 172

Chọn task ID hiện tại từ danh sách khóa, không từ feedback hoặc số task ngẫu nhiên.

```powershell
            $case = $caseNames[$index]
```

### Dòng 173

Ghi reservation NOT_RUN/UTC trước launch để thấy case đã tới nếu script bị ngắt.

```powershell
            $summary.cases += [ordered]@{letter=$letter;task_id=$case;status='NOT_RUN';reserved_utc=[DateTime]::UtcNow.ToString('o')}
```

### Dòng 174

Cập nhật summary nguyên tử: reservation/kết quả/status, để interruption không mất trạng thái đã ghi.

```powershell
            Write-Json $summaryPath $summary
```

### Dòng 175

Ban đầu trỏ evidence nguồn sang SavedRoot; ReadSaved không sinh patch mới.

```powershell
            $caseRoot = $SavedRoot
```

### Dòng 176

Chỉ nhánh Run mới gọi CLI generation; ReadSaved không thể âm thầm chạy model.

```powershell
            if ($Mode -eq 'Run') {
```

### Dòng 177

Trong Run, audit sẽ đọc đúng output mới của invocation này, không lấy PASS cũ.

```powershell
                $caseRoot = $OutputRoot
```

### Dòng 178

Gọi run_demo.py --mode real với task/profileV11/outputcase; một generation trong private worktree, giữ caps/model/source.

```powershell
                Invoke-Logged ('run_'+$letter) $Python @('scripts\run_demo.py','--mode','real','--task',('examples\tasks\'+$case+'.json'),'--config',(Join-Path $OutputRoot 'profile.json'),'--output-root',(Join-Path $OutputRoot $letter))
```

### Dòng 179

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
            }
```

### Dòng 180

Sau run (hoặc khi ReadSaved), dump mọi log rồi chạy audit bổ sung; stdout lưu audit_<letter>.console.log/all_logs.

```powershell
            Invoke-Logged ('audit_'+$letter) $Python @($helperPath,'audit',$root,$OutputRoot,$caseRoot,$letter)
```

### Dòng 181

Đọc audit_<letter>.json UTF-8 vừa sinh; không nhập tay run ID.

```powershell
            $audit = Get-Content -Raw -Encoding UTF8 (Join-Path $OutputRoot ('audit_'+$letter+'.json')) | ConvertFrom-Json
```

### Dòng 182

PowerShell kiểm độc lập audit.status=PASS và gate_errors rỗng, fail-closed nếu helper result không đạt.

```powershell
            if ($audit.status -ne 'PASS' -or @($audit.gate_errors).Count -ne 0) { throw "Acceptance gate failed for $letter; inspect audit JSON." }
```

### Dòng 183

Thay reservation bằng audit thật cho case đã hoàn tất, gồm canonical ref/tokens/duration.

```powershell
            $summary.cases[$index] = $audit
```

### Dòng 184

Cập nhật summary nguyên tử: reservation/kết quả/status, để interruption không mất trạng thái đã ghi.

```powershell
            Write-Json $summaryPath $summary
```

### Dòng 185

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
        }
```

### Dòng 186

Chỉ in3/3sau ba audit PASS; text phân biệt ReadSaved với fresh Run để không nhận nhầm reproduction.

```powershell
        Write-Log '3/3 CASE AUDITS PASS. ReadSaved re-audits existing records; only Run performs NEW generations.'
```

### Dòng 187

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
    }
```

### Dòng 188

Đặt invocation PASS sau gates của mode: Check chỉ readiness, ReadSaved chỉ old evidence, Run là fresh repairs.

```powershell
    $summary.status = 'PASS'
```

### Dòng 189

Đánh dấu invocation đã terminal; complete=true không tự nghĩa repair PASS, phải xem status/mode.

```powershell
    $summary.complete = $true
```

### Dòng 190

Ghi UTC kết thúc invocation vào summary; command/canonical có timers riêng.

```powershell
    $summary.ended_utc = [DateTime]::UtcNow.ToString('o')
```

### Dòng 191

Cập nhật summary nguyên tử: reservation/kết quả/status, để interruption không mất trạng thái đã ghi.

```powershell
    Write-Json $summaryPath $summary
```

### Dòng 192

In mode và đường dẫn summary để người chạy biết output ở đâu.

```powershell
    Write-Log ("DONE mode={0}; summary={1}" -f $Mode,$summaryPath)
```

### Dòng 193

Thoát child PowerShell với exit0 sau successful mode; chỉ Run mới chứng minh ba generations mới PASS.

```powershell
    exit 0
```

### Dòng 194

Nhánh quản lý lỗi: lưu exception/stack, không retry hoặc thay V11 để sửa kết quả.

```powershell
} catch {
```

### Dòng 195

Giữ lỗi PowerShell và ScriptStackTrace trước khi chạy diagnostic helper phụ.

```powershell
    $caughtFailure = $_.ToString() + [Environment]::NewLine + $_.ScriptStackTrace
```

### Dòng 196

Chỉ Run mặc định mới chạy self-tests; Check/ReadSaved không rerun tests, SkipSelfTests được ghi rõ.

```powershell
    if ($Mode -eq 'Run' -and (Get-Variable -Name letter -ErrorAction SilentlyContinue)) {
```

### Dòng 197

Gọi audit helper để in raw/parser/worker của failed run. Helper vẫn reject FAIL, catch chỉ giữ log, không biến FAIL thành PASS.

```powershell
        try { Invoke-Logged ('failed_evidence_'+$letter) $Python @($helperPath,'audit',$root,$OutputRoot,$OutputRoot,$letter) } catch { Write-Log 'Failure evidence dump completed or failed; original failure is retained below.' }
```

### Dòng 198

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
    }
```

### Dòng 199

Ghi ERROR terminal cho invocation; xem canonical để phân biệt model candidate FAIL với runtime ERROR.

```powershell
    $summary.status = 'ERROR'
```

### Dòng 200

Đánh dấu invocation đã terminal; complete=true không tự nghĩa repair PASS, phải xem status/mode.

```powershell
    $summary.complete = $true
```

### Dòng 201

Lưu lỗi gốc vào summary.reason thay vì chỉ thông báo exit code.

```powershell
    $summary.reason = $caughtFailure
```

### Dòng 202

Ghi UTC kết thúc invocation vào summary; command/canonical có timers riêng.

```powershell
    $summary.ended_utc = [DateTime]::UtcNow.ToString('o')
```

### Dòng 203

Cập nhật summary nguyên tử: reservation/kết quả/status, để interruption không mất trạng thái đã ghi.

```powershell
    Write-Json $summaryPath $summary
```

### Dòng 204

In và lưu nguyên lỗi/stack gốc vào all_logs.txt.

```powershell
    Write-Log $summary.reason
```

### Dòng 205

Thông báo các cases phía sau chưa launch; không chỉnh candidate/tests hoặc giấu failure.

```powershell
    Write-Log 'STOP: remaining cases were NOT launched. Inspect canonical/worker evidence; never edit a patch to force PASS.'
```

### Dòng 206

Thoát exit2 với lỗi managed readiness/selftests/run/audit; setup guards trước try có thể exit1, luôn coi nonzero là chưa hoàn tất.

```powershell
    exit 2
```

### Dòng 207

Finally ngoài cùng chạy khi success/error: khôi phục cwd và env của child script, không xóa evidence.

```powershell
} finally {
```

### Dòng 208

Quay về cwd ban đầu của child PowerShell.

```powershell
    Pop-Location
```

### Dòng 209

Khôi phục PYTHONUTF8 trước đó trong child PowerShell; không thay môi trường Windows toàn máy, không xóa dữ liệu.

```powershell
    $env:PYTHONUTF8 = $priorEnvironment.PYTHONUTF8
```

### Dòng 210

Khôi phục TEMP trước đó trong child PowerShell; không thay môi trường Windows toàn máy, không xóa dữ liệu.

```powershell
    $env:TEMP = $priorEnvironment.TEMP
```

### Dòng 211

Khôi phục TMP trước đó trong child PowerShell; không thay môi trường Windows toàn máy, không xóa dữ liệu.

```powershell
    $env:TMP = $priorEnvironment.TMP
```

### Dòng 212

Đóng khối/tham số đang mở; đây là cú pháp cấu trúc, không phải lệnh chạy độc lập, không tạo input/output.

```powershell
}
```

## 6. Toàn bộ script liền mạch

Đây là bản đối chiếu của `test_abc_v11_r002.ps1` tại thời điểm bàn giao. Để chạy,
ưu tiên file PS1 trong root; không lưu đè script khi bạn đã có bản đúng. Không có
lệnh cài đặt trong workflow này; các thao tác ghi chỉ tạo output/worktree/private
temp cần thiết cho kiểm thử, không áp dụng patch vào repository gốc.

```powershell
[CmdletBinding()]
param(
    [ValidateSet('Run','Check','ReadSaved')][string]$Mode = 'Run',
    [string]$Python = '',
    [string]$OutputRoot = '',
    [string]$SavedRoot = '',
    [switch]$SkipSelfTests
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:PYTHONOPTIMIZE -and $env:PYTHONOPTIMIZE -ne '0') { throw 'Unset PYTHONOPTIMIZE: acceptance checks must not be disabled.' }
$root = [IO.Path]::GetFullPath($PSScriptRoot)
if (-not $Python) { $Python = Join-Path $root '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Core Python missing; install prerequisites first.' }
if (-not $OutputRoot) { $OutputRoot = Join-Path $root ('results\manual_abc\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)) }
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$resultsBoundary = [IO.Path]::GetFullPath((Join-Path $root 'results')) + [IO.Path]::DirectorySeparatorChar
if (-not $OutputRoot.StartsWith($resultsBoundary,[StringComparison]::OrdinalIgnoreCase)) { throw 'OutputRoot must be a new directory below this project results.' }
if (Test-Path -LiteralPath $OutputRoot) { throw 'OutputRoot already exists; evidence is never overwritten. Use a NEW path.' }
$ancestor = [IO.Path]::GetDirectoryName($OutputRoot)
while ($ancestor -and $ancestor.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) {
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse-point output ancestors are not allowed.' }
    $ancestor = [IO.Path]::GetDirectoryName($ancestor)
}
if (-not $SavedRoot) { $SavedRoot = Join-Path $root 'results\final_acceptance\2026-10-15-v11-r002' }
$utf8 = New-Object Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$logPath = Join-Path $OutputRoot 'all_logs.txt'
function Write-Log([string]$Text) {
    [IO.File]::AppendAllText($logPath,$Text + [Environment]::NewLine,$utf8)
    Write-Output $Text
}
function Write-Json([string]$Path,$Value) {
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary,($Value | ConvertTo-Json -Depth 100),$utf8)
    if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary,$Path,($Path + '.previous')) } else { [IO.File]::Move($temporary,$Path) }
}
function Invoke-Logged([string]$Name,[string]$Executable,[string[]]$Arguments) {
    $start = [DateTime]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    Write-Log ("COMMAND {0}: {1} {2}" -f $Name,$Executable,($Arguments -join ' '))
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $nativeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    $timer.Stop()
    $text = $lines -join [Environment]::NewLine
    [IO.File]::WriteAllText((Join-Path $OutputRoot ($Name + '.console.log')),$text,$utf8)
    Write-Json (Join-Path $OutputRoot ($Name + '.command.json')) ([ordered]@{argv=@($Executable)+$Arguments;exit_code=$nativeExit;started_utc=$start.ToString('o');ended_utc=[DateTime]::UtcNow.ToString('o');duration_ms=$timer.ElapsedMilliseconds})
    Write-Log $text
    Write-Log ("END {0}; exit={1}; duration_ms={2}" -f $Name,$nativeExit,$timer.ElapsedMilliseconds)
    if ($nativeExit -ne 0) { throw "Command failed: $Name (exit $nativeExit); inspect its console log and canonical evidence." }
}
$helper = @'
import ast,json,sys,importlib.metadata as md,subprocess
from pathlib import Path,PureWindowsPath
if sys.flags.optimize:raise RuntimeError('Optimized Python is not allowed for acceptance checks')
root=Path(sys.argv[2]).resolve();sys.path.insert(0,str(root/'src'))
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.b_experiment import runtime_fingerprint
from vgar_m2_w78.campaign import assess_record
from vgar_m2_w78.config import load_config
from vgar_m2_w78.contracts import RepairTask
from vgar_m2_w78.evidence import atomic_json,digest
from vgar_m2_w78.pipeline import require_trusted_fixture
from vgar_m2_w78.patch import PatchPolicy,parse_unified_diff,_bind
output=Path(sys.argv[3]).resolve();action=sys.argv[1]
reference=verify_reference()
prior=root/'results/b_repair/2026-10-15-evidence-driven-b'
old=json.loads((prior/'frozen_inputs.json').read_text(encoding='utf-8'))
registered=json.loads((prior/'revisions/r002.json').read_text(encoding='utf-8'))
oldroot=PureWindowsPath(old['runtime_root'])
expected={PureWindowsPath(p).relative_to(oldroot).as_posix():h for p,h in registered['files'].items()}
current={Path(p).relative_to(root).as_posix():h for p,h in runtime_fingerprint(root).items()}
assert expected==current,'Qualified core r002 changed; do not silently accept a new runtime'
assert digest((root/'prompts/repair_v11.txt').read_bytes())=='sha256:ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8','V11 changed'
policy,profile=load_config(root/'config/demo.json');policy=policy.model_copy(update={'prompt_version':'m2-w78-v11'})
assert policy.model_dump()==dict(old['policy'],prompt_version='m2-w78-v11'),'Policy changed'
tasks={}
for letter,case in zip('ABC',('single_file_login','multi_file_invoice','missing_links')):
    path=root/'examples/tasks'/f'{case}.json';data=json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_repo','bundle_directory'):data[key]=(path.parent/data[key]).resolve()
    task=RepairTask.model_validate(data);require_trusted_fixture(task);tasks[letter]=task
if action=='preflight':
    core={name:md.version(name) for name in ('pydantic','python-dotenv','tokenizers','jinja2','pytest','mypy','ruff')}
    if core!={'pydantic':'2.13.5','python-dotenv':'1.2.3','tokenizers':'0.22.1','jinja2':'3.1.6','pytest':'8.4.2','mypy':'1.20.2','ruff':'0.16.7'}:raise RuntimeError('Core version pins differ from the qualified environment: '+str(core))
    assert sys.version_info[:2]==(3,11),'Qualified profile uses Python 3.11'
    result={'status':'PASS','scope':'preflight, NOT repair acceptance','core_versions':core,'reference':reference,'runtime_revision':'r002','profile':profile.model_dump(mode='json'),'policy':policy.model_dump()}
    if sys.argv[4]!='ReadSaved':
        assert profile.snapshot.name==profile.revision and profile.snapshot.is_dir() and profile.interpreter.is_file()
        code="import json,torch,importlib.metadata as m;print(json.dumps({'cuda':torch.cuda.is_available(),'versions':{n:m.version(n) for n in ('torch','transformers','tokenizers','accelerate','safetensors')},'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"
        probe=subprocess.run([str(profile.interpreter),'-c',code],capture_output=True,text=True,timeout=60)
        assert probe.returncode==0,probe.stderr
        gpu=json.loads(probe.stdout);assert gpu['cuda'],'No CUDA; no CPU fallback allowed'
        assert gpu['versions']=={'torch':'2.11.0+cu128','transformers':'4.57.6','tokenizers':'0.22.2','accelerate':'1.15.0','safetensors':'0.8.0'},'HF environment differs from qualified profile'
        result['hf']=gpu
    atomic_json(output/'profile.json',{'policy':policy.model_dump(),'model':profile.model_dump(mode='json')})
    atomic_json(output/'preflight.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0)
assert action=='audit'
case_root=Path(sys.argv[4]).resolve();letter=sys.argv[5];task=tasks[letter]
paths=list((case_root/letter).glob('*/run_record.json'));assert len(paths)==1,'Exactly one canonical per case is required'
path=paths[0];record=json.loads(path.read_text(encoding='utf-8'));assessment=assess_record(path)
print('CANONICAL '+str(path));print(path.read_text(encoding='utf-8'))
for label,key in (('PROMPT','prompt.txt'),('RAW OUTPUT',record.get('artifacts',{}).get('raw_output')),('CANDIDATE',record.get('artifacts',{}).get('candidate')),('APPLIED',record.get('artifacts',{}).get('applied')),('EVIDENCE BUNDLE',record.get('artifacts',{}).get('bundle'))):
    if key:
        artifact=(path.parent/key).resolve();assert artifact.parent==path.parent.resolve() and not artifact.is_symlink()
        print(label+' '+str(artifact))
        try:print(artifact.read_text(encoding='utf-8'))
        except OSError as exc:print('ARTIFACT READ ERROR '+repr(exc))
for worker in sorted((case_root/letter/'model-workers').rglob('*.json')):
    assert not worker.is_symlink();print('WORKER JSON '+str(worker))
    try:print(worker.read_text(encoding='utf-8'))
    except OSError as exc:print('WORKER READ ERROR '+repr(exc))
assert assessment['status']=='PASS' and not assessment['gate_errors'],assessment
assert record['task']==task.model_dump(mode='json') and record['model']==profile.model_dump(mode='json')
assert record['policy']==policy.model_dump() and record.get('prompt_feedback') is None
stages=record['stages'];prompt=stages['prompt'];generation=stages['generation']
assert prompt['template_hash']==digest((root/'prompts/repair_v11.txt').read_bytes()) and prompt.get('metadata',{}).get('feedback') is None
assert digest((path.parent/'prompt.txt').read_bytes())==prompt['prompt_hash']
assert generation['input_sha256']==prompt['prompt_hash'].removeprefix('sha256:')
raw=(path.parent/record['artifacts']['raw_output']).read_bytes()
assert raw==(path.parent/record['artifacts']['candidate']).read_bytes() and raw.decode('utf-8')==generation['raw_text']
diagnostic=generation['generation_diagnostics'];mask=diagnostic['attention_mask']
assert diagnostic['status']=='PASS' and diagnostic['effective_observed'] is True
assert diagnostic['effective_generation_config']['do_sample'] is False and diagnostic['effective_generation_config']['max_new_tokens']==1536
assert 0<generation['input_tokens']==prompt['input_tokens']<=6000 and generation['device_map']
assert mask['shape']==[1,generation['input_tokens']] and mask['binary'] is True and mask['zeros']==0
assert all(record['source_fingerprint'][p]==h for p,h in expected.items())
assert stages['cleanup']['status']=='PASS'
required=stages['baseline']['required_ids'];assert len(required)==(2 if letter=='B' else 1)
assert all(stages['baseline']['tests']['outcomes'][n]=='FAIL' for n in required)
parsed=parse_unified_diff(raw.decode('utf-8'),PatchPolicy(task.allowed_source_paths,task.protected_paths));predicted,_=_bind(parsed,task.source_repo)
def signatures(data):
    return {n.name:(type(n).__name__,ast.dump(n.args),ast.dump(n.returns) if n.returns else None) for n in ast.parse(data).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
assert all(signatures((task.source_repo/p).read_bytes())==signatures(data) for p,data in predicted.items())
require_trusted_fixture(task)
result=dict(assessment,task_id=task.task_id,letter=letter,runtime_revision='r002',prompt_version='m2-w78-v11',input_tokens=generation['input_tokens'],output_tokens=generation['output_tokens'],duration_ms=record['duration_ms'])
atomic_json(output/f'audit_{letter}.json',result);print('AUDIT '+letter+' PASS')
'@
$helperPath = Join-Path $OutputRoot 'verification_job.py'
[IO.File]::WriteAllText($helperPath,$helper,$utf8)
$summary = [ordered]@{status='NOT_RUN';complete=$false;mode=$Mode;skip_self_tests=[bool]$SkipSelfTests;started_utc=[DateTime]::UtcNow.ToString('o');ended_utc=$null;cases=@();output_root=$OutputRoot;reason=$null}
$summaryPath = Join-Path $OutputRoot 'summary.json'
Write-Json $summaryPath $summary
$priorEnvironment = @{PYTHONUTF8=$env:PYTHONUTF8;TEMP=$env:TEMP;TMP=$env:TMP}
Push-Location $root
try {
    $env:PYTHONUTF8 = '1'
    $env:TEMP = Join-Path $OutputRoot 'temp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
    Write-Log "MODE=$Mode OUTPUT=$OutputRoot; no install, no source edits, no automatic retries."
    Invoke-Logged 'preflight' $Python @($helperPath,'preflight',$root,$OutputRoot,$Mode)
    if ($Mode -eq 'Run' -and -not $SkipSelfTests) {
        try { Invoke-Logged 'self_tests' $Python @('scripts\record_tests.py','tests','--timeout-seconds','240','--output-root',(Join-Path $OutputRoot 'self_tests')) }
        finally {
            if (Test-Path -LiteralPath (Join-Path $OutputRoot 'self_tests')) {
                Get-ChildItem -LiteralPath (Join-Path $OutputRoot 'self_tests') -Filter 'run_record.json' -Recurse -File | ForEach-Object { Write-Log ([IO.File]::ReadAllText($_.FullName,$utf8)) }
            }
        }
        Invoke-Logged 'ruff' $Python @('-m','ruff','check','--select','E9,F','src','scripts','tests')
    }
    if ($Mode -ne 'Check') {
        $caseNames = @('single_file_login','multi_file_invoice','missing_links')
        $letters = @('A','B','C')
        for ($index=0; $index -lt 3; $index++) {
            $letter = $letters[$index]
            $case = $caseNames[$index]
            $summary.cases += [ordered]@{letter=$letter;task_id=$case;status='NOT_RUN';reserved_utc=[DateTime]::UtcNow.ToString('o')}
            Write-Json $summaryPath $summary
            $caseRoot = $SavedRoot
            if ($Mode -eq 'Run') {
                $caseRoot = $OutputRoot
                Invoke-Logged ('run_'+$letter) $Python @('scripts\run_demo.py','--mode','real','--task',('examples\tasks\'+$case+'.json'),'--config',(Join-Path $OutputRoot 'profile.json'),'--output-root',(Join-Path $OutputRoot $letter))
            }
            Invoke-Logged ('audit_'+$letter) $Python @($helperPath,'audit',$root,$OutputRoot,$caseRoot,$letter)
            $audit = Get-Content -Raw -Encoding UTF8 (Join-Path $OutputRoot ('audit_'+$letter+'.json')) | ConvertFrom-Json
            if ($audit.status -ne 'PASS' -or @($audit.gate_errors).Count -ne 0) { throw "Acceptance gate failed for $letter; inspect audit JSON." }
            $summary.cases[$index] = $audit
            Write-Json $summaryPath $summary
        }
        Write-Log '3/3 CASE AUDITS PASS. ReadSaved re-audits existing records; only Run performs NEW generations.'
    }
    $summary.status = 'PASS'
    $summary.complete = $true
    $summary.ended_utc = [DateTime]::UtcNow.ToString('o')
    Write-Json $summaryPath $summary
    Write-Log ("DONE mode={0}; summary={1}" -f $Mode,$summaryPath)
    exit 0
} catch {
    $caughtFailure = $_.ToString() + [Environment]::NewLine + $_.ScriptStackTrace
    if ($Mode -eq 'Run' -and (Get-Variable -Name letter -ErrorAction SilentlyContinue)) {
        try { Invoke-Logged ('failed_evidence_'+$letter) $Python @($helperPath,'audit',$root,$OutputRoot,$OutputRoot,$letter) } catch { Write-Log 'Failure evidence dump completed or failed; original failure is retained below.' }
    }
    $summary.status = 'ERROR'
    $summary.complete = $true
    $summary.reason = $caughtFailure
    $summary.ended_utc = [DateTime]::UtcNow.ToString('o')
    Write-Json $summaryPath $summary
    Write-Log $summary.reason
    Write-Log 'STOP: remaining cases were NOT launched. Inspect canonical/worker evidence; never edit a patch to force PASS.'
    exit 2
} finally {
    Pop-Location
    $env:PYTHONUTF8 = $priorEnvironment.PYTHONUTF8
    $env:TEMP = $priorEnvironment.TEMP
    $env:TMP = $priorEnvironment.TMP
}
```

