# Giải thích M2 tuần 7–8 và cách tự kiểm thử

**Cập nhật mới nhất 15/10/2026:** final A/B/C đã chạy mới, không feedback và
**3/3 PASS cùng template V11/core runtime r002**, source gốc không đổi. Đọc
[báo cáo/hướng dẫn final](NGHIEM_THU_FINAL_A_B_C_V11_R002.md) trước khi dùng các
lệnh profile/campaign lịch sử trong tài liệu này. Core hiện tại khớp qualification
234 tests PASS. `config/demo.json` vẫn V2; dùng final_profile.json phải có --config.
Không coi standalone final3 là M3 MCP integration hoặc teammate reproduction.

Ngày thực hiện: 14/10/2026. Thư mục triển khai: `D:\Project\CAPSTONES\M2_week_7_8`.

## 1. Task này yêu cầu gì?

M2 tuần 7–8 xây **repair pipeline và verification cơ bản**: nhận mô tả lỗi và
context của M1, cho một mô hình sinh một unified diff, kiểm tra patch, áp vào bản
copy riêng, chạy kiểm thử và lưu bằng chứng. Đây không phải fine-tuning hoặc
benchmark SWE-bench. Chưa phải toàn hệ thống LangGraph/MCP của M3.

Bảy nội dung chính là: prompt sửa lỗi cố định; backend LLM cố định; parser unified
diff; apply vào worktree; chọn relevant tests; pytest/typecheck/lint; EvidenceBundle.
Plan chính: `New_task/2026-10-13-m2-w7-w8-brainstorm-implementation-plan.md`.
Scope dựa trên tuần 7–8 của `New_task/project_plan_16_weeks.md`, không triển khai
plan P0–P5 đang đóng băng.

### 1.1. Kết quả thực tế — không nhầm engine PASS với LLM PASS

**Đã có engine chạy end-to-end bằng patch tham chiếu ở chế độ fake. Chưa nghiệm thu
repair LLM thật trên ba case.** Một lần gọi model trả `OK` chỉ xác nhận inference
hoạt động, không chứng minh model sửa được code.

| Gate | Trạng thái | Ý nghĩa |
|---|---|---|
| M1 handoff/source validation | Đã có và dùng trong pipeline | Context phải khớp task/repo/revision/graph/source/tokenizer |
| Core offline tests | Có evidence riêng mỗi lần | Test engine và các trường hợp lỗi, không dùng model thật |
| Fake demo ba fixture | Ba case PASS ở lượt đầu | Patch mẫu qua parser/apply/pytest/mypy/Ruff; không tính là model success |
| Real invocation Qwen3-4B | PASS | Model pinned trả `OK`; ~35 giây; không phải repair |
| Real repair A v1 | FAIL | Model trả SEARCH/REPLACE, parser từ chối |
| Real repair A v2 | FAIL | Model trả diff nhưng số dòng hunk sai; parser từ chối |
| Real repair B/C | Chưa chạy | Dừng phương pháp sau hai failure, không đốt thêm inference |
| ≥3 real valid diff + verification | Chưa đạt | Không dùng fake thay bằng chứng LLM |
| MCP/M3 integration và đồng đội chạy lại | Chưa nghiệm thu | Service độc lập sẵn để bàn giao; không ký thay M3/người dùng |

Vì vậy không thể gọi task hoàn thành 100% theo gate demo thật của plan. Blocker
hiện quan sát được là **format model**, không phải CUDA thiếu hoặc pytest lỗi.
Không kết luận model không bao giờ sửa được; chỉ kết luận hai lượt đã chạy không
đạt. Không chuyển SEARCH/REPLACE sang diff hoặc tự sửa `@@` để làm đẹp kết quả.

## 2. M2 dựa vào M1 và M3 như thế nào?

M1 reference nằm ở `D:\Project\CAPSTONES\VGAR`, commit
`b8e2461635b81d1ae790445efea5c9757d91700a`. M2 chỉ đọc, không sửa repo này.

