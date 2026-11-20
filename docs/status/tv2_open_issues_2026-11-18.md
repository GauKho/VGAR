# TV2 · Vấn đề còn mở và kiến trúc pipeline (18/11/2026)

Tổng hợp từ các lượt kiểm tra ngày 18/11. Số R1 với SCIP lấy lúc 13:38 UTC, khi lượt chạy chưa xong.
Mọi số ở đây đều có nguồn trong `docs/status/` hoặc trong thư mục kết quả `~/rt1` (WSL).

## A. Kết quả mới

| # | Việc | Trạng thái | Tiếp theo |
|---|---|---|---|
| A1 | R1 với SCIP (`~/rt1/results/r1_scip50`) | **Xong 50/50** (SCIP chạy được 41). `task_trace_rt1`: MRR hàm 0,270 → 0,249, −0,021, CI [−0,049; −0,004], 0/10; R@5 hàm −0,031 (CI chạm 0); reach +0,010. Build 12,7 → 207 s. Báo cáo: `tv2_r1_scip_2026-11-18.md` | Giữ SCIP tắt cho retrieval; thử lại sau phạm vi A |
| A2 | G1 với SCIP (`~/rt1/g1/report_scip3`, timeout 2.700 s) | Xong. SCIP chạy được 10/12 repo. `CALLS`: P 1,000 → 0,967, R 0,418 → 0,527. `CALLS + MAY_CALL`: P 0,486 → 0,687, R 0,609 → 0,618 | Viết báo cáo; chạy lại G1 sau khi sửa C8 |
| A3 | Kết luận | **Có CI (50 task):** SCIP làm graph đủ hơn (G1: recall `CALLS` 0,418 → 0,527), nhưng với bộ xếp hạng hiện tại retrieval xấu đi nhẹ (MRR hàm −0,021, CI không chứa 0); reach gần như không đổi, thêm cạnh làm loãng thứ hạng như lượt full layer. G1 cùng cấu hình với R1 (`report_scip4`): recall `CALLS` 0,418 → 0,536, P 0,967 | Thử SCIP sau phạm vi A |

## B. Retrieval còn yếu

| # | Vấn đề | Số đo | Hướng xử lý |
|---|---|---|---|
| B1 | Reach hàm thấp | Reach gộp theo hàm 0,50 (trung bình theo task 0,52–0,60); 17/70 hàm gold không tới được bằng mở rộng | Mở rộng method con theo file, xếp lại theo thân hàm. Trần mô phỏng (gộp theo hàm): 0,69–0,76 |
| B2 | Anchor nhiễu | 96,7 anchor/task, tối đa 727 | Lọc top-20 (giữ 34/36 task có anchor gold) |
| B3 | Graph thuần thua baseline văn bản ở mức hàm | R@5 hàm: graph 0,363, BM25 0,389, neighbor 0,471 | Phạm vi A; RRF là phân tích phụ |
| B4 | Gói context luôn lấp đầy 12k token | Mọi cấu hình 11,5–12k | Khung xương (mô phỏng 12 task: −37% cùng nội dung) + dừng sớm |
| B5 | "Token tới gold" chỉ tính trên task trúng | Hàm: graph 18/50, BM25 30/50. Tính đủ 50 task (trượt = 12.000): graph tốn hơn +2.114 [+632; +3.618] | Báo cáo cả hai cách tính, đo lại sau phạm vi A |
| B6 | Full layer (tsg + JARVIS + Joern) không có lợi | Không chỉ số nào tăng; build trung bình 12,7 → 186,5 s; retrieval không đọc cạnh G_code của Joern | Giữ tắt; nếu cải tiến thì sửa phía VGAR, không sửa code của tool |
| B7 | M2 ("hơn grep/BM25/embedding") chưa đạt | Graph thuần chưa hơn | Ghi rõ trong báo cáo |

## C. Chất lượng graph và cách đánh giá

