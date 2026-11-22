# Thiết kế: harness agent sửa lỗi đủ 7 bước (repair_agent)

Ngày: 22/11/2026 (bản 2, sau review cùng ngày). Trạng thái: chờ duyệt. Thư mục riêng `repair_agent/`; không sửa file nào
trong `src/` hay `baseline/` (chỉ import).

## 1. Mục đích

Kiểm chứng workflow sửa lỗi của proposal (§9.1, prompt `repair_with_graph_context` 7 bước ở §10.4) với một mô hình
mạnh gọi qua API, để biết đề xuất có tốt không và cần thêm/bớt gì. Harness T2 hiện chỉ chạy bước 1–3 với Qwen3-4B (định
vị); harness này chạy cả bước 4–7 (patch → impact → kiểm → evidence).

Giai đoạn đầu gọi mô hình qua **9Router** (cổng cục bộ tương thích OpenAI) để kiểm harness; sau đó đổi sang GPT hoặc
nhà cung cấp khác chỉ bằng cấu hình.

## 2. Mục tiêu, không làm, phản mục tiêu

- **Mức A (làm trước):** vòng lặp chạy đủ, tool MCP trả kết quả, mô hình sửa code trên bản sao, harness ra một patch áp
  được vào cây gốc; ghi log đủ để đọc lại từng lượt. Không Docker, không chạy test, không chấm SWE-bench.
- **Mức B (sau, trước khi chạy API trả phí):** chạy test trong image Docker SWE-bench của từng task; chấm patch bằng
  harness chính thức (`src/vgar/evaluation/harness/`). Thiết kế chi tiết mức B làm sau mức A.
- **Không làm:** sửa server MCP hay retrieval; fine-tune; giao diện chat; thêm thư viện mới.
- **Phản mục tiêu:** harness chạy được nhưng kết quả không so được giữa các cánh (khác prompt ngoài chủ đích, khác giới
  hạn, khác mô hình); harness sửa cây gốc; ghi API key vào log hay file kết quả.

## 3. Ràng buộc

- Chạy trong WSL (graph `~/rt1/graphs/base`, cây task từ `baseline.run_offline.prepare_task`, venv `~/.vgar-wsl`).
- API theo chuẩn OpenAI Chat Completions có `tools`; gọi bằng **`httpx2`**. Không dùng `httpx`: venv WSL không có nó.
  `httpx2` được `mcp` (phụ thuộc chính thức của dự án) kéo theo, có ở cả venv WSL lẫn `.venv` Windows, và có
  `MockTransport` cho test. Không thêm thư viện.
- Cấu hình qua biến môi trường `VGAR_LLM_BASE_URL`, `VGAR_LLM_API_KEY`, `VGAR_LLM_MODEL` (tham số dòng lệnh ghi đè).
  Key chỉ đọc từ môi trường, không bao giờ ghi vào log hay file kết quả.
- 9Router mặc định ở `http://localhost:20128/v1` trên Windows; WSL đang ở chế độ mạng NAT (`.wslconfig` không có
  `networkingMode=mirrored`) nên không gọi được `localhost` của Windows. Người dùng chọn một: bật mirrored, chạy
  9Router trong WSL, hoặc dùng IP máy host làm base URL.
- **Cây task chỉ chứa file `.py`** (`extract_python_tree` giải nén mọi `.py`, kể cả test): agent không thấy và không sửa
  được file khác. Không ảnh hưởng bộ dev 50 task (0/50 bản sửa gold đụng file ngoài `.py`, kiểm 22/11), nhưng là giới
  hạn đã biết.
- Không chạy song song với job GPU hoặc job nặng khác (WSL 12 GB); lượt thử nhỏ trên repo nhỏ được phép.

## 4. Phương án đã cân nhắc

