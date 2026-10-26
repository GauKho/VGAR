# M2-W9-4 — Arm và variant provenance xuyên session/evidence

Cập nhật ngày 23/10/2026. **M2-W9-4 hoàn thành kỹ thuật theo các gate đã duyệt.**
Xem [trạng thái M2](status/m2.md) và `PROGRESS.md` để biết điểm dừng cuối.
Phạm vi chỉ W9-4, không phải admission SWE-bench, real repair hoặc runner M3.

## 1. Đã bổ sung gì, nằm ở đâu?

| Thành phần | Vai trò |
|---|---|
| `src/vgar/repair/experiment.py` | Validate profile; bind explicit arm; tính policy hash; kiểm snapshot khi reload |
| `src/vgar/repair/context_adapter.py` | Optional arm/expected hashes; giữ consumer validation, khóa actual hashes |
| `src/vgar/repair/pipeline.py` | Thêm keyword `experiment=None`, chuyển vào session |
| `src/vgar/repair/session.py` | Persist profile; kiểm trước load/write; truyền policy vào baseline/verification; xuất bundle |
| `src/vgar/mcp/servers/repair_server.py` | `get_task_context` nhận experiment JSON; tools sau reload profile từ session |
| `tests/m2/w910/conftest.py` | Copy fixture W7–8 tin cậy; dùng tokenizer assets hiện có |
| `tests/m2/w910/test_context_arm.py` | Arm, expected hashes, legacy metadata và consumer fixture W9 |
| `tests/m2/w910/test_variant_provenance.py` | Policy binding, tamper, lỗi sớm, native fake repairs theo variant |
| `tests/m2/w910/test_runner_contract.py` | Reload từng bước, MCP, drift bundle, template/prompt hash giữa arms |

`repair/evidence.py` đã hỗ trợ metadata generic nên không cần refactor. Public
DTO, statuses, parser/apply guards, registry và ba policy configs không đổi.

## 2. Input và output

### 2.1. Input opt-in

Ví dụ chuẩn bị input từ config hiện có, chưa chạy repair:

```python
import json
from pathlib import Path

definition = json.loads(Path("configs/m2/variants/A0.json").read_text(encoding="utf-8"))
experiment = {"variant_policy": definition, "arm": "bm25"}
```

- Arm bắt buộc là `bm25` hoặc `graph`; không suy arm từ A0/A1/A2.
- Policy `arm=null` được bind trên bản policy hiệu lực rồi tính lại hash. Config gốc không đổi.
- Policy đã có arm khác input bị từ chối. Caller không được tự khai `policy_hash`.
- Optional `expected_hashes` phải có đúng ba keys: `context.json`,
  `context_manifest.json`, `test_links.json`. Mỗi giá trị là `sha256:` + 64 ký tự
  hex thường, lấy từ bundle/index caller đã chọn, không dùng hash ví dụ.
- Nếu không truyền expected hashes, consumer vẫn validate và engine khóa actual hashes.
- Arm là **nhãn caller khai từ handoff/index**, không phải consumer chứng minh thuật toán retrieval.
- Profile sai bị từ chối trước workspace/generation. Profile đúng nhưng context sai
  vẫn có terminal record ERROR giữ provenance.

Direct API thêm keyword:

```python
handle = run_repair(task, policy, generator, None, output_root,
    m1_counter=counter, tokenizer=tokenizer, experiment=experiment)
```

`start_session` nhận cùng keyword. MCP `get_task_context` nhận optional JSON
experiment ở cuối arguments; tools sau chỉ cần `run_dir`. Không truyền thì giữ
hành vi/metadata legacy. Fake mode vẫn cần counter/tokenizer assets hợp lệ.

### 2.2. Pending, terminal và EvidenceBundle

Cả `session.json` và `run_record.json` có từ đầu:

```text
experiment_required = true
experiment.variant_id
experiment.arm
experiment.policy_hash
experiment.variant_policy       # policy hiệu lực, đã bind explicit arm
experiment.expected_hashes      # null nếu caller không truyền
experiment.bundle_hashes        # null trước validation; actual hashes sau đó
```

Marker `experiment_required` là metadata internal độc lập để phát hiện mất
profile hai phía, không phải public DTO hoặc chữ ký xác thực. Khi baseline PASS,
cả session baseline và canonical baseline phải có hash khớp policy hiệu lực.
Baseline ERROR sớm chưa sinh hash vẫn load được nếu profile/marker hợp lệ.

