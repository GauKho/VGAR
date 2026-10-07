# Báo cáo task chưa hoàn thành — VGAR tuần 3–6

Cập nhật: **07/10/2026**. Báo cáo này bổ sung cho [PROGRESS](../PROGRESS.md) và [kế hoạch đã duyệt](superpowers/plans/2026-10-06-fix-vgar-integration-week-1-6.md), không thay thế lịch sử evidence.

## 1. Quy tắc dừng được người dùng xác nhận

**Checkpoint mới sau mở lại:** tối đa3thất bại/task/phương pháp rồi chuyển; không lặp cách cũ không có hypothesis mới. [Mục6 của hướng dẫn](GIAI_THICH_VGAR_TRUOC_SAU_FIX_TUAN_3_6_VA_CACH_KIEM_THU.md#6-trạng-thái-task-chưa-hoàn-thành-trước-hoàn-thành-sau) là bảng current; các mục bên dưới là **checkpoint lịch sử19/25**, không overwrite artifact. Pylint inheritance ID đã fix; snapshot preparation đã tối ưu/kiểm59targeted tests; suitecode365passed4skip. Run mới `20261007T114731162059Z-f27e07ec6a8b` terminal23SUCCEEDED/2FAILED, comparison `20261007T122342844612Z-12c751a0b3f6` COMPARED_PARTIAL23pairs/exit1. Đủ sốlượng≥20, chưa strict25. Cả6cases lỗi trước PASS trong run mới nhưng Django13212/13344 WinError5 EXTRACT_TREE; dừng direct-rename group có2historical+2new failures, không tựđổiACL/tắtbảovệ/retry. Jedi3timeouts dừng; coldSympy17318/20438 vẫn timeout300s trongrunriêng dùwarmPASS. Owner approvals chờngười. Không commit/push hayjobđangchạy; khôngenvironment/modelinference.

Quy tắc mới ngày07/10: task **fail1lần có thể dừng** và chuyển sang task độc lập khác; không cần đợi lỗi lặp lại. Ghi lại nguyên nhân đã xác định, evidence, phần chưa biết và điều kiện tiếp tục; không tự retry cùng cấu hình. **Dừng task không có nghĩa task đã hoàn thành hoặc được loại khỏi tiêu chí nghiệm thu.**

Chỉ tuần **3–6**. Không sửa research tuần 1–2, hệ thống cũ, model inference/fine-tuning hoặc tuần 7–16. Không commit/push. Không tự đổi profile benchmark, tăng timeout, bỏ task lỗi hoặc bỏ validator để đạt số đẹp.

**Thay đổi đã được người dùng duyệt:** no-Jedi làm profile chính, giữ dataset/tokenizer/budget8000/resolver nội bộ. **Environment50–100/smoke3 loại khỏi đợt này**; không kiểm/chạy/cài Docker/environments. Jedi lịch sử giữ riêng. Pilot no-Jedi SUCCEEDED3/3; dev25 `20261007T014445273889Z-664d06a6c1c0` đã terminal **19success/6failures/25attempts**. Không task đang chạy tại checkpoint cuối này. [Kết quả đầy đủ](reviews/2026-10-07-dev25-no-jedi-results.md).

## 2. Trạng thái bàn giao hiện tại

- Milestones 1–6: implementation qua gate kỹ thuật; milestone 7: tài liệu vận hành đã cập nhật. Sign-off thực sự của các thành viên vẫn riêng.
- Gate8.1 cuối: [full recorder sau hostbinding](../artifacts/fixes/w3-w6/host-source-binding/full-suite/20261007T022934073929Z-4a8c5e505aa4487993dca0fd82a2607f.json), **359passed/4skipped**, testexit0, phaseDONE; pytest140,38s, wrapper144,980s; source trước/sau giống nhau. Bốnsymlink cases serialized NOT_RUN, không PASS. Suite355 lịch sử giữ trong PROGRESS.
- Gate 8.2: [fixture pipeline](../artifacts/fixes/w3-w6/20261007T012636266959Z-7ac7378bc98e/result.json) **PASS**: actual worker build → task overlay → retrieval → rank adapter/shared scorer → serializer → paired comparison → REPORT. Archive/gold/manifest và source không đổi. Đây là fixture dùng bytes/4 diagnostic; **không phải kết quả SWE-bench hoặc repair success**.
- [Fixture có input/output giữ lại](../artifacts/m8-fixture-99543a81/): source archive, manifest, gold patch, graph/tree, run/attempt logs, BM25 baseline và comparison. [REPORT](../artifacts/m8-fixture-99543a81/compared/20261007T012637548656Z-15fbdea1ef97/REPORT.md) và toàn bộ nội dung report nằm trong JSON gate phía trên.
- Official pinned-tokenizer stateless MCP fixture đã PASS ở phiên trước; không tải model weights, không inference.

## 3. Danh sách task còn thiếu và cách xử lý

| Task/gate | Trạng thái | Evidence / nguyên nhân | Điều kiện tiếp tục |
|---|---|---|---|
| 8.3 — Pilot3 profile chính | **HOÀN THÀNH no-Jedi đã duyệt** | Run20261007T013925676777Z-55ae5fb6a24a, SUCCEEDED3/3/exit0; Jedi giữ riêng | Không chạy lại pilot; chuyển dev25 cùng profile |
| 8.4 — Paired evaluation20–30, mục tiêu25 | **DỪNG/CHƯA ĐẠT:19pairs** | Dev25terminal19success/6failures; dưới20, không retry | Điều tra các lỗi dưới đây khi được mở lại; không tự drop/đổideadline/đổiprofile/claim25 |
| Report/CI, denominator/no-anchor/unscorable | **HOÀN THÀNH report partial19**, không gate25 | [REPORT](../results/retrieval/20261007T022806825449Z-7e61dc92fe7b/REPORT.md), [diễn giải](reviews/2026-10-07-dev25-no-jedi-results.md); same hashes/protocol, oracle riêng | Giữ CI conditional19, coverage25, không thay kết quả âm; owners review |
| Manual audit 10 task distinct | **HOÀN THÀNH self-audit10** | [Báo cáo](reviews/2026-10-07-manual-retrieval-audit-10.md), issue/base/gold/source/anchors/top5/packing; integrity10/10 | Owners có thể review độc lập; không thay task25 hoặc sign-off bằng audit10 |
| Environment readiness SWE-bench 50–100, trước hết smoke3 | **KHÔNG THỰC HIỆN trong đợt này — người dùng loại trừ** | Giữ evidence lịch sử; không kiểm/chạy/cài environment mới | Chỉ mở lại khi người dùng yêu cầu; không ảnh hưởng việc chạy retrieval offline |
| Sign-off M1/M2/M3 cho identity/task_handle/consumer mapping | **CHƯA XÁC NHẬN bởi owners** | Automated consumer tests PASS; người dùng đã chọn task_handle | Các thành viên thực sự review ADR/contract; agent không ký thay |
| Review bàn giao affected diff | **HOÀN THÀNH self-review, chưa ready nghiệm thu/merge** | [Review](reviews/2026-10-07-affected-files-review-w3-w6.md); hostbinding đã RED→GREEN/fullsuite; Importantbenchmarkfailures còn mở | Không review độc lập/sign-off; dừng failures theo user rule, owners quyết định tiếp |
| Sympy16597/17318/20438 | **DỪNG sau1attempt/case** | Timeout300s PREPARE_RETRIEVAL, peakRSS4,79–4,90GB (bytes trong report), không MemoryError/Jedi | Profiling preparation/build/cache trước resource/deadline decision; không nângbudget bằng phỏng đoán |
| Django11885/13512 | **DỪNG sau1attempt/case** | WinError5 EXTRACT_TREE renamepartialdir, ~3,5s, trace giữ nguyên | Xác định handle/ACL/rename timing bằng reproducer; không tắt bảo vệ/chmod/retry tùy tiện |
| Pylint6386 duplicateedge | **DỪNG sau1attempt, lỗi code chưa sửa** | GraphValidationError BUILD_GRAPH, 32,684s, edge8ebedb… | M1 định vị occurrence/cause, viết regression trước fix; không bỏschema validator/dedup để giấu lỗi |

## 4. Pilot thất bại ở đâu?

### 4.1. Lỗi cache trước đó đã có cách khôi phục

[Pilot đầu](../results/retrieval/20261006T155910874325Z-e34289af181b/result.json) 0/3 vì `EXTRACT_TREE` hash mismatch. [Đối chiếu archive/cache](../artifacts/fixes/w3-w6/20261006T160056698401Z-9df672c32ba9/result.json) xác định Git checkout chuyển LF→CRLF; archive hash khớp marker cũ nhưng bytes trong tree khác.

Đã thêm `--rebuild-trees`: giải nén raw archive bytes sang thư mục UUID ngắn, giữ nguyên cache cũ; không normalize cache, sửa marker hoặc bỏ kiểm hash. Regression đã pass. Đây không còn là lỗi chặn trong recovery pilot mới.

### 4.2. Lỗi lặp lại hiện tại nằm ở BUILD_GRAPH với Jedi

[Recovery pilot](../results/retrieval/20261006T160820338280Z-24c3cf0056d1/result.json): `complete=true`, `PARTIAL_FAILURE`, **0/3**, khoảng 901,211s. Cả ba task có deadline 300s và worker 1:

| Task | Kết quả | Phase | Peak RSS quan sát |
|---|---|---|---:|
| django__django-11138 | ERROR / TimeoutError | BUILD_GRAPH | 1.710.469.120 bytes |
| matplotlib__matplotlib-14623 | ERROR / TimeoutError | BUILD_GRAPH | 1.778.511.872 bytes |
| pydata__xarray-3993 | ERROR / TimeoutError | BUILD_GRAPH | 1.818.783.744 bytes |

Không có `MemoryError` trong ba lượt này. RSS không phải VRAM, không chứng minh máy tuyệt đối đủ RAM; nhưng **không có cơ sở quy lỗi này cho GPU hoặc đòi nâng RAM ngay**. Retrieval không chạy LLM.

### 4.3. Chẩn đoán có giới hạn; không sửa phương pháp để gọi là PASS

1. [Xarray không Jedi](../results/retrieval/20261006T162334561191Z-8d3c4f6a13e7/result.json): **SUCCEEDED**, tổng 21,509s, task 20,164s, build 4,220s; 39.846 nodes/55.309 edges, peakRSS392.568.832 bytes. Counter official pin/8000token budget, offline/rebuild-trees. Issue-only fileRecall@5=1, functionRecall@5=0,5, MRR=1, packed gold-function coverage=1, context7970tokens. Đây chỉ **một diagnostic task**, không đủ kết luận chất lượng graph trên 25 task.
2. [Jedi stack diagnostic](../artifacts/fixes/w3-w6/20261007T012123887065Z-1f83886bd988/result.json): timeout 85,045s tại BUILD_GRAPH; faulthandler chỉ ra `jedi.inference.dynamic_params`, `references._check_fs/search_in_file_ios` và suy luận lồng nhau. Điều này xác định Jedi inference/reference search là điểm nghẽn quan sát được trên xarray; chưa đo chính xác mọi call site của ba repo.
3. [Tắt dynamic_params chỉ trong subprocess diagnostic](../artifacts/fixes/w3-w6/20261007T012331157674Z-e681a29a0215/result.json): ERROR/WorkerProcessError, exit3221225477 (`0xC0000005`), 47,874s, không có terminal worker JSON. Không đủ bằng chứng quy native crash cho một thư viện cụ thể hoặc kết luận tắt dynamic_params là cách sửa. Không áp dụng override này vào production/benchmark.

**Quyết định lịch sử:** dừng các lượt Jedi tương tự; không chạy thêm khi chưa có thay đổi được duyệt. **Cập nhật:** người dùng đã trả lời “Duyệt no-Jedi làm profile chính”. Benchmark mới dùng Tree-sitter + resolver nội bộ; CALLS có thể ít hơn vì không dùng Jedi fallback. App default không đổi; dataset, tokenizer, budget/scorer/population giữ nguyên. Chỉ chạy pilot/paired theo gate; không gọi đó là kết quả Jedi.

## 5. Phần độc lập đã hoàn tất sau khi dừng pilot

### Failure mới của profile no-Jedi (không retry)

Dev25 `20261007T014445273889Z-664d06a6c1c0`, task `sympy__sympy-16597`: **ERROR/TimeoutError300.031s**, phase **PREPARE_RETRIEVAL**, peakRSS **4.785.938.432bytes**. Không phải lỗi Jedi profile cũ: graph build đã kết thúc nhưng bước chuẩn bị retrieval chưa xong trong total task deadline. Không có MemoryError, không LLM/GPU; không suy ra mọi case chỉ do thiếu RAM. Artifact ở `tasks/sympy__sympy-16597.json`, attempt/log/trace theo attempt_path trong đó. Theo user rule: dừng case này, giữ failure trong population25, runner chuyển task tiếp theo; không tăng budget/deadline hay retry. Nếu cuối run chỉ20–24 valid pairs thì vẫn cần leader duyệt exclusions/protocol, không tự tick gate25.

Audit context chọn10 success đầu theo manifest order khi có đủ artifact, không chọn theo accuracy/wins; không dùng audit10 để loại Sympy khỏi benchmark. Failure này có báo cáo riêng vì chưa có ranking/packed output để audit context.

Failures bổ sung cùng run (không retry):

- `sympy__sympy-17318`: ERROR/TimeoutError300,010s, PREPARE_RETRIEVAL, RSS4.904.476.672bytes; không Jedi/MemoryError/GPUinference.
- `django__django-11885`: FAILED/PermissionError WinError5, **EXTRACT_TREE**, 3.541s; rename partial directory sang destination mới bị access denied. Không có evidence xác định antivirus/permission/process cụ thể giữ handle, không tự quy Windows Defender hoặc sửa hash guards. Giữ partial tree và logs để điều tra, không retry case.
- `pylint-dev__pylint-6386`: FAILED/GraphValidationError **BUILD_GRAPH**, 32.684s; duplicate edge id `sha256:8ebedb794e2918e78ab0c78081a7c418e1c244d9dda54940e642110a39465fe7`. Validator chặn đúng; chưa định vị được occurrence tạo collision nên chưa sửa/deduplicate âm thầm. Task artifact/trace giữ nguyên; báo lỗi code còn mở, không gọi mọi lỗi là thiếu tài nguyên.
- `sympy__sympy-20438`: ERROR/TimeoutError300,043s, PREPARE_RETRIEVAL, RSS4.809.166.848bytes. `django__django-13512`: FAILED/PermissionError WinError5 EXTRACT_TREE,3,397s/RSS194.367.488bytes. Tất cả sáucase được giữ và không retry; run terminal43phút, không19/19che denominator25.

Manual10 đã được diễn giải trong [báo cáo audit](reviews/2026-10-07-manual-retrieval-audit-10.md). Collector gốc giữ `manual_review_completed=false` vì chỉ thu evidence trước diễn giải, không overwrite để đổi lịch sử. BM25 historical checkout bị LF→CRLF; bản sao raw Git blobs đúng25/25hash được xuất riêng, không chạy lại BM25. Helper failures và recovery provenance trong PROGRESS.

- Sửa lọc credentials của public retrieval worker trong `src/vgar/evaluation/retrieval/lifecycle.py`: chặn tên `TOKEN`, hậu tố `_TOKEN` và các mẫu API_KEY/PASSWORD/SECRET/ACCESS_TOKEN; không sửa environment của host và không xóa `TOKENIZERS_PARALLELISM`.
- Test hồi quy: `tests/m2/test_retrieval_lifecycle.py::test_public_retrieval_worker_does_not_inherit_credentials`. [RED](../artifacts/fixes/w3-w6/20261007T012518923284Z-0305790e711a/result.json) 1 failed; [GREEN liên quan](../artifacts/fixes/w3-w6/20261007T012531597287Z-42e1a0bf5de4/result.json) 58 passed. Chỉ synthetic credentials dùng trong test, không in secrets thật. Lọc tên biến môi trường không phải sandbox/allowlist đảm bảo mọi loại secret đều bị chặn.
- Hoàn tất assertions REPORT và input/source immutability trong `tests/m2/test_retrieval_compare_contract.py::test_comparison_consumes_actual_runner_output`; không tạo artificial `arm` trong output runner.
- Chạy full suite qua M2 recorder; giữ toàn bộ failed runs, stdout/stderr/cases và JUnit trong evidence.

## 6. Cách tiếp tục ở phiên sau mà không làm lại

1. Đọc PROGRESS và báo cáo này; kiểm git status/diff mới, không quét lại repo hoặc overwrite dirty changes.
2. Milestones1–7/gates8.1/8.2/pilot3/manual10/partialreport/hostbinding/selfreview đã có evidence. Không làm lại; suite359 không thay benchmark gate20–30 còn chưa đạt.
3. No-Jedi chính đã duyệt; dev25terminal19pairs. Không tự retry failures, không trộn profile hoặc sửa recordedhashes. Sourcecode có hostbinding/test mới sau đo, resumeidentity sẽ khác; chỉ mở benchmark task lại khi có direction/điều tra concrete, giữguards/counter/gold.
4. Không thực hiện task môi trường đã được người dùng loại trừ. Task owners sign-off chuyển thành viên phụ trách; không thay chúng bằng tick tự động.
5. Sau mỗi task, thêm evidence run mới và cập nhật PROGRESS. Không xóa artifact cũ, không commit/push nếu chưa được yêu cầu.

**Kết luận:** code kiểm thử được và các boundary đã cải thiện; **chưa đủ bằng chứng nghiệm thu toàn bộ tuần3–6** vì các gate trong mục3 còn thiếu. Tạm dừng task lỗi là quyết định tiết kiệm thời gian đã được người dùng cho phép, không phải tuyên bố mọi task hoàn tất.
