# TV2 · RT-1: retrieval đủ 6 đặc trưng và `components_depending_on`

> **Trạng thái:** đã duyệt, 10/11/2026 (§4.5 chọn C, §4.6 để TV1 quyết; §5 và §6 cập nhật theo trao đổi cùng ngày; sau khi đối chiếu lại proposal và plan 2 tuần: bỏ §4.4, phần so với BM25 và các baseline chuyển sang R1).
>
> **Nguồn:** chỉ dùng plan `docs/status/plan_2_weeks_mcp_server_2026-11-07.md` (**[plan]**), proposal
> `D:\kltn\proposal_vgar_mcp_final_corrected.md` (**[P]**, dẫn số dòng), **[cp]** `check proposal.txt`, **[rq]** `rq metrics matrix.txt`, **[mm]** `metrics matrix.txt`, **[test]** `test.txt`.
> Không dùng plan 16 tuần. Code có sẵn chỉ là hiện trạng.
>
> **Đánh dấu:** **(TV2 chốt)** là anh/chị đã quyết. **(research)** là câu trả lời research ngày 10/11 đã đối chiếu với nguồn và repo. **(đề xuất)** là lựa chọn của người viết spec, chờ duyệt. **(chờ chốt)** là câu hỏi còn mở.

## 1. Bối cảnh

[plan] dòng 132 giao RT-1: retrieval có đủ 6 đặc trưng xếp hạng (`task_similarity`, `graph_distance`, `edge_confidence`, `failing_test_proximity`, `recent_change_frequency`, `public_api_risk`) và `components_depending_on`, theo [P] 972–993:

```text
candidates += k_hop_neighbors(anchor, k), callers, callees, tests_covering, components_depending_on(anchor)
ranked = rank_by(candidates, 6 đặc trưng)
return pack_until_budget(ranked, budget_tokens=12000)
```

[cp] dòng 117: `recent_change_frequency` cần lịch sử commit (Layer 4), `components_depending_on` cần `G_arch`. [plan] Phụ lục B dòng 471: RT-1 chờ L4-1 của TV3 cho lịch sử commit. Milestone M2 (dòng 199): tăng recall file và hàm gold so với grep, BM25, embedding; đo ở R1 (tuần 2 ngày 3, [rq] mục 1).

**Hiện trạng `graph/retrieval.py`:**

| Phần | Có | Thiếu |
|---|---|---|
| 6 đặc trưng | Đủ tên, trọng số mặc định `task_similarity` 0,5, `graph_distance` 0,2, `edge_confidence` 0,1, `failing_test_proximity` 0,2, `public_api_risk` 0,0, `recent_change_frequency` 0,1 | `public_api_risk` có trọng số 0; `recent_change_frequency` chỉ có khi script truyền file lịch sử, nếu không thì báo "unavailable" |
| Ứng viên | Hàng xóm theo `CALLS`, `IMPORTS`, `CONTAINS`, `TESTS`, `INHERITS`, `REFERENCES`; "component seed" là tên thư mục xuất hiện trong issue | Không dùng Component, `DEPENDS_ON`, Port của `G_arch`; không đi theo `MAY_CALL` (confidence ≤ 0,5 dưới ngưỡng 0,6) |
| Cạnh của TV2 | | Không dùng `TRACES_TO` (TR-1) |
| Cấu hình | `RetrievalConfig`; `ranking_config_hash` | `evaluation/dry_run.py` từ chối chạy nếu hash của cấu hình mặc định khác `FROZEN_RANKING_HASH` |

**Dữ liệu và công cụ đo sẵn có:** manifest dev 50 task `configs/m1/w10_dev_manifest.json`; `scripts/run_graph_retrieval.py` (nhận cấu hình JSON), `scripts/run_bm25_retrieval.py`, `scripts/compare_graph_vs_bm25.py` (bootstrap). Checkout trong WSL là shallow, mỗi repo một commit; pipeline đánh giá tải mã nguồn không kèm lịch sử. Repo chưa có baseline embedding.

## 2. Mục tiêu, ngoài phạm vi, điều cần tránh

**Mục tiêu**

1. Cả 6 đặc trưng và `components_depending_on` hoạt động thật trong code; cấu hình trọng số tách khỏi code **(TV2 chốt, research câu 1)**.
2. Một cấu hình RT-1 riêng, cấu hình mặc định cũ giữ nguyên **(TV2 chốt, research câu 2)**.
3. Dùng các tầng mới: `G_arch` (Component, `DEPENDS_ON`, Port), `MAY_CALL` có giảm điểm, `TRACES_TO` của TR-1.
4. Đo từng thay đổi trên bộ dev, báo cả Recall@k và Recall@B.

**Ngoài phạm vi**

