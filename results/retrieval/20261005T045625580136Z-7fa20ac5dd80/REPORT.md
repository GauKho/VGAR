# Kết quả retrieval M2 tuần 5–6

Run: `20261005T045625580136Z-7fa20ac5dd80`; dataset: `princeton-nlp/SWE-bench_Verified` @ `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
Attempted: 25; completed: 25; failed: 0.
Scoring: `retrieval-scoring-v1`; budget: 8000 token; counter: `local-hf:Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554:sha256=aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4:no-special-tokens`.

Đây là retrieval pilot, không chạy agent sửa code, không chứng minh tỷ lệ repair PASS. Gold là changed-code proxy từ developer patch.

## Số chính — rank đầy đủ (dedup trước k)

Recall@k và MRR tính trên toàn bộ ranking, không phụ thuộc budget. Gold mà arm không chạm tới là miss (MRR đóng góp 0), task không bị loại. `*_reach` = tỉ lệ gold xuất hiện ở bất kỳ hạng nào.

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| file_recall@3 | 0.3600 | 25 |
| file_recall@5 | 0.5267 | 25 |
| file_recall@10 | 0.5933 | 25 |
| function_recall@3 | 0.2000 | 25 |
| function_recall@5 | 0.2783 | 25 |
| function_recall@10 | 0.4217 | 25 |
| file_mrr | 0.5907 | 25 |
| function_mrr | 0.4168 | 25 |
| file_reach | 1.0000 | 25 |
| function_reach | 1.0000 | 25 |

## Số phụ — context đóng gói @8000 token

Phản ánh thứ agent thực sự nhìn thấy: cùng counter, cùng budget, cùng snippet policy (tối đa 80 dòng/snippet, có header `path::symbol`). `tokens_to_first_gold_*` chỉ tính trên task có gold trong context (xem Eligible).

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| packed_gold_file_in_context | 0.6767 | 25 |
| packed_gold_function_in_context | 0.4391 | 25 |
| packed_all_gold_files_in_context | 0.4400 | 25 |
| packed_all_gold_functions_in_context | 0.2000 | 25 |
| context_tokens | 7997.3 | 25 |
| packed_tokens_to_first_gold_file | 1163.0 | 23 |
| packed_tokens_to_first_gold_function | 1694.4 | 18 |
| packed_items_packed | 22.9 | 25 |
| packed_truncated | 1.0000 | 25 |

## Graph vs BM25

Hai chế độ cùng đọc từ một rank mỗi task. Số chính là rank đầy đủ; số phụ là context đóng gói. Nếu hai số mâu thuẫn (Graph thắng ở rank, thua ở packed) thì phân tích, không chọn số đẹp hơn.

**AWAITING_GRAPH**: cần RankRecord thật của Graph (từ `RetrievalResult.candidates`, cùng corpus/counter/budget); không dùng demo fixture thay benchmark.

## Per task

| Instance | Status | File R@5 | Function R@5 | Gold fn in context | Mapping coverage |
|---|---|---:|---:|---:|---:|
| astropy__astropy-13398 | SUCCEEDED | 0.3333 | 0.0000 | 0.8000 | 1.0000 |
| django__django-11138 | SUCCEEDED | 0.5000 | 0.0000 | 0.0769 | 1.0000 |
| matplotlib__matplotlib-14623 | SUCCEEDED | 0.0000 | 0.1667 | 0.1667 | 1.0000 |
| pydata__xarray-3305 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-4551 | SUCCEEDED | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| sphinx-doc__sphinx-10673 | SUCCEEDED | 0.3333 | 0.4000 | 0.2000 | 1.0000 |
| sympy__sympy-16597 | SUCCEEDED | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| astropy__astropy-8707 | SUCCEEDED | 0.5000 | 0.0000 | 0.5000 | 1.0000 |
| django__django-11734 | SUCCEEDED | 0.3333 | 0.3333 | 0.3333 | 1.0000 |
| pydata__xarray-3993 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-4604 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
| sphinx-doc__sphinx-8120 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| sympy__sympy-17318 | SUCCEEDED | 1.0000 | 0.6667 | 0.6667 | 1.0000 |
| django__django-11885 | SUCCEEDED | 0.5000 | 0.3750 | 0.5000 | 1.0000 |
| pydata__xarray-6992 | SUCCEEDED | 0.5000 | 0.3333 | 0.6667 | 1.0000 |
| pylint-dev__pylint-6386 | SUCCEEDED | 0.5000 | 0.0000 | 0.4000 | 1.0000 |
| sphinx-doc__sphinx-8548 | SUCCEEDED | 1.0000 | 0.5000 | 1.0000 | 1.0000 |
| sympy__sympy-20438 | SUCCEEDED | 0.3333 | 0.2500 | 0.5000 | 1.0000 |
| django__django-12155 | SUCCEEDED | 0.5000 | 0.3333 | 0.6667 | 1.0000 |
| django__django-12325 | SUCCEEDED | 1.0000 | 0.5000 | 1.0000 | 1.0000 |
| django__django-12741 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| django__django-13195 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| django__django-13212 | SUCCEEDED | 0.5000 | 0.1000 | 0.5000 | 1.0000 |
| django__django-13344 | SUCCEEDED | 0.3333 | 0.0000 | 0.0000 | 1.0000 |
| django__django-13512 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
