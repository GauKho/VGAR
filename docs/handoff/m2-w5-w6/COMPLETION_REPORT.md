# Báo cáo triển khai M2 tuần 5–6

Kế hoạch được duyệt: `New_task/2026-10-13-hoan-thien-m2-w5-w6-cx-mp-ct.md`.
Target: `D:\Project\CAPSTONES\VGAR`, baseline HEAD `73814b8f89666c71b1911e42e98b8ecc7f6e3e99` + diff M2. Không commit/push. Không thực thi các kế hoạch đã đóng băng.

## 1. Phạm vi và cách hiểu kết quả

Tuần 5–6 của M2 có bốn task: BM25 trên code/function chunks; gold labels từ developer patch; retrieval evaluation 20–30 tasks; phối hợp M1 debug context/gold mapping. Hai task đầu đã có implementation; lần này không viết lại chúng.

**Retrieval evaluation không phải repair:** pipeline tìm context và đo mức bao phủ các file/function được developer sửa. Không gọi LLM, không tạo/apply patch, không chạy tests bên trong SWE-bench repositories. Không có kết luận resolved/pass@1 từ các số retrieval.

**Trạng thái cuối:** M2-03 chuyển CX → HT theo gate đã duyệt: attempted25,22valid primary pairs có raw/report/hashes. BM25 25/25 thành công; Graph 22/25 thành công,3timeout (PARTIAL_FAILURE/exit1), **không phải25/25PASS**. M2-04 vẫn MP đến khi chủ task M1 review; agent không ký thay. Hai task M2-01/02 giữ HT.

| Task | Trạng thái | Đã đạt / còn thiếu |
|---|---|---|
| W05-06-M2-04 | MP — xếp trước vì chưa đóng | Consumer tests/proof/diagnostics và hồ sơ handoff đã đủ kỹ thuật; thiếu xác nhận người phụ trách M1 |
| W05-06-M2-03 | HT trong phạm vi evaluation |25attempted/22validpairs ≥20;3timeouts công bố; không có claim repair/resolved |
| W05-06-M2-01 | HT — giữ | BM25 baseline không viết lại/tune; regression pass |
| W05-06-M2-02 | HT — giữ | Gold extractor không viết lại; regression/mapping guards pass |

## 2. Những thay đổi và nơi triển khai

| File/phần | Trước | Sau | Vì sao cần |
|---|---|---|---|
| `src/vgar/evaluation/retrieval/compare.py` | Chỉ kiểm query/corpus/base_commit giữa hai task | Thêm `patch_hash` vào guard | Cùng issue/source nhưng developer labels khác không được coi là cùng phép so sánh |
| `src/vgar/evaluation/retrieval/scoring.py` — `CorpusIndex.resolve_function` | Single definition khớp tên có thể map bất kỳ range | Path + qualified name + containment bắt buộc | Tránh function recall giả khi source span sai |
| Cùng file — `_source_line_span` / `graph_rank` | Default range thiếu thành dòng1; không kiểm native byte columns | Kiểm kiểu, thứ tự, bounds, UTF-8 boundaries; exclusive end; legacy line-only hợp lệ vẫn hỗ trợ | Ngăn malformed source binding; end_col0 không kéo dòng/function kế tiếp |
| `tests/m2/test_context_gold_handoff.py` | Chưa có | 24 cases consumer/identity/source-range | Regression cho lỗi đã reproduce; fake word counter chỉ dùng unit tests |
| `docs/handoff/m2-w5-w6/` | Chưa có hồ sơ đợt này | Protocol/ledger/handoff/blockers/report | Cho M1 review và khôi phục checkpoint |
| `PROGRESS.md`, `Task Status.md` | Trạng thái cũ | Chỉ cập nhật tiến độ/ID M2 được nghiệm thu | Không tick ownership khác |

