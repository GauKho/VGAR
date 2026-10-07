# Vận hành retrieval evaluation tích hợp tuần 5–6

Tài liệu khớp code cập nhật 06/10/2026. Không triển khai research tuần 1–2, model inference, fine-tune, full repair hoặc tuần 7–16.

## 1. Đang chạy cái gì?

BM25: function/code chunks → rank → shared gold mapping/scoring. Graph: repository snapshot → task anchors/overlay → graph retrieval → cùng scorer. **Không gọi LLM**, không sinh/apply patch. Developer patch chỉ dùng sau ranking để chấm retrieval. PASS của unit/smoke không chứng minh đã repair một SWE-bench task.

Thông số đang khóa:

| Nội dung | Giá trị |
|---|---|
| Manifest chính | `data/manifests/verified-c104f840cc67-dev-25.json` |
| Dataset revision | `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` |
| Split/query | dev; problem_statement only, không hints/gold |
| Tokenizer | Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554 |
| Counter assets | `artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json` |
| Snippet budget | 8.000 token, không phải toàn prompt |
| Shared scorer | `retrieval-scoring-v1`; header, tối đa 80 dòng, overlap skip policy |
| Graph benchmark chính (người dùng duyệt 07/10/2026) | max_hops=2; max_candidates=100; **--no-jedi**, Tree-sitter + resolver nội bộ |
| Execution | một subprocess/task, 300s/task mặc định, không worker song song |

App/builder vẫn mặc định bật Jedi; chỉ benchmark chính dùng `--no-jedi` theo quyết định người dùng. Pilot Jedi đã timeout 0/3 và được giữ làm evidence riêng, không lẫn với no-Jedi khi resume/claim. Pilot no-Jedi `20261007T013925676777Z-55ae5fb6a24a` đã SUCCEEDED 3/3, nên đủ điều kiện chạy dev25 cùng profile. Không có Jedi fallback có thể giảm độ bao phủ CALLS; không tuyên bố resolver đạt đầy đủ. `--allow-fallback-counter` chỉ diagnostic synthetic fixtures, không cho comparison chính thức. M1 native snippet context khác scorer packing; xem [ADR](adr/2026-10-06-stateless-task-handles-and-context-boundary.md).

## 2. Setup một lần, tránh cài lại mỗi lần

