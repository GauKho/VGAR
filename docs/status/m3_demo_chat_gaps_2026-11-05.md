# Demo chat trước hội đồng: kịch bản chính và lỗ hổng (05/11/2026)

Hướng đã chọn (05/11): **(a)** giữ `langchain-mcp-adapters` + `langchain.agents.create_agent`, sửa các lỗ hổng của `vgar chat`.
Mục đích: một AI agent chat được qua MCP, chạy Qwen thật khi demo. Không tự viết lại adapter MCP.

Tham khảo: [MCP build-server (2026-07-28)](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server),
[ReAct loop](https://www.mindstudio.ai/blog/what-is-react-loop-ai-agent-reasoning).
Thiết kế demo gốc: brainstorm 02–03/11 (demo trên repo code thật, hệ thống tự dựng task).

---

## 1. Kịch bản demo chính

Repo demo: `D:\kltn\vgar-demo-shop\vgar-demo-shop` (shop/: cart, catalog, checkout, discounts, money, shipping, tax).
Model: Qwen3-4B-Instruct-2507 thật cho cả agent và generator. Fake chỉ dùng cho CI.

| Bước | Người demo làm | Hệ thống / agent làm | Màn hình phải thấy |
|---|---|---|---|
| 0 | Chạy `pytest` trong repo demo | — | Một vài test đỏ (do nhóm viết sẵn, đã khoá) |
| 1 | Mở chat, chỉ đưa **đường dẫn repo** | **Tự dựng task (repo intake)**: chạy baseline pytest → test fail là ứng viên FAIL_TO_PASS, test pass là PASS_TO_PASS; file được sửa = mọi `.py` không phải test; thư mục test bị khoá; `revision` = git HEAD; dựng graph repo. Không có JSON viết tay. | Tóm tắt task vừa dựng |
| 2 | Hỏi: "lỗi nằm ở file nào, hàm nào?" | **Chỉ đọc.** Agent dùng các tool graph và repository để lần từ test fail tới file/hàm, không được dùng tool sửa code | File + hàm + bằng chứng (dòng code, test liên quan) |
| 3 | Gõ: "hãy sửa lỗi X" | Agent chọn test mục tiêu trong số test fail (ghi vào bằng chứng) → generator V11 sinh diff → áp bản vá → chạy test → verify. Fail thì mở run mới và thử lại, **tối đa 3 lần** (ReAct) | Từng bước Thought/Action/Observation, kết luận của engine M2 (PASS/FAIL) |
| 4 | — | Bug thứ hai không được nhắc trong prompt giữ nguyên | FAIL→FAIL "ngoài phạm vi" |

Câu cần nói khi bảo vệ:
- Model **thấy** test fail, khác SWE-bench (test bị ẩn). Số liệu luận văn chỉ lấy từ SWE-bench; repo demo chỉ dùng để demo và chạy nghiệm thu trước khi bảo vệ.
- Kết luận do engine M2 đưa ra, không phải do agent tự nhận.
- Agent không tự viết test tái hiện lỗi: đưa vào Hạn chế / Hướng phát triển (đã chốt 03/11).

### Việc chuẩn bị repo demo (còn treo từ 03/11, chưa làm tính tới 05/11)
- [ ] `git init` repo demo (hiện chưa phải git repo, mà intake cần git HEAD).
- [ ] Đổi tên `tests/test_x.py::test_bug`.
- [ ] Thêm test chặn kiểu sửa ăn gian: đổi `min_order` của SAVE10 thành `499_999` vẫn pass hết test. Đề xuất `discount_amount(2_000_000, "SAVE20") == 400_000`.
- [ ] Đảm bảo có ≥2 bug độc lập ở các file khác nhau, mỗi bug có test fail riêng.

---

## 2. Lỗ hổng của `vgar chat` hiện tại

Đối chiếu với kịch bản trên và hai tài liệu tham khảo. Mức: **C** = chặn demo, **H** = cao, **M** = trung bình, **L** = thấp.

| # | Mức | Lỗ hổng | Bằng chứng | Hướng sửa |
|---|---|---|---|---|
| G1 | C | **Chưa có repo intake.** `vgar chat` bắt buộc `--task` JSON. JSON này còn chứa sẵn `issue_text` (mô tả luôn lỗi) và `allowed_source_paths` (chỉ luôn file), nên bước 2 không chứng minh được agent tự tìm ra lỗi | `cli.py` subparser `chat --task` (required); `examples/m2/tasks/single_file_login.json` | Bước intake dựng task từ repo như mục 1, bước 1 |
| G2 | C | **Mỗi phiên chỉ áp được một bản vá.** `apply_patch` chỉ chạy khi run ở phase `prepared`; test fail xong thì không áp được bản vá mới, nên vòng quan sát → hành động lại bị gãy | `src/vgar/mcp/servers/repair_server.py:31-32` (`REQUIRED_PHASE`) | Mở run mới cho mỗi lần thử như `AgentRepairHost` (`tool_agent.py:31` `MAX_ATTEMPTS = 3`) |
| G3 | H | **Agent tự viết diff** trong tham số tool, giới hạn 512 token. Model 4B dễ cắt cụt hoặc escape JSON sai. `solve --agent` đã cố ý tránh việc này | `src/vgar/agents/chat.py:33`; `src/vgar/config/settings.py:64`; so với `tool_agent.py:38` (`NoArgs`, generator V11 giữ diff) | Chat dùng chung `AgentRepairHost` / tool `generate_patch` (kế hoạch thống nhất chat từ 02/11, chưa có trong code) |
| G4 | H | **Không có ranh giới chỉ đọc.** Agent nhận `run_dir` và lời dặn sửa bằng `repair_apply_patch` ngay từ lượt 1, nên có thể sửa code khi người dùng chỉ hỏi "lỗi ở đâu" | `chat.py:24-25` (`CHAT_SERVERS` gồm `repair`, chỉ ẩn `repair_get_task_context`); `chat.py:28-33` | Lượt hỏi chỉ đọc chỉ có tool graph/repository; tool sửa chỉ mở ở lượt sửa |
| G5 | M | **14 tool** cho model 4B. Spike chọn tool trước đây tốt nhất chỉ 2/3 | `chat.py:24`; `vgar tools` liệt kê 11 tool + 4 tool repair − 1 tool ẩn | Rút bộ tool theo từng lượt |
| G6 | M | **Ngữ cảnh phình ra.** Mỗi lượt gửi lại toàn bộ lịch sử + schema tool, không cắt hay tóm tắt (lỗi "context growth" trong bài ReAct) | `chat.py:91` | Cắt hoặc tóm tắt kết quả tool cũ giữa các lượt |
| G7 | L | **Không thấy bước "Thought".** Instruct-2507 không có chế độ suy nghĩ; trace chỉ có Action/Observation | `configs/m2/demo.json` `model_id` | Prompt yêu cầu một dòng lý do trước mỗi lần gọi tool, ghi vào trace |
| G8 | L | Docstring CLI ghi sai cách gọi | `src/vgar/cli.py:10` (`vgar chat --repo REPO`, thực tế là `--task`) | Sửa khi làm G1 |

Phía MCP server (đối chiếu tài liệu build-server):

| # | Mức | Ghi chú |
|---|---|---|
| S1 | L | Tài liệu 2026-07-28 dùng Python SDK 2.0 (`mcp.server.MCPServer`). Repo khoá `mcp<2` và dùng `mcp.server.fastmcp.FastMCP`, vì `langchain-mcp-adapters==0.3.2` yêu cầu `mcp<2.0.0`. Với hướng (a) thì chấp nhận; ghi rõ trong luận văn |
| S2 | M | Server mới chỉ chạy với client của repo. Nên thử kết nối từ MCP Inspector hoặc Claude Desktop để chứng minh đúng chuẩn MCP (hội đồng dễ hỏi) |
| S3 | L | `configs/mcp.yaml` không được code nào đọc; `src/vgar/mcp/client.py` ghi cứng lệnh khởi động server |

Phía server đã đúng hướng dẫn: tool khai báo bằng `@mcp.tool()` có type hint và docstring, chạy stdio, không `print()` ra stdout, lỗi trả theo định dạng thống nhất có mã lỗi, có audit, thư mục do host cấp.

Phía ReAct đã có: giới hạn số lần gọi tool (`core.py:87` `ToolCallLimitMiddleware`) cùng `recursion_limit`; host tự gọi `repair_verify_patch` khi agent không verify; tool lỗi trả lại thông báo kèm mã lỗi; trace v2.

---

## 3. Bước tiếp theo
1. Viết spec "repo intake + chat thống nhất" (G1–G4 trước, sau đó G5–G7), theo `docs/superpowers/specs/`.
2. Code sau đợt chốt W12. Không đụng các đường chạy thí nghiệm A1–A3.
3. Nhóm chuẩn bị repo demo theo checklist ở mục 1.
