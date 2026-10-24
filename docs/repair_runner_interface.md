# M2-W9-0 — Giao diện runner ↔ repair session

Lập ngày 21/10/2026; xử lý review M3 ngày 22/10/2026. Baseline code: `525f9936a3c0abe5ea056c532c1f889ce84627a7`.

**Trạng thái: M2-W9-0 hoàn thành deliverable interface, đã xử lý phản hồi duyệt của M3.** Xem [receipt và bảng xử lý](reviews/2026-10-22-m2-w9-0-m3-review-resolution.md). Ngày 22/10 là ngày M2 ghi nhận/xử lý, không chứng minh review diễn ra đúng ngày 1. Environment contract M1/M2, full baseline và phần tích hợp W9 tiếp tục được ghi riêng; baseline cũ vẫn NOT_RUN, không chặn đóng riêng interface. Xem [trạng thái M2](status/m2.md) và [quyết định liên thành viên](m2_w9_decisions.md).

**Cập nhật W9-4 ngày 23/10/2026:** root `run_repair`/`RepairSession` và MCP đã nhận experiment opt-in; policy W9-1 được truyền thực vào verifier W9-2. Phần interface W9-0 và review M3 vẫn giữ lịch sử; trạng thái nghiệm thu mới xem [báo cáo W9-4](m2_w9_4_variant_provenance.md) và [status M2](status/m2.md). Không đổi public DTO/status hoặc admission.

Tài liệu này giúp M3 xây runner trên đúng engine hiện tại, đồng thời chỉ rõ extension cần có ở những task M2 tiếp theo. Nguồn yêu cầu là `New_task/VGAR_W9_W16_Deliverables.md` v2 ở workspace và kế hoạch M2 ngày 20/10/2026, giới hạn ở M2-W9-0. Tuần 1–8 giữ nguyên nghiệm thu của nhóm.

## 1. Ranh giới trách nhiệm

| Thành viên | Sở hữu | Đầu vào/đầu ra trao đổi |
|---|---|---|
| M1 | Source tại base commit, bundle graph/BM25, environment task, harness | Giao snapshot/bundle/profile có provenance; nhận yêu cầu adapter và report của M2 |
| M2 | Engine admission, prompt/generation binding, strict apply, verification, evidence, cleanup | Nhận task/profile; trả `RunHandle` và artifacts của một attempt |
| M3 | Runner, scheduling, attempt/resume, thống kê, MCP/agent integration | Chọn task/variant; gọi engine; giữ mọi kết cục và tổng hợp |

**M2-W9-0 chỉ soạn hợp đồng và kiểm tra baseline.** Không viết runner, variant policy, admission mới hoặc environment bridge trong task này. Review M3 đã được ghi nhận ở mục 7.1; không đánh dấu M1 hoặc các quyết định chung còn chờ là đã được duyệt.

## 2. API đang có trong code

### 2.1. Entry point một attempt

Nguồn: `src/vgar/repair/pipeline.py`.

```python
run_repair(
    task, policy, generator, executor, output_root,
    *, m1_counter, tokenizer,
    profile=None, temp_root=None, keep_workspace=False,
    supersedes_run_id=None, rerun_reason=None,
    feedback=None, deadline=None, experiment=None, admission=None,
)
```

Trả về `vgar.repair.evidence.RunHandle`, không phải dict hoặc exit code. Code hiện không ghi return annotation; kiểu trả về được xác định qua `session.finish`.

