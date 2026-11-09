# Preflight L6-8 offline — 09/11/2026

## Baseline và phạm vi

Chỉ preflight, không cài/download package, model/agent, login/auth check, provider implementation, global host settings, commit/push hoặc full L6-8. Người dùng đã chọn offline trước. User từng stop sau đọc source, lần resume này không làm lại task L6-6/L6-7 đã seal.

Artifact `results/mcp_server/preflight/20261109T055933Z-offline/`; baseline2894hashes, HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`, branch `m2/w12-a3-verifier-d15-20261105`. Source/DB/report/requirements/old MCP seals và index được bảo vệ; PROGRESS/contract/status chỉ append khi final gates đạt.

## IN_PROGRESS — Điểm khôi phục

- `scripts/mcp_server/smoke_mcp.py`: mandatory --preflight, output jail/no overwrite, before/after source hashes/git snapshots, provider/owner dependency table, strict receipt consumers, client version/help only, independent readiness vs full integration.
- `_preflight_worker.py`: fixed actions probe/runtime/graph/clients, môi trường allowlist trước import/spawn; private authority/grant fixtures chỉ ở temp ngoài results, không export. Default registry observation + signed-context missing-grant denial; adapter control audit được phân biệt với operation writes.
- RED19missingCLI→GREEN19; RED2probe/schema→GREEN21; RED H1 rank prose signature được map exact sang public candidates array, giữ oracle immutable. Diagnostic read-only consumer của old SDK2 wire PASS. RED consumer bool-exit/duplicate-tools/missing-sidecars→đang hoàn thiện consumer; một intermediate test dùng profile rỗng đã sửa fixture để kiểm đúng missing sidecars.
- Config templates riêng Inspector modern/legacy và Claude Code; metadata TEMPLATE_NOT_EXECUTED. Không chọn Inspector version/latest, không dùng Claude session; Node22.22.2/npm10.9.7/Claude2.1.193 đã quan sát ở planning, execution sẽ ghi phiên bản thực lại.
- Còn chạy unit/consumer gates, real CLI preflight vào fresh subfolder (dự kiến exit2/PARTIAL), review read-only, regression/scoped lint/preservation, report/owner matrix và final seal. Không sửa source khi CLI đang chạy vì protected-input gate sẽ phát hiện drift.
- Mọi capability có implementation chưa bind khác với implementation thiếu. Default production mới vẫn thiếu binding/providers; real fixture verification không được dùng để đóng production/full L6-8. Client auth/session NOT_CHECKED_OFFLINE/NOT_RUN.

Python SDK2/legacy giữ nguyên. UTF8/-B/demo collection/no pytest cache/temp ngoài repo; sample DB chỉ thử trên copy. Dừng sau preflight.


## Final checkpoint — DONE kỹ thuật preflight; full L6-8 PARTIAL

Phục hồi từ mục này; phần IN_PROGRESS phía trên là lịch sử. Real CLI campaign-02 exit2/PARTIAL và local_checks PASS; 8 SDK2 wire lanes modern2026-07-28/legacy2025-11-25; hai real-static fixture chains cold/reuse/warm/read đã được independent consumer kiểm sidecars/DB/binding. Campaign-01 lỗi smoke lazy init được giữ nguyên, không phải lỗi production builder.

Final SDK2 50 PASS (31 cases preflight), legacy40 PASS+1skip cũ; Ruff/pipcheck PASS; không rerun399-suite L6-6 vì không sửa domain/runtime. Review3 findings đóng, RED6→GREEN31 có reproducer. Cli preservation2903 PASS. Final preservation và checksums nằm cùng artifact; PROGRESS/contract/status append-only, không có source cũ bị sửa trong task. Process inventory không còn MCP server/worker của preflight.

Đọc `campaign-02/dependencies.md` (20dòng) trước khi triển khai tiếp: implementation thiếu khác với đã có nhưng chưa bind. TV1 còn wiring/storage profile/external host; TV2 SC-1/layers/query/path/context/impact; TV3 evidence/verification/ranking/tests/baseline. Không cài Inspector hoặc chạy Claude/model/agent trong task; Claude version/help chỉ metadata, auth chưa kiểm. Các template chưa execute, fullchain production NOT_RUN. Không tự chuyển task.

Task mới tạo9file: scripts/mcp_server/smoke_mcp.py; scripts/mcp_server/_preflight_worker.py; tests/mcp_server/test_end_to_end.py; configs/mcp_server/{inspector-modern.template.json,inspector-legacy.template.json,claude-code.template.json,preflight-templates.json}; docs/mcp_server/runbook.md; checkpoint này. Chỉ append3file PROGRESS.md/docs/mcp_server/{contract.md,status.md}. Không dùng số PASS fixture để đóng WAITING_PROVIDER/WAITING_SCHEMA_PROVIDER.
