# 01 — Bàn giao M2 tuần 7–8 cho M1 và M3

Ngày chốt: 15/10/2026. Project: `D:\Project\CAPSTONES\M2_week_7_8`.
Đọc tài liệu này trước khi tích hợp; không lấy trạng thái BLOCKED trong các báo
cáo lịch sử làm kết quả cuối cùng. Code/evidence hiện có được giữ nguyên.

## 1. Kết luận bàn giao

M2 đã có pipeline standalone **issue → context M1 → prompt → một generation →
unified diff → private worktree → verification → EvidenceBundle**. Ba case A/B/C
đã chạy mới bằng cùng template V11, core runtime r002, cùng model/policy, **không
feedback**, và **3/3 PASS**. Đây là fixtures development, không SWE-bench, không
chứng nhận độc lập của đồng đội và không phải MCP/LangChain end-to-end.

| Hạng mục M2 tuần 7–8 | Kết quả / vị trí |
|---|---|
| Repair prompt cố định | `prompts/repair_v11.txt`; `prompt.py`, `context_presentation.py` |
| Backend cố định | HF Qwen3-4B; `generator_hf.py`, `hf_backend.py`, `hf_worker.py` |
| Validate/parse diff | `src/vgar_m2_w78/patch.py`; strict paths/counts/exact binding |
| Apply temporary worktree | `workspace.py` + `patch.py`; all-file preflight và byte attestation |
| Relevant-test selection | `test_selection.py`; M1 diagnostics + required inputs + approved full-fixture fallback |
| pytest/type/lint | `test_runner.py`, `pytest_plugin.py`, `verification.py`, `checks.py` |
| Evidence bundle | `pipeline.py`, `evidence.py`; public DTO từ VGAR, canonical chi tiết hơn |

Tên module viết ngắn trong bảng thuộc `src/vgar_m2_w78/`. Không cần viết lại bảy
phần này. Chưa có adapter cho arbitrary executor/repository ngoài ba fixtures.

## 2. Kết quả cụ thể và vị trí log

Root bằng chứng final: `results/final_acceptance/2026-10-15-v11-r002/`.

| Case | Task / file sửa | Baseline → post | Pipeline / generation | Input / output tokens |
|---|---|---|---|---|
| A | `single_file_login`, `auth.py` | 1 required FAIL + 1 regression PASS → 2 PASS | 68,828s / 53,250s | 1.299 / 43 |
| B | `multi_file_invoice`, **`invoice.py` và `pricing.py`** | 2 required FAIL + 1 regression PASS → 3 PASS | 157,282s / 142,406s | 1.769 / 157 |
| C | `missing_links`, `formatter.py` | 1 required FAIL + 1 regression PASS → 2 PASS | 64,031s / 51,250s | 1.169 / 43 |

Tổng pipeline **290,141s**, generation **246,906s**; **4.237 input / 243 output**
tokens. Không cộng thời gian đọc log/soạn tài liệu vào generation latency. Không
gọi API trả phí; compute/điện local chưa đo giá tiền, không gọi là miễn phí.

| Case | Canonical tương đối với root final |
|---|---|
| A | `A/20261015T072711985584Z-dc47a96417ee/run_record.json` |
| B | `B/20261015T072938917449Z-a0075c35e2ee/run_record.json` |
| C | `C/20261015T073254806383Z-68a9a593f8d6/run_record.json` |
| Combined audit | `audits/20261015T073438247626Z-8ce2a58ef084/run_record.json` — PASS, scope `3/3 final acceptance` |

Mỗi canonical folder có `prompt.txt`, `raw_model_output.txt`, `candidate.diff`,
`applied.diff`, `evidence_bundle.json`, `REPORT.md`. Worker request/response/
`generation_diagnostics.json`/`command.json` ở `<case>/model-workers/<worker-id>/`.
`run_manifest.json` trỏ đúng từng canonical; không cần đoán latest folder.

