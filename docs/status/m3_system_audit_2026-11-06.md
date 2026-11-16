# Audit hệ thống: metric ablation, thuật toán, logic, chạy trên repo thật (06/11/2026)

Nhánh `m3/w12-all`, HEAD `3f77fcf6`. Đường dẫn code không có tiền tố tính từ `src/vgar/`.
Mức: **C** = chặn demo hoặc chặn số liệu luận văn, **H** = cao, **M** = trung bình, **L** = thấp.
Cột "Kiểm chứng": **chạy** = đã tái hiện bằng lệnh (§5), **đọc** = suy ra từ việc đọc code.

## 1. Kết luận

- **Metric F1–F8, Recall@k, FAR/FRR được tính đúng định nghĩa** trong `docs/protocol_freeze_heldout.md` §8.
  Mẫu số luôn là toàn bộ quần thể, có cổng fairness giữa các arm, và kiểm tra hash ở mọi đầu vào.
- **Phần thống kê §9 chưa có code.** Chưa có McNemar exact, chưa có Holm. Bootstrap chỉ có cho retrieval và lấy
  2.000 vòng thay vì 10.000. Đây là lỗ hổng lớn nhất của phía đánh giá (E1, E2).
- **Thuật toán retrieval chạy đúng như thiết kế**, nhưng trên repo thật, phần mô tả lỗi viết bằng lời không định vị được
  symbol nào. Anchor chỉ đến từ test fail, và hàm có lỗi không lọt vào context (A1, A3).
- **Trên repo thật, agent mới dùng được 3 trong 7 tool graph.** `get_related_context`, `find_task_anchors`,
  `get_related_tests` và `analyze_patch_impact` hỏng trong `vgar run` / `vgar chat`. Lý do: agent không được cho biết
  `graph_version`, và host không đặt biến tokenizer cùng thư mục repo (R1, R2).
- **Repo demo chưa sẵn sàng:** chưa có git, chỉ có 1 test fail, và test đó cần sửa **hai** bug ở hai file khác nhau (R3).

## 2. Metric ablation và thống kê

| # | Mức | Vấn đề | Bằng chứng | Kiểm chứng | Hướng sửa |
|---|---|---|---|---|---|
| E1 | C | **Chưa có McNemar exact và Holm.** Protocol §9 đăng ký ba phép so sánh (A1 vs A0, A2 vs A1, A3 vs A2) bằng McNemar exact kèm b, c, và hiệu chỉnh Holm. Trong `src/` và `scripts/` không có hàm nào làm việc này. `aggregate.py` chỉ đếm funnel | `grep -ri "mcnemar\|holm\|binom"` không ra kết quả; `evaluation/repair/aggregate.py` | đọc | Thêm module ghép cặp theo `task_id` từ `rows` của `aggregate.json`: tính b, c, p hai phía bằng nhị thức (b+c, 0,5), rồi Holm trong nhóm 3 phép so sánh. Với FAR/FRR thì ghép theo slot của mutant pool. Viết test với b, c tính tay |
| E2 | M | **Số vòng bootstrap lệch protocol:** code lấy 2.000 vòng, protocol §9 ghi 10.000 | `evaluation/retrieval/compare.py:81` (`rounds: int = 2000`) | đọc | Đổi mặc định hoặc truyền `rounds=10000` ở lệnh chạy held-out, và ghi số vòng vào `result.json` |
| E3 | M | **Mẫu số retrieval khác mẫu số repair.** Phép so sánh graph vs BM25 bỏ task không SUCCEEDED ở cả hai run (`skipped`). Funnel repair thì giữ toàn bộ N | `compare.py:117-120` so với docstring `aggregate.py:3` | đọc | Báo cáo `paired_tasks` / `eligible` cạnh mọi Recall@k. Nếu `skipped` khác rỗng thì ghi rõ trong luận văn |
| E4 | M | **FAR tính ERROR là "đã từ chối".** Verifier lỗi càng nhiều thì FAR càng thấp, nghĩa là trông càng tốt. Bảng V2 có cảnh báo, nhưng con số FAR chính ở V1 vẫn tính gộp | `evaluation/repair/verifier_eval.py:283-291` | đọc | Thêm cột FAR chỉ tính trên các vector không ERROR (chỉ phân loại PASS/FAIL), hoặc báo cáo FAR kèm `bad_errors` ở cùng ô |
| E5 | M | **Suy A2/A3 từ A1 (ĐX1) chưa có code.** Nếu nhóm chốt ĐX1 thì `aggregate.py` cần đọc record A1 và ghi `derived_from` | `grep derived_from` không ra kết quả | đọc | Làm theo `docs/status/m3_a0_a3_plan_2026-11-04.md` §4, hoặc ghi lại là đã bỏ |
| E6 | L | **Check bắt buộc ở trạng thái `UNAVAILABLE` vẫn tính là pass.** Task nào không có mypy thì A2 cho kết quả giống A1 | `repair/verification.py:174`; `verifier_eval.py:63` | đọc | Không phải bug. Báo cáo subgroup `mypy_*` (đã có trong `aggregate.py:150`) và nêu trong phần Hạn chế |
| E7 | L | **Định nghĩa Recall@k trong protocol chưa khớp code.** Protocol §8 ghi "top-k context", còn code tính trên thứ tự xếp hạng; mức "có trong context đã đóng gói" là metric riêng `packed_gold_*_in_context` | `evaluation/retrieval/metrics.py:9-22` | đọc | Sửa câu trong protocol: Recall@k tính trên thứ tự xếp hạng sau khi khử trùng lặp |
| E8 | L | Tiêu đề và docstring vẫn ghi "A0-A2", dù code đã hỗ trợ A3 | `aggregate.py:1`, `:177` | đọc | Sửa chữ khi làm E1 |

