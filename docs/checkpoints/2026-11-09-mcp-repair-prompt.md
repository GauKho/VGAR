# Checkpoint L6-4 — MCP repair prompt — 09/11/2026

## Baseline và phạm vi

Chỉ L6-4 theo proposal §10.4 và Final_Task implementation plan. Dirty branch `m2/w12-a3-verifier-d15-20261105`, HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`. Không commit/push/install/model/Docker/campaign hoặc task khác.

Artifact UTC `results/mcp_server/prompts/20261108T181049Z-template/`; ngày làm việc Asia/Saigon09/11. Baseline chụp2.369 hashes gồm tracked/untracked, index và seals H1/L6-1/L6-2/L6-3/L6-5; giữ status/staged/unstaged diff. V11/policies/DB/report cũ nằm trong protected inventory.

## IN_PROGRESS — điểm khôi phục

- Đã thêm renderer thuần hai user messages, đúng7 bước; public prompt3 required string arguments. Failing tests dùng JSON array string, budget dùng positive ASCII decimal, không đặt default token budget.
- Frozen lower-only byte limits65.536 input/rendered UTF-8, optional trusted context redaction, no env/source/gold/provider/tool/grant access. Central serve_prompt audit counts/templatehash, không raw issue/tests/prompt; audit failure không return success.
- Golden prompt fixture viết riêng trước implementation; RED45 missing-feature failures, GREEN45 unit. Native SDK unknown prompt echo được tái hiện qua STDIO3 RED cases, sau đó safe public get_prompt boundary trước SDK validation có GREEN49 gồm wire/optimized.
- Runtime controller RED2 cases chứng minh listing-only/missing/FAILpromptgate từng bị coi PASS; worker/controller đã kiểm thật get_prompt/schema/messages, inventory tests cập nhật1 prompt graph/0 others. Chưa sửa oracle H1 hoặc sealed artifacts.
- Technical reviewer read-only đang xem whole owned change. Gate tổng hợp/regression/wire/preservation còn chờ; kiểm logs/XML thực trước khi chạy lại. Không coi mốc này là DONE.

Final results sẽ append sau khi nhận đủ receipts.

## Kết quả cuối — DONE kỹ thuật L6-4

- SDK2 release **266 PASS,0skip/fail/error**,58,30 giây: 55 prompt/controller cases mới cùng211 gates hiện có. Legacy **102 PASS +1skip cũ**,85,79 giây. Các nhóm overlap, không cộng thành unique tests.
- Compatibility wire **16/16 PASS**; graph prompt_gate PASS qua SDK2 modern2026-07-28/legacy2025-11-25 và SDK1 cross/native legacy. Worker gọi get_prompt thật và so oracle; controller không nhận listing-only/missing/FAILgate. Ba prompt-positive sessions và hai raw-protocol cases nằm trong SDK2 gate, không gọi model/provider.
- Review phát hiện SDK structural parameter rejection xảy ra trước application handler: SDK1 từng echo raw validation data vào stderr. Guard đã generic hóa warning, ghi riêng protocol_reject; SDK2 generic protocol error an toàn. Không bịa prompt_render khi renderer chưa chạy hoặc correlation chưa được cấp. Raw regression gửi tiếp valid request để chứng minh session còn hoạt động. Ruling này phân biệt transport rejection với render attempt, không mở rộng thành transport proxy hoặc agent host.
- Minor leading-zero budget được normalize trước int parse; input5000zeros+1 render thành1. Không tăng budget/default hoặc sửa Python global integer settings. Review đã kiểm lại hai findings bằng temp-only reproductions; không sửa repo/DB.
- Ruff scoped và pip check PASS. Process inventory sau gates không có MCP/fixture worker còn sót; CIM chỉ đọc cần escalation vì sandbox, không kill process. V11/policy/DB/sealed history được kiểm trong final preservation.
- `seal_prompts.py` kiểm actual XML/commands/wire/template hash/package inventories/HEAD/index/staged/append history trước final status và checksums. Chỉ cập nhật code/tests/docs của L6-4, không install/model/Docker/campaign/commit/push.
- Graph1 prompt, others0; tools20/resources8 canonical+alias giữ nguyên. Provider dependencies của L6-2/L6-3 không đổi; Inspector/Claude Code và workflow thực vẫn L6-8. **Dừng sau L6-4.**
