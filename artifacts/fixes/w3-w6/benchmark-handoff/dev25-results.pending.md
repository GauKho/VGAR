# Kết quả dev25 no-Jedi và bàn giao — VGAR tuần 3–6

Ngày: **07/10/2026**. Phạm vi: retrieval evaluation và các boundary tích hợp tuần3–6. Không chạy model, không sinh/sửa patch SWE-bench, không chạy môi trường benchmark hoặc test của các repo bên ngoài. Người dùng đã duyệt no-Jedi chính và loại trừ environment readiness50–100/smoke3.

## 1. Kết quả và gate

| Nội dung | Kết quả thật |
|---|---|
| Pilot no-Jedi đã duyệt | 3/3 SUCCEEDED, exit0 |
| Dev25 | **25attempts, 19SUCCEEDED, 3FAILED, 3ERROR, 0NOT_RUN** |
| Comparison | **COMPARED_PARTIAL**, 19/25 valid pairs, exit1 |
| Gate paired20–30 / mục tiêu25 | **CHƯA ĐẠT**, vì 19pairs dưới ngưỡng20 |
| Report/CI | Đã tạo từ19pairs, giữ failures/denominator25, không gọi là gate25PASS |
| Manual10 | Self-audit hoàn tất, không owner sign-off/independent review |
| Inference/repair pass rate | NOT_RUN / không có số đo |
| Environment readiness | EXCLUDED_BY_USER / NOT_RUN |

`complete=true` nghĩa run đã kết thúc và lưu đủ trạng thái, **không có nghĩa mọi task thành công**. Exit1 của comparison là chủ đích báo partial coverage, không phải parser/scorer crash. Không retry bất kỳ task lỗi nào, không bổ sung task cho đủ20/25, không giảm denominator hoặc tăng timeout/budget.

## 2. Input và fairness

Dataset Verified revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, manifest `data/manifests/verified-c104f840cc67-dev-25.json`, splitdev, problem_statement-only. Task population25 không đổi. Developer patch chỉ làm gold sau ranking. No-Jedi chỉ tắt Jedi fallback trong benchmark, vẫn Tree-sitter + resolver nội bộ; app default Jedi giữ nguyên.

Counter: pinned local tokenizer Qwen3-4B-Instruct-2507@`cdbee75f17c01a7cc42f958dc650907174af0554`, snippet budget8.000, max80line/header/overlap policy, scorer `retrieval-scoring-v1`. Không dùng bytes/4 trong benchmark. Graph max_hops2/max_candidates100; BM25 full saved rank, không cap/rerank/repack để số đẹp. F2P là **oracle-assisted arm** riêng, không failing tests quan sát từ môi trường.

Historical BM25 đạt25 nhưng Git checkout LF→CRLF làm raw task hashes sai. [Recovery evidence](../../artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/result.json) xác minh25/25 Git blobs đúng recordedhash và xuất **copy mới**; không overwrite originals, sửahash hoặc chạy lạiBM25. Comparator kiểm cùng query/corpus/base/repo/patch/gold/counter/budget/scorer/snippet và population. Manifest nguyên bytes có thể khác vì newline; không giả hai raw manifesthashidentical. Patch-text hash theo universalnewlines, source/taskartifact hashes theo rawbytes.

Các run/source identities và hashes cụ thể nằm trong evidence dưới đây. Code host binding được sửa **sau dev25/comparison terminal**, không trộn vào measurements; nó không thay ranking/graph builder/scorer. Sourcefingerprint của run phản ánh code lúc đo, không giả bằng currentcheckout. Resume có fingerprint khác phải bị từ chối; muốn đo với code mới cần run mới/approval, không sửa identity của run cũ.

## 3. Số liệu primary trên 19 valid pairs

Macro means: mỗi eligible task đóng góp một giá trị. Recall không phải tỷ lệ repairPASS. Δ=Graph−BM25. Bootstrap95%CI, seed0,2.000resamples, **conditional trên19successpairs**; không suy rộng qua6cases đã lỗi hoặc mọi repo/dataset.

| Metric | BM25 | Graph issue-only | MeanΔ | 95%CIΔ |
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
| Packed tokens | 7.997,7 | 7.142,2 | −855,5 | [−1.663,3,−275,9] |

Full precision và wins/ties/losses trong [REPORT](../../results/retrieval/20261007T022806825449Z-7e61dc92fe7b/REPORT.md) và [comparisonJSON](../../results/retrieval/20261007T022806825449Z-7e61dc92fe7b/result.json). FileR5:4wins/2ties/13losses; functionR5:1win/8ties/10losses. Giảm tokens không tự là tốt nếu mất relevantcontext; với context_tokens, “wins” trong helper chỉ có nghĩa numericΔ>0, **không là chất lượng tốt hơn**.

Graph có0no-anchor tasks nhưng trung bình78,6anchors/task,79,3candidates/task; unmappedtotal0. Mappingcoverage1 trên19eligiblecases và file-retrievabilitymean.986842 (Astropy13398 có file mới). **Không thiếu anchors không đồng nghĩa anchors đúng**. Gold là changed-codeproxy, không phải proof duy nhất nơi sửa; missing/new/unscorable labels phải giữ đúng denominator, không điền0 giả.

Graph+F2P có R5 bằng issue-only trong run này, packedfunctioncoverage.2140 thấp hơn.2316. Không chọn oracle như primary hoặc diễn giải “F2P luôn cải thiện”. Không thực hiện multiple-hypothesis confirmatory claim từ bảng descriptiveCI này.

**Đọc REPORT đúng:** header/“Số chính”, “Số phụ”, “Per task” đầu/cuối là **BM25 source run25**. Riêng phần GraphvsBM25 và coverage mới là19pairs/Graph25attempts. Đừng thấy “completed25” ở header rồi kết luận Graph25/25.

