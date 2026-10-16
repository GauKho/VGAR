# M2 tuần 7–8 — Repair & Verification

**Cập nhật: 15/10/2026.** Đây là package độc lập `M2_week_7_8` dùng đầu ra
Graph & Retrieval của M1 để sinh patch bằng LLM, áp dụng vào bản sao riêng và
kiểm chứng trước khi bàn giao kết quả.

**Trạng thái đã xác minh:** ba case A/B/C chạy LLM thật đều **PASS**, cùng
repair template **V11**, core runtime **r002**, không feedback. Người dùng đã
tự chạy lại workflow thành công; kết quả và đường dẫn của lượt đó được ghi ở mục4.

> **Phạm vi kết luận:** M2 đạt nghiệm thu kỹ thuật repair–verification trên ba
> fixtures development. Chưa đồng nghĩa toàn bộ VGAR có MCP/LangChain của M3,
> SWE-bench hoặc khả năng sửa mọi repository đã hoàn tất.

## 1. Chạy nhanh trên máy đã setup

Nếu đang dùng máy đã chạy thành công và không thay đổi profile, chỉ cần mở
PowerShell trong VS Code rồi chạy **một lệnh**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Project\CAPSTONES\M2_week_7_8\test_abc_v11_r002.ps1"
```

Script tự tìm project theo vị trí file PS1; không cần activate venv, không cần
biến `$python` từ phiên terminal trước và không cần chạy từng case bằng tay.

Workflow mặc định:

1. Kiểm tra prerequisites, pinned source, runtime và profile.
2. Chạy self-tests của M2 và Ruff.
3. Chạy LLM sửa A, kiểm chứng A; sau đó tương tự B rồi C.
4. Audit từng kết quả, in đầy đủ logs và lưu evidence riêng.

**Không cài lại dependencies hoặc tải model trong script.** Mỗi case tối đa một
generation; script dừng ở lỗi đầu tiên, không tự đổi prompt hoặc retry đến PASS.
Đọc mục6 nếu muốn kiểm tra môi trường hoặc xem kết quả cũ mà không inference.

Output mặc định tự tạo, không nhập run ID:

```text
D:\Project\CAPSTONES\M2_week_7_8\results\manual_abc\<UTC-GUID>\
```

Chạy tests cần tạo logs/temp/worktree riêng, nhưng **không áp dụng patch vào source
gốc**. ExecutionPolicy Bypass chỉ áp dụng child PowerShell này, không đổi policy
Windows toàn máy. Lệnh trên giả định folder và prerequisites hiện có trên máy;
máy mới cần đọc mục8 trước.

## 2. M2 làm gì, không làm gì?

### 2.1. Bảy task đã triển khai

| Task | Cách thực hiện trong package |
|---|---|
| Repair prompt cố định | V11 quy định phạm vi, format và replacement hunks; ghép issue/baseline/context theo từng case |
| Một LLM backend cố định | Local HF Qwen3-4B pinned; worker tách process, không fake/API fallback |
| Validate/parse unified diff | Kiểm format, paths, protected files, counts và giới hạn patch |
| Apply temporary worktree | Tạo private Git snapshot/worktree; exact bind, Git preflight/apply, đối chiếu bytes |
| Relevant-test selection | Dùng M1 hints từ actual changed paths; giữ required tests và full approved fixture regression/fallback |
| Pytest/typecheck/lint | Collect và chạy tests thật; syntax, mypy, Ruff; so baseline với post-patch |
| Evidence bundle | Lưu input/output/patch/commands/outcomes/timing/diagnostics/integrity và public bundle |

Code điều phối chính ở [pipeline.py](src/vgar_m2_w78/pipeline.py).
Giải thích từng task bằng ngôn ngữ dễ hiểu: mục0.3 của [File02](docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md).

### 2.2. Ranh giới với M1 và M3

| Vai trò | Trách nhiệm |
|---|---|
| M1 | Cung cấp graph-guided context, node IDs/ranges/metadata, consumer và test-link hints |
| M2 | Nhận/validate context, gọi model, parse/apply patch, chọn/chạy tests và trả evidence |
| M3 | Bọc MCP tools, nối LangChain retrieve → generate → patch → verify và nghiệm thu tích hợp |

M2 không xây lại graph/ranking của M1. Nó dùng consumer `receive_context_handoff`
và diagnostics `diagnose_changed_paths` từ sibling VGAR đã pin. Kết quả hints
không phải coverage hoặc bằng chứng tests đã chạy; M2 phải collect/execute thật.

Standalone hiện chưa có tool calls MCP thực thi. M3 phải giữ cùng worktree,
baseline và run state khi bọc `apply_patch`, `run_relevant_tests`, `verify_patch`;
không tạo workspace khác cho mỗi tool rồi coi như cùng repair.

Native worktree **không phải OS sandbox**. Chỉ ba fixtures tin cậy được khóa bytes
được chấp nhận trong profile này; không dùng script để chạy repository lạ.

## 3. Năm file chính: đọc file nào, dùng khi nào?

| File | Mục đích | Khi nào dùng? |
|---|---|---|
| [01 — Bàn giao M1/M3](docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md) | Kết quả, input/output, provenance M1, interface và phần việc còn lại | Trước khi bàn giao hoặc tích hợp |
| [02 — Báo cáo toàn bộ M2](docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md) | Giải thích task, thuật toán, flow, lịch sử, từng module và path inventory | Khi cần hiểu hoặc kiểm tra implementation |
| [03 — PowerShell A/B/C](docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md) | Lệnh theo thứ tự, giải thích từng dòng script, output và toàn bộ log families | Khi tự chạy và điều tra kết quả |
| [requirement.txt](requirement.txt) | Core dependency pins và ghi chú prerequisites HF/tools tách riêng | Chỉ setup lần đầu hoặc xử lý môi trường thiếu/sai |
| [test_abc_v11_r002.ps1](test_abc_v11_r002.ps1) | Thực thi toàn workflow bằng một lệnh, có Check/ReadSaved/Run | Khi kiểm tra hoặc nghiệm thu thực tế |

### 3.1. File01 — dùng để bàn giao

M1/M3 đọc để biết M2 đã nhận gì từ M1, đã kiểm chứng đến đâu, bằng chứng nằm ở đâu
và ai cần làm gì tiếp. File có interface Python, ownership/worktree/baseline
requirements, giới hạn Native và gate tích hợp chưa được ký thay.

Bảng số liệu trong File01 được gắn với lượt final trước đó, không tự cập nhật
sau mỗi lần chạy. Số liệu lượt người dùng tự chạy lại ở mục4 README này.

### 3.2. File02 — dùng để hiểu dự án

Đọc theo thứ tự:

- **Mục0.1–0.2:** vai trò và cách sử dụng đầu ra M1.
- **Mục0.3:** từng task yêu cầu gì, làm bằng phương pháp nào và ở file nào.
- **Mục0.4–0.7:** boundary M3, flow, ví dụ A/B/C và tự kiểm thử.
- **Mục0.9:** chuyên đề V11, giải thích từng quy tắc và liên kết với code.
- **Mục1–15:** đối chiếu kỹ thuật, module, history, checks và references.
- **Phụ lục A:** tra từng file/thư mục, gồm dependencies/caches/evidence lịch sử.

Inventory là snapshot theo thời điểm đã ghi, không tự mở rộng khi run sinh files
mới. Venv/vendor có mặt trong bảng không có nghĩa chúng là code M2 tự viết hoặc
đều cần push. Preview File02 có thể nặng vì phụ lục lớn; dùng tìm kiếm theo path.

### 3.3. File03 — dùng để tự chạy

File giải thích input, mục đích, expected output và vị trí logs của các lệnh.
Có cả chú thích từng dòng của PS1 và bản script liền mạch để đối chiếu.
Ưu tiên chạy file PS1 thực tế; không dán riêng một dòng nằm giữa function hoặc
Python here-string.

Phân biệt rõ Check, ReadSaved và Run; chỉ Run tạo repairs mới.

### 3.4. requirement.txt — dùng để setup, không phải lệnh chạy repair

Các dòng dependency thực thi của file chỉ cài **core M2**. HF worker cần môi trường
riêng; hướng dẫn/pins HF và Git/driver/model/tokenizer assets nằm trong comments.
Không trộn hai môi trường vì tokenizer versions khác nhau.

Không chạy lại pip mỗi lần test nếu môi trường đã sẵn sàng. File không tự cung
cấp model weights, NVIDIA driver, Git hay pinned source M1.

### 3.5. PS1 — dùng để thực thi

Script chọn V11 rõ ràng, kiểm core r002/profile, chạy tuần tự và lưu output riêng.
Không ghi đè output cũ, không reset historical campaign/quota, không sửa fixture/
prompt/parser/verifier để ép PASS. Kết quả thực tế ở JSON/logs, không chỉ terminal.

**Gợi ý đọc nhanh:** muốn chạy → README + File03; muốn hiểu → File02; muốn bàn giao
→ File01; thiếu môi trường → requirement.txt và mục8; chạy toàn luồng → PS1.

## 4. Tổng hợp kết quả đã chạy và evidence

### 4.1. Lượt người dùng tự chạy lại — PASS

Run:

```text
20261015T114826234Z-922d5c80
```

[Summary](results/manual_abc/20261015T114826234Z-922d5c80/summary.json)
ghi `status=PASS`, `complete=true`, `mode=Run`, `skip_self_tests=false` và ba audits
có `gate_errors=[]`. Các canonical đều `mode=real`, V11/r002. Đây là generation
mới, không phải re-audit old records.

Thời gian workflow: **khoảng 7 phút 9 giây (429,152 giây)**, từ 18:48:26 đến 18:55:35
ngày 15/10/2026 theo Asia/Saigon (UTC+7). Tổng này gồm self-tests, readiness, repairs
và audits; không gọi toàn bộ nó là thời gian model.generate.

**Tách trước/sau để tránh hiểu nhầm FAIL:**

| Case và file thực sự sửa trong worktree | Trước sửa — Baseline | Sau sửa — Post | Kết quả cuối |
|---|---|---|---|
| A — `single_file_login`, `auth.py` | 1 test FAIL, 1 test PASS | 2 tests PASS | **PASS** |
| B — `multi_file_invoice`, `invoice.py` và `pricing.py` | 2 tests FAIL, 1 test PASS | 3 tests PASS | **PASS** |
| C — `missing_links`, `formatter.py` | 1 test FAIL, 1 test PASS | 2 tests PASS | **PASS** |

**FAIL ở baseline là bằng chứng code ban đầu có lỗi, không phải final repair FAIL.**
Required failing tests phải chuyển FAIL→PASS; những tests vốn đúng phải tiếp tục
PASS. C thực sự dùng fallback `tests` vì source→test links bị thiếu.

| Case | Pipeline repair (giây) | Input tokens | Output tokens |
|---|---:|---:|---:|
| A | 70,953 | 1.299 | 43 |
| B | 163,765 | 1.769 | 157 |
| C | 66,906 | 1.169 | 43 |
| Tổng | 301,624 | 4.237 | 243 |

Pipeline là thời gian của một repair run, gồm nhiều stages, không chỉ model
generation. Timers generation stage và model.generate là những phép đo khác,
có phần lồng nhau nên không cộng trùng. Các số này mô tả lượt đã lưu, không cam
kết lần sau luôn cùng tốc độ hoặc luôn PASS.

| Kiểm tra khác trong lượt này | Kết quả |
|---|---|
| Self-tests engine | **234 PASS trong 117,63 giây**, recorder 118,438 giây |
| Ruff của engine | exit 0 |
| Collection và post-tests A/B/C | PASS |
| Syntax / mypy / Ruff của ba fixtures | PASS |
| Audit A/B/C | PASS, không gate errors |
| Cleanup và original source integrity | PASS; source gốc giữ nguyên cả ba case |

234 tests là kiểm code engine, khác 7 tests fixture sau sửa (2+3+2). Bộ 8 tests riêng
của script bàn giao đã được kiểm ở phiên trước; không cộng chúng thành số tasks
LLM sửa thành công hoặc coi như đã chạy mới trong workflow này.

### 4.2. Mở đúng hồ sơ của lượt trên

| Nội dung | File |
|---|---|
| Tổng hợp | [summary.json](results/manual_abc/20261015T114826234Z-922d5c80/summary.json) |
| Full logs | [all_logs.txt](results/manual_abc/20261015T114826234Z-922d5c80/all_logs.txt) |
| Canonical A | [A/run_record.json](results/manual_abc/20261015T114826234Z-922d5c80/A/20261015T115029684721Z-de11d86b3fe2/run_record.json) |
| Canonical B | [B/run_record.json](results/manual_abc/20261015T114826234Z-922d5c80/B/20261015T115142396726Z-ac33bc20c338/run_record.json) |
| Patch B thực tế | [B/applied.diff](results/manual_abc/20261015T114826234Z-922d5c80/B/20261015T115142396726Z-ac33bc20c338/applied.diff) |
| Canonical C | [C/run_record.json](results/manual_abc/20261015T114826234Z-922d5c80/C/20261015T115427854568Z-9e414afa7685/run_record.json) |
| Self-tests | [self_tests/run_record.json](results/manual_abc/20261015T114826234Z-922d5c80/self_tests/20261015T114830171270Z-c6796e15d1a7/run_record.json) |
| Ruff command/exit | [ruff.command.json](results/manual_abc/20261015T114826234Z-922d5c80/ruff.command.json) |

Các links evidence chỉ mở được khi package kết quả tương ứng có trên máy/repo.
Không giả định caches/weights/results đều được đưa lên Git.

### 4.3. Đối chiếu lượt final trước đó và lịch sử

Lượt final gốc cũng đạt 3/3 V11/r002, không feedback; xem
[báo cáo final](docs/NGHIEM_THU_FINAL_A_B_C_V11_R002.md),
[manifest](results/final_acceptance/2026-10-15-v11-r002/run_manifest.json) và
[combined audit](results/final_acceptance/2026-10-15-v11-r002/audits/20261015T073438247626Z-8ce2a58ef084/run_record.json).

Các báo cáo V1–V10/campaign cũ có FAIL/BLOCKED là lịch sử theo mốc đó, không thay
kết quả hiện tại. Không xóa failures hoặc reset campaigns terminal. B development
từng PASS với feedback; final3 và lượt người dùng ở trên không gộp PASS khác
versions hoặc dùng feedback để gọi thành final cùng-template.

## 5. Flow hoạt động: input → patch → kiểm chứng → output

```text
Task JSON + original snapshot + M1 bundle/counter
                    ↓