M2 tái sử dụng `vgar.contracts.consumer.receive_context_handoff` để kiểm bundle
và render context, `diagnose_changed_paths` để tìm test hints từ các file thực tế
bị patch thay đổi, `vgar.graph.token_counter.LocalTokenizerCounter` để đếm snippet,
và DTO public trong `contracts/repair.py`, `contracts/evidence.py`.

Không viết lại graph builder/ranking của M1. Không coi test links là bằng chứng
coverage: chúng chỉ là **candidate**; M2 phải collection và chạy pytest thật.
M3 có thể bọc Python service thành MCP tool sau khi owner duyệt. Phiên này không
chạy MCP, không sửa tool schema và không chạy agent LangGraph. `mcp_calls=[]`
trong JSON nghĩa **MCP không được thực thi**, không phải bị thiếu log.

## 3. Input nằm ở đâu, chứa gì?

Mỗi case có ba loại input, tất cả dưới `D:\Project\CAPSTONES\M2_week_7_8`:

| Input | Đường dẫn tương đối | Nội dung / tác dụng |
|---|---|---|
| Task | `examples/tasks/<case>.json` | Issue, task ID, repo key, revision, graph version, source/bundle paths, failing selectors, fallback scope, file được sửa |
| Source gốc | `examples/snapshots/<case>/` | Repo nhỏ đang có lỗi; chỉ đọc, không sửa trực tiếp |
| M1 bundle | `examples/handoffs/<case>/` | `context.json`, `manifest.json`, `test_links.json`; producer text chỉ tham khảo, consumer render lại |
| Receipt | `examples/inputs_receipt.json` | Source M1/export provenance và byte hashes lúc chuẩn bị input |
| Source pin | `config/source_pin.json` | Commit reference và hashes của shared modules được phép import |
| Native registry | `config/trusted_fixtures.json` | Byte hashes và allowlist của đúng ba fixture; task tự ghi `trusted=true` vẫn không đủ để qua guard |
| Policy/model | `config/demo.json` | Budgets, timeout, fixed prompt version, model/SHA, cached snapshot, interpreter, tokenizer manifest |
| Fixed prompt | `prompts/repair_v1.txt`, `repair_v2.txt` | Instruction format; version/hash được ghi mỗi run; v2 chỉ thay instruction sau v1 failure |

Các đường dẫn tương đối trong task được resolve từ **thư mục chứa task JSON**,
không từ thư mục source. Thay issue/source/bundle không đúng pin có thể bị từ chối;
đó là guard, không sửa hashes để bỏ qua.

Ba case hiện có:

| Case | Source / lỗi | Required test và file được sửa |
|---|---|---|
| `single_file_login` | `auth.py`: login chấp nhận tên toàn khoảng trắng | `tests/test_auth.py::test_login_rejects_whitespace`; allow `auth.py` |
| `multi_file_invoice` | `pricing.py` dùng phần trăm discount như số tiền; `invoice.py` cộng phần trăm tax như số tiền | Hai tests discount/tax trong `tests/test_invoice.py`; allow hai file nguồn |
| `missing_links` | `formatter.py`: label chưa trim; liên kết test gián tiếp/dynamic thiếu | `tests/test_formatter.py::test_label_trim`; allow `formatter.py`; fallback scope `tests` |

`tests/fixtures/reference_patches/<case>.diff` là input **chỉ cho FakeGenerator**
để kiểm engine. Real mode không đọc các patch này. Không đưa chúng vào context.

## 4. Flow từ đầu đến cuối

