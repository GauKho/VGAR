# Kế hoạch xử lý W11–12: nợ từ các giai đoạn trước, kỹ thuật, test case, bảng đánh giá

> ⚠️ **ĐỀ XUẤT — KHÔNG THAY THẾ DELIVERABLES V2.** Plan chính thức là `D:\kltn\VGAR_W9_W16_Deliverables (1).md` (v2, 19/10/2026). File này chỉ là ghi chú tham khảo để nhóm cân nhắc; mọi thay đổi plan phải được nhóm duyệt và ghi amendment.

> **Ngày:** 31/10/2026 (M3). Tiếp nối `docs/status/plan_audit_2026-10-31.md` (§3 đánh giá task, §6 xử lý nợ).
> **Trạng thái:** đề xuất, chưa được nhóm duyệt, chưa sửa code.
> **Nguồn đối chiếu:** proposal §8.5, §10.3, §10.5, §11, §12, §13.2; plan 16 tuần (W11–12, bảng metrics, bảng ablation); deliverables v2 (W11–12, cổng M6).

## 1. Nợ từ giai đoạn trước ảnh hưởng tới W11–12 (đã kiểm trong code ngày 31/10)

Mã B01–B12 lấy từ `Task Status.md` §6. Cột "Còn mở?" là kết quả kiểm code hôm nay, không lấy lại nguyên từ audit cũ.

