# M1-W9-4 — Official harness: wrapper và kiểm thử offline

## 1. Mục đích và trạng thái

Task này kiểm **hạ tầng chấm gold patch**, không yêu cầu model tự sửa lỗi.
Gold patch là patch của developer trong dataset; official SWE-bench áp dụng patch,
chạy test patch/commands của task trong Docker và sinh report. Wrapper không tự
viết lại cách chấm F2P/P2P, không dùng native pytest để thay official grading.

**Nghiệm thu local24/10/2026: QUALIFIED,3/3 official gold RESOLVED.**
[Báo cáo kết quả/giới hạn/evidence](m1_w9_4_acceptance_report.md), campaign `20261024T081750218758Z-3af0d2d105bc`.
Wrapper49PASS; selected regression467PASS/1SKIP. Raw pytest có failures ngoài
official grading; không suy mọi testPASS hoặc model repair rate từ qualification.
Quota2/2campaigns,6/6attempts đã dùng; không tự chạy gold thêm. Local qualified
profile trong results ignored, skeleton public vẫnUNQUALIFIED để không giả lập
qualification ở clone/máy khác. Review/merge nhóm giữ riêng.

### Lịch sử preflight/offline trước qualification

Preflight thật đã chạy ngày23/10/2026, exit2/BLOCKED:
`results/m1/w9/m1-w9-4/preflight-runs/20261023T114337054050Z-46467d0ae8ea/`.
Run này kiểm cached Parquet thật, tạo inputs cho đúng3task; không launch harness,
Docker hoặc model. Cả3task là NOT_RUN; resolved_count=0 không có nghĩa0/3 thất bại.
Preflight không gọi external commands khi host/profile chưa đáp ứng điều kiện cơ bản.

Blockers: host Windows thay vì Linux harness đã qualification; profile UNQUALIFIED;
chưa provision interpreter/source harness riêng, Docker endpoint và3pinned image identities.
Kiểm chỉ-đọc ở phiên lập kế hoạch còn thấy Docker daemon không kết nối, distro
docker-desktop đang dừng. Không tự sửa trạng thái đó hoặc cài thêm ở task này.

## 2. File và flow

| File | Vai trò |
|---|---|
| src/vgar/evaluation/harness/gold_inputs.py | Kiểm manifest/cache/task identity; tạo dataset và predictions chứa gold, chỉ ở evaluation |
| src/vgar/evaluation/harness/official.py | Profile, preflight, argv, process capture, per-task orchestration, cleanup và CLI |
| src/vgar/evaluation/harness/reports.py | Đọc đúng report format của pin; kiểm patch bytes/ID/boolean/artifacts; không tự chấm tests |
| configs/m1/w9_harness_profile.json | Skeleton UNQUALIFIED; không chứa interpreter/image giả |
| scripts/run_official_harness.sh | Entry point Bash, truyền argv nguyên vẹn; mặc định chỉ preflight |
| tests/test_official_harness.py | Offline tests; harness/Docker boundary giả lập, report fixtures luôn synthetic |

```text
Pinned pilot manifest + cached Parquet thật
  → so dataset byte hash / task ID / repo / basecommit / query hash
  → ignored evaluation inputs: dataset.json + predictions.jsonl + inputs.json
  → preflight Linux / harness source+module+version+CLI / Docker / pinned images
      thiếu: BLOCKED, mọi task NOT_RUN
      đủ nhưng không --execute: argv được ghi, task NOT_RUN
      đủ và --execute:
        task1 → task2 → task3, một worker, fresh run IDs
        official harness → raw reports/logs → strict report reader
        cleanup owned container + recheck runtime/input hashes
  → run_record.json, giữ đủ3task và mọi failures
```

API theo plan:

```python
run_gold_validation(pilot_manifest, *, harness_profile, instance_ids, output_root)
```

API này yêu cầu **execution** và vẫn chạy preflight trước; CLI mặc định không
execution. Code wrapper không import/cài package swebench trong host VGAR.
Việc kiểm module swebench diễn ra qua interpreter riêng trong profile khi readiness
cơ bản đủ. Handoff/retrieval M1 và pipeline/session M2 không bị thay đổi.

## 3. Inputs và pins

- SWE-bench v4.1.0, commit `726c5461e2ef52d83cf1ea2107870a8bb3328d57`.
- Dataset snapshot `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`; Parquet SHA-256
  `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`.
- Chỉ ba task đầu manifest W9, giữ thứ tự:
  `astropy__astropy-13398`, `django__django-11138`, `matplotlib__matplotlib-14623`.
- Project split là `dev` theo hash policy VGAR; partition nguồn SWE-bench Verified
  là `test`. Truyền `--split test` cho local dataset không đổi project split.
- `patch` giữ nguyên chuỗi UTF-8; test_patch/F2P/P2P chỉ trong evaluation inputs.
  Manifest retrieval và graph/BM25 bundles không nhận thêm gold metadata.

