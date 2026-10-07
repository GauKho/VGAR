# Kết quả dev25 no-Jedi và bàn giao — VGAR tuần 3–6

Ngày: **07/10/2026**. Phạm vi: retrieval evaluation và các boundary tích hợp tuần 3–6. Không chạy model, không sinh/sửa patch SWE-bench, không chạy môi trường benchmark hoặc test của các repo bên ngoài. Người dùng đã duyệt no-Jedi chính và loại trừ environment readiness 50–100/smoke3.

## 1. Kết quả và gate

| Nội dung | Kết quả thật |
|---|---|
| Pilot no-Jedi đã duyệt | 3/3 SUCCEEDED, exit 0 |
| Dev25 | **25 attempts, 19 SUCCEEDED, 3 FAILED, 3 ERROR, 0 NOT_RUN** |
| Comparison | **COMPARED_PARTIAL**, 19/25 valid pairs, exit 1 |
| Gate paired 20–30 / mục tiêu 25 | **CHƯA ĐẠT**, vì 19 pairs dưới ngưỡng 20 |
| Report/CI | Đã tạo từ19 pairs, giữ failures/denominator 25, không gọi là gate 25 PASS |
| Manual audit 10 | Self-audit hoàn tất, không owner sign-off/independent review |
| Inference/repair pass rate | NOT_RUN / không có số đo |
| Environment readiness | EXCLUDED_BY_USER / NOT_RUN |

`complete=true` nghĩa run đã kết thúc và lưu đủ trạng thái, **không có nghĩa mọi task thành công**. Exit1 của comparison là chủ đích báo partial coverage, không phải parser/scorer crash. Không retry bất kỳ task lỗi nào, không bổ sung task cho đủ 20/25, không giảm denominator hoặc tăng timeout/budget.

## 2. Input và fairness

Dataset Verified revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, manifest `data/manifests/verified-c104f840cc67-dev-25.json`, split dev, problem_statement-only. Task population 25 không đổi. Developer patch chỉ làm gold sau ranking. No-Jedi chỉ tắt Jedi fallback trong benchmark, vẫn Tree-sitter + resolver nội bộ; app default Jedi giữ nguyên.

Counter: pinned local tokenizer Qwen3-4B-Instruct-2507@`cdbee75f17c01a7cc42f958dc650907174af0554`, snippet budget 8.000, max 80 lines/header/overlap policy, scorer `retrieval-scoring-v1`. Không dùng bytes/4 trong benchmark. Graph max_hops=2/max_candidates=100; BM25 full saved rank, không cap/rerank/repack để số đẹp. F2P là **oracle-assisted arm** riêng, không failing tests quan sát từ môi trường.

Historical BM25 đạt 25 nhưng Git checkout LF→CRLF làm raw task hashes sai. [Recovery evidence](../../artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/result.json) xác minh 25/25 Git blobs đúng recorded hash và xuất **copy mới**; không overwrite originals, sửa hash hoặc chạy lại BM25. Comparator kiểm cùng query/corpus/base/repo/patch/gold/counter/budget/scorer/snippet và population. Manifest nguyên bytes có thể khác vì newline; không giả hai raw manifest hashes giống nhau. Patch-text hash theo universal newlines, source/task artifact hashes theo raw bytes.

Các run/source identities và hashes cụ thể nằm trong evidence dưới đây. Code host binding được sửa **sau dev25/comparison terminal**, không trộn vào measurements; nó không thay ranking/graph builder/scorer. Source fingerprint của run phản ánh code lúc đo, không giả bằng checkout hiện tại. Resume có fingerprint khác phải bị từ chối; muốn đo với code mới cần run mới/approval, không sửa identity của run cũ.

## 3. Số liệu primary trên 19 valid pairs

Macro means: mỗi eligible task đóng góp một giá trị. Recall không phải tỷ lệ repair PASS. Δ=Graph−BM25. Bootstrap 95% CI, seed=0, 2.000 resamples, **conditional trên 19 success pairs**; không suy rộng qua 6 cases đã lỗi hoặc mọi repo/dataset.

