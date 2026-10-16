# Tích hợp M2 tuần 7–8 vào VGAR — 16/10/2026

## 1. Phạm vi đã được người dùng xác nhận

Tích hợp đầy đủ M2/A/B/C vào VGAR, giữ thư mục M2 độc lập, chưa nối MCP/LangChain
do M3 phụ trách. Không commit/push, không triển khai SWE-bench hoặc research khác.

```text
CAPSTONES/
├── M2_week_7_8/              BẢN NGUỒN ĐỘC LẬP — không sửa/xóa
└── VGAR/
    ├── src/vgar/            M1/M3 và M2 tuần cũ — giữ nguyên
    ├── run_m2_abc.ps1       launcher mới, mặc định Check
    └── M2_week_7_8/         bản nhúng đầy đủ
        ├── src/vgar_m2_w78/ core repair, parser, worktree, verifier, logs
        ├── examples/       task inputs, source snapshots, M1 handoff bundles
        ├── prompts/        V1–V11 giữ nguyên bytes
        ├── config/         chỉ rebase hai file config path
        ├── tests/          tests/fixtures gốc; conftest trỏ VGAR cha
        ├── docs/           đủ tài liệu bàn giao/báo cáo/hướng dẫn gốc
        ├── results/        toàn bộ lịch sử/evidence đã copy + runs mới tách biệt
        ├── .venv/          bản copy local, không portable/không đưa lên Git
        └── integration/    receipt và byte gốc các file đã rebase
```

Đây là **package integration**, không chỉ shortcut gọi source M2 cũ. CLI/worker,
source fixtures, prompt và outputs thuộc bản nhúng; contracts/consumer/counter
thuộc `VGAR/src/vgar`. Môi trường HF và weights hiện có vẫn là tài nguyên ngoài
package, giống profile trước; không có tải/cài mới.

## 2. Cách giữ đầy đủ nội dung

Trước copy, ghi SHA256, size và đường dẫn tương đối của **mọi file**, kể cả hidden,
venv, caches, temporary workspace leftovers và results. Copy cả các thư mục rỗng.
Đối chiếu toàn bộ file/directory sau copy, trước khi rebase đường dẫn.

Evidence quá trình tích hợp:

- `docs/audit/2026-10-16-m2-w7-w8-integration/before.json`: source inventory,
  dirty VGAR files, Git status/diff/HEAD.
- `.../copy.json`: số file/folder/bytes, thời gian, copy mismatches.
- `.../preservation-<UTC>.json`: kiểm tra nguồn M2 và các file VGAR trước/sau.
- `M2_week_7_8/integration/relocation.json`: danh sách thay đổi paths/hash.
- `M2_week_7_8/integration/originals/`: **byte gốc** sáu file đã chỉnh ở bản nhúng.

Các file generated cũ được giữ để không bỏ sót, không vì vậy trở thành source
cần commit. Chưa push. Không copy đè lại bản nhúng khi đã có runs mới; xem receipt
và status trước bất kỳ lần đồng bộ tiếp theo nào.

## 3. Những gì thay đổi và không thay đổi

| File ở bản nhúng | Thay đổi | Vì sao |
|---|---|---|
| `config/source_pin.json` | reference root trỏ VGAR cha | M2 không còn là sibling của VGAR |
| `config/demo.json` | rebasing snapshot/interpreter/tokenizer paths | Vẫn cùng Qwen/SHA/assets/model config, không đổi budgets |
| `pyproject.toml` | pytest thêm `../src` | Shared VGAR source đúng checkout |
| `tests/conftest.py` | VGAR là parent của package nhúng | Core tests dùng đúng M1 fixture/handoff |
| `test_abc_v11_r002.ps1` | explicit relocation hashes + historical comparison trong bộ nhớ + ID mới | Không bỏ runtime guard hoặc sửa frozen r002 |
| `src/vgar_m2_w78/b_inputs.py` | Adapter chỉ cho phép đúng ba before/after hash pairs của config/conftest đã rebase | Full suite phát hiện freezer lịch sử từ chối path relocation; vẫn từ chối mọi bytes ngoài allowlist và đòi backup gốc khớp |

Các thuật toán repair/parser/worktree/verifier, scripts, templates, fixtures,
reference patches, canonical records và frozen manifests không đổi. Chỉ helper
freeze-input `b_inputs.py` cần adapter layout có regression tests. Bản gốc sáu file trên cũng
được lưu; bản M2 độc lập không thay đổi bất kỳ file nào.

**Định danh mới:** `r002-vgar-i001` = repair core r002 + layout/config relocation + freeze-input adapter được
ghi nhận. Không được gọi toàn bộ fingerprint layout mới là r002 byte-identical.
Old evidence tiếp tục có historical paths và hashes; ReadSaved chỉ rebase task
paths **khi so sánh trong bộ nhớ**, không ghi ngược lại JSON/bundle cũ.