Profile local tương lai cần cung cấp Python harness riêng, full checkout sạch
đúng commit, explicit `docker_host` và cached Parquet; đặt qualification_state=READY
chỉ khi đã provision. Ví dụ endpoint `unix:///var/run/docker.sock`; không chọn
daemon ngầm từ current CLI context. Cả CLI/SDK/harness/cleanup dùng cùng DOCKER_HOST,
loại DOCKER_CONTEXT ambient và preflight so Docker server ID của CLI với SDK thật.
Mỗi `images[instance_id]` phải có `tag`, `reference`, `image_id`, `repo_digest`.
Reference theo naming upstream của pin:
`swebench/sweb.eval.x86_64.<instance_id thay __ bằng _1776_>:<tag>`.
Preflight quan sát Docker image ID/RepoDigests thực, không chỉ tin nhãn READY.
Không dùng config skeleton để tuyên bố runtime đã qualification.

## 4. PowerShell — chỉ kiểm thử/preflight trên máy hiện tại

Các lệnh dưới tạo evidence mới trong ignored results, không sửa pipeline,
không setup Docker/WSL, không tải weights/images và không chạy gold thật.

```powershell
# Vào root VGAR; không cần activate nếu gọi đúng interpreter có sẵn.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = 'D:\Project\CAPSTONES\environments\vgar-week78-cuda\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Chọn interpreter có dependencies hiện hữu, không tự cài lại.' }
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'

# Chạy offline tests wrapper; synthetic reports không được dùng làm gold evidence.
& $python -B -m pytest .\tests\test_official_harness.py -q -p no:cacheprovider
$LASTEXITCODE

# Xác minh cached inputs thật và ghi preflight. KHÔNG có --execute.
# Không đủ runtime: dự kiến exit2, BLOCKED, 3task NOT_RUN; không phải test regression FAIL.
$parquet = 'D:\Project\CAPSTONES\M2_week_5_6\data\downloads\c104f840cc67f8b6eec6f759ebc8b2693d585d4a\test-00000-of-00001.parquet'
& $python -B -m vgar.evaluation.harness.official --dataset-parquet $parquet
$LASTEXITCODE

# Chọn terminal run mới nhất ở output-root mặc định; không nhập UUID bằng tay.
$record = Get-ChildItem .\results\m1\w9\m1-w9-4\runs -Filter run_record.json -Recurse -File |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $record) { throw 'Chưa có terminal run; kiểm session trước khi chạy lại.' }
$result = Get-Content -Raw -Encoding UTF8 $record.FullName | ConvertFrom-Json
$result | Select-Object run_id,mode,status,complete,resolved_count,duration_seconds
$result.preflight.blockers
$result.tasks | Select-Object instance_id,status,reason
```

Trên Linux đã provision đúng profile, shell entrypoint tương lai có dạng sau;
**không chạy trong phạm vi offline hiện tại**:

```bash
# VGAR_HARNESS_PYTHON là interpreter chạy wrapper; profile.python là interpreter
# harness dùng subprocess. Cả hai cần được provision; không tự động cài.
bash scripts/run_official_harness.sh --profile /absolute/path/qualified-profile.json
# Chỉ sau readiness thật PASS và được phép chạy qualification mới thêm --execute.
```

Shell dùng Bash và quoted argv. Windows drive paths phải đổi sang Linux paths
tương ứng trong profile khi chuyển WSL/Linux; không mặc định distro docker-desktop
là một Linux working environment đã setup Python. Phần offline không dựng môi trường
đó; phần local mới chỉ cài distro, chưa provision harness và đangBLOCKED như checkpoint.

Git Bash `-n` trên Windows đã PASS cú pháp. Thử bổ sung shell `--help` bằng Git
Bash + Windows Python có lỗi import path (`No module named vgar`), lưu
`bash_help.json`. Đây **không phải Linux shell execution PASS**; entrypoint hỗ trợ
Linux/WSL làm việc đã provision, chưa hỗ trợ MSYS→Windows Python path conversion.
Python module CLI trên Windows vẫn chạy được bằng các lệnh PowerShell ở trên.
Controller interpreter cần Python3.11+, Pydantic2 và pyarrow; harness interpreter
cần dependencies của pin riêng. Không tự cài trong shell entrypoint.

## 5. Output, trạng thái và thời gian

```text
results/m1/w9/m1-w9-4/<output-root>/<fresh-run-id>/
  reservation.json / profile.json / preflight.json / run_record.json
  preflight/                  command JSON + stdout/stderr nếu readiness cơ bản đủ
  inputs/                     dataset.json, predictions.jsonl, inputs.json
  <task-id>/
    record.json               process, report binding, cleanup, runtime-after
    harness.json / harness.stdout.log / harness.stderr.log
    runtime-after/            source/module/image recheck commands
    logs/run_evaluation/<invocation-id>/vgar-w9-gold/<task-id>/
      report.json / patch.diff / test_output.txt / run_instance.log / eval.sh
```

Các thư mục execution chỉ xuất hiện khi thực sự launch; không sinh raw logs giả
cho preflight BLOCKED. Raw reports nằm đúng invocation mới, tránh dùng nhầm cache.
Inputs có gold ignored; không push và không chuyển sang prompt/retrieval.