| Metric | BM25 | Graph issue-only | Mean Δ | 95% CI Δ |
|---|---:|---:|---:|---|
| File Recall@3 | .3640 | .1754 | −.1886 | [−.3333,−.0351] |
| File Recall@5 | .5439 | .2412 | −.3026 | [−.5088,−.0921] |
| File Recall@10 | .6184 | .3509 | −.2675 | [−.4518,−.0702] |
| Function Recall@3 | .2193 | .0877 | −.1316 | [−.2474,−.0211] |
| Function Recall@5 | .2982 | .0877 | −.2105 | [−.3596,−.0702] |
| Function Recall@10 | .4421 | .1140 | −.3281 | [−.5439,−.1123] |
| File MRR | .5888 | .3023 | −.2865 | [−.4433,−.1397] |
| Function MRR | .4334 | .1944 | −.2391 | [−.4206,−.0457] |
| Packed gold-file coverage | .6711 | .5132 | −.1579 | [−.3860,+.0877] |
| Packed gold-function coverage | .4690 | .2316 | −.2374 | [−.4584,−.0228] |
| Packed tokens | 7997.7 | 7142.2 | −855.5 | [−1663.3; −275.9] |

Full precision và wins/ties/losses trong [REPORT](../../results/retrieval/20261007T022806825449Z-7e61dc92fe7b/REPORT.md) và [comparison JSON](../../results/retrieval/20261007T022806825449Z-7e61dc92fe7b/result.json). File R5: 4 wins/2 ties/13 losses; function R5: 1 win/8 ties/10 losses. Giảm tokens không tự là tốt nếu mất relevant context; với context_tokens, “wins” trong helper chỉ có nghĩa numeric Δ>0, **không là chất lượng tốt hơn**.

Graph có 0 no-anchor tasks nhưng trung bình78,6 anchors/task, 79,3 candidates/task; unmapped total=0. Mapping coverage=1 trên 19 eligible cases và file-retrievability mean=0.986842 (Astropy13398 có file mới). **Không thiếu anchors không đồng nghĩa anchors đúng**. Gold là changed-code proxy, không phải proof duy nhất nơi sửa; missing/new/unscorable labels phải giữ đúng denominator, không điền 0 giả.

Graph+F2P có R5 bằng issue-only trong run này, packed function coverage=0.2140 thấp hơn 0.2316. Không chọn oracle như primary hoặc diễn giải “F2P luôn cải thiện”. Không thực hiện multiple-hypothesis confirmatory claim từ bảng descriptive CI này.

**Đọc REPORT đúng:** header/“Số chính”, “Số phụ”, “Per task” đầu/cuối là **BM25 source run 25**. Riêng phần Graph vs BM25 và coverage mới là19 pairs/Graph25attempts. Đừng thấy “completed 25” ở header rồi kết luận Graph25/25.

## 4. Failure taxonomy — giữ tất cả sáu case

| Task | Kết quả/phase | Duration | Peak RSS bytes | Điều biết / điều chưa biết |
|---|---|---:|---:|---|
| sympy16597 | ERROR/TimeoutError, PREPARE_RETRIEVAL | 300,031s | 4.785.938.432 | Graph build đã xong; preparation vượt total deadline, chưa profiling từng constructor |
| sympy17318 | ERROR/TimeoutError, PREPARE_RETRIEVAL | 300,010s | 4.904.476.672 | Cùng phase; không Jedi hoặc MemoryError được ghi |
| django11885 | FAILED/PermissionError, EXTRACT_TREE | 3,541s | 194.310.144 | WinError5 rename partial directory; không biết process/ACL cụ thể giữ handle |
| pylint6386 | FAILED/GraphValidationError, BUILD_GRAPH | 32,684s | 194.224.128 | Duplicate edge 8ebedb…; validator chặn đúng, occurrence gây collision chưa xác định |
| sympy20438 | ERROR/TimeoutError, PREPARE_RETRIEVAL | 300,043s | 4.809.166.848 | Build 223,357s, deadline cho cả task 300s, không có thời gian chuẩn bị đủ |
| django13512 | FAILED/PermissionError, EXTRACT_TREE | 3,397s | 194.367.488 | WinError5 renamepartial directory; không tự tắt antivirus/changeACL hoặc retry |