```text
Task JSON + original snapshot + M1 bundle + fixed policy
                 │
                 ▼
Source pin + trusted bytes + M1 consumer validation
                 │ sai → ERROR, không gọi model
                 ▼
Copy byte-identical → private seed Git → detached worktree
                 ▼
Baseline: collect IDs → pytest → syntax/mypy/Ruff
                 │ phải tái hiện assertion FAIL của required test
                 ▼
Fixed prompt: issue + failed IDs + validated M1 context
                 ▼
Đếm toàn chat prompt → một generation (real hoặc explicit fake)
                 ▼
Lưu raw → strict unified diff parser → all-file preflight
                 │ sai format/count/path → FAIL, không apply/verify
                 ▼
Git --check --index → apply --index → byte attestation + applied.diff
                 ▼
Actual changed paths → M1 hints → collection → fallback nếu cần
                 ▼
Post pytest + required FAIL→PASS + regression PASS→PASS
       + syntax + mypy + Ruff + protected/original guards
                 ▼
EvidenceBundle + cleanup → terminal JSON/REPORT
```

### 4.1. Source/worktree và apply

`src/vgar_m2_w78/workspace.py` copy source vào private seed rồi tạo detached
worktree bên trong `.workspaces/m2-w78-<random>/`. Nó **không dùng** `git worktree add`
trên `.git` của VGAR/source gốc. Seed commit là dữ liệu runtime riêng, không phải
commit project/GitHub. Native chạy trong worktree, không chạy ở source.

`patch.py` nhận unified diff: header `--- a/path`, `+++ b/path`, `@@ -old,count
+new,count @@`; dòng space là context, `-` là bỏ, `+` là thêm. Count phải đúng,
context/removal phải khớp source; mọi file phải trong allowlist. Không chấp nhận
rename/add/delete/binary/path traversal hoặc fuzzy apply trong profile này.
Một file thứ hai sai thì preflight chặn cả candidate, không áp một phần.

Raw model được giữ nguyên. `transport.diff` chỉ bind LF/CRLF với newline của source
để Git không đổi byte ngoài ý muốn, không sửa nội dung/counts. Git apply dùng
`--check --index` trước rồi `--index`; không dùng `--reject`, `--recount`, `--3way`,
`--ignore-whitespace`. Sau apply còn đối chiếu bytes với predicted result.

Mặc định worktree bị dọn sau run; patch/evidence vẫn tồn tại. `--keep-workspace`
chỉ dành debug, có lưu path trong stage workspace. Đừng nhầm source không đổi là
repair thất bại: repair phải diễn ra trong worktree và được ghi `applied.diff`.

### 4.2. Baseline và post verification

Baseline là kết quả **trước patch**. Gate baseline PASS nghĩa môi trường phù hợp
và lỗi được tái hiện: ít nhất một required assertion FAIL, không phải source đã
hết lỗi. Vì vậy baseline stage PASS có thể chứa `tests.status=FAIL` — đây là đúng.

Collection lấy exact pytest node IDs, ví dụ `tests/test_auth.py::test_login_rejects_whitespace`.
Sau patch required phải PASS; các test baseline PASS phải tiếp tục PASS. Test
missing/skip/xfail/incomplete không tính đã sửa. Zero tests hoặc all skip là ERROR.
Mapping M1 thiếu/limited/unlinked sẽ dùng scope `tests` đã duyệt. Ba fixture nhỏ
luôn chạy full regression scope, không suy ra coverage từ static test links.

Syntax dùng `ast.parse`; mypy dùng config cố định với `check_untyped_defs`; Ruff
dùng E9/F và không auto-fix. Đây là kiểm cơ bản, không phải proof mọi semantics.
API/structural checks public giữ NOT_RUN vì không triển khai ở scope này.

### 4.3. Model/runtime, input/output tokens và thời gian

Real worker dùng `Qwen/Qwen3-4B-Instruct-2507` ở revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, greedy `do_sample=False`, FP16,
`device_map=auto`. Worker không tự tải weights, không fallback CPU/fake khi lỗi.
Máy hiện tại dùng RTX4050; một số layers trên CPU do hạn chế bộ nhớ. Đây là
**prototype riêng**, không Qwen32B/vLLM hoặc kết quả benchmark.

Core venv không chứa Torch. Worker dùng interpreter đã có ở
`D:\Project\CAPSTONES\vgar_mcp_mvp\.venv\Scripts\python.exe`; chỉ tái sử dụng
libraries/interpreter, không import hoặc sửa source hệ thống cũ.

