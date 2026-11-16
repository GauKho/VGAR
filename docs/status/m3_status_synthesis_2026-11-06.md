# Tổng hợp tình trạng VGAR và danh sách việc cần sửa (06/11/2026)

> **Đọc file này trước khi nhận việc.** File viết để người chưa theo dõi các phiên làm việc trước vẫn hiểu được: vấn đề
> là gì, bằng chứng ở đâu, sửa ở file nào, kiểm bằng cách nào, việc nào cần nhóm quyết.
>
> Trạng thái code: nhánh `m3/w12-all`, commit `3f77fcf6`. Đường dẫn code không có tiền tố tính từ `src/vgar/`; đường
> dẫn khác tính từ gốc repo `D:\kltn\vgar_mcp_mvp_demo`. Số dòng đúng tại commit trên.

## Mục lục

0. Thuật ngữ và bối cảnh
1. Nguồn của bản tổng hợp
2. Môi trường và cách tái hiện
3. Kết luận nhanh
4. Đã có bằng chứng tốt
5. Danh sách vấn đề (25 mục)
6. Việc nhóm phải quyết
7. Kế hoạch 3 tuần và phân công
8. Việc đang làm dở
9. Tài liệu liên quan

---

## 0. Thuật ngữ và bối cảnh

**VGAR là gì.** Hệ thống sửa lỗi Python cấp repo, gồm ba phần:
1. Dựng graph code (symbol, lời gọi hàm, import, test) và lấy context theo graph (phần M1).
2. Cho model Qwen3-4B sinh diff, áp diff vào bản sao repo, rồi verify bằng test và static check (phần M2).
3. Đưa toàn bộ qua các MCP server cho agent LangChain gọi (phần M3).

**Phân vai.** M1: graph, retrieval, harness, môi trường task. M2: repair, verification. M3: MCP, agent, runner, thống kê,
paper. Từ 01/11, người làm M3 viết code cho cả M1 lẫn M3; M2 phải review mọi PR.

| Thuật ngữ | Nghĩa |
|---|---|
| **A0–A3** | Bốn arm của ablation. A0: BM25 + chỉ test. A1: graph + chỉ test. A2: graph + test, syntax, mypy, Ruff. A3: A2 + check API và structural. Config: A0–A2 ở `configs/m2/variants/w10/`, A3 ở `configs/m2/variants/A3.json` |
| **F1–F8** | Các bước của funnel repair (`evaluation/repair/aggregate.py`). F1: sinh xong. F2: diff áp được ở chế độ strict. F3: diff cuối cùng áp được. F4: diff sửa ít nhất 1 file mà gold patch sửa. F5: sửa ít nhất 1 hàm của gold. F6: test trong scope PASS. F7: verifier ACCEPT. F8: F7 **và** harness chính thức chấm RESOLVED |
| **Metric chính đã chốt (03/11)** | F3, F4, Recall@k, FAR/FRR. Resolved (F8) là metric phụ, vì trên dev mọi arm đều 0/25 |
| **FAR / FRR** | Đo trên mutant pool. FAR = tỉ lệ patch hỏng (BAD) được verifier chấp nhận. FRR = tỉ lệ patch tốt (GOOD, là gold patch) bị từ chối |
| **Mutant pool** | Patch hỏng tạo nhân tạo từ gold patch theo 5 loại: `condition_flip`, `import_cycle`, `public_function_delete`, `signature_change`, `test_skip` |
| **Vector / `verify_once`** | Verify một patch cố định **một lần** với đủ mọi check, lưu kết quả thành "vector". Sau đó `derive_verdict` suy ra verdict cho từng arm mà không chạy lại (`evaluation/repair/verifier_eval.py`) |
| **R1** | Bảng retrieval: graph so với BM25, Recall@k/MRR trên dev, budget 8.000 token |
| **Bundle / handoff** | Gói context M1 xuất cho M2: `context.json`, `context_manifest.json`, `test_links.json`. Budget của bundle repair là 1.500 token (`configs/m1/w9_bundle_profile_repair.json:8`) |
| **Snapshot / `graph_version`** | Mỗi lần dựng graph tạo một snapshot trong SQLite, tên là hash nội dung, dạng `sha256:…` (71 ký tự). Tool graph dùng tên này để chọn đúng snapshot |
| **Anchor / grounding** | Điểm xuất phát trên graph, tìm từ mô tả lỗi và test fail (`graph/grounding.py`) |
| **Lease / bản sao** | Agent và engine không bao giờ sửa repo gốc; mọi thao tác chạy trên bản sao (worktree) do host cấp |
| **Ba đường chạy agent** | (1) **Batch A0–A3**: `evaluation/repair/runner.py` → `repair.pipeline.run_repair`; không có agent; sinh 1 lần. (2) **`vgar solve --agent`**: `agents/tool_agent.py`; agent chọn 6 tool không tham số; diff do generator V11 sinh; tối đa 3 lần thử. (3) **`vgar run`** (chỉ đọc) và **`vgar chat`**: agent có tool graph, repository, execution (và repair trong chat) |
| **Constrained agent** | Cách gọi đường (2) trong luận văn: host dựng context và giữ diff; agent chỉ chọn bước tiếp theo |
| **X2b** | Ba lần chạy `solve --agent` thật (Qwen) trên 5 task dev, ngày 03–04/11, dùng để làm bảng RQ5 (MCP usability) |
| **Repo demo** | `D:\kltn\vgar-demo-shop\vgar-demo-shop`: shop/ gồm cart, catalog, checkout, discounts, money, shipping, tax; dùng để demo trước hội đồng |
| **MCP server** | 4 server ở `mcp/servers/`: `graph`, `repository`, `execution`, `repair`. Agent gọi qua `langchain-mcp-adapters` |