| # | Nợ (giai đoạn gốc) | Bằng chứng | Còn mở? | Ảnh hưởng tới task W11–12 |
|---|---|---|---|---|
| D1 | **B10 nối sai import** (W3–4 M1-05) | `src/vgar/graph/builder.py:1355`: vẫn fallback `unique_symbols_by_name` kể cả khi tên đã được import tường minh từ module khác | **Có** | M2-W11-2: edge giả sinh ra **cycle giả**, làm A3 false reject. Impact (W10) kéo theo caller/test sai. M1-W11-2: ranking tune trên graph sai |
| D2 | 79% call site chưa resolve (W3–4 M1-04/05, W10) | Smoke flask-5014: 3261 unresolved | Có | M2-W11-1: không trả lời được "caller đã được cập nhật chưa". M2-W11-2: cycle trên `CALLS` không có nghĩa |
| D3 | IMPORTS fan-out nhiễu trong impact (W10) | Memory W10: 67 impacted, phần lớn ở hop 2 | Có | M2-W11-1/2 nếu dùng impact để chọn phạm vi check; phép đo RQ3 |
| D4 | `public_api_risk` có trọng số 0 (W5–6 M1-06) | `src/vgar/graph/retrieval.py:30` | Có | M1-W11-2: ứng viên tune; khi M2-W11-1 có `signature_changed` thì feature này mới có dữ liệu |
| D5 | Anchor nhiễu ở grounding (W5–6) | Memory `graph-anchor-noise-w5-w6` | Có | M1-W11-2 |
| D6 | **B12 redact secret hỏng** (W3–4 M3-05) | `src/vgar/observability/instrumentation.py:31`: raw string chứa `\\b`, `\\s` nên không bao giờ match `Bearer …`; `phase_logger.py:17` ghi rõ "not a secrets redactor"; `mcp/client.py:17` chỉ lọc theo `SECRET_KEYS` | **Có** | M3-W11-1: test secret redaction **sẽ fail** nếu chưa sửa |
| D7 | **B04/B05 legacy servers** (W3–4) | `configs/mcp.yaml` vẫn đăng ký `repository_server`, `execution_server`; `execution_server.run_pytest` nhận selector và timeout do caller chọn | **Có** | M3-W11-1/2; DoD "không chạy command tùy ý" |
| D8 | **B02 resource node URL-encoded** (W3–4 M3-02) | `graph_server.py` không decode ID | Có (theo audit, chưa sửa) | M3-W11-3: contract test phải phủ cả resource |
| D9 | B11 verdict `vgar run` yếu (W7–8) | `cli.py`; `solve` đã đúng, `run` chưa | Có | M3-W11-2: bỏ hoặc chuyển `vgar run` sang engine M2 |
| D10 | B06 skip-only false accept (W3–4) | Engine M2 đã có `VERIFICATION_INCOMPLETE` (`repair/verification.py:21,60`); đường legacy chưa | Đã xử lý trong engine M2; legacy còn | M2-W12-2: mutant kiểu "skip test" phải bị bắt; đây là một loại mutant bắt buộc |
| D11 | B01 test HF constructor fail (W3–4) | 1 fail có sẵn, đang deselect | Có | CI là điều kiện của branch protection: cần sửa hoặc `xfail(strict=True)` kèm lý do |
| D12 | Model revision chưa pin (W1–2 CHUNG-03) | Task Status 5.1 | Có | M3-W12-2: freeze không hợp lệ nếu thiếu |
| D13 | `local_chat.py` không trả usage | Không có `usage`/token count trong file | Có | M3-W12-1: không đo được token/lượt |
| D14 | VRAM để trống ở 7 row W10 | `evaluation/repair/gpu.py:45`: trả `None` khi bất kỳ mẫu nào lỗi | Có | M3-W12-1: số đo hiệu năng thiếu |
| D15 | Timeout dồn vào arm graph (W10, D26) | 6/7 `GENERATION_TIMEOUT` ở A1/A2 | Có | M2-W12-1 (A3 cũng là arm graph), M3-W12-2 |
| D16 | Harness và Docker dễ vỡ (W9–10, D21) | Image đã xóa; cổng RAM ≥2 GiB; ổ C bị chiếm khi pull | Có | Cổng "harness ổn định", M2-W12-2 (mutant cần môi trường), chạy lại A1/A2/A3 |
| D17 | Bất biến của policy W10 | `policy_hash` của A0–A2 đã ghi trong record W10 | Rủi ro | M2-W11-3: thêm trường mới **không được** đổi hash A0–A2, nếu không bảng dev W10 mất hiệu lực |
| D18 | Test selection là static hint, không phải coverage runtime (W7–8) | `repair/test_selection.py` | Có | M2-W12-2 và W14: không được gọi là "coverage" |
| D19 | `vgar chat`/`run` phụ thuộc legacy server (W3–4, B03/B11) | `agents/core.py` nạp mọi server trong `configs/mcp.yaml`; sửa file bằng tool exact-edit của `repository_server`; verify chỉ là lời dặn trong `prompts/system.md` | Có | M3-W11-2: gỡ legacy thì `chat` mất cả tool sửa file lẫn tool **đọc** file theo đường dẫn. **Chốt 31/10 (thay phương án (a)): vá, giữ 4 server** (spec Q2). `chat` dùng graph + `repository_read_file` (read-only, root theo lease) + `execution_run_pytest` (đã vá) + repair; bỏ `repository_server.apply_patch`, ghi file chỉ qua `repair_server` |
| D20 | RQ5 không có nguồn số liệu | Runner A0–A3 (`evaluation/repair/launch.py`) gọi thẳng `repair.pipeline.run_repair`, không có MCP tool call | Có | M3-W12-1: **chốt 31/10**, đo trên `vgar solve --agent` (5 dev task, mô tả). Chưa có bằng chứng `solve --agent` chạy trên task SWE-bench (các run 18/10 và 30/10 đều trên task demo/fixture) → cần smoke trước |

## 2. Đề xuất kỹ thuật theo từng task

### M1-W11-2 ranking (làm trước M1-W11-1)

1. **Sửa D1 trước khi tune.** Ở `builder.py:1355`, nếu `expression` có trong `module.imported_symbols` mà target không có trong repo thì trả `None` (ghi unresolved hoặc candidate), **không** fallback theo tên duy nhất. Fallback chỉ dùng khi tên không được import tường minh.
2. **Tune chỉ trên dev 25 task**, từng bước một: (a) sau khi sửa B10, (b) bật `public_api_risk`, (c) giảm trọng số IMPORTS hop 2. Mỗi bước ghi vào `docs/m1_retrieval_method.md` kèm bảng R1 (§4).
3. **Đóng băng config** (hash trọng số và hash builder) → dùng cho lần chạy lại A1/A2/A3 ở W12.

### M1-W11-1 incremental

