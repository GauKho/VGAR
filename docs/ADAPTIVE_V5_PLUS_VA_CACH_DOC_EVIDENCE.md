# M2 tuần 7–8 — Adaptive Repair Prompt V5+ và cách đọc evidence

Phiên được duyệt ngày **15/10/2026**, không phải tiếp tục reset campaign V3/V4 đã FAIL.
Chỉ package M2 độc lập; VGAR, hệ thống cũ, tests/gold/parser/verifier không sửa.
Trạng thái actual xem `../PROGRESS.md`; không coi tài liệu dự kiến là kết quả PASS.

**Sau logging update15/10:** runtime đã thay đổi; campaign cũ vẫn giữ frozen hash
nguyên gốc. `--status` với runtime mới sẽ fail-closed; không reset/bypass guard.
Đọc section6 của `LOG_DIAGNOSTICS_VA_CACH_DOC_LOI.md` để audit V5+ bằng archive.
Các kết quả bên dưới là historical, không có thêm real run sau task logging.

## Kết quả đã chốt ngày 15/10/2026 — đọc trước khi chạy lệnh

**Phiên đã kết thúc FAIL / TUNING_QUOTA_EXHAUSTED, không còn model chạy.**
B FAIL4lượt(V5–V8), C PASS1lượt(V9); final chưa chạy vì B không qua tuning.
C PASS không đủ thay thế gate ba cases mới cùng prompt. Không có final_profile.json.
Không init/reset/register/run-next tiếp hoặc lấy slots dư để chạy B5.
Các lệnh --status/--history và đọc evidence bên dưới vẫn an toàn, không inference.

| Task | Trạng thái | Vì sao |
|---|---|---|
| B multi_file_invoice | BLOCKED | V5/V6 sai counts; V7 thiếu context-prefix; V8 hallucinate metadata file; hết4lượt |
| Final A/B/C | NOT_RUN / chưa nghiệm thu | Chỉ được chạy khi B và C tuningPASS; không ghép A cũ với C mới |
| Teammate reproduction / M3 | Chưa có xác nhận ngoài package | Chưa ký thay đồng đội; không tự chạy thêm để vượt phạm vi |
| C missing_links | RealPASS dướiV9 | Parse/apply/collection/fallback2tests/syntax/mypy/Ruff; source nguyên trạng |
| Code/self-tests/audit | Hoàn thành | 152testsPASS, RuffPASS; archive/evidence/frozen/source/caps PASS |

Kết quả chi tiết từng lượt: `../results/adaptive_acceptance/2026-10-15-v5-plus/REPORT.md`
và `summary.json`. Các mô tả controller bên dưới giải thích implementation,
không phải lời cho phép chạy thêm real attempts sau terminal.

## 1. Vì sao cần phiên mới?

B-V3 chỉ sửa pricing, bỏ invoice; B-V4 sửa hai file nhưng hunk invoice bắt đầu
dòng1 thay4. V5 yêu cầu kiểm mọi mệnh đề issue và tọa độ tuyệt đối trong file,
với ví dụ trung tính bắt đầu3/6 thay vì mọi ví dụ bắt đầu1. Metadata được nhấn
mạnh ngoài source; không sửa hoặc thêm nội dung source trong M1 context.

Một lượt có flow: source/task/M1 handoff được kiểm hash → private worktree mới →
baseline → prompt/pinned tokenizer → một generation Qwen → strict parse → exact
all-file apply → collection/selection/tests/syntax/mypy/Ruff → canonical/bundle → cleanup.
FAIL output/patch có thể dẫn đến prompt mới, nhưng không được sửa raw output hộ model.

## 2. Tự động nghĩa là gì?

Codex đọc log và viết Vn+1 giữa các attempts, ghi hypothesis/change/parent failed run.
Script không tự sáng tác prompt, không thêm planner/model/agent khác. Mỗi lệnh
`--run-next` chỉ chạy **một generation** rồi trả trạng thái. Không chạy script
song song hoặc dùng vòng PowerShell tự retry y nguyên khi thấy exit1.

Tối đa4 lượt tuning B,4 C,3 final. B hết4fail được note blocked, Codex tạo revision
mới trước khi chuyển C; không mang feedback B vào C. C hết4fail hoặc B chưaPASS
thì không được ghi final acceptance PASS. OOM/timeout/source mismatch/runtimeERROR
dừng phiên, không cải thiện prompt để che lỗi môi trường.