| Input | Ý nghĩa và giới hạn hiện tại |
|---|---|
| `task` | `RepairTask` từ `repair/contracts.py`: identity, source/bundle paths, issue, selectors, scope, allowed/protected paths và trusted flag |
| `policy` | `RepairPolicy`: prompt, budgets, timeouts, giới hạn patch; runtime mặc định `native_trusted_fixtures`; opt-in `docker_admitted` xem mục 6.1 |
| `generator` | Object có `.mode` và `.generate(prompt, profile, timeout_seconds)`; explicit fake hoặc real |
| `executor` | **Phải truyền `None` hiện tại.** `session.prepare` từ chối object executor bên ngoài |
| `output_root` | Thư mục kết quả; recorder tạo thư mục run duy nhất bên dưới |
| `m1_counter` | Counter cho validation handoff, có `counter_label`; phải khớp tokenizer manifest |
| `tokenizer` | Có `apply_chat_template`; dựng/count toàn prompt; không dùng character tokenizer để claim số token model |
| `profile` | `ModelProfile` khi cần; profile thật pin model/revision/runtime. Fake unit test có thể dùng `None` nếu cung cấp counter/tokenizer độc lập |
| `temp_root` | Root private workspaces; không được trùng/lồng với source; mặc định `.workspaces` trong repo |
| `keep_workspace` | Mặc định `False`; bật giữ workspace chỉ khi có chủ đích, không mô tả là đã dọn sạch |
| `supersedes_run_id`, `rerun_reason` | Provenance của attempt mới; không tự tạo retry hay kiểm duplicate |
| `feedback` | Optional data cho prompt; code kiểm task ID, keys và giới hạn feedback; không là quyền sửa trực tiếp output |
| `deadline` | Absolute deadline theo `time.monotonic()` trong process gọi; **không phải số giây timeout** và không lưu để tái dùng giữa máy/process |
| `experiment` | Opt-in internal profile: `variant_policy`, explicit `arm`, optional ba sidecar `expected_hashes`; không truyền thì giữ legacy. Xem mục 5 |

Các path từ `load_task`/`load_config` được resolve theo file cấu hình. `RepairTask` tự khai không đủ quyền chạy: `require_trusted_fixture` vẫn kiểm registry, paths và hash source. Nhánh SWE-bench opt-in được bổ sung ở W9-3, xem mục 6.1; native vẫn kiểm registry.

`RepairPolicy` mặc định hiện có input 6.000, output 1.536, reserve 256 tokens; generation 900s, command 120s, global 1.800s; max diff 256 KiB, max files 5, max changed lines 500. Đây là cấu hình prototype hiện tại, chưa phải protocol W9 đã được nhóm phê duyệt.

### 2.2. Generator contract hiện hữu

`generate` nhận `PromptArtifact` và trả dict. Ví dụ `vgar.models.generator.FakeGenerator` trả:

```python
{
    "status": "PASS", "mode": "fake", "raw_text": "<unified diff>",
    "finish_reason": "fixture", "truncated": False,
    "input_tokens": prompt.input_tokens, "output_tokens": None,
    "token_measurement": "unit-test-only", "duration_ms": 0,
}
```

Đây là mô tả shape, không phải record của lượt chạy mới. `record_generation` cần tối thiểu `status`, `raw_text`, `truncated`; các trường khác giữ evidence backend. `status != PASS` hoặc output truncated không đi tiếp như output hợp lệ. Backend real lỗi không tự fallback thành fake.

Runner gọi engine một lần tương ứng tối đa một generation; nếu prepare fail thì không generation. `ScriptedPatchGenerator` trong `agents/fakes.py` có thể cung cấp chuỗi diff để M3 test nhiều attempts, nhưng mỗi call `run_repair` vẫn là attempt riêng.

### 2.3. Ví dụ gọi bằng fixture hiện có

**Ví dụ dùng API đang tồn tại, chưa thực thi ở phiên W9-0 này.** Cần dependencies/tokenizer hợp lệ và source fixture nguyên bản. Chạy từ root `VGAR` trong Python đã import được package `vgar`.

```python
from pathlib import Path
from vgar.repair.config import load_config, load_task
from vgar.repair.pipeline import build_generation, run_repair

task = load_task(Path("examples/m2/tasks/single_file_login.json"))
policy, profile = load_config(Path("configs/m2/demo.json"))
output_root = Path("results/m2/w9/manual-fixture")
generator, tokenizer, counter = build_generation(
    "fake", task, policy, profile, output_root
)
handle = run_repair(
    task, policy, generator, None, output_root,
    m1_counter=counter, tokenizer=tokenizer,
    profile=None, temp_root=Path(".workspaces/m2-w9-fixture"),
)
print(handle.path)
print(handle.record["status"], handle.record["complete"])
```

`build_generation("fake", ...)` vẫn cần profile/tokenizer manifest hợp lệ để dựng tokenizer/counter; không bỏ profile ở bước này. Riêng `run_repair(..., profile=None)` ở fake mode thống nhất với CLI; đây không phải real model profile được nghiệm thu. Ví dụ chưa được chạy lại trong lần chỉnh tài liệu này.

`build_generation("fake", ...)` dùng patch test tại `tests/fixtures/m2/reference_patches/<task_id>.diff`, không gọi LLM. Đây chỉ là fixture kiểm plumbing; tuyệt đối không dùng reference/gold patch của SWE-bench làm generator thật hoặc tính fake PASS thành model repair PASS.

