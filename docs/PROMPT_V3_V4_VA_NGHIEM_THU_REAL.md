# Prompt V3/V4 và nghiệm thu real M2 tuần 7–8

**Trạng thái cuối:** campaign **FAIL / FAILURE_LIMIT** sau bốn attempts và hai
failures. A real PASS với V3/V4; B-V3 bỏ sót invoice, B-V4 sai dòng bắt đầu hunk
invoice; C **NOT_RUN**. Gate ba cases PASS cùng prompt cuối **chưa đạt**.
Không chạy `--run` để thử lại, không reset hoặc tạo campaign mới vượt giới hạn.
Dùng `--status` và khối đọc kết quả dưới đây. Báo cáo chi tiết:
`../results/acceptance/2026-10-14-prompt-v3-v4/REPORT.md`.

Extension ngày14/10/2026, không thay model/SHA/budget/guards/M1/M3. V1/V2 giữ
nguyên, failures cũ không bị overwrite. V3/V4 là hai candidate định nghĩa trước,
không bảo đảm model sinh diff đúng hoặc đạt3PASS.

## Thay đổi

- `context_presentation.py` giữ exact snippet bytes/text và item order; thêm
  start/endexclusive/lastcovered/snippetcount/fullfilecount ngoài code. Kiểm
  source hash lại sau M1 validation. Original M1 renderer text nằm trong prompt
  metadata evidence, không sửa source/contract/render của VGAR.
- `prompt.py` explicit template mapping V1–V4; V1/V2 assembly giữ nguyên. V3
  giải thích hunkcounts bằng context+removed/added và one neutral example.
- V4 thêm neutral two-file example và checklist all issue clauses/units.
  Không có auth/invoice/formatter gold trong templates; model chỉ trả unified diff.
- `campaign.py` durable manifest/counters/owner lock/PID birth check/gate assessment.
- `scripts/run_acceptance.py` explicit --run; --status chỉ đọc. Core venv không
  Torch; actual inference vẫn ở bounded cached HF worker. Không modelOK extra.

## Quy tắc trial

Chạy V3 theo thứ tự A → B → C. Nếu cả ba PASS thì chốt V3, không chạy V4.
FAIL đầu tiên chuyển sang V4 đã khóa và bắt đầu lại từ A; không mang PASS của
V3 sang. Hai failures hoặc sáu attempts là giới hạn dừng. Runtime ERROR dừng
ngay, không dùng prompt V4 để chữa OOM, timeout hoặc lỗi input. Failures V1/V2
vẫn được giữ riêng. Mỗi run chỉ sinh một candidate, không best-of-N.

Campaign mặc định: `results/acceptance/2026-10-14-prompt-v3-v4/`.
`campaign.json`: từng reserved attempt, ownerPID/birth, UTCstart/end, terminal
record/hash/status/gate errors/finalversion. `frozen_inputs.json`: model/policy,
reference/task/source/bundle/code/tokenizer fingerprints, template hashes.
Mỗiattempt có `attempts/<number>/<UTC-run>/run_record.json` và artifacts;
workers ở `attempts/<number>/model-workers/`. Đừng chỉ chọn latest global run.