- Dùng `graph_version` sẵn có (`builder.py:150, 203`). Updater nhận danh sách file đổi, xóa node/edge thuộc các file đó, parse lại, rồi link lại cho **closure ngược** (các file import hoặc gọi vào node đã đổi).
- So bằng **chuẩn hóa tập node/edge** (sắp xếp, bỏ timestamp) giữa bản incremental và bản full rebuild trên cùng source.

### M2-W11-1 api_check

- Lấy chữ ký bằng `ast` (không cần graph): tên public (theo `__all__` nếu có, nếu không thì tên không bắt đầu bằng `_`) và tham số (positional, kw-only, default, `*args/**kwargs`).
- Không tương thích khi: xóa symbol public; thêm tham số bắt buộc; xóa tham số hay đổi thứ tự positional; bỏ default. Thêm tham số có default thì tương thích.
- Ghi `callers_in_repo` từ graph **chỉ để báo cáo** (D2: không dùng làm điều kiện quyết định).
- Kết quả ghi vào `ImpactReport.risk.signature_changed` (mở D4).

### M2-W11-2 structural_check

- Rule chung, không cần config: **không thêm cycle IMPORTS mới so với baseline**. Chỉ tính edge IMPORTS đã resolve trong repo, confidence ≥ ngưỡng, sau khi sửa D1. Không xét cycle trên CALLS (D2).
- Rule theo config (`configs/m2/structural/<repo>.yaml`): import cấm, layer. Không có config thì `NOT_RUN`.
- Kết quả so delta với baseline: cycle có sẵn thì không tính.

### M2-W11-3 evidence

- Thêm `api_check`, `structural_check` vào `contracts/evidence.py` dạng `{status: PASS|FAIL|NOT_RUN|ERROR, reasons, details_ref}`.
- **Giữ nguyên `policy_hash` của A0–A2 (D17):** trường mới là "recorded" và không vào `required_checks` của A0–A2. Có test chặn việc hash đổi.

### M2-W12-1 A3

- `configs/m2/variants/A3.json` = A2 + `required_checks += [api, structural]`. **Dùng cùng vòng retry với A2**, kết quả fail của check mới chỉ đưa vào feedback (không re-plan riêng).
- Mở rộng `fairness.py`: A3 chỉ được khác A2 ở `required_checks`.
- Chạy trên **cùng 25 dev task** (cùng tiền tố manifest W10).

### M2-W12-2 mutant pool

- `scripts/build_mutant_pool.py` sinh mutant **xấu** từ gold patch của 25 dev task, có seed cố định, gồm 5 loại:
  1. đảo điều kiện;
  2. xóa hàm public;
  3. đổi chữ ký;
  4. thêm import tạo cycle;
  5. làm test bị skip (D10).
- Patch **tốt** = gold patch.
- Nhãn kỳ vọng do loại mutant quyết định. Script **không import** code verifier, nên nhãn độc lập với verifier.
- `verifier_eval.py` verify mỗi patch **một lần** với tập check đầy đủ (tests, static, api, structural), rồi suy verdict của A0–A3 bằng cách áp `required_checks` của từng arm lên cùng kết quả → bảng V1 (§4). Hợp lệ vì các arm chỉ khác nhau ở `required_checks` (V12).
- **Máy chạy (chốt 31/10, phương án A):** máy M3, nối tiếp sau khi GPU W12 xong; không chạy song song GPU. Xem `docs/status/w11_w12_assignment.md` §0.6.

### M3-W11-1 security và M3-W11-2 legacy

- **Vá, không gỡ** (spec Q2): giữ `repository_server` và `execution_server` trong `configs/mcp.yaml`.
  - `repository_server`: chỉ còn `read_file`, read-only, root theo lease do host cấp (B04), đọc theo khoảng dòng, output có trần. **Bỏ `apply_patch`.**
  - `execution_server.run_pytest`: root theo lease; selector, timeout, output do server quyết định qua runner chung của M2 (B05).
  - Cập nhật `scripts/smoke_mcp.py`. `vgar run` bỏ hoặc chuyển sang `solve` (D9).
