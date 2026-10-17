# Tích hợp M2 W7-W8 vào `src/vgar` — thiết kế

Ngày: 2026-10-17 · Nhánh: `feature/m3-w7-w8-repair-loop` · Người làm: M3

## 1. Mục đích và lý do

Hoàn thành phần **M2 tuần 7–8** của `D:\kltn\project_plan_16_weeks.md` (dòng 207–217) chỉ bằng code của repo chính:

- repair prompt cố định (V11), một LLM backend cố định (Qwen3-4B qua HF);
- validate/parse unified diff, `apply_patch` vào worktree tạm;
- relevant-test selection, chạy pytest + mypy + Ruff;
- evidence bundle. Deliverable: pipeline **issue → context → diff → worktree → evidence bundle**.

Code M2 hiện nằm trong gói riêng `M2_week_7_8/src/vgar_m2_w78` (≈3 000 dòng, 30 module) và chỉ chạy được từ thư mục đó. Mục tiêu: **xóa `M2_week_7_8/` mà repo vẫn chạy đúng**, vì từng module M2 đã nằm ở đúng vị trí theo vai trò trong `src/vgar` (không giữ nguyên gói rồi đổi tên).

## 2. Ba giai đoạn (thứ tự do người dùng quyết định)

1. **Giai đoạn 1 — spec này.** Chuyển code M2 vào `src/vgar`; agent LangGraph `solve` chạy theo luồng M2 và **chỉ sinh một lần** (như M2).
2. **Giai đoạn 2 — spec này.** Khi Giai đoạn 1 đã kiểm chứng xong: xóa `M2_week_7_8/` và kiểm chứng lại.
3. **Giai đoạn 3 — spec riêng, sau.** Vòng thử lại khi verify fail. *Không nằm trong spec này.* Ghi chú cho giai đoạn đó: `build_repair_prompt(..., feedback=...)` của M2 đã hỗ trợ phản hồi cho các bản prompt ≥ v5 (gồm V11) mà không đổi byte của lần sinh đầu, và `run_repair` đã có `supersedes_run_id`/`rerun_reason`. Giai đoạn 1 phải giữ nguyên các tham số này để Giai đoạn 3 dùng lại.

## 3. Mục tiêu, không phải mục tiêu, phản mục tiêu

**Mục tiêu**
- Mọi module lõi của M2 có chỗ trong `src/vgar` (bảng ở §5).
- `vgar repair --task … --mode fake|real` chạy A/B/C (`single_file_login`, `multi_file_invoice`, `missing_links`) như CLI M2 cũ.
- `vgar solve` (LangGraph) gọi pipeline M2, một lần sinh, trả về evidence bundle của M2.
- Prompt mặc định là **V11** (`m2-w78-v11`).

**Không phải mục tiêu**
- Vòng thử lại (Giai đoạn 3).
- Campaign/tuning: `campaign.py`, `adaptive_campaign.py`, `b_acceptance.py`, `b_experiment.py`, `b_inputs.py` và các script `run_acceptance.py`, `run_adaptive_acceptance.py`, `run_b_experiment.py`, `qualify_model.py`, `prepare_inputs.py`, `summarize_runs.py`, `record_tests.py`.
- Prompt V1–V10 và evidence cũ (ngoài bộ golden ở §6).
- `bootstrap.py` (cơ chế pin source đã hỏng ở HEAD `2ddb20c0`; thay bằng test).
- `M2_week_7_8/integration/`.
- Mở MCP tools `apply_patch`/`run_relevant_tests`/`verify_patch` mới (việc của M3, làm sau).
- Sửa `graph/grounding.py` (việc của M1).

**Phản mục tiêu — coi là thất bại dù code chạy**
- Byte của prompt render ra khác bản đã lưu.
- Parser diff bị nới lỏng (chấp nhận diff mà M2 từ chối).
- Làm hỏng test đang pass của repo (mốc ở §7).
- Repo gốc / snapshot nguồn bị ghi trực tiếp.
- Còn bất kỳ import, đường dẫn hay test nào trỏ vào `M2_week_7_8/` hay `vgar_m2_w78`.

## 4. Ràng buộc