---

## 1. Nguồn của bản tổng hợp

| Mã | Nguồn | Nội dung |
|---|---|---|
| **[A]** | `docs/status/m3_system_audit_2026-11-06.md` | Metric, thống kê, thuật toán retrieval, chạy trên repo thật |
| **[B]** | `docs/status/m3_workflow_latency_audit_2026-11-06.md` | Workflow, tool server, latency, đối chiếu proposal và plan 16 tuần |
| **[R]** | Review ngoài: `C:\Users\nlhnh\Downloads\BAO_CAO_REVIEW_VGAR.md` (cùng commit `3f77fcf6`) | Findings F01–F09, smoke trên `psf__requests-1766`, phân tích metric. **File nằm ngoài repo**; nếu cần chia sẻ thì chép vào `docs/reviews/` |
| **[P]** | `docs/status/m2_w12_pool_dev_results_2026-11-06.md` | Kết quả mutant pool trên dev (138 slot) và danh sách việc M2-T1…T11 |
| **[S]** | Smoke `analyze_patch_impact` ngày 06/11 (§2.3) | Kiểm tool impact trên diff SWE-bench thật |

Cột "Xác minh" trong §5:
- **đã chạy**: tái hiện bằng lệnh;
- **đã đọc code**: suy từ code, chưa chạy;
- **kiểm lại**: finding của [R] đã kiểm lại trên checkout này;
- **chỉ [R]**: chưa kiểm lại, chỉ dựa theo review.

---

## 2. Môi trường và cách tái hiện

### 2.1. Máy

| Thành phần | Giá trị |
|---|---|
| Windows | Repo `D:\kltn\vgar_mcp_mvp_demo`, venv `.venv` (Python 3.11.0) |
| WSL (Ubuntu) | Venv `~/vgar/.venv`; dữ liệu task SWE-bench `~/w10` (checkout ở `~/w10/repositories/<task_id>`); clone chạy X2b `~/vgar-x2b` (commit `eded53cb`, **cũ hơn** HEAD); clone chạy pool `~/vgar-a3` |
| GPU | Một máy, RTX 4050 Laptop 6 GB. Chỉ máy này có Docker và image của 25 task dev. Mọi job GPU/Docker chạy **lần lượt**, không chạy song song |
| Tokenizer đang ghim | `artifacts/m2/w5-w6/tokenizer_manifest.json` (theo `configs/m2/demo.json:16`) |

### 2.2. Lệnh test

```bash
.venv/Scripts/python.exe -m pytest -q -m "not hf and not docker"
```

Ngày 06/11: 2.297 passed, 20 skipped, 1 xfailed, mất khoảng 32 phút.
- Chỉ có 1 test fail: `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`. Có
  vẻ là lỗi đã có từ trước (ghi nhận 02/11), chưa ai tìm nguyên nhân.
- Chạy test sẽ ghi đè `artifacts/sample_graph.db` (README đã cảnh báo). Chạy xong thì `git checkout artifacts/sample_graph.db`.

### 2.3. Tái hiện các phát hiện về repo thật (không cần model, không cần Docker)

1. Baseline repo demo: `pytest -q` trong `vgar-demo-shop` → `1 failed, 10 passed` (`tests/test_x.py::test_bug`,
   `550000 == 495000`).
2. Dựng graph: `.venv/Scripts/vgar.exe index <repo> --db <thư mục tạm>/shop.db` → 120 node trong khoảng 2,5 s. Với
   `src/` của VGAR: 15.432 node trong khoảng 5,4 s.
3. Gọi tool qua MCP: dùng `vgar.mcp.client.create_mcp_client(servers=(...), extra_env={...})` rồi `tool.ainvoke(args)`,
   với các biến môi trường:
   - `VGAR_GRAPH_DATABASE=<db>`;
   - `VGAR_LEASE_ROOT=<bản sao>` (cho repository/execution);
   - `VGAR_ALLOWED_SELECTORS='["tests/test_x.py::test_bug"]'`;
   - `VGAR_REPOSITORY_ROOT=<repo đã index>` và `VGAR_TOKENIZER_MANIFEST=<tokenizer ở §2.1>` (cho tool graph theo task).

   Script probe đã dùng nằm trong scratchpad của phiên, không nằm trong repo. Spec
   `docs/superpowers/specs/2026-11-06-m3-demo-graph-tools-design.md` sẽ thêm script giữ lại là
   `scripts/smoke_demo_graph_tools.py`.
