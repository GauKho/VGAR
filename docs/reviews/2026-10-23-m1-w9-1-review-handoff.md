# Bàn giao review contract ImpactReport — M1-W9-1

Ngày chuẩn bị: 23/10/2026. **M2: PENDING; M3: PENDING.**
Đây là yêu cầu review, không phải receipt phê duyệt; không ký thay thành viên.

**Cập nhật nghiệm thu 23/10/2026:** trạng thái PENDING trên là lịch sử trước quyết
định mới. Người dùng đảm nhiệm M1/M2 đã ủy quyền Codex review và miễn M3 riêng
task này. [Receipt hiện hành](2026-10-23-m1-w9-1-close-review.md) thay gate chờ
review ban đầu; M3 không được ghi APPROVE. Checklist bên dưới giữ để tham khảo.

Đọc [schema](../impact_report_schema.md), `src/vgar/contracts/impact.py`,
`tests/test_impact.py` và spec `VGAR_W9_W16_Deliverables.md` phần M1-W9-1.
Kết quả kiểm chứng/hashes có tại evidence index trong status M1.

| Người review | Nội dung cần xem | Điểm cần trả lời |
|---|---|---|
| M2 | ChangeSpan/zero-count boundary, baseline ranges, parser limits, hash identities | Có đủ đầu vào để verification/evidence phân biệt changed/unmapped và chưa tính impact/risk? |
| M3 | JSON serialization, statuses, completeness, consumer/MCP tương lai | Naming và NOT_COMPUTED có rõ, transport có giữ provenance mà không suy PASS? |
| Cả hai | Giới hạn W9 vs W10 và producer validation | Có chấp thuận DTO draft này trước khi W9-2 dùng không? |

Các quyết định kỹ thuật để review:

- Strict models riêng cho impact ranges; giữ nguyên ContextPayload và parser hiện hữu.
- Một changed entry/node; duplicate bị từ chối, caller gộp spans trước.
- COMPLETE nghĩa xử lý đủ mapping input, vẫn có thể có unmapped; PARTIAL phải nêu lý do.
- Impact/risk chưa tính chỉ NOT_COMPUTED; không hỗ trợ computed payload cho đến W10 review.
- Source hash chỉ inventory Python, không bao toàn repo. Hash transport không là chữ ký xác thực.
- Producer W9-2 phải kiểm graph/source/raw patch thực tế; DTO chỉ kiểm cấu trúc.

Mẫu trả lời (chưa được điền):

```text
Reviewer / vai trò:
Ngày thực review:
SHA-256 code + schema docs hoặc commit đã xem:
Kết luận: APPROVE / REQUEST_CHANGES
Phần cần chỉnh / điều kiện:
Evidence / đường dẫn phản hồi:
```

Không yêu cầu chạy LLM hoặc SWE-bench để review schema. Có thể tự chạy lệnh
pytest trong schema docs; kết quả human review ghi đúng ngày, không hồi tố target
“hai ngày đầu tuần”. Chưa được dùng agent review làm phê duyệt M2/M3.