- **Prompt:** `repair_v11.txt` chép nguyên byte. Logic `build_repair_prompt` giữ nguyên (kể cả nhánh `feedback`, `present_context(absolute_lines, patch_contract)`), chỉ đổi cách tìm file template.
- **Parser/patch:** `parse_unified_diff`, `PatchPolicy`, `apply_patch` giữ nguyên hành vi. Không thêm nhánh chấp nhận mới.
- **Môi trường:** một `.venv` ở gốc (torch 2.5.1+cu121, transformers 4.57.6, tokenizers **0.22.2**; M2 pin 0.22.1). Snapshot Qwen `cdbee75…` có sẵn trong `~/.cache/huggingface`. `interpreter` trong config M2 trỏ tới `vgar_mcp_mvp/.venv` không tồn tại trên máy này → đổi sang python của `.venv` gốc.
- **Trusted fixture:** `require_trusted_fixture` vẫn chặn native execution ngoài các fixture đã khớp byte trong `trusted_fixtures.json`. Áp dụng cho cả `vgar repair` và `vgar solve`.
- **Phụ thuộc M1:** dùng các API M1 sẵn có, không sửa: `vgar.contracts.consumer` (`HandoffTarget`, `receive_context_handoff`, `diagnose_changed_paths`), `vgar.contracts.context.ContextPayload`, `vgar.graph.token_counter.LocalTokenizerCounter`, `vgar.contracts.evidence.*`, `vgar.contracts.repair.{FailureReason, PatchApplyResult}`.

## 5. Bản đồ module

Nguyên tắc: **chuyển, không viết lại.** Giữ tên file M2 trừ chỗ trùng với module có sẵn; sửa import tương đối `from .x` thành đường dẫn mới; bỏ `verify_reference()`.

### 5.1 `src/vgar/repair/` — pipeline và kiểm chứng

| M2 | Đích | Cách làm |
|---|---|---|
| `pipeline.py` | `repair/pipeline.py` | Mới. `run_repair` giữ nguyên chữ ký (cả `feedback`, `supersedes_run_id`, `rerun_reason`); có thể bỏ `campaign_id`/`attempt_id`/`phase`/`before_generation` vì chỉ campaign dùng. |
| `prompt.py` + `prompts/repair_v11.txt` | `repair/prompt.py` + `repair/prompts/repair_v11.txt` | Mới. `template_path` tìm trong `repair/prompts/`; chỉ đăng ký V11 — phiên bản khác báo lỗi rõ ràng. |
| `patch.py` | `repair/patch.py` | Mới. |
| `verification.py` | `repair/verification.py` | Mới. |
| `checks.py` + `config/fixtures/{mypy.ini,ruff.toml}` | `repair/static_checks.py` + `configs/m2/static/` | **Thay** nội dung bản chưa commit hôm 2026-10-16 bằng ngữ nghĩa `checks.py` của M2 (API `run_static_checks(lease, targets, policy, executor)`, kiểm `syntax`/`mypy`/`ruff`, hash config). Test cũ trong `tests/unit/test_static_checks.py` được port sang API này nếu còn ý nghĩa, còn lại bỏ. |
| `test_selection.py` | `repair/test_selection.py` | Mới (policy của M2 trên `diagnose_changed_paths`). Khác `graph/test_selection.py` — không gộp. |
| `context_adapter.py`, `context_presentation.py` | `repair/context_adapter.py`, `repair/context_presentation.py` | Mới. |
| `workspace.py` | `repair/workspace.py` | **Thay** bản cũ. Các caller hiện có (`agents/nodes/{prepare,finalize,verify}.py`, `cli.py`, `mcp/servers/repository_server.py`) dùng `safe_relative_path`, `fingerprint_source`, `create_workspace`: giữ các hàm này trong module mới (chuyển sang hoặc giữ lại bên cạnh API M2) để caller vẫn chạy. |
| `test_runner.py` + `pytest_plugin.py` | `repair/test_runner.py` + `repair/pytest_plugin.py` | **Thay** bản cũ. Caller cũ của `run_tests(workspace, selectors, timeout)` (`cli.py`, `agents/nodes/verify.py`, scripts) phải được cập nhật hoặc xóa cùng node bị bỏ. Plugin được nạp bằng tên module mới (`-p vgar.repair.pytest_plugin`). |
| `evidence.py` | `repair/evidence.py` | Mới. `evidence_writer.py` và `baseline.py` cũ: xóa nếu sau khi chuyển không còn caller ngoài test/scripts của chính chúng; xóa luôn test/scripts đó. |
| `executor.py`, `diagnostics.py` | `repair/executor.py`, `repair/diagnostics.py` | Mới. `remaining_timeout` (từ `bootstrap.py`) chuyển vào `executor.py`. |
| `config.py` | `repair/config.py` | Mới. `load_config` đọc `configs/m2/demo.json`. |
| `cli.py` | lệnh con `vgar repair` trong `src/vgar/cli.py` | Mới. Tham số giữ như CLI M2 (`--task`, `--config`, `--mode`, `--output-root`, `--keep-workspace`, `--supersedes-run-id`, `--rerun-reason`). Mã thoát PASS 0 / FAIL 1 / ERROR 2. |