4. **Smoke impact [S]:**
   - Trên WSL: `PYTHONPATH=/mnt/d/kltn/vgar_mcp_mvp_demo/src ~/vgar/.venv/bin/python <script>`.
   - Script gọi `agents.runtime.impact_graph_tool(settings, ~/w10/repositories/django__django-10914, <db>)` rồi gọi tool
     với `applied.diff` của
     `~/vgar-x2b/results/m3/w12/agent/20261104T050429Z/20261104T052927829968Z-a6d172867dea/`.
   - Kết quả lưu ở `/tmp/vgar-impact-smoke/result.json` trên WSL. `/tmp` có thể bị xóa khi khởi động lại; cần thì chép ra.

---

## 3. Kết luận nhanh

| Mảng | Tình trạng |
|---|---|
| Hạ tầng (graph, SQLite, MCP, sandbox, audit) | **Chạy được** trên repo thật: demo shop, `src/` VGAR, requests [R], django [S] |
| Retrieval / grounding | Chạy được, nhưng **hay lệch trọng tâm**: trên cả 3 repo thử, file hoặc hàm có lỗi không lọt vào context |
| Verifier | Logic test chặt. **A3 hiện từ chối mọi patch** vì check API ra `NOT_RUN` ở 133/133 vector [P]. **A2 có FRR 48%** vì mypy từ chối 10/23 patch gold [P] |
| Metric | Công thức đúng định nghĩa; **chưa có code** cho McNemar/Holm; bootstrap mới chạy 2.000 vòng thay vì 10.000 |
| Agent / demo | `solve --agent` chạy được. `run`/`chat` trên repo thật **chỉ dùng được 3/7 tool graph**. Repo demo chưa sẵn sàng |
| Kết quả nghiên cứu | 0 resolved trên dev. R1: graph chưa hơn BM25 (delta −0,091, CI95 [−0,292; 0,121], 22 cặp). Chưa có A3 thật, chưa có FAR/FRR chính thức |

**Smoke impact [S], chi tiết:**
- Status **PASS** ở HEAD `3f77fcf6`: 2 method bị đổi, 21 node phụ thuộc. Cùng diff đó ở run X2b 04/11 trả
  `INVALID_ARGUMENT`, vì clone `eded53cb` cũ hơn commit sửa lỗi `ad0aa740`.
