# Đối chiếu kế hoạch và đánh giá tiến độ — 31/10/2026 (M3)

> ⚠️ **ĐỀ XUẤT — KHÔNG THAY THẾ DELIVERABLES V2.** Plan chính thức là `D:\kltn\VGAR_W9_W16_Deliverables (1).md` (v2, 19/10/2026). File này chỉ là ghi chú tham khảo để nhóm cân nhắc; mọi thay đổi plan phải được nhóm duyệt và ghi amendment.

> **Mục đích:** ghi lại kết quả đối chiếu giữa proposal, plan 16 tuần và deliverables W9–W16 với trạng thái thực tế, để phiên làm việc sau tiếp tục được ngay.
> **Người lập:** M3 (cùng Claude Code). **Ngày:** 31/10/2026, ngay sau khi xong W10.
> **Trạng thái tài liệu:** bản đánh giá nội bộ, chưa được nhóm duyệt. Chưa sửa `Task Status.md` hay file deliverables theo các đề xuất dưới đây.

## 0. Nguồn và giới hạn

| Nguồn | Vai trò |
|---|---|
| `D:\kltn\proposal_vgar_mcp_final_corrected.md` | Phạm vi nghiên cứu: RQ1–RQ5, §10.5 security, §11 incremental, §12 verification, §13 evaluation. **Không có lịch theo tuần.** |
| `D:\kltn\project_plan_16_weeks.md` | Yêu cầu và DoD từng giai đoạn; **bảng ablation A0–A5 chính thức**; quy tắc cắt scope |
| `D:\kltn\VGAR_W9_W16_Deliverables (1).md` (v2, 19/10) | Deliverable chi tiết W9–W16 theo M1/M2/M3; quy ước §0: deliverable = PR đã merge vào `main` |
| `Task Status.md` | Trạng thái HT/MP/CT/CX. Số liệu W1–6 của 16/10, W7–8 của 18/10, W9–10 của 30/10 |
| git, code | Kiểm chứng một số điểm (liệt kê trong từng mục) |

Giới hạn:
- Chưa audit lại W1–8 từ đầu. Có dòng đã cũ: **W09-10-M3-02** ghi "retry chưa gọi tool impact", nhưng commit `483f4394` đã làm việc này. Các lỗi B04/B05/B12 có thể đã đổi.
- Mục **CX** (chưa xác minh) có thể đã được làm ngoài repo, chủ yếu là literature, research design, Related Work. Cần hỏi nhóm trước khi coi là "chưa làm".

## 1. Đánh giá từng giai đoạn

| Giai đoạn | HT/MP/CT/CX | DoD của plan | Kết luận | Còn thiếu chính |
|---|---|---|---|---|
| W1–2 Research design | 6/5/0/10 (trên 21) | 0/3: sign-off CX; branch protection **chưa bật** (kiểm 30/10); literature CX | ❌ Chưa đạt | `docs/research_design.md`, literature table, protocol sign-off, pin model revision và budget (CHUNG-03), issue board |
| W3–4 Graph MVP | 16/5/0/1 | Callers/imports hợp lý MP (B10: import ngoài bị nối sai vào nội bộ); kiểm tay 20 edge CX; log HT | ⚠️ Đạt phần lớn | B10; SCIP indexer chưa chạy thật; resource node qua MCP lỗi (B02); sandbox B04 |
| W5–6 Grounding và retrieval | 13/4/1/2 | Bảng Graph vs BM25 HT (22 cặp); kiểm tay 10 task CX | ⚠️ Đạt phần lớn | Subset 50–100 task chạy được (CT); Related Work CX; FailingTest node |
| W7–8 Repair loop | 17/1/0/1 | ≥3 diff hợp lệ HT; không ghi repo gốc HT | ✅ Đạt | Ranking M1-02 (đẩy sang W11); draft Methodology CX |
| W9–10 Impact và A0–A2 | 13/6/1/0 | A0–A2 cùng subset/config HT; bảng kết quả HT | ⚠️ Đạt kỹ thuật, **chưa đạt theo quy ước v2** | Xem bên dưới |
| W11–12 | 1/8/6/1 | — | Chưa tới hạn | `api_check`, structural check, A3, mutant pool, incremental đều CT |
| W13–14 | 0/6/4/6 | — | Chưa tới hạn | Cần protocol freeze trước |
| W15–16 | 1/8/0/7 | — | Chưa tới hạn | — |