Validate source/task/context/provenance
                    ↓
Tạo private Git snapshot và worktree
                    ↓
Collect + chạy baseline tests/static checks
                    ↓
V11 + permissions + issue + failed IDs + context
                    ↓
Tokenize/full-chat budget → HF Qwen sinh một diff
                    ↓
Lưu raw → parse/paths/counts → exact bind/Git apply
                    ↓
Actual changed files → M1 test-link diagnostics
                    ↓
Required + full fixture regression/fallback
                    ↓
Post collection/tests + syntax/mypy/Ruff
                    ↓
Original/protected integrity + cleanup
                    ↓
Canonical + raw/candidate/applied diff + EvidenceBundle
```

| Bước | Input và cách xử lý | Output quan trọng |
|---|---|---|
| Nhận task | Đọc issue/source/bundle/selectors/allowed paths từ JSON | Validated task |
| Nhận M1 | Consumer kiểm repo/revision/graph/snippet/range/token/hash | Validated context + provenance |
| Workspace | Sao chép approved bytes, tạo private Git worktree | Lease/worktree ID, original hashes |
| Baseline | Collect thật và chạy buggy code trong worktree | Required IDs/outcomes/commands/JUnit/static |
| Prompt | Quy tắc V11 + dữ liệu case, original coordinates/read-only metadata | `prompt.txt`, template/full-prompt hashes/tokens |
| Generation | Pinned HF worker, không API/fake fallback | Raw text, finish reason/config/mask/device/timing |
| Parse/apply | Đúng format/paths/counts/source text; Git check/apply; byte attestation | Candidate/transport/applied diff |
| Chọn tests | Actual changed paths qua M1 diagnostics; giữ required/full approved scope | Selection/fallback reasons |
| Verification | Required FAIL→PASS, regression PASS, static/config/integrity | Post outcomes và reasons |
| Finalize | Cleanup; bind canonical/public artifacts | `run_record.json`/`evidence_bundle.json`/`REPORT.md` |

Model chỉ đề xuất patch. Nó không tự thực thi commands hoặc tự tuyên bố PASS.
Prompt có yêu cầu bảo toàn chữ ký/hành vi; audit final đối chiếu signatures cơ
bản của fixtures, không thay một API/architecture verifier tổng quát.

## 6. Các cách chạy và thứ tự khuyến nghị

### 6.1. Máy đã sẵn sàng: không cài lại

Có thể đứng ở bất kỳ working directory nào nếu dùng đường dẫn tuyệt đối dưới
đây. Lệnh dùng Windows PowerShell, không phải Arduino.

**Kiểm môi trường trước — không load weights để generation:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Project\CAPSTONES\M2_week_7_8\test_abc_v11_r002.ps1" -Mode Check
```

