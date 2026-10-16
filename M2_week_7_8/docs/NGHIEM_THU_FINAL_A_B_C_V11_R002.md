# Nghiệm thu A/B/C cùng final prompt V11 và runtime r002

**Trạng thái cuối: HOÀN THÀNH — 3/3 PASS**, combined audit PASS ngày 15/10/2026.
Không còn case pending; không cần chạy thêm model. Ba runs đều mới, không feedback.

## Mục tiêu và protocol

Người dùng yêu cầu hoàn tất gate chung A/B/C sau khi B tuning đã PASS. Thực hiện
**ba runs mới**, tuần tự A → B → C, một generation/case, **không feedback**, giữ
nguyên V11 và core r002 cho cả ba. Không ghép A/V4, C/V9 hoặc B/V11 tuning cũ
thành nghiệm thu final. Không mở lại/reset quota campaigns cũ.

Đây là nghiệm thu **development fixtures**, không held-out benchmark, không
xác nhận độc lập của đồng đội và không phải tích hợp MCP của M3.

## Những gì được giữ nguyên

- Qwen/Qwen3-4B-Instruct-2507 @ `cdbee75f17c01a7cc42f958dc650907174af0554`.
- Greedy (`do_sample=false`), FP16, `device_map=auto` có CPU offload.
- Input 6.000, output 1.536, reserve 256 tokens; generation 900s, command 120s,
  global pipeline 1.800s/run. Phiên này tối đa ba runs, không auto-retry.
- Parser, exact bind/apply, verifier, tests/config/source fixtures, gold và M1/M3
  không sửa. Không viết/sửa diff hộ model, không nới acceptance.
- Core `src/scripts/config` khớp runtime r002 đã qualified **234 tests PASS**;
  trước/sau inference kiểm lại fingerprints, không triển khai lại core.
- Template `prompts/repair_v11.txt` SHA:
  `ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8`.

“Cùng prompt” nghĩa là **cùng template/version/hash và cách trình bày context**.
Full rendered prompt/input tokens khác nhau vì issue và context của A/B/C khác
nhau; không tuyên bố ba full-input hashes phải giống nhau.

## Cách thực hiện

Dùng CLI sẵn có `scripts/run_demo.py`, không thêm controller hoặc sửa code runtime.
Profile riêng nằm trong results để không đổi `config/demo.json` hay fingerprints
của r002. Một operator reservation trong `run_manifest.json` được ghi trước mỗi
launch; interruption phải kiểm tra process/canonical, không chạy lại tự động.

```powershell
# Thiết lập mỗi terminal mới; không cài lại dependencies hay tải weights.
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$finalRoot = Join-Path (Get-Location) 'results\final_acceptance\2026-10-15-v11-r002'
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $finalRoot 'temp'
$env:TMP = $env:TEMP
```

Các command đã dùng (để truy vết, không chạy lặp lại case đã reserved/terminal):

```powershell
# A — login; không dùng --mode fake.
& $python '.\scripts\run_demo.py' --mode real --task '.\examples\tasks\single_file_login.json' --config (Join-Path $finalRoot 'final_profile.json') --output-root (Join-Path $finalRoot 'A')
# B — hai file production.
& $python '.\scripts\run_demo.py' --mode real --task '.\examples\tasks\multi_file_invoice.json' --config (Join-Path $finalRoot 'final_profile.json') --output-root (Join-Path $finalRoot 'B')
# C — thiếu test links, phải collection/fallback thật.
& $python '.\scripts\run_demo.py' --mode real --task '.\examples\tasks\missing_links.json' --config (Join-Path $finalRoot 'final_profile.json') --output-root (Join-Path $finalRoot 'C')
```

Không gọi qualifier OK, không dùng previous failure feedback. CLI không được
coi là quota controller; operator reservations/unique output roots và checkpoint
ngăn khởi chạy trùng. Nếu một case FAIL/ERROR, dừng chẩn đoán và không đổi template
giữa bộ final này. Không tuyên bố PASS chỉ từ exit code.

## Audit và evidence

Thư mục phiên: `results/final_acceptance/2026-10-15-v11-r002/`.

| Thành phần | Nội dung |
|---|---|
| `final_profile.json` | Model/policy giống nhau cho cả ba, paths môi trường hiện tại |
| `run_manifest.json` | Reservations, trạng thái, canonical references; không chứa kết quả cũ được gộp |
| `frozen_final.json` | Hash core r002, protected inputs/history/assets, profile và audit job |
| `A/`, `B/`, `C/` | Mỗi case đúng một canonical folder mới + model-worker request/response/diagnostics |
| `<case>/<run>/run_record.json` | Stages, command/stdout/stderr/exit, times, baseline/post, token/placement, cleanup/integrity |
| `<case>/<run>/prompt.txt`, `raw_model_output.txt` | Full prompt và output model nguyên bản |
| `<case>/<run>/candidate.diff`, `applied.diff` | Candidate nguyên bản và Git export của patch thực sự áp dụng |
| `<case>/<run>/evidence_bundle.json` | Public verification và hash binding về canonical |
| `audits/<audit>/run_record.json` | Preflight/partial/final audit riêng; partial PASS không phải 3/3 PASS |

Audit job ở `.superpowers/sdd/2026-10-15-final-abc-v11-r002/audit_final.py` chỉ đọc
records và sinh audit evidence; **không launch model, không sửa canonical/raw**.
Nó dùng core `assess_record` giữ nguyên và thêm kiểm model/policy/task/template,
feedback=None, prompt/raw/candidate/input hash, actual diagnostics/mask, core
source fingerprint, protected inputs, signatures, baseline required FAIL và cleanup.
Core audit kiểm actual changed files, collection/required/regression/static,
Git export, EvidenceBundle/canonical hash. Với C, fallback thực thi phải có evidence.