Input gồm system instruction + host path policy + issue + failed test IDs +
validated context, sau đó chat template của tokenizer. M1 đếm snippet; M2 đếm
**toàn bộ chat prompt** để tránh nhầm hai budgets. Policy hiện input6000,
output1536, reserve256; command120s, generation900s, global1800s. Deadline giới
hạn các subprocess và chặn stage/generation khi đã hết; cleanup/evidence an toàn
vẫn phải thực hiện và có thể thêm chút thời gian ngoài compute budget.

Thời gian bao gồm: copy/hash/Git setup, baseline pytest/static, tokenization,
load weights/offload CPU, generation, apply/post tests, cleanup/evidence.
UTC start/end cho mốc thời gian; duration dùng monotonic nên không phụ thuộc đồng
hồ máy đổi giờ. `api_cost_usd=0` nghĩa không trả API; không nói điện/compute miễn phí.

## 5. File/folder triển khai có vai trò gì?

Tất cả đường dẫn dưới root `D:\Project\CAPSTONES\M2_week_7_8`.

| File/folder | Vai trò |
|---|---|
| `pyproject.toml`, `.venv/` | Dependency core/dev và môi trường riêng, không model weights |
| `src/vgar_m2_w78/bootstrap.py` | Read-only HEAD/hash/import-origin checks trước dùng shared VGAR |
| `contracts.py`, `config.py` | Internal task/policy/profile, path/selector validation; không đổi public DTO |
| `context_adapter.py` | Thin M1 consumer adapter, frozen sidecar hashes |
| `prompt.py`, `local_chat.py` | Prompt có version/hash; offline chat rendering/counter, không inference |
| `generator.py` | Explicit FakeGenerator, tuyệt đối không fallback khi real lỗi |
| `generator_hf.py`, `hf_backend.py`, `hf_worker.py`, `model_worker.py` | Worker request/response, bounded process, pinned local model, prompt/count/hash consistency |
| `executor.py` | Fixed argv, timeout/output cap, secrets filtering, Windows Job Object kill descendants; Native không phải security sandbox |
| `workspace.py`, `patch.py` | Private lease, byte-copy, strict parser, all-file preflight, apply/attest/export |
| `test_selection.py` | Changed paths → M1 hints → approved fallback scope |
| `pytest_plugin.py`, `test_runner.py` | Exact IDs/outcomes/durations, actual pytest/stdout/stderr/JUnit |
| `checks.py`, `verification.py` | Syntax/type/lint và baseline/post transitions, protection/source guards |
| `pipeline.py` | Điều phối một candidate/run, gates, canonical evidence, cleanup/public projection |
| `evidence.py` | Unique run ID, atomic JSON, terminal report, hash liên kết bundle/canonical |
| `cli.py`, `scripts/run_demo.py` | CLI explicit fake/real, exit0 PASS/1 FAIL/2 ERROR |
| `scripts/record_tests.py` | Chạy self-tests thật và ghi run evidence, không chỉ print summary |
| `scripts/prepare_inputs.py` | Chuẩn bị bản copy/export từ M1, receipt; không overwrite inputs đổi |
| `scripts/qualify_model.py` | Short real invocation, không được tính là repair success |
| `scripts/summarize_runs.py` | Chỉ đọc evidence, nhóm mode/prompt version; không inference lại |
| `config/fixtures/` | Mypy/Ruff config ngoài target worktree, hash trước/sau |
| `tests/` | Unit/integration guards và explicit reference patches |
| `examples/` | Task JSON/snapshots/handoff/receipt đã frozen |
| `results/` | Durable evidence của mỗi lần chạy; không sửa/xóa failures cũ |
| `.workspaces/` | Dữ liệu private runtime, mặc định dọn sau run |
| `PROGRESS.md`, `.superpowers/progress.md` | Current checkpoint và ledger lịch sử/rulings để resume |
| `docs/FAILURES.md`, `HANDOFF_M1_M3.md`, `REUSE_MAP.md` | Blocker, interface/gates, code được tái sử dụng |

