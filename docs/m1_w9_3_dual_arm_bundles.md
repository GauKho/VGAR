# M1-W9-3 — Bundle graph và BM25 cho 5 task dev

Phạm vi: retrieval export và kiểm consumer, không generate/apply/test target,
không official harness. Quy trình M1-W9-3 được người dùng duyệt ngày23/10/2026.
Status/evidence cuối xem `docs/status/m1.md` và
[báo cáo nghiệm thu](m1_w9_3_acceptance_report.md): campaign cuối đã có10/10bundle
PASS và audit đọc lại PASS. Đây chỉ là retrieval handoff, không là repair PASS.

## 1. Inputs và profile đã chốt

| Input | Identity / quy tắc |
|---|---|
| Dataset | SWE-bench Verified snapshot c104f840cc67f8b6eec6f759ebc8b2693d585d4a |
| Population | 5dev tasks trong configs/m1/w9_pilot_manifest.json; recompute split từ ID và repo-round-robin, multi-file stratum |
| Query | problem_statement; không F2P/P2P/hints/test_patch/developer patch |
| Tokenizer | Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554; bốn assets hash khớp manifest |
| Token accounting | Encode từng exact snippet, no special tokens; sum=total; budget8000 cho mỗi arm |
| Resolver | Graph static; không SCIP/LSP/Jedi enrichment trong profile này |
| BM25 | Node-range profile W9, k1=1.2/b=0.75; cùng source-node filter với graph |
| Tests | Empty links/failing selectors; cùng baseline-discovered test-file fallback; collection_verified=false |
| Deadline | Mỗi task export worker600giây; ghi cả timeout/error, không tự đổi population |

Các task: astropy__astropy-13398, django__django-11138, matplotlib__matplotlib-14623,
pydata__xarray-3305, pylint-dev__pylint-4551. Base commits/query hashes nằm trong
manifest được sinh từ dữ liệu gốc; không lấy nguyên manifest25 cũ split=test.

Phân tầng multi-file dùng developer patch ở bước chọn dữ liệu; ghi selection policy
minh bạch. Gold metadata bị loại khỏi producer projection, không dùng để ranking,
allowlist source hay lựa chọn test. Đây là development pilot, không held-out.

## 2. Thành phần và flow

| Thành phần | Vai trò |
|---|---|
| evaluation/retrieval/pilot_manifest.py | Thin task projection, split/hash/population validation, tokenizer identity guard |
| evaluation/retrieval/bm25_handoff.py | BM25 core trên path/symbol/exact source ranges; no graph-edge scoring |
| evaluation/retrieval/pilot_export.py | Build graph một lần/task, export hai arm, gọi load_handoff thật |
| graph/handoff.py | Producer source/sidecar validation hiện hữu; thêm opt-in test_hint_policy=issue-only, default graph giữ nguyên |
| scripts/prepare_w9_pilot_inputs.py | Kiểm cached data/assets, sinh manifest pin, full checkout repo@commit |
| scripts/export_w9_pilot_bundles.py | Parent/worker,600s timeout, stdout/stderr, per-task records và run summary |
| configs/m1/w9_bundle_profile.json | Profile versioned; model/budget không thay ngầm |

```text
pinned Parquet → deterministic dev selection → no-gold task manifest
full Git source@commit + verified tokenizer
    → static graph baseline → graph issue-only retrieval / lexical BM25 node rank
    → exact snippets +8000-token packing
    → producer context/manifest/empty-test-links
    → M2 load_handoff + source/counter/identity checks
    → per-arm validation / per-task record /10-bundle run summary
```

Handoff nhận ba file bắt buộc: context.json, context_manifest.json, test_links.json.
repair-context.txt là output tiện đọc, consumer tự render lại từ DTO đã validate.
Arm nằm ở run/index ngoài bundle, không thêm field vào public ContextPayload.