- So với BM25, grep, embedding, file-neighbor, agent default và chạy R1 đầy đủ: thuộc R1 (tuần 2 ngày 3, [plan] dòng 167). RT-1 chỉ so cấu hình RT-1 với cấu hình mặc định.
- Giảm điểm anchor trùng từ thông dụng: không có trong [P] và [plan], chuyển sang việc làm sau (§7).
- Học trọng số từ dữ liệu: bộ dev nhỏ, dễ khớp quá mức **(research câu 5)**.
- Lịch sử commit chi tiết, GraphDiff: L4-1, L4-x của TV3.
- Đổi chữ ký tool MCP: thuộc TV1.

**Điều cần tránh**

- Đổi `RetrievalConfig()` mặc định hay `FROZEN_RANKING_HASH`.
- Dùng bất kỳ thông tin nào sau `base_commit` hoặc từ patch gold, `FAIL_TO_PASS` khi xếp hạng.
- Chỉnh trọng số theo held-out; chỉ dùng bộ dev.

## 3. Quyết định

| # | Quyết định | Đánh dấu |
|---|---|---|
| 1 | Giữ code đủ 6 đặc trưng; trọng số là dữ liệu của cấu hình | **(TV2 chốt)** |
| 2 | Thêm `RT1_CONFIG` (một `RetrievalConfig` có tên), kèm `ranking_config_hash` ghi vào kết quả; mặc định cũ không đổi | **(TV2 chốt)** |
| 3 | `components_depending_on` dùng `DEPENDS_ON` của `G_arch`, giới hạn số ứng viên mỗi component | **(research câu 7)** |
| 4 | Đi theo `MAY_CALL` với hệ số giảm, không bỏ qua | **(research câu 8)**; L2-2 đã để phần này cho RT-1 |
| 5 | Dùng top-1 `TRACES_TO` làm nguồn ứng viên bổ sung | **(đề xuất)**, bàn giao TR-1 (top-1 P 0,70 trên 31 task) |
| 6 | ~~Giảm điểm anchor phổ biến~~: bỏ khỏi RT-1 vì không có trong [P] và [plan] | **(TV2 chốt)**, xem §7 |
| 7 | `public_api_risk`: có Port thì symbol của Port là công khai, không có `G_arch` thì dùng `visibility`; trọng số trong `RT1_CONFIG` vẫn 0 | **(research câu 4)** |
| 8 | Nguồn lịch sử cho `recent_change_frequency`: giữ "unavailable" (C), `change_counts` là hợp đồng với TV3 | **(TV2 chốt)**, xem §4.5 |
| 9 | `get_related_context` nhận `config` tùy chọn; TV1 chọn cấu hình cho tool MCP | **(TV2 chốt)**, xem §4.6 |

Không theo research ở câu 9 ("ưu tiên frame sâu nhất trong repo"): task duy nhất có traceback đo ở TR-1 cho kết quả ngược (frame sâu nhất ở `connectionpool.py`, đáp án `sessions.py`). Frame tiếp tục vào làm anchor như hiện nay (`path_line` 0,95), không thêm tầng điểm theo độ sâu.

## 4. Thiết kế

Mọi thay đổi bật/tắt bằng cờ mới của `RetrievalConfig`, mặc định tắt, để cấu hình cũ cho đúng kết quả cũ và giữ hash.

### 4.1 `components_depending_on`

Cờ `use_component_dependents: bool = False`, `dependent_symbols_per_component: int = 3`.

- Component của anchor: Component có `properties.files` chứa `path` của anchor.
- Component phụ thuộc: các D có cạnh `DEPENDS_ON` D → C.
- Ứng viên từ mỗi D: symbol trong D gọi vào symbol của C (cạnh `CALLS` từ CallSite thuộc D tới đích thuộc C), xếp theo số lời gọi rồi theo id; lấy tối đa `dependent_symbols_per_component`.
- Rationale `COMPONENT_DEPENDENT`, khoảng cách 2, confidence lấy từ cạnh `CALLS`.
- Graph không có Component: không thêm gì, ghi vào `unavailable_features`.

### 4.2 `MAY_CALL`

Cờ `may_call_factor: float = 0.0` (0 là tắt). Khi > 0, cạnh `MAY_CALL` được đi như `CALLS` với confidence hiệu dụng = `confidence × may_call_factor`, không bị ngưỡng `min_edge_confidence` chặn. Giá trị trong `RT1_CONFIG` chọn ở §5.

### 4.3 `TRACES_TO`

