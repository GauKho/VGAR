# Checkpoint L6-3 — Resource serving — 09/11/2026

## Baseline và phạm vi

Chỉ L6-3; giữ dirty checkout, không commit/push/install/model/Docker hoặc task kế tiếp. H1 được tự quyết; không đặt human review TV2/TV3 làm blocker. Artifact UTC: `results/mcp_server/resources/20261108T173125Z-serving/` (ngày làm việc theo Asia/Saigon là 09/11).

Baseline HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`, branch `m2/w12-a3-verifier-d15-20261105`. 2.042 hashes gồm tracked/untracked, index và các artifacts H1/L6-1/L6-2/L6-5 đã seal; diff/status trước chỉnh sửa nằm trong artifact.

## IN_PROGRESS — điểm khôi phục

- Đã thêm resource DTO/capabilities, raw URI reader/strict decoding, factory subclass public read_resource override, 8 canonical +1 alias registrations. Không sửa SDK package hoặc tạo provider thật.
- Unit gate đầu 52 PASS; sau registration65 PASS trong nhóm runtime nhỏ; resource-only55 PASS sau audit/validation redaction fixes. Wire lần đầu3 failure do test đòi correlation cả malformed URI bị từ chối trước host factory; test đã sửa để đúng điều kiện khi có context, pending rerun.
- Audit reader thêm optional output_bytes, đo serialized JSON trước khi advance cursor; mặc định callers cũ giữ hành vi. Resource mới yêu cầu context/source/snapshot/evidence binding, cap UTF-8, public view/redaction và unavailable lỗi rõ.
- Test fixture provider/service là synthetic; STDIO fixture không chứng minh rich graph/provider production. Thiếu schema/component/task/baseline provider vẫn WAITING_PROVIDER.
- Đang bổ sung SQLite immutability, audit malformed/limits và chạy regression; chưa tuyên bố DONE ở mốc này. Đọc XML/log thực trước khi chạy lại hoặc sửa tiếp. Không regenerate artifacts đã seal.

Final results sẽ được bổ sung sau gates và preservation.

## Kết quả cuối — DONE kỹ thuật resource serving / WAITING_PROVIDER

- SDK2 final **211 PASS, 0 skip/fail/error**, 46,90 giây: 72 resource/unit/wire cases mới cùng 139 gates L6-2/L6-5/runtime hiện có. Legacy regression **100 PASS + 1 skip cũ** (Windows symlink unavailable), 89,23 giây; không cộng các nhóm overlap thành unique tests.
- Compatibility wire **16/16 PASS**: SDK2 modern4+legacy4, SDK1→SDK2legacy4, SDK1→SDK1legacy4. Actual protocols 2026-07-28/2025-11-25. Resource-positive wire riêng3 synthetic sessions (SDK2 modern/legacy, SDK1legacy) nằm trong SDK2 gate; không phải thí nghiệm provider production.
- Ruff scoped và pip check PASS; hai package inventories không đổi so với L6-2. Không cài/nâng package hoặc sửa lock/venv. Process inventory sau gates không có MCP/test worker sót; CIM chỉ đọc cần escalation do sandbox, không kill process.
- Independent review đã đóng3 Important findings: completed metadata redaction, protocol error secret redaction trước scope unwind, hard200 audit-record cap khi host đặt cao hơn. Review rerun6 targeted cases và3 temp-only reproductions, không sửa repo/DB. MIME regression tái hiện application/json khác defaultlegacy; khôi phục text/plain và final wire kiểm lại.
- Ordinary reads kiểm UTF-8 byte cap, duplicate/nonfinite JSON, source/snapshot/task/run binding và evidence file/hash. Baseline không tự chọn latest; serialized audit pagination không bỏ/lặp record. SQLite proof dùng temp copy và kiểm DB bytes/source unchanged.
- `seal_resources.py` xác minh XML/commands/wire/package/preservation trước append-only PROGRESS/contract/status và final checksums. Giữ cả RED/import errors/failed-wire tests để giải thích lịch sử, không thêm skip/xfail để che lỗi.
- Default production chưa có resource schema/component/task/baseline providers. Canonical subgraph/audit cần trusted host binding; ba legacy URI vẫn tương thích. **Dừng sau L6-3**, không L6-4/L6-6/L6-7, model/Docker/campaign/commit/push.