| # | Vấn đề | Chi tiết |
|---|---|---|
| C1 | Nhãn G1 do Claude gán | Người kiểm tra mẫu 30 mục: raw 0,733, kappa 0,599. So sánh giữa các cấu hình vẫn công bằng vì dùng chung bộ nhãn |
| C2 | Component boundary (G_arch) chưa đo | Metric thứ 5/5 của G1; cần nhãn người (O7) |
| C3 | Joern chưa có số chất lượng cạnh | Chỉ có lượt chạy chức năng |
| C4 | LSP gần như không thêm cạnh | Bị chặn ở 200 request; chưa đo với giới hạn cao hơn |
| C5 | SCIP thất bại ở seaborn, scikit-learn | pyright dùng hết heap 6 GB trên một file; giới hạn của công cụ |
| C6 | R1/G1 không có LLM, không qua MCP | Đo hạ tầng, không đo agent sửa lỗi |
| C7 | Bộ dev có 5 task đa file, 11 task đa hàm | Chưa đủ để chứng minh sửa lỗi đa file |
| C9 | **MCP server chạy `RetrievalConfig()` (tương đương cánh `task_trace`), không phải `task_trace_rt1`** | Các báo cáo R1 trước gọi `task_trace_rt1` là "cấu hình phục vụ"; đã sửa nhãn. Từ 18/11 chỗ chọn duy nhất là `SERVED_CONFIG` (`src/vgar/graph/retrieval.py`), giữ `RetrievalConfig()` tới sau held-out |
| C8 | **G1 và R1 dùng cấu hình SCIP khác nhau** | G1 cũ: `import_roots=()`; R1, server và `run_graph_retrieval.py`: `("src", "lib")`. **Đã sửa 18/11** (mặc định chung trong `scip_config`); G1 chạy lại (`report_scip4`): `CALLS` P 0,967 / R 0,536, gần như không đổi so với lượt cũ (R 0,527) |

## D. Lệch so với plan 2 tuần

| # | Vấn đề | Ảnh hưởng |
|---|---|---|
| D1 | Bộ dev dùng min1, plan ghi `min_source_files=2` | Điều kiện §8.3 "patch cần thông tin cross-file" không được đảm bảo |
| D2 | Freeze R1 chưa ký, held-out chưa chạy | Chờ các quyết định ở mục F |
| D3 | Baseline "agent default" (§13.1) chưa có | Đề nghị TV1 |
| D4 | Incremental chưa đúng thuật toán §11.2 | Vẫn link lại toàn bộ |
| D5 | UTango (L4-3), `coverage_count` (L5-3) chưa làm | |
| D6 | RP1, M1, A0–A5, V1, I1, GD1, T2, T3 không có báo cáo trong repo | Có thể ở máy hoặc nhánh khác; cần hỏi TV1/TV3 |
| D7 | Workflow prompt (`src/vgar/mcp/proposal/prompts.py`) lệch §9.1 | Không hướng agent đi `get_callers`/`get_callees`; việc của TV1 |

## E. Hạ tầng và môi trường

| # | Vấn đề | Trạng thái |
|---|---|---|
| E1 | Claude Code không nối được MCP server: `~/.claude.json` thiếu `VGAR_REPOSITORY_ROOT`, `VGAR_GRAPH_DATABASE` là đường dẫn tương đối | Chưa sửa |
| E2 | `scripts/run_repair_experiment.py`, `scripts/dry_run_heldout_chain.py` bị xóa trong `90a79029`, nhưng plan và runbook vẫn dùng | Chưa báo TV1 |
| E3 | SCIP để lại `scip-pyrightconfig.json` khi bị dừng giữa chừng; lần sau dùng nhầm file cũ | Đã dọn; xóa file sót trước mỗi lượt chạy |
| E4 | Tiến trình nền bị hệ thống dừng khi thiếu RAM | Chạy lượt dài trong terminal WSL |
| E5 | `--stack-size` không được phép trong `NODE_OPTIONS` | Đã thay bằng `~/vgar-tools/node-big` |
| E6 | File rác ở thư mục gốc: `olve --agent on admitted…` và thư mục `~` | Chưa xóa |
| E7 | `requirement.txt` ghi `mcp[cli]>=1.24,<2` và LangChain, trái với `pyproject.toml` (`mcp==2.2.0`) | Cài theo file này thì server SDK 2 không chạy |
| E8 | Ba test mở thẳng `artifacts/sample_graph.db` (file được commit) và sửa nó | `tests/test_mcp_tool_contract.py:32`, `tests/test_w3_w4_graph_resources.py:11`, `tests/test_mcp_day5.py:22` |
| E9 | `"worktree": {"bgIsolation": "none"}` đang nằm trong `.claude/settings.json` (file dùng chung) | Đã sửa 18/11: chỉ còn trong `.claude/settings.local.json` |
| E10 | R1 với `--prune` xóa archive và cây mã của mọi task đã chạy, kể cả 12 archive mà kit G1 cần (12 task của G1 nằm trong 50 task của R1); G1 sau đó dừng với `refused: No such file` | Đã khôi phục 18/11: tải lại 12 archive từ GitHub (cả 12 khớp SHA-256 đã khóa) và giải nén lại cây mã. Sau mỗi lượt R1 có `--prune`, phải khôi phục trước khi chạy G1 |

## F. Quyết định còn chờ