Không sửa M1 graph builder/resolver/ranking/schema, MCP, model/repair, BM25 parameters, gold extractor, global fingerprint/cache policy. Không thêm third-party model runtime.

Range không hợp lệ bị bỏ khỏi scoring, giữ `unmapped` item-level `INVALID_SOURCE_RANGE`; không cấp file/function hit cho context không gắn được source. Range hợp lệ nhưng tên không map vẫn có file-level item, function_id=null. Đây là diagnostic phía M2, không đổi error/schema public của M1.

## 3. Inputs, profile và tài nguyên thực dùng

| Input/profile | Giá trị và đường dẫn |
|---|---|
| Dataset | `princeton-nlp/SWE-bench_Verified` @ `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` |
| Manifest25 | `data/manifests/verified-c104f840cc67-dev-25.json`; SHA256 `9ce4e3bdc805d140d13af00253970b3c38c919f7424e363efb27c4dd9891f754` |
| Selection | Dev splitter hiện có; ≥2 production Python files trong developer patch; round-robin25. 500 raw →208 dev/292 heldout →28 eligible dev →25 selected. Không thay tasks sau khi biết kết quả |
| Source | `data/repositories/archives/` tại base_commit từng task; không apply gold/test patch để index |
| Cache reuse | Verified parquet +10 matching archives reuse;15 archives còn thiếu fetch/verify. `source_cache_receipt.json`, `source_fetch_progress.json` ghi provenance |
| Primary query | Chỉ problem_statement; không hints, gold paths/patch, FAIL_TO_PASS |
| Primary arms | Full BM25 k1=1.2/b=0.75 vs Graph static issue-only,2hops/100candidates |
| Shared packing | 8000 tokens,80 snippet lines/header=true/overlap skip; ranking và packed là hai phép đo khác nhau |
| Tokenizer | Qwen3-4B-Instruct-2507 @ cdbee75f17c01a7cc42f958dc650907174af0554; chỉ tokenizer, không weights/inference |
| Counter manifest | `artifacts/m2/w5-w6/tokenizer_manifest.json`;4 assets verified dưới `artifacts/m1/tokenizers/` |
| Interpreter | `.venv-m2-w5-w6/Scripts/python.exe`, Python3.13.0, tokenizers0.22.1. Root venv0.23.1 không bị downgrade |
| CPU/runtime | Graph một worker/lần,300s/task; BM25/Graph tuần tự. Không cần GPU, API key hoặc Docker |

`graph_f2p` dùng oracle test names từ dataset chỉ là diagnostic. BM25 capped100 cũng chỉ diagnostic; không đổi chúng thành primary arm/ablation A0–A3. `provisional_m3_alignment` trong manifest vẫn giữ nguyên: không tự nhận M3 split approval.

## 4. Flow từ đầu đến cuối

```text
Pinned dataset → manifest25 (IDs/base_commit/issue/developer patch)
                      │
          verified pre-patch source archives
                      │
       ┌──────────────┴───────────────────┐
       │                                  │
 AST/code chunks → BM25(issue)    M1 static graph → anchors(issue)
       │                                  │
       │                         candidate order + node document
       │                                  │
       └──────── M2 canonical RankRecord ──┘
                     rank frozen
                         │
 developer patch → gold-file/function proxy → shared scoring
                         │
 task JSON + run JSON + statuses + hashes + timings
                         │
 paired compare (identity/config/counter guards)
                         │
 REPORT.md + >=20-pair acceptance receipt + M1 handoff
```

Source files được parse, không import/execute code repository. Developer patch tham gia chọn eligibility/chấm labels, không tham gia primary retrieval. Retrieval miss/no anchor là kết quả hợp lệ0; gold/function labels không đủ là ineligible/None, không đổi thành0. Failures/timeouts giữ trong attempted population và báo cáo riêng, không trộn vào mean như score0.

## 5. Các kiểm thử đã thực hiện

