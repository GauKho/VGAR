# Thiết kế: harness đo toàn bộ layer của graph theo proposal (TV2) — 19/11/2026

Trạng thái: **bản nháp, chờ duyệt.**

## 1. Mục đích

Đồ án xây graph (Arch-CPG) phục vụ coding agent qua MCP cho **lỗi đa file**. Harness này đo **từng layer đóng góp gì**
theo đúng chỉ số §13.2 và baseline §13.1, trên **cùng một graph** cho phần đo offline và phần có LLM. Lý do cần phần có
LLM: giá trị của graph (cạnh chéo file, confidence, impact) chỉ lộ ra khi có LLM chọn anchor và đi theo cạnh; R1 hiện
chỉ đo cận dưới không có LLM.

## 2. Mục tiêu, không làm, không được xảy ra

**Mục tiêu**
- Bảng "mỗi layer đóng góp bao nhiêu" theo profile thêm dần, cho chất lượng graph, retrieval/impact offline và LLM điều hướng.
- Graph dựng một lần cho mỗi (task, bản dựng), lưu SQLite, dùng chung cho tầng offline và tầng LLM.
- Mọi bảng tách riêng tầng `cross_file` (≥ 2 file gold); kết luận về graph chỉ đưa ra trên tầng này.
- Mỗi con số có lệnh tái tạo.

**Không làm**
- Sửa lỗi đầu-cuối (patch success, resolved rate) — phạm vi TV1. Verification (§12, false accept/reject) — phạm vi TV3.
- Cải tiến retrieval (phạm vi A tạm dừng). Không đổi code layer.

**Không được xảy ra**
- **Sửa code trong `src/` hay các script hiện có.** Toàn bộ code mới nằm trong `baseline/` (yêu cầu của người dùng 19/11).
- Tầng offline và tầng LLM đọc hai graph khác nhau.
- F\* được suy ra từ chính graph (thiên vị graph).
- Chạy model GPU khi người dùng chưa chạy (người dùng tự chạy lượt GPU dài).

## 3. Ràng buộc

- Máy: RTX 4050 6 GB; dữ liệu R1 ở WSL `~/rt1` (archive, cây mã, gold, manifest 50 task dev, 5 task đa file).
- Server MCP SDK 2.2.0, repo lấy từ biến môi trường host (`VGAR_REPOSITORY_ROOT`, `VGAR_GRAPH_DATABASE`,
  `VGAR_MCP_AUDIT_LOG`), mỗi tiến trình một repo; server xếp hạng bằng `SERVED_CONFIG` (= cánh `task_trace`, tức A2).
- Model: `Qwen/Qwen3-4B-Instruct-2507` (đã ghim trong `.env`), chưa có trọng số trong cache; venv WSL chưa có `mcp`.
- Chỉ dùng tập dev; held-out chỉ chạy sau freeze.

## 4. Các cách đã cân nhắc

| Quyết định | Phương án | Chọn | Lý do |
|---|---|---|---|
| Trục profile | thêm dần / bỏ từng layer | **thêm dần** (người dùng chọn) | khớp thang §13.1 và §13.3, rẻ hơn |
| Graph dùng chung | dựng trong bộ nhớ mỗi lần (như R1) / một SQLite cho mỗi (task, bản dựng) | **SQLite** (người dùng chọn) | tầng offline và tầng LLM đọc đúng một graph |
| Chạy Qwen | A: HF transformers 4-bit / B: llama.cpp, Ollama GGUF | **A** (người dùng chọn), có spike đo tốc độ trước | không thêm công cụ, cùng model đã ghim, tái lập tốt |
| F\* | giữ nguyên / 2a thêm tên dòng bị xóa / 2b thêm caller | **2a** (người dùng chọn) | rẻ, chỉ dựa văn bản, không thiên vị graph |
| Nơi đặt code | `ablation_matrix/` / thư mục riêng | **`baseline/`** (người dùng chọn) | không ảnh hưởng code chính |

## 5. Profile (thêm dần)

Thứ tự theo §13.3 (A1 → A2 → A3), trước đó là baseline AST-only của §13.1, sau đó các layer dựng thêm.