| Trạng thái | Ý nghĩa |
|---|---|
| RESOLVED | Process kết thúc hợp lệ, report đúng ID/strict booleans, applied patch khớp gold và cleanup/integrity đạt |
| UNRESOLVED | Harness report grading hợp lệ nhưng resolved=false; không suy từ exit code |
| ERROR | Report thiếu/hỏng/sai identity, patch mismatch, process lỗi hoặc cleanup/integrity lỗi |
| TIMEOUT | Owned subprocess hết deadline; không gọi là unresolved thông thường |
| BLOCKED | Không đủ prerequisites, chưa launch gold |
| NOT_RUN | Không execution hoặc dừng trước khi đến task này |

Run QUALIFIED cần ít nhất2/3 task RESOLVED, runtime/input integrity còn đúng;
task thứ ba vẫn được giữ cùng lỗi nếu có. CLI exit0: preflight đủ nhưng NOT_RUN,
hoặc QUALIFIED; exit2: BLOCKED; exit1: ERROR/UNMET. Luôn đọc cả mode/status,
không lấy exit0 để nói gold resolved. `complete=true` chỉ là record terminal.

Test timeout1800s/task; subprocess deadline3600s/task, một worker, không retry.
Timeout bên trong official harness có thể exit0 và không tạo report; wrapper
giữ TIMEOUT khi log đúng dấu timeout của pin và applied patch bytes khớp.
Mỗi command ghi UTC start/end/duration/stdout/stderr/exit/traceback. Build/pull/test
time chưa đo riêng để null, không tự suy từ tổng wall time. Cleanup không prune
hoặc xóa image chung; chỉ container có fresh name được xác nhận absent trước run
và inspect đúng name/image sau run. Process termination chỉ áp dụng child do wrapper tạo.
Trên Linux child có session/process group riêng, chỉ signal group do Popen này
tạo; timeout recovery/drain có bound5+5+1giây, ghi thời gian thực kể cả finalization.
Cleanup/recovery không an toàn thì dừng, không launch task sau hoặc QUALIFIED.
Input bị xóa/không đọc được cũng là ERROR với record task terminal, không còn
RESOLVED giả. Chưa kiểm kill/remove thật trên Linux/Docker trong phiên này.

## 6. Evidence và công việc chưa làm

Evidence QA: `results/m1/w9/m1-w9-4/20261023-offline/`: RED/GREEN, JUnit,
lint, Bash syntax và selected regression. Fixtures trong pytest dùng báo cáo
SYNTHETIC có nhãn rõ; command-capture tests dùng child Python nhỏ, không Docker.

Xem [receipt review độc lập](reviews/2026-10-23-m1-w9-4-offline-review.md) cho
năm findings và regression RED→GREEN. Review không thay external qualification.

| Kiểm tra đã chạy | Kết quả | File trong evidence QA |
|---|---|---|
| RED ban đầu |29errors missing-module; module chưa tồn tại |red.json / red.junit.xml |
| GREEN đầu |27PASS/2FAIL do test doubles raw hash/cleanup state; đã sửa setup, giữ guards |green.json |
| Runtime-after RED→GREEN |41PASS/1FAIL rồi42PASS |runtime_red.json / green2.json |
| Findings review RED→GREEN |42PASS/6FAIL rồi48PASS |review_red.json / review_green.json |
| Final selected regression |**426PASS,1SKIP**,69,44giây; không full suite |final_regression.json / final_regression.junit.xml |
| Ruff thực có0.16.5 |PASS, không qualification đúng pin0.17 |lint_final.json / ruff_version.json |
| Git Bash syntax |PASS; không gọi Linux execution PASS |bash_syntax.json |
| Git Bash+Windows Python --help bổ sung |exit1 import-path; giữ limitation MSYS rõ ràng |bash_help.json |
| Runtime versions |Python3.11.6,pytest8.4.2,pyarrow23.0.1 |versions_verified.json |
| Cache preflight thật cuối |BLOCKED/exit2; gold3taskNOT_RUN, không Docker/harness launch |actual_preflight_final.json và run directory ở §1 |

Một SKIP là filesystem symlink test cần quyền Windows; các test khác ngoài
selected group chưa chạy, không chuyển thành PASS. Raw artifacts/gold/logs ignored
được giữ local; clone code không mang theo các evidence lớn này.

Gold qualification local đã đạt ngày24/10/2026; xem báo cáo nghiệm thu và
checkpoint mới nhất. Các bảng offline phía trên giữ evidence lịch sử.
Không tự mua tài nguyên hoặc thay ba IDs. M1-W9-5/environment loop không thuộc
phần triển khai này. Full repository suite không được suy từ selected tests.

## Reference

Chỉ hỗ trợ pin đã đối chiếu, không suy format từ main mới hơn:

- [Official run_evaluation và CLI](https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/run_evaluation.py).
- [Local dataset/predictions loader](https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/utils.py).
- [Upstream grading/report semantics](https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/grading.py).
- [Image/container identities](https://github.com/SWE-bench/SWE-bench/blob/726c5461e2ef52d83cf1ea2107870a8bb3328d57/swebench/harness/test_spec/test_spec.py).
