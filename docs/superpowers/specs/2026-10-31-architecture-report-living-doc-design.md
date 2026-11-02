# Thiết kế: báo cáo kiến trúc thành tài liệu sống và agent demo bảo vệ

> ⚠️ **ĐỀ XUẤT — KHÔNG THAY THẾ DELIVERABLES V2.** Plan chính thức là `D:\kltn\VGAR_W9_W16_Deliverables (1).md` (v2, 19/10/2026). File này chỉ là ghi chú tham khảo để nhóm cân nhắc; mọi thay đổi plan phải được nhóm duyệt và ghi amendment.
>
> **Chưa chốt (31/10):** sau khi viết bản này, M3 chốt thêm: (1) cấu trúc trình diễn lúc bảo vệ = báo cáo kiến trúc hiện tại, giữ đủ 4 MCP server (hướng "vá" legacy server thay vì "gỡ" của M3-W11-2), báo cáo chỉ được bổ sung; (2) thành phẩm = AI coding agent chạy theo query có định dạng `/fix` (`repo`, `bug`, `test`, `files`), sau này thêm query tự do có xác nhận; (3) bản 1 dựa trên `vgar solve --agent` với 5 bước nhỏ. Các mục §4.3 (bỏ server ở W11) và "`chat` chỉ đọc" trong bản này **đã lỗi thời** theo các chốt trên, chưa được viết lại. Ngày bảo vệ: sau W16 (khoảng cách chưa rõ).

> **Ngày:** 31/10/2026 · **Người đề xuất:** M3 (cùng Claude Code) · **Trạng thái:** chờ M3 duyệt, sau đó nhóm duyệt amendment.
> **Liên quan:** `docs/BAO_CAO_KIEN_TRUC_AGENT_LANGCHAIN_LANGGRAPH_MCP_VGAR.md` (báo cáo), `docs/status/plan_audit_2026-10-31.md`, `docs/status/w11_w12_remediation_plan.md`, `docs/status/w11_w12_assignment.md`; `D:\kltn\proposal_vgar_mcp_final_corrected.md`, `D:\kltn\project_plan_16_weeks.md`, `D:\kltn\VGAR_W9_W16_Deliverables (1).md`.
> Đánh dấu **[Quyết định của Claude]** là chỗ chưa được M3 nói trực tiếp; M3 có thể đổi khi duyệt.

## 1. Mục đích và lý do

Nhóm cần hai thứ từ nay tới buổi bảo vệ (diễn ra **sau W16**):

1. **Ở mỗi giai đoạn, mở báo cáo kiến trúc ra là biết bảng đánh giá nào sinh từ đường chạy nào, bằng lệnh nào.** Báo cáo hiện mô tả đúng kiến trúc ngày 27/10, nhưng không nối với bảng đánh giá. Sau W11 (gỡ 2 legacy server) nó sẽ lỗi thời.
2. **Ở buổi bảo vệ, có thứ chạy thật:** mở một repo, gõ vào chat mô tả lỗi, agent tự sửa và verify trong lúc nhóm thuyết trình.

Hai việc tách rời: việc 1 là tài liệu, cần ngay từ W11; việc 2 là phần mềm, viết code ở W13–15. Tài liệu này **thiết kế đầy đủ việc 1**. Với việc 2, tài liệu chỉ ghi **yêu cầu và quyết định đã chốt**; thiết kế kỹ thuật chi tiết nằm ở spec riêng viết trong W12.

## 2. Mục tiêu, ngoài phạm vi, điều phải tránh

**Mục tiêu**
- G1. Báo cáo luôn khớp code ở mỗi mốc (W11, W12, W14, W15, trước bảo vệ).
- G2. Mỗi bảng đánh giá truy ngược được: bảng → đường chạy → lệnh → nơi lưu output → script tổng hợp.
- G3. Demo bảo vệ sửa thành công lỗi thật. Tiêu chí sẵn sàng: tập 10 lần, ít nhất 8 lần PASS, mỗi lần ≤ 40 phút.
- G4. Kết quả nghiên cứu không bị ảnh hưởng bởi việc phát triển demo.

**Ngoài phạm vi**
- Báo cáo không chứa trạng thái tiến độ (đã có `Task Status.md`, `docs/status/m*.md`) và không chứa nội dung Methodology (nằm ở `docs/paper/`).
- Không gộp các đường chạy thành một pipeline. Giữ nguyên nguyên tắc §3 của báo cáo.
- Agent demo không phải arm thí nghiệm và không chạy trên held-out.
- Agent demo không tự viết test tái hiện lỗi.