Check PASS chỉ là readiness. Nếu không đạt, đọc log để xử lý trước; không sửa
registry/frozen hashes để bỏ guard.

**Tùy chọn đọc/audit old final evidence — không sinh patch mới:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Project\CAPSTONES\M2_week_7_8\test_abc_v11_r002.ps1" -Mode ReadSaved
```

Mặc định ReadSaved dùng `results/final_acceptance/2026-10-15-v11-r002`, không tự
chọn lượt manual mới nhất. Nó tạo logs/audits riêng nhưng giữ nguyên records cũ.

**Chạy mới toàn workflow A → B → C:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Project\CAPSTONES\M2_week_7_8\test_abc_v11_r002.ps1"
```

Đây là mode Run mặc định. Không cần chạy `record_tests.py tests` thêm trước đó,
vì workflow đã làm. Không cần thực hiện cả ReadSaved và Run nếu chỉ muốn xem kết
quả đã có. Compute/điện local vẫn tốn tài nguyên, không chạy lặp chỉ để lấy thêm PASS.

**Xem exit code ngay sau lệnh cần kiểm:**

```powershell
$LASTEXITCODE
```

- Exit 0: hoàn tất theo mode. Chỉ Run mới có generations mới.
- Exit 2: lỗi trong vùng readiness/command/audit được script quản lý.
- Setup guard trước try có thể exit 1, ví dụ Python thiếu/output đã có.
- Mọi nonzero đều cần xem summary/canonical; không mặc định model là nguyên nhân.