M3 agent/settings/CLI cũ không bị thay thế. `mcp_calls=[]` của standalone vẫn
nghĩa là chưa chạy MCP, không phải “đã tích hợp MCP”. API/structural verifier
NOT_RUN vẫn NOT_RUN, không chuyển thành PASS.

## 4. Input → xử lý → output

1. Launcher định vị package bằng `$PSScriptRoot`, không phụ thuộc cwd.
2. Runner kiểm Python pins, fingerprint (hai config delta + một freeze-input adapter đã khóa hash),
   V11 hash, trusted fixtures, reference HEAD/12 shared boundary hashes.
3. Input tasks: `VGAR/M2_week_7_8/examples/tasks/<case>.json`; source ở
   `examples/snapshots/<case>`, context/manifest/test links ở `examples/handoffs/<case>`.
4. Run: tự kiểm full M2 suite/Ruff → private baseline/worktree → V11 → một HF
   generation → strict parse/exact bind/Git apply/attestation → collection,
   required/regression tests, syntax/mypy/Ruff → cleanup/integrity → audit.
5. A sửa `auth.py`; B phải sửa cả `pricing.py`/`invoice.py`; C sửa `formatter.py`
   với actual fallback collection/execution. Source snapshots gốc vẫn có bug là
   đúng thiết kế: code sửa nằm ở worktree/artifact, không ở original snapshots.
6. Output mới: `VGAR/M2_week_7_8/results/manual_abc/<run-id>/` tự sinh. Đọc
   `summary.json`, `all_logs.txt`, `preflight.json`, `audit_A/B/C.json`, command
   receipts/logs và `<A|B|C>/<canonical-id>/run_record.json`.
7. Canonical có prompt/raw/candidate/applied diff/bundle, commands/stdout/stderr,
   exit codes, UTC start/end + durations, parser diagnostics/tracebacks,
   tokens/effective generation config/mask/placement, cleanup và integrity.
   HF worker logs nằm dưới `<case>/model-workers/`. Check không tạo các artifacts
   repair này; ReadSaved đọc historical artifacts, không generation.

## 5. Chạy từ đầu đến cuối bằng PowerShell

### 5.1. Máy hiện tại — không cài lại

```powershell
# Vào repository tích hợp; không vào thư mục M2 độc lập.
Set-Location 'D:\Project\CAPSTONES\VGAR'

# Kiểm prerequisite/profile, KHÔNG load weights hoặc sinh patch.
powershell -NoProfile -ExecutionPolicy Bypass -File '.\run_m2_abc.ps1' -Mode Check
if ($LASTEXITCODE -ne 0) { throw 'Check fail; xem logs, không tự đổi profile.' }

# Xem/audit lại ba real records đã copy, không tiêu tốn lượt generation mới.
powershell -NoProfile -ExecutionPolicy Bypass -File '.\run_m2_abc.ps1' -Mode ReadSaved
if ($LASTEXITCODE -ne 0) { throw 'Saved evidence audit fail.' }

# CHỈ chạy dòng sau khi muốn tạo một lượt A/B/C MỚI thật sự.
powershell -NoProfile -ExecutionPolicy Bypass -File '.\run_m2_abc.ps1' -Mode Run
$runExit = $LASTEXITCODE
Write-Host "A/B/C exit code: $runExit"
```

