# Kết quả retrieval M2 tuần 5–6

Run: `baseline`; dataset: `fixture` @ `fixture-revision`.
Attempted: 1; completed: 1; failed: 0.
Scoring: `retrieval-scoring-v1`; budget: 200 token; counter: `FALLBACK:utf8_bytes_ceil_div4`.

> **CẢNH BÁO — counter dự phòng bytes/4.** Số token dưới đây KHÔNG so được với M1 `LocalTokenizerCounter`. Không dùng cho bảng Graph vs BM25 chính thức; chạy lại với tokenizer manifest.

Đây là retrieval pilot, không chạy agent sửa code, không chứng minh tỷ lệ repair PASS. Gold là changed-code proxy từ developer patch.

## Số chính — rank đầy đủ (dedup trước k)

Recall@k và MRR tính trên toàn bộ ranking, không phụ thuộc budget. Gold mà arm không chạm tới là miss (MRR đóng góp 0), task không bị loại. `*_reach` = tỉ lệ gold xuất hiện ở bất kỳ hạng nào.

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| file_recall@3 | 1.0000 | 1 |
| file_recall@5 | 1.0000 | 1 |
| file_recall@10 | 1.0000 | 1 |
| function_recall@3 | 1.0000 | 1 |
| function_recall@5 | 1.0000 | 1 |
| function_recall@10 | 1.0000 | 1 |
| file_mrr | 1.0000 | 1 |
| function_mrr | 1.0000 | 1 |
| file_reach | 1.0000 | 1 |
| function_reach | 1.0000 | 1 |

## Số phụ — context đóng gói @200 token

Phản ánh thứ agent thực sự nhìn thấy: cùng counter, cùng budget, cùng snippet policy (tối đa 80 dòng/snippet, có header `path::symbol`). `tokens_to_first_gold_*` chỉ tính trên task có gold trong context (xem Eligible).

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| packed_gold_file_in_context | 1.0000 | 1 |
| packed_gold_function_in_context | 1.0000 | 1 |
| packed_all_gold_files_in_context | 1.0000 | 1 |
| packed_all_gold_functions_in_context | 1.0000 | 1 |
| context_tokens | 17.0 | 1 |
| packed_tokens_to_first_gold_file | 17.0 | 1 |
| packed_tokens_to_first_gold_function | 17.0 | 1 |
| packed_items_packed | 1.0 | 1 |
| packed_truncated | 0.0000 | 1 |

## Graph vs BM25

Hai chế độ cùng đọc từ một rank mỗi task. Số chính là rank đầy đủ; số phụ là context đóng gói. Nếu hai số mâu thuẫn (Graph thắng ở rank, thua ở packed) thì phân tích, không chọn số đẹp hơn.

Comparison status: **COMPARED**; paired tasks: 1/1.

| Run | Attempted | Succeeded | Failed/Error | NOT_RUN |
|---|---:|---:|---:|---:|
| bm25 | 1 | 1 | 0 | 0 |
| graph | 1 | 1 | 0 | 0 |

Các mean dưới đây chỉ dùng paired successes; không coi tasks lỗi là successes hoặc bỏ denominator của chúng khỏi coverage.

Primary: BM25 full rank và Graph ranking đã lưu; Graph max_candidates = 100. Số reach phải đọc cùng giới hạn candidate universe, không coi hai ranking có cùng độ dài.

`graph` là issue-only; `graph+F2P` là **oracle-assisted** dùng test IDs FAIL_TO_PASS từ benchmark metadata, không phải failing tests đã được quan sát khi chạy base environment. Không gộp hai arm khi claim fairness.

### Rank đầy đủ (chính)

| Metric | bm25 (full rank) | graph | graph+F2P (oracle-assisted) |
|---|---:|---:|---:|
| file_recall@3 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| file_recall@5 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| file_recall@10 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| function_recall@3 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| function_recall@5 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| function_recall@10 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| file_mrr | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| function_mrr | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| file_reach | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| function_reach | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |

### Context đóng gói (phụ)

| Metric | bm25 (full rank) | graph | graph+F2P (oracle-assisted) |
|---|---:|---:|---:|
| packed_gold_file_in_context | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| packed_gold_function_in_context | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| packed_all_gold_files_in_context | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| packed_all_gold_functions_in_context | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) |
| context_tokens | 17.0 (n=1) | 17.0 (n=1) | 17.0 (n=1) |
| packed_tokens_to_first_gold_file | 17.0 (n=1) | 17.0 (n=1) | 17.0 (n=1) |
| packed_tokens_to_first_gold_function | 17.0 (n=1) | 17.0 (n=1) | 17.0 (n=1) |
| packed_items_packed | 1.0 (n=1) | 1.0 (n=1) | 1.0 (n=1) |
| packed_truncated | 0.0000 (n=1) | 0.0000 (n=1) | 0.0000 (n=1) |

### Delta theo cặp task

**graph − bm25 (full rank)** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| file_recall@5 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| file_recall@10 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_recall@3 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_recall@5 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_recall@10 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| file_mrr | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_mrr | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| packed_gold_file_in_context | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| packed_gold_function_in_context | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| context_tokens | 1 | +0.0 | [+0.0, +0.0] | 0 / 1 / 0 |

**graph+F2P (oracle-assisted) − bm25 (full rank)** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| file_recall@5 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| file_recall@10 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_recall@3 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_recall@5 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_recall@10 | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| file_mrr | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| function_mrr | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| packed_gold_file_in_context | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| packed_gold_function_in_context | 1 | +0.0000 | [+0.0000, +0.0000] | 0 / 1 / 0 |
| context_tokens | 1 | +0.0 | [+0.0, +0.0] | 0 / 1 / 0 |

### Chẩn đoán Graph (quyết định hybrid vs giảm nhiễu anchors)

| Arm | Task không có anchor | Anchors/task | Unmapped (tổng) | Unmapped/task | Candidates/task |
|---|---:|---:|---:|---:|---:|
| graph | 0 | 1.0 | 0 | 0.00 | 3.0 |
| graph+F2P (oracle-assisted) | 0 | 1.0 | 0 | 0.00 | 3.0 |

### Theo repo (mean File R@5 / Function R@5)

| Repo | n | bm25 (full rank) | graph | graph+F2P (oracle-assisted) |
|---|---:|---:|---:|---:|
| o/r | 1 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |

### Task cần kiểm tay (Δ = Δfile R@5 + Δfunction R@5 so với bm25 (full rank))



## Per task

| Instance | Status | File R@5 | Function R@5 | Gold fn in context | Mapping coverage |
|---|---|---:|---:|---:|---:|
| t-2 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
