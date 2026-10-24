# M1-W9-5 — Môi trường task bằng Docker

**Hoàn thành kỹ thuật theo tiêu chí M1-W9-5: 3 COLLECTED và 2 EXCLUDED có lý do.**
Đủ kết quả và profile cho cả 5 task. Điều này không có nghĩa cả 5 task đều runnable.
Review/merge nhóm, M2 admission và quyết định population pilot được xử lý riêng.

## Kết quả collection thật

Run `w95-3178eb33a42b414d81656b21b64cc2e2`: COMPLETE. Raw records, profiles và logs ở `results/m1/w9/m1-w9-5/collection-runs/w95-3178eb33a42b414d81656b21b64cc2e2/` (ignored).

| Task | Kết quả | Node IDs ghi nhận | Pytest exit | Python / pytest |
|---|---|---|---|---|
| astropy__astropy-13398 | EXCLUDED | 23146 | 2 | 3.9.20 / 7.4.0 |
| django__django-11138 | EXCLUDED | 0 | None | 3.6.13 / None |
| matplotlib__matplotlib-14623 | COLLECTED | 7892 | 0 | 3.8.20 / 8.3.4 |
| pydata__xarray-3305 | COLLECTED | 8713 | 0 | 3.10.15 / 7.4.0 |
| pylint-dev__pylint-4551 | COLLECTED | 1429 | 0 | 3.9.20 / 6.2.5 |

- Astropy: 23.146 node IDs là collection một phần; exit 2 với 2 collection errors
  tại astropy/convolution/tests/test_convolve_kernels.py. NumPy phát
  DeprecationWarning về chuyển array có ndim > 0 sang scalar; cấu hình base coi
  warning này là lỗi khi import Gaussian2DKernel/discretize_model. Không bỏ warning,
  cắt scope hoặc đổi dependency để ép PASS. Giữ đầy đủ raw errors.
- Django: target Python 3.6.13 không có module pytest; ghi PYTEST_UNAVAILABLE.
  Không cài pytest hoặc thay bằng native unittest rồi gọi là pytest collection PASS.
- Matplotlib: 7.892 node IDs; Xarray: 8.713; Pylint: 1.429. Cả ba exit 0 và không có
  collection errors. Đây là collection, chưa phải test execution hay repair PASS.

Cả 5 candidate vẫn nằm trong manifest gốc. Không tự xóa hai task bị loại hoặc
thay denominator. Việc chuẩn bị pilot 5 task/15 records cần quyết định riêng cho
hai môi trường chưa đủ điều kiện; báo cáo này không nghiệm thu pilot đó.

## Contract vgar-task-env-v1

Bốn field tối thiểu: `task_id`, `base_commit`, `env_ref`, `test_command`.

- `task_id`, `repo`, `base_commit` bind task trong manifest cố định. Consumer gọi
  `validate_profile(profile, expected_task=manifest_task)` để kiểm binding.
- `env_ref` có dạng `docker://swebench/sweb.eval.x86_64.<task>@sha256:<digest>`.
  `image_id` và `daemon_id` là identities thật đã quan sát; không dùng mutable tag.
- `cwd=/testbed`; `python=/opt/miniconda3/envs/testbed/bin/python`.
- `test_command` là fixed argv `[python,-m,pytest,-q,-p,no:cacheprovider]`;
  `collection_command` thêm `--collect-only`. Không có shell/argv do model cung cấp.
- `scope=[@pytest-default]` dùng pytest discovery và cấu hình trong base repo.
  Retrieval fallback có cả negative/data fixtures, nên không ép pytest import mọi
  file trong fallback. Hai arm cùng policy; paired hints/scopes vẫn được kiểm tra
  và hash-bind. Không sửa bundles hoặc dùng gold để chọn test scope.
- `visibility=base_only_no_oracle`: không test_patch, F2P/P2P, gold hoặc model patch.
- `source_before/source_after`: HEAD, trạng thái clean của tracked tree, số lượng
  và hash tracked Python inventory. Hash dựa trên sorted `[relative_path,file_SHA256]`
  mã hóa UTF-8 JSON với separators(',',':'). Không phải hash mọi file của image.
- `runtime`: target executable, Python và pytest versions. `probe_protocol` là
  `vgar-pytest-collection-v1`. `collection`: exit_code, node_ids và errors.
- `scope_hash/profile_hash`: canonical JSON SHA-256, sorted keys, không whitespace,
  ensure_ascii=False, allow_nan=False. Hash thể hiện identity, không phải chữ ký.

API trong `src/vgar/evaluation/harness/task_env.py`:
`build_profile(task,image,scope,probe,daemon_id=...)` và
`validate_profile(profile,expected_task=...)`.
Target `collection_probe.py` chỉ cần stdlib và pytest có sẵn, hỗ trợ syntax Python
3.5 trở lên; không cài VGAR/Torch vào interpreter của repo mục tiêu.

COLLECTED yêu cầu exit 0, node_ids khác rỗng/không trùng, không collection errors,
source đúng base và không thay đổi. EXCLUDED chỉ dùng khi thiếu pytest, collection
rỗng hoặc collection fail thật, kèm reason/raw streams. Source/identity/timeout/
output-cap/cleanup failure là ERROR và dừng các task sau. Không biến lỗi hạ tầng
thành lý do loại; NOT_RUN không tính là một task đã hoàn tất collection.