| Nhóm | Evidence | Kết quả/phạm vi |
|---|---|---|
| RED patch identity | `artifacts/m2/test-runs/20261013T112504100380Z-49c006ef1b4b464fae4baa5ced28c19b.json` | 1fail/1pass; đúng guard thiếu trước sửa |
| RED range containment | `20261013T113403752051Z-4960ccc60659477e91d87cd290ea4c38.json` cùng folder | 1fail/10pass; wrong source span trước sửa |
| RED exclusive end | `20261013T113744502165Z-199bc82d7a374225beacc79947aa0238.json` | 1fail; snippet kéo next function header |
| RED malformed span review | `20261013T115802447312Z-67c7be8e7cc44e5ea4232413c35573f0.json` | 12fail/12pass; thiếu/rỗng/zero-length/out-of-bounds/type/UTF-8 |
| GREEN sau sửa cuối | `20261013T115854955079Z-65e7f223162744848886560ea140285a.json` |121 passed:60 retrieval/consumer +61 native handoff cases; no skip |
| Regression cuối sau benchmark | `artifacts/m2/w5-w6/commands/20261013T125931577415Z-c5e38fe74935/result.json` |121passed/0failed/0skip trong5,47s, code source digest trước/sau không đổi |
| Actual producer proof | `artifacts/m2/w5-w6/native_handoff_final/result.json` |2 context items,47 snippet tokens,0unmapped; source unchanged; owner pending |

Test recorder lưu command/argv/cwd/interpreter/version, UTC start/end, duration, stdout/stderr, exit code, JUnit counters và source before/after. Dữ liệu nằm trong `test_result`, không phải top-level `stdout`. Không chạy full model test suite hoặc SWE-bench harness để đóng hai task retrieval.

Native proof dùng fixture `artifacts/m2/w5-w6/handoff_fixture/src/{auth,service}.py` qua producer M1 thật: PythonGraphBuilder → TaskOverlayBuilder → GraphContextRetriever → M2 mapping/scoring. Snippet-token total47 không đồng nghĩa fair-packed cost: headers/policy khiến con số khác. Context/graph/gold/scoring trong proof có thể mở đối chiếu.

Các setup failures cũng giữ receipt: sandbox socket WinError10013 rồi provision có quyền đã PASS; root tokenizers0.23.1 không phù hợp nên tạo isolated0.22.1; relative interpreter path WinError2 được sửa bằng absolute path. Không tính những lỗi setup đã xử lý này là failure của 25 SWE-bench tasks. Expected RED dùng để chứng minh regression bắt đúng lỗi, không phải lỗi còn tồn tại sau sửa.

## 6. Evidence evaluation hiện hành và lịch sử

Các runs trước review malformed-range được giữ, **không** dùng làm final profile: BM25 pilot `20261013T113922544857Z-71d031a5b567`, Graph pilot `20261013T114247160430Z-dbbca1352e5f`, paired pilot `20261013T114848575334Z-f3e4c1c72a48`, BM25 full25 `20261013T114849628933Z-e53bca69dacc` (25/25 succeeded).

Sau sửa cuối: preflight receipt `artifacts/m2/w5-w6/commands/20261013T120018413619Z-4b721297e455/result.json`; native proof command `20261013T120019234067Z-84d397fed368`; BM25 pilot `results/retrieval/20261013T120020961896Z-420d8af4121c` (3/3). Final references/metrics bổ sung khi terminal, không lấy “latest raw run” tùy tiện.

Graph pilot hiện hành `20261013T120150745677Z-4a1982129910` đạt3/3 (61.1s/76.1s/30.9s); paired pilot `20261013T120701552389Z-9f3e066ed941` COMPARED/3pairs. Một nested function ở Matplotlib có range hợp lệ nhưng không match canonical definition, được giữ file-level và ghi `NO_FUNCTION_MATCH`; không đoán function ID hoặc sửa M1 để tăng recall. Đây là mapping diagnostic, không phải task runtime failure.

