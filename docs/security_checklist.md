# Security checklist MCP (bảng S1)

> M3-W12-3, spec `docs/superpowers/specs/2026-11-03-m3-w12-design.md` §5. Nguồn yêu cầu: bảng S1–S16 trong
> `docs/status/w11_w12_remediation_plan.md` và thiết kế `docs/superpowers/specs/2026-11-01-m3-w11-security-design.md`.
> Mỗi dòng trỏ tới test chứng minh. `tests/test_security_checklist.py` kiểm mọi test được trỏ tới còn tồn tại.

| ID | Yêu cầu | Cách làm | Test | Giới hạn còn lại |
|---|---|---|---|---|
| S1 | Không đọc/ghi ra ngoài root (path jail) | Mọi đường dẫn resolve trong root được lease; `..`, đường dẫn tuyệt đối, symlink ra ngoài bị từ chối với `PATH_OUTSIDE_ROOT` | `tests/test_mcp_legacy_servers.py::test_read_file_rejects_parent_escape`<br>`tests/test_mcp_legacy_servers.py::test_read_file_rejects_symlink_escape`<br>`tests/test_mcp_security.py::test_repair_rejects_run_dir_outside_run_root`<br>`tests/test_mcp_tool_contract.py::test_leased_root_and_inside` | Kiểm ở thời điểm gọi; không chặn được tiến trình con của pytest tự mở file |
| S2 | Root do server cấp, model không tự chọn | Root lấy từ `VGAR_LEASE_ROOT` / `VGAR_RUN_ROOT`; không có lease thì `ROOT_NOT_LEASED` | `tests/test_mcp_legacy_servers.py::test_read_file_without_lease_is_root_not_leased`<br>`tests/test_mcp_security.py::test_repair_without_run_root_is_root_not_leased`<br>`tests/test_mcp_security.py::test_runtime_repair_tools_lease_output_root` | Ai đặt được biến môi trường của server thì đổi được root |
| S3 | Selector pytest nằm trong allowlist của task | Từ chối selector ngoài scope, `..`, tuyệt đối, cờ `-k`, xuống dòng (`SELECTOR_REJECTED`) | `tests/test_mcp_legacy_servers.py::test_run_pytest_rejects_selector_outside_allow_list`<br>`tests/test_mcp_legacy_servers.py::test_run_pytest_rejects_selector_tricks` | Allowlist đúng bằng scope của task; test trong scope vẫn chạy code tùy ý của target |
| S4 | Timeout cứng, dừng cả cây tiến trình | Timeout do server đặt; hết giờ thì kill cả nhóm tiến trình | `tests/test_mcp_security.py::test_timeout_kills_grandchild`<br>`tests/test_mcp_legacy_servers.py::test_run_pytest_timeout_is_coded` | Tiến trình tự tách khỏi nhóm (double fork, `setsid`) có thể sống sót ngoài Docker |
| S5 | Output có trần ngay trong lúc chạy | Cắt khi vượt trần, có cờ `truncated` | `tests/test_mcp_security.py::test_output_is_capped_while_running` | Trần tính theo byte, không theo dòng |
| S6 | Secret không lọt vào audit, log hay lỗi | Một hàm redact dùng chung; audit chỉ ghi hash input | `tests/test_redaction.py::test_secret_never_reaches_audit_or_tool_error`<br>`tests/test_mcp_day5.py::test_repair_audit_hashes_inputs_not_raw_text` | Redact theo mẫu; secret có dạng lạ có thể lọt |
| S7 | Tiến trình con chỉ thấy biến môi trường được phép | Env con dựng theo allowlist | `tests/test_redaction.py::test_child_environment_is_allow_listed` | Allowlist do code đặt; file `.env` trong repo target không bị chặn |
| S8 | Audit mọi lời gọi, kể cả lỗi | Mỗi call một dòng audit với `request_id`, `status`, hash input | `tests/test_mcp_day5.py::test_repair_errors_are_audited`<br>`tests/test_mcp_tool_contract.py::test_every_call_is_audited_including_errors`<br>`tests/test_mcp_day5.py::test_repair_unexpected_exception_is_internal_error_envelope` | Audit là file local, không chống sửa (không ký) |
| S9 | Chỉ tool đã qua guard được công bố | Danh sách `PUBLIC_TOOLS`; tool lạ bị từ chối; không tool nào nhận root hay timeout từ model | `tests/test_mcp_security.py::test_unknown_tool_is_refused`<br>`tests/test_mcp_security.py::test_all_current_tools_are_public`<br>`tests/test_mcp_legacy_servers.py::test_no_tool_accepts_root_or_timeout_and_only_repair_writes` | — |
| S10 | Envelope và mã lỗi thống nhất | Envelope C4 `{status, data, error{code, message, retryable}, metadata}`; `retryable` suy từ bảng mã | `tests/test_mcp_day5.py::test_tool_errors_carry_known_code_and_retryable`<br>`tests/test_mcp_tool_contract.py::test_retryable_follows_the_code_table` | — |
| S11 | Id node có `/` và `:` đi qua resource MCP đúng | Client mã hóa phần trăm, server giải mã đúng một lần | `tests/test_w3_w4_graph_resources.py::test_node_resource_roundtrip_encoded_id`<br>`tests/test_w3_w4_graph_resources.py::test_node_resource_decodes_id_only_once` | — |
| S12 | Văn bản lấy từ repo được đánh dấu không tin cậy | Kết quả có `untrusted: true`; policy không đổi theo nội dung repo | `tests/test_mcp_legacy_servers.py::test_read_file_marks_content_untrusted`<br>`tests/test_mcp_day5.py::test_graph_tools_mark_repository_text_untrusted` | Cờ chỉ là tín hiệu cho model; không chặn được prompt injection hoàn toàn |
| S13 | Graph server không có tool ghi | Liệt kê tool graph, không tool nào ghi file | `tests/test_mcp_day5.py::test_graph_server_has_no_write_tool` | — |
| S14 | Agent chat không có tool ghi ngoài `repair_server` | Repository server chỉ còn `read_file`; ghi file chỉ qua repair server | `tests/test_mcp_legacy_servers.py::test_repository_server_has_no_write_tool`<br>`tests/test_mcp_legacy_servers.py::test_execution_server_tools` | — |
| S15 | `solve --agent` chạy trọn vòng trên task SWE-bench đã qua admission | Smoke chế độ fake, gold patch làm patch kịch bản; chạy tay trên máy M3 (Docker) | Không có test tự động: `docs/m3_w11_s15_smoke.md` (đánh dấu docker, chạy tay) | Chỉ là smoke trên 1 task |
| S16 | Đọc file có trần và đánh dấu không tin cậy | Cắt ở trần của server, có `truncated`; ngoài lease bị từ chối | `tests/test_mcp_legacy_servers.py::test_read_file_truncates_at_server_cap`<br>`tests/test_mcp_legacy_servers.py::test_read_file_reads_inside_the_lease` | — |

## Giới hạn

Checklist này **không phải an toàn tuyệt đối**. Ba giới hạn chính:

1. **pytest vẫn chạy code của target.** Guard giới hạn *lệnh nào* được chạy (argv cố định, `shell=False`, selector trong
   allowlist), không giới hạn *code trong test* làm gì. Cách ly thật dựa vào Docker của harness.
2. **Không có sandbox mạng hay hệ thống file ngoài Docker.** Khi chạy local (không Docker), tiến trình test có quyền
   của user đang chạy.
3. **MCP không có xác thực hay giới hạn tần suất.** Server chỉ dùng qua stdio trên máy local, không mở ra mạng.