## 3. Vòng đời session hiện tại

Nguồn: `src/vgar/repair/session.py`. Đường chạy chuẩn:

```text
start_session → prepare → generator.generate → record_generation
              → apply_candidate → run_selected_tests → finish
```

| Bước | Phase thành công | Tác dụng |
|---|---|---|
| `start_session(...)` | `started` | Tạo run/session, source fingerprint engine, deadline, stages NOT_RUN |
| `prepare(session, counter, tokenizer, executor=None)` | `prepared` | Kiểm trusted fixture, validate M1, tạo worktree, baseline, prompt |
| `record_generation(..., started_utc, duration_ms, error=None)` | `generated` | Ghi raw generation hoặc exception; kiểm truncated/deadline |
| `apply_candidate(session, raw)` | `applied` | Strict parse, exact binding/apply/attestation, lưu diff |
| `run_selected_tests(session, counter)` | `tested` | Reload handoff, chọn test scope, collect và chạy post tests |
| `finish(session, on_record=None)` | `finished` | Hoàn tất static verification, integrity, bundle, cleanup, terminal record |

`run_repair` điều phối những bước này. `_step` có thể trả `None` và lưu `outcome` khi lỗi; runner không được hiểu `None` là PASS. Nếu gọi từng bước trực tiếp, sau lỗi vẫn phải đi finalization hợp lệ. `finish` lần hai trên session finished sẽ raise; không phải thao tác idempotent.

`RepairSession.load(run_dir)` hỗ trợ nạp session giữa các process, đã có test W78 cho chuỗi bước. Nhưng **load không phải thao tác chỉ đọc**: nó gọi `load_run`, constructor `RunHandle` ghi lại record. Muốn quan sát tiến độ thì chỉ đọc JSON, không gọi load trên run đang hoạt động.

Code có phase và outcome nhưng không phải transaction scheduler có lock/reservation toàn runner. Không gọi hai step writers đồng thời trên cùng run; không giả định crash ở giữa apply sẽ tự resume an toàn.

### 3.1. Deadline và cleanup

- Deadline ban đầu là min của policy global timeout và deadline caller, nếu có; session lưu mốc `deadline_utc` để dựng phần còn lại khi reload.
- Mỗi command bị giới hạn bởi command timeout và global còn lại qua `DeadlineExecutor`; timestamp UTC và duration monotonic được ghi.
- Engine truyền timeout cho generator rồi kiểm deadline sau call. **Không thể bảo đảm hard timeout với generator tùy ý chỉ vì có tham số này.** Runner real phải dùng backend được qualification về timeout/process ownership; in-process backend không được mặc nhiên coi tương đương worker có deadline.
- `finish` kiểm source và cleanup trước công bố terminal kết quả. Cleanup lỗi có thể đổi PASS dự kiến thành ERROR.
- Process bị kill ngoài kiểm soát có thể để record pending/workspace còn tồn tại. Quy trình recovery của M3 cần xác nhận process ownership trước khi cleanup/rerun; không kill PID không xác minh được.
- Exception trước khi có `RunHandle`, filesystem lỗi hoặc publish lỗi nghiêm trọng có thể propagate. Runner cần ghi launch/infrastructure failure của chính mình; không giả định mọi exception đều có bundle.

### 3.2. Ctrl+C / KeyboardInterrupt — hành vi hiện tại, không đổi code

`observe()` bắt `BaseException`, ghi stage lỗi rồi **ném lại**. Tầng `_step()` bên ngoài cũng bắt `BaseException`, có thể chuyển `KeyboardInterrupt` thành outcome ERROR và lưu `error_detail` thay vì để exception truyền ra runner. Lời gọi generator trong `run_repair` cũng bắt `BaseException`, chuyển exception qua `record_generation` rồi `_step`. Vì vậy, Ctrl+C không bảo đảm luôn ngắt bằng một exception mà caller nhìn thấy.

Runner nên đọc `error_detail.type == "KeyboardInterrupt"` và stage/nested error tương ứng khi có; không chỉ trông chờ `except KeyboardInterrupt` bên ngoài `run_repair`. Reason phụ thuộc callsite: thường INTERNAL_ERROR, nhưng stage workspace có thể WORKTREE_ERROR; lỗi finalization có thể thay reason. Khi finalization hoàn tất, record có thể `complete=true` dù outcome ERROR; không coi đó là một attempt thành công.