BM25 run có `result.json`, `tasks/<instance_id>.json`, `REPORT.md`. Graph run có `result.json` và task JSON; CLI Graph không tự tạo standalone REPORT.md. Report so sánh nằm ở comparison folder riêng. `artifacts/m2/w5-w6/commands/<id>/result.json` lưu command stdout/stderr/exit/duration/source fingerprint. Expected RED và runtime/permission failures được phân loại riêng trong `UNFINISHED_TASKS.md`.

### 6.1. Final artifacts đã nghiệm thu

| Artifact | Path trong VGAR |
|---|---|
| BM25 final25 | `results/retrieval/20261013T120702363418Z-b067d65c7d70` |
| Graph final25 | `results/retrieval/20261013T121221258372Z-9ae258fd202e` |
| Primary/diagnostic comparison | `results/retrieval/20261013T125307312086Z-6d6b0b52b105/REPORT.md` và `result.json` |
| Acceptance receipt | `artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json` |
| Graph command/log | `artifacts/m2/w5-w6/commands/20261013T121220058318Z-8d130aa1cb78/result.json` |
| Comparison command/log | `artifacts/m2/w5-w6/commands/20261013T125300589016Z-2b06e48424e7/result.json` |
| Verification command/log | `artifacts/m2/w5-w6/commands/20261013T125342146736Z-c0170ebb1926/result.json` |

Receipt kiểm same manifest25/population/current source digest, nonfallback counter, budget8000, task artifact hashes, BM25/Graph run hashes, paired22 và per-metric N. Source digest cuối `sha256:f00423af0725e1539b89e00c9f7ab46588e37cb0810f8c6f44e7da005b8c8284`.

QA bàn giao: câu lệnh PowerShell nhanh ở mục7 đã chạy thực tế,121PASS/6,32s, receipt `commands/20261013T130531805480Z-8d827766d692/result.json`. `git diff --check` PASS tại `commands/20261013T130539105247Z-3f13b67e8193/result.json`. Task Status vẫn150IDs duy nhất/0duplicate; chỉM2-03 đổi trạng thái, aggregate37HT/55MP/26CT/32CX. Không đồng nhất QA mới này với audit full-suite cũ.

### 6.2. Primary metrics — cùng22 valid pairs, không so mean25 của BM25 với mean22 của Graph

| Metric | BM25 full | Graph issue-only | N |
|---|---:|---:|---:|
| File Recall@5 |0.537879|0.446970|22|
| Function Recall@5 |0.274621|0.315239|22|
| File MRR |0.578182|0.605395|22|
| Function MRR |0.428167|0.418428|22|
| Packed gold function coverage |0.445921|0.413724|22|
| Mean packed tokens |7997.909|7966.545|22|

Graph−BM25 File Recall@5 delta −0.090909, bootstrap95%CI[−0.291667;0.121212]; Function Recall@5 delta +0.040618,CI[−0.156818;0.249709]. Cả hai CI chứa0: **chưa có bằng chứng rõ để khẳng định Graph tốt hơn BM25 tổng quát**. Không tune profile/dataset để đảo kết quả. Graph có4unmapped diagnostics/22tasks; no-anchor count0 trong paired set, không suy số này cho3timeout chưa có retrieval output.

Ba skipped primary pairs: `sympy__sympy-16597`, `sympy__sympy-17318`, `sympy__sympy-20438`, mỗi task attempt1/300s. Biết task deadline vượt; chưa xác định bottleneck sâu do phase/RAM. Không xem chúng là retrieval score0. Paired set mất toàn bộ SymPy nên bị giới hạn khả năng suy rộng sang repository này.

Runtime thực: BM25 final286,388s (~4,77phút); Graph final2402,459s (~40,04phút), gồm3timeout. Graph3warm-cache/19successfulcold; pilot/setup overhead không cộng vào final task denominator. Model inference/API cost0.