Nếu B,C đều PASS: khóa version cuối, A→B→C chạy mới **không feedback cũ**. Final
FAIL không tạo thêm version/rerun trong quota này. PASS cần cả ba cùng template,
không trộn tuning/old/fake/invocationOK. Ba development fixtures không phải benchmark.

## 3. Inputs và outputs nằm ở đâu?

Mọi đường dẫn dưới đây tính từ `D:\Project\CAPSTONES\M2_week_7_8`.

| Nội dung | Đường dẫn / vai trò |
|---|---|
| Issue, allowed/protected paths, required tests | `examples/tasks/<case>.json` |
| Source gốc, không chỉnh sửa | `examples/snapshots/<case>/` |
| M1 context/inputs/source manifest | `examples/handoffs/<case>/` |
| Pinned model/budget | `config/demo.json`; version này vẫn giữ V2 historical, controller chọn adaptive version từ registry |
| Instructions V5+ | `prompts/repair_v5.txt`, sau đó append V6+ khi có FAIL và quota |
| Runtime trước thay đổi | `results/adaptive-preflight/20261015T001508430263Z-6296d566fd2e/runtime/` |
| Hash map runtime/historical/VGAR bảo vệ | Cùng preflight folder, `archive_manifest.json` |
| Phiên mới | `results/adaptive_acceptance/2026-10-15-v5-plus/` |
| Trạng thái, counters, owner, canonical paths | Trong phiên: `campaign.json` |
| Code/model/task/source/tokenizer khóa | `frozen_inputs.json` |
| Template hash, parent run, lý do/hypothesis | `revisions/m2-w78-vN.json` |
| Evidence một lượt | `attempts/NN/<UTC-run>/run_record.json` |
| Prompt/model output | Cùng canonical folder: `prompt.txt`, `raw_model_output.txt` |
| Diff thực sự applied | `applied.diff` chỉ có khi apply/export đạt; FAIL trước apply không có file này |
| Public projection | `evidence_bundle.json`, trỏ canonical hash; đọc NOT_RUN đúng nghĩa |

Canonical có baseline/post stage commands, stdout/stderr/exit/duration, actual
nodeIDs/outcomes, input/output tokens và resource metadata. Worker logs ở
`attempts/NN/model-workers/`. Dòng command dùng interpreter Torch có sẵn trong
venv cũ là tái sử dụng dependency read-only, không chạy/import source hệ thống cũ.

## 4. PowerShell chỉ đọc — an toàn, không inference/cài lại

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# CHỈ ĐỌC trạng thái lịch sử; code logging mới khác frozen runtime cũ.
# Không gọi --status để buộc code mới khớp source hash của code cũ.
$saved = Get-Content -Raw -Encoding UTF8 -LiteralPath '.\results\adaptive_acceptance\2026-10-15-v5-plus\campaign.json' | ConvertFrom-Json
$saved | Select-Object campaign_id,status,complete,reason,final_version
# CHỈ ĐỌC lịch sử: đối chiếu old runtime đã archive + evidence cũ.
# Không dùng legacy --status để đòi code mới phải khớp fingerprints của code cũ.
& $python .\scripts\run_adaptive_acceptance.py --history
$LASTEXITCODE
```

Trong runtime cũ, exit0 của `--status` chỉ nghĩa đọc thành công, không chứng minh
campaign PASS. Sau logging change dùng archive reader được chỉ ở đầu tài liệu.
Trong khi generation chưa xong, public `status=NOT_RUN, complete=false` có thể là
record đang pending, không phải chưa launch. Xem `next_action.action=PENDING`,
owner PID/birth và stage `started_utc`. Không khởi chạy worker thứ hai để thử lại.
Chỉ Codex điều phối trong phiên đã được duyệt mới dùng init/register/run-next.
Không copy các lệnh từ history để reset hoặc sinh lượt thứ12.

## 5. Tự chọn đúng attempt để xem, không dán run ID

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$campaign = Join-Path (Get-Location).Path 'results\adaptive_acceptance\2026-10-15-v5-plus'
$manifestPath = Join-Path $campaign 'campaign.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Chưa init campaign mới; không lấy fake run thay thế.' }
$study = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
$study | Select-Object campaign_id,status,complete,reason,final_version
$study.attempts | Select-Object number,phase,task_id,version,status,complete,record
# CHỈ ĐỌC: chọn latest terminal attempt, không giấu FAIL/ERROR.
$attempt = $study.attempts | Where-Object { $_.complete -and $_.record } |
    Sort-Object number -Descending | Select-Object -First 1
if (-not $attempt) { throw 'Chưa có terminal evidence; xem pending owner, không chạy trùng.' }
$record = Get-Content -Raw -Encoding UTF8 -LiteralPath $attempt.record | ConvertFrom-Json
$folder = Split-Path -Parent $attempt.record
$record | Select-Object run_id,task_id,adaptive_phase,status,reason,duration_ms,original_source_unchanged
$record.stages.generation | Select-Object input_tokens,output_tokens,finish_reason,duration_ms
$record.stages.verification | ConvertTo-Json -Depth 8
foreach ($key in @('raw_output','applied','bundle')) {
    $relative = $record.artifacts.$key
    if ($relative) { Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $folder $relative) }
}
```