## 6. Output, logs và cách đọc

Self-tests: `results/tests/<UTC-ID>/run_record.json`, `junit.xml`, `REPORT.md`.
Repair: `results/repair/<UTC-ID>/run_record.json`, `REPORT.md` và artifacts theo stage.
Model workers: `results/repair/model-workers/<uuid>/request.json`, `response.json`,
`command.json`. Dữ liệu worker được tham chiếu/nhúng trong generation evidence;
request prompt có thể chứa code, không public nếu repository riêng tư.

| Artifact | Có lúc nào? | Nội dung |
|---|---|---|
| `run_record.json` | Ngay khi bắt đầu | Run/task/mode/model/policy, stages, UTC/duration, stdout/stderr, argv/exit, source/hash/reasons |
| `prompt.txt` | Prompt hợp lệ | Full rendered chat; JSON cũng giữ messages/template/prompt hash/input tokens |
| `raw_model_output.txt` | Generation có output | Nguyên output model, kể cả sai format |
| `candidate.diff` | Parse PASS | Candidate đã parse, không tự sửa hunk |
| `transport.diff` | Apply PASS | Diff EOL-bound cho Git, tách khỏi raw |
| `applied.diff` | Attested apply + export hoàn chỉnh | Git diff của bytes thực tế trong worktree |
| `evidence_bundle.json` | Có lease và export hợp lệ | Public DTO + metadata/canonical hash; API/structural NOT_RUN |
| `REPORT.md` | Terminal | Summary, không thay JSON chi tiết |

`complete=True` nghĩa **đã ghi kết quả cuối**, không nghĩa PASS. `NOT_RUN` là chưa
thực thi. Finalization lỗi phải ERROR trên **cùng run**, không tạo một PASS giả.
Public test status dùng required/regression assessment, không chỉ exit0. Raw
pytest status vẫn được lưu để giải thích trường hợp pytest exit0 nhưng required
bị skip, khiến assessed test ERROR.

Các run cũ trước fix finalization giữ nguyên để truy vết; receipt/code fingerprint
cho biết chúng là historical, không dùng để chứng minh phiên code mới đã export
bundle/cleanup đúng. Dùng latest complete run có task/mode/prompt đúng khi tự kiểm.

## 7. Tự chạy từ đầu đến cuối bằng Windows PowerShell

### 7.1. Chỉ lần đầu hoặc dependency đổi

Máy hiện tại đã có `.venv`; **không cần cài lại mỗi lần**. Máy khác cần Python3.11,
Git, package M2 và checkout VGAR sibling đúng commit/hash. Cần tokenizer assets
theo manifest M1 (không nằm trong Git); sửa **path** cho đúng máy sau provision,
không tự đổi SHA/model/byte guard.

```powershell
# CHỈ LẦN ĐẦU: không ghi đè venv đã có.
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
}
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
# CHỈ LẦN ĐẦU hoặc dependency đổi; không chạy lại để test mỗi lần.
& $python -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Cài dependencies thất bại' }
```

Không cần activation script nếu gọi Python bằng full path. Biến `$python` không
giữ qua terminal mới: luôn khai báo lại ở mục dưới, tránh lỗi `& $python` rỗng.

### 7.2. Mỗi terminal mới / mỗi lần muốn self-test

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# CHẠY TEST CODE M2: không load model; tạo một run JSON mới.
& $python .\scripts\record_tests.py tests --timeout-seconds 240
$testExit = $LASTEXITCODE
Write-Host "Self-test exit: $testExit"
# CHỈ ĐỌC: tự chọn latest TEST run có canonical file.
$testRun = Get-ChildItem -LiteralPath '.\results\tests' -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'run_record.json') } |
    Sort-Object Name -Descending | Select-Object -First 1