EvidenceBundle lưu cùng snapshot ở `metadata.experiment` trước khi tính
`metadata.canonical_sha256` từ terminal record. Không tạo vòng hash tự tham chiếu.
M3 aggregate JSON read-only, không cần gọi `RepairSession.load` chỉ để đọc kết quả.

## 3. Flow và các giới hạn

```text
Task/bundle + explicit arm + variant definition
  → validate, bind arm, derive policy hash
  → pending record + session + marker
  → admission W7–8 giữ nguyên
  → consumer validate + expected hashes → khóa actual hashes
  → private workspace → baseline theo variant W9-2
  → prompt hiện có → generation (task này kiểm bằng fake)
  → strict parse/apply → tests → static delta theo variant
  → source integrity → cleanup → terminal record + EvidenceBundle
```

Reload đọc hai JSON và kiểm profile/hash/context/baseline **trước** `load_run`,
vì hàm đó có ghi dữ liệu. Mất profile một phía hoặc cả hai khi marker còn, policy
sai và baseline binding thiếu/sai đều fail-fast. Record legacy thực sự không có
experiment/marker vẫn load theo nhánh cũ.

Đây là consistency, không chống một bên chủ động viết lại tất cả anchors/hashes.
Byte hashes và arm label không thay authentication hoặc admission.

Variant được dùng thật: A0/A1 có thể PASS dù raw mypy FAIL khi optional; raw FAIL
vẫn được lưu. A2 yêu cầu static baseline delta. `experiment=None` giữ verdict
strict W7–8. Hai arm có thể chung template hash nhưng khác rendered-prompt hash
do context khác nhau; đó không phải lỗi binding.

Fixture W9-6 chỉ được kiểm consumer, không tự có quyền native execution. Admission
và environment SWE-bench thuộc W9-3, không được triển khai trong task này.
Runner M3 không có trong checkout, vì vậy interoperability thật vẫn NOT_RUN.

## 4. Evidence và kiểm chứng

Root mới: `results/m2/w9/m2-w9-4/20261023-implementation/` (ignored).
Mỗi command có argv, interpreter, stdout/stderr, exit code, UTC start/end,
duration; pytest có JUnit; snapshots trước/sau có hashes và HEAD.

| Check | Kết quả đã quan sát | Evidence |
|---|---|---|
| Baseline repair server trước thay đổi | 10 PASS, 69,12 giây | `planning-baseline/20261023T132810456269Z-e772396fc275/result.json` dưới root W9-4 |
| RED API/module mới | 30 FAIL do chưa có interface, không phải 30 regressions | `red.json` |
| Unit GREEN ban đầu | 27 PASS / 3 deselected | `green_unit.json` |
| Native fake repairs theo policy | 3 tests PASS; verdict A0/A1 PASS, A2 FAIL khi thêm mypy debt | `green_pipeline.json` |
| Repair server sau wiring | 10 PASS | `repair_server_after_wiring.json` |
| Reload/MCP/template | 4 PASS | `runner_contract.json` |
| Consumer/producer regression | 226 PASS | `consumer_regression.json` |
| Review RED → GREEN | 1 + 4 FAIL tái hiện; sau sửa 6 PASS / 19 deselected | `review_missing_red.json`, `review_baseline_red.json`, `review_green.json` |
| W7–8 + W9 lần đầu | 278 PASS / 1 FAIL, không exclusions | `full_w78_w9.json` |
| W9 + repair server sau review fix | 141 PASS, không exclusions | `final_w9_and_server_correct_path.json` |
| Toàn bộ W7–8 + W9 sau review/environment fix | **285 PASS**, 0 FAIL/ERROR/SKIP, không exclusions; command 419,63 giây | `final_full_w78_w9.json`, JUnit cùng tên |
| Ruff sau review fix | PASS | `final_lint.json` |

Các số focused PASS không cộng dồn thành số tests độc lập hoặc thay gate full.
Một command `final_w9_and_repair_server.json` dùng nhầm đường dẫn test, exit 4,
không chạy tests; giữ evidence và chạy command mới đúng path W7–8.

### 4.1. Lỗi environment đã xác định và được phép xử lý

Full suite lần đầu chỉ fail ở test subprocess không `PYTHONPATH`: file
`environments/vgar-week78-cuda/Lib/site-packages/vgar_week78_source.pth` trỏ
tới source path không tồn tại. Probe ngoài repo tái hiện `ModuleNotFoundError`.