- **`vgar chat` (D19):** `core.py` giữ nguyên cơ chế nạp tool. Sau khi vá, `chat` có tool graph + `repository_read_file` + `execution_run_pytest` + repair; ghi file chỉ qua `repair_server`. Sửa `prompts/system.md` để không nhắc tới exact-edit. Chat unification (A5) để sau freeze.
- **Sửa D6:** bỏ escape thừa ở `instrumentation.py:31` (`r"(?i)\bBearer\s+…"`). Dùng chung một hàm redact cho audit, `phase_logger` và message lỗi. Môi trường tiến trình con dùng **allowlist** thay cho denylist `SECRET_KEYS`.
- **Giới hạn do server đặt:** timeout tối đa, kích thước output tối đa **trong lúc capture**, selector phải là node id pytest nằm trong root.
- **Hai ý còn thiếu so với proposal §10.5:**
  - tool ghi file chỉ chạy trên lease, không có trên graph server (graph server read-only);
  - kết quả trả từ text trong repo được gắn `untrusted: true` trong envelope.

### M3-W11-3 schema và error taxonomy

- Envelope chung: `{ok, data | error{code, message, retryable}, audit_id}`. `code` thuộc một enum duy nhất trong `mcp/schemas.py`. Ghi lại trong `docs/mcp_tool_contract.md`.
- Sửa D8: decode node id đúng một lần ở biên resource.

### M3-W12-1 đo lường

- `local_chat.py` trả `usage{prompt_tokens, completion_tokens}` (D13). Lấy từ tokenizer đã có, không cần ước lượng.
- `gpu.py` giữ peak của các mẫu thành công và ghi `samples_failed` thay vì trả `None` (D14).
- Hai metric thiếu:
  - **invalid call rate** = số call trả `error.code ∈ {SCHEMA_INVALID, ARG_INVALID}` / tổng số call;
  - **audit completeness** = số call có audit entry / tổng số call trong trace agent.
- **Nguồn dữ liệu (D20):** trace của `vgar solve --agent` (`tool_agent.py` đã ghi trace và từng lượt model). Trước hết smoke ở chế độ fake trên 1 dev task (M3-X2a, W11), sau đó chạy Qwen thật trên 5 dev task RUNNABLE đầu tiên theo thứ tự manifest, config như A2 (M3-X2b, W12). Chỉ dùng để mô tả, không so sánh thống kê với A0–A3.
- **Ranh giới claim:** `solve --agent` là agent bị ràng buộc (model chọn tool, lúc thử lại, lúc dừng; tối đa 3 lần thử, 15 tool call; không đọc code, không tự viết diff). Không gọi kết quả A0–A3 là kết quả của agent.

### M1-W12-2 dry-run và cổng "harness ổn định"

- `scripts/dry_run_heldout_chain.sh` chạy trên 2 dev task: retrieval → runner (A0–A3) → harness grade → aggregate. Ghi lệnh, hash config, thời gian và đường dẫn output.
- Cổng đạt khi chạy 2 lần liên tiếp không có ERROR hạ tầng (D16).

### M3-W12-2 protocol freeze

- Phải có: model revision SHA (D12), prompt hash, budget, timeout (D15), hash config ranking sau tune, manifest hash held-out, **metric chính và phụ** (§4), phép thống kê, lệnh chạy lấy từ dry-run.
- `dataset.py` chỉ mở held-out khi hash của file freeze khớp tag `protocol-freeze`.

## 3. Test case

Tên test là đề xuất. File đặt theo quy ước hiện có. Tất cả phải chạy trong CI với `-m "not hf and not docker"`, trừ test có đánh dấu riêng.

### 3.1. Graph (M1)

| ID | Test | Input | Kỳ vọng |
|---|---|---|---|
| G1 | `test_explicit_external_import_not_bound_to_internal_unique_name` | `from wrong.module import unique_helper`; repo có `a.unique_helper` | Không có edge CALLS tới `a.unique_helper`; call ghi unresolved |
| G2 | `test_unique_name_fallback_without_import_still_resolves` | Gọi `unique_helper()` không có import | Vẫn resolve như cũ (không regression) |
| G3 | `test_incremental_equals_full_rebuild[modify\|add_file\|delete_file\|rename_function\|move_import]` | Fixture repo và một delta | Tập node/edge chuẩn hóa và `graph_version` giống full rebuild |
| G4 | `test_incremental_relinks_callers_when_callee_deleted` | Xóa hàm được gọi ở file khác | Edge từ caller bị xóa; caller không mang edge treo |
| G5 | `test_incremental_noop_keeps_version_and_hits_cache` | Không có file đổi | `graph_version` không đổi; cache hit = 100% |
| G6 | `test_ranking_config_hash_recorded` | Chạy retrieval | Output có hash trọng số; đổi trọng số thì hash đổi |

