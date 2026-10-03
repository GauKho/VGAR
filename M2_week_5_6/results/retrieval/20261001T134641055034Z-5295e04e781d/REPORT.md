# Kết quả retrieval M2 tuần 5–6

Run: `20261001T134641055034Z-5295e04e781d`; dataset: `princeton-nlp/SWE-bench_Verified` @ `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
Attempted: 25; completed: 25; failed: 0.

Đây là retrieval pilot, không chạy agent sửa code, không chứng minh tỷ lệ repair PASS. Gold là changed-code proxy từ developer patch.

## BM25 — ranking đầy đủ, dedup trước k

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| file_recall@3 | 0.2086 | 25 |
| file_recall@5 | 0.3952 | 25 |
| file_recall@10 | 0.6152 | 25 |
| function_recall@3 | 0.0895 | 25 |
| function_recall@5 | 0.1095 | 25 |
| function_recall@10 | 0.1855 | 25 |
| file_mrr | 0.4450 | 25 |
| function_mrr | 0.2581 | 25 |
| context_token_estimate | 3995.9600 | 25 |
| mapping_coverage | 1.0000 | 25 |
| file_retrievability_coverage | 0.9900 | 25 |

Token cost là estimate ceil(UTF-8 bytes/4), bao gồm path/symbol header và snippet; không phải bill/tokenizer LLM. API cost = 0 vì không gọi LLM.

## Graph vs BM25 — cùng budget context

Không so Graph context hữu hạn với toàn bộ BM25 ranking. Bảng paired chỉ dùng context đã đóng gói cùng token policy.

Comparison status: **AWAITING_M1**; paired tasks: 0/25.

**Chưa có M1 output thật. Không có số đo Graph; chưa đạt DoD paired comparison.**


## Per task

| Instance | Status | File R@5 | Function R@5 | Mapping coverage |
|---|---|---:|---:|---:|
| astropy__astropy-13398 | SUCCEEDED | 0.3333 | 0.0000 | 1.0000 |
| django__django-10554 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| matplotlib__matplotlib-14623 | SUCCEEDED | 0.0000 | 0.1667 | 1.0000 |
| mwaskom__seaborn-3187 | SUCCEEDED | 0.5000 | 0.5000 | 1.0000 |
| pydata__xarray-3095 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-4551 | SUCCEEDED | 0.0000 | 0.0000 | 1.0000 |
| pytest-dev__pytest-5840 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| scikit-learn__scikit-learn-12682 | SUCCEEDED | 1.0000 | 0.1538 | 1.0000 |
| sphinx-doc__sphinx-10673 | SUCCEEDED | 0.3333 | 0.4000 | 1.0000 |
| sympy__sympy-13091 | SUCCEEDED | 0.0476 | 0.0179 | 1.0000 |
| astropy__astropy-14369 | SUCCEEDED | 1.0000 | 0.5000 | 1.0000 |
| django__django-11138 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| matplotlib__matplotlib-24870 | SUCCEEDED | 0.0000 | 0.0000 | 1.0000 |
| pydata__xarray-3305 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-4604 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| pytest-dev__pytest-8399 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| scikit-learn__scikit-learn-25102 | SUCCEEDED | 0.0000 | 0.0000 | 1.0000 |
| sphinx-doc__sphinx-7462 | SUCCEEDED | 0.0000 | 0.0000 | 1.0000 |
| sympy__sympy-13877 | SUCCEEDED | 0.5000 | 0.5000 | 1.0000 |
| astropy__astropy-8707 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| django__django-11333 | SUCCEEDED | 0.5000 | 0.5000 | 1.0000 |
| matplotlib__matplotlib-25479 | SUCCEEDED | 0.0000 | 0.0000 | 1.0000 |
| pydata__xarray-3993 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-6386 | SUCCEEDED | 0.5000 | 0.0000 | 1.0000 |
| sphinx-doc__sphinx-7590 | SUCCEEDED | 0.6667 | 0.0000 | 1.0000 |