Cờ `use_trace_component: bool = False`. Khi có overlay, lấy cạnh `TRACES_TO` xếp đầu theo `rank_component_traces` (TR-1), chỉ khi `confidence` ≥ 0,7. Thêm Port của Component đó (symbol trong `symbol_id`) làm seed yếu, confidence 0,45 như component seed hiện có, tối đa `dependent_symbols_per_component` symbol, ưu tiên symbol trùng từ với issue.

### 4.5 `recent_change_frequency`

Đặc trưng đã có, nhận `change_counts: {path hoặc node id: số lần sửa}`. Vấn đề là nguồn dữ liệu: checkout và pipeline đánh giá không có lịch sử.

| Cách | Cần gì | Rủi ro |
|---|---|---|
| A. Dùng đầu ra L4-1 của TV3 | TV3 xuất `change_counts` tính tới `base_commit` | Chờ TV3 ([plan] dòng 471) |
| B. TV2 viết script tạo `change_counts` từ một bản clone không kèm nội dung file (`git clone --filter=blob:none`) rồi `git log <base_commit> --name-only` | Mạng, dung lượng cho lịch sử commit | Phải chặn đúng tại `base_commit`; tốn thời gian tải cho repo lớn |
| C. Giữ "unavailable" như hiện nay và ghi rõ trong báo cáo | Không | Đặc trưng có trong code nhưng không đo được tác dụng |

**(TV2 chốt)** Làm C: đặc trưng báo "unavailable", không tự gán 0 như đã đo, và báo cáo ghi rõ. Định dạng `change_counts` giữ làm hợp đồng với TV3 (A); B chỉ làm nếu TV3 không kịp. Research cũng ghi đặc trưng này ít giúp định vị lỗi trên SWE-bench (câu 6), nên trọng số trong `RT1_CONFIG` nhỏ.

### 4.6 MCP

`sqlite_service.get_related_context` nhận thêm tham số tùy chọn `config: RetrievalConfig | None`, mặc định giữ cấu hình cũ. TV1 quyết định tool `get_related_context` truyền `RT1_CONFIG` hay giữ mặc định ở L6-8 **(TV2 chốt)**. RT-1 không sửa code MCP của TV1.

### 4.7 `public_api_risk`

Symbol có Port trỏ tới (`Port.symbol_id`) là công khai; nếu graph không có Port thì dùng `visibility == "public"` như hiện tại. Giá trị đặc trưng giữ công thức hiện có. Trọng số trong `RT1_CONFIG` là 0 vì API công khai không cho thấy có lỗi **(research câu 4)**.

## 5. Đo và chọn giá trị

- Bộ dev: manifest 50 task `configs/m1/w10_dev_manifest.json` ([rq] mục 1, [plan] dòng 382), giữ nguyên `manifest_hash`. Ổ đĩa không đủ giữ cả 50 checkout cùng lúc, nên chạy hai bước **(TV2 chốt)**:
  1. Chỉnh tham số trên 25 task đã đo ở TR-1 (tên thư mục trong `~/tr1-repos`). Pipeline đánh giá tải archive mã nguồn tại `base_commit`, không dùng checkout git. Kết quả bước này chỉ dùng để chọn giá trị, ghi rõ là "25/50 task", không báo như kết quả bộ dev.
  2. Số liệu báo cáo chạy đủ 50 task theo kiểu cuốn chiếu: mỗi lần một task, tải mã tại `base_commit` không kèm lịch sử, build graph, chạy mọi cấu hình cần đo, ghi file JSON kết quả, rồi xóa checkout và graph. Lúc nặng nhất đĩa chỉ giữ một task. Chạy lại được từ task dở dang (bỏ qua task đã có kết quả).
- Trước khi chạy đủ bộ: chạy thử 1–5 task để kiểm tra pipeline ([test] mục 3, tầng 2).
- Chỉ số: `gold_file_recall@k`, `gold_function_recall@k`, Recall@B ở ngân sách 12.000 token theo [P] 972 (đúng bằng `packed_gold_file_in_context` và `packed_gold_function_in_context`, [P] 816), MRR; so `RT1_CONFIG` và từng cờ với cấu hình mặc định bằng `compare_graph_runs` (bootstrap ghép cặp theo task). So với BM25 và các baseline khác để R1 làm, dùng chính kết quả 50 task này **(TV2 chốt)**.
- Mỗi cờ ở §4.1–4.3 đo riêng (bật một cờ, giữ phần còn lại), rồi đo tổ hợp. Giá trị `may_call_factor` (0,5; 1,0) thử ít mức cố định, không dò tinh, để tránh khớp quá mức trên 50 task.
- `RT1_CONFIG` gồm các cờ làm tăng recall mà không giảm MRR quá khoảng tin cậy; cờ không giúp thì để tắt và ghi kết quả.
- Đo lại riêng nhóm task có traceback dùng đường dẫn tuyệt đối (bàn giao TR-1).
- Báo cáo ghi hai giới hạn: manifest chọn với `min1` (sau khi dựng gold từ parquet: 5/50 task sửa từ 2 file nguồn trở lên), trong khi [plan] phụ lục A.3 ghi bộ lọc `min_source_files=2`; bộ 12 task ở §6 mục 1b là của TV2, khi nhóm chốt repo mẫu chung ([plan] dòng 470 mục 3) thì thêm một case RT-1 trên repo đó.