| Tham số | Mục đích / lưu ý |
|---|---|
| `-Mode Run` | Mặc định; readiness+selftests+Ruff+fresh repairs+audits |
| `-Mode Check` | Readiness, không inference; không chứng minh repair PASS |
| `-Mode ReadSaved` | Re-audit hồ sơ có sẵn, không independent model reproduction |
| `-SavedRoot` | Chọn root chứa A/B/C khi ReadSaved |
| `-OutputRoot` | Phải là path mới dưới results của M2; không ghi đè evidence |
| `-Python` | Core interpreter; không phải HF worker interpreter |
| `-SkipSelfTests` | Chỉ khi cùng code đã được kiểm; vẫn chạy fixture verification, summary ghi đã skip |

### 6.2. Vì sao cần giữ nguyên config và source?

Model `Qwen/Qwen3-4B-Instruct-2507` pin revision
`cdbee75f17c01a7cc42f958dc650907174af0554`; greedy/FP16/`device_map=auto`,
có thể offload CPU. Profile giữ input 6.000/output 1.536/reserve 256 tokens,
generation 900s/command 120s/global 1.800s mỗi repair run.

`config/demo.json` vẫn historicalV2. Root runner tạo profile V11 riêng ở output;
không tự sửa default. CLI cũ không truyền config phù hợp có thể chạy V2 dù file
V11 tồn tại. Xem [final profile](results/final_acceptance/2026-10-15-v11-r002/final_profile.json).