### 5.2 `src/vgar/models/` — sinh

| M2 | Đích |
|---|---|
| `generator.py` (`FakeGenerator`) | `models/generator.py` |
| `generator_hf.py` (`HFGenerator`, `HFChatTokenizer`) | `models/huggingface/generator_hf.py` |
| `hf_backend.py`, `hf_diagnostics.py`, `hf_worker.py`, `model_worker.py` | `models/huggingface/` (worker chạy bằng `python -m vgar.models.huggingface.hf_worker`) |
| `local_chat.py` | `models/huggingface/local_chat.py` |

`hf_model.py`/`local_hf_chat_model.py` (LangChain chat model) giữ nguyên; `vgar run`/`vgar chat` vẫn dùng chúng.

### 5.3 `src/vgar/contracts/`

`contracts.py` của M2 (`safe_path`, `safe_selector`, `RepairTask`, `RepairPolicy`, `ModelProfile`) → nối vào `contracts/repair.py`, cạnh `FailureReason`/`PatchApplyResult` có sẵn.

### 5.4 Thay hằng `ROOT`

M2 dùng `ROOT = parents[2]` của gói để tìm `prompts/`, `config/`, `tests/fixtures/`, và để băm `source_fingerprint` trên `src/scripts/prompts/config`. Sau khi chuyển:
- prompt: tương đối với `repair/prompt.py`;
- config, fixture: tương đối với gốc repo (`configs/m2/`, `examples/m2/`);
- `source_fingerprint`: băm `src/vgar/repair`, `src/vgar/models`, `src/vgar/contracts`, `configs/m2`. Byte `run_record.json` vì thế khác bản cũ — chấp nhận, không thuộc bất biến §6.

### 5.5 Dữ liệu

| M2 | Đích |
|---|---|
| `config/demo.json` | `configs/m2/demo.json` — `prompt_version` = `m2-w78-v11`, `interpreter` = python `.venv` gốc, các đường dẫn khác tính lại theo vị trí mới |
| `config/trusted_fixtures.json` | `configs/m2/trusted_fixtures.json` |
| `examples/{tasks,handoffs,snapshots}` | `examples/m2/…` (input demo, không chỉ là test) |
| `tests/fixtures/reference_patches/*.diff` | `tests/fixtures/m2/reference_patches/` (output giả cho fake mode) |
| bộ golden §6 | `tests/fixtures/m2/golden_v11/{A,B,C}/` |

### 5.6 LangGraph `solve` (Bước 2 của Giai đoạn 1)

Luồng mới: `START → initialize → repair_run → finalize | failed → END`.

- `repair_run` gọi `vgar.repair.pipeline.run_repair` đúng một lần với generator chọn theo mode (fake / HF), rồi đưa `run_record` + `evidence_bundle.json` vào state. Không có cạnh `verify → repair`.
- Đây là lựa chọn của thiết kế: giữ pipeline M2 nguyên khối thay vì tách thành nhiều node, vì Giai đoạn 3 có thể lặp bằng cách gọi lại `run_repair(feedback=…)`.
- Bỏ khỏi luồng `solve`: node `prepare_workspace`, `repair` (exact-edit agent), `verify`, cùng thay đổi chưa commit của hôm 2026-10-16 trong `nodes/repair.py`, `nodes/verify.py`, `tests/unit/test_workflow.py`. `agents/core.py` và lệnh `vgar run`/`vgar chat` giữ nguyên.
- `cmd_solve` nhận một file task M2 (`--task`) thay cho `--repo/--issue/--selectors`, và in đường dẫn run.
- Instrumentation hiện có (`instrument_node`, `emit`) bọc node mới để vẫn log prompt version, model, latency, token.

## 6. Bất biến byte và golden test

Bộ golden chép từ `M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/{A,B,C}/<run>/` (đang được git track): `prompt.txt`, `raw_model_output.txt`, `applied.diff`, `evidence_bundle.json`, `run_record.json`. Không chép `model-workers/`.