BM25 anchor_ids=[] và graph_distance=0 là placeholder tương thích DTO; rationale
LEXICAL_BM25_NO_GRAPH_TRAVERSAL; confidence1 biểu thị binding bytes đã kiểm, không
phải xác suất relevance. Raw scores và omissions lưu riêng. Không lấy kết quả
windowed BM25 W5–6 như cùng profile thí nghiệm này.

Hai arm cùng inventory/filter, tokenizer và budget. Shared filter chỉ nhận node
có source range chính xác và chứa ít nhất một ký tự không phải whitespace.
File/Module rỗng không thể làm repair context hữu dụng, dù path của nó match query.
Graph có traversal/packing đặc thù hiện hữu; BM25 rank lexical, skip overlap và
item vượt cap. Không gọi đây
là phép so sánh chỉ thay đúng một trọng số. Shared graph build cost đo riêng; BM25
runtime không được báo như toàn bộ pipeline cost nếu bỏ qua preparation.

## 3. Trust, integrity và acceptance

`validate_manifest` kiểm self-hash, snapshot label, taskIDs/split và thin fields;
tự nó không xác minh nội dung issue/commit với Hugging Face. Preparation xác minh
raw cached Parquet, chọn tasks và tạo manifest chuẩn. Launcher còn so manifest
hash với bản đã pin trong repo; manifest recompute self-hash khác không tự thành
input được duyệt. Hash không là digital signature; thay manifest chuẩn cần amendment.

Tokenizer identity so với manifest Qwen đã duyệt, cho phép relocation assets;
LocalTokenizerCounter kiểm từng asset hash/size và runtime major/minor0.22.
Không dùng estimator bytes/4 cho real export. Full Git checkout HEAD và clean
status được kiểm trước/sau worker; consumer recheck Python inventory/sidecar hashes.
Không chạy code hoặc pytest của source repos. Raw dataset/cache/checkouts/bundles
ngoài Git; manifest/profile/script và summary nhỏ mới là artifacts bàn giao Git.

Một task chỉ PASS khi worker exit0, có finalized source integrity và cả hai arm
validate PASS. passed_bundles ghi per-arm validation; accepted_bundles chỉ tính
task finalize PASS. Run chỉ PASS khi cả hai đều10; complete=true không là PASS.
Worker hỏng JSON, runtime error hoặc timeout vẫn giữ đủ5task×2arm records.

8000 snippets không bảo đảm full repair prompt vừa6000 inputcap hiện tại. W9-3
không tăng cap hoặc gọi run_repair. Admission/env/session integration vẫn thuộc
M2-W9-3/4; test hints/fallback ở đây không chứng minh tests collect hoặc baseline qualify.

## 4. Chạy trên máy hiện tại bằng PowerShell

```powershell
# Vào root; chọn runtime đã kiểm tương thích tokenizer0.22 và Tree-sitter pin.
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = 'D:\Project\CAPSTONES\environments\vgar-week78-cuda\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Cần runtime export phù hợp, xem pyproject và tokenizer manifest' }
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')

# Chỉ định cache snapshot gốc và cache đúng tokenizer revision trên máy của bạn.
# Trên máy khác: download đúng snapshot/files và hashes trước, không cần model weights.
$datasetCache = 'D:\Project\CAPSTONES\M2_week_5_6\data\downloads\c104f840cc67f8b6eec6f759ebc8b2693d585d4a'
$tokenizerCache = 'D:\Project\CAPSTONES\.cache\huggingface\hub\models--Qwen--Qwen3-4B-Instruct-2507\snapshots\cdbee75f17c01a7cc42f958dc650907174af0554'

# Kiểm caches, materialize bốn assets, chuẩn bị full source checkouts.
# Đã có checkout đúng/clean thì tái kiểm, không fetch lại; không reset directory khác.
& $python -B .\scripts\prepare_w9_pilot_inputs.py --dataset-cache $datasetCache --tokenizer-cache $tokenizerCache --prepare-sources
if ($LASTEXITCODE -ne 0) { throw 'Inputs/source preparation chưa đạt, đọc lỗi trước export' }

# Chạy5task tuần tự; mỗi lần tạo thư mục run mới, in RUN DIRECTORY và RESULT.
& $python -B .\scripts\export_w9_pilot_bundles.py --manifest .\configs\m1\w9_pilot_manifest.json --profile .\configs\m1\w9_bundle_profile.json --tokenizer-manifest .\artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json
$LASTEXITCODE

# Tự tìm run mới nhất có terminal record, không dán UUID bằng tay.
$record = Get-ChildItem .\artifacts\m1\w9\bundles -Filter run_record.json -Recurse -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $record) { throw 'Chưa có terminal record; kiểm session đang chạy trước khi launch lại' }
$result = Get-Content -Raw -Encoding UTF8 $record.FullName | ConvertFrom-Json
$result | Select-Object status,complete,passed_bundles,accepted_bundles,expected_bundles,duration_seconds,output_directory
$result.tasks | Select-Object task_id,status,exit_code,timed_out,duration_seconds
```