Nếu muốn riêng B/C hoặc final, thêm điều kiện `task_id`/`phase` vào Where-Object;
không chọn latest toàn bộ results vì có thể lấy self-test/fake thay real run.

## 6. Tự kiểm package và bàn giao

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
# CHẠY TEST package, không generation LLM, có receipt JSON/REPORT riêng.
& $python .\scripts\record_tests.py tests --timeout-seconds 240
$LASTEXITCODE
# CHỈ CHECK, không auto-fix: giữ quy tắc Ruff của package hiện có.
& $python -m ruff check --select E9,F src scripts tests
$LASTEXITCODE
```

Sau final3PASS, `final_profile.json` trong campaign chứa version/model/budget đã
khóa. Đồng đội cần đúng M1 checkout/pin, dependencies, source/handoff/tokenizer
assets và weights SHA; kiểm lại các đường dẫn local trên máy mình. Chạy một
fixture bằng profile này qua `run_demo.py --config ... --mode real` với output
directory riêng sau approval riêng, không sửa campaign đang nghiệm thu.
Không chạy thêm replay trên máy hiện tại trong quota11 nếu chưa được duyệt.
Human reproduction và M3 transport do chủ sở hữu xác nhận; không tự tick thay họ.

Full self-tests không thay thế real3PASS. Nếu final chưa đạt, không dùng profile
export tạm hoặc một lần tuningPASS để tuyên bố có prompt cuối đã được nghiệm thu.

## 7. Đọc riêng C đã PASS: input → xử lý → output

Input issue/policy: `examples/tasks/missing_links.json`; source gốc:
`examples/snapshots/missing_links/formatter.py`; M1 handoff:
`examples/handoffs/missing_links/`. Prompt instruction là `prompts/repair_v9.txt`.
Token/profile/pins từ frozen_inputs.json; model/runtime không đổi so với approval.

Flow thực tế:

```text
Task + source/handoff hashes
    -> private worktree mới
    -> baseline: trim FAIL, empty PASS
    -> V9 + exact source context + Qwen pinned, feedback=None
    -> raw unified diff -> strict parser -> exact Git apply/byte attestation
    -> M1 unlinked -> fallback tests -> collect-only -> 2 node IDs
    -> pytest tests: 2 PASS -> syntax/mypy/Ruff PASS
    -> canonical + raw/candidate/transport/applied + EvidenceBundle
    -> cleanup worktree; source gốc vẫn không đổi
```

Tìm output của C từ manifest, không dán run folder thủ công:

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$campaign = Join-Path (Get-Location).Path 'results\adaptive_acceptance\2026-10-15-v5-plus'
$study = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $campaign 'campaign.json') | ConvertFrom-Json
$attempt = $study.attempts | Where-Object {
    $_.task_id -eq 'missing_links' -and $_.phase -eq 'tuning_C' -and $_.complete
} | Sort-Object number -Descending | Select-Object -First 1
if (-not $attempt -or -not $attempt.record) { throw 'Chưa có canonical C; không lấy fake run thay.' }
$record = Get-Content -Raw -Encoding UTF8 -LiteralPath $attempt.record | ConvertFrom-Json
$folder = Split-Path -Parent $attempt.record
$record | Select-Object run_id,status,reason,duration_ms,original_source_unchanged
# BASELINE: failed_cases / outcomes trước sửa, không nhầm stage PASS với tests PASS.
$record.stages.baseline.tests.outcomes | ConvertTo-Json
# M1 unlinked -> selected tests; selection.collection_verified=false là hint tĩnh,
# không phủ định collection thật được chạy ở stages.verification.collection.
$record.stages.selection | ConvertTo-Json -Depth 8
$record.stages.verification.collection | Select-Object status,node_ids,exit_code,complete | ConvertTo-Json -Depth 5
$record.stages.verification.tests.outcomes | ConvertTo-Json
$record.stages.verification.static | ConvertTo-Json -Depth 7
# RAW: diff model tự sinh, không được host chữa nội dung/counts.
Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $folder $record.artifacts.raw_output)
# APPLIED: Git diff export, có thể gọn hơn raw vì Git chuẩn hóa context;
# đây không phải host sửa raw để qua parser. Parser/apply đã đạt trước export.
if ($record.artifacts.applied) {
    Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $folder $record.artifacts.applied)
}
```