| Profile | Bản dựng graph | Cánh retrieval (đã có trong `ablation_matrix/retrieval_variants.py`) | Ứng với |
|---|---|---|---|
| P0 | `base` | `ast_no_task_trace` (AST-only, suy ra từ `base` bằng `ast_only`) | §13.1 AST-only graph |
| A1 | `base` | `no_task_trace` | repo symbol graph |
| A2 | `base` | `task_trace` (= server mặc định) | + task trace |
| A3 | `base` | `a3` | + architecture |
| A3+SCIP | `scip` | `a3` | + SCIP |
| A3+SCIP+LSP | `scip_lsp` | `a3` | + LSP |
| Full | `full` (+ tree-sitter-graph, Joern, JARVIS) | `a3` | full Arch-CPG |

Bốn bản dựng (`base`, `scip`, `scip_lsp`, `full`) là bốn `LayerConfigs` khai báo trong `baseline/profiles.py`, dùng các
hàm sẵn có của `vgar.graph.layer_config`. Lịch sử GraphDiff (Layer 4) là profile phụ `A2+H` (cờ `--history` sẵn có của R1),
chỉ chạy khi có clone git.

## 6. Bốn tầng đo

| Tầng | Chỉ số (§13.2) | LLM | Cách làm |
|---|---|---|---|
| **T0 chất lượng graph** | call edge P/R, symbol resolution (G1); trace link P/R (TR-1); GraphDiff P/R/F1 (GD1); incremental correctness (U1); component boundary (khi có nhãn người) | Không | **Chỉ gom kết quả** của các script sẵn có (mỗi script có bộ dữ liệu riêng); `baseline/report.py` đọc JSON của chúng. Không chạy lại trong harness |
| **T1 retrieval + impact offline** | recall@k file/hàm, MRR, frontier Recall@B (trên gói server: `native_*`), token; grep/BM25/neighbor/embedding; I1 đa file | Không | `baseline/run_offline.py` (mục 7) |
| **T2 LLM điều hướng** | Hit@k file/hàm, frontier Recall trên phần LLM đã đọc; tool calls/task, latency trung bình, token, số file không phải gold đã đọc | Có | `baseline/nav/` (mục 8) |
| T3 sửa lỗi, verification | – | – | ngoài phạm vi |

## 7. T1: chạy offline

Mỗi task:
1. Lấy cây mã như R1 (`read_repository_sources`, `extract_python_tree`).
2. Với mỗi bản dựng cần cho profile đang chạy: nếu `~/rt1/graphs/<build>/<instance_id>.db` chưa có thì dựng bằng
   `PythonGraphBuilder(**layers.builder_kwargs())` rồi `SQLiteGraphStore(db).ingest(document)`; có rồi thì
   `load_document`. Ghi `build_seconds`, trạng thái từng layer (`layer_summary`).
3. Gọi các hàm cấp thấp sẵn có: `variant_outputs` (cánh của profile), `evaluate_graph_task(..., frontier=True)`,
   `native_context_metrics`, `component_metrics`, các baseline văn bản (chỉ một lần cho mỗi task, trên `base`;
   embedding chỉ chạy khi truyền model, vì cần GPU — mặc định tắt).
   Đây là thành phần của `run_r1_ablation.evaluate_task` được ghép lại, vì hàm đó tự dựng graph trong bộ nhớ.
4. Thay `gold["frontier_functions"]` bằng **F\*_core v2** (mục 9) trước bước chấm.
5. I1 đa file: `gold_impact.cross_file_reach` trên graph của bản dựng (task có ≥ 2 file gold).
6. Ghi `~/rt1/results/layers/<profile>/tasks/<instance_id>.json`; `--only`, `--resume`, `--profiles`.

Phân tích: `ablation_matrix/compare_runs.py` (đã có CI theo cặp, `--min-gold-files 2`) so profile kề nhau.

## 8. T2: Qwen điều hướng graph (định vị lỗi)

**Cánh**
- `base`: tool đọc file — `grep(pattern, glob)`, `read_file(path, start, end)`, `list_dir(path)` (cài trong harness,
  chặn đường dẫn ra ngoài cây mã). Ứng với "agent default exploration" của §13.1.
- `graph_v0`: `base` + tool của server graph qua client MCP SDK 2.2 (stdio, mỗi task một server trỏ vào DB `base`):
  `search_symbols`, `find_task_anchors`, `get_related_context`, `get_callers`, `get_callees`, `explain_dependency_path`.
  Harness điền sẵn `graph_version` và `task_id`; `get_related_context` dùng ngân sách nhỏ (mặc định 3000).
