# Hướng dẫn M2 — Repair & Verification, tuần 5–6

## 1. Task của bạn thực chất làm gì?

Dù tên nhóm là Repair & Verification, công việc tuần 5–6 là **retrieval baseline và evaluation**, chưa phải sửa code. Cho một issue, hệ thống phải tìm các function/file có liên quan. BM25 là mốc so sánh để biết graph retrieval của M1 có hữu ích hơn cách tìm theo từ khóa hay không.

Bốn đầu việc: (1) BM25 trên function/code chunks; (2) chuẩn hóa gold-file/gold-function từ developer patch; (3) đánh giá ban đầu trên 20–30 SWE-bench task; (4) phối hợp M1 sửa context/gold mapping. DoD chung còn cần Graph vs BM25 và inspect ≥10 task.

Thư mục này độc lập; không sửa VGAR W3–4, không chạy lại hệ thống cũ. Không cần fine-tune, API key, GPU hoặc Docker để làm task này.

## 2. Input → xử lý → output

```text
HF Verified snapshot (revision cố định)
    → lọc patch ≥2 source Python files → khóa manifest 25 task
              ├─ problem_statement → QUERY (BM25 được nhìn)
              ├─ repo + base_commit → archive source trước khi sửa
              └─ developer patch → GOLD OFFLINE (BM25 không được nhìn)

source → AST function/method/nested/module chunks → BM25 index
query  → score/rank chunks → context dưới 4.000 estimated tokens
developer patch + base source → gold file/function + mapping events
ranking/context + gold → Recall@k/MRR/token cost → evidence JSON
M1 context thật + sidecar → validate → paired Graph vs BM25
```

Input cụ thể:

- `data/manifests/verified-c104f840cc67-25.json`: dataset ID/revision, 25 IDs/repositories/base commits/issues, hash query/patch, selection audit.
- `data/gold/patches/<instance_id>.patch`: developer patch để tạo gold labels. Không nhét vào query hay M1 request.
- `data/repositories/archives/<owner>__<repo>-<commit>.tar.gz`: source snapshot trước sửa; `.tar.json` cùng tên lưu URL, SHA256, commit.
- M1 export khi có: `data/m1_exports/<instance_id>.json`; format trong `M1_M3_HANDOFF.md`.

Sau mỗi run: `results/retrieval/<run_id>/result.json` là file tổng hợp; `tasks/<instance_id>.json` chứa chi tiết ranking, context, labels, events, metrics, source provenance; `m1_requests/<instance_id>.json` là output không chứa gold để gửi M1. Không có repaired repository/patch mới vì task này không sửa code.

## 3. Các thuật ngữ quan trọng

- **Chunk**: một phần code để tìm kiếm. Function dài được chia cửa sổ tối đa 80 dòng, overlap 16 dòng. Mọi cửa sổ giữ cùng `parent_id` để không tính một function nhiều lần.
- **AST**: cây cú pháp Python; dùng `ast.parse`, không import/chạy code của benchmark. Phân biệt function, method, nested function, decorator và code ngoài function.
- **Qualified name**: tên đầy đủ, ví dụ `auth.service.Auth.validate`; ID canonical thường là `path::qualified_name`, khác ID node của M1. Nếu hai AST definitions cùng qname (getter/setter, handler đăng ký lặp), thêm `@definition:start:end` để không tính nhầm function chưa sửa là gold.
- **Module chunk**: import, hằng số, class header/field hoặc code ngoài function. Giúp retrieval file; không được tính là function.
- **BM25**: xếp hạng theo tần suất từ khóa, độ hiếm của từ trong corpus và độ dài chunk. `k1=1.2`, `b=0.75`; IDF là `log(1 + (N-df+0.5)/(df+0.5))`. Không phải embedding/model train.
- **Tokenizer code**: giữ identifier đầy đủ và thêm phần snake/camel case; lowercase. Query term được dùng một lần trong score; không fine-tune tham số trên tập final.
- **Gold**: nhãn tham chiếu từ phần code developer thực sự thay đổi, không đồng nghĩa mọi code liên quan. File mới/function mới chỉ có sau patch không thể retrieve từ base.
- **Hunk relocation**: header diff đôi khi lệch line so với base. Chỉ căn lại khi old-context khớp exact duy nhất, ghi offset; không đoán match khi mơ hồ. Đọc events `hunk_relocated`/`unmapped` khi audit.
- **Recall@k**: tỷ lệ gold xuất hiện trong k file/function đầu tiên, sau dedup riêng từng cấp. Ví dụ gold có 2 files, top5 chứa 1 → Recall@5=0.5.
- **MRR**: 1/rank của gold đầu tiên; không có hit → 0. Gold không đủ điều kiện → N/A, không giả 0/1.
- **Mapping coverage**: tỷ lệ events diff xử lý được; module/new-function được phân loại không có nghĩa chúng trở thành gold function retrievable. Phải đọc cả dispositions và `function_labels_complete`.
- **Token budget**: giới hạn context bằng estimator bytes/4; bao gồm header path/symbol. Đây là ước lượng chung để so sánh, không phải actual LLM tokens.
- **Manifest**: danh sách task và dữ liệu đã khóa trước thí nghiệm. **Fingerprint/hash** nhận diện chính xác input/source/config. **Resume** chỉ tái sử dụng khi binding hash khớp.

