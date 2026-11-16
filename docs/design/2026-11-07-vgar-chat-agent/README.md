# Biểu đồ dự kiến: chatbot `vgar chat` sau thay đổi (06–07/11/2026)

Trạng thái: **đề xuất trong lúc brainstorm, chưa có spec duyệt, chưa có code.** Các con số trong mockup là giả định để
minh hoạ.

Mở trực tiếp bằng trình duyệt (file HTML độc lập, không cần server):

| File | Nội dung |
|---|---|
| `01-chat-terminal-mockup.html` | Mockup terminal của một phiên `vgar chat --repo` trên repo demo. Hai mức chi tiết; **người dùng chọn bản A (chi tiết)**. Mỗi bước gắn nhãn phần lý thuyết proposal (§6.6, §9.2, §9.3, §8.5, §10.5) |
| `02-roles-gpt-qwen-ft.html` | So sánh hai cách chia vai. B: Qwen-FT viết hướng dẫn cho GPT (không đề xuất). A: GPT điều phối, Qwen-FT chỉ sinh diff V11 (đề xuất) |
| `03-architecture-after-change.html` | Kiến trúc 10 tầng sau khi thêm GPT (`langchain_openai`) và Qwen-FT; màu block: mới / sửa / giữ nguyên / cloud; ghi file trong code |

Bản gốc dạng fragment nằm ở `.superpowers/brainstorm/249-1793980243/content/`. Link
`http://localhost:60638/?key=…` của phiên brainstorm **chỉ sống khi server còn chạy** (tự tắt sau 4 giờ không dùng),
nên dùng các file ở thư mục này thay cho link.

## Các quyết định đã chốt trong brainstorm

1. Chatbot là `vgar chat --repo PATH`, chạy trong terminal, giao diện theo bản A của mockup.
2. **Điều phối:** GPT qua `langchain_openai` ở chế độ chính; Qwen3-4B gốc ở chế độ dự phòng (`--orchestrator qwen`).
3. **Sinh diff:** luôn là Qwen-FT (Qwen3-4B gốc + LoRA V11), qua tool `generate_patch`. Host dựng prompt V11; người điều
   phối không thấy và không sửa được diff.
4. **Kết luận:** do engine M2 đưa ra, kèm evidence bundle.
5. **Batch A0–A3:** giữ Qwen gốc đã ghim, không agent, không GPT. Hiệu quả fine-tune đo bằng thí nghiệm riêng (cùng
   bundle, cùng prompt V11).

## Còn mở

- Chuyển từ lượt chỉ đọc sang lượt sửa: bằng lệnh rõ ràng (ví dụ `/fix`) hay để model tự hiểu ý.
- Generator mặc định là Qwen-FT, hay có công tắc để demo so Qwen gốc với Qwen-FT trên cùng một lỗi.
- Bản fine-tune đã train xong chưa; context lúc train là "code gold + đoạn nhiễu" hay bundle graph của VGAR.
- File spec fine-tune `docs/superpowers/specs/2026-10-21-qwen3-v11-finetune-design.md` không có trong repo.

Liên quan: `docs/superpowers/specs/2026-11-06-m3-demo-graph-tools-design.md` (phần nền: tool graph), 
`docs/status/m3_status_synthesis_2026-11-06.md`, `docs/status/plan_3_weeks_defense1_2026-11-06.md`.