if (-not $testRun) { throw 'Không có test evidence' }
$test = Get-Content -Raw -Encoding UTF8 (Join-Path $testRun.FullName 'run_record.json') | ConvertFrom-Json
$test | Select-Object run_id,status,complete,duration_ms
$test.stages.pytest | Select-Object exit_code,complete,timed_out,output_truncated
$test.stages.pytest.stdout
$test.stages.pytest.stderr
```

Exit0 và summary `N passed` là self-test đạt. Không gọi đó là N task LLM sửa được.
Để chạy nhóm nhỏ, thay `tests` bằng `tests/test_patch.py` hoặc
`tests/test_review_guards.py`; không cài lại dependency.

### 7.3. Demo engine bằng fake — không phải sửa bằng LLM

```powershell
# MỖI LẦN DEMO: chọn một trong ba case; ví dụ multi-file.
$case = 'multi_file_invoice'
& $python .\scripts\run_demo.py --task ".\examples\tasks\$case.json" --mode fake
$repairExit = $LASTEXITCODE
Write-Host "Repair exit: $repairExit"
# CHỈ ĐỌC: tự chọn latest complete run đúng TASK và MODE, không lấy model-workers.
$matches = @(Get-ChildItem -LiteralPath '.\results\repair' -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'run_record.json') } |
    Sort-Object Name -Descending | ForEach-Object {
        $p = Join-Path $_.FullName 'run_record.json'
        $r = Get-Content -Raw -Encoding UTF8 $p | ConvertFrom-Json
        if ($r.task_id -eq $case -and $r.mode -eq 'fake' -and $r.complete) {
            [pscustomobject]@{Directory=$_.FullName; Record=$r}
        }
    })