M3 báo runner đã bắt SIGINT và kiểm `error_detail.type`. Đây là thông tin do M3 bàn giao, chưa được M2 kiểm chứng implementation runner ở checkout này. Theo lựa chọn được M3 cho phép, W9-0 chỉ bổ sung mô tả hiện trạng; **không sửa engine để ném lại KeyboardInterrupt** và không tuyên bố mọi vị trí Ctrl+C đều được recovery an toàn.

## 4. Kết quả và cách M3 đọc

`RunHandle.directory` là thư mục run; `.path` là `run_record.json`; `.record` là dữ liệu trong bộ nhớ. Sau return bình thường từ `run_repair`, dùng canonical file trên đĩa để kiểm terminal evidence.

| Artifact/field hiện có | Cách sử dụng |
|---|---|
| `run_record.json` | `run_id`, `task_id`, `kind`, `mode`, `status`, `complete`, start/end/duration, task/policy/model, stages, reason, artifact refs |
| `session.json` | Phase/outcome/deadline/lease; state để engine tiếp tục step, không là bảng tổng hợp benchmark |
| `prompt.txt` | Chỉ có sau prepare thành công; prompt hashes/token count ở stage prompt |
| `raw_model_output.txt` | Raw output đã ghi; malformed output vẫn có thể được lưu ở đây |
| `candidate.diff` | Chỉ xuất hiện sau parse thành công; không phải mọi FAIL đều có file này |
| `transport.diff`, `applied.diff` | Transport/apply evidence khi apply thành công; dùng applied diff để downstream grading |
| `evidence_bundle.json` | Public DTO, recommendation, verification, diff, source hashes, metadata canonical hash |
| `REPORT.md` | Tóm tắt recorder; không thay canonical JSON |

Các artifacts là có điều kiện theo stage; caller đọc `artifacts` thay vì đoán mọi path đều tồn tại. Admission/prepare fail trước workspace có thể không có EvidenceBundle. Record có command logs nằm trong stage; output bị truncate phải được giữ cờ và không gọi là đầy đủ.

`complete=true` ở run nghĩa recorder đã kết thúc, **không có nghĩa mọi check đã PASS**. Có thể terminal ERROR với nhiều stage NOT_RUN. Ngược lại `complete=false`/thiếu record chưa đủ để kết luận process chết.

### 4.1. Status và mã lỗi hiện tại

| Vị trí/tình huống | Kết quả code hiện tại | M3 nên đọc thêm |
|---|---|---|
| Verification thành công | PASS → ACCEPT | Source integrity, artifacts và cleanup |
| Parser `ValueError` ở parse stage | FAIL / `PATCH_PARSE_ERROR` → REVISE | Raw output, parser diagnostics |
| Apply thất bại | Theo `PatchApplyResult`, thường `PATCH_APPLY_FAILED` | Apply commands, exact binding |
| Required/regression tests thất bại | FAIL / `TEST_FAILED` | Baseline/post outcomes, missing cases |
| Type/lint fail | FAIL / `TYPECHECK_FAILED` hoặc `LINT_FAILED` | Canonical static command |
| Baseline không qualify | ERROR / `VERIFICATION_INCOMPLETE` | Baseline reason như `BASELINE_NOT_QUALIFIED` |
| Trusted fixture/source hoặc context fail trong prepare | Thường ERROR / `INTERNAL_ERROR` | `error_detail.stage`, exception, traceback; chưa có taxonomy admission riêng |
| Workspace exception | ERROR / `WORKTREE_ERROR` | Source/workspace logs |
| Deadline/truncated/incomplete | ERROR; reason tùy callsite | Deadline, timed_out, truncated, nested reason; **không có terminal status TIMEOUT riêng** |
| Test command timeout | Canonical verification thường ERROR / VERIFICATION_INCOMPLETE; DTO `verification.tests.reason.code` có thể TEST_TIMEOUT | Đọc command `timed_out` ở baseline/verification và collection khi có; xem mục 4.1.1 |
| Finalization lỗi | ERROR / `FINALIZATION_ERROR` ở canonical | `finalization_errors`; mã này không thuộc public `FailureCode` hiện tại |

Public `FailureReason` có danh sách enum hạn chế trong `contracts/repair.py`; canonical reason có thể rộng hơn. Không ép mọi canonical code vào DTO enum. Taxonomy thống nhất mọi kết cục là deliverable W10, chưa implement trong W9-0.