r002 là version core, không phải model. Runner so với registered r002 fingerprint.
Thay model/config/pinned inputs có thể làm guard dừng; phải có quy trình review/
qualification riêng, không sửa frozen registration hoặc old evidence để “khớp”.

## 7. Output nằm đâu và đọc như thế nào?

### 7.1. Cấu trúc output của một lần chạy

```text
results/manual_abc/<UTC-GUID>/
├── summary.json                # mode/status/cases/canonical refs
├── all_logs.txt                # toàn bộ text script in ra
├── preflight.json              # readiness/profile/runtime/dependencies
├── profile.json                # policy V11 + model paths cho lần này
├── verification_job.py          # audit helper của lần này
├── *.command.json              # argv/exit/UTC/duration của mỗi child step
├── *.console.log               # stdout/stderr của child step
├── audit_A.json / audit_B.json / audit_C.json
├── self_tests/<ID>/             # core pytest recorder/JUnit/REPORT
└── A/ B/ C/
    ├── <ID>/
    │   ├── run_record.json
    │   ├── prompt.txt
    │   ├── raw_model_output.txt
    │   ├── candidate.diff
    │   ├── transport.diff
    │   ├── applied.diff
    │   ├── evidence_bundle.json
    │   └── REPORT.md
    └── model-workers/<ID>/      # requests/responses/command/diagnostics
```

Đây là cấu trúc minh họa; `A/ B/ C/` là ba thư mục riêng, không một path có spaces.
Artifacts chỉ xuất hiện khi stage tương ứng đã có dữ liệu. Source worktree
private/cleanup receipts được core quản lý riêng; không cần worktree còn tồn tại
để đọc applied diff đã xuất.

`summary.json.previous` nếu có là bản gần trước của atomic update, không verdict
terminal mới nhất.

### 7.2. Tự tìm Run mới nhất, tránh nhầm Check/ReadSaved

**Đổi vào project để dùng các relative paths dưới đây:**

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
```

**Chỉ đọc: tìm folder default có summary mode Run; không nhập tay run ID:**

```powershell
$run = Get-ChildItem -LiteralPath '.\results\manual_abc' -Directory |
    Where-Object {
        $candidateSummary = Join-Path $_.FullName 'summary.json'
        if (Test-Path -LiteralPath $candidateSummary) {
            (Get-Content -Raw -Encoding UTF8 $candidateSummary | ConvertFrom-Json).mode -eq 'Run'
        }
    } |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1 -ExpandProperty FullName