**Kết quả (10/11):** trên 25 task chỉ `may_call_factor=0.5` qua quy tắc chọn, nên `RT1_CONFIG = RetrievalConfig(may_call_factor=0.5)`. Trên 50 task, arm `graph`: Recall@B file 0,773 → 0,818, MRR file 0,514 → 0,537, Recall@5 hàm 0,338 → 0,363, Recall@5 file 0,743 → 0,723; mọi CI95 chạm 0. Chi tiết: `docs/status/tv2_rt_1_retrieval_run_2026-11-10.md`.

## 6. Tiêu chí nghiệm thu

1. Test cho từng cờ: graph tối thiểu có Component, `DEPENDS_ON`, `MAY_CALL`, overlay có `TRACES_TO`; ứng viên và rationale đúng; giới hạn mỗi component đúng; graph không có `G_arch` không lỗi.
1b. Kiểm tra trên repo thật với bộ 12 task `software_repair_benchmark` (4 repo: `shop-ledger`, `cart-dispatch`, `fee-engine`, `tiny-edges`): mỗi cờ đổi kết quả ở task của nó và không đổi kết quả ở task khác; cấu hình mặc định cho kết quả như trước RT-1; chạy hai lần cho cùng kết quả. Bộ này là kiểm thử, không phải số liệu R1, vì task do nhóm tự viết. Một task chỉ dùng được cho cờ của nó khi thỏa điều kiện: cờ `use_trace_component` cần issue có traceback dạng `File "...", line N`. Hiện task 06, 08, 09 chưa thỏa và chờ sửa repo; trước đó chúng chỉ dùng cho kiểm tra cấu hình mặc định và chạy lặp. Task 03 (từ khóa phổ biến) không còn cờ tương ứng sau khi bỏ §4.4, nên chỉ dùng cho kiểm tra cấu hình mặc định và chạy lặp.
2. `RetrievalConfig()` mặc định cho đúng kết quả cũ trên các test retrieval hiện có; `FROZEN_RANKING_HASH` không đổi.
3. Không đặc trưng nào đọc dữ liệu sau `base_commit`, patch gold hay `FAIL_TO_PASS`.
4. Báo cáo đo trên bộ dev ở `docs/status/`, mỗi số kèm lệnh tái tạo ([plan] dòng 170).
5. Toàn bộ test suite chỉ còn các test fail đã biết; test RT-1 chạy trên Windows và WSL.

## 7. Các đề xuất research không đưa vào

Danh mục tài liệu của research không có trong bản dán; các con số dẫn từ ARISE, KGCompass, RGFL chưa kiểm chứng được và không dùng làm căn cứ.

| Câu | Đề xuất | Lý do |
|---|---|---|
| 3 | TV2 tự đếm từ `git log` tại `base_commit` | Checkout shallow, pipeline tải mã nguồn không kèm lịch sử; [plan] dòng 471 giao lịch sử cho TV3. Xem §4.5 |
| 9 | Ưu tiên frame sâu nhất | Dữ liệu TR-1 cho kết quả ngược; giữ frame làm anchor như hiện nay |
| 12 | Chạy R1 trên 31 task "đã lọc qua TR-1, SC-1"; 19 task "chưa sạch" | 31 task được chọn theo checkout có sẵn, không qua lọc; [rq] dùng bộ dev 50 task |
| 12 | Dùng `pyserini` hoặc `rank_bm25` | Repo đã có BM25 riêng (`run_bm25_retrieval.py`) |
| 13 | Module `vgar.retrieval.rt1_engine`, hàm `build_context_bundle` | Không có trong repo; dùng `GraphContextRetriever` và `sqlite_service` sẵn có |
| 10 | Giảm điểm anchor là tên phổ biến theo tỉ lệ file chứa tên (cờ `common_anchor_share`) | Không có trong [P] 972–993 và [plan] dòng 132; ý tưởng đến từ bàn giao TR-1. Để làm sau, nếu R1 cho thấy anchor nhiễu làm giảm recall |
| 1 | Hai profile `RT1_R1_OPTIMIZED` và `RT1_FULL_PLAN` | Một `RT1_CONFIG` cùng cờ bật/tắt đã đủ cho đo từng phần; thêm profile thứ hai khi R1 cần |