1. Làm phạm vi A (lọc anchor, mở rộng method con có xếp hạng, khung xương, dừng sớm; khoảng 2–2,5 ngày) rồi freeze, hay freeze ngay.
2. PCST / PPR: đăng ký trước freeze, hay làm sau như hướng mở rộng.
3. Cấu hình nào làm cánh chính R1 (`PRIMARY_PAIRS`, bản freeze).
4. min1 hay min2 cho held-out.
5. Có bật SCIP mặc định không. **Đề xuất sau R1 SCIP:** tắt cho retrieval và held-out R1 (MRR hàm −0,021, build ×16); cân nhắc bật riêng cho impact / agent sau khi đo I1, M1.

## G. Tài liệu và code cần cập nhật

| # | Việc |
|---|---|
| G1 | `tv2_r1_full_layers_2026-11-16.md` dòng 88 và 116 đã cũ: lượt tách cho thấy xarray-4629 thua do layer, xarray-6992 thua do cờ `use_variable_references` (`tv2_r1_all_numbers_2026-11-16.md:218-219`) |
| G2 | Code chưa commit: `scripts/g1_evaluate.py`, `scripts/run_graph_retrieval.py`, `ablation_matrix/run_r1_ablation.py` (kèm thay đổi embedding từ trước), `ablation_matrix/tests/test_run_r1_ablation.py`, `tests/test_g1_labels.py`; cùng các file treo từ 17/11 (`ablation_matrix/paper_metrics.py`, `docs/protocol_freeze_r1_heldout.md`, các báo cáo R1 ngày 17/11) |
| G3 | Viết báo cáo G1 SCIP và R1 SCIP |
| G4 | Đưa Hit@k/Acc@k và chỉ số token (cả hai cách tính) vào bản freeze R1 làm chỉ số phụ; không sửa proposal |
| G5 | Đối chiếu số CoSIL/ARISE trong `tv2_r1_paper_comparison_2026-11-17.md` với bản PDF |

## H. Pipeline trong kiến trúc của proposal

Bước ③–⑤ (PPR, PCST, đóng gói 3 mức) và tool `read_symbol` là **đề xuất**, chưa có trong code.

```text
BUILD (offline, Layer 1–4, lưu ở Layer 6)
  Repo @ base_commit
    L1 tree-sitter + ast  -> G_repo: File/Class/Method, CONTAINS, range
    L1 tree-sitter-graph  -> Field, GlobalVariable, HAS_*, REFERENCES          (tắt mặc định)
    L2 resolver tĩnh      -> CALLS                                            (bật)
    L2 SCIP / LSP         -> CALLS resolve theo kiểu                          (tắt mặc định, đã đo)
    L2 JARVIS             -> CALLS bổ sung                                    (tắt mặc định)
    L2 MAY_CALL           -> cạnh đoán, có confidence và provenance           (bật)
    L3 Joern              -> G_code: CFG_NEXT, DATA_/CONTROL_DEPENDS_ON       (tắt mặc định)
    Lift                  -> G_arch: Component, Port, DEPENDS_ON, EXPOSES/CONSUMES_PORT
    L4 dulwich            -> lịch sử commit (cho recent_change_frequency; R1 không có)
    SC-1 validate         -> SQLite (L6), cập nhật incremental (§11)

TASK (mỗi issue)
  issue / traceback / test fail -> G_task overlay: Issue, BugReport, StackTraceFrame,
                                   ErrorMessage, FailingTest; MENTIONS, REPRODUCES, TRACES_TO

TRƯỚC PATCH: retrieval (§9.2), graph server
  1  anchor top-20               find_task_anchors     G_task + G_repo
  2  _walk 2 bước + method con   get_related_context   CALLS/TESTS/CONTAINS, MAY_CALL x0,5, G_arch seeds
  3  PPR                         (trong bước 2)        trọng số cạnh = confidence x hệ số loại cạnh
  4  PCST, prize = PPR           (trong bước 2)
  5  đóng gói 3 mức + khung xương (trong bước 2)       range của nút + ast
  6  dừng sớm -> agent
     agent khám phá thêm: get_callers, get_callees, explain_dependency_path, read_symbol (§9.1)

SAU PATCH: impact và verification (§9.3, §12)
  7  analyze_patch_impact          diff -> graph edit; đi ngược CALLS/IMPORTS/TESTS và
                                   EXPOSES_PORT/CONSUMES_PORT/DEPENDS_ON (F2, max_hops=2)
  8  verify_patch_graph_constraints  schema, kiến trúc (cycle, import ngược tầng, mất port), API
  9  run_relevant_tests            cạnh TESTS -> chọn test; pytest + mypy/ruff; invariant (tắt)
  10 rank_patch_candidates         evidence 9 trường -> score(patch) (§8.5)
     -> agent sửa tiếp hoặc nộp patch kèm evidence
```