```

**Dừng nếu chưa có output Run:**

```powershell
if (-not $run) {
    throw 'Chưa có output mode Run trong results\manual_abc.'
}
```

Cách tìm này chỉ áp dụng output default. Nếu dùng `-OutputRoot` riêng, đọc path
script đã in. Latest có thể là run thất bại/đang chạy, phải xem status/complete
thay vì tự coi latest=PASS.

**Đọc index đầy đủ:**

```powershell
Get-Content -Raw -Encoding UTF8 (Join-Path $run 'summary.json')
```

**Đọc full logs, không cắt nested fields thành bảng:**

```powershell
Get-Content -Raw -Encoding UTF8 (Join-Path $run 'all_logs.txt')
```

**Xem patch B đã apply trong private worktree:**

```powershell
if (Test-Path -LiteralPath (Join-Path $run 'B')) {
    Get-ChildItem -LiteralPath (Join-Path $run 'B') -Filter 'applied.diff' -File -Recurse |
        ForEach-Object {
            Get-Content -Raw -Encoding UTF8 $_.FullName
        }
}
```

Nếu B chưa tới stage apply sẽ chưa có file này. Xem raw/parser/summary, không
tự lấy reference diff thay vào.

**Tùy chọn audit lại đúng Run vừa chọn, không generation mới:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\test_abc_v11_r002.ps1' -Mode ReadSaved -SavedRoot $run
```

### 7.3. Logs và trạng thái cần đọc

Canonical giữ từng stage, UTC start/end, elapsed durations, argv/cwd/interpreter,
stdout/stderr/exit/timeout/truncation, collected IDs/outcomes/JUnit/config hashes.
Parser lỗi có raw line/file/hunk/expected-actual counts/`counts_complete`;
exception managed boundaries có chained traceback. HF diagnostics có observed
effective config, actual mask, token counts, device placement và load/gen times.

Runner in canonical, prompt, raw, candidate/applied diff, bundle và worker JSON.
Không token-streaming từ model; terminal có thể cắt hiển thị nhưng file log/raw
là nguồn đầy đủ. Pipeline FAIL/ERROR ở stage nào chưa tới thì giữ NOT_RUN/null,
không bịa PASS.

| Giá trị | Hiểu đúng |
|---|---|
| Baseline tests FAIL | Mong đợi cho lỗi ban đầu, chưa phải verdict repair |
| `baseline.status=PASS` | Baseline đủ điều kiện, không nghĩa buggy tests đã PASS |
| Final PASS | Đạt checks/gates hiện có của fixture/profile, không proof mọi semantics |
| FAIL | Candidate/behavior/static không đạt; xem stage/reasons |
| ERROR | Input/runtime/incomplete/finalization cần điều tra |
| NOT_RUN | Chưa chạy, không được coi PASS |
| `complete=true` | Run đã terminal; vẫn cần xem status và mode |

API/structural fields trong public bundle hiện NOT_RUN; audit signatures fixture
cơ bản không tự biến chúng thành full verifier tuần sau.

## 8. Setup lần đầu hoặc chuyển máy: không trộn hai môi trường

**Máy hiện tại đã chạy PASS: bỏ qua cài đặt và dùng mục1/6.** Runner không tự sửa
môi trường. Clone/copy source không tự có drivers, weights, venv hoặc mọi assets.

### 8.1. Prerequisites

- Windows PowerShell 5.1 trở lên, Python 3.11 x64 (đã qualified 3.11.6), Git for Windows.
- NVIDIA driver/GPU và HF Torch CUDA phù hợp profile. Không fallback CPU-only.
- Sibling `VGAR` đúng [source_pin.json](config/source_pin.json), hiện pin HEAD
  `b8e2461635b81d1ae790445efea5c9757d91700a` và 12 boundary files/import origin.
- Prepared `examples/tasks`, `snapshots`, `handoffs`, `inputs_receipt.json`.
- M1 tokenizer manifest/assets đúng hashes; current manifest ở
  `..\VGAR\artifacts\m2\w5-w6\tokenizer_manifest.json`.
- Cached Qwen snapshot đúng revision, local_files_only; không auto-download.

Windows fixture bytes hiện dùng CRLF. Khi chuyển/copy/checkout phải giữ đúng
bytes; mismatch cần review/provision/export đúng, không sửa registry để bypass.
Chưa mặc định nghiệm thu Linux/container portability.

### 8.2. Core venv — chỉ khi chưa được provision