Phần còn thiếu của W9–10:
- N = 25/arm, dưới mức 30–50 (D24).
- Methodology v1 (M3-W10-5) là CT, chưa có thư mục `docs/paper/`.
- Impact chưa có risk theo component.
- **W10 chưa merge vào `main`.** 4 commits `62b0222b..483f4394` mới ở `origin/m3/w10-dev-ablation` (push 30/10).
- Cổng W9 còn mở: `main` chưa bật branch protection, PR #2–#4 có 0 review, chưa có Projects board.

Tổng tới W10: **65/102 mục HT (≈64%)**. Toàn dự án: 67/150.

Kết quả thực nghiệm W10: **0 task resolved** ở mọi arm (N=25/arm). Funnel F3 5/6/5, F4 2/4/4, F8 = 0. 6/7 lần `GENERATION_TIMEOUT` rơi vào arm graph A1/A2 (D26: giữ nguyên và báo cáo confound).

## 2. Đối chiếu với các RQ của proposal

| RQ | Hiện có | Khoảng trống |
|---|---|---|
| RQ1 Graph construction | Builder, SCIP/LSP, schema | **Chưa đo precision/recall của edge**; 79% call site chưa resolve; không task nào ở W9–16 nhận |
| RQ2 Retrieval | Bảng dev Graph vs BM25 | CI chứa 0; ranking chưa tune xong |
| RQ3 Patch impact | `analyze_patch_impact` chạy trên patch thật (16/16 ImpactReport) | **Không task nào đo chất lượng impact**, cũng không so với baseline chỉ đọc diff |
| RQ4 Verification | A0–A2, static so với baseline | FAR/FRR để W12; dev 0 resolved |
| RQ5 MCP usability | Agent tự gọi tool qua MCP | Đo latency, token, invalid-call để W12 |

Arch-CPG mới làm tới `G_code` và `G_repo`. Không có `G_arch`. GraphDiff, semantic invariants (Daikon), MCP resources/prompts đầy đủ và embedding baseline không có task. Các phần này khớp quy tắc cắt scope của plan, nhưng cần ghi vào Limitations hoặc amendment.

**Về ablation:** bảng §13.3 của proposal (A1 = repo graph, A2 = issue-aware, A3 = architecture…) **đã được plan 16 tuần định nghĩa lại**: A0 = BM25 + tests; A1 = graph + tests; A2 = A1 + typecheck/lint; A3 = A2 + API/structural; A4/A5 tùy chọn. Code (`configs/m2/variants/A*.json`) và deliverables theo bảng của plan. Không cần amendment mới, chỉ cần Methodology ghi rằng §13.3 đã được thu gọn theo quy tắc cắt scope.

## 3. Đánh giá 15 task W11–12 (deliverables v2)

### Tuần 11