- `graph_v0_scip`: như `graph_v0`, DB `scip`.
- `graph_conf` (sau khi `graph_v0` ổn định): như `graph_v0`, nhưng lớp chuyển tool trong harness thêm `confidence` và
  `provenance` của cạnh `CALLS` (đọc từ cùng DB, chỉ đọc) và các cạnh vào/ra cho node. Đây là **bản thử phía harness**
  của thay đổi server; chuyển vào server khi người dùng đồng ý.

**Vòng lặp** (tự viết, không LangChain): prompt hệ thống giống nhau mọi cánh, chỉ khác danh sách tool. Qwen sinh
`<tool_call>` theo chat template có `tools`; harness gọi tool, cắt kết quả (≤ 1500 token mỗi lần), tối đa 12 lời gọi,
ngữ cảnh tối đa 16k token, greedy (temperature 0). Kết thúc bằng JSON `{"files": [≤5], "functions": [≤10]}`.
Hết lượt hoặc JSON hỏng: ghi trạng thái, giữ task trong mẫu số.

**Chấm**
- Danh sách cuối → `RankRecord` → `score_record` (recall@k, MRR) như R1.
- "Phần đã đọc" = mọi đoạn code Qwen đã thấy (`read_file`, `get_related_context`, các đoạn trong kết quả tool); tính
  frontier Recall (F\*_core v2) và "đủ mọi file gold đã thấy" trên phần này.
- MCP usability: số lời gọi theo tool, latency mỗi lời gọi, token vào/ra, số file không phải gold đã đọc.
- Ghi toàn bộ hội thoại và lời gọi tool vào `~/rt1/results/nav/<arm>/<instance_id>.json`.

**Spike trước** (`baseline/nav/spike_qwen_speed.py`, bỏ đi sau khi đo): nạp Qwen 4-bit (bitsandbytes nf4), một lượt có
tool, in giây/lượt và bộ nhớ GPU. Quá 2 phút mỗi task trung bình thì quay lại cân nhắc phương án B.

## 9. F\*_core v2

`baseline/frontier_v2.py`: như `vgar.evaluation.retrieval.frontier.dependency_frontier`, nhưng lấy tên trong **cả dòng
thêm và dòng bị xóa** của file nguồn trong patch gold (tên duy nhất trong kho, bỏ từ khóa và builtin). Không dùng graph.
Báo cáo ghi rõ đây là F\*_core v2; F\*_ext (hàm do test FAIL_TO_PASS chạy qua, lấy từ coverage) để giai đoạn sau.

## 10. Bố cục thư mục

```
baseline/
  profiles.py          # 4 bản dựng LayerConfigs + bảng profile -> (bản dựng, cánh)
  graph_store.py       # dựng hoặc nạp graph (task, bản dựng) trong SQLite
  frontier_v2.py       # F*_core v2
  run_offline.py       # T1
  nav/
    spike_qwen_speed.py
    model.py           # nạp Qwen 4-bit, sinh và tách <tool_call>
    tools.py           # tool đọc file + client MCP + lớp graph_conf
    run_nav.py         # T2: vòng lặp, chấm, ghi kết quả
  report.py            # bảng theo layer (T0 gom từ JSON sẵn có, T1, T2), mỗi số kèm lệnh tái tạo
  tests/
```

Code trong `baseline/` chỉ **import** từ `src/vgar` và `ablation_matrix/`, không sửa chúng.

## 11. Môi trường

Chạy trong WSL (`~/.vgar-wsl`). Người dùng cài thêm `mcp==2.2.0` và `bitsandbytes` vào venv này và tải trọng số Qwen
(khoảng 8 GB). Lệnh cài và lệnh chạy ghi trong kế hoạch; người dùng tự chạy mọi lượt dài và mọi lượt GPU.

## 12. Để lại cho người xây (quyết định của mình, người dùng có thể sửa)

- Đường dẫn cache graph `~/rt1/graphs/<build>/<instance_id>.db`, một DB cho mỗi (task, bản dựng).
- Giới hạn T2: 12 lời gọi, 1500 token mỗi kết quả tool, 16k ngữ cảnh, ngân sách `get_related_context` 3000.
- Thứ tự làm: F\*_core v2 → T1 cho P0–A3 (rẻ) → spike Qwen → T2 `base` và `graph_v0` trên 10 task thử → 50 task →
  bản dựng `scip`, `scip_lsp`, `full` → `graph_conf`.
- Bản dựng `full` cần Docker (Joern, JARVIS) và chậm; có thể chỉ chạy trên một phần task, ghi rõ số task.