## Kết quả hiện tại

| Case | Task | Trạng thái | Input/output | Pipeline/gen |
|---|---|---|---|---|
| A | `single_file_login` | PASS, partial audit PASS | 1.299 / 43 tokens | 68,828s / 53,250s |
| B | `multi_file_invoice` | PASS, partial + combined audit PASS | 1.769 / 157 tokens | 157,282s / 142,406s |
| C | `missing_links` | PASS, combined audit PASS | 1.169 / 43 tokens | 64,031s / 51,250s |

A: `A/20261015T072711985584Z-dc47a96417ee/run_record.json`;
audit `audits/20261015T072910452391Z-6bc45ef93046/run_record.json`.
B: `B/20261015T072938917449Z-a0075c35e2ee/run_record.json`;
partial audit `audits/20261015T073226931714Z-986411624f02/run_record.json`.
C: `C/20261015T073254806383Z-68a9a593f8d6/run_record.json`.
**Combined audit cả ba:**
`audits/20261015T073438247626Z-8ce2a58ef084/run_record.json` — PASS,
`scope="3/3 final acceptance"`, gate errors rỗng cho A/B/C.

| Verification thực tế | A | B | C |
|---|---|---|---|
| Required baseline FAIL → post PASS | 1 test | 2 tests | 1 test |
| Regression baseline/post | 1 PASS → PASS | 1 PASS → PASS | 1 PASS → PASS |
| Production files thực sự thay đổi | `auth.py` | `invoice.py`, `pricing.py` | `formatter.py` |
| Parser/exact bind/Git apply/attestation | PASS | PASS | PASS |
| Collection/post tests | PASS | PASS | PASS; fallback `tests`, reason `unlinked` |
| Syntax/mypy/Ruff/signatures | PASS | PASS | PASS |
| Cleanup/source integrity/bundle binding | PASS | PASS | PASS |
| Actual diagnostics/config/mask/placement | PASS | PASS | PASS |
| Core fingerprint/template/model/policy | V11/r002 pin | V11/r002 pin | V11/r002 pin |

Patch A đổi kiểm tra truthiness sang kiểm tra giá trị sau trim, B đổi flat discount/
tax sang phép tính phần trăm, C trim label. Đó là code do model sinh; host không
viết/correct/count lại patch. Chỉ worktrees được sửa, fixtures gốc giữ nguyên.

Tổng ba canonical pipelines **290,141s (~4 phút 50 giây)**; riêng generation
**246,906s (~4 phút 7 giây)**. Tổng generation input **4.237**, output **243 tokens**.
Đây là tổng duration trong canonical records, không phải wall-clock của toàn phiên
có đọc log/audit/soạn tài liệu. Offline engineering/observations không tính vào đó.
Không dùng API trả phí; điện/compute local không được gọi là miễn phí hoặc gán giá
khi chưa đo. Phần lớn model có thể offload CPU, không mô tả chạy toàn GPU.

Không thay production runtime nên không chạy lại một full suite giống hệt chỉ
để lấy số mới: preflight và audit kiểm current code/canonical source fingerprints
khớp chính xác qualification r002 **234 PASS**, giữ nguyên hashes của tests cũ.

### Những gì đã đóng / chưa đóng

- Đã đóng gate **A/B/C cùng final template V11 và core runtime r002**, no feedback,
  ba runs mới, 3/3 verification PASS và original-source unchanged.
- Chưa có teammate chạy lại độc lập; không tự ký thay người khác.
- Chưa nghiệm thu tích hợp MCP/LangChain của M3/VGAR; standalone không tự thành MCP.
- Không có kết quả SWE-bench/held-out hoặc claim resolved rate ngoài ba fixtures.
- `config/demo.json` **vẫn V2** để giữ qualified runtime/historical hashes. Muốn
  dùng profile final phải truyền `--config .../final_profile.json` rõ ràng. Không
  chạy bare default rồi cho rằng đó là V11.

## Đọc output không nhập tên run thủ công

```powershell
# CHỈ ĐỌC: chọn case A/B/C, canonical path lấy từ manifest.
$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $finalRoot 'run_manifest.json') | ConvertFrom-Json
$manifest.cases | ConvertTo-Json -Depth 8
$caseLetter = 'B'
$entry = $manifest.cases.PSObject.Properties[$caseLetter].Value
if (-not $entry.record) { throw 'Case chưa có canonical path.' }
$recordPath = Join-Path $finalRoot $entry.record
$record = Get-Content -Raw -Encoding UTF8 $recordPath | ConvertFrom-Json
$record | Select-Object task_id,status,complete,reason,duration_ms,original_source_unchanged
$record.stages.verification | ConvertTo-Json -Depth 25
$record.stages.generation | ConvertTo-Json -Depth 25
$directory = Split-Path -Parent $recordPath
if ($record.artifacts.applied) { Get-Content -Raw -Encoding UTF8 (Join-Path $directory $record.artifacts.applied) }
if ($record.artifacts.bundle) { Get-Content -Raw -Encoding UTF8 (Join-Path $directory $record.artifacts.bundle) }
```

Fixture gốc vẫn cố ý chứa lỗi. Model sửa trong worktree riêng; xem `applied.diff`
để thấy thay đổi. Không copy patch ngược vào fixture rồi làm mất baseline.