### 3.2. Verification (M2)

| ID | Test | Input | Kỳ vọng |
|---|---|---|---|
| V1 | `test_api_remove_public_function_fails` | Xóa `def f` public | `FAIL`, `API_SYMBOL_REMOVED` |
| V2 | `test_api_add_required_param_fails` / `..._with_default_passes` | `f(a)` → `f(a, b)` / `f(a, b=1)` | `FAIL` / `PASS` |
| V3 | `test_api_private_and_body_only_changes_pass` | Đổi `_g`; chỉ đổi thân `f` | `PASS` |
| V4 | `test_api_respects___all__` | Symbol không có trong `__all__` bị xóa | `PASS` |
| V5 | `test_api_unparseable_baseline_is_error_not_pass` | Baseline lỗi cú pháp | `ERROR` hoặc `NOT_RUN`, không `PASS` |
| V6 | `test_structural_new_import_cycle_fails` | Patch thêm `b → a` khi đã có `a → b` | `FAIL`, `NEW_IMPORT_CYCLE` |
| V7 | `test_structural_preexisting_cycle_passes` | Cycle có sẵn ở baseline, patch không chạm | `PASS` |
| V8 | `test_structural_ignores_unresolved_and_low_confidence_edges` | Edge kiểu B10 (conf 0.6, external) | Không tạo cycle |
| V9 | `test_structural_no_config_layer_rules_not_run` | Repo không có config | Layer `NOT_RUN`; cycle rule vẫn chạy |
| V10 | `test_not_run_never_counts_as_pass_in_A3` | A3, `api_check = NOT_RUN` | Verdict `VERIFICATION_INCOMPLETE`, không ACCEPT |
| V11 | `test_policy_hash_A0_A2_unchanged` | Load A0–A2 sau khi thêm trường | Hash trùng giá trị ghi trong record W10 |
| V12 | `test_A3_differs_from_A2_only_in_required_checks` (mở rộng `test_arm_fairness.py`) | Config A2, A3 | Chỉ khác `required_checks`; sửa thêm field khác thì runner từ chối |
| V13 | `test_mutant_labels_independent_of_verifier` | Import graph của `build_mutant_pool.py` | Không import `vgar.repair.verification` |
| V14 | `test_mutant_pool_deterministic` | Chạy 2 lần cùng seed | Byte-identical |
| V15 | `test_skip_mutant_rejected` | Mutant làm test bị skip | `VERIFICATION_INCOMPLETE` |
| V16 | `test_derived_arm_verdict_matches_direct_verify` | Fixture: một patch, verify đầy đủ một lần, rồi suy verdict A0–A3; so với verify trực tiếp từng arm | Verdict trùng nhau ở cả 4 arm |

### 3.3. MCP và security (M3)