| | Phương án | Quyết định |
|---|---|---|
| Nơi xây | (1) dùng lại harness T2 bằng cách import `baseline.nav`; (2) harness viết mới hoàn toàn; (3) framework agent có sẵn | **(1)**, code nằm ở `repair_agent/`, chỉ import, không sửa `baseline/` (người dùng yêu cầu thư mục riêng). (2) viết lại phần đã có; (3) thêm thư viện, khó giữ đúng prompt/log. |
| Tạo patch | (a) mô hình tự viết unified diff; (b) tool `edit_file` sửa bản sao, harness sinh diff | **(b)**: patch luôn đúng định dạng, cây gốc không bị sửa. Lệch proposal (bước 4 bảo mô hình tự viết diff; ở đây thêm tool sửa file) — ghi vào luận văn. |
| Vòng lặp | dùng lại `run_task` của T2 (giao thức text `<tool_call>` của Qwen) hay viết vòng lặp native tool calling | **Viết vòng lặp mới**: API trả `tool_calls` có cấu trúc và cần message `role: tool` kèm `tool_call_id`, khác giao thức text của Qwen. |

## 5. Thiết kế

### 5.1 Hai cây thư mục (điểm quan trọng)

- **Cây gốc** (`prepare_task`): server graph trỏ vào đây (`VGAR_REPOSITORY_ROOT`), vì mỗi lần gọi nó kiểm hash nguồn
  so với graph; cây này không bao giờ bị sửa.
- **Bản sao làm việc** (thư mục tạm, chép từ cây gốc): `edit_file` sửa ở đây; tool đọc file (`FileTools`) cũng đọc ở
  đây để agent thấy chính thay đổi của mình. Diff = so bản sao với cây gốc. Xóa bản sao khi xong task.

### 5.2 Thành phần (đều trong `repair_agent/`)

- `llm.py` — client Chat Completions trên `httpx2`: gửi `messages` + `tools`, trả nội dung, `tool_calls`, `usage`.
  Thử lại khi 429/5xx/timeout (tối đa 5 lần, backoff); lỗi 4xx khác dừng task với trạng thái `API_ERROR` kèm nội dung
  lỗi (dùng để phát hiện route của 9Router không hỗ trợ tool). Không gửi `tool_choice`; `temperature` chỉ gửi khi người
  dùng đặt (một số mô hình từ chối tham số này). Gửi lại nguyên message `assistant` có `tool_calls` ở lượt sau.
- `workspace.py` — bản sao làm việc; `edit_file(path, old_text, new_text)` (thay đúng một chỗ; báo lỗi nếu không thấy
  hoặc thấy nhiều chỗ; chỉ trong bản sao, chỉ file `.py` có sẵn hoặc file mới hợp lệ), `show_diff()`; sinh diff kiểu git
  (`diff --git a/x b/x`, `--- a/x`, `+++ b/x`), đúng định dạng `vgar.repair.patch.parse_unified_diff` nhận;
  `patch_applies` = `git apply --check` trên một bản sao sạch của cây gốc (git có trong WSL).
- `tools.py` — gom tool cho mô hình:
  - đọc file: `FileTools(bản sao)` (`grep`, `read_file`, `list_dir`);
  - graph: lớp con của `baseline.nav.tools.GraphTools` với `TOOLS` mở rộng thêm `analyze_patch_impact`,
    `verify_patch_graph_constraints` (lớp gốc lọc bỏ mọi tool ngoài `TOOLS`). Như cánh `graph_v1`: gắn sẵn
    `graph_version`, `task_id`, issue đầy đủ; ẩn các tham số đó khỏi schema. Tham số `diff` của hai tool mới cũng được
    ẩn và harness gắn diff hiện tại của bản sao trước mỗi lời gọi; nếu chưa có thay đổi thì trả "chưa có patch".
  - sửa file: `edit_file`, `show_diff`.
  - Mức A **không** có `run_relevant_tests`: tool này chạy pytest bằng Python của server ngay trên máy, sai môi trường với
    repo SWE-bench.
  - Thời gian chờ mỗi lời gọi: 300 s, riêng `verify_patch_graph_constraints` 900 s (dựng graph bản vá, chậm trên repo
    lớn). Lớp gốc đánh dấu cả server graph là không dùng được sau một lần quá giờ; lớp con chỉ coi tool đó là lỗi, các tool
    graph khác vẫn dùng tiếp.
- `loop.py` — vòng lặp một task: prompt → gọi API → chạy các tool call **lần lượt theo thứ tự** (không song song: tránh
  đọc/sửa bản sao cùng lúc và giữ kết quả lặp lại được) → trả kết quả `role: tool` → lặp. Dừng khi mô hình trả lời cuối,
  hết lượt, hết thời gian, hết ngân sách, hoặc context ước tính gần trần (khi đó xin câu trả lời cuối, như T2).