**Chọn project:**

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
```

**Tạo core venv chỉ khi chưa có interpreter:**

```powershell
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe' -PathType Leaf)) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Không tạo được core venv Python 3.11.' }
}
```

**Cài 7 core pins từ requirement.txt một lần; không chạy mỗi lần test:**

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r '.\requirement.txt'
if ($LASTEXITCODE -ne 0) { throw 'Cài core dependencies thất bại.' }
```

**Cài editable package một lần, không tự resolve lại dependencies:**

```powershell
& '.\.venv\Scripts\python.exe' -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Cài editable package thất bại.' }
```

Build backend cần setuptools theo pyproject; cài đặt lần đầu có thể cần mạng.
Không có lệnh cài đặt nào trong root test runner.

### 8.3. HF worker — môi trường riêng

| Môi trường | Python/packages chính | Công việc |
|---|---|---|
| Core `M2_week_7_8/.venv` | Pydantic, dotenv, Jinja2, tokenizers 0.22.1, pytest, mypy, Ruff theo requirement.txt | Điều phối, consumer, parser, tests, evidence |
| HF interpreter riêng | Torch 2.11.0+cu128, Transformers 4.57.6, tokenizers 0.22.2, Accelerate 1.15.0, safetensors 0.8.0 | Tokenize và sinh patch |

Đường dẫn HF hiện tái dùng
`D:\Project\CAPSTONES\vgar_mcp_mvp\.venv\Scripts\python.exe`. Đây là dùng interpreter/
dependencies, không chạy/import/sửa hệ thống cũ. Không xóa venv đó nếu profile
còn trỏ tới nó. Có thể provision interpreter riêng nhưng cần profile/qualification
được ghi nhận; thay config làm thay frozen core hash, không sửa registration cũ.

HF install commands có chú thích trong [requirement.txt](requirement.txt); phải
thực thi bằng **HF Python**, không core Python. Hai tokenizer pins khác nhau là
có chủ đích. Cài core requirements không đủ để có Torch/model/driver.

Nếu đổi máy/paths/source, không hứa chỉ cài pip là runner r002 đã tái lập được:
cần đồng bộ assets, reference và profile theo quy trình được duyệt. Không chỉnh
old records/hash để giả là cùng môi trường. Model qualifier OK cũng không thay
repair acceptance.

### 8.4. Nếu chỉ muốn kiểm code engine, không inference