| Task | Plan | Proposal | Đánh giá |
|---|---|---|---|
| M1-W11-1 incremental | Có | §11 | Phù hợp. Không ảnh hưởng kết quả A0–A3 (runner build graph mới cho mỗi task), nên làm sau M1-W11-2 |
| M1-W11-2 ranking | Không (nợ W7–8) | RQ2 | Cấp hơn W11-1: cửa sổ tune cuối trước W13. **Nếu ranking đổi thì phải chạy lại A1/A2 trên dev** trước khi freeze |
| M2-W11-1 api_check | Có | §12.3 | Phù hợp. Mở được `signature_changed` trong ImpactReport |
| M2-W11-2 structural_check | Có ("nếu repo config cho phép") | §12.2 | Phù hợp. Repo SWE-bench không có config nên phần lớn sẽ `NOT_RUN`. Nên dùng rule so với baseline, không cần config: "không thêm cycle mới", "không xóa public port" |
| M2-W11-3 điền evidence | Ngầm trong "verification v2" | §8.5 | Phù hợp; `NOT_RUN ≠ PASS` đúng tinh thần proposal. `evidence.py` là contract nên **cả ba người phải review**. Mở PR sớm để không chặn A3 |
| M3-W11-1 security | Có | §10.5 | Phù hợp. Thiếu hai ý của proposal: write op cần xác nhận; coi text trong repo là untrusted (prompt injection) |
| M3-W11-2 legacy servers | Ngầm trong "command allowlist" | §10.5 | **Bắt buộc.** `configs/mcp.yaml` vẫn đăng ký `repository_server` và `execution_server`; `execution_server.run_pytest` nhận selector tùy ý, nên DoD "MCP tools không chạy command tùy ý" đang trượt |
| M3-W11-3 schema/error | Có | §10.3 | Phù hợp, khớp bảng interface của plan. Mở rộng `tests/test_mcp_tool_contract.py` |

### Tuần 12

| Task | Plan | Proposal | Đánh giá |
|---|---|---|---|
| M1-W12-1 bench_incremental | Có | §11.3 | Phù hợp |
| M1-W12-2 dry-run retrieval | Không | — | Quá hẹp. Cổng W12 "Harness chạy ổn định" **không task nào nhận**. Nên mở rộng thành dry-run toàn chuỗi held-out trên dev (retrieval → runner → harness) |
| M2-W12-1 A3 | Plan đòi "A3 results" | §12 | Pilot 5 task quá ít so với 25 task/arm của A0–A2. Nên chạy cùng 25 dev task. **Bỏ re-plan**: dùng cùng vòng retry với A2, nếu không A3 khác A2 ở hai biến cùng lúc (Phụ lục A cũng xếp re-plan vào nhóm cắt trước) |
| M2-W12-2 mutant pool FAR/FRR | Có ("nếu khả thi") | §13.2 | Nên nâng lên mức giữ bằng mọi giá: metric có tín hiệu khi dev 0 resolved |
| M3-W12-1 đo lường | Có | §13.2 | Thiếu **invalid call rate** và **audit-log completeness** (bảng metrics của plan). `models/huggingface/local_chat.py` chưa trả usage metadata; tái dùng cost fields của M2-W10-2; read redundancy có thể cắt |
| M3-W12-2 protocol freeze | Không (plan W13 chỉ ghi "đã chốt trước") | — | Đúng thời điểm, nhưng cần chốt 3 việc ở §4 |
| M3-W12-3 security checklist, Results draft | Có | — | Phù hợp. Bảng dev A0–A3 cần A3 và A1/A2 (sau tune) đã chạy lại trên dev |

Chat unification (memory 22/10): plan đã có **slot A5 tùy chọn** ("served through full MCP agent workflow"), nên không cần amendment mới. Theo quy tắc cắt scope, nên làm sau freeze hoặc làm dưới dạng demo, không chen vào W11.

## 4. Ba quyết định phải chốt trong protocol freeze (W12)

1. **Metric chính.** Plan W13–14 lấy resolved rate làm chỉ số chính, nhưng dev đang 0/25, nên McNemar sẽ không có cặp lệch nào. Đề xuất: metric chính là funnel F3/F4, Recall@k và FAR/FRR; resolved rate là chỉ số phụ. Phải ghi **trước khi** thấy held-out.
2. **Timeout và budget.** Tăng timeout cho mọi arm, hoặc giữ nguyên và báo cáo là threat (confound timeout ở arm graph).
3. **Config sau khi tune ranking.** Bản freeze dùng config sau M1-W11-2, và bảng dev phải được chạy lại với đúng config đó.

