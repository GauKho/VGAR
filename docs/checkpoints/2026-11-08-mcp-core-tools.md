# Checkpoint L6-2 — 08/11/2026

## Baseline và phạm vi

HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`, nhánh `m2/w12-a3-verifier-d15-20261105`. Tiếp tục trên dirty checkout theo chỉ dẫn người dùng; không commit/push/stash/reset/clean. Không model/Docker/campaign hoặc task khác.

Artifact mới: `results/mcp_server/tools/20261108T141511Z-adapters/`. Baseline chụp 1.768 files tracked/untracked và sealed artifacts H1/L6-1/L6-5; git status, staged/unstaged diff trước triển khai. Không cài hoặc nâng package, không sửa DB tracked. PROGRESS/contract/status chỉ append.

## Triển khai và bằng chứng trung gian

- Thêm DTO/ports/CoreTools, 5 server registrations và allowlist. Inventory 20 tools, đủ 11 core, giữ 3 resources/0 prompts.
- Strict frozen DTO, exact UTF-8 hashes, immutable host registry, synthetic/production isolation, provider/context/result binding, evidence disk verification, bounded path/traversal, fail-closed ranking và private test lifecycle.
- Legacy depth 1/payload/required arguments giữ nguyên. Depth >1 không còn giả support bằng echo; phải có provider. Host factory cấu hình thì cả legacy query cũng được bind, actual backend snapshot phải khớp.
- RED đầu 2 failed vì thiếu module/tools. Behavior RED còn import errors vì module chưa có, không gọi đó là reproducer logic. Sau triển khai gate tăng dần; giữ tất cả log/XML.
- RED riêng tái hiện bool score/thiếu rank evidence, same-thread async lock reentry, timeout thiếu receipt, queued source drift, legacy factory bypass, cleanup fake/missing workspace, ignored cache và xóa lease data.
- Independent technical review phát hiện các lỗi trên, đã có regression và fix. Cleanup kiểm đầy đủ cả cache/empty dirs, build bảo toàn lease tuyệt đối; test chỉ xóa candidate subtree được host bind. Source kiểm lại dưới khóa trước grant/provider. OS lock polling không block event loop.
- Hai test inventory legacy được cập nhật cho core additions; giữ tên test S13 để security checklist cũ còn resolve được. Không sửa checklist hoặc thêm skip/xfail. Một lần gate bắt lỗi tên tham chiếu; giữ failed log.

## Khôi phục / dependency

Đọc final summary/preservation trước khi làm tiếp, không chạy lại setup hoặc ghi đè artifact cũ. Xem [tools runbook](../mcp_server/tools.md) về interface/bootstrap/limits và giới hạn synthetic. Production default chưa có build/path/traversal/verification/ranking/tests providers; không tuyên bố all-tools production READY. Không cần chờ human review TV2/TV3.

Final gate và trạng thái sẽ được bổ sung sau khi nhận đủ receipts.

## Kết quả cuối — DONE kỹ thuật adapter / WAITING_PROVIDER

- SDK2 final **139 PASS**, không skip/fail/error, 36,97 giây; gồm **61 test adapter/core/wire mới** và 78 security/runtime gates hiện có. Legacy **100 PASS, 1 skip cũ**, 89,33 giây; regression cuối cho pinned binding **56 PASS, 1 skip cũ**, 21,60 giây. Các nhóm có overlap, không cộng thành unique tests.
- Compatibility wire **16/16 PASS**: SDK2 modern4 + legacy4, SDK1→SDK2 legacy4, SDK1→SDK1 legacy4. Actual protocol: 2026-07-28 hoặc 2025-11-25. Thêm 4 core synthetic STDIO cases trong SDK2 gate, không phải production provider experiment.
- Ruff scoped và pip check PASS. Process inventory sau gates không có MCP server/fixture worker sót; truy vấn CIM chỉ đọc cần thoát sandbox, không kill process hoặc sửa hệ thống.
- Review độc lập đã kiểm lại các cleanup bypass và xác nhận đóng; source revalidation dưới khóa, legacy context factory và nonblocking OS contention cũng đã được kiểm lại. Pinned/no-latest guard có regression RED/GREEN.
- `seal_tools.py` xác minh XML, wire receipts, package inventory không đổi, HEAD/staged diff không đổi, file hashes và append-only history rồi mới cập nhật PROGRESS/contract/status. `summary.json`, `preservation.json`, `artifact_hashes.json` và `deliverable_hashes.json` là hồ sơ khôi phục cuối.
- Chưa có provider production mới, không claim rich graph/algorithm hoặc build READY. Không Docker/model/campaign/install/commit/push. **Dừng sau L6-2.**