Lệnh dưới là **tùy chọn riêng**, không cần chạy thêm khi đã dùng Run mặc định:

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\record_tests.py' tests --timeout-seconds 240
$LASTEXITCODE
```

Output có canonical/JUnit/REPORT dưới `results/tests`. Engine tests PASS không
đồng nghĩa model sửa được A/B/C. Fake mode dùng reference diff chỉ thử plumbing,
không được tính real repair; không ưu tiên nó thay workflow V11 ở mục1.

## 9. Cấu trúc project và inputs A/B/C

```text
M2_week_7_8/
├── README.md
├── PROGRESS.md
├── requirement.txt
├── test_abc_v11_r002.ps1
├── pyproject.toml
├── config/             # pins, defaultV2, trusted registry, static configs
├── examples/
│   ├── tasks/          # RepairTask JSON
│   ├── snapshots/      # original buggy source/tests/config
│   ├── handoffs/       # M1 context/manifest/test_links/producer text
│   └── inputs_receipt.json
├── prompts/            # historical V1–V11 templates
├── src/vgar_m2_w78/     # core repair/verification
├── scripts/            # demo, recorder, qualifier, preparation, campaigns
├── tests/              # engine tests; reference patches chỉ fake/unit
├── docs/               # ba tài liệu chính + guides/history
├── results/            # immutable history + new per-run evidence
├── .workspaces/        # private worktrees/cleanup receipts
└── .venv/              # local core environment, không model weights
```

`requirement.txt` và PS1 thuộc root, không nằm dưới docs. Source snapshots là
fixtures M1 đã được chuẩn bị, không SWE-bench tasks:

| Case | Input task | Source và mục tiêu |
|---|---|---|
| A | [single_file_login.json](examples/tasks/single_file_login.json) | Trim tên trước kiểm rỗng; `auth.py` |
| B | [multi_file_invoice.json](examples/tasks/multi_file_invoice.json) | Discount/tax phải là phần trăm; `pricing.py` + `invoice.py` |
| C | [missing_links.json](examples/tasks/missing_links.json) | Trim label, kiểm fallback khi link thiếu; `formatter.py` |

Bundle có `context.json`/`context_manifest.json`/`test_links.json` authoritative;
`repair-context.txt` chỉ tham khảo. M2 validate và render từ DTO thay vì tin
producer text. [inputs_receipt.json](examples/inputs_receipt.json) ghi source M1
run `20261014T072245Z-a8015356523c45cfa264244c07d252b0` và task/source/bundle hashes.
Không chạy lại `prepare_inputs.py` nếu inputs còn đúng; nó không phải lệnh repair.

## 10. Câu hỏi thường gặp và cách tránh hiểu nhầm

**“Run PASS nhưng source trong examples vẫn lỗi?”** Đúng thiết kế: patch áp dụng
trong private worktree rồi cleanup. Đọc `applied.diff` và baseline/post outcomes,
không dùng việc source gốc không đổi làm kết luận model chưa sửa được.

**“Trong báo cáo có FAIL?”** Xem đó là baseline hay final. Required FAIL trước
sửa là điều cần chứng minh; sau sửa phải PASS và regression vẫn PASS.

**“Thông báo nhắc ReadSaved, vậy có chạy thật không?”** Câu cuối script mô tả cả
hai modes. Xem `summary.mode`: Run là generations mới; ReadSaved là hồ sơ cũ.

**“Không thấy patch?”** Có thể stage chưa tới vì input/generation/parser lỗi.
Đọc raw/canonical; đừng tạo hoặc lấy gold patch thế vào để báo PASS.

**“Chạy lâu không thấy text?”** Không có streaming từng token. Đọc pending
canonical/worker receipt nếu cần; không bấm chạy trùng. Nếu bị ngắt, kiểm
process/state trước khi launch mới; không ghi đè output cũ hoặc tự kill process
không xác định.

**“Source/runtime/version mismatch?”** Giữ lỗi và so pin/profile/hashes. Không
đổi tests/config/registry/parser hoặc frozen registration để lách kiểm tra.

**“Cleanup Windows fail?”** Có bounded retry/log cho transient locks; lock kéo
dài vẫn ERROR. Xem [cleanup guide](docs/CLEANUP_WINDOWS_VA_CACH_KIEM_THU.md);
không xóa broad temp directories/tắt bảo vệ Windows để ép thành công.

**“Có thể tích hợp vào VGAR ngay không?”** Có thể bàn giao core/evidence, nhưng
M3 vẫn cần transport/schema/state/adapter review và integrated smoke. Không coi
standalone 3 PASS là MCP acceptance hoặc general security sandbox.

## 11. Bàn giao và các giới hạn còn lại

**M2 có bằng chứng kỹ thuật để bàn giao**: issue → validated M1 context → model
diff → worktree → verification → evidence, với 3 real repairs PASS V11/r002 và lượt người
dùng tự chạy lại.

Cần tách các gate ngoài kết quả đó:

- M1 review provenance/mapping khi nhận bàn giao hoặc khi source/graph thay đổi.
- M3 expose MCP tools, nối LangChain, giữ lease/baseline/state và chạy integration.
- Đồng đội/người nghiệm thu ghi nhận reproduction của họ; một lượt local do
  người dùng chạy không tự ký thay một người khác hoặc chứng minh cross-machine.
- Repository ngoài fixtures, container execution, SWE-bench/held-out/ablation
  hoặc verifier API/architecture tổng quát cần scope/protocol riêng.

Lịch sử triển khai và những cách từng fail vẫn ở
[PROGRESS](PROGRESS.md), [FAILURES](docs/FAILURES.md) và các báo cáo campaign.
Các hướng dẫn/campaign cũ không thay lệnh chạy final V11 trong README này.
Không reset quota hay tái dùng tên campaign để che failures.

**Thực hành khi bàn giao:** giữ nguyên run folder gồm summary/all_logs/canonical/
worker/artifacts; ghi người chạy/ngày/máy/profile. Không cần rerun chỉ để lấy thêm
một PASS. Khi có lỗi mới, lưu evidence và phân loại trước khi sửa, không quy mọi
failure thành lỗi prompt.

## 12. Đọc tiếp

- [Bàn giao M1/M3](docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md).
- [Báo cáo đầy đủ, phần dễ hiểu và chuyên đề V11](docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md).
- [Toàn bộ PowerShell và giải thích từng dòng](docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md).
- [Log diagnostics](docs/LOG_DIAGNOSTICS_VA_CACH_DOC_LOI.md).
- [Báo cáo final A/B/C trước lượt người dùng](docs/NGHIEM_THU_FINAL_A_B_C_V11_R002.md).
- [Reuse M1/VGAR](docs/REUSE_MAP.md).
- [Checkpoint qua các phiên](PROGRESS.md).

Các số liệu trong README lấy từ saved evidence ngày 15/10/2026. Việc viết lại
README không chạy thêm LLM, không sửa source/fixtures/guards/templates, không
install, commit hoặc push.