### 6.3. Recorder cuối bị ngắt — giữ evidence, không sửa runner tuần3–4

Existing recorder hash toàn workspace trước/sau, gồm `data`, `results` và `.venv-m2-w5-w6`, nên final invocation sau khi cache tăng lớn hơn5phút chưa có terminal evidence. Chỉ dừng owned launcher22168 đã kiểm path/start time; child24956 kết thúc theo job, guard không stop PID khác. Không giả định pytest của invocation đó đã pass/fail.

Interruption receipt `commands/20261013T125931493926Z-ed28d248bb9f/result.json` và `clarification.json` giữ chi tiết/giới hạn. Chuyển sang **existing** `retrieval.evidence.record_command` để record targeted pytest trực tiếp; không sửa W3–4 fingerprint/runner. Final command log `commands/20261013T125931577415Z-c5e38fe74935/result.json` PASS121. Receipt này có code fingerprint/duration/stdout/stderr/exit; không có full-workspace before/after hash hay JUnit counter extraction, khác recorder cũ. Không đổi profile retrieval/test selectors.

Đọc runtime bằng `duration_seconds` của task/run. Với task warm-cache, `graph.build_seconds` là thời gian build được giữ từ cache gốc, không phải thời gian rebuild của invocation mới; xem thêm `graph.cached`, `cache_read_seconds`. Không cộng các historical build durations rồi gọi đó là wall time của final. Peak RSS nếu đo được nằm trong `tasks/<id>.json → memory`, không phải bằng chứng GPU inference.

## 7. Hướng dẫn kiểm lại trên máy hiện tại

### Mỗi PowerShell session — không cài lại môi trường đã qualify

```powershell
Set-Location 'D:\Project\CAPSTONES\VGAR'
$python = Join-Path $PWD '.venv-m2-w5-w6\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Chưa có interpreter retrieval đã qualify.' }
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = Join-Path $PWD 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'

# Chỉ kiểm, không tải model hoặc đổi package.
& $python -B '.\artifacts\m2\w5-w6\preflight.py'
if ($LASTEXITCODE -ne 0) { throw 'Preflight fail; xem lỗi, không fallback counter.' }

# Chạy regression nhanh bằng logger command có sẵn; source fingerprint chỉ code,
# không hash hàng chục nghìn source/cache files như recorder tuần3–4.
# Mỗi lần gọi tạo JSON mới với command/stdout/stderr/exit/duration/code hashes.
$selectors = @('tests/m2/test_context_gold_handoff.py','tests/m2/test_graph_arm.py','tests/m2/test_retrieval_eval_graph.py','tests/m2/test_retrieval_scoring.py','tests/m2/test_retrieval_evaluation.py','tests/m2/test_dataset_split.py','tests/test_m1_handoff.py')
& $python -B -c "import sys; from vgar.evaluation.retrieval.evidence import record_command; p,r=record_command([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',*sys.argv[1:]],'.','artifacts/m2/w5-w6/commands',timeout=300,kind='my-m2-w56-check'); print(p); print(r['stdout']); print(r['stderr']); sys.exit(r['exit_code'])" @selectors
$testExit = $LASTEXITCODE
if ($testExit -ne 0) { throw 'Test fail; giữ JSON recorder, không coi đó là PASS.' }
```

Nếu muốn định dạng `TestRunResult`/JUnit/full-workspace hashes như tuần3–4 thì existing `scripts/record_m2_test.py <selectors> ...` vẫn giữ nguyên, nhưng hash setup/cleanup không nằm trong pytest timeout300s và có thể rất chậm sau khi data/results tăng lớn. `record_final_regression.py` dưới artifacts chỉ ghi lại invocation của đợt triển khai này, có interruption lịch sử; không dùng nó làm reusable run script.

### Đọc kết quả nghiệm thu tự động — không nhập tên raw run