### 4.1.1. Đọc timeout: canonical record khác DTO của bundle

Ở luồng test hiện tại, `assess_transition` trả ERROR/VERIFICATION_INCOMPLETE khi thực thi không đầy đủ. `_project_bundle` có thể chuyển test command `timed_out=true` thành `TEST_TIMEOUT` trong DTO. Vì vậy không tìm riêng `record.reason == "TEST_TIMEOUT"` để kết luận có/không có timeout; cũng không coi mọi loại timeout đều có cùng reason.

Các vị trí cần đọc trong `run_record.json`, **chỉ khi stage/artifact tồn tại**:

- `stages.baseline.tests.command.timed_out` cho baseline tests.
- `stages.verification.tests.command.timed_out` cho post tests đã được ghi.
- `stages.baseline.collection.command` và `stages.verification.collection.command` cho collection; related collection nếu có được đọc tương tự.
- `stages.<stage>.error_type`, `error_detail.type`, traceback/nested reason cho deadline/exception; có thể chưa tạo được test command.

Xem cả `complete`, `output_truncated`, exit code và reason; không đổi missing field thành `timed_out=false`. Global deadline, generator timeout hoặc cleanup error phải phân loại theo stage thực tế, không suy từ một cờ test. Bundle có thể không được tạo nên không dùng riêng DTO để thống kê mọi lượt ERROR.

### 4.2. Quy tắc runner/resume đề xuất cho M3

1. M3 ghi reservation/launch record trước gọi engine; khóa logical task×variant×experiment config để tránh hai writers.
2. Run terminal được giữ nguyên, kể cả FAIL/ERROR; không tự chạy lại vì kết quả không đẹp.
3. Pending phải được phân loại bằng cơ chế ownership/exclusivity đã thống nhất; khi chưa xác minh được quyền recovery thì không launch trùng. Không bắt buộc implementation phải theo dõi PID nếu có cơ chế khóa đáp ứng các điều kiện bên dưới.
4. Nếu process đã xác nhận terminal nhưng run chưa finalize: ghi interrupted attempt và cleanup/recovery có owner; retry là attempt mới với parent/reason.
5. Config/model/prompt/bundle/env thay đổi thì là experiment identity khác, không dùng record cũ làm kết quả mới.
6. Không truyền monotonic timestamp giữa process; runner điều phối thời gian còn lại và engine lưu deadline tuyệt đối hiện có.

**Phản hồi (c) của M3:** runner dùng `runner.lock` độc quyền theo experiment, không theo dõi PID. M3 báo các reservation còn treo lúc runner mới khởi động được xử lý là interrupted. M2 ghi nhận phương án này, không yêu cầu đổi sang PID. Điều kiện an toàn: khóa bao phủ vòng đời điều phối cần bảo vệ, mọi runner của cùng experiment tuân thủ lock, và recovery không xung đột worker cũ còn có thể ghi run. Chỉ lấy được lock không tự chứng minh mọi child process đã dừng.

Implementation runner/lock chưa được M2 kiểm chứng trong checkout này; đây không phải claim đã có runner W9 ở local hoặc đã test resume. Có thể đọc record terminal bằng JSON read-only; không cần `RepairSession.load` chỉ để aggregate.

## 5. Interface W9 opt-in — đã implement, nghiệm thu theo W9-4

`run_repair` và `start_session` đã thêm keyword `experiment=None`; positional
arguments và kiểu trả `RunHandle` không đổi. MCP `get_task_context` nhận JSON
experiment ở cuối arguments. Các tools sau reload cùng session, không cần caller
gửi lại profile. Không truyền experiment thì metadata/hành vi legacy giữ nguyên.

Input tối thiểu: `{"variant_policy": <nội dung config A0/A1/A2>, "arm": "bm25"}`.
Arm chỉ nhận `bm25` hoặc `graph`; config arm null được bind vào bản policy hiệu
lực, hash tính lại. Caller không tự khai hash và không suy arm từ variant ID.
Optional `expected_hashes` phải có đúng ba sidecar hashes hợp lệ. Arm là nhãn
caller từ handoff/index, không phải bằng chứng consumer nhận diện thuật toán.

Canonical record/session có `experiment_required=true` và cùng snapshot tại
`experiment`: variant_id, arm, policy_hash, variant_policy, expected_hashes,
bundle_hashes. Bundle lưu cùng snapshot ở `metadata.experiment` trước canonical
hash cuối. Reload kiểm hai phía trước write; mất profile hoặc baseline binding
thiếu/sai bị từ chối. Đây là consistency, không phải chữ ký xác thực.