Raw=candidate bytes; model tự sinh diff, host không sửa hunk/counts. Applied diff
là Git export của thay đổi **đã áp dụng**, không nhất thiết giống cách biểu diễn
raw (Git có thể bổ sung context). Tất cả source gốc giữ nguyên. Fixture vẫn có
lỗi là đúng thiết kế; bản sửa ở private worktree và artifact `applied.diff`.

Core r002 đã đạt **234 tests PASS trong 124,45s**; qualification:
`results/b-repair-preflight/20261015-evidence-driven/full-r002-v11/20261015T070616016658Z-306d4603f3b7/run_record.json`.
Final không thay core; fingerprints và 262 frozen input/core/profile/audit files
được kiểm trong combined audit. PASS không chứng minh mọi semantics ngoài tests.

Để tránh hiểu sai latency: cột generation ở trên là **stage generation của
pipeline**, gồm worker/load/IO. Bên trong HF còn có timers riêng:

| Case | model_load_ms | generation_ms đo quanh model.generate | cuda_peak_allocated_bytes |
|---|---:|---:|---:|
| A | 8515 | 35703 | 5238012928 |
| B | 8859 | 125906 | 5777223680 |
| C | 8844 | 34859 | 5112930304 |

Peak CUDA allocated không phải toàn bộ VRAM process/OS; không cộng nhầm load/gen
timers lồng nhau với outer stage rồi công bố duration lớn hơn thực tế.

## 3. Profile phải giữ khi tái lập

- `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`.
- Greedy, FP16, `device_map=auto`: có GPU/CPU offload, không chạy toàn bộ trên GPU.
- Input 6.000 / output 1.536 / reserve 256; generation 900s / command 120s /
  global pipeline 1.800s; một generation/case, không auto-retry.
- Template V11 SHA256 `ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8`.
- Final profile: `results/final_acceptance/2026-10-15-v11-r002/final_profile.json`.
  `config/demo.json` vẫn V2 vì giữ historical hashes: bare CLI default KHÔNG là V11.
- Core interpreter: `M2_week_7_8/.venv/Scripts/python.exe`; HF interpreter hiện tại:
  `D:\Project\CAPSTONES\vgar_mcp_mvp\.venv\Scripts\python.exe`. Đây là dùng dependencies,
  không chạy source hệ thống cũ. Có thể provision một HF venv riêng nhưng phải
  cấu hình và nghiệm thu paths/environment tương ứng; không giả là byte-identical record cũ.
- Hai môi trường có tokenizers core0.22.1 / HF0.22.2 khác nhau; xem `requirement.txt`.
- Cần Git/PowerShell/Python/NVIDIA driver và local model/tokenizer assets; không
  tự tải weights hoặc cài packages trong runner. Pin cache metadata không phải
  independent full weight-byte attestation.

## 4. M2 đã kết hợp với M1 như thế nào?

### 4.1. Nguồn M1 đã tiêu thụ, không tự xây lại graph

VGAR dependency ở sibling `../VGAR`, pin `b8e2461635b81d1ae790445efea5c9757d91700a`.
`config/source_pin.json` khóa HEAD và 12 boundary files. `bootstrap.verify_reference`
kiểm hashes và import origin trước khi dùng DTO/consumer/token counter. Dirty
paths ngoài boundary được ghi, không tự revert; M2 không sửa ranking/SCIP/Jedi.

`examples/inputs_receipt.json` xác nhận input preparation PASS ngày14/10, source
M1 run `20261014T072245Z-a8015356523c45cfa264244c07d252b0`. Ba case đến từ fixtures
handoff M1, không phải tasks SWE-bench hay tasks do model tự nghĩ ra. Entry point
chuẩn bị: `scripts/prepare_inputs.py`; không chạy lại khi snapshots/hashes còn đúng.

### 4.2. Các input phải bàn giao cùng nhau