| ID | Test | Input | Kỳ vọng |
|---|---|---|---|
| S1 | `test_path_traversal_rejected[../, absolute, symlink_out]` | Path ra ngoài root | `error.code = PATH_OUTSIDE_ROOT` |
| S2 | `test_wrong_root_rejected` (B04) | Root sibling hoặc tự chọn | Bị từ chối; lease root mới hợp lệ |
| S3 | `test_selector_policy` (B05) | `../x.py::t`, `/abs::t`, `-k x`, xuống dòng | Bị từ chối |
| S4 | `test_timeout_capped_and_process_tree_killed` | Test `sleep` lâu hơn max; tiến trình con sinh cháu | Kết thúc ở max; không còn tiến trình mồ côi |
| S5 | `test_output_bounded_during_capture` | Test in 100 MB | Bộ nhớ có giới hạn; output bị cắt, có cờ `truncated` |
| S6 | `test_secret_redaction[bearer, password=, api_key in args, in error message]` (B12) | Credential **giả** | Không xuất hiện trong audit, log hay error |
| S7 | `test_child_env_allowlist` | Đặt `DUMMY_TOKEN=x` | Tiến trình con không thấy biến này |
| S8 | `test_every_call_has_audit_entry_including_errors` | 1 call OK + 1 call lỗi schema | 2 audit entry có `input_hash`, `status` |
| S9 | `test_vgar_tools_lists_only_guarded_tools` | `vgar tools` | Mọi tool đều qua guard; không còn `repository_apply_patch`; `repository_read_file` và `execution_run_pytest` không nhận `repo_path` từ model |
| S10 | `test_envelope_and_error_codes_uniform` (mở rộng `test_mcp_tool_contract.py`) | Mọi tool, input đúng và sai | Đúng envelope; `code` thuộc enum |
| S11 | `test_node_resource_roundtrip_encoded_id` (B02) | Node id chứa `/` và `:` qua MCP thật | Tìm thấy node |
| S12 | `test_repo_text_marked_untrusted` | README chứa "ignore previous policy" | Kết quả có `untrusted: true`; policy không đổi |
| S13 | `test_graph_server_has_no_write_tools` | Liệt kê tool graph | Không tool nào ghi file |
| S14 | `test_chat_agent_has_no_write_tool_outside_repair` | `load_mcp_tools` với `configs/mcp.yaml` mới | Có `repository_read_file`; không có tool ghi file nào ngoài `repair_server` |
| S16 | `test_read_file_bounded_and_untrusted` | Đọc file lớn theo khoảng dòng; đọc ngoài root lease | Output có trần và cờ `truncated`, có `untrusted: true`; ngoài root bị từ chối |
| S15 | `solve --agent` chế độ fake trên 1 dev task (smoke, đánh dấu `docker`, chạy tay trên máy M3) | Gold patch làm patch kịch bản | Run kết thúc bằng `repair_verify_patch`; có trace và run record; repo gốc không đổi |

### 3.4. Đo lường và quy trình

| ID | Test | Kỳ vọng |
|---|---|---|
| M1 | `test_local_chat_returns_usage` | `usage.prompt_tokens > 0`, khớp tokenizer |
| M2 | `test_gpu_peak_kept_when_some_samples_fail` | Peak là max của các mẫu thành công; có `samples_failed` |
| M3 | `test_invalid_call_rate_and_audit_completeness` | Trace fixture: 1/4 lỗi schema → 0.25; audit completeness 1.0 |
| M4 | `test_p50_p95_per_tool` | Tính đúng trên fixture đã biết |
| P1 | `test_heldout_locked_without_freeze` | `dataset.py` từ chối held-out khi không có hoặc sai hash freeze |
| P2 | `test_hf_constructor` (B01) | Sửa, hoặc `xfail(strict=True)` kèm lý do; CI xanh mà không cần deselect |

## 4. Bảng đánh giá (theo proposal §13.2 và bảng metrics của plan)

Quy ước chung:
- Mọi bảng sinh từ script và ghi mẫu số N.
- Có CI 95% paired bootstrap ở các cột so sánh giữa arm (`stats.py`, W14).
- Task lỗi hoặc timeout **vẫn nằm trong mẫu số**.
- Cột "Vai trò" cho biết bảng nào là **metric chính** cần chốt trong protocol freeze.

### R1 — Retrieval (RQ2) · Vai trò: **chính**

| Arm | N | File R@3 | File R@5 | File R@10 | Function R@k | MRR | Token context | Δ so BM25 [CI 95%] |
|---|---|---|---|---|---|---|---|---|
| BM25 | | | | | | | | — |
| Graph (trước tune) | | | | | | | | |
| Graph (sau tune) | | | | | | | | |

Tách thêm theo single-file / multi-file.

### P1 — Repair funnel (RQ4) · Vai trò: **chính** cho F3/F4, **phụ** cho resolved

| Arm | N | F1…F8 (theo `aggregate.py`) | Resolved (harness) | GENERATION_TIMEOUT | Số lần generate | Token/task | Latency/task | VRAM peak |
|---|---|---|---|---|---|---|---|---|
| A0 BM25 + tests | | | | | | | | |
| A1 Graph + tests | | | | | | | | |
| A2 + typecheck/lint | | | | | | | | |
| A3 + API/structural | | | | | | | | |