Khi có process đang chạy, đọc logs/run directory; không launch trùng để “xem tiến độ”.
Trên máy khác, runtime host có thể khác target repo; đây chỉ export, chưa env pytest
cho SWE-bench. Không cài whole CUDA environment chỉ để chạy tokenizer nếu dùng được
environment tối thiểu đáp ứng dependencies; ghi phiên bản thực, không tự gọi qualified.

## 5. Output và evidence

```text
artifacts/m1/w9/bundles/<run-id>/
  pilot_manifest.json / profile.json / run_record.json
  <task-id>.json / <task-id>.stdout.log / <task-id>.stderr.log
  <task-id>/
    graph.json / graph-retrieval.json / bm25-retrieval.json
    graph/ và bm25/ mỗi nơi có ba sidecars + repair-context.txt
    graph-validation.json / bm25-validation.json
    export_record.json / worker_result.json
```

Test/QA evidence root: `results/m1/w9/m1-w9-3/20261023-export/`, không overwrite.
Các stage RED/GREEN giữ cả failures: module thiếu, GraphError expectation, controller
malformed JSON, nonzero worker exit và tokenizer identity. Reviewer độc lập là code
QA, không M3 approval; exception review W9-1 không áp dụng task này.
Số test cuối/result pilot thực tế được ghi vào status và summary sau chạy.

## 6. Lỗi tìm thấy trong pilot và cách xử lý

Campaign `20261023T065655Z-37324a98e210` giữ nguyên để đối chiếu: graph5PASS,
BM25 5ERROR. Nguyên nhân là một số File/Module có range source rỗng hoặc chỉ
whitespace vẫn được lexical rank nhờ tên/path; producer tạo item0token và consumer
đúng khi từ chối bằng lỗi `Repair context must contain usable source snippets`.
Đây không phải timeout, thiếu weights hoặc lỗi Qwen/tokenizer.

Hai tests empty/whitespace và một paired-export test đã tái hiện RED, sau đó sửa
chung eligibility của **cả graph lẫn BM25** trước khi chạy campaign mới. Giữ nguyên
validator, DTO, bytes/ranges, model/tokenizer, budget8000, population và static
resolver. Runtime không được thay trong khi campaign đang chạy; không ghép graph
PASS của campaign cũ với BM25 của campaign mới để nghiệm thu.

Regression sau sửa: **391 PASS, 1 SKIP, 2 deselected**, Ruff PASS. Một SKIP là
filesystem symlink cần quyền Windows; hai exclusions là
`test_baseline_to_repair_and_static_evidence` và
`test_verify_patch_equals_tests_then_completion`, cần tokenizer qualification
riêng của W7–8. Provision tokenizer cho W9 export không đồng nghĩa hai tests đó
đã chạy. Đây là selected regression, không phải full repository suite.

Giữ đầy đủ evidence `empty_source_red.json`, `shared_empty_red.json`,
`empty_source_green.json`, `post_filter_regression.json` và
`post_filter_lint_green.json` trong evidence root nêu trên.