Model output957input/43output tokens; generation thuần33.703s, toànrun65.359s.
Baseline `test_label_trim` FAIL -> postPASS; `test_label_empty` vốnPASS vẫnPASS.
Applied diff có sửa `formatter.py`; không copy ngược vào source gốc tự động.
Khi mở repo gốc vẫn thấy `return name` là đúng chế độ disposable worktree.
Public DTO api_check/structural_check NOT_RUN không được đọc thành PASS:
đó không phải gate nâng cao đã triển khai ở tuần7–8 này.

## 8. Files thay đổi trong extension và kiểm chứng cuối

| File / nhóm | Vai trò thay đổi |
|---|---|
| `src/vgar_m2_w78/contracts.py` | Internal prompt_version nhận Vn hợp lệ; public DTO/status không đổi |
| `src/vgar_m2_w78/prompt.py` | Explicit template lookup, optional same-case bounded feedback, full chat budget |
| `src/vgar_m2_w78/context_presentation.py` | Absolute first-source-line metadata ngoài source; không sửa snippets/order |
| `src/vgar_m2_w78/pipeline.py` | Optional feedback/phase/campaign metadata và truyền vào prompt, giữ apply/verify |
| `src/vgar_m2_w78/adaptive_campaign.py` | B4/C4/final3 state machine; reserve/recover/owner/revision/hash gates; history reader |
| `scripts/run_adaptive_acceptance.py` | Init/register/status/history/run-next, một generation/lệnh, không tự thiết kế prompt |
| `prompts/repair_v5.txt`–`repair_v9.txt` | Instruction revisions bất biến sau đăng ký; parent/reason/hypothesis ở campaign registry |
| `tests/test_prompt_adaptive.py`, `test_prompt_v6.py`–`test_prompt_v9.py` | Neutral examples/metadata/feedback/budget/strict parser+bind+Git-apply checks |
| `tests/test_adaptive_campaign.py`, `test_adaptive_cli.py` | Caps/transitions/resume/owner/immutability/recovery/CLI history guards |
| `docs/REVIEW_ADAPTIVE_V5_PLUS_2026_10_15.md` | Fresh review findings, một RED→GREEN fix pass và minor deferred |

Trước extension126tests; sau extension/prompt tests152testsPASS. Không sửa các
fixture tests, gold/reference patches, parser/verifier/registry/config/model.
Trong69 archived original runtime files, chỉ bốn module cũ ở bảng trên có thay
đổi; archive/new modules/templates/docs không bị diễn giải là code cũ.

Full suite: `results/tests/20261015T005945598043Z-a4f4d47f3d8d/run_record.json`.
Final audit: `results/checks/20261015T010114900109Z-cfbffe5811a9/run_record.json`.
Full suite152PASS88.51s, recorder89.203s; Ruff E9/F PASS. Historical reader kiểm
69 files archive,69 files evidence cũ,4 files VGAR dirty bảo vệ; current frozen
runtime/source/tokenizer/revisions và cả5 public/canonical bundles/caps đềuPASS.
Đây là kiểm tính toàn vẹn, **không** phải thí nghiệm3/3PASS.

Nếu tiếp tục nghiên cứu sau cap, cần owner phê duyệt phương pháp/phiên mới có
định danh riêng; không ghi đè failures/counters. Hiện chưa có evidence cho thấy
OOM/timeout gây B FAIL. Prompt có ảnh hưởng nhưng chưa được chứng minh có thể
bảo đảm3/3 với cùng model/profile. Không tự đổi backend, fine-tune hoặc nới guards.
