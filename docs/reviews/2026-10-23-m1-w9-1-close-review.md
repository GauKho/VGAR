# Review và nghiệm thu M1-W9-1 — 23/10/2026

**Kết luận: APPROVED về kỹ thuật; M1-W9-1 hoàn thành theo điều kiện nghiệm thu
đã được người dùng điều chỉnh.** Người review: Codex theo ủy quyền của người dùng
đảm nhiệm M1/M2. Không đại diện phê duyệt của M3.

## 1. Quyết định áp dụng

Người dùng đã yêu cầu “Review và đóng M1-W9-1 theo quyết định của người dùng”:
ủy quyền Codex review kỹ thuật và miễn review M3 cho riêng M1-W9-1. Quyết định
được ghi thành amendment §6.4 trong plan M1 ngày23/10 ở New_task.
Không mở rộng ngoại lệ sang task khác hoặc sửa roadmap chung của nhóm.

Artifact cố định: `src/vgar/contracts/impact.py` và `docs/impact_report_schema.md`.
Chưa commit/push/merge, không chứng minh thời hạn hai ngày đầu. Checkpoint/status
đóng task local theo ngoại lệ; quy trình merge GitHub vẫn có trạng thái riêng.

## 2. Phiên bản đã review

HEAD: `525f9936a3c0abe5ea056c532c1f889ce84627a7`, có thay đổi local.

| Artifact | SHA-256 bytes (không prefix) |
|---|---|
| src/vgar/contracts/impact.py | b1b3621103279373a98204dc2f84cba42ac3527b0f6b464316a1a1779e9e5884 |
| tests/test_impact.py | 141c894554a53444c3cb0e953f86ba687eccec17fe4b460cd3edab2faaab8d29 |

Hashes schema docs/status/plan sau cập nhật nằm ở `delivery_check.json` trong
evidence mới. Source/test giữ nguyên phiên bản đã kiểm; docs sửa riêng phần
nghiệm thu, không đổi API hoặc ví dụ JSON.

## 3. Bảng review theo góc nhìn M2

| Nội dung | Kết luận và ranh giới |
|---|---|
| changed / unmapped | Có node/path/range/basis/spans, reason rõ; duplicate node/span bị chặn. Producer W9-2 chịu trách nhiệm coverage raw diff và graph membership |
| Coordinates | Range baseline UTF-8 end-exclusive, nonempty; old/new count riêng, zero-count boundary hợp lệ, bool/negative/string bị từ chối theo contract |
| Identity | Graph/source/patch hash tách biệt; source chỉ inventory Python. DTO không tự attest source/Git hoặc xác thực chữ ký |
| impacted / risk | NOT_COMPUTED và unavailable features rõ; không biến empty items thành bằng chứng không có ảnh hưởng hoặc risk=0 |
| limits | PARTIAL cần lý do; truncated không được COMPLETE. COMPLETE mapping có thể chứa unmapped, không phải repair success |
| Transport | JSON roundtrip và canonical ordering đạt; canonical hash graph giữ order arrays. Không thay ContextPayload/public DTO khác |
| M2 consumption | Đủ contract cho producer tuần9; không làm thay parser/apply/verification, không đòi model/tokenizer để validate DTO |

Không phát hiện blocker kỹ thuật mới. Lỗi LiteralFalse nhận số0 đã được sửa và có
regression0/0.0 từ phiên triển khai; phiên review này kiểm lại tests, không sửa code.
Review không chứng minh reverse impact/risk tuần10, runtime mapping hoặc MCP đã chạy.

## 4. Evidence kiểm chứng mới

Root: `results/m1/w9/m1-w9-1/20261023-close-review/` (ngoài Git).

| Check | Kết quả | Record |
|---|---|---|
| Schema | 45 PASS, exit0, pytest0.37s | schema.json + schema.junit.xml |
| Selected regression | 167 PASS, 2 deselected, exit0, pytest35.23s | regression.json + regression.junit.xml |
| Ruff source/tests | PASS, exit0, Ruff thực có0.16.5 | lint.json |
| Source preservation / docs QA | Xem delivery_check.json, phải PASS trước bàn giao | before.json, after.json, delivery_check.json |

Các JSON commands lưu argv/cwd/interpreter, raw stdout/stderr, exit, UTC và
monotonic duration; `.stdout.log`/`.stderr.log` để đọc riêng. 45 schema tests nằm
trong167, không cộng thành212. Hai exclusions giữ nguyên:
`test_baseline_to_repair_and_static_evidence`,
`test_verify_patch_equals_tests_then_completion`, cần assets tokenizer chưa provision.
Full repository suite/qualification vẫn NOT_RUN, không gọi selected tests là full PASS.

## 5. Điểm kết thúc

Cập nhật status M1, schema docs, handoff review cũ và append PROGRESS; source M2
và mọi thay đổi ngoài phạm vi được bảo toàn. Không bắt đầu W9-2 hoặc task khác.