Phạm vi các nhóm dữ liệu (không gộp admission/environment vào profile vừa implement):

| Nhóm | Dữ liệu | Task sẽ làm |
|---|---|---|
| Variant | `variant_id`, `arm`, required/recorded checks, `policy_hash` | W9-1/W9-4 đã implement, xem gate mới |
| Admission | Approved manifest, base/source hashes, quyền sửa/protected paths | W9-3 |
| Environment | Serializable backend/profile/ref/hash và output mapping | W9-3, M1 phối hợp |
| Provenance | Bundle hashes trong experiment; tokenizer/model/config/template giữ evidence hiện có; oracle policy còn chờ protocol | W9-4 không tự chốt oracle/admission |

Profile phải persist qua session reload; khi không truyền thì giữ W78. Không serialize callable executor. Ưu tiên dùng EvidenceBundle.metadata cho provenance, public DTO nếu cần đổi phải review cả ba thành viên.

### 5.1. Điều kiện (d) M3 đã nêu và cách xử lý ở W9-4

- W9-0 chỉ ghi ví dụ fields do M3 đề xuất, chưa implement. Plan W9-4 người dùng
  duyệt nay chọn chính tên `record["experiment"]["variant_id"]`, `["arm"]`,
  `["policy_hash"]` và thêm định nghĩa policy/bundle hashes để kiểm lại.
- Direct và MCP dùng cùng validator/save-load; tests mới kiểm reload giữa từng
  bước, terminal ERROR và canonical/bundle binding. Không ghi runner M3 đã test.
- `tests/m2/w78/test_w78_repair_server.py` đã được chạy sau wiring; kết quả
  sau review fix, full W7–8/W9 và blocker môi trường được ghi tại báo cáo W9-4.

Engine-side interface đã implement; việc nghiệm thu đủ gates và interoperability
runner M3 thật là hai trạng thái riêng. Không tự ghi M3 duyệt implementation mới.

Mapping đề xuất vẫn là A0=BM25/tests; A1=graph/tests; A2=graph/tests+static delta,
nhưng không hardcode trong engine hoặc tự ghi nhóm đã duyệt. Required sets theo
policy hiện có. A0/A1 có thể ACCEPT dù raw static FAIL khi optional; A2 áp delta
thật. Không đổi raw FAIL thành PASS, không coi fixtures là kết quả pilot.

Template hash giữa arm phải giống theo cấu hình thí nghiệm; rendered prompt hash có thể khác vì context khác. Không so rendered hash bằng nhau để bác bỏ hai arm hợp lệ.

## 6. Environment contract cần M1 bàn giao

Bốn field tối thiểu plan chính: `task_id`, `base_commit`, `env_ref`, `test_command`. Để bridge hoạt động, M1/M2 cần thống nhất các dữ liệu sau trước task W9-3 tích hợp thật:

| Nội dung | Yêu cầu bàn giao |
|---|---|
| Identity | Repo/task/base commit, immutable environment identity và attestation; không chỉ mutable tag |
| Source | Snapshot đúng base, inventory hashes; tách source base với test overlay nếu có |
| Runtime | Python repo, pytest/tool versions, backend Docker/WSL hoặc native đã được duyệt |
| Workspace | Bind private patched bytes vào environment; cwd/path mapping; chứng minh đúng snapshot sau apply |
| Command | argv/approved template, selectors, fallback scope; không input shell tự do từ model |
| Report | Exit code, raw streams, complete/truncated/timed_out, node outcomes, collection/JUnit, path mapping và hash |
| Static | Tool/config/scope/version pin; có thể khác Python host; không âm thầm cài tools sau pin |
| Lifecycle | Run/process/container owner, timeout, terminate, cleanup và logs |
| Oracle | F2P/P2P/test_patch visibility, hash overlay và thời điểm cài; gold patch không là input repair |

Hiện `_invoke` của `repair/test_runner.py` dùng `sys.executable` và plugin `vgar.repair.pytest_plugin`. Vì vậy “M1 tạo xong image” chưa chứng minh VGAR chạy được tests trong image. Cần probe import/plugin hoặc report adapter tương thích, không mặc định cài toàn package VGAR và Torch vào interpreter của target repo.