- **Chậm:** mỗi lần gọi khoảng 43 s, kể cả khi DB đã dựng xong (xem #18).
- **Phản hồi gây hiểu nhầm:** dòng phản hồi ghi "0 test(s)" nhưng ngay sau đó liệt kê các module `tests.*`.
- **Chưa kiểm:** agent có tự gọi tool impact rồi đưa kết quả vào prompt của lần thử lại hay không. Phần này cần model
  thật: `scripts/check_agent_impact_real.py`; người dùng tự chạy job GPU.

---

## 4. Đã có bằng chứng tốt (không cần sửa)

- **Verify chặt** [A][R]:
  - baseline phải tái hiện được lỗi;
  - test thiếu, skip hay error không bao giờ thành PASS (`repair/verification.py:57`, `assess_transition`);
  - có kiểm path policy, fingerprint source và phát hiện thay đổi ngoài file đã vá (`PROTECTED_SOURCE_CHANGED`).
- **Metric đúng định nghĩa** [A][R]:
  - F1–F8 và Recall@k/MRR khử trùng lặp trước khi lấy k (`evaluation/retrieval/metrics.py`);
  - FAR/FRR: BAD là lớp dương;
  - mẫu số funnel repair giữ toàn bộ quần thể;
  - cổng fairness chặn mọi khác biệt ngoài `arm` và `required_checks` (`evaluation/repair/fairness.py`);
  - `A0 == A1` trên mutant pool được assert (`verifier_eval.py:595`).
- **Security** [A][B]:
  - path jail;
  - allowlist selector (selector ngoài danh sách bị `SELECTOR_REJECTED`, đã chạy thử);
  - redaction;
  - audit đủ 100% ở cả 3 run X2b.
- **Workflow pipeline A0–A3 khớp plan W7–8:** một lượt retrieve → generate → apply → test → verify (`agents/workflow.py`).

---

## 5. Danh sách vấn đề

Mỗi mục ghi: vấn đề, bằng chứng, hướng sửa, cách kiểm, người làm. Mã **T1–T19** khớp danh sách task trong
`docs/status/plan_3_weeks_defense1_2026-11-06.md`. Mã **M2-Tn** khớp danh sách trong [P] §5.

### 5.1. Chặn số liệu luận văn (phải xong trước khi chạy held-out)

**#1. Chưa có code thống kê theo protocol §9.** [A] E1–E2, [R] §5 · Xác minh: 2 nguồn · Task T4 · Người: M3
- **Vấn đề:**
  - Protocol `docs/protocol_freeze_heldout.md` §9 đăng ký ba phép so sánh (A1/A0, A2/A1, A3/A2) bằng McNemar exact hai
    phía kèm b, c, rồi hiệu chỉnh Holm.
  - `grep -ri "mcnemar\|holm\|binom" src scripts` không ra kết quả.
  - Bootstrap ở `evaluation/retrieval/compare.py:81` mặc định 2.000 vòng, trong khi protocol ghi 10.000.
- **Sửa:**
  - Thêm `evaluation/stats.py`: ghép cặp theo `task_id` từ `rows` của `aggregate.json`.
  - Tính b, c và p hai phía theo nhị thức (b + c, 0,5); Holm cho nhóm 3 phép so sánh.
  - Với FAR/FRR thì ghép theo slot của pool.
  - Chạy bootstrap 10.000 vòng và ghi số vòng vào output.
- **Kiểm:** so với b, c tính tay; Holm với p cho sẵn.

**#2. Check API của A3 hầu như luôn ra `NOT_RUN`.** [R] F03, [P] §4.1 · Xác minh: 2 nguồn (pool thật) · Task T5 / M2-T1 · Người: M2
- **Vấn đề:**
  - Trên pool dev, check `api` ra `NOT_RUN` ở 133/133 vector hợp lệ (`API_UNSUPPORTED_DECLARATION`,
    `API_INHERITED_CONSTRUCTOR`, `API_AMBIGUOUS_BINDING`, `API_UNSUPPORTED_EXPORT`).
  - `assess_compatibility` biến `NOT_RUN` thành ERROR khi API là check bắt buộc, nên A3 có FAR 0% và **FRR 100%**.
  - [R] đo thêm: chỉ 16/168 module VGAR và 12/72 file `requests` phân tích được.
  - Đổi chữ ký `__call__` vẫn ra API PASS, vì vòng lặp bỏ qua mọi tên bắt đầu bằng `_`.
- **File:** `repair/api_check.py:212`, `:225`, `:342`.
- **Sửa (theo quyết định Q2, §6):** check API chỉ xét symbol public mà patch thật sự đổi, để cấu trúc chưa hỗ trợ ở chỗ
  khác trong file không làm cả file `NOT_RUN`; xử lý dunder `__call__`. Làm tối đa 2 ngày. Không đạt thì A3 chỉ báo cáo
  coverage, không chạy McNemar.
- **Kiểm:**
  - Reference patch `multi_file_invoice`: A3 không còn ERROR.
  - Đổi chữ ký `__call__` thì phát hiện được.
  - Trên pool, phần lớn vector có `api` PASS hoặc FAIL.

**#3. Check structural ghi cố định thư mục gốc `src`.** [R] F02 · Xác minh: kiểm lại (`repair/verification_checks.py:123` có `module_roots=['src']`) · Task T6 · Người: M2 + M1
- **Vấn đề:** repo dùng layout `lib` (matplotlib dùng `lib/matplotlib`) bị resolve import sai, nên bỏ sót import cycle.
  [R] tái hiện: cùng byte, root `src` ra PASS, root `lib` ra FAIL `NEW_IMPORT_CYCLE`.
- **File:** `repair/verification_checks.py:102`, `:123`; `graph/builder.py:1516`.
- **Sửa:** ghim riêng import root của từng task (tách khỏi production scope), truyền xuyên builder, bundle, admission và
  evidence structural; bump provenance.
- **Kiểm:** layout `lib/pkg`, patch tạo import cycle → FAIL `NEW_IMPORT_CYCLE`.

**#4. FAR coi run ERROR là "đã từ chối".** [A] E4, [R] §5 · Xác minh: 2 nguồn · Task T7 / M2-T4 · Người: M2
- **Vấn đề:** `confusion_metrics` (`verifier_eval.py:268-292`) tính ERROR là không ACCEPT. Verifier lỗi càng nhiều thì
  FAR càng thấp, tức trông càng tốt. Pool dev có 18–19 BAD ERROR ở A0–A2 và 114 ở A3. Ngoài ra code trả FAR/FRR = N/A
  khi có pool ERROR (2 task bị loại).
- **Sửa:** thêm cột FAR/FRR chỉ tính trên vector đã qualified, kèm FAIL-detection tách khỏi ERROR; quyết định cách xử lý
  2 task bị loại (M2-T4).
- **Kiểm:** pool mà mọi BAD đều ERROR → FAR qualified = N/A, không phải 0.

**#5. Protocol trỏ sai file variant.** [R] §5 · Xác minh: kiểm lại (`docs/protocol_freeze_heldout.md:32-34`) · Người: M3 (sửa tài liệu)
- **Vấn đề:**
  - Protocol §3 trỏ `configs/m2/variants/A0.json`, `A1.json`, `A2.json`: đó là bản W9 (strict/all), không phải bản W10
    (normalized/context) mà runbook dùng.
  - Trộn hai bộ thì cổng fairness sẽ từ chối, và prompt bản W9 vượt cap 6.000 token (sự cố X2b ngày 03/11).
- **Sửa:** đổi sang `configs/m2/variants/w10/A0–A2.json`; A3 giữ `configs/m2/variants/A3.json`.

**#6. Protocol nói sai về F3/F4.** [A] E7, [R] §5 · Xác minh: 2 nguồn · Người: M3 (tài liệu)
- **Vấn đề:**
  - Protocol §8 ghi "F3/F4 đổi gián tiếp qua feedback lượt thử lại". Batch chỉ sinh **một lần**, không có feedback.
  - Với cùng patch: ACCEPT(A3) ⊆ ACCEPT(A2) ⊆ ACCEPT(A1) = ACCEPT(A0). Thêm check chỉ đổi accept/reject, không đổi được
    F1–F6.
- **Sửa câu thành:** "F1–F6 giống nhau giữa A1, A2, A3 vì cùng một lần sinh; chỉ F7, F8 và FAR/FRR khác nhau". Đồng
  thời sửa định nghĩa Recall@k: tính trên thứ tự xếp hạng sau khi khử trùng lặp; "có trong context đóng gói" là metric
  riêng `packed_gold_*_in_context`.

**#7. Regression thực chỉ chạy test tái hiện lỗi.** [R] §4 · Xác minh: chỉ [R] · Người: ghi vào Hạn chế
- `repair/test_selection.py:18` đặt `selected=scope`. Với task chạy qua Docker admission, scope không được mở rộng bằng
  graph. Nhiều task (`requests-1766`, `matplotlib-13989`) chỉ có một file tái hiện lỗi trong `fallback_scope`. Vì vậy F6
  không phải regression suite.

**#8. R1 không đo đúng context đưa vào prompt repair.** [R] §5 · Xác minh: chỉ [R] · Người: M1
- R1 dùng budget 8.000 và tập 25 task khác với tập repair; repair dùng bundle 1.500 token.
- **Sửa:** đo Recall@B=1.500 trực tiếp trên bundle repair, cùng tập task repair. Nếu không kịp thì ghi vào Hạn chế.

**#9. Runner cho chạy lại cả attempt không phải lỗi hạ tầng.** [R] F09 · Xác minh: chỉ [R] · Task T8 · Người: M3
- **Vấn đề:**
  - Research design chỉ cho chạy lại attempt `class=INFRA`.
  - `evaluation/repair/runner.py:176`, `:187` chỉ kiểm target đã TERMINAL và có lý do.
  - `tests/m3/test_runner.py:149` còn chấp nhận chạy lại một attempt PASS.
  - Aggregator lấy attempt TERMINAL mới nhất, nên chạy lại có thể thay kết quả được báo cáo.
- **Sửa:** chỉ cho chạy lại attempt INFRA; muốn chạy lại cho mục đích khác thì dùng nhãn hoặc experiment riêng.
- **Kiểm:** chạy lại attempt PASS/MODEL → bị từ chối.

**#10. Mẫu số so sánh retrieval khác mẫu số repair.** [A] E3, [R] §5 · Xác minh: 2 nguồn · Người: M1 (báo cáo)
- `compare.py:117-120` chỉ ghép task SUCCEEDED ở cả hai run (BM25 N=25, graph N=22 vì 3 task sympy timeout). Báo cáo
  `paired_tasks` cạnh mọi Recall@k; không lấy hiệu hai mean khác N làm delta ghép cặp.

**#10b. (Bổ sung từ [P]) mypy làm FRR của A2 lên 48%.** [P] §4.2 · Task M2-T2 · Người: M2
- 10/11 patch gold bị A2 từ chối là do `TYPECHECK_FAILED`. Các task: matplotlib-13989, xarray-3993, pylint-4604,
  sympy-11618, astropy-13453, matplotlib-20488, xarray-4629, sphinx-11510, astropy-13977, matplotlib-20676.
- **Kiểm:** lỗi mypy mới là thật, hay do so với baseline sai (line map, cách định danh diagnostic). Có giải thích cho
  từng task.

### 5.2. Chặn demo trên repo thật

**#11. Tool graph thiếu biến môi trường trong `vgar run` / `vgar chat`.** [A] R1 · Xác minh: đã chạy · Task T1 · Người: M3
- **Vấn đề:**
  - `get_related_context` cần `VGAR_TOKENIZER_MANIFEST` (`graph/factory.py:33-39`, `graph/sqlite_service.py:60`); không
    đường agent nào đặt biến này.
  - `vgar run` còn không đặt `VGAR_REPOSITORY_ROOT` (`cli.py:221-223` chỉ đặt `VGAR_LEASE_ROOT`), nên
    `analyze_patch_impact` cũng hỏng (`sqlite_service.py:116`).
  - Thiếu biến thì báo `GRAPH_NOT_READY`; đặt biến thì PASS (đã thử).
- **Sửa:** theo spec `docs/superpowers/specs/2026-11-06-m3-demo-graph-tools-design.md`, Task B.

**#12. Agent không biết `graph_version`.** [A] R2 · Xác minh: đã chạy · Task T2 · Người: M3
- **Vấn đề:**
  - 4 tool (`find_task_anchors`, `get_related_context`, `get_related_tests`, `analyze_patch_impact`) bắt buộc truyền
    chuỗi hash 71 ký tự.
  - Prompt không ghi chuỗi này (`cli.py:158-163`, `agents/chat.py:28-33`), và không tool nào trả nó về.
  - Truyền `"guess"` → `GRAPH_NOT_READY`.
- **Sửa (đã chọn cách "cho phép bỏ trống"):** spec trên, Task A. Bỏ trống thì server dùng snapshot đang phục vụ; truyền
  sai vẫn báo lỗi. `task_id` cũng cho bỏ trống.

**#13. Repo demo chưa sẵn sàng.** [A] R3 · Xác minh: đã chạy · Người: M1
- **Vấn đề:**
  1. Chưa `git init`, mà bước dựng task cần git HEAD.
  2. Chỉ có 1 test fail.
  3. Test đó **chỉ pass khi sửa cả hai bug**: `shop/discounts.py` `is_eligible` dùng `>` (phải là `>=`), và
     `shop/checkout.py` tính VAT trên subtotal (phải trên subtotal − discount). Đã thử trên bản sao: chỉ sửa `>=` thì vẫn
     fail (`500000 == 495000`); sửa thêm VAT thì 11 passed.
  4. Vì vậy kịch bản "bug thứ hai không được nhắc tới vẫn FAIL" chưa chạy được.
- **Sửa:**
  - `git init` rồi commit.
  - Tách `test_bug` thành 2 test, mỗi test cho 1 bug.
  - Thêm test chặn kiểu sửa ăn gian (đổi `min_order` của SAVE10 thành 499_999 vẫn pass hết): ví dụ
    `discount_amount(2_000_000, "SAVE20") == 400_000`.

**#14. Chưa có bước dựng task từ repo; chat chỉ áp được 1 bản vá.** [A] R4 (G1, G2) · Xác minh: đã đọc code · Task T19 (bản đầy đủ) · Người: M3
- **Vấn đề:**
  - `vgar chat --task` bắt buộc file JSON (`cli.py:483`). JSON này còn chứa sẵn mô tả lỗi và file cần sửa.
  - `apply_patch` chỉ chạy khi run đang ở phase `prepared`.
- **Bản tối giản cho demo (đề xuất trong kế hoạch 3 tuần):** `vgar solve --agent --repo PATH --issue "…"`:
  1. chạy pytest ban đầu (test fail là FAIL_TO_PASS);
  2. file được sửa là mọi `.py` không phải test; khóa thư mục test;
  3. revision = git HEAD;
  4. xuất bundle bằng exporter có sẵn;
  5. ghi hash vào `configs/m2/trusted_fixtures.json` (đường native chỉ nhận fixture đã đăng ký hash, xem
     `repair/pipeline.py:19`).

  Dùng lại `AgentRepairHost` (3 lần thử, mỗi lần mở run mới), nên không cần sửa G2. **Chưa có spec.**

**#15. Grounding từ mô tả lỗi viết bằng lời yếu.** [A] A1/A3, [R] §7 · Xác minh: 2 nguồn · Người: ghi vào Hạn chế
- **Bằng chứng:**
  - Repo demo: issue "Checkout with coupon SAVE10…" chỉ sinh đúng 1 anchor (test fail). `is_eligible` không lọt vào 11
    item context (budget 2.000); 5 trong 11 item là test.
  - `requests-1766` [R]: cả graph lẫn BM25 không lấy được `requests/auth.py` ở B=1.500 và B=8.000.
- **Nguyên nhân:** VGAR so khớp bằng trùng từ (`_words`, `graph/source_evidence.py` `similarity`), không dùng embedding.
- **Không sửa trước bảo vệ:** đổi ranking sẽ đổi hash đã đóng băng. Chọn điểm xuất phát bằng embedding là Hướng phát
  triển.

### 5.3. Vận hành và độ tin cậy

| # | Vấn đề | Bằng chứng | Xác minh | Task | Sửa |
|---|---|---|---|---|---|
| 16 | Agent bị hủy (Ctrl-C, timeout) thì không đóng run; workspace bị xóa nhưng record chưa được đóng | `agents/tool_agent.py:552-557` chỉ bắt `Exception`; [R] F04 | kiểm lại | T10 | Spec, Task D |
| 17 | Guard junction trên Windows không chạy: Python 3.11 không có `Path.is_junction`, nên inventory và graph discovery có thể đi ra ngoài root | `repair/workspace.py:42`, `:49`, `:82`, `:239`; `graph/builder.py:47`; [R] F01 | kiểm lại (venv 3.11.0, `hasattr` = False) | T11 | Kiểm reparse point, và resolved path phải nằm trong root. Mọi run thí nghiệm chạy trên WSL, nên đây là hạn chế của nền Windows |
| 18 | **Mỗi lần gọi MCP mở một tiến trình server mới**: khoảng 2,3 s/call ở client so với 3–8 ms ở server; impact trên django khoảng 43 s/call | `langchain_mcp_adapters/tools.py:460-466` (không truyền session thì mở session mới); `agents/core.py:44`, `agents/nodes/mcp_repair.py:25` chỉ dùng `client.get_tools()` | đã chạy | T17 | Giữ session suốt phiên và cache graph trong server. **Để sau freeze**, vì sẽ đổi số latency đã đo |
| 19 | Có thể mỗi lần thử lại chạy lại baseline (`get_task_context` p50 khoảng 80–100 s, 2–3 lần mỗi task) | Bảng M1 của X2b | **chưa xác nhận** | T18 | Đọc `repair_server.get_task_context` / `repair/session.py`; nếu đúng thì cache theo (task, revision, policy hash) |
| 20 | `generate_patch` (generator agent) không áp timeout; p95 lên tới 1.035 s | `docs/status/m3.md` (seaborn 856–1.076 s) | đã có sửa trong commit `ad0aa740` | — | Xác nhận trên run mới |
| 21 | Audit completeness ghép theo cửa sổ thời gian ±2 s, có thể đếm thừa | `evaluation/agent_metrics.py:48`; [R] F06 | 2 nguồn | T13 | Ghép theo `request_id` một-một |
| 22 | Comparator tune (`compare_graph_runs`) không kiểm dataset, query hash, corpus hash | `evaluation/retrieval/compare.py:180`; [R] F05 | chỉ [R] | T14 | Dùng lại phần kiểm của `compare_runs` |
| 23 | Metric U1 `affected_node_count` bỏ qua thay đổi nội dung | `graph/incremental.py:56`; [R] F07 | chỉ [R] | T15 | Tính cả node đổi `content_hash`, hoặc đổi tên metric |
| 24 | `pyproject.toml` cho phép `tokenizers<=0.23.0`, nhưng guard chỉ nhận 0.22 | `pyproject.toml:16`, `graph/token_counter.py:69`; [R] F08 | kiểm lại | T12 | Thu hẹp thành `<0.23` |
| 25 | Tool graph không có timeout | `mcp/servers/graph_server.py` | đã đọc code | T16 | Spec, Task E (timeout phía client 120 s) |

### 5.4. Lệch so với proposal (ghi trong Methodology, không phải bug)

Nguồn: `D:\kltn\proposal_vgar_mcp_final_corrected.md` §9–§11; [B] §2–§3.

- **Agent:** là constrained agent, không phải vòng §9.1 (agent tự hỏi graph rồi tự sửa code). Ở X2b, agent làm theo gợi
  ý NEXT của host 40/42 lượt.
- **MCP surface:**
  - Có 8/11 tool của §10.3. Thiếu `build_or_update_graph`, `explain_dependency_path`, `rank_patch_candidates`;
    `verify_patch_graph_constraints` gộp vào `repair_verify_patch`.
  - Có 3/8 resource; adapter không nạp resource cho agent.
  - **0 prompt** MCP.
- **Graph:** graph cú pháp/symbol; chưa có G_arch/CFG/PDG. Impact chưa có DEPENDS_ON/ports.
- **Incremental:** `graph/incremental.py` có code nhưng chưa nối vào đường agent hay verify.
- **Profile patch:** chỉ sửa file có sẵn, tối đa 5 file và 500 dòng [R].

---

## 6. Việc nhóm phải quyết (đầu tuần 09/11)

| # | Câu hỏi | Đề xuất | Lý do |
|---|---|---|---|
| Q1 | A2/A3 có sinh patch riêng không (ĐX1)? | **Không.** Chỉ sinh A0 và A1. Lấy patch A1, chạy `verify_once` → vector → `derive_verdict` cho A2/A3 | Tiết kiệm một nửa thời gian GPU; cùng patch nên so sánh check sạch hơn |
| Q2 | A3 khi check API ra `NOT_RUN` 133/133? | (b) M2 sửa check API tối đa 2 ngày; không đạt thì (a): A3 chỉ báo cáo coverage, không chạy McNemar | Hiện A3 ra FRR 100%, nên phép so A3/A2 chưa có nghĩa |
| Q3 | Timeout (ĐX2) | `generation_timeout` 1.500 s, `global_timeout` 2.700 s cho mọi arm | D15: trung vị 615 ms/token, nên 1.536 token mất khoảng 945 s, vượt hạn 900 s |
| Q4 | Có chạy held-out trước bảo vệ không? N bao nhiêu? | Có, nếu cổng 13/11 PASS; N = 30–40 (khoảng 12 giờ GPU cho A0 + A1) | Không qua cổng thì báo số dev, ghi rõ "dev, khám phá" |
| Q5 | Duyệt spec tool graph cho demo | Chờ người làm M3 duyệt: `docs/superpowers/specs/2026-11-06-m3-demo-graph-tools-design.md` | Mở 4 tool graph cho đường demo |

---

## 7. Kế hoạch 3 tuần và phân công

Chi tiết: `docs/status/plan_3_weeks_defense1_2026-11-06.md`. Giả định: bảo vệ lần 1 khoảng 27/11; một máy GPU.

| Tuần | M3 (kèm code M1) | M2 | M1 (người thứ ba) | Máy GPU |
|---|---|---|---|---|
| **1** (09–15/11) | #11, #12, #16, #25, dòng phản hồi impact (spec tool graph); bước dựng task tối giản (#14); #1; #9; sửa protocol (#5, #6) | #2, #3, #4, #10b, M2-T5 (`nodeids.json`), M2-T6 (xóa `snapshot.tar`); review mọi PR | #13 repo demo; M2-T8 CRLF; dry-run held-out trên 1 task; script đo #8; mẫu cạnh cho edge precision | — |
| **Cổng 13/11** | CI xanh; dry-run PASS; A3 đã có hướng (Q2); FRR A2 có giải thích; ba người ký → tag `protocol-freeze` | | | |
| **2** (16–22/11) | `scripts/make_tables.py`; kịch bản demo | Codebook phân loại lỗi (**viết trước khi xem kết quả**); Methodology repair | Retrieval held-out; bảng R1; bench U1; Methodology graph | Pool chính thức (6–7 giờ) → A0 + A1 held-out (khoảng 12 giờ) → verify cho A2/A3 + chấm harness → chạy thử demo |
| **3** (23–27/11) | Bảng thống kê; slide | Phân tích 10–15 case lỗi repair | Phân tích 10–15 case lỗi retrieval | Tập demo 3 lần với Qwen thật; quay 1 lần chạy thật làm dự phòng |

**Không làm trước bảo vệ, ghi vào Hạn chế / Hướng phát triển:** #7, #8 (nếu không kịp), #15, #17, #18, #21–#23, chat
đầy đủ (G2), embedding cho grounding.

**Quy tắc:**
- Người làm M3 tự commit; không ai commit hộ.
- Không chạy hay dừng job GPU khi chưa hỏi người làm M3.
- Không sửa code giữa lúc đang chạy held-out; có lỗi môi trường thì ghi amendment.

---

## 8. Việc đang làm dở

| Việc | Trạng thái | Ở đâu |
|---|---|---|
| Spec tool graph cho demo (#11, #12, #16, #25, dòng phản hồi impact) | Đã viết và qua reviewer; **chờ duyệt**; chưa có plan, chưa có code | `docs/superpowers/specs/2026-11-06-m3-demo-graph-tools-design.md` |
| Bốn báo cáo 06/11 | Chưa commit | `docs/status/m3_system_audit_2026-11-06.md`, `m3_workflow_latency_audit_2026-11-06.md`, `m3_status_synthesis_2026-11-06.md`, `plan_3_weeks_defense1_2026-11-06.md` |
| Pool dev | Bản duy nhất nằm ở `~/vgar-a3/results/m2/w1112/pool-20261105T062327Z` trên WSL; **cần chép ra D:** (M2-T9) | [P] §1 |
| `artifacts/sample_graph.db` | Bị test ghi đè (đang `M` trong git status) | `git checkout artifacts/sample_graph.db` |

---

## 9. Tài liệu liên quan

| Tài liệu | Dùng để |
|---|---|
| `docs/protocol_freeze_heldout.md` | Protocol held-out (metric §8, thống kê §9); chưa ký |
| `docs/research_design.md` | Thiết kế nghiên cứu, quy tắc chạy lại, D13/D19 |
| `docs/status/m3_a0_a3_plan_2026-11-04.md` | Đề xuất ĐX1–ĐX5, phân tích A1/A2/A3 dùng chung một lần sinh |
| `docs/status/m3_x2b_diagnosis_2026-11-04.md` | Vì sao các lần thử của agent fail; Docker chậm khi model nằm trên RAM |
| `docs/status/m3_demo_chat_gaps_2026-11-05.md` | Kịch bản demo và lỗ hổng G1–G8 của `vgar chat` |
| `docs/m3_w12_agent_runbook.md` | Cách chạy `solve --agent` trên SWE-bench (có bước preflight bắt buộc) |
| `docs/paper/results_draft_v1.md` | Bản nháp Results (các bảng P1, R1, V1/V2, U1, M1, S1) |
| `D:\kltn\project_plan_16_weeks.md` | Plan 16 tuần (bảng ablation và metric tối thiểu ở cuối file) |
| `D:\kltn\VGAR_W9_W16_Deliverables (1).md` | Deliverables v2: bản kế hoạch chính thức, không thay đổi |
| `D:\kltn\proposal_vgar_mcp_final_corrected.md` | Proposal (§9 workflow, §10 MCP, §12 verification) |