## Chuẩn bị source và lifecycle

Image official có thể khởi động tại commit setup SWE-bench thay vì base commit.
Chỉ sau khi xác minh container mới đúng name/image, controller kiểm Git root là
/testbed và original base object tồn tại, rồi reset đúng SHA trong container đó.
Probe yêu cầu HEAD/clean inventory đúng trước và sau collection. Không reset repo
host hoặc sửa image layers. M2 phải bind private patched source theo bridge riêng;
không dùng bước reset base này sau khi đã áp dụng candidate patch của M2.

Container có UUID mới, network=none, cap-drop ALL, no-new-privileges, không host
mount. Verify name/image trước probe và cleanup. Collection timeout 300 giây;
capture tối đa 8 MiB mỗi stream. Incomplete/timeout/truncated không tạo profile đủ
điều kiện. Cleanup chỉ container có ownership đã chứng minh, không prune/reset.

Controller Linux/amd64, Unix endpoint rõ ràng, CLI/SDK cùng daemon. Trước pull và
collection: Windows/Linux mỗi bên có 4 GiB RAM available; C/D còn ít nhất 10/20 GiB.
Không tự hạ gate, đổi RAM/swap/settings, restart WSL hoặc đóng ứng dụng.
Trong lần nghiệm thu này người dùng duyệt riêng tối đa 6 lần sync/drop_caches=1
cho W9-5 khi không có container chạy và RAM Windows thiếu; thực dùng 1 lần.

## CLI

```bash
export PYTHONDONTWRITEBYTECODE=1
PY=/home/vgar/w9/venvs/controller/bin/python
$PY -B scripts/prepare_task_env.py --help
$PY -B scripts/prepare_task_env.py --runtime /absolute/pinned-runtime.json
$PY -B scripts/prepare_task_env.py --runtime /absolute/pinned-runtime.json --prepare-images
$PY -B scripts/prepare_task_env.py --runtime /absolute/qualified-runtime.json --execute
```

Mặc định chỉ preflight. Public runtime skeleton vẫn UNQUALIFIED, không coi clone
hoặc máy khác đã được nghiệm thu. `--prepare-images` chỉ pull missing digest đã
pin; không latest hoặc đổi tag. `--execute` mới chạy collection trong container.
Local config đã dùng: `results/m1/w9/m1-w9-5/20261024-docker-only/qualified-runtime-02.json`.

Mỗi task có `task_env.json` kể cả EXCLUDED, probe-input/result.json, collection.json,
stdout/stderr logs, record.json, source/runtime identities và cleanup evidence.
Toàn run có runtime-input.json, frozen-images.json, resource/SDK/CLI records và
run_record.json. Output dùng run mới; không ghi đè artifacts cũ.

## QA và evidence

- Linux 45 tests PASS; selected regression 320 PASS trong 35,80 giây; lint 4 file mới PASS.
- Audit độc lập kiểm 5 profiles, actual reports, pins/argv, source before=after,
  hashes và cleanup; không còn container thuộc run.
- Lượt đầu `w95-52ab71e3ab1b49cd861f8803588aa750` giữ ERROR do Astropy khởi động
  tại commit setup 4b487276 thay base 6500928; chưa collection, 4 task sau NOT_RUN.
  Diagnostic chỉ đọc chứng minh original base object tồn tại và tree khác.
  Base preparation fix qua RED 2 FAIL rồi GREEN 45 tests trước run mới.
- Các lượt lỗi quyền/encoding ở test invocation và gate RAM vẫn giữ evidence.
  Không sửa fixture cũ, scope/dependency hoặc guard để che lỗi hay đổi kết quả.

Evidence root: `results/m1/w9/m1-w9-5/20261024-docker-only/`.
Xem `independent_audit.json`, `independent_audit_receipt.json`, `collection_run_02.json`,
`collection_reservation_02.json`, `before.json`, `before_collection_02.json`,
`regression_base_fix.json`, `lint_base_fix.json` và `progress.md`.

## Bàn giao và giới hạn

M2 chưa có admission/private lease bridge, target pytest-plugin/report adapter,
static-tool hoặc test execution/verification qualification từ task này. Oracle/
test overlay cần quyết định riêng. Không thay phê duyệt M1/M2/M3 hoặc review/merge nhóm.
Full VGAR/model/gold/native không chạy; không sửa Task Status.md, commit hoặc push.
Code/config/fixtures/evidence cũ giữ nguyên; source controller frozen suốt run cuối.
Review receipt và final checkpoint/closing QA được ghi khi chốt bàn giao.


## Review và closing QA

[Review độc lập](reviews/2026-10-24-m1-w9-5-docker-review.md) không có blocker kỹ thuật.
Hai lỗi tài liệu mới (encoding và checklist chốt sớm) đã được sửa trong closing QA,
không có minor tùy chọn còn lại. Final evidence: delivery_final.json,
delivery_final_receipt.json và checkpoint_final.json trong evidence root.