if (-not $matches.Count) { throw 'Không tìm thấy run đúng task/mode' }
$chosen = $matches[0]
$r = $chosen.Record
Write-Host "Evidence: $($chosen.Directory)"
$r | Select-Object run_id,status,reason,original_source_unchanged,duration_ms
$r.stages.baseline.tests.outcomes | ConvertTo-Json -Depth 5
$r.stages.apply | ConvertTo-Json -Depth 5
$r.stages.verification.tests.outcomes | ConvertTo-Json -Depth 5
$r.stages.verification.static | ConvertTo-Json -Depth 5
if ($r.artifacts.applied) {
    Get-Content -Raw -Encoding UTF8 (Join-Path $chosen.Directory $r.artifacts.applied)
}
if ($r.artifacts.bundle) {
    Get-Content -Raw -Encoding UTF8 (Join-Path $chosen.Directory $r.artifacts.bundle)
}
Get-Content -Encoding UTF8 (Join-Path $chosen.Directory 'REPORT.md')
```

Chạy case A/C bằng cách đổi `$case` thành `single_file_login`/`missing_links`.
Không cần điền folder run thủ công. Nếu chạy nhiều terminal song song, lấy path
script vừa in ra làm authoritative; latest chỉ phù hợp chạy tuần tự.

### 7.4. LLM thật — hiện BLOCKED, không lặp lại phương pháp cũ

Không chạy lại v1/v2 hiện có chỉ để mong may mắn. Hai failure đã lưu. Sau khi owner
duyệt một phương pháp format/profile mới trong đúng scope thì mới chạy một run
riêng, ghi prior run và reason; không merge kết quả các versions.

Lệnh tham khảo sau qualification/approval mới, **không phải bước cần chạy ngay**:

```powershell
# SAU KHI DUYỆT PROFILE/PROMPT MỚI và config đã pin đúng máy.
& $python .\scripts\qualify_model.py
if ($LASTEXITCODE -ne 0) { throw 'Invocation qualifier thất bại; không repair' }
# Một generation/run; không auto retry. Dùng config được owner duyệt.
& $python .\scripts\run_demo.py --task .\examples\tasks\single_file_login.json --mode real
$LASTEXITCODE
# CHỈ ĐỌC: xem tất cả real evidence, nhóm theo version.
& $python .\scripts\summarize_runs.py --mode real
```

Không chạy repo ngoài, không SWE-bench, không bật quantization/model khác âm thầm.
Qualifier chưa phải format qualification; A phải sinh valid diff trước khi đi B/C.

## 8. Evidence thất bại thật và bước tiếp theo

V1: `results/repair/20261014T090352481580Z-8f8da9b4cddd/run_record.json`:
raw SEARCH/REPLACE, 662 input / 26 output tokens, parser FAIL trước apply.

V2: `results/repair/20261014T091104527173Z-8e59e14c75c7/run_record.json`:
header `@@ -1,3 +1,3 @@` nhưng old/new thực tế chỉ có 2 dòng. Raw giữ nguyên,
`parse_patch.reason=Truncated or malformed hunk`, source unchanged. Thời gian
62.453s toàn run, 724 input / 38 output tokens. Hai run không phải
BUDGET_EXHAUSTED và không test post patch.

Đọc raw bằng `Get-Content -Raw -Encoding UTF8 <run>\raw_model_output.txt`, đồng thời
đọc `run_record.json.stages.parse_patch`. Không sửa file evidence/raw.

Để đóng gate real còn thiếu: M1/M2/leader cần quyết định một thay đổi format có
lý do hoặc backend phù hợp unified diff; pin version, ngân sách và giữ parser/
verifier. Chạy lại A có provenance riêng, sau đó B/C. Chưa có quyền đổi model
hay train trong phiên này. M3 cần tích hợp tool wrapper và tự nghiệm thu transport;
đồng đội cần chạy lại trên môi trường của mình. Xem `PROGRESS.md` cho checkpoint
và evidence mới nhất, không dựa số test cũ trong hội thoại.

## 9. Giới hạn cần nêu trong báo cáo

- Native không cô lập code độc hại; chỉ ba fixture byte-verified, không arbitrary repo.
- Test passing là patch plausible theo suite, không chứng minh semantic correctness.
- Fake patch chạy thành công không phải kết quả model sinh code.
- Three fixtures không phải resolved rate SWE-bench hoặc khả năng tổng quát.
- API/graph structural validation, MCP runtime, benchmark/fine-tuning là ngoài phiên này.
- JUnit hiện kiểm XML hợp lệ, exact outcome guard dựa reporter riêng; chưa đối chiếu
  toàn bộ counters JUnit với reporter (review minor đã ghi nhận).
- Byte/EOL manifests là profile Windows hiện tại; Linux/container chưa nghiệm thu.
- EvidenceBundle đúng public DTO nhưng không có aggregate public verification status;
  đọc tests/typecheck/lint/reasons và metadata repair_status/canonical JSON.
- Results chứa code/prompt/stdout; review privacy trước chia sẻ. Không commit/push phiên này.

## 10. Extension prompt V3/V4 đã được duyệt ngày14/10

**Kết quả hiện tại:** campaign đã kết thúc với **FAIL / FAILURE_LIMIT**, bốn
attempts và hai failures. A PASS ở V3/V4; B-V3 bỏ sót `invoice.py`, B-V4 sai dòng
bắt đầu hunk `invoice.py` (1 thay vì 4). C chưa chạy do giới hạn failures.
Không còn process repair đang chạy; không chạy thêm hoặc reset campaign.
Gate 3/3 real repairs cùng prompt cuối **chưa đạt**. Kiểm thử package cuối:
126 tests PASS, exit 0. Các mục trước extension giữ làm lịch sử.

Không chạy lại V1/V2 từ mục7.4. Dùng
[hướng dẫn campaign mới](PROMPT_V3_V4_VA_NGHIEM_THU_REAL.md), giữ model/SHA/guards,
một generation/run và6newattempts/2failures. V3/V4 templates viết trước inference;
full offline tests mới lưu riêng. Latest actual status luôn ở rootPROGRESS.
Mục1/8 bên trên mô tả kết quả historical trước extension, không overwritefailures.