**Điều phải tránh** (làm đúng kỹ thuật mà vẫn là thất bại)
- A1. Báo cáo chép lại lệnh held-out hoặc lệnh sinh bảng, rồi lệch với protocol freeze hoặc `make_tables.py`.
- A2. Phát triển demo làm đổi đường chạy đã freeze (engine, runner, config, prompt).
- A3. Dùng tỷ lệ thành công của demo làm bằng chứng nghiên cứu (vi phạm "không overclaim", proposal §0).
- A4. Demo thất bại trên sân khấu mà không có dự phòng.
- A5. Gọi agent demo là "A5" khiến người đọc hiểu nhầm đã làm A4 (semantic invariants).

## 3. Ràng buộc

- **Một máy GPU** (laptop RTX 4050, Qwen3-4B, revision `cdbee75f…`). Chỉ M3 khởi chạy hoặc dừng run model. Không chạy hai việc nặng song song (đã chốt cho mutant pool).
- **Protocol freeze cuối W12.** Sau đó chỉ được thêm code; muốn sửa đường chạy đã khóa phải ghi amendment.
- **Deliverables v2 §0:** mỗi lần cập nhật là một PR đã merge, có review; kết quả chạy không commit.
- **Proposal §10.5:** write operation cần xác nhận; command allowlist; audit mọi call.
- **Plan 16 tuần:** demo và UI thuộc nhóm "chỉ làm khi core đã chạy". DoD W15–16: README từ máy sạch chạy được demo, người ngoài nhóm tái tạo được ít nhất một bảng.
- **Tải M3:** W14 có 3 deliverable; W15 phải ráp paper, Dockerfile, script reproduce.

## 4. Việc 1 — Báo cáo kiến trúc thành tài liệu sống

### 4.1. Bản gốc và người chịu trách nhiệm

