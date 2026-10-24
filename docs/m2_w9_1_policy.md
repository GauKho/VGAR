# M2-W9-1 — Policy A0/A1/A2 và kết quả kiểm thử

Lập ngày 21/10/2026; nghiệm thu lại ngày 22/10/2026; baseline code `525f9936a3c0abe5ea056c532c1f889ce84627a7`.

**Trạng thái: M2-W9-1 hoàn thành theo tiêu chí deliverable của `VGAR_W9_W16_Deliverables.md`.** Ngày 22/10 kiểm lại 28 policy tests PASS, selected regression 48 PASS (đã gồm 28 policy tests), lint PASS. Review M1/M3 không phải điều kiện nghiệm thu riêng của W9-1. M2-W9-0 vẫn chờ review/environment baseline; không đóng thay task đó.

Hiện W9-2 đã có verifier opt-in nhận `variant`; chưa nối profile W9 qua root pipeline/session, thuộc công việc integration sau. Không yêu cầu hoàn tất integration hoặc SWE-bench để đóng deliverable policy.

## 1. Đã làm gì?

Ví dụ một patch làm tests PASS nhưng Ruff phát hiện lỗi mới: A0/A1 chỉ lấy tests làm check bắt buộc; A2 còn yêu cầu syntax/mypy/Ruff. W9-1 định nghĩa chính xác sự khác biệt này dưới dạng config và loader kiểm tra; bản thân module policy không chạy các checks. Phần thực thi verifier opt-in nằm trong W9-2, không phải đầu ra bổ sung của W9-1.

| Variant | Required checks | Recorded checks khai báo | Retrieval arm hiện tại |
|---|---|---|---|
| A0 | tests | tests, syntax, mypy, ruff | null — chưa chốt |
| A1 | tests | tests, syntax, mypy, ruff | null — chưa chốt |
| A2 | tests, syntax, mypy, ruff | tests, syntax, mypy, ruff | null — chưa chốt |

Đề xuất A0=BM25/A1,A2=graph vẫn chờ M1/M3 review; không dùng việc triển khai required checks để tự phê duyệt mapping này.

## 2. File và API

| File | Vai trò |
|---|---|
| `src/vgar/repair/policy.py` | Model immutable `VariantPolicy`, loader, canonical hash, đọc tập required checks |
| `configs/m2/variants/A0.json`, `A1.json`, `A2.json` | Ba policy riêng, không trộn vào `demo.json` của W78 |
| `tests/m2/w910/test_policy.py` | 28 tests mới: config, required sets, invalid inputs, hashing, immutability và default W78 |
| `docs/status/m2.md`, `docs/m2_w9_decisions.md`, `PROGRESS.md` | Trạng thái, quyết định và checkpoint |

```python
from pathlib import Path
from vgar.repair.policy import load_variant, policy_hash, required_checks

policy = load_variant(Path('configs/m2/variants/A2.json'))
checks = required_checks(policy)  # frozenset({'tests', 'syntax', 'mypy', 'ruff'})
fingerprint = policy_hash(policy)
assert policy.arm is None  # Chưa có mapping retrieval được duyệt.
```

Loader từ chối unknown/missing variant, required sets khác plan, check trùng hoặc không hỗ trợ, recorded checks thiếu, mode/version không hỗ trợ và extra fields. Không có fallback âm thầm sang A0. Output object immutable, không phụ thuộc file bị sửa về sau.

Các checks có tính tập hợp được chuẩn hóa thứ tự; thứ tự keys JSON và formatting không đổi hash. Hash gồm `variant_id`, `arm`, `required_checks`, `recorded_checks`, `static_mode`, `diagnostic_identity_version` sau khi validate và áp defaults; không gồm timestamp hoặc đường dẫn file. Field `policy_hash` tự khai bị từ chối. Đây không phải fingerprint toàn bộ experiment/model/runtime.

