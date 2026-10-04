# M1 contract decision log

Ngày tạo: 03/10/2026. Trạng thái ghi từ bằng chứng trong phiên làm việc;
**không có dòng nào là xác nhận của M2/M3 khi chưa nhận được xác nhận đó**.

| ID | Nội dung | Trạng thái | Nguồn xác nhận / bước còn lại |
|---|---|---|---|
| I01 | Shared context class consolidation, M1 re-export compatibility | Implemented and verified | 49 M1 tests; 3 JSON schemas before/after equal; public fields unchanged |
| I02 | M1 task overlay và grounding mở rộng | Implemented and verified 03/10/2026 | 67 tests; full-repo no-Jedi/SQLite smoke; không thêm shared contract change; xem Milestone 2 report |
| I03 | M1 semantic retrieval/ranking/source checks/context packing | Implemented and standalone tokenizer acceptance verified 03/10/2026 | 95 tests; full-repo actual token API/CLI/boundary; shared contracts unchanged; dev quality và M2/M3 integration còn riêng |
| D01 | Tài liệu hiện hành của repo tích hợp nằm ở VGAR/docs; sibling giữ lịch sử | User approved 03/10/2026 | Người dùng: “được, tôi duyệt tất cả” |
| D02 | No public schema_version, graph_version chỉ định danh snapshot | User approved 03/10/2026 | Baseline hiện hành được duyệt |
| D03 | Giữ INHERITS và Test containment, TESTS dedup semantics | User approved 03/10/2026 | Existing graph regression tests; consumer review vẫn riêng |
| D04 | Giữ DTO tối thiểu, direct callers/callees, threshold 0.60 | User approved 03/10/2026 | Existing query contracts/fixtures |
| D05 | M1 là ContextPayload producer; M2 consumer, M3 transport/audit | User approved; consumer confirmation separate | Không tự sửa module M2/M3 |
| D06 | Shared definitions tại vgar.contracts.context; M1 re-export | User approved 03/10/2026 | I01 đã triển khai; shared contract không đổi shape |
| D07 | Giữ current error codes, lazy source/snapshot validation plan | User approved 03/10/2026 | Source checks triển khai ở milestone retrieval; chưa thêm public error |
| D08 | Reject Windows drive paths trong shared ContextItem validator | User approved; implemented and verified 03/10/2026 | C:/, drive-relative và UNC bị từ chối qua cả hai import; valid fixture giữ nguyên |
| D09 | Inject pinned token counter, snippet-only budget, whole-snippet baseline | Principles and concrete standalone M1 configuration user approved; verified 03/10/2026 | Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554, 8000 snippet tokens; assets local/hash verified; M3 model pin và total prompt allocation còn riêng |

## Điều kiện đóng Milestone 1

- [x] Literature/schema/manual-review lịch sử đã tìm thấy và được dẫn nguồn.
- [x] ContextPayload có một nguồn định nghĩa; import cũ còn chạy.
- [x] Validation tests và fixture round trip đạt, JSON schemas không đổi.
- [x] Hồ sơ đối chiếu và handoff sẵn để review.
- [x] Người dùng duyệt gói D01–D07 ngày 03/10/2026.
- [x] D08 được sửa và kiểm thử hồi quy đạt.
- [x] D09 thống nhất nguyên tắc; cấu hình cụ thể do model/runtime owner phối hợp chốt.
- [ ] Consumer xác nhận các điểm shared contract/ownership nếu nhóm yêu cầu.

**Kết luận:** Milestone 1 hoàn tất trong phạm vi M1 được người dùng duyệt.
Chưa ghi là freeze liên nhóm. Việc M2/M3 xác nhận handoff và cấu hình production
còn là follow-up riêng. Retrieval và official tokenizer accounting đã nghiệm thu
standalone M1 ở [Milestone 3](m1_tokenizer_acceptance.md); chưa là benchmark chất lượng.

Bằng chứng: [49 tests](D:/KLTN/reports/vgar_m1_20261003/m1_tests_approved.txt),
[schema sau duyệt](D:/KLTN/reports/vgar_m1_20261003/context_schema_approved.json),
[scope audit](D:/KLTN/reports/vgar_m1_20261003/approved_scope_audit.json).