- Bản gốc là `docs/BAO_CAO_KIEN_TRUC_AGENT_LANGCHAIN_LANGGRAPH_MCP_VGAR.md` trong repo (đã commit ở `92e73afe`). Bản ở `D:\kltn\` có cùng nội dung (chỉ khác CRLF); từ nay chỉ dùng làm bản sao để gửi. **[Quyết định của Claude]**
- M3 cập nhật ở cuối mỗi mốc. M1, M2 cung cấp các dòng bảng và lệnh của phần mình trong PR đó; chủ phụ review theo S5. **[Quyết định của Claude]**
- Giữ định dạng hiện tại: tiếng Việt, Markdown, sơ đồ Mermaid, liên kết tới code.

### 4.2. Phần thêm mới

**§9. Bản đồ bảng đánh giá → đường chạy → lệnh** (mới). Mỗi dòng gồm:

| Cột | Nội dung |
|---|---|
| Bảng | Mã bảng theo `w11_w12_remediation_plan.md` §4 (R1, P1, V1, V2, I1, G1, U1, M1, S1) và bảng tập demo D1 |
| RQ | RQ1–RQ5, hoặc "demo" |
| Đường chạy | Một trong các đường ở §3 của báo cáo, hoặc một script offline |
| Lệnh | **Trỏ tới nguồn gốc**, không chép: protocol freeze (lệnh held-out), `scripts/make_tables.py` (bảng cuối, từ W14), hoặc script của giai đoạn đó (trước W14) |
| Output | Thư mục ngoài Git (ví dụ `~/w10/agg-both-run1`), kèm hash hoặc experiment id |
| Giai đoạn | Mốc bảng được sinh hoặc cập nhật |

Nội dung khởi đầu:

| Bảng | RQ | Đường chạy | Nguồn lệnh | Giai đoạn |
|---|---|---|---|---|
| R1 retrieval | RQ2 | Script đánh giá retrieval offline (BM25, graph) | Script retrieval → freeze → `make_tables.py` | W5–6 → W11 (sau tune) → W13 |
| P1 repair funnel | RQ4 | Runner A0–A3 (`scripts/run_repair_experiment.py`), gọi thẳng engine M2, không qua MCP | `run_repair_experiment.py aggregate` → freeze → `make_tables.py` | W10 → W12 → W13 |
| V1, V2 FAR/FRR | RQ4 | Mutant pool → `verifier_eval.py` | Script M2 → `make_tables.py` | W12 → W14 |
| I1 impact | RQ3 | `analyze_patch_impact` trên gold patch | Script M1 | W12 |
| G1 graph quality | RQ1 | Mẫu edge kiểm tay | Script M1 | W12 |
| U1 incremental | — (§11.3) | `scripts/bench_incremental.py` | Script M1 | W12 |
| M1 MCP usability | RQ5 | `vgar solve --agent` | Script M3-W12-1b | W12 → W13 |
| S1 security | — (§10.5) | Test S1–S15 trong CI | `pytest` | W11 → W12 |
| D1 tập demo | demo | Agent demo (`vgar chat`) | Script tập demo | Sau W16 |

**§10. Lịch sử phiên bản** (mới): mỗi mốc một dòng: ngày, tag, những gì đổi trong kiến trúc, PR.

**§1 (bổ sung):** một đoạn nói rõ báo cáo là tài liệu sống, phạm vi theo §2 của thiết kế này, và hai loại kết quả (nghiên cứu và demo).

### 4.3. Nội dung cập nhật theo từng mốc

| Mốc | Thay đổi trong báo cáo |
|---|---|
| **W11** (sau M3-W11-2/3) | §3, §4, §5.1, §6.2: bỏ `repository_server` và `execution_server` khỏi bảng và sơ đồ; còn 2 server (graph, repair). `vgar chat`/`run` chỉ đọc (hỏi đáp trên graph) cho tới khi có agent demo, vì tool `get_task_context` của repair server bắt buộc có `TASK.json`. Envelope và mã lỗi chung. Tạo §9 với các dòng đã có số (R1, P1 của W10), §10 |
| **W12** (protocol freeze) | §3 thêm đường chạy runner thí nghiệm (hiện thiếu). Ghi `solve --agent` là nguồn dữ liệu RQ5. §9 trỏ lệnh held-out về `docs/protocol_freeze_heldout.md`. Thêm API/structural check vào §7.1 |
| **W14** (`results-v1`) | §9 trỏ bảng cuối về `make_tables.py` |
| **W15** (`demo-rc`) | Thêm đường chạy agent demo vào §3, §5 (sơ đồ riêng) và §6. Ghi rõ dùng chung engine M2 với `solve --agent` nhưng là đường khác runner thí nghiệm |
| **Trước bảo vệ** (`defense`) | Rà lần cuối khớp tag; thêm dòng D1 |

### 4.4. Kiểm chứng

- Mỗi PR cập nhật báo cáo có một reviewer khác vai trò, kiểm: (a) mọi liên kết code tồn tại; (b) mọi tên server/tool trong sơ đồ khớp `configs/mcp.yaml` và `vgar tools`; (c) mọi dòng §9 trỏ được tới lệnh hoặc file thật.
- Ở các tag `protocol-freeze`, `results-v1`, `defense`: kiểm thêm rằng chạy theo §9 ra lại được bảng.

## 5. Việc 2 — Agent demo bảo vệ (yêu cầu đã chốt)

### 5.1. Kịch bản

1. Đầu buổi thuyết trình, nhóm mở một **repo chuẩn bị trước, có lỗi thật và một test đang fail** chứng minh lỗi.
2. Nhóm gõ vào chat một câu mô tả lỗi bằng lời thường.
3. Agent chạy nền trong khoảng 40 phút thuyết trình: tìm chỗ qua graph, sinh bản sửa, áp vào bản sao riêng của repo **qua engine M2** (repair server), chạy test, verify, thử lại có giới hạn.
4. Agent ghi từng bước của mình để hiển thị.
5. Kết quả: sửa gì, ở đâu, vì sao, kèm diff và bằng chứng verify. **Thành công = verdict ACCEPT của engine M2.**

### 5.2. Tiêu chí và dự phòng

- **Sẵn sàng:** tập 10 lần trên tag `demo-rc`, ít nhất 8 lần PASS, mỗi lần ≤ 40 phút (điều kiện 40 phút: **[Quyết định của Claude]**).
- **Dự phòng:** lần trên sân khấu thất bại thì chạy lại ngay; không kịp thì chiếu video quay từ một lần tập thành công thật. Bắt đầu demo ngay đầu buổi. Dùng thời gian đo được khi tập để đặt mốc "còn kịp chạy lại"; quá mốc thì chuyển sang video. **[Quyết định của Claude]**

### 5.3. Ràng buộc để khớp ba tài liệu

| # | Ràng buộc | Lý do |
|---|---|---|
| C1 | Gọi là **"agent demo"**, không gọi "A5". Nếu cần nhãn ablation thì ghi amendment "A5′ = A3 qua MCP agent" | Plan định nghĩa A5 = A4 qua MCP agent; A4 đã cắt |
| C2 | Có **chế độ fake chạy trên CPU** (`ScriptedRepairAgent`) để README và người ngoài nhóm chạy được | DoD W15–16 của plan |
| C3 | Chỉ ghi vào worktree riêng. **Không ghi ngược vào repo gốc**; nếu sau này cần thì phải có xác nhận của người dùng | Proposal §10.5 |
| C4 | Tỷ lệ tập 8/10 là độ sẵn sàng demo, trên repo tự chuẩn bị; **không đưa vào Results như bằng chứng RQ** | Proposal §0 |
| C5 | Chỉ thêm code; không sửa engine M2, runner, config hay prompt đã freeze | Deliverables v2 §0, protocol freeze |
| C6 | Thuộc nhóm **cắt trước** nếu trễ (sau incremental, read redundancy) | Quy tắc cắt scope của plan; tải M3 W14–15 |

### 5.4. Để lại cho spec W12

Cách dựng task từ câu chat cộng với test fail; giao diện hiển thị (log hay UI mỏng); dùng lại `AgentRepairHost` của `tool_agent.py` tới đâu; cách chọn lỗi demo; nội dung video; người review.

## 6. Chiến lược ổn định: vừa phát triển vừa có kết quả

Hai luồng dùng chung engine nhưng không đổi cùng lúc: **luồng đóng băng** (kết quả nghiên cứu) và **luồng phát triển** (demo, tài liệu).

1. **Tag ở mỗi mốc**, và thuyết trình/demo chạy từ tag, không chạy từ `main`:

   | Tag | Khi nào | Nội dung |
   |---|---|---|
   | `w10-dev` | W11 ngày 1 (merge W10) | Bảng A0–A2 dev |
   | `protocol-freeze` | Cuối W12 | Engine, runner, config, prompt, model SHA đã khóa |
   | `results-v1` | Cuối W14 | Bảng held-out, thống kê, `make_tables.py` |
   | `demo-rc` | Cuối W16 | Agent demo chạy model thật |
   | `defense` | Trước bảo vệ | Bản mang lên sân khấu, đã tập 8/10 |

2. **Sau freeze chỉ thêm code**, có test canh: `policy_hash` không đổi (V11), fairness (V12), khóa held-out (P1).
3. **Kết quả sinh lại được:** bảng sinh từ record bằng script, chạy 2 lần giống từng byte. **Sao lưu record ra ngoài laptop** (ổ ngoài hoặc cloud) ở mỗi mốc. Ghi digest Docker image; **không prune Docker từ W12 tới hết bảo vệ**.
4. **CI dùng fake cho mọi PR; GPU chỉ chạy ở mốc** (W12 dev, W13 held-out, tích hợp demo, tập demo). Thứ tự ưu tiên máy GPU: thí nghiệm, rồi mutant pool, rồi demo.
5. **Đóng code:** từ `demo-rc` chỉ sửa lỗi, mỗi lần sửa phải tập lại đủ 10 lần; 3–5 ngày trước bảo vệ không đổi code.
6. **Hai loại kết quả trình bày tách nhau:** bảng nghiên cứu từ `results-v1` lên slide; demo minh họa cơ chế. Demo trục trặc không ảnh hưởng kết quả đồ án.

## 7. Lịch tổng hợp

| Tuần | Luồng đóng băng | Luồng phát triển |
|---|---|---|
| W11 | Phát triển trên `main` qua PR | Báo cáo bản W11 |
| W12 | Freeze → tag `protocol-freeze` | Báo cáo bản W12; spec agent demo |
| W13 | Chạy held-out từ tag | Agent demo trên fake (nhánh riêng) |
| W14 | Thống kê, `make_tables.py` → `results-v1` | Báo cáo bản W14 |
| W15 | Không đổi | Agent demo với model thật khi GPU rảnh; báo cáo bản W15 |
| W16 | Không đổi; paper bản cuối, người ngoài nhóm chạy README (fake mode) | Ổn định demo → tag `demo-rc` |
| Sau W16 → bảo vệ | Không đổi | Tập 10 lần, quay video, đóng code → tag `defense` |

Vì bảo vệ diễn ra sau W16, việc tập demo dời ra sau W16. W15–16 của M3 ưu tiên paper và artifact. **[Quyết định của Claude]**

## 8. Những gì để lại cho người làm

Chi tiết câu chữ và bố cục của §9, §10; cách kiểm liên kết (tay hay script); nơi sao lưu record; tên script tập demo.

## 9. Tóm tắt quyết định của Claude (để M3 kiểm)

1. Bản gốc báo cáo nằm trong `docs/` của repo.
2. M3 cập nhật báo cáo; M1, M2 cung cấp dòng.
3. Điều kiện mỗi lần tập ≤ 40 phút.
4. Mốc "còn kịp chạy lại" lấy từ số đo khi tập; bắt đầu demo ngay đầu buổi.
5. Sáu ràng buộc C1–C6.
6. `chat` chỉ đọc từ W11 tới khi có agent demo.
7. Tag `demo-rc` cuối W16; tập demo sau W16.
8. Không prune Docker từ W12 tới hết bảo vệ; sao lưu record ở mỗi mốc.