Một lệnh duy nhất nếu đã sẵn sàng chạy mới:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'D:\Project\CAPSTONES\VGAR\run_m2_abc.ps1' -Mode Run
```

Run vẫn có thể FAIL trên model/environment; không retry tự động hoặc sửa diff
cho PASS. Giữ full self-tests, không khuyến nghị `-SkipSelfTests` cho nghiệm thu.
Exit0 của Check chỉ nghĩa prerequisite PASS; exit0 của ReadSaved chỉ re-audit;
exit0 của Run mới là ba real generations trong workflow này đã qua audit.

### 5.2. Máy khác/clean clone — setup một lần

Không copy venv local sang máy khác làm “cài đặt”. Tạo core Python3.11 venv trong
package nhúng, cài `M2_week_7_8/requirement.txt`; HF environment riêng theo comments
trong file đó. Provision pinned Qwen revision/local tokenizer assets và kiểm12
shared files bằng source pin. Không trộn tokenizers core0.22.1 với HF0.22.2.

Venv copy có editable `.pth` lịch sử trỏ bản M2 độc lập. Các launcher/scripts
được hỗ trợ chủ động prepend source nhúng, nên không dùng source cũ. Không chạy
bare `python -c "import vgar_m2_w78"` rồi suy ra đó là source nhúng, và không
dùng console entrypoint cũ của venv copy. Dùng `run_m2_abc.ps1` hoặc
`M2_week_7_8/scripts/run_demo.py` theo hướng dẫn; chưa nghiệm thu import/install
workflow khác, không tự cài lại môi trường hiện tại để “sửa” `.pth`.

Profile hiện dùng HF interpreter trong `../vgar_mcp_mvp/.venv` chỉ như nơi đặt
dependencies, không import old system source. Nếu đổi path/máy/env, phải lập
relocation/profile receipt mới và qualification riêng, không sửa config rồi
giả hash cũ còn hợp lệ. Source pin hiện còn khóa HEAD; commit mới trong VGAR
sẽ cần requalification, không bỏ guard để chạy qua.

### 5.3. Đọc run mới mà không nhập folder thủ công

```powershell
$resultsRoot = Join-Path $PWD 'M2_week_7_8\results\manual_abc'
# Chỉ chọn Run mới của bản tích hợp; không nhầm Check/ReadSaved hoặc historical Run đã copy.
$candidates = @(Get-ChildItem -LiteralPath $resultsRoot -Filter summary.json -Recurse -File |
    ForEach-Object { $s = Get-Content -Raw -Encoding UTF8 $_.FullName | ConvertFrom-Json; if ($s.mode -eq 'Run' -and $s.PSObject.Properties['integration_id'] -and $s.integration_id -eq 'r002-vgar-i001') { [pscustomobject]@{Path=$_.FullName; Summary=$s; Started=$s.started_utc} } })