## 4. Setup chỉ dành cho máy chạy lần đầu

Đã có venv trong folder hiện tại thì **bỏ qua toàn bộ mục 4**, sang mục 5. Thành viên clone folder này về máy khác mới cần setup.

```powershell
# LẦN ĐẦU: đi vào đúng folder, không phải VGAR/vgar_mcp_mvp.
Set-Location 'D:\Project\CAPSTONES\M2_week_5_6'
# LẦN ĐẦU: kiểm tra có Python 3.11/3.12/3.13.
py -0p
# LẦN ĐẦU: tạo venv riêng; đổi -3.11 thành phiên bản đã cài phù hợp nếu cần.
py -3.11 -m venv .venv
# LẦN ĐẦU: pyarrow chỉ để đọc dataset Parquet. Không cài torch/datasets/VGAR.
& '.\.venv\Scripts\python.exe' -m pip install pyarrow==23.0.1
```

Không cần `.venv\Scripts\Activate.ps1`: gọi executable trực tiếp tránh execution policy và lỗi biến `$python` chưa gán. Không cần `$env:PYTHONUTF8=1` cho pipeline vì file/subprocess encoding được chỉ rõ; có thể dùng nếu terminal của bạn gặp lỗi Unicode. Không đưa token/API key vào command/log.

## 5. Mỗi lần chạy — kiểm tra implementation

```powershell
# MỖI PHIÊN: chuyển thư mục.
Set-Location 'D:\Project\CAPSTONES\M2_week_5_6'
# MỖI PHIÊN: kiểm tra interpreter riêng, không cài lại.
& '.\.venv\Scripts\python.exe' --version
# KHI MUỐN KIỂM THỬ: chạy cả suite và lưu stdout/stderr/exit/duration/source hashes.
& '.\.venv\Scripts\python.exe' '.\scripts\record_tests.py'
# NGAY SAU TEST: 0 = tests PASS; giá trị khác cần xem Evidence JSON mà script in ra.
$LASTEXITCODE
```

File `results/tests/<run_id>/result.json`: `command_argv`, `cwd`, interpreter/version/platform, started/ended UTC, timeout, full stdout/stderr, exit code, duration, fingerprint. Test RED trong lịch sử là bằng chứng TDD, không phải trạng thái suite hiện tại.

Full suite cuối có 41 tests; gồm regression tests từ review và kiểm tra thư mục `testing/` của pytest được loại khỏi corpus. `tasks/<instance>.json` có `ranked_identity_order` chứa toàn bộ dedup file/function order để tái lập Recall/MRR kể cả gold ở xa ngoài 100 snippets được lưu. Resume kiểm tra cả hash file task và metadata, không chỉ manifest/config.