### Mỗi layer dùng ở bước nào

| Layer (§5.2) | Thành phần | Bước | Mặc định | Căn cứ |
|---|---|---|---|---|
| L1 tree-sitter + ast | Node, CONTAINS, range | 1, 2, 5, 7 | Bật | Lõi; build trung vị 8,3 s (`r1_50`) |
| L1 tree-sitter-graph | Field, GlobalVariable, HAS_*, REFERENCES | 2 (cạnh đọc biến chỉ dùng khi bật cờ `use_variable_references`) | Tắt | Không thêm cạnh CALLS. Build xarray 11,5 → 30,5 s. Cờ `use_variable_references` làm xấu xarray-6992 |
| L2 resolver tĩnh | CALLS | 2, 3, 4 | Bật | G1: P 1,000 / R 0,418 |
| L2 MAY_CALL | Cạnh đoán | 2, 3, 4 (trọng số x0,5) | Bật (`RT1_CONFIG`) | Cải thiện nhỏ ở file R@1 và MRR; mọi CI95 chạm 0 |
| L2 SCIP / LSP | CALLS resolve theo kiểu | 2, 3, 4, 7 | Tắt | G1: R 0,418 → 0,527, P 0,967 (10/12 repo). R1: đang đo, xu hướng sớm chưa có lợi. LSP: giới hạn 200 request |
| L2 JARVIS | CALLS bổ sung | 2, 3, 4 | Tắt | G1: R 0,527 (cận dưới); lỗi ở 9/50 task R1; cần Docker |
| L3 Joern | G_code | 7 | Tắt | Retrieval không đọc cạnh G_code; impact có dùng (`impact.py:263`) |
| L3 CodeQL / Glean / Kythe | — | — | Bỏ theo §5.3 | |
| Lift → G_arch | Component, Port, DEPENDS_ON | 2 (component seeds), 7, 8 | Bật | Gần như không thêm gì cho retrieval; giá trị chính ở impact và verify |
| G_task overlay | BugReport, StackTraceFrame, FailingTest, TRACES_TO | 1, 2 (`failing_test_proximity`) | Bật | Layer có lợi rõ nhất: R@5 hàm 0,207 → 0,338 |
| L4 GraphDiff | Lịch sử commit, graph edit | 2 (`recent_change_frequency`), 7 | Có, thiếu UTango | `~/rt1` không có lịch sử nên đặc trưng này vắng trong R1 |
| L5 pytest, mypy, ruff | Test, kiểm tra tĩnh | 9 | Bật | EV-3 |
| L5 invariant (Daikon) | Likely invariant | 9 → `semantic_invariant_preserved` | Tắt | L5-1/L5-2 |
| L6 SQLite + MCP SDK 2 + incremental | Lưu và phục vụ graph | Mọi bước | Bật | 11 tool, 8 resource; U1 12/12 |

### Trọng số cạnh đề xuất cho PPR / PCST (chỉnh trên `tune25`)

| Cạnh | Layer | Trọng số |
|---|---|---|
| CALLS / CALLERS | L2 | Cao: bằng confidence |
| MAY_CALL | L2 | confidence x 0,5 (như `may_call_factor`) |
| TESTS / TESTED_BY | L1 + G_task | Cao: gần test fail |
| MEMBER_REFERENCE | L1 | Trung bình |
| INHERITS, IMPORTS | L1 / L2 | Trung bình đến thấp |
| CONTAINS, cùng file | L1 | Thấp, để không lan theo file |
| DEPENDS_ON, EXPOSES/CONSUMES_PORT | G_arch | Rất thấp hoặc bỏ ở bước 3–4; dùng ở bước 7–8 |
| TRACES_TO | G_task | Chỉ dùng để tạo vector hạt giống của PPR, không dùng để lan |

### Tín hiệu trước và sau patch

| Tín hiệu | Trước patch (bước 1–6) | Sau patch (bước 7–10) |
|---|---|---|
| S_task, S_trace, S_call, S_struct | Có | |
| S_edit (đổi signature, exception, API) | Không (chưa có diff) | Có, bước 7 |
| F1: vùng phụ thuộc trực tiếp | Có, `_walk` | |
| F2: lan truyền khi đổi interface | | Có, bước 7 (đã có từ IM-1) |
| Test | Dùng làm anchor và để chấm `failing_test_proximity`; không đóng gói | Có, bước 9 |
| F\*_approx | Không: chỉ là nhãn chấm điểm, dựng từ patch gold | |
