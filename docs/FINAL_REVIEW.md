# Final review và fix pass — 14/10/2026

Theo skill executing-plans, một reviewer fresh context (gpt-6-astra) đã review
read-only toàn package; không sửa file, không chạy models, không spawn reviewer
thứ hai. Không có Critical trong approved trusted-fixture scope.

## Important và xử lý

| Finding | Sửa | Test tái hiện |
|---|---|---|
| Terminal PASS xuất hiện trước bundle/cleanup | Cleanup độc lập, bắt lỗi trên cùng run; chuẩn bị terminal record, ghi bundle/hash trước publish canonical; artifacts.bundle có path | `test_finalization.py`: bundle/cleanup faults, canonical hash |
| Public tests PASS khi required bị skip | Projection dùng assessed required/regression status, public reasons và raw pytest status riêng; top-level non-PASS reason có dữ liệu | `test_review_guards.py::test_public_bundle_uses_assessed_tests_not_raw_exit_zero` |
| Tokenization/workspace/reference vượt deadline | Remaining deadline đi qua Git setup/reference/worker; observe chặn stage và generation hết budget | Ba deadline tests trong `test_review_guards.py` |
| Export applied diff lỗi vẫn apply PASS | Ghi lệnh diff vào apply evidence; incomplete/non-PASS export làm ERROR, không chạy verifier | `test_review_guards.py::test_applied_diff_export_failure_is_error` |

RED finalization: `results/tests/20261014T092414173775Z-11cf41314bf1/run_record.json`
(4 failures). GREEN: `20261014T092541735569Z-e703c9592ee6` (4 pass).
RED review guards: `20261014T092655109032Z-594cc738633a` (5 failures).
GREEN combined: `20261014T092804983040Z-297a1b66c7ae` (9 pass).
Full suite sau fix: `20261014T092916031507Z-e46dedd4f6bb` (76 pass).
Checkpoint cuối dùng full-suite receipt mới hơn trong `PROGRESS.md` nếu có.

Thêm coverage acceptance: descendant bị kill khi parent thoát trước; thiếu
mypy/Ruff khiến baseline ERROR. Các tests mới trên behavior đã có chạy GREEN,
không giả nhận là bug đã RED. Regression missing/skip/xfail giờ phân loại
incomplete ERROR, không assertion FAIL.

## Minor / giới hạn

- JUnit mới kiểm XML parse hợp lệ, chưa đối chiếu counters/testcases với reporter;
  deferred. Exact guards vẫn dùng node IDs/outcomes của reporter và command.
- Coverage gap của missing tools/process descendants đã nâng thành acceptance
  test gap và bổ sung; không phải đổi runtime policy.
- `artifacts.bundle` đã xử lý cùng Important finalization, không sửa polish riêng.

## Những phần reviewer không đánh giá, ruling của implementer

- Ba real repairs: gate chưa đạt; không retry sau hai failures. Cost: acceptance
  phải chờ owner duyệt phương pháp mới, không dùng fake làm kết quả model.
- Arbitrary repo/OS sandbox/benchmark/Linux: ngoài profile được user duyệt.
  Cost: package không nghiệm thu cho những môi trường đó.
- M1 ranking/M3 transport/API/structural/dirty VGAR: không sửa ownership khác.
  Cost: integrated-system gate vẫn chưa nghiệm thu.
- Guide/checkpoint: author hoàn thiện bằng code/evidence actual; chưa có independent
  human reproduction. Cost: đồng đội cần tự chạy lại.
- Model quality/weight cache integrity: chỉ claim pinned local invocation và hai
  outputs đã ghi, không claim hiệu quả tổng quát hoặc hashing toàn weights.
  Cost: không sử dụng các run làm bằng chứng benchmark.

Không review lần hai, không inference sau fix. Các failure model giữ nguyên.
Không có commit/push. Ledger/evidence được giữ vì chưa có commit-based recovery.
