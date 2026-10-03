# Review và cách khắc phục — M2 W5–6

Review độc lập giới hạn `M2_week_5_6/src,scripts,tests,docs/IMPLEMENTATION_PLAN.md`, không sửa repo, không chạy unrecorded tests/network. Không có Critical. Một lượt sửa các Important, có regression tests RED→GREEN; không dispatch review lại.

| Finding | Fix | Regression test |
|---|---|---|
| splitlines hiểu sai formfeed/Unicode separators | Shared CR/LF physical_lines cho AST slices/diff/M1 snippets | test_formfeed_does_not_shift_ast_diff_or_chunk_lines |
| Module-only successful parse `[]` bị coi là parse failure | after_ok riêng với danh sách function | test_module_only_change_does_not_exclude_other_gold_function |
| Resume đọc task đã bị sửa | Hash task bytes + metadata/metrics/manifest binding | test_tampered_resume_task_is_rejected |
| M1 valid JSON nhưng root [] làm abort | Validate object shapes, catch lỗi per-export, finalize evidence | test_malformed_m1_root_does_not_abort_comparison_evidence |
| Same qname definitions gây false gold hit | Span-disambiguated IDs + before/after line origins | test_duplicate_qualified_definition_is_not_a_false_gold_hit |
| MRR tail không replay từ top100 snippets | Lưu complete dedup file/function ordering | test_complete_rank_identity_trace_replays_tail_mrr |
| BM25 sum theo unsorted set không deterministic | Sort unique query terms | test_bm25_scores_are_identical_across_python_hash_seeds |
| Chuẩn bị/comparison thiếu executing fingerprint/duration/log | Bổ sung metadata recorder; regraded là requirement evidence | result JSON của dataset/comparison cuối |
| Thực tế matplotlib hunk header lệch 2 lines | Exact unique context relocation, log offset, không fuzzy | test_exact_unique_context_relocation_reports_offset_and_maps_actual_line |
| Corpus giữ testing/ của pytest | Bổ sung explicit testing directory exclusion | test_pytest_testing_directory_is_not_production_corpus |

RED review: `results/tests/20261001T134120716670Z-ab8ea11e4e6e/result.json` và `results/tests/20261001T134512501764Z-08698f16fbba/result.json`.
GREEN 41 tests: `results/tests/20261001T134556113383Z-2fbf1a287c70/result.json` (bản cuối sẽ có thêm test run verification, không thay source).

Các run trước sửa được giữ nguyên, không dùng số liệu cũ làm bảng cuối. Source caches được tái dùng chỉ để tránh tải lại dữ liệu immutable, không tái dùng metrics khác fingerprint.

## Rulings / hạn chế không giả là đã giải quyết

- Isolation là thư mục mới không gắn Git repo cũ; không worktree/auto commit/push. Lợi ích: giữ scope; đánh đổi: chưa có commit history cho package mới.
- Bộ 25 là pilot repo-stratified provisional, chưa stratify difficulty/patch size hoặc nhận manifest chung M3. Không tuyên bố random representative/final blind benchmark.
- GitHub archive dùng SHA URL/root/archive hash/source hash, không cryptographic Git object proof. Đánh đổi đã ghi provenance, không ngầm gọi Git verification PASS.
- Token là estimator chung, không actual tokenizer/billing. API cost=0; không ước đoán năng lực coding model từ metric này.
- Chưa có Graph output thật nên bảng paired chưa đạt DoD; static adapter tests không thay được benchmark/live collaboration.
- Inspection từng10 do assistant, không phải xác nhận của thành viên/leader/human audit độc lập.

Các mục reviewer không đánh giá live reliability/final25/docs/manual10 đã được kiểm tra bằng run artifacts/inspection/docs của root; phần M1/Git proof/actual LLM token vẫn để mở theo phạm vi nói trên. Không có sửa style ngoài task hoặc thay đổi repo cũ.