| Config | Policy SHA-256 |
|---|---|
| A0 | `sha256:bca5f7b7f208f217ce72373305e8325922ed6a43ebe378305920bc50ebfacbbf` |
| A1 | `sha256:2b29abdb298d364685edf0236556cb648eb61d7cb5160d2380783a3a894bef00` |
| A2 | `sha256:2f7c85d1124c77b5f5c67160e8acc644e64cf638d9bdcc10bbab4eb768be55ca` |

`static_mode` và diagnostic identity version là định danh cho consumer; riêng W9-1 chỉ định nghĩa và kiểm tra chúng, không chứng minh thuật toán baseline-delta. Thuật toán hiện đã có trong W9-2; xem báo cáo W9-2 và evidence riêng. Không truyền VariantPolicy thay RepairPolicy vào pipeline hiện tại: đây là hai vai trò khác nhau, chưa có experiment integration xuyên root session.

## 3. Kiểm thử thực tế và giới hạn

Evidence root: `results/m2/w9/m2-w9-1/20261021/` (ignored, không commit raw results).

| Lượt | Kết quả | Ý nghĩa |
|---|---|---|
| `red.json` | 4 FAIL ở unknown variant tests | Thất bại trước implementation vì module mới chưa có; giữ traceback |
| `red_full.json` | 27 FAIL + 1 PASS | RED của các tests mới; check default W78 đã PASS trước implementation |
| `green.json` | 28 PASS; command duration 988 ms | Policy implementation đạt tests mới |
| `regression.json` | 48 PASS; command duration 945 ms | 28 policy + 20 contract/config hiện hữu; không cộng thành 76 tests |
| `lint.json` | C408 trong test helper | Lỗi style được sửa thành dict literal, không auto-fix source khác |
| `lint_green.json` | All checks passed; 115 ms | Ruff 0.16.5 có sẵn; chưa phải pin repo 0.17.0 |
| `policy_hashes.json` | SyntaxError ở command `python -c` do PowerShell quoting | Lỗi câu lệnh thu evidence; không phải lỗi policy/model. Giữ log, chuyển sang helper file |
| `policy_hashes_file.json` | Exit 0, sinh hashes ở bảng trên | Dùng helper Python file, tránh lặp cách quote sai |

Cả stdout/stderr, argv/cwd/interpreter, exit code, UTC start/end, duration và timeout flag được lưu trong mỗi command JSON; GREEN/regression có JUnit tương ứng. RED là bước TDD có chủ đích, không phải regression W78.

Interpreter thực chạy: `D:\Project\CAPSTONES\.venv\Scripts\python.exe`, Python 3.13.0; pytest 8.4.2 và Pydantic 2.13.5. Gói `python-dotenv` hiện có để import package `vgar`. Không cần tokenizer/model cho nhóm tests này. Không cài thêm package hoặc thay phiên bản môi trường dùng chung.

**Full repository/W78 runtime suite vẫn NOT_RUN** vì tokenizer assets thiếu và dependencies ngoài nhóm tests này chưa qualified; xem `full_suite_status.json` và preflight W9-0. Không có claim về real repair, SWE-bench, baseline-delta hoặc toàn pipeline từ 48 tests này.

## 4. Tự chạy tests trong PowerShell

Các lệnh sau dùng interpreter đã dùng trong evidence. Nếu chạy trên máy khác, thay path interpreter bằng môi trường đã cài dependencies phù hợp.