Những điểm đã đúng:
- F4 chỉ tính khi F3 đúng và có `applied.diff`.
- F5 trả về `unavailable` thay vì `False` khi không có graph.
- `harness_status` được khóa theo `run_id`, nên điểm của lần chạy trước không bị gán cho lần chạy lại.
- `check_arm_fairness` chặn mọi khác biệt ngoài `arm` và `required_checks`.
- `A0 == A1` trên mutant pool được assert (`verifier_eval.py:595`).
- A3 dùng đúng bộ variant W10 (normalized/context), cùng bộ với A0–A2 (`docs/m2_w12_1_a3.md:18`). **Đính chính 06/11:**
  điều này chỉ đúng cho runbook; `docs/protocol_freeze_heldout.md:32-34` vẫn trỏ tới variant W9 cũ (xem tổng hợp, #5).

## 3. Thuật toán và logic

| # | Mức | Vấn đề | Bằng chứng | Kiểm chứng | Ghi chú |
|---|---|---|---|---|---|
| A1 | H | **Phần mô tả lỗi viết bằng lời không sinh được anchor.** Với issue "Checkout with coupon SAVE10 on a 500000 VND order gives no discount…", `find_task_anchors` chỉ trả về đúng 1 anchor là test fail. Không anchor nào trỏ tới `checkout`, `discount_amount` hay `is_eligible` | §5, bước 4 | chạy | Khớp với anchor noise ghi từ W5–W6 (`graph/grounding.py`). Trên SWE-bench, test bị ẩn, nên arm graph phụ thuộc hẳn vào phần chữ này |
| A2 | M | **Feature `failing_test_proximity` (trọng số 0,2) bị bỏ khi không có cạnh REPRODUCES.** Trọng số được chuẩn hóa lại trên các feature còn lại. Theo kế hoạch 04/11 thì feature này đang null trên dev | `graph/retrieval.py:179-182` | đọc | Ghi trong luận văn: thực tế ranking chạy với 4 feature |
| A3 | M | **Trên repo demo, hàm có lỗi `is_eligible` không lọt vào context** (budget 2.000 token). `discount_amount` (nơi gọi nó) đứng hạng 5; 5 trong 11 item là test | §5, bước 5 | chạy | Đường gọi qua MCP không lọc test khỏi context như đường bundle. Nên xem lại budget và bộ lọc |
| A4 | L | **`graph_distance = confidence/(1+d)` và `edge_confidence = confidence` tương quan với nhau.** Thực chất `confidence` chiếm trọng số 0,3 | `graph/retrieval.py:251-252` | đọc | Không phải bug; cần giải thích nếu hội đồng hỏi |
| A5 | L | **43% lời gọi hàm trên repo demo không resolve được** (20/46, resolver static). `get_callers`/`get_callees` có thể thiếu cạnh | `graph_metadata.statistics.unresolved_call_rate = 0.435` | chạy | SCIP/LSP có sẵn nhưng `vgar index` dùng static |

Đã kiểm tra và thấy đúng:
- `assess_transition` (`repair/verification.py:57`) chỉ PASS khi mọi test bắt buộc pass và không có test nào từ PASS
  chuyển sang không PASS. Thiếu kết quả thì trả về ERROR, không bao giờ PASS.
- `select_relevant_tests` chạy toàn bộ fallback scope, nên không bỏ sót regression.
- Check static so theo delta với baseline, có line map.
- Phát hiện được thay đổi ngoài file đã vá (`PROTECTED_SOURCE_CHANGED`).

## 4. Khả năng vận hành trên repo thật

| # | Mức | Vấn đề | Bằng chứng | Kiểm chứng | Hướng sửa |
|---|---|---|---|---|---|
| R1 | C | **`graph_get_related_context` luôn báo `GRAPH_NOT_READY` trong `vgar run` / `vgar chat`.** Tool này cần `VGAR_TOKENIZER_MANIFEST`, mà không đường agent nào đặt biến này. `vgar run` còn không đặt `VGAR_REPOSITORY_ROOT`, nên `analyze_patch_impact` cũng hỏng | `graph/factory.py:33-39`, `graph/sqlite_service.py:60`, `:116`; `cli.py:221-223` chỉ đặt `VGAR_LEASE_ROOT`; `agents/chat.py:85` | chạy (thiếu biến thì lỗi; đặt biến thì PASS) | Host truyền `VGAR_TOKENIZER_MANIFEST` và `VGAR_REPOSITORY_ROOT=<lease>` cho server graph |
| R2 | C | **Agent không biết `graph_version`.** 4 tool bắt buộc tham số này, nhưng prompt không ghi giá trị, và không tool nào trả về nó (`repo_summary` là resource, adapter không nạp resource thành tool). Đoán sai thì nhận `GRAPH_NOT_READY` | `cli.py:158-163` (`task_prompt`), `agents/chat.py:28-33`, `cli.py:71` (không đặt `version`) | chạy | Đưa `graph_version` vào prompt, hoặc server dùng phiên bản mặc định khi tham số trống (`VGAR_GRAPH_VERSION`) |
| R3 | C | **Repo demo chưa sẵn sàng:** (1) chưa `git init`; (2) chỉ có 1 test fail (`tests/test_x.py::test_bug`); (3) test này chỉ pass khi sửa **cả** `discounts.is_eligible` (`>` thành `>=`) **và** `checkout` (VAT tính sau chiết khấu). Kịch bản bước 4 ("bug thứ hai giữ nguyên FAIL") vì vậy không đúng | §5, bước 1 và 6 | chạy | Tách thành hai test, mỗi test ứng với một bug; thêm test chặn kiểu sửa ăn gian (SAVE20); `git init` và commit |
| R4 | C | G1 (chưa có repo intake) và G2 (một bản vá mỗi phiên) vẫn còn | `cli.py:483` (`--task` bắt buộc); `mcp/servers/repair_server.py` | đọc | Như `docs/status/m3_demo_chat_gaps_2026-11-05.md` |
| R5 | M | **Server repository chỉ có `read_file`.** Không có tool liệt kê file hay tìm theo nội dung; agent phải biết đường dẫn từ graph | `mcp/servers/repository_server.py:56` | chạy | Chấp nhận được nếu prompt hướng agent dùng `graph_search_symbols` trước |

Những gì đã chạy được trên repo thật:
- `vgar index`: repo demo ra 120 node trong 2,5 s; `src/` của VGAR ra 15.432 node trong 5,4 s.
- `graph_search_symbols`, `repository_read_file` và `execution_run_pytest` đều trả về đúng.
- Selector ngoài danh sách cho phép bị chặn (`SELECTOR_REJECTED`).
- Repo gốc không bị sửa: mọi thao tác chạy trên bản sao.

## 5. Cách tái hiện (06/11)

Không chạy model; mọi file sinh ra đều nằm trong thư mục scratchpad.
1. `pytest -q` trong `vgar-demo-shop` → `1 failed, 10 passed` (`test_x.py::test_bug`: `550000 == 495000`).
2. `vgar index <repo> --db <scratch>/shop.db` → 120 node.
3. Script probe gọi qua `create_mcp_client`, với `VGAR_LEASE_ROOT` trỏ vào bản sao: search, read, run_pytest đều PASS;
   `tests/test_cart.py` bị `SELECTOR_REJECTED`.
4. `graph_find_task_anchors` với `graph_version="guess"` → `GRAPH_NOT_READY`; với đúng hash → PASS, anchor duy nhất là
   `tests.test_x.test_bug`.
5. `graph_get_related_context`: không có `VGAR_TOKENIZER_MANIFEST` → `GRAPH_NOT_READY`; đặt
   `artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json` → PASS, 11 item, không có `is_eligible`.
6. Trên bản sao: chỉ sửa `>=` → vẫn fail (`500000 == 495000`); sửa thêm VAT sau chiết khấu → `11 passed`.

Test (06/11, `-m "not hf and not docker"`, chạy hai đợt): 2297 passed, 20 skipped, 1 xfailed. Chỉ có 1 test fail:
`tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`, có vẻ trùng lỗi harness
đã có từ trước.

## 6. Thứ tự đề xuất

1. R1, R2: nhỏ, chỉ sửa host/prompt, nhưng mở được 4 tool graph cho đường demo.
2. R3: nhóm sửa repo demo, không cần code VGAR.
3. E1, E2: cần có trước khi chạy held-out. E1 chỉ đọc artifact, không cần GPU.
4. E4, E7: sửa cách báo cáo và câu chữ trong protocol (cần M2 duyệt).
5. R4 (G1, G2): theo kế hoạch spec repo intake, làm sau đợt chốt W12.