Chạy từ root VGAR, dùng Python 3.11–3.13 theo pyproject. Nếu đã có `.venv` hợp lệ thì không tạo/cài lại.

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR' # MỖI phiên: chỉnh path nếu máy khác.
$env:PYTHONUTF8 = '1'                    # MỖI phiên: UTF-8 output.
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path # MỖI phiên: bind interpreter rõ ràng.
& $python --version                     # CHECK, không cài gì.
```

Nếu chưa có venv/dependencies, chỉ chạy **lần đầu**:

```powershell
py -3.11 -m venv .venv                  # LẦN ĐẦU, không ghi đè venv đang hoạt động.
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]' # LẦN ĐẦU hoặc khi dependencies thay đổi.
```

Máy triển khai đợt fix dùng interpreter `..\vgar_mcp_mvp\.venv\Scripts\python.exe` đã cài sẵn, **chỉ mượn interpreter, không sửa hệ thống cũ**. Evidence ghi đường dẫn này là đúng sự thật; code/cwd/root vẫn là VGAR. Team clone nên có venv riêng. Vì setup cài đầy đủ pyproject có torch/model dependencies, riêng retrieval không cần load weights/CUDA; không kết luận GPU là bắt buộc.

Chỉ tạo `.env` nếu chưa có, không overwrite secrets. Source archives, downloads và tokenizer assets không tự xuất hiện sau clone; thiếu dữ liệu báo rõ. Không tự thay pin/revision để né lỗi. Máy đợt fix thiếu bundle tokenizer (manifest vẫn có), nên đã provision lại đúng bốn files/15.880.703 bytes, không weights; evidence ở PROGRESS.

Nếu clone mới thiếu assets, chỉ chạy bước **LẦN ĐẦU khi có mạng**, manifest provisioning mới không ghi đè acceptance manifest cũ:

```powershell
$provisionManifest = Join-Path '.\artifacts\m1' ('tokenizer-provision-' + [guid]::NewGuid().ToString('N') + '.json')
& $python scripts\provision_m1_tokenizer.py --model-id 'Qwen/Qwen3-4B-Instruct-2507' --revision cdbee75f17c01a7cc42f958dc650907174af0554 --assets-root artifacts\m1\tokenizers --manifest $provisionManifest
if ($LASTEXITCODE -ne 0) { throw 'Provision tokenizer không thành công; không chạy benchmark.' }
```

Provisioner verify upstream commit/blob/hash. Bundle nằm đúng đường dẫn mà acceptance manifest tương đối đã chỉ; retrieval tiếp tục dùng acceptance manifest cũ, không thay hash/protocol. Nếu máy đã có bundle đúng hash thì không cần chạy lại.

## 3. Kiểm fixture trước benchmark

```powershell
& $python scripts\record_m2_test.py tests --task-id integrated-w3-w6-check --timeout-seconds 240 --preflight-timeout-seconds 30
$LASTEXITCODE                            # ĐỌC NGAY, 0 khi test PASS.
& $python scripts\smoke_w3_w4_full.py --strict-resources # Full fixture/MCP/test, không LLM.
$LASTEXITCODE
& $python scripts\smoke_w5_w6.py --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json # Context qua transport, không model.
$LASTEXITCODE
```

M2 recorder tạo JSON ở `artifacts/m2/test-runs`, kể cả setup/timeout errors. W6 script in `run: <folder>` ngay từ đầu, mặc định lưu dưới `artifacts/fixes/w3-w6`. W6 result có calls/responses, audit JSONL, SQLite graph, graph.json, context.json, CONTEXT.md, original/fixture hashes. Không tự xóa run lỗi.

## 4. Pilot 3 task trước dev25

```powershell
& $python scripts\run_graph_retrieval.py . data\manifests\verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --budget-tokens 8000 --task-id django__django-11138 --task-id matplotlib__matplotlib-14623 --task-id pydata__xarray-3993 --task-timeout-seconds 300 --offline --rebuild-trees --no-jedi
$LASTEXITCODE
```

`--offline` không download source: cần cache đã có. Pilot đã chọn ba nhóm lỗi lịch sử: Django11138 (MemoryError/repo lớn), matplotlib14623 (snapshot mismatch), xarray3993 (saved success). Task thiếu archive là LOAD_SOURCE error, không phải graph accuracy/RAM failure. `--limit 3` chỉ lấy ba task đầu manifest, không đảm bảo đúng ba nhóm lỗi; có thể dùng cho quick smoke nhưng không thay pilot nghiệm thu đã chọn. Không sửa manifest hoặc dùng held-out để debug/tune.

**Cache sau clone trên Windows:** source trees đang tracked có thể bị Git core.autocrlf chuyển LF→CRLF; bytes không còn khớp archive marker. Đợt nghiệm thu đã tái hiện đúng lỗi này, không phải MemoryError. Thêm `--rebuild-trees` vào lệnh pilot/dev25 nếu gặp EXTRACT_TREE integrity mismatch: giải nén archive đã verify sang tree mới `data/repositories/trees/rebuilt/<uuid12>`, giữ tree cũ nguyên trạng, không normalize bytes/bỏ hash guard. Namespace ngắn tránh MAX_PATH; repo/SHA vẫn kiểm trong marker/cache identity. Các tree runtime mới đã gitignore. Mỗi task rebuild tạo thư mục mới, tốn thêm disk; `source_tree.path` chỉ ra path dùng thật. `--rebuild-graphs` là option khác, không tự chữa source tree hỏng. Khi resume, giữ rebuild-trees flag giống run gốc.

## 5. Chạy dev25 và comparison

Chỉ chạy sau pilot3 đạt hoặc đã có quyết định xử lý failures được ghi rõ:

```powershell
& $python scripts\run_graph_retrieval.py . data\manifests\verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --budget-tokens 8000 --task-timeout-seconds 300 --offline --rebuild-trees --no-jedi
$LASTEXITCODE
```

Graph run in folder ngay từ đầu; chờ result.complete=true và đọc status/task statuses. 300s ×25 = tối đa khoảng125 phút cho task deadlines, **không phải dự đoán latency**; setup/cache I/O ngoài deadline riêng còn tốn thời gian.

BM25 baseline đã có 25 task ở hai run lịch sử. Chỉ reuse sau comparator kiểm cùng dataset/query/corpus/base/gold/counter/budget/scorer/snippet policy; đừng chạy lại baseline chỉ vì timestamp cũ. Nếu cần run mới:

```powershell
& $python scripts\run_bm25_retrieval.py . data\manifests\verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --budget-tokens 8000 --offline
$LASTEXITCODE
```

Chọn **hai run complete cùng population** tự động (không chọn nhầm smoke). Graph complete có thể là PARTIAL_FAILURE: vẫn so sánh các valid pairs và báo tất cả failures, **không gọi gate25 là hoàn tất**.

Historical JSON cũng có thể bị Git LF→CRLF làm sai raw artifact hash. Đợt này đã phục hồi **bản sao** từ Git blob đúng hash, không thay checkout/recorded hash, không chạy lại BM25: [evidence 25/25](../artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/result.json). Bản sao vẫn mang timestamp/run_id/measurement metadata cũ. Selector sau tìm cả run thường và bản sao đã kiểm, từ chối artifacts có bytes không khớp. Không normalize JSON để né hash guard.

```powershell
$runDirectories = @(Get-ChildItem '.\results\retrieval' -Directory)
$recoveryRoot = '.\artifacts\fixes\w3-w6\manual10-no-jedi\baseline-recovery'
if (Test-Path -LiteralPath $recoveryRoot) {
    $runDirectories += @(Get-ChildItem $recoveryRoot -Directory | ForEach-Object {
        $recovered = Join-Path $_.FullName 'recovered-run'
        if (Test-Path -LiteralPath $recovered) { Get-Item -LiteralPath $recovered }
    })
}
$runs = @($runDirectories | ForEach-Object {
    $path = Join-Path $_.FullName 'result.json'
    if (Test-Path -LiteralPath $path) {
        $r = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json
        if ($r.complete -eq $true -and $r.task_results.Count -eq 25) {
            $validArtifacts = $true
            foreach ($task in $r.task_results) {
                $taskPath = Join-Path $_.FullName ('tasks\' + $task.instance_id + '.json')
                if (-not (Test-Path -LiteralPath $taskPath) -or -not $task.artifact_hash) {
                    $validArtifacts = $false; break
                }
                $actual = 'sha256:' + (Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actual -ne $task.artifact_hash) { $validArtifacts = $false; break }
            }
            if ($validArtifacts) {
                [pscustomobject]@{ Directory=$_.FullName; Kind=$r.kind; Status=$r.status; Started=$r.started_utc; UseJedi=$r.config.graph.use_jedi }
            } else {
                Write-Warning ('Bỏ qua run có artifact hash không khớp: ' + $_.FullName)
            }
        }
    }
})
$bm = $runs | Where-Object { $_.Kind -eq 'retrieval' -and $_.Status -eq 'SUCCEEDED' } | Sort-Object Started -Descending | Select-Object -First 1
$gr = $runs | Where-Object { $_.Kind -eq 'retrieval_graph' -and $_.UseJedi -eq $false } | Sort-Object Started -Descending | Select-Object -First 1
if (-not $bm -or -not $gr) { throw 'Chưa có đủ hai run complete 25 tasks với artifacts đúng hash. Không bỏ guard.' }
& $python scripts\compare_graph_vs_bm25.py . $bm.Directory $gr.Directory
$LASTEXITCODE # 0=đủ pairs; nonzero=zero/partial/guard rejection, không coi như PASS.
```

Primary BM25 là **full saved rank**. `--bm25-cap N` chỉ thêm rank-only sensitivity, không repack context và không giả packed/token metrics là capped-system. `graph_f2p` là oracle-assisted FAIL_TO_PASS, tách riêng issue-only `graph`. Nếu thiếu valid pairs, report vẫn giữ attempts/status/denominators, không xóa task lỗi cho số đẹp.

Manifest raw hash có thể khác giữa checkout LF/CRLF; không nói hai manifest nguyên bytes giống nhau nếu không đúng. Comparator phải kiểm dataset revision/split, cùng task population và per-task query/corpus/base/gold/patch cùng protocol; recovery giữ nguyên saved manifest hash, không giả hash mới. Source/task artifact hashes vẫn exact raw bytes. Patch text hash theo universal-newline policy của evaluator, khác raw patch-file hash; hai loại không được tráo.

## 6. Evidence và resume

```text
results/retrieval/<new-run>/
  result.json                 config/source identity, summary, statuses, timing
  tasks/<instance_id>.json    canonical task artifact + hash trong summary
  attempts/<id>/<uuid>/       attempt riêng, không overwrite attempt cũ
    request.json              input/config; gold path không được đưa vào ranking
    result.json               pending → terminal do parent quản lý
    telemetry.json            phase + durations + worker peak RSS
    worker-result.json        kết quả/trace do worker trả
    stdout.log, stderr.log    log đã capture; quá limit báo ERROR, log vẫn giữ
```

Gold file chỉ mở trong SCORE sau retrieval. Source archive/tree/graph cache đều có hash checks. Cache hỏng bị từ chối; `--rebuild-graphs` tạo **pair mới**, không ghi đè pair cũ. Tree unowned/partial không tự bị xóa. Rebuild pair mới không tự sửa pair cache cũ hỏng; lần sau vẫn cần explicit rebuild hoặc người quản lý chọn cache root mới sau khi giữ evidence.

`--resume-run <folder>` tạo **run nối tiếp mới**; không sửa folder cũ. Success được copy nguyên bytes sau hash/identity checks; failure chạy attempt mới. Config/manifest/code fingerprint/root/tokenizer/F2P phải khớp. Legacy run không có resume identity bị từ chối. Giữ cùng flags/counter/profile/subset; source code thay đổi thì cần run mới, không trộn measurements.

Ví dụ dùng biến `$gr.Directory` vừa chọn, với flags giống run đó:

```powershell
& $python scripts\run_graph_retrieval.py . data\manifests\verified-c104f840cc67-dev-25.json --tokenizer-manifest artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json --budget-tokens 8000 --task-timeout-seconds 300 --offline --rebuild-trees --no-jedi --resume-run $gr.Directory
$LASTEXITCODE
```

Parent bị hard kill/mất điện không thể finalize ngay; pending artifact còn đó. Đừng gọi complete=false là PASS. Worker timeout/crash/MemoryError khi parent còn sống được finalize với failing phase/trace/logs. RSS = max(worker-reported peak, tree RSS được parent quan sát mỗi0.5s); không phải virtual memory/GPU VRAM, và sampled timeout có thể bỏ lỡ spike giữa hai samples.

## 7. Đọc metrics và giới hạn kết luận

- File/function Recall@k: phần gold entity tìm được trong k kết quả sau dedup **ở cùng level**; không phải repair pass rate.
- MRR: reciprocal rank của gold entity đầu tiên; 0 khi không tìm được, null khi không đủ gold labels.
- Packed coverage: gold source range thực sự nằm trong context đã pack; không chỉ xuất hiện trong full ranking.
- Context tokens: shared-scorer packed token cost; native M1 token count ở diagnostics là policy khác.
- Mapping/unmapped/function-label completeness: label không ánh xạ được phải được báo; metric denominator loại ineligible cases chứ không biến missing labels thành0 hoặc successful hits.
- CI/bootstrap/wins/ties/losses là paired comparison trên valid pairs; sample25 nhỏ, không leaderboard hoặc chứng minh Graph luôn thắng.
- latency/RSS/build time giúp phân biệt LOAD_SOURCE/EXTRACT_TREE/BUILD_GRAPH/GROUND/RETRIEVE/SCORE/WRITE. **Không** suy ra mọi error là thiếu tài nguyên nếu chưa đọc trace.

API inference cost của flow này:0 USD do inference NOT_RUN. CPU/RAM/disk hoặc thuê máy vẫn có chi phí riêng. Unit pass không thay cho retrieval25, manual audit10, environment readiness50–100 hoặc sign-off của nhóm.

## 8. An toàn và bàn giao

MCP workspace lease chặn read/write/exec vào root khác theo capability policy. Đây **không** là container/OS sandbox. Chạy pytest trong repo bên ngoài có thể chạy arbitrary host code; biến môi trường bị lọc không chứng minh filesystem secrets không thể bị đọc. Không cài dependencies mọi SWE-bench repo vào cùng venv, không execute external repos trong đợt retrieval này.

Đối chiếu tiến độ ở [PROGRESS](../PROGRESS.md) và [nghiệm thu](w5_w6_completion.md). Kết quả07/10: [dev25no-Jedi](reviews/2026-10-07-dev25-no-jedi-results.md) 19success/6failures, comparator19pairs/exit1, dưới20 nên benchmark gate chưa đạt; [manual10](reviews/2026-10-07-manual-retrieval-audit-10.md) self-audit đã hoàn tất. Không suy ra mọi gate PASS từ code/full suite359passed/4skipped. Không retry task lỗi hoặc chạy environment excluded. Code host binding thay đổi sau terminal, nên sourcefingerprint cũ không còn khớp checkout cho resume; cần quyết định/run mới khi được mở lại, không sửa identity hoặc bypass guard.