```powershell
# Vào đúng repo; kiểm thử chỉ file mới và contract/config, không chạy model.
Set-Location 'D:\Project\CAPSTONES\VGAR'

# Chọn Python đã dùng ở lần kiểm; không tự cài lại dependencies.
$python = 'D:\Project\CAPSTONES\.venv\Scripts\python.exe'

# Khớp environment kiểm thử: UTF-8, không ghi bytecode, không nạp plugin pytest ngoài.
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'src')

# Chạy 28 policy tests; mong đợi PASS và exit 0.
& $python -B -m pytest tests/m2/w910/test_policy.py -q -p no:cacheprovider
$LASTEXITCODE

# Chạy 48 tests gồm policy + contract/config cũ; không phải full suite.
& $python -B -m pytest tests/m2/w910/test_policy.py tests/m2/w78/test_w78_contracts.py tests/m2/w78/test_w78_config.py tests/m2/test_contracts.py -q -p no:cacheprovider
$LASTEXITCODE
```

Các override trên chỉ đặt trong PowerShell session hiện tại. Khi chạy bộ tests khác cần external pytest plugins, dùng terminal mới hoặc khôi phục biến tương ứng; không suy ra chúng là cấu hình CI toàn repo.

## 5. Bàn giao và điểm dừng

M1 reviewer có thể kiểm module/config/tests độc lập; M3 cần biết arm vẫn unresolved và chưa có policy wiring vào root run/session. Verifier opt-in đã được triển khai riêng trong W9-2; full integration thuộc task sau, không tự chạy tiếp.

Chưa có M1/M3 review receipt, chưa merge/commit/push. Đây là trạng thái quy trình bàn giao, không phải blocker của tiêu chí W9-1. Giữ mọi thay đổi chưa commit từ W9-0/W9-2 và tài liệu riêng của người dùng.

## 6. Nghiệm thu lại ngày 22/10/2026

Nguồn nghiệm thu: mục M2 tuần 9 trong `New_task/VGAR_W9_W16_Deliverables.md`, không bổ sung yêu cầu phải được M1/M3 duyệt hoặc chạy pilot cho deliverable này. Quyết định mapping `arm` vẫn để `null`, không suy ra đã được nhóm phê duyệt.

Evidence mới: `results/m2/w9/m2-w9-1/20261022-close-policy/`. Evidence 21/10 được giữ nguyên.

| Kiểm tra | Kết quả mới | Evidence |
|---|---|---|
| Policy tests | 28 PASS, exit 0; pytest 1,53 giây, command 2.262 ms | `policy.json`, `policy.junit.xml` |
| Selected contract/config regression | 48 PASS, exit 0; gồm 28 policy + 20 tests hiện hữu; pytest 0,54 giây, command 1.239 ms | `regression.json`, `regression.junit.xml` |
| Lint module policy và tests | PASS, exit 0, command 1.596 ms; Ruff 0.16.5 hiện có, không phải pin 0.17.0 | `lint.json` |
| Config và policy hashes | A0/A1/A2 exact required sets đúng; arm vẫn null; policy hashes khớp bảng ở mục 2 | `policy_hashes.json` |
| Bảo toàn source | Đối chiếu snapshot trước/sau; chỉ cho phép ba tài liệu/checkpoint của lần nghiệm thu này thay đổi | `before.json`, `after.json` |

Mỗi command record lưu argv/cwd/interpreter, stdout/stderr, exit code, UTC start/end, duration đo monotonic và trạng thái timeout. Interpreter Python 3.13.0, pytest 8.4.2, Pydantic 2.13.5; không cài thêm gói. `record_close.py` trong evidence là helper thu log cục bộ, không phải API production.

Các test đã kiểm exact required sets, unknown/missing variant, invalid config, không fallback, hash ổn định/nhạy với thay đổi semantics và default W7–8 không đổi. Không cần sửa code/config/tests. Full repository/runtime qualification vẫn chưa được xác nhận; không gọi 48 tests là full suite hoặc cộng thành 76.

**Kết luận: hoàn thành M2-W9-1 theo tiêu chí deliverable; không tuyên bố tuần 9 hoặc toàn pipeline đã Done. Chờ người dùng ra lệnh; chưa được phép bắt đầu task tiếp theo.**

**Chờ người dùng ra lệnh; chưa được phép bắt đầu task tiếp theo.**