## 4. Failure taxonomy — giữ tất cả sáu case

| Task | Kết quả/phase | Duration | PeakRSS bytes | Điều biết / điều chưa biết |
|---|---|---:|---:|---|
| sympy16597 | ERROR/TimeoutError, PREPARE_RETRIEVAL | 300,031s | 4.785.938.432 | Graphbuild đã xong; preparation vượt totaldeadline, chưa profiling từng constructor |
| sympy17318 | ERROR/TimeoutError, PREPARE_RETRIEVAL | 300,010s | 4.904.476.672 | Cùng phase; không Jedi hoặc MemoryError được ghi |
| django11885 | FAILED/PermissionError, EXTRACT_TREE | 3,541s | 194.310.144 | WinError5 rename partialdir; không biết process/ACL cụ thể giữ handle |
| pylint6386 | FAILED/GraphValidationError, BUILD_GRAPH | 32,684s | 194.224.128 | Duplicateedge8ebedb…; validator chặn đúng, occurrence gây collision chưa xác định |
| sympy20438 | ERROR/TimeoutError, PREPARE_RETRIEVAL | 300,043s | 4.809.166.848 | Build223,357s, deadline cho cảtask300s, không có thời gian chuẩn bị đủ |
| django13512 | FAILED/PermissionError, EXTRACT_TREE | 3,397s | 194.367.488 | WinError5 renamepartialdir; không tự tắt antivirus/changeACL hoặc retry |

Mỗi case có canonical `tasks/<instance_id>.json` trong [graph run](../../results/retrieval/20261007T014445273889Z-664d06a6c1c0/), `attempt_path`, request/result/telemetry, stdout/stderr và traceback. [Một file evidence tổng hợp](../../artifacts/fixes/w3-w6/benchmark-handoff/20261007T022932115081Z-785d8f78eb4e/result.json) chứa **toàn bộ error evidence** sáucase, config, per-success timing/metrics/sourcehashes và comparisonJSON. Canonicaltasksha25/25 đã kiểm; không normalize để néguard.

AllSympy3fail tạo bias:19validpairs có6repos, **không có Sympy**; haiDjango và mộtPylint cũng bị mất vì executionfailure. Phải báo selection này, không gọi CI là performance toànpopulation25.

## 5. Latency, tài nguyên và cost

Runwall2.576,420s, khoảng42,94phút cho25attempts + setup/serialization. Success19: mean86,005s/task, median63,949s, nearest-rankp95/max176,730s. Deadline300s là **total per-task**, không300s cho mỗiphase; không phải dự báo cần125phút.

BUILD_GRAPH stage quan sát hiện tại trên19success: mean57,582s, median36,851s, p95/max122,944s. Có3graphcachehits; `graph_build_seconds` trongmetadata có thể là thời gian builder từ lúccache được tạo, **không phải elapsedstagehiện tại**. Vì vậy dùng telemetryBUILD_GRAPH khi bànlatency; không so cold/warm như cùng điều kiện. Baseline lịch sử không rerun nên không claim speeduphead-to-head hoặc pairedlatencyCI với phần cứng/cache kiểm soát.

PeakRSS lớn nhất quan sát4.904.476.672bytes (~4,57GiB), không phải VRAM/virtualmemory. Phép đo max(workerpeak,parent-observedprocesstree mỗi0,5s) có hạn chế sampling khi timeout. Không `MemoryError` ở sáufailures; chưa có căn cứ chỉ cần nângGPU/RAM là hết lỗi. Graph preparation/Windowsrename/schema duplicateedge là các vấn đề khác nhau.

APIinferencecost=**0USD**, vì không gọiLLM và không tảiweights. LocalCPU/RAM/storage hoặc máy thuê vẫn cócostriêng. Runtimeartifacts/cache/rebuilt trees/baseline recovery copies tốn disk và được giữ đểaudit; không tự xóa dữ liệu người dùng.

## 6. Manual audit và bước tiếp theo được phép

[Self-audit10](2026-10-07-manual-retrieval-audit-10.md) có issue/basepatch/ASTdefinitions/anchors/top5files/functions/rawsourceproof/packedtokens/nhậnxét cho10successdistinct. [JSONbundle](../../artifacts/fixes/w3-w6/manual10-no-jedi/completed/20261007T021118025559Z-44e2a8e0c817/result.json) giữreport+cards,collector cũ không overwrite. Đây không independenthumanreview hoặc ownerapproval.

Theo quy tắc fail1lần có thể dừng: **dừng task benchmark/gatepaired**, ghi sáu failures và chuyển kiểm thử tích hợp độc lập. Không chạy tiếp Jedi, tăng timeout, đổigold/scorer hoặc tựresumefailedcases. Khi được phép mở lại: M1 định vị duplicateedge bằng reproducer nhỏ; điều tra permissionhandle/rename; profiling PREPARE_RETRIEVAL trước quyết định resource/budget. Những việc chưa triển khai phải ở [báo cáo task chưa hoàn thành](../BAO_CAO_TASK_CHUA_HOAN_THANH_W3_W6.md).

Kết quả khoa học hiện tại: Graph profile này **kém BM25 trên phần lớn metric của19successpairs**; artifacts reproducible/honest không phải bằng chứng đã đạt lợi ích Graph hay completedWeek6DoD. Không fake repairPASS, không kỳ vọng fine-tuning tự chữa lỗischema/permission. OwnerM1/M2/M3 review/sign-off còn riêng. Environment đã loại trừ, không chạy; researchtuần1–2 và tuần7–16 ngoài phạm vi này.
