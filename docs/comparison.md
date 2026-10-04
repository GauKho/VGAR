# So sánh VGAR-main và bản dev VGAR

Ngày đối chiếu: **03/10/2026**, Asia/Saigon.

`main` có thêm phần tích hợp CLI/MCP/agent; bản dev có nhiều chức năng M1
Graph & Retrieval hơn. Bảng so sánh code hiện có trong hai thư mục, bao gồm
các thay đổi chưa commit của bản dev.

| Nội dung | VGAR-main — branch main | VGAR — bản dev hiện tại |
|---|---|---|
| **Trạng thái Git** | Commit `21b6f23`, working tree sạch. Có thêm 1 commit sau commit gốc của dev. | Commit `2491a04`, branch `integrated-w3-w4-m1-m2-m3-20260930`; các cải tiến M1 chưa commit. |
| **Graph builder** | Giữ implementation nền tảng W3–W4. | Đã sửa lexical shadowing, hàm/class lồng trong test, cạnh TESTS trùng và định danh snapshot theo resolver. |
| **Tree-sitter** | Vẫn pin **0.26.0**. | Pin **0.25.2**, theo bản sửa lỗi native crash đã kiểm chứng trước đó. |
| **Task grounding** | Chưa có implementation grounding mới. | Có tìm anchors từ path/line, traceback, symbol, pytest selector và literal route; xử lý ambiguity. |
| **Task overlay** | Chưa có module tạo overlay theo task. | Có Issue/MENTIONS/REPRODUCES, tách khỏi base graph; liên kết failing test dựa trên báo cáo đầu vào. |
| **Graph retrieval** | Chưa có pipeline retrieval tuần 5–6. | Có traversal giới hạn, callers/callees/import/test, ranking và rationale trong [retrieval.py](../src/vgar/graph/retrieval.py). |
| **Snippet và token budget** | Có model ContextPayload, chưa có producer retrieval hoàn chỉnh. | Kiểm source/hash/range, loại overlap, pack nguyên snippet và đếm bằng tokenizer Qwen đã pin; budget **8000 token**. |
| **Context contract** | Còn hai bộ định nghĩa context ở graph/contracts; validator chưa có sửa Windows drive paths. | Graph re-export shared definitions; đã bổ sung validation Windows drive paths. |
| **Graph node trả qua API** | Đổi sang wrapper `{"repo": {...}}`, thêm confidence/provenance/metadata qua adapter. | Giữ dạng phẳng với node_id, node_type, source_range… **Đây là khác biệt contract cần xử lý khi tích hợp.** |
| **Cấu hình runtime** | Settings lấy từ environment → .env → defaults; truyền Settings vào model/MCP/agent. | Settings chủ yếu đọc YAML. Bốn file YAML giống main, nhưng cơ chế sử dụng khác nhau. |
| **CLI chung** | Có vgar doctor, tools, index, run, chat trong [cli.py](../../VGAR-main/src/vgar/cli.py). | cli.py còn trống; có các script riêng cho M1. |
| **MCP đọc/sửa/chạy test** | Có read_file, apply_patch, run_pytest; xử lý môi trường server con và thêm parser kết quả MCP. | Repository/execution server chủ yếu là health checks; chưa có các tool mới này. |
| **Agent và smoke tích hợp** | Factory model được thống nhất; thêm smoke cho agent, MCP patch/test và evidence. | Giữ implementation agent cũ; chưa có các script smoke tích hợp mới. |
| **Code M2 cốt lõi** | Workspace, test runner, baseline, evidence writer và tests M2. | **Giống main** trong các phần này; khác biệt mới nằm ở lớp MCP/CLI tích hợp. |
| **Đánh giá Graph–BM25** | Chưa có bộ đánh giá retrieval. | Chưa có bộ đánh giá retrieval. |
| **Bằng chứng kiểm thử** | Có thêm tests Settings/parser và script smoke; chưa chạy lại trong lượt so sánh này. | Checkpoint M1 đã kiểm chứng **95/95 tests đạt**. |

Hiện chưa có bản nào chứa đầy đủ cả hai nhóm cải tiến: main còn thiếu công việc
M1 đang dev; bản dev còn thiếu commit tích hợp mới của main. Các điểm cần đối
chiếu kỹ khi ghép là **GraphNode contract, Settings và dependency Tree-sitter**.

So sánh dựa trên source, Git history và bằng chứng checkpoint đã lưu; không
coi việc có script smoke là bằng chứng script đã chạy thành công trong lượt này.