## 5. Việc cần làm tiếp (theo thứ tự)

| # | Việc | Ai | Lý do |
|---|---|---|---|
| 1 | Mở PR và merge W10 (`m3/w10-dev-ablation`), bật branch protection, lấy review | M3 (user commit) | Quy ước §0 v2; DoD W1–2; cổng W9 |
| 2 | Cập nhật `Task Status.md`: lật W09-10-M3-02 sang HT, audit lại các dòng W1–8 đã cũ | M3 | Chỉ M3 sửa file này |
| 3 | `research_design.md`/protocol, pin model, prompt và budget | M3 + nhóm | Gốc cho freeze W12 (nợ W1–2) |
| 4 | M3-W11-2 → M3-W11-1 → Methodology v1 → M3-W11-3 | M3 | Thứ tự ưu tiên W11 |
| 5 | Đề xuất với nhóm: M1 nhận kiểm tay precision/recall edge (RQ1) và "harness ổn định"; thêm một phép đo impact (RQ3), ví dụ impact có chứa file hoặc test mà gold patch chạm tới không, so với baseline chỉ dùng file trong diff | Nhóm | Hai lỗ RQ chưa có task |
| 6 | Sửa W11–12 trong deliverables: A3 chạy trên 25 task, bỏ re-plan, thêm 2 metric MCP, mở rộng dry-run, chạy lại A1/A2 sau tune | M3 soạn, nhóm duyệt | §3 |
| 7 | Lên lịch GPU W12: khoảng 75 run (A1/A2 rerun + A3 × 25 task) ≈ 16 giờ máy với 13 phút/task | M3 (user chạy GPU) | Compute |
| 8 | Hỏi nhóm các mục CX (literature, Related Work, research design) có bản ngoài repo không | M3 | Tránh đánh giá sai |
| 9 | Đưa các phần cắt (GraphDiff, `G_arch`, Daikon, embedding baseline) vào Limitations | M3 | Không overclaim |

## 6. Đề xuất xử lý nợ tồn đọng trước khi vào W11–12

Nguyên tắc: không trả hết nợ rồi mới bắt đầu W11. Chỉ nợ nào **chặn W11 hoặc chặn protocol freeze** mới phải xử lý trước. Phần còn lại chạy song song hoặc dời đến lúc chờ máy (W13), giống cách S6 của v2.

### 6.1. Nhóm A — làm ngay, ngày 1–2 của W11 (chặn bắt đầu)

| # | Nợ | Cách xử lý | Ai | Kiểm chứng |
|---|---|---|---|---|
| A1 | W10 chưa merge; cổng W9 và DoD W1–2 về branch protection/review | Mở PR từ `m3/w10-dev-ablation`. 4 commits đã tách theo vai trò, CODEOWNERS tự gán M1/M2 review. Bật branch protection trên `main` (1 review + CI `tests.yml`). Tạo issue W11 trên Projects | M3 (thao tác GitHub web; máy không có `gh`) | PR merge; PR thử không review bị chặn |
| A2 | `Task Status.md` có dòng đã cũ | Lật W09-10-M3-02 sang HT. Kiểm nhanh B02/B04/B05/B12 trong code hiện tại, ghi trạng thái thật | M3 | Dòng 9–10 và W11–12 khớp code |
| A3 | Các quyết định chưa ai chốt (§4 và §3) | Họp 45 phút, ghi vào `docs/m3_w11_decisions.md`: metric chính; timeout; A3 = 25 task, không re-plan; chạy lại A1/A2 sau tune; M1 nhận kiểm tay edge, harness ổn định, phép đo impact (RQ3); hỏi các mục CX có bản ngoài repo không | Cả nhóm, M3 ghi | File quyết định có đủ 3 người đồng ý |

### 6.2. Nhóm B — làm song song trong W11, xong trước freeze W12