- `run.py` — chạy nhiều task (manifest R1, `--arms`, `--only`, `--limit`, `--resume`), ghi kết quả; mỗi task một server
  graph mới (như T2).

### 5.3 Prompt và cánh

- `repair` — prompt `repair_with_graph_context` lấy từ server (`GraphTools.prompt`) + một đoạn ghi chú của harness:
  sửa code bằng `edit_file` (harness sinh diff, thay cho bước 4 "tự viết diff"); bước 6 không có test trong lượt này,
  dùng `analyze_patch_impact` và `verify_patch_graph_constraints`; định dạng câu trả lời cuối. Không có câu "dừng sau bước
  3". `context_budget` 1000 như T2.
- `repair_nograph` — prompt chung (tìm và sửa lỗi), chỉ tool đọc file + sửa file; cùng ghi chú về `edit_file` và định dạng
  kết thúc. Dùng làm mốc khi chạy thật; lượt thử mức A chỉ cần `repair`.
- Hai cánh giống nhau ở mô hình, giới hạn, ngân sách và định dạng kết thúc; chỉ khác prompt và bộ tool graph.

### 5.4 Kết thúc và đầu ra

- Mô hình kết thúc bằng JSON `{"files": [...], "functions": [...], "summary": "..."}` (đọc bằng
  `baseline.nav.model.parse_final`; `summary` lưu riêng). Patch cuối là diff của bản sao lúc kết thúc.
- Mỗi task một file `<out>/<arm>/<instance_id>.json`, các khóa tương thích với `baseline.nav.run_nav.score_nav`
  (`answer`, `tool_calls`, `spans`, `usage`, `status`, `ended_by`) cộng thêm `patch`, `patch_applies`, `summary`,
  `turns`. Điểm: `score_nav` trên câu trả lời; định vị theo patch = `extract_gold(patch, sources)` so với gold (file/hàm
  mà patch thật sự sửa). Audit log MCP như T2.

### 5.5 Giới hạn mặc định (chỉnh bằng tham số)

30 lượt gọi mô hình, 40 tool call, 20 phút mỗi task; context ước tính tối đa 100.000 token (bytes/4); ngân sách mỗi task
2.000.000 token vào cộng dồn và 100.000 token ra. Kết quả tool cắt như T2 (context 2.000, tool khác 1.500).

## 6. Kiểm chứng mức A

1. Test đơn vị (chạy bằng `.venv` Windows): client với `httpx2.MockTransport` (tool call, nhiều tool call một lượt, thử
   lại khi 429, dừng khi 400, kết thúc); `edit_file` (một chỗ, không thấy, nhiều chỗ, ngoài bản sao); diff đúng định dạng
   và `patch_applies`; tham số `diff` được gắn tự động; vòng lặp dừng đúng ở mỗi giới hạn.
2. Chạy thật qua 9Router trên 2–3 task repo nhỏ (flask-5014, requests-1724): có tool call graph, có `edit_file`, ra patch
  với `patch_applies = true`, log đọc lại được, không có key trong file kết quả.

## 7. Rủi ro đã biết

- 9Router chưa có tài liệu xác nhận chuyển tiếp đúng tool calling; tùy mô hình phía sau mà có thể không hỗ trợ. Lượt thử
  mức A phát hiện điều này (trạng thái `API_ERROR` hoặc mô hình không gọi tool).
- Mô hình miễn phí qua 9Router có thể có context nhỏ hơn trần 100.000; chỉnh trần bằng tham số.
- `verify_patch_graph_constraints` chậm trên repo lớn (sympy); có thể quá 900 s.

## 8. Để lại cho người xây

Tên hàm/tham số cụ thể, cách cắt hội thoại trong file kết quả, cách tính chi phí khi API không trả `usage` đầy đủ.

## 9. Ghi chú

- Vòng agent trọn vòng là mục #18 của TV1 (`docs/status/tv2_proposal_gaps_2026-11-20.md`); harness này là bản đo của TV2.
- Kết quả mức A chỉ chứng minh harness chạy đúng; tỉ lệ sửa được cần mức B.
