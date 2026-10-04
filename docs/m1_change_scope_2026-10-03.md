# Phạm vi thay đổi M1 và ảnh hưởng M2/M3 — 03/10/2026

Đối chiếu working tree của `D:/KLTN/VGAR` với base commit
`2491a047638c183a6d6adee41c8a8f79b8b9020d` trên branch tích hợp.
Kết luận chỉ áp dụng cho đợt làm việc hiện tại; không suy ra hoạt động của
thành viên khác, branch khác hoặc trước commit gốc.

## Code riêng của M2/M3

| Phần | Trạng thái trong đợt làm việc |
|---|---|
| M2: src/vgar/repair; contracts/repair.py, evidence.py; tests/m2, fixtures/m2; hai scripts M2 | Không sửa, thêm hoặc xóa |
| M3: src/vgar/mcp, agents, models, config; cli.py; configs; run_agent và smoke scripts | Không sửa, thêm hoặc xóa |
| DTO query/error: contracts/graph.py, error.py; M3 tests | Không sửa, thêm hoặc xóa |

Code M1 được sửa/thêm ở builder, grounding, context re-export, tests và scripts
của M1. README/docs/artifacts bổ sung bằng chứng và handoff của M1.

## Phần dùng chung có thay đổi

| File/phần | Thay đổi | Ảnh hưởng consumer |
|---|---|---|
| src/vgar/contracts/schema.py | Cho phép CONTAINS Test → Function/Class | Graph chứa helper/nested class trong test được validate; không đổi node/edge fields |
| src/vgar/contracts/context.py | D08: reject Windows drive paths, được người dùng duyệt 03/10 | M2/M3 nếu validate context với C:/... hoặc C:... sẽ nhận validation error; relative POSIX vẫn hợp lệ |
| src/vgar/graph/context.py | Re-export shared class thay vì định nghĩa bản sao | Import cũ còn hoạt động; cùng class/validators cho producer và consumer |
| pyproject.toml và egg-info metadata | Tree-sitter 0.26.0 → 0.25.2 theo yêu cầu người dùng | Dependency chung thay đổi khi cài môi trường; đã cài vào venv Windows M1, không tự cập nhật mọi venv |
| Output graph của M1 | Sửa lexical resolution, dedup TESTS, resolver-profile trong snapshot hash | Consumer có thể nhận edges/counts/graph_version khác khi rebuild; API/DTO query giữ nguyên |

Shared validators, dependency và dữ liệu graph đầu vào có ảnh hưởng gián tiếp
đến M2/M3 như bảng trên, dù code riêng chưa bị chỉnh.

## Các chặng tiếp theo

Cập nhật Milestone 3 ngày 03/10: đã thêm retrieval API/CLI/tests nội bộ M1;
shared contract files giữ nguyên so với lúc bắt đầu chặng này, code riêng M2/M3
không đổi. Tokenizer-only provisioning thực hiện riêng sau người dùng duyệt;
runtime 0.22.1 nằm ở D:/KLTN/M1/tokenizer-runtime, assets download trong Git-ignored
artifacts/m1/tokenizers. .gitignore thêm đúng thư mục cache M1. CLI/counter M1
đã nghiệm thu offline, không sửa model loader/prompt/config M3 hoặc tải weights.
Xem [tokenizer acceptance/scope audit](m1_tokenizer_acceptance.md).

Cập nhật Milestone 2 ngày 03/10: đã thêm task_overlay API/CLI/tests ở M1 và
mở rộng grounding; dùng Issue/MENTIONS/REPRODUCES hiện có. Không thêm shared
contract changes, không sửa code riêng M2/M3. Xem [checkpoint](../artifacts/m1/task-grounding/manifest.json).

- M1 đã triển khai task overlay, traversal/ranking, source-verified snippets và packing
  trong phần Graph & Retrieval, theo các nguyên tắc đã duyệt.
- D09 đã duyệt thêm cấu hình tokenizer/revision/8000 snippets cho M1; chưa thêm tokenizer vào model loader, thay prompt,
  sửa agent/config hoặc expose MCP tool.
- Nếu cần chỉnh code riêng M2/M3, public API/error/DTO, sẽ trình rõ file và ảnh
  hưởng để người dùng duyệt trước. M2/M3 integration là follow-up bàn giao.
- Người dùng duyệt baseline M1 chưa được ghi thay cho consumer sign-off.

## Bằng chứng

- [Scope audit theo đường dẫn](D:/KLTN/reports/vgar_m1_20261003/approved_scope_audit.json):
  không có thay đổi trực tiếp ở các vùng M2/M3 được kiểm.
- [49/49 M1 tests](D:/KLTN/reports/vgar_m1_20261003/m1_tests_approved.txt) gồm
  graph validation, SQLite/query, context fixture round trip và regression paths.
- [Context schemas sau duyệt](D:/KLTN/reports/vgar_m1_20261003/context_schema_approved.json)
  bằng cả ba schemas trước thay đổi. JSON schema không thể hiện thay đổi behavior
  của custom validator; regression test là bằng chứng cho D08.

Chưa commit/push hoặc gửi tài liệu cho thành viên khác. Chưa dùng kết quả M1
để tuyên bố toàn bộ repair/agent/model pipeline đã được kiểm thử.