| File | Nội dung / tác dụng |
|---|---|
| `examples/tasks/<case>.json` | task_id, issue, source/bundle paths, repo_key, revision, graph_version, required/fallback selectors, allowlist/protected paths |
| `examples/snapshots/<case>/` | Source gốc + tests/config đã khóa; oracle của baseline, không phải code đã fix |
| `examples/handoffs/<case>/context.json` | ContextPayload: graph_version, anchor_ids; items với node_id/path/symbol/range/snippet/relevance/confidence/tokens và metadata |
| `.../context_manifest.json` | Identity/source inventory/context provenance để bind bundle với đúng source/revision |
| `.../test_links.json` | Mapping path/node → selectors, link details/confidence/traversal/fallback, failing selectors/scope |
| `.../repair-context.txt` | Producer text để tham khảo; M2 render lại từ DTO đã validate, không tin text này thay source validation |
| `../VGAR/artifacts/m2/w5-w6/tokenizer_manifest.json` + assets | Counter M1 đếm snippets; không thay cho đếm toàn chat prompt của M2 |

### 4.3. Flow thật phía M2

1. `context_adapter.load_handoff` gọi M1 `receive_context_handoff` với
   `HandoffTarget(task_id,repo_key,repository_revision,graph_version)` và counter.
   Từ chối mismatched snapshot/ranges/tokens/provenance; lưu SHA các sidecars.
2. `prompt.build_repair_prompt` dùng context đã validate. M2 chỉ bổ sung phần
   trình bày permission/read-only/absolute source line counts cho V11, không sửa
   snippets/order/IDs/payload M1 hoặc thêm gold patch vào prompt.
3. Sau exact apply, lấy **actual changed files**, gọi M1 `diagnose_changed_paths`
   trên snapshot gốc/hints. Không lấy file list do LLM tự khai làm sự thật.
4. M2 giữ required failing selectors; với fixtures nhỏ, `selected` dùng full
   approved scope `tests` để chạy regression. Graph selectors được collect riêng.
5. Hints thiếu/limited chỉ quyết định fallback; collection và tests chạy thật
   trên worktree mới quyết định outcomes. C có `fallback_required=true`, scope
   `tests`, reason `unlinked`, nhưng vẫn qua collection/post tests thực tế.

## 5. Interface để M3 tích hợp

Entry point hiện tại:

```python
run_repair(task, policy, generator, executor, output_root,
           m1_counter=..., tokenizer=..., profile=...)
```

Nằm `src/vgar_m2_w78/pipeline.py`. Input nội bộ là `RepairTask`, `RepairPolicy`,
`ModelProfile` ở `contracts.py`; trả `RunHandle` với `.path`, `.directory`, `.record`.
Đối với Native hiện tại, truyền `executor=None`: pipeline tự sở hữu private lease
và executor. External executor không được nhận trước khi có approved adapter.
Đây là Python service boundary, **chưa phải public MCP schema**.

| Khối code đã có | M3 cần bọc/điều phối thế nào |
|---|---|
| `parse_unified_diff(raw, PatchPolicy)` | Validate input/raw/path policy trước apply, không tự recount |
| `create_workspace(...)` → WorkspaceLease | Giữ lease/ownership/run state trong host, không cho LLM tự chọn root |
| `apply_patch(lease, parsed, executor)` | Chỉ dùng lease đang active; all-file check/Git apply/attestation |
| `capture_baseline`, `select_relevant_tests`, `verify_patch` | Giữ baseline và required IDs cùng run; không gọi mỗi tool trên session/workspace khác rồi mất state |
| `RunHandle` + EvidenceBundle projection | Trả public verification + artifact/run refs; canonical giữ command/raw/diagnostics đầy đủ |

M3 cần quyết định bọc toàn pipeline hay tách ba tools. Nếu tách `apply_patch`,
`run_relevant_tests`, `verify_patch`, phải giữ cùng lease/baseline/run state. Không
gọi lại `run_repair` từ đầu cho mỗi tool rồi coi như cùng repair. Không truyền shell
commands/interpreter/source roots tự do từ model; public schema/transport thuộc M3.

`EvidenceBundle.verification.api_check` và `structural_check` hiện NOT_RUN: không
tự đổi thành PASS. Audit final có AST signature comparison cơ bản cho ba fixtures,
không tương đương một verifier API/architecture tổng quát ở tuần sau.

## 6. Phần việc còn lại và owner