Người dùng đã cho phép sửa **đúng source mapping đó** thành
`D:/Project/CAPSTONES/VGAR/src`. Không cài dependencies hoặc đổi Python/tool
versions. Lưu bytes gốc tại `environment_mapping_original.pth.txt`, hashes và
probe trước/sau tại `environment_mapping_before.json` / `environment_mapping_after.json`.
Probe sau sửa import đúng plugin VGAR, exit 0; test gốc PASS trong
`plugin_mapping_green.json`. Không sửa test/plugin/executor để né gate.

Full suite sau sửa đã có terminal PASS ở `final_full_w78_w9.json`. Toàn bộ tests
W7–8 chạy không exclusions; 141 W9/repair-server tests và 226 consumer tests là
các nhóm có chồng lặp, không cộng thành số tests độc lập. Preservation kiểm
HEAD và hashes trước/sau: các file baseline ngoài allowlist giữ nguyên, gồm
M1/W9-1/W9-2, fixtures, configs, prompts, registry và `Task Status.md`.

### 4.2. Xem artifacts thật của fake repairs

Đã giữ **11 terminal records** từ run full suite cuối tại
`terminal_fake_repairs/`, index `terminal_fake_repairs_index.json` trong evidence
root. Bao gồm A0/A1 PASS với raw static FAIL và A2 FAIL vì thêm debt, cùng các
lượt ERROR theo chủ đích của tests. Đây là fake-generation execution trên fixture
tin cậy, không phải LLM thật hoặc SWE-bench resolved. Các bytes record/bundle
được copy nguyên; paths trong record là lịch sử của workspace test, không được
tự dùng bản archive để resume một lease đã cleanup.

Index trỏ tới raw output, prompt, candidate/applied diff, baseline/post command
logs, session và bundle nếu run đã tạo chúng. Run lỗi sớm có thể không có bundle
hoặc generation; không điền hồi tố. Pending profile có cùng shape ở mục 2.2,
`bundle_hashes=null` cho tới context validation; terminal giữ actual hashes.
Điểm vào nghiệm thu tổng hợp: `closing_checks.json`, snapshots `before.json` và
`after.json`. Failures cũ vẫn tồn tại để đối chiếu, không bị thay bằng PASS.

Versions thực: Python 3.11.6, pytest 8.4.2, Pydantic 2.14.0, MCP 1.30.0,
mypy 1.18.2, Ruff 0.13.3, tokenizers 0.22.2. Không tuyên bố qualification mọi
requirements pins, model hoặc benchmark. Không có generation thật trong task.

[Review độc lập và hai findings đã xử lý](reviews/2026-10-23-m2-w9-4-provenance-review.md).

## 5. Tự kiểm thử

Chạy từ root VGAR bằng Python đã có dependencies và source mapping đúng.
Không cài lại nếu đã đủ. Các lệnh này không gọi LLM:

```powershell
$python = 'D:\Project\CAPSTONES\environments\vgar-week78-cuda\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
# Tests mới: input/profile, reload, MCP và policy behavior.
& $python -B -m pytest tests/m2/w910/test_context_arm.py tests/m2/w910/test_variant_provenance.py tests/m2/w910/test_runner_contract.py -q
$LASTEXITCODE
# Gate toàn bộ W7–8/W9, không loại tests tokenizer hoặc subprocess.
& $python -B -m pytest tests/m2/w78 tests/m2/w910 -q
$LASTEXITCODE
```

Exit 0 và JUnit không failures/errors là kết quả mong đợi, không giả định trước.
Native tests chỉ dùng bản copy fixture tin cậy; source gốc phải giữ hashes và
private workspace phải cleanup. Muốn giữ đầy đủ evidence như phiên này, dùng
`record.py` trong evidence với tên run mới; script từ chối overwrite logs cũ.

## 6. Bàn giao và điểm dừng

M3 cần truyền explicit arm/variant, giữ experiment xuyên ledger, đọc ba fields
`variant_id`, `arm`, `policy_hash` và đối chiếu canonical/bundle. Xem thêm
[runner interface](repair_runner_interface.md), [decision log](m2_w9_decisions.md).
Không suy ra runner M3 đã tích hợp hoặc M3 đã duyệt implementation mới.

Chỉ đóng kỹ thuật khi full W7–8/W9, repair server, consumer, Ruff, review và
preservation đạt. Pilot thật, admission W9-3 và gold M1-W9-4 ghi riêng, không
thêm thành gate của phần engine này. Không commit/push hoặc sửa `Task Status.md`.
**Kết thúc tại M2-W9-4, dừng chờ lệnh mới.**