Test bắt buộc (viết **trước** khi chuyển code, chạy đỏ, rồi xanh dần):
1. **Prompt byte:** với mỗi A/B/C, chạy pipeline fake mode, đặt `FakeGenerator` trả `raw_model_output.txt` đã lưu → `prompt.txt` mới khớp byte bản lưu (SHA-256 đầu: A `b39baa82…`, B `4f234c25…`, C `c37a5ef2…`; template `repair_v11.txt` là `ba6d1478…`) và `input_tokens` khớp `run_record.json` lưu. Kiểm tra lại token count vì tokenizers 0.22.2 ≠ 0.22.1.
2. **Parser/apply:** cùng lượt đó → `applied.diff` mới khớp byte bản lưu, trạng thái run như bản lưu.
3. **Đối chiếu với gói cũ (trước Giai đoạn 2):** chạy cả `vgar_m2_w78` cũ lẫn code mới trên cùng input fake → `prompt.txt` và `applied.diff` giống hệt nhau. Nếu (1) lệch nhưng (3) khớp, độ lệch có sẵn từ trước (do tokenizer local vs HF): ghi lại, không "sửa" prompt.
4. Port các test lõi của M2: `test_patch`, `test_pipeline`, `test_prompt_v11`, `test_workspace`, `test_workspace_cleanup`, `test_test_runner`, `test_verification`, `test_executor`, `test_evidence`, `test_context_adapter`, `test_test_selection`, `test_generator`, `test_hf_adapter`, `test_local_chat`, `test_contracts`, `test_diagnostic_logging`, `test_finalization`, `test_generation_diagnostics`, `test_tokenizer_flags`, `test_review_guards`, `test_cli`. Bỏ test của campaign, V1–V10, bootstrap, relocation.

## 7. Mốc test và cách kiểm chứng

**Mốc hiện tại (2026-10-17, chạy `pytest -q` ở gốc):** 578 pass, 1 skip, 4 fail có từ trước:
- `tests/m2/test_w78_integration.py` × 3 — kiểm tra relocation của thư mục M2; xóa cùng thư mục ở Giai đoạn 2 (cùng `tests/m2/test_w78_preservation.py`, `scripts/check_m2_integration.py`, `run_m2_abc.ps1` nếu chúng chỉ phục vụ thư mục đó).
- `tests/test_hf_model.py::test_local_chat_model_uses_one_greedy_generation_config` — không liên quan, không sửa.

**Sau mỗi bước:** mọi test từng pass vẫn pass (trừ test bị xóa có chủ đích, liệt kê trong commit), cộng test mới; một commit mỗi bước.

**Kết thúc Giai đoạn 1:** golden test xanh; `vgar repair --mode fake` PASS cho A/B/C; `vgar solve --task … ` (fake) PASS cho A/B/C.

**Giai đoạn 2:** đổi tên `M2_week_7_8/` trước, chạy toàn bộ test + fake A/B/C + `grep` không còn `vgar_m2_w78`/`M2_week_7_8` trong `src tests scripts configs`; nếu xanh thì **hỏi người dùng xác nhận** rồi mới xóa hẳn (thư mục có 307 file đang được git track) trong một commit riêng. Sau đó chạy thật Qwen3-4B trên GPU cho A/B/C bằng `vgar repair --mode real`, lưu output vào `results/` (bị gitignore).

**Nếu lần chạy thật FAIL:** ghi lại evidence, điều tra một lần, báo người dùng. Không sửa prompt hay parser để cho qua.

## 8. Thứ tự làm (gợi ý cho kế hoạch)

0. Chép golden + examples + reference patches; viết test §6 (đỏ).
1. Tầng nền: `contracts/repair.py`, `repair/executor.py`, `repair/diagnostics.py`, `repair/config.py`.
2. Tầng chạy: `workspace`, `test_runner` + `pytest_plugin`, `static_checks`, `evidence`; cập nhật caller.
3. Tầng repair: `context_adapter`, `context_presentation`, `prompt`, `patch`, `verification`, `test_selection`.
4. Tầng model: `generator`, `huggingface/*`.
5. `pipeline` + `vgar repair`; golden test xanh.
6. Nối `vgar solve` (§5.6).
7. Giai đoạn 2 (§7).

## 9. Để người làm tự quyết

- Chi tiết gộp API `workspace`/`test_runner` cũ với API M2 (miễn caller còn lại chạy đúng và không còn hai bản trùng chức năng).
- Cấu trúc file test mới trong `tests/` (gợi ý `tests/m2/w78/`).
- Tên field trong `VGARState` cho kết quả `run_repair`.
- Có cập nhật `README.md`/`PROGRESS.md` hay không: chỉ một đoạn ngắn hướng dẫn `vgar repair`/`vgar solve`.