| # | Nợ (giai đoạn gốc) | Cách xử lý | Ai |
|---|---|---|---|
| B1 | Research design và protocol (W1–2 CHUNG-01/06, M3-02) | Không viết lại từ đầu. Ráp từ spec W9, quyết định D13–D26, kiểm fairness có sẵn, thêm RQ, hypothesis và metric. Bản này là khung của `protocol_freeze_heldout.md` (M3-W12-2) | M3 |
| B2 | Pin model, prompt, budget (W1–2 CHUNG-03) | Ghi HF revision SHA của model, prompt hash, budget và timeout từng stage vào protocol | M3 |
| B3 | Sign-off scope (W1–2 DOD-01) | Gộp với chữ ký protocol freeze ở W12: một lần ký cho cả hai | Cả nhóm |
| B4 | Lỗi B10, nối sai import (W3–4 M1-05, DOD-01) | Sửa cùng đợt tune ranking M1-W11-2, vì B10 làm nhiễu cả retrieval lẫn impact. Phải xong trước khi chạy lại A1/A2 | M1 |
| B5 | Kiểm tay ≥20 edge (W3–4 DOD-02) | Làm sau B4, mở rộng thành mẫu precision/recall cho RQ1 | M1 |
| B6 | Kiểm tay 10 task retrieval (W5–6 DOD-02) | Làm trên lần chạy retrieval sau tune, theo rubric lưu trong repo | M1 |
| B7 | Legacy servers và sandbox (W3–4 M2-01, M3-02; B02/B04/B05/B12) | Chính là M3-W11-2 và M3-W11-1: làm đầu tiên trong W11 | M3 |
| B8 | Methodology v1 (W7–8 M3-04, W9–10 M3-03/04) | Time-box 1,5 ngày: khung `docs/paper/methodology.md` (system overview, experimental design). M1/M2 viết bản cuối phần của mình ở W13 như v2 đã định | M3 |

### 6.3. Nhóm C — dời lại hoặc ghi amendment, không chặn W11–12

| Nợ | Xử lý |
|---|---|
| Literature table, Related Work (W1–2, W5–6) | Hỏi bản ngoài repo trước (A3). Nếu chưa có: mỗi người 8–10 bài theo mảng, làm trong W13 lúc chờ held-out |
| Subset 50–100 task (W5–6 M3-03) | Amendment: thay bằng dev N=25 (D24); N của held-out chốt trong protocol |
| FailingTest node (W5–6 M1-03) | Amendment: chấp nhận biểu diễn tương đương (Test → Issue) |
| SCIP indexer chưa chạy thật (W3–4 M1-04) | M1 xác nhận bundle hiện dùng resolver nào; nếu không dùng SCIP thì ghi limitation |
| Impact risk theo component | Cắt, ghi limitation (không có `G_arch`) |

### 6.4. Lịch đề xuất

| Thời điểm | Việc |
|---|---|
| W11 ngày 1 | A1, A2 |
| W11 ngày 1–2 | A3 (họp quyết định) |
| W11 ngày 2–5 | M3: B7 → B1/B2 → B8 → M3-W11-3 · M1: B4 + M1-W11-2 → B5, B6 · M2: M2-W11-1..3 |
| W12 đầu tuần | Chạy GPU: A1/A2 rerun + A3 trên 25 task (~75 run, ~16 giờ máy) |
| W12 cuối tuần | Ký protocol freeze (gồm B3) |

Chi tiết kỹ thuật, test case và mẫu bảng đánh giá cho W11–12: xem `docs/status/w11_w12_remediation_plan.md`. Phân công theo thành viên và lịch theo ngày: `docs/status/w11_w12_assignment.md`.

**Tiêu chí "sẵn sàng vào W11":** W10 đã merge; branch protection bật; `docs/m3_w11_decisions.md` có 3 người đồng ý; issue W11 đã có trên board.