| Owner | Việc cần làm | Vì sao / đầu ra nghiệm thu |
|---|---|---|
| M1 | Review mapping/provenance của ba bundles và consumer call boundary nếu chưa ký | Xác nhận source/task/graph/token identity; M2 có automated evidence nhưng không ký thay M1 |
| M1 | Khi đổi graph/ranking/source, export bundles mới đồng bộ manifest/test links | Không tái dùng context cũ trên source mới; tạo revision/evidence mới, không sửa hashes cũ |
| M1 | Hỗ trợ lỗi hints/ranges/source/token mismatches khi tích hợp | Phân biệt producer bug với M2 render/apply bug; không cần sửa M1 nếu dữ liệu cũ đã hợp lệ |
| M3 | Bọc MCP tools và nối LangChain retrieve → generate → patch → verify | Đưa standalone vào integrated system; lưu tool names/args/results/durations/run IDs |
| M3 | Quản lý lease/session/baseline state hoặc adapter executor được duyệt | Không mất worktree giữa tool calls; Native không phải OS sandbox |
| M3 | Chạy integrated smoke A/B/C và audit tool/public/canonical binding | Log MCP thực sự, không dùng `mcp_calls=[]` của standalone làm bằng chứng đã tích hợp |
| M3 | Provision môi trường container/ngoài fixture nếu scope mới yêu cầu | Chưa nằm trong Native approved three-fixture profile; không mở rộng tự động |
| Một đồng đội khác người triển khai | Chạy lại độc lập bằng hướng dẫn 03 và runner | Lưu results mới + người chạy/ngày/máy/profile/exit/audit; không ghi đè final evidence của M2 |
| M2 | Hỗ trợ lỗi thuộc core M2 phát hiện trong integration/reproduction | Reproduce + regression test + fix/versioning riêng khi có lỗi thật; không khẳng định không còn việc trước integrated tests |

Không giao cả hai external gates cho M1; M3 chủ trì integration. “M2 đã sẵn sàng
bàn giao” không có nghĩa teammate/M3 đã hoàn tất hoặc đã sign-off.

## 7. Quy trình nhận bàn giao đề xuất

1. Đọc file02 để hiểu implementation và file03 để chạy. Provision prerequisites
   **chỉ lần đầu** theo requirement.txt; không cài lại khi Check đã PASS.
2. Chạy `test_abc_v11_r002.ps1 -Mode Check`; đây không phải repair PASS.
3. Đọc lại evidence chuẩn bằng `-Mode ReadSaved` (không inference); ghi rõ là
   re-audit old records, không được tính teammate đã chạy model độc lập.
4. Khi tự nghiệm thu model, dùng mode Run, outputroot mới (tự sinh), không sửa
   fixtures; lưu summary/all_logs/canonical/worker logs nguyên vẹn.
5. Người chạy xác nhận kết quả riêng. Nếu FAIL, giữ nguyên và điều tra raw,
   parser/stage/command/traceback/config/mask; không sửa `@@` hoặc tests để PASS.
6. Sau M3 tích hợp, chạy lại integrated tests và đối chiếu artifacts với standalone;
   báo riêng nếu environment/profile thay đổi. Không biến prototype thành benchmark.

## 8. Rủi ro / điều không được hiểu nhầm

- Native chạy code trên host dù trong worktree: chỉ ba fixture tin cậy đã hash.
- Tests PASS chỉ là bằng chứng theo oracle hiện có; không chứng minh correctness
  tổng quát, security, API compatibility hay khả năng sửa repo bất kỳ.
- Lịch sử V1–V10/old campaigns còn giữ nguyên failures; đừng reset để lấy quota.
- `requirements` không tự cung cấp model weights, driver, Git hay pinned VGAR.
- Paths trong saved JSON là đường dẫn máy thực nghiệm. Khi clone sang máy khác,
  provisioning/rebase input paths cần được ghi nhận; đừng sửa records cũ cho đẹp.
- Runner mới nằm ở root, không đổi core r002. Run mode là lượt model mới, có thể
  FAIL trên environment khác; không hứa 3/3 luôn luôn thành công.

Tham khảo chi tiết kỹ thuật và paper: file02. Toàn bộ commands/log view: file03.