Git apply và source attestation vẫn thuộc private host lease trong đề xuất; tests/static đi task environment. Không biến mọi lệnh thành Docker command bằng thay chuỗi đường dẫn chung. Inventory hiện có giới hạn file/repo, từ chối link và `.gitattributes`; phải kiểm pilot compatibility trước model, không nới guard trong W9-0.

## 6.1. Bổ sung M2-W9-3 — Docker admission ngày 24/10/2026

Đường direct/session nhận keyword `admission=admit_task(...)` với expected
manifest/profile/ba sidecar hashes độc lập, exact Git base/raw-byte inventory,
production source roots và protected issue-test overlay. Yêu cầu runtime
`docker_admitted` và experiment W9 rõ ràng; `executor` vẫn phải là `None`.
Gate W9-3 đã hoàn thành kỹ thuật: Xarray scripted run_repair PASS, hash sai
bị chặn, final317PASS/audit14operations/cleanup PASS. Không suy model/M3 hoặc
đủ năm tasks runnable. Chi tiết API, source/config/target binding, deadlines và
giới hạn: [báo cáo admission](m2_w9_3_admission.md).

Adapter giữ Git/patch trong host private lease; mỗi target command tạo container
mới, digest/daemon/image pinned, không network hoặc mount. Standalone reporter
chuyển node outcomes/JUnit về host; pytest/static/syntax dùng Python target.
Cleanup có ownership check và ngăn PASS nếu lỗi. Persisted state/record/bundle
có cùng admission snapshot; thiếu hoặc đổi binding bị từ chối trước resume write.
MCP start chưa thêm input admission; không suy runner M3 đã tích hợp.

Các mô tả chưa có bridge và `.gitattributes` ở mục 6 là baseline lịch sử W9-0.
Nhánh admitted nay tắt Git attribute transforms trên private seed rồi attest
bytes; native fixture guard không đổi. Raw module-static errors vẫn được ghi;
A2 chưa được qualification tools trong image Xarray. Kết quả nghiệm thu cuối ở
báo cáo W9-3 và status M2, không sửa kết quả W9-0/W9-4 đã ghi.
## 7. Evidence W9-0 và checklist review

Evidence cục bộ: `results/m2/w9/m2-w9-0/20261021/` (ignored bởi Git).

- `preflight_command.json`: argv/cwd/interpreter, stdout/stderr, exit code, UTC start/end, duration.
- `preflight.json`: Python/dependency versions, tokenizer paths/hashes và `baseline_ready=false`.
- `source_before.json`: hash từng tracked file và file untracked người dùng trước thay đổi tài liệu.
- `baseline_status.json`: baseline tests chưa chạy, command dự kiến, lý do chặn; không có test PASS mới.
- `delivery_check.json`: kiểm tra tĩnh tài liệu, source preservation; không thay thế pytest baseline.

### 7.1. Kết quả xử lý review ghi nhận ngày 22/10/2026

[Phản hồi M3 nguyên văn](reviews/review_M2-W9-0_M3_original.md) được lưu trong repo; [receipt/bảng xử lý](reviews/2026-10-22-m2-w9-0-m3-review-resolution.md) ghi nguồn, hash, mức phê duyệt và phần còn mở. Không bắt buộc bổ sung chữ ký/hash tài liệu do M3 ký để thay đổi tiêu chí plan; không suy ra ngày review hoặc đúng hạn ngày 1 từ ngày ghi nhận của M2.

- [x] M3 duyệt entrypoint/output và hướng interface; yêu cầu chỉnh tài liệu (a)/(b)/fake đã xử lý; ghi nhận lock ở (c).
- [x] Điều kiện experiment/save-load/MCP regression ở (d) đã ghi follow-up cho W9-4, không tự đóng phần implementation.
- [ ] M1/M2 thống nhất environment/report/source binding.
- [ ] Nhóm chốt các quyết định trong `m2_w9_decisions.md` trước phần tích hợp tương ứng.
- [ ] Baseline W78 và consumer được chạy trên môi trường đạt điều kiện, evidence được bổ sung.

Hai mục environment/baseline và các quyết định trước integration vẫn ghi đúng trạng thái; không phải gate bổ sung cho deliverable tài liệu W9-0. Không có claim baseline/model/runner/MCP PASS mới trong đợt này.

**M2-W9-0 hoàn thành deliverable interface sau xử lý review M3. Chờ người dùng ra lệnh; chưa được phép bắt đầu task tiếp theo.**