Mỗi case có canonical `tasks/<instance_id>.json` trong [graph run](../../results/retrieval/20261007T014445273889Z-664d06a6c1c0/), `attempt_path`, request/result/telemetry, stdout/stderr và traceback. [Một file evidence tổng hợp](../../artifacts/fixes/w3-w6/benchmark-handoff/20261007T022932115081Z-785d8f78eb4e/result.json) chứa **toàn bộ error evidence** sáu case, config, per-success timing/metrics/source hashes và comparison JSON. Canonical task SHA256 25/25 đã kiểm; không normalize để né guard.

Ba task Sympy đều thất bại tạo bias: 19 valid pairs có 6 repos, **không có Sympy**; hai Django và một Pylint cũng bị mất vì execution failure. Phải báo selection này, không gọi CI là performance toàn population 25.

## 5. Latency, tài nguyên và cost

Run wall time 2.576,420s, khoảng 42,94 phút cho 25 attempts + setup/serialization. 19 success cases: mean 86,005s/task, median 63,949s, nearest-rank p95/max 176,730s. Deadline 300s là **total per-task**, không 300s cho mỗi phase; không phải dự báo cần 125 phút.

BUILD_GRAPH stage quan sát hiện tại trên 19 successes: mean 57,582s, median 36,851s, p95/max 122,944s. Có 3 graph cache hits; `graph_build_seconds` trong metadata có thể là thời gian builder từ lúc cache được tạo, **không phải elapsed stage hiện tại**. Vì vậy dùng telemetry BUILD_GRAPH khi bàn latency; không so cold/warm như cùng điều kiện. Baseline lịch sử không rerun nên không claim speedup head-to-head hoặc paired latency CI với phần cứng/cache kiểm soát.

Peak RSS lớn nhất quan sát 4.904.476.672 bytes (~4,57 GiB), không phải VRAM/virtual memory. Phép đo max(worker peak, parent-observed process tree mỗi 0,5s) có hạn chế sampling khi timeout. Không `MemoryError` ở sáu failures; chưa có căn cứ chỉ cần nâng GPU/RAM là hết lỗi. Graph preparation/Windows rename/schema duplicate edge là các vấn đề khác nhau.

API inference cost=**0 USD**, vì không gọi LLM và không tải weights. Local CPU/RAM/storage hoặc máy thuê vẫn cócost riêng. Runtime artifacts/cache/rebuilt trees/baseline recovery copies tốn disk và được giữ để audit; không tự xóa dữ liệu người dùng.

## 6. Manual audit và bước tiếp theo được phép

[Self-audit 10](2026-10-07-manual-retrieval-audit-10.md) có issue/base patch/AST definitions/anchors/top5 files/functions/raw source proof/packed tokens/nhận xét cho 10 distinct success cases. [JSON bundle](../../artifacts/fixes/w3-w6/manual10-no-jedi/completed/20261007T021118025559Z-44e2a8e0c817/result.json) giữ report+cards, collector cũ không overwrite. Đây không independent human review hoặc owner approval.

Theo quy tắc fail 1 lần có thể dừng: **dừng task benchmark/gate paired**, ghi sáu failures và chuyển kiểm thử tích hợp độc lập. Không chạy tiếp Jedi, tăng timeout, đổi gold/scorer hoặc tự resume failed cases. Khi được phép mở lại: M1 định vị duplicate edge bằng reproducer nhỏ; điều tra permission handle/rename; profiling PREPARE_RETRIEVAL trước quyết định resource/budget. Những việc chưa triển khai phải ở [báo cáo task chưa hoàn thành](../BAO_CAO_TASK_CHUA_HOAN_THANH_W3_W6.md).

Kết quả khoa học hiện tại: Graph profile này **kém BM25 trên phần lớn metric của19successpairs**; artifacts reproducible/honest không phải bằng chứng đã đạt lợi ích Graph hay hoàn thành Week 6 DoD. Không fake repair PASS, không kỳ vọng fine-tuning tự chữa lỗi schema/permission. Owner M1/M2/M3 review/sign-off còn riêng. Environment đã loại trừ, không chạy; research tuần 1–2 và tuần 7–16 ngoài phạm vi này.