## PowerShell — không cài lại

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:PYTHONUTF8 = '1'
# CHỈ ĐỌC: chưa có campaign thì NOT_RUN, không tạo directory/model.
& $python .\scripts\run_acceptance.py --status
# CHỈ ĐỌC: exit 0 ở đây nghĩa là đọc được trạng thái, KHÔNG nghĩa campaign PASS.
$LASTEXITCODE
# Lệnh đã dùng để chạy phiên được duyệt là:
# & $python .\scripts\run_acceptance.py --run
# Để comment: campaign hiện đã terminal FAIL, không được chạy thêm inference.
```

Nếu pending owner còn sống: không launch; chờ process cụ thể kết thúc. Nếu PID
không tồn tại hoặc đã reuse birth khác: reconcile unique terminal record; nếu
không có terminal record thì ERROR interruption, không rerun tự động.
Nếu không đọc được process identity: giữ pending, không suy diễn là chết.
Manifest/file/code hash mismatch thì dừng, không sửahash/resetcampaign để chạy.

## Gate

Mỗi accepted real run cần parser/apply/baseline/postcollection/required/regression/
syntax/mypy/Ruff đúng, applieddiff delivered, bundle→canonicalhash đúng,
source unchanged. B đổi2sourcefiles, C collection/fallback có evidence. Fake và
qualifierOK không được cộng. Publicstatuses unchanged.

## Đồng đội tự chạy lại

Sau khi final prompt đạt3PASS, dùng cùng package/source/model/tokenizer profile;
copy final config/path cho máy của mình nếu cần qualification riêng. Run độc lập
phải dùng output directory riêng và ghi model/runtime/source profile. Không
chỉnh campaign đã terminal hoặc tự tạo campaign mới để vượt cap phiên hiện tại.
Human reproduction vàM3 MCPgate chưa được agent ký thay.

Kết quả cuối đã được cập nhật trong `PROGRESS.md`, `docs/COMPLETION_REPORT.md`
và campaign `REPORT.md`/`summary.json`. Full self-test cuối: **126 passed**, exit 0.
Không coi ba development fixtures là held-out SWE-bench, chứng minh mọi hành vi
đúng, hoặc bằng chứng prompt tối ưu toàn cục.

## Đọc kết quả tự động, không điền folder run

```powershell
# MỖI TERMINAL: cần đúng cwd; các lệnh dưới CHỈ ĐỌC.
Set-Location 'D:\Project\CAPSTONES\M2_week_7_8'
$campaign = Join-Path (Get-Location).Path 'results\acceptance\2026-10-14-prompt-v3-v4'
if (-not (Test-Path -LiteralPath (Join-Path $campaign 'campaign.json'))) {
    throw 'Campaign chưa được tạo; không lấy một latest fake run thay thế.'
}
$study = Get-Content -Raw -Encoding UTF8 (Join-Path $campaign 'campaign.json') | ConvertFrom-Json
$study | Select-Object campaign_id,status,complete,final_version,reason
$study.attempts | Select-Object number,version,task_id,status,complete,record,gate_errors
# Tự chọn latest TERMINAL attempt; vẫn hiển thị nếu FAIL, không giấu failure.
$attempt = $study.attempts | Where-Object { $_.complete -and $_.record } |
    Sort-Object number -Descending | Select-Object -First 1
if (-not $attempt) { throw 'Chưa có terminal canonical run; xem pending owner, không launch lại.' }
$r = Get-Content -Raw -Encoding UTF8 -LiteralPath $attempt.record | ConvertFrom-Json
$runDirectory = Split-Path -Parent $attempt.record
$r | Select-Object run_id,task_id,status,reason,original_source_unchanged,duration_ms
$r.stages.generation | Select-Object input_tokens,output_tokens,finish_reason,duration_ms
$r.stages.verification | ConvertTo-Json -Depth 8
if ($r.artifacts.raw_output) {
    Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $r.artifacts.raw_output)
}
if ($r.artifacts.applied) {
    Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $r.artifacts.applied)
}
if ($r.artifacts.bundle) {
    Get-Content -Raw -Encoding UTF8 (Join-Path $runDirectory $r.artifacts.bundle)
}
```

Campaign PASS chỉ khi3cases đềurealPASS cùngfinalversion. Campaign NOT_RUN với
pending không có nghĩa là hỏng: run vẫn có thể đang generation. --status không
can thiệp worker. Gate audit không sửa raw/canonical; discrepancy là ERROR,
không tự khôi phục ledger thành PASS. Các structural simulated records trong
unit tests chỉ kiểm controller, hoàn toàn không là real evidence.