```powershell
# Chỉ chọn acceptance receipt đã kiểm cả population/source/hashes/gates.
$receiptFile = Get-ChildItem -LiteralPath '.\artifacts\m2\w5-w6\final-verification' -Filter result.json -Recurse -File |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $receiptFile) { throw 'Chưa có final acceptance receipt; xem PROGRESS.md.' }
$receipt = Get-Content -Raw -Encoding UTF8 $receiptFile.FullName | ConvertFrom-Json
if ($receipt.status -ne 'PASS') { throw 'Acceptance chưa PASS.' }
$receipt | Select-Object status,attempted,paired_tasks,owner_signoff
$receipt.counts | ConvertTo-Json
$comparison = Join-Path $PWD $receipt.runs.comparison
Get-Content -Encoding UTF8 (Join-Path $comparison 'REPORT.md')
$comparisonResult = Get-Content -Raw -Encoding UTF8 (Join-Path $comparison 'result.json') | ConvertFrom-Json
$comparisonResult.paired.graph | ConvertTo-Json -Depth 6
$graph = Join-Path $PWD $receipt.runs.graph
$graphResult = Get-Content -Raw -Encoding UTF8 (Join-Path $graph 'result.json') | ConvertFrom-Json
$graphResult.task_results | Select-Object instance_id,status,error_class,error,duration_seconds
```

Không chạy lại final25 nếu chỉ muốn xem kết quả. Khi chủ ý đánh giá lại, dùng existing run_bm25_retrieval.py / run_graph_retrieval.py / compare_graph_vs_bm25.py với cùng manifest/counter/profile; lưu paths mà mỗi script in ra. Graph không có `--resume`; không truyền flags Jedi/SCIP từ repo cũ. Cache chỉ reuse khi source/builder/profile hash khớp.

## 8. Phần bàn giao còn cần người phụ trách

Đọc `CONTEXT_GOLD_HANDOFF.md` và proof/current report, M1 xác nhận path/span semantics, order, source binding, unmapped policy và evidence source/config. Ghi người review/ngày/accept hoặc request changes. Sau đó mới chuyển `W05-06-M2-04` từ MP sang HT. Không cần triển khai tuần7–8/MCP/model để review consumer W5–6.

Chi phí API/GPU inference của đợt này:0; chi phí chủ yếu CPU/thời gian, disk source/graph caches và network tokenizer/source archives. Không khẳng định toàn VGAR hoặc toàn tuần5–6 đã nghiệm thu từ targeted tests này.

## 9. Giới hạn khi đưa số liệu vào báo cáo đồ án

- Đây là dev evaluation ban đầu25tasks theo week5–6, không phải final blind repair benchmark.
- Gold là code được developer thay đổi, không bảo đảm bao phủ mọi dependency/root cause. Function labels incomplete có mẫu số riêng.
- Graph static hạn chế ở dynamic calls, source qualification và canonical mapping; không đưa kết quả thành edge precision/recall.
- Paired means/CI chỉ mô tả những cặp đủ điều kiện; exclusions/timeouts có thể không ngẫu nhiên, phải xem toàn population và theo repository. Không suy luận Graph tốt hơn trên mọi repository từ một mean.
- Bootstrap task-level seed0/2000rounds là cách hiện có trong code, không phải clustered repository-bootstrap hay kiểm định sửa lỗi resolved/unresolved.
- Source fingerprint chung chưa hash nested `tests/m2`; acceptance receipt bổ sung hashes này. Không đổi cache policy M1.
- `retrieval-scoring-v1` được giữ theo protocol; source digest/run IDs phân biệt pre-fix/current. Chỉ dùng receipt xác minh source hiện hành, không ghép runs chỉ vì có cùng version string.
- Kết quả targeted121tests không chứng minh full-suite/MCP/model/repair của toàn VGAR đã không còn lỗi; các findings audit ngoài phạm vi được giữ nguyên.