### V1 — Verification (RQ4) · Vai trò: **chính**

Quy ước: positive = patch xấu. FAR = số patch xấu được ACCEPT / tổng patch xấu. FRR = số patch tốt bị REJECT / tổng patch tốt.

| Arm | Patch xấu (N) | Patch tốt (N) | TP | FN (false accept) | TN | FP (false reject) | FAR | FRR |
|---|---|---|---|---|---|---|---|---|
| A0/A1 (tests) | | | | | | | | |
| A2 | | | | | | | | |
| A3 | | | | | | | | |

### V2 — Tỷ lệ phát hiện theo loại mutant (proposal: API break, structural violation)

| Loại mutant | N | A1 | A2 | A3 |
|---|---|---|---|---|
| Đảo điều kiện | | | | |
| Xóa hàm public | | | | |
| Đổi chữ ký | | | | |
| Import tạo cycle | | | | |
| Skip test | | | | |

### I1 — Patch impact (RQ3) · Vai trò: **phụ** (đề xuất mới, cần nhóm duyệt)

Ground truth: test FAIL_TO_PASS và PASS_TO_PASS của SWE-bench. Không cần gán nhãn tay.

| Phương pháp | N task | Recall test F2P trong vùng impact | Median kích thước vùng impact | Recall file gold |
|---|---|---|---|---|
| Chỉ dùng diff (file trong diff và test cùng tên) | | | | |
| Graph impact (`analyze_patch_impact`, gold patch) | | | | |

### G1 — Graph quality (RQ1) · Vai trò: **phụ**

| Loại edge | Mẫu gán tay (n) | Precision | Recall | % call site unresolved | Trước/sau sửa B10 |
|---|---|---|---|---|---|
| CALLS | | | | | |
| IMPORTS | | | | — | |
| TESTS | | | | — | |

### U1 — Incremental update (proposal §11.3)

| Kịch bản | Cold build (s) | Warm update p50/p95 (s) | Speedup | File đổi | Node bị ảnh hưởng | Cache hit | Trùng full rebuild |
|---|---|---|---|---|---|---|---|
| Sửa thân hàm | | | | | | | |
| Thêm/xóa file | | | | | | | |
| Đổi chữ ký public | | | | | | | |

### M1 — MCP usability (RQ5)

Nguồn: trace `vgar solve --agent` trên 5 dev task (M3-X2b). Chỉ mô tả, ghi rõ N = 5.

| Tool | Số call | p50 (ms) | p95 (ms) | Invalid call rate | Audit completeness | Token/lượt model |
|---|---|---|---|---|---|---|
| `repair_get_task_context` | | | | | | |
| `analyze_patch_impact` | | | | | | |
| … | | | | | | |

### S1 — Security checklist (proposal §10.5)

| Rule | Test | Trạng thái |
|---|---|---|
| Path jail và allowlist | S1, S2 | |
| Read-only mặc định; write tách riêng | S13 | |
| Command allowlist | S3, S9 | |
| Timeout và giới hạn tài nguyên | S4, S5 | |
| Không lộ secret | S6, S7 | |
| Audit mọi call | S8 | |
| Text trong repo là untrusted | S12 | |

## 5. Thứ tự thực hiện và phụ thuộc

```text
D1 (B10) ──> M1-W11-2 tune ──> freeze ranking config ──┐
         └─> M2-W11-2 structural (cycle không giả)      │
M2-W11-1 api ──> M2-W11-3 evidence (V11 giữ hash) ──> A3.json ──┤
D6/D7/D8 ──> M3-W11-1/2/3 ──> S1–S13 xanh                       │
D13/D14 ──> M3-W12-1                                             │
D16 ──> dry-run 2 lần (cổng harness ổn định) ───────────────────┤
                                                                 v
             W12 GPU: A1/A2 rerun + A3 × 25 dev; mutant pool ──> bảng R1, P1, V1, V2, I1
                                                                 v
                                             M3-W12-2 protocol freeze (D12, D15)
```