$selected = $candidates | Sort-Object Started -Descending | Select-Object -First 1
if (-not $selected) { throw 'Chưa có Run mới của bản tích hợp; không coi ReadSaved/historical Run là lượt chạy mới.' }
$selected.Summary | Select-Object status,complete,mode,started_utc,ended_utc,reason
$selected.Summary.cases | Select-Object letter,task_id,status,input_tokens,output_tokens,duration_ms
Get-Content -Encoding UTF8 (Join-Path (Split-Path $selected.Path -Parent) 'all_logs.txt')
```

## 6. Kiểm thử tích hợp và trạng thái nghiệm thu

**Đã hoàn thành tích hợp package theo phạm vi được duyệt.** Không tuyên bố toàn
VGAR hết lỗi hoặc đã nối agent/MCP. Bằng chứng ngày16/10/2026:

| Kiểm tra | Kết quả thực tế | Evidence |
|---|---|---|
| Copy toàn bộ source M2 | PASS: **13.071 files, 5.252 directories, 203.602.347 bytes**, zero mismatches | audit `copy.json` |
| Full suite M2 bản nhúng | **236 PASS**, 129,27s pytest /130,016s recorder | `M2_week_7_8/results/integration-qualification/final-core-suite/20261016T070502676971Z-3cde4ebc98db/run_record.json` |
| Regression launcher/auditor | **7 PASS**,8,98s; gồm explicit relative paths và tamper rejection | audit command `20261016T071003225820Z-424ac56f6133/result.json` |
| Check profile | PASS,5,370s; CUDA True/RTX4050; không load weights/generate | audit command `20261016T070621462828Z-dd0d36d6e606/result.json` |
| ReadSaved A/B/C | **3/3 historical real records audit PASS**; absolute và relative paths đều được test | `M2_week_7_8/results/integration-tests/<run-id>/{summary,preflight,audit_A,audit_B,audit_C}.json` |
| Fake pipeline A | PASS;1requiredFAIL→PASS và regressionPASS; post2PASS | `.../fake-abc/single_file_login/20261016T070729727952Z-818cb8ed7c51/run_record.json` |
| Fake pipeline B | PASS;2requiredFAIL→PASS, regressionPASS; post3PASS; actual2productionfiles | `.../fake-abc/multi_file_invoice/20261016T070738974290Z-9b739565f2e2/run_record.json` |
| Fake pipeline C | PASS; requiredFAIL→PASS, regressionPASS; post2PASS; collection/fallback thật | `.../fake-abc/missing_links/20261016T070748123490Z-157b23081364/run_record.json` |
| Ruff E9,F + PowerShell AST + diff whitespace | PASS | audit command `20261016T071231030790Z-8adba3d79c5c/result.json`; static checks được ghi riêng |
| Full VGAR sau fix review | **571 PASS,2SKIP,1FAIL**,81,14s; FAIL là lỗi HF đã tái hiện trước tích hợp | audit command `20261016T071014208534Z-364e407364e4/result.json`, `final-vgar-suite.xml` |
| Nguồn M2/dirty VGAR/historical bytes trước-sau | **PASS**, zero changed/missing/added source files; zero protected VGAR changes | `preservation-20261016T071223180685Z.json` |

Các paths `audit command` ở trên tương đối với
`docs/audit/2026-10-16-m2-w7-w8-integration/commands/`.
`.../fake-abc` là `M2_week_7_8/results/integration-qualification/fake-abc`.
Không cộng số tests ở các hàng thành một suite; các lượt có giao nhau.

### 6.1. Hai lỗi tích hợp đã phát hiện và sửa

1. **Freezer lịch sử không biết layout mới:** first full suite233PASS/1FAIL,
   134,53s, từ chối `tests/conftest.py`. Adapter có ba before/after hash pairs,
   backup gốc bắt buộc; RED2→GREEN5→full236PASS. Không sửa old baseline/history.
2. **Explicit relative paths đổi nghĩa sau chdir:** reviewer phát hiện; test
   tái hiện exit2 trước fix, launcher normalize theo caller location; GREEN7.
   Không giải quyết bằng đổi đường dẫn người dùng trong saved evidence.

Initial RED/full failures được giữ dưới `results/integration-qualification/`
và audit commands, không xóa hoặc đổi thành PASS. Các draft integration receipt
được giữ riêng; final relocation receipt mô tả đủ sáu file thực sự thay đổi.

### 6.2. Lỗi VGAR cũ còn nguyên, không phải regression M2

`tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config`
FAIL `KeyError: generation_config` tại dòng53. Đã tái hiện trước khi rebase M2:
command `20261016T030156219054Z-cafc0c55c9eb`,1FAIL/58,63s. Full sau tích hợp
và full sau review vẫn chỉ có đúng failure này. Nó thuộc backend HF của agent
VGAR cũ, không phải HF worker của package M2 mới; không sửa trong phạm vi này.

Hai skips của full VGAR là optional/platform gates; xem JUnit để biết test IDs.
Không gọi full VGAR “PASS” hoặc suy ra toàn hệ thống sẵn sàng vì M2 đạt236PASS.

Root tests làm thay bytes SQLite fixture `artifacts/sample_graph.db`. Đã lưu
`sample_graph-after-tests.db` và khôi phục **chỉ side effect của tests phiên này**
từ backup trước test, không reset Git hoặc source của thành viên. Receipt:
`sqlite-preservation.json`. Hai dirty retrieval files và mọi pre-existing
untracked content được đối chiếu hash, không bị ghi đè.

### 6.3. Việc chưa chạy/chưa thuộc phạm vi

- **Không chạy ba generation mới sau relocation.** Check/ReadSaved/fake không
  thay thế nghiệm thu real của bản layout mới. Dùng `-Mode Run` để tạo evidence
  mới nếu muốn; không hứa model luôn PASS vì historical runs đã PASS.
- Không nối MCP/LangChain, không dùng arbitrary untrusted repository, không
  đóng gate đồng đội/M1/M3 thay họ. Native vẫn chỉ ba trusted byte-locked fixtures.
- Không cài lại dependencies, tải weights hoặc provision môi trường portable.
- Không commit/push; branch/HEAD vẫn như trước. Commit mới cần requalify source
  pin HEAD, không bỏ kiểm tra để chạy qua.

### 6.4. Tự kiểm tra bảo toàn sau này

```powershell
# Chỉ đọc source/M2/VGAR theo manifest; tạo preservation receipt mới, không copy đè.
python -B '.\scripts\check_m2_integration.py' --stage final
```

Lệnh phải chạy từ VGAR; Python3.11+. Sau khi chủ ý sửa code/config/history, một
FAIL có thể là drift cần review chứ không tự cập nhật expected hashes để PASS.
Không chạy lại `--stage copy`: copy.json là receipt bất biến đã có; auditor từ
chối ghi đè. Final auditor đọc song song tối đa8files,6,375s ở lần nghiệm thu;
lần serial đầu236,828s được giữ nguyên, không chỉnh số thời gian lịch sử.

Historical real A/B/C V11/r002 đều PASS; kết quả baseline FAIL → post PASS là
điều cần đạt, không phải thất bại final. Việc chép lại evidence không phải
generation mới, cũng không phải teammate độc lập hoặc nghiệm thu MCP của M3.

## 7. Các tài liệu M2 được giữ nguyên

- `M2_week_7_8/docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md`.
- `M2_week_7_8/docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md` — bao gồm giải thích V11 và file inventory lịch sử.
- `M2_week_7_8/docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md` — commands lịch sử;
  với layout mới, ưu tiên launcher/hướng dẫn ở file này.
- `M2_week_7_8/requirement.txt`, README/PROGRESS gốc, tất cả plans và evidence.

Không sửa tài liệu lịch sử để che giấu failures hoặc làm chúng có vẻ được tạo
trong VGAR. Hướng dẫn tích hợp này giải thích delta thay vì viết lại quá khứ.