Có thể chạy riêng nhóm test (vẫn được ghi JSON):

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\record_tests.py' --pattern 'test_gold_boundaries.py'
```

## 6. Dataset — chỉ tải/chọn khi chưa có manifest

```powershell
# CHỈ LẦN ĐẦU / KHI CHỦ ĐÍCH TẠO SNAPSHOT MỚI: pin revision để tái lập.
& '.\.venv\Scripts\python.exe' '.\scripts\prepare_dataset.py' --count 25 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
```

Không bỏ revision để lấy latest khi cần so sánh với lần cũ. Dataset Verified là public, không cần quyền vào GitHub riêng của nhóm. Những repo benchmark cũng public. Bộ 25 hiện tại là pilot provisional; khi M3 gửi manifest chung, nhóm cần thống nhất IDs/commits/query policy trước khi chạy lại, không trộn bảng hai manifest.

## 7. Chạy retrieval smoke, pilot, đủ 25 task

```powershell
# SMOKE (3 task): kiểm tra đường đi thật, có thể tải archive lần đầu.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --limit 3
# PILOT (5 task): kiểm tra runtime/lỗi trước đợt 25.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --limit 5
# EVALUATION 25 task: không gọi LLM, không chạy pytest benchmark.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --budget-tokens 4000
# NGAY SAU RUN: exit 0 là pipeline retrieval hoàn tất, KHÔNG phải repair thành công.
$LASTEXITCODE
```

Nếu archives đã đủ, thêm `--offline` để không tải mạng. Mỗi run folder mới; cache nguồn dùng lại. Pipeline xử lý từng task tuần tự, không giữ toàn bộ repository graphs trong RAM. Thời gian gồm tải mạng + AST/index + ghi artifacts; số đo cụ thể nằm trong `duration_seconds`, `index_seconds`, `retrieval_seconds`, provenance source bytes/chunk count.

## 8. Xem kết quả

```powershell
# LẤY RUN MỚI NHẤT: kiểm tra nó completed/failed trước khi dùng trong báo cáo.
$run = Get-ChildItem '.\results\retrieval' -Directory | Sort-Object Name | Select-Object -Last 1
$result = Get-Content -Raw (Join-Path $run.FullName 'result.json') -Encoding UTF8 | ConvertFrom-Json
$result | Select-Object run_id,status,complete,exit_code,duration_seconds
$result.summary | ConvertTo-Json -Depth 6
# XEM CHI TIẾT 1 TASK THẬT.
$detail = Get-Content -Raw (Join-Path $run.FullName 'tasks\astropy__astropy-13398.json') -Encoding UTF8 | ConvertFrom-Json
$detail.gold | ConvertTo-Json -Depth 8
$detail.metrics | ConvertTo-Json -Depth 5
$detail.context | ConvertTo-Json -Depth 8
```

Macro mean lấy trung bình theo task đủ điều kiện; luôn báo eligible denominator và failed task count. Không loại task khó để cải thiện score. `function_labels_complete=false` thì function metrics N/A. Cần báo parse failures/corpus coverage, không diễn giải N/A là score tốt.

## 9. Resume sau gián đoạn

```powershell
# THAY bằng folder run cũ mà script đã in; giữ y nguyên limit/budget/manifest/source.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --budget-tokens 4000 --resume '.\results\retrieval\<RUN_ID_CU>' --offline
```

Resume tạo folder mới, đọc artifact đầy đủ của task đã SUCCEEDED; task lỗi/chưa chạy được thực hiện lại. Không chỉnh code/test/config giữa hai lần nếu muốn resume; hash mismatch → tạo run mới. Khi còn thiếu archive, bỏ `--offline`. Không chỉ sao chép summary vì mất context/gold/request.

## 10. Graph vs BM25 và bàn giao

```powershell
# SAU KHI M1 CUNG CẤP EXPORT THẬT: thay RUN_ID bằng run 25 task cần so sánh.
& '.\.venv\Scripts\python.exe' '.\scripts\compare_m1.py' --run '.\results\retrieval\<RUN_ID_25_TASK>' --exports '.\data\m1_exports'
# Exit 2 / AWAITING_M1 nghĩa thiếu M1, không phải BM25 lỗi và không được giả kết quả Graph.
$LASTEXITCODE
```

Comparison JSON lưu trong `results/comparison/<run_id>/result.json`; `REPORT.md` nằm trong folder retrieval được chọn. Nếu chỉ có một phần exports thì chỉ là subset paired, chưa phải đủ25. Không dùng demo fixture hay BM25 output đổi tên thành Graph.

Bàn giao: package/docs/tests/manifest, result JSON + task details + report, inspection notes, `m1_requests/`; **không gửi gold folder cho agent/M1 retrieval**. Leader/human cần xác nhận inspection và thống nhất M3 manifest. Không commit `.venv`, archive/cache, key/secrets; results dung lượng lớn nên chia sẻ artifact riêng có hashes. Đọc PROGRESS để biết bằng chứng cụ thể và những việc chưa hoàn tất.

## 11. Rủi ro/phạm vi còn lại

Không thể cam kết “không bao giờ lỗi” trên mọi máy/mạng. HTTP timeout, hết disk, source syntax khác Python host, invalid export được ghi lại để xử lý. AST/Jedi/Tree-sitter có thể khác qname/decorator range; adapter từ chối mismatch thay vì đoán mapping. Định nghĩa gold hiện tại không làm full refactoring mining hay semantic proof. Kết quả ban đầu dùng để debug, không công bố frontier repair performance.
