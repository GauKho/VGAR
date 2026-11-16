# Đo các layer trong graph của MCP và cờ mới của tool (15/11/2026)

Spec: `docs/superpowers/specs/2026-11-15-layers-in-build-and-agent-tools-design.md`. Plan: `docs/superpowers/plans/2026-11-15-layers-in-build-and-agent-tools.md`.

**Mọi cờ mới mặc định tắt.** Chỉ bật mặc định sau khi bạn xem số đo dưới đây và quyết định. Không chỉnh cờ trên chính tập task dùng để báo cáo.

## 1. Bật layer cho graph của MCP (host)

Thêm vào `env` của `vgar-graph` (và `vgar-execution` nếu dùng chung graph) trong `~/.claude.json`, mọi đường dẫn là tuyệt đối:

| Biến | Layer |
|---|---|
| `VGAR_REPOSITORY_ROOT`, `VGAR_GRAPH_DATABASE`, `VGAR_MCP_AUDIT_LOG` | bắt buộc (thiếu thì server không khởi động) |
| `VGAR_TSG_EXECUTABLE`, `VGAR_TSG_TREE_SITTER_DIR` | tree-sitter-graph (Field, GlobalVariable, cạnh đọc biến) |
| `VGAR_SCIP_ENTRY` (+ `VGAR_NODE`, `VGAR_SCIP_ENVIRONMENT`, `VGAR_SCIP_TIMEOUT`, `VGAR_SCIP_PYTHON`) | SCIP |
| `VGAR_LSP_ENTRY` (+ `VGAR_LSP_PYTHON`) | LSP |
| `VGAR_JARVIS=1` (+ `VGAR_JARVIS_IMAGE`, `VGAR_JARVIS_TIMEOUT`) | JARVIS (Docker) |
| `VGAR_JOERN=1` (+ `VGAR_JOERN_IMAGE`, `VGAR_JOERN_TIMEOUT`) | Joern (Docker) |
| `VGAR_IMPACT_FOLLOW_VARIABLE_READERS=1` | cờ impact A |
| `VGAR_IMPACT_NARROW_WITH_DATAFLOW=1` | cờ impact B |

Khi bật bất kỳ layer tuỳ chọn nào, mỗi lần `build_or_update_graph` là build toàn bộ (không incremental). Kết quả tool có `layers` (ready / off / failed + lý do) và `revision` (SHA của HEAD, hoặc `cli` nếu không phải repo git).

## 2. Thứ tự đo (bạn chạy trong WSL, như R1)

1. **I1 baseline (chưa từng có):**
   ```bash
   python scripts/measure_patch_impact.py --manifest <dev manifest> --data-root <root> --parquet <parquet> \
       --task-inputs <dir> --out results/i1/baseline
   ```
2. **I1 + cờ A** (cần tree-sitter-graph):
   ```bash
   python scripts/measure_patch_impact.py ... --tsg-executable <abs> --tsg-tree-sitter-dir <abs> \
       --follow-variable-readers --out results/i1/A
   ```
3. **I1 + A + B** (thêm Joern, Docker):
   ```bash
   python scripts/measure_patch_impact.py ... --tsg-executable <abs> --tsg-tree-sitter-dir <abs> --joern \
       --follow-variable-readers --narrow-with-dataflow --out results/i1/AB
   ```
   So 1 với 2 với 3 theo từng task: tỉ lệ chạm tới test FAIL_TO_PASS, kích thước vùng impact. Khi có layer hoặc cờ bật, `i1.json` ghi `layers` và `impact_flags`, và mỗi task ghi `layers` (layer nào ready/failed). Lần chạy mặc định (1) không có hai khóa này.
4. **R1 cờ context** (arm `task_trace`, 50 task, cần tree-sitter-graph):
   ```bash
   python ablation_matrix/run_r1_ablation.py <root> <manifest> --out <out>/tsg_off --allow-fallback-counter \
       --tsg-executable <abs> --tsg-tree-sitter-dir <abs>
   python ablation_matrix/run_r1_ablation.py <root> <manifest> --out <out>/tsg_on --allow-fallback-counter \
       --tsg-executable <abs> --tsg-tree-sitter-dir <abs> --use-variable-references
   ```
   So arm `task_trace` giữa hai thư mục (R@5 hàm, MRR hàm, Recall@B). Cả hai lần đều build graph có tree-sitter-graph, nên khác biệt chỉ đến từ cờ.

## 3. Đọc kết quả

- Cờ A có ích nếu tỉ lệ chạm F2P tăng mà vùng impact không phình quá mức.
- Cờ B có ích nếu vùng impact nhỏ đi mà tỉ lệ chạm F2P không giảm. Xem `dataflow_fallbacks` (hàm không có G_code) để biết B thực sự phủ bao nhiêu.
- Cờ context có ích nếu R@5 hàm hoặc MRR hàm của `task_trace` tăng. R1 ngày 11/11 cho thấy thêm cạnh thường làm loãng xếp hạng, nên kết quả rỗng hoặc âm là khả năng có thật và được báo đúng như vậy.

## 4. Việc sau review (15/11) — đã đóng hết

- **Lỗi 2 — đã sửa.** Hàm bị cờ B thu hẹp không còn được tính vào `seed_components` (`src/vgar/graph/impact.py`), nên component phụ thuộc nó qua `DEPENDS_ON` không bị báo nữa. Số `I1+A+B` vì thế đo đủ tác dụng thu hẹp của B.
- **Lỗi 8 — đã sửa.** `i1.json` chỉ ghi `impact_flags` / `layers` (ở cấp file và cấp task) khi có cờ hoặc layer bật; lần chạy mặc định giữ dạng cũ.

Chi tiết: `.superpowers/sdd/2026-11-15-layers-in-build-and-agent-tools/progress.md` (mục "Follow-up 3").
