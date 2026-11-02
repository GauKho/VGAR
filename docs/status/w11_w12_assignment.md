# Phân công W11–12 cho M1, M2, M3

> ⚠️ **ĐỀ XUẤT — KHÔNG THAY THẾ DELIVERABLES V2.** Plan chính thức là `D:\kltn\VGAR_W9_W16_Deliverables (1).md` (v2, 19/10/2026). File này chỉ là ghi chú tham khảo để nhóm cân nhắc; mọi thay đổi plan phải được nhóm duyệt và ghi amendment.

> **Ngày:** 31/10/2026 (M3). **Trạng thái:** đề xuất, cần chốt ở buổi họp ngày 1 của W11.
> **Căn cứ:** deliverables v2 W11–12, `docs/status/plan_audit_2026-10-31.md` (§3, §6), `docs/status/w11_w12_remediation_plan.md` (nợ D1–D18, test, bảng).

## 0. Nguyên tắc chia

1. **Theo chủ module** (bảng chủ chính/phụ S5 của v2): nợ nằm trong module của ai thì người đó sửa. Chủ phụ review.
2. **Cân tải:** M1 nhẹ ở W11–12 (v2 Phụ lục D), M3 nặng nhất. Vì vậy M1 nhận thêm việc thuộc graph và harness, M2 nhận các nợ thuộc model backend. M3 giữ security, MCP, đo lường, freeze.
3. **Issue 0,5–2 ngày** (S7). Mã issue là mã deliverable cộng hậu tố; việc mới nằm ngoài v2 dùng mã `-Xn`.
4. **Bảng nào do người đó sinh script.** M3 chỉ ráp Results draft.
5. **Chạy GPU** trên máy của M3: chỉ M3 khởi chạy hoặc dừng.
6. **Mutant pool: phương án A (đã chốt 31/10).** Chạy trên máy M3 vì chỉ máy này có Docker image của 25 task. Chạy **nối tiếp sau khi GPU xong**, không chạy song song (tránh tranh RAM/CPU/ổ đĩa, tránh thêm timeout vào run A1/A2/A3, tránh làm sai số đo M3-W12-1). M2 viết và test toàn bộ code pool trên fixture trong CI trong lúc GPU chạy. Mỗi patch chỉ verify **một lần** với tập check đầy đủ; verdict của A0–A3 được suy ra bằng cách áp policy của từng arm lên cùng kết quả đó (~150 lần verify thay vì ~600).
7. **Luồng agent (đã chốt 31/10).**
   - **`vgar chat`/`vgar run`: vá legacy server, giữ 4 server** (thay phương án (a); spec Q2). `repository_server` chỉ còn `read_file` read-only, bỏ `apply_patch`; `execution_server.run_pytest` vá theo B05. Ghi file chỉ qua `repair_server`. Không tắt `chat`; A5 (chat unification) để sau freeze.
   - **RQ5 lấy số liệu từ `vgar solve --agent`.** Runner A0–A3 gọi thẳng `repair.pipeline.run_repair`, không gọi MCP tool nào, nên không đo được tool call/task, invalid call rate hay audit completeness. Thêm một loạt run nhỏ của `solve --agent`, chỉ để mô tả (không so sánh thống kê với A0–A3).
   - **Paper:** `solve --agent` gọi là "agent bị ràng buộc" (model chọn tool, thời điểm thử lại và dừng; không đọc code, không tự viết diff). Kết quả A0–A3 là của pipeline sinh một lượt, không phải của agent.

## 1. Tổng quan theo thành viên

| | M1 — Graph, retrieval, harness | M2 — Repair, verification | M3 — MCP, đánh giá, paper |
|---|---|---|---|
| **Deliverable v2** | M1-W11-1, M1-W11-2, M1-W12-1, M1-W12-2 | M2-W11-1, M2-W11-2, M2-W11-3, M2-W12-1, M2-W12-2 | M3-W11-1, M3-W11-2, M3-W11-3, M3-W12-1, M3-W12-2, M3-W12-3 |
| **Nợ nhận thêm** | D1 B10, D3 IMPORTS noise, D4 api_risk, D5 anchor, D8 B02, D16 harness ổn định | D10 skip mutant, D11 B01 test HF, D15 phân tích timeout, D17 giữ `policy_hash`, D18 wording | D6 B12 secret, D7 legacy, D9 `vgar run`, D12 pin model, D13 usage, D14 VRAM, quy trình (merge W10, protection, board) |
| **Việc mới (ngoài v2)** | M1-X1 kiểm tay edge (RQ1), M1-X2 phép đo impact (RQ3) | — | M3-X1 Methodology v1 khung (nợ W10) · M3-X2 run `solve --agent` cho RQ5 |
| **Test** | G1–G6, S11 | V1–V15, P2 | S1–S10, S12, S13, M1–M4, P1 |
| **Bảng sinh** | R1, G1, I1, U1 | P1 (cột verify), V1, V2 | P1 (ráp), M1, S1 |
| **Reviewer mặc định** | M3 | M1 | M2 |

## 2. Lịch chi tiết

### Tuần 11

| Ngày | M1 | M2 | M3 |
|---|---|---|---|
| 1 | **Họp 45 phút** (cả nhóm): chốt `docs/m3_w11_decisions.md` (metric chính, timeout, A3 = 25 task không re-plan, chạy lại A1/A2, máy chạy mutant pool) · Rebase lên `main` sau khi W10 merge | **Họp** · Rebase | **M3-W11-0a** merge W10, bật branch protection, tạo issue W11 trên board (0,5) · **M3-W11-0b** cập nhật `Task Status.md` (0,5) |
| 1–2 | **M1-W11-2a** sửa B10 tại `builder.py:1355` + G1, G2 (1) | **M2-W11-1a** `api_check.py`: trích chữ ký bằng `ast`, V1–V5 (1,5) | **M3-W11-2a** vá `repository_server` (chỉ còn `read_file` read-only, root theo lease, bỏ `apply_patch`) và `execution_server.run_pytest` (B05), sửa `smoke_mcp.py`, xử lý `vgar run` (D9), sửa `prompts/system.md` cho khớp; S2, S3, S9, S14, S16 (1,5) |
| 2–3 | **M1-W11-2b** tune ranking trên dev: (a) sau B10, (b) bật `public_api_risk`, (c) giảm IMPORTS hop 2; mỗi bước một dòng bảng R1 + `docs/m1_retrieval_method.md` (1,5) | **M2-W11-2a** `structural_check.py`: cycle IMPORTS mới so baseline (dùng graph sau B10), V6–V8 (1) | **M3-W11-1a** sửa redact B12 (`instrumentation.py:31`), dùng chung một hàm redact, env tiến trình con theo allowlist, S6, S7 (1) |
| 3 | | **M2-W11-2b** rule theo config + `NOT_RUN`, V9 (0,5) | **M3-W11-1b** giới hạn do server đặt (timeout, output trong lúc capture, selector), path jail, S1–S5 (1) |
| 4 | **M1-W11-2c** đóng băng config ranking (hash), G6 (0,5) · **M1-W11-1a** updater incremental: modify, add, delete (1,5, sang ngày 5) | **M2-W11-3a** điền `api_check`/`structural_check` vào `evidence.py`, V10, **V11 giữ `policy_hash` A0–A2** (1) · *PR cần cả 3 người review* | **M3-W11-1c** audit mọi call kể cả lỗi, đánh dấu `untrusted`, graph server read-only, S8, S12, S13 (1) |
| 5 | **M1-W11-1b** relink caller, cache, G3–G5 | **M2-W12-1a** (kéo sớm) `A3.json` + mở rộng fairness, V12 (0,5) · **M2-X1** B01: sửa test HF hoặc `xfail(strict=True)`, P2 (0,5) | **M3-W11-3a** envelope và enum mã lỗi chung trong `mcp/schemas.py`, `docs/mcp_tool_contract.md`, S10 (1) · **M3-X2a** smoke `solve --agent` ở chế độ fake trên 1 dev task SWE-bench, dùng gold patch làm patch kịch bản; máy M3 đang rảnh GPU ở W11; S15 (0,5) |
| Cuối tuần | **Bàn giao H5:** hash ranking đã đóng băng | **Bàn giao H5:** `A3.json` đã merge | Review PR `evidence.py` |

### Tuần 12

| Ngày | M1 | M2 | M3 |
|---|---|---|---|
| 1 | **M1-X3** sửa B02 (decode node id ở biên resource), S11 (0,5) · Nối `signature_changed` từ `api_check` vào `ImpactReport` (0,5) | **M2-W12-1b** A3 smoke 2 task (M3 chạy GPU) · **M2-W12-2a** `build_mutant_pool.py` 5 loại mutant, seed cố định, **chỉ trên fixture, chạy trong CI, không cần Docker**; V13, V14 (1) | **GPU:** chạy lại A1/A2 + A3 × 25 dev (~75 run, ~16 giờ, chạy qua đêm ngày 1–3) · **M3-W12-1a** `local_chat.py` trả usage, sửa `gpu.py`, M1, M2 (1) |
| 2 | **M1-W12-1** `bench_incremental.py`, bảng U1 (1) | **M2-W12-2a** (tiếp) loại "skip test", V15 · **M2-W12-2b** `verifier_eval.py`: verify mỗi patch **một lần** với tập check đầy đủ, suy verdict A0–A3 theo policy; V16 trên fixture; chuẩn bị lệnh chạy cho M3 (1) | **M3-W12-1b** invalid call rate, audit completeness, p50/p95, M3, M4; bảng M1 (1) |
| 3 | **M1-X1** kiểm tay mẫu edge CALLS/IMPORTS/TESTS, trước và sau B10; bảng G1 (1,5) | Kiểm record GPU vừa xong (A3); trực hỗ trợ khi M3 chạy mutant pool | **M3-X1** khung `docs/paper/methodology.md` (1) · **Sau khi GPU xong (H9):** M3 khởi chạy mutant pool trên 25 task (~150 lần verify, ước tính 3–5 giờ; tính lại theo timing W10). **Không chạy khi GPU còn chạy** |
| 4 | **M1-X2** phép đo impact trên gold patch (recall test F2P so với baseline chỉ dùng diff); bảng I1 (1) · **M1-W12-2** dry-run toàn chuỗi held-out trên 2 dev task, **chạy 2 lần** (cổng "harness ổn định"), **sau khi mutant pool xong** vì dùng chung máy (1) | **M2-W12-2c** sinh bảng V1, V2 từ record pool (H10) (0,5) · **M2-X2** phân tích timeout theo arm (độ dài prompt so với thời gian sinh), đề xuất số timeout cho freeze (D15) (0,5) · Cột verify của bảng P1 | **M3-W12-3a** `docs/security_checklist.md` (bảng S1) · ráp Results draft từ R1, P1, V1, V2, I1, G1, U1 (1) · **M3-X2b** tối ngày 4, sau dry-run: `solve --agent` với Qwen thật trên **5 dev task đầu tiên có trạng thái RUNNABLE** theo thứ tự manifest (chọn trước khi chạy), config như A2; ước tính 1–3 giờ |
| 5 | Ký freeze | Ký freeze | Sáng: sinh bảng M1 (RQ5) từ trace của M3-X2b bằng script của M3-W12-1b, đưa vào Results draft (0,5) · **M3-W12-2** `docs/protocol_freeze_heldout.md`: model SHA (D12), prompt hash, budget, timeout (theo M2-X2), hash ranking, manifest hash, metric chính/phụ, thống kê, lệnh từ dry-run; **cả 3 ký**, gắn tag `protocol-freeze`, P1 (1,5) |

## 3. Điểm bàn giao giữa các thành viên

| Mã | Khi nào | Từ → đến | Nội dung | Nếu trễ |
|---|---|---|---|---|
| H1 | W11 ngày 1 | M3 → M1, M2 | W10 đã merge vào `main` | Mọi người làm trên nhánh tạm, rebase sau |
| H2 | W11 ngày 2 | M1 → M2 | B10 đã merge (structural dùng graph sạch) | M2 viết V6–V8 trên fixture, chạy lại sau |
| H3 | W11 ngày 4 | M2 → M1 | Định dạng kết quả `api_check` | M1 để `signature_changed` ở `NOT_COMPUTED` |
| H4 | W11 ngày 4 | M2 → M1, M3 | PR `evidence.py` cần 3 review | Chặn A3, nên review trong ngày |
| H5 | Cuối W11 | M1, M2 → M3 | Hash ranking đóng băng + `A3.json` | **Lùi lịch GPU**: đường găng |
| H6 | W12 ngày 3 | M3 → tất cả | Record GPU xong | Bảng P1 dùng số W10, ghi rõ |
| H9 | W12 ngày 3 | M3 (GPU xong) → M3 | Bắt đầu chạy mutant pool trên máy M3 | GPU trễ thì pool lùi sang tối ngày 3/sáng ngày 4; V1/V2 cuối ngày 4 |
| H10 | W12 ngày 4 sáng | M3 → M2 | Record mutant pool (đường dẫn ngoài Git) | Freeze ghi V1/V2 "đang chờ"; metric chính chốt định nghĩa, không cần số |
| H7 | W12 ngày 4 | M1 → M3 | Dry-run 2 lần không có ERROR hạ tầng (chạy trên máy M3, sau H10) | Không ký freeze; lùi sang W13 ngày 1 |
| H11 | W12 ngày 4 tối | M3 → M3 | Run `solve --agent` (M3-X2b), sau H7 | Freeze vẫn ký với định nghĩa metric RQ5; bảng M1 điền ở W13 ngày 1 |
| H8 | W12 ngày 4 | M2 → M3 | Số timeout đề xuất | Giữ timeout W10, ghi là threat |

## 4. Ma trận review (theo S5 và CODEOWNERS)

| PR thuộc | Người review | Ghi chú |
|---|---|---|
| `src/vgar/graph/`, `evaluation/retrieval/`, harness | M3 (và M2 cho harness) | `graph_server.py` (B02) là file nóng, M3 duyệt |
| `src/vgar/repair/`, `configs/m2/` | M1 | `A3.json` và fairness thì M3 cũng xem |
| `src/vgar/contracts/evidence.py` | **M1 + M2 + M3** | Contract |
| `src/vgar/mcp/`, `agents/`, `evaluation/repair/`, `observability/` | M2 | |
| `configs/mcp.yaml`, `cli.py`, `pyproject.toml` | M3 | PR chỉ chứa thay đổi file nóng đó |
| `docs/protocol_freeze_heldout.md` | Cả 3 ký | |

## 5. Tải (số ngày công ước tính)

| | W11 | W12 | Ghi chú |
|---|---|---|---|
| M1 | ≈ 5 | ≈ 5 | Tăng so với v2 (2 + 2 deliverable): nhận B10, B02, dry-run, RQ1, RQ3 |
| M2 | ≈ 5 | ≈ 4,5 | Kéo A3 config sang W11; nhận B01 và phân tích timeout |
| M3 | ≈ 6 | ≈ 6 + giám sát GPU | Đã chuyển B02, B01, timeout, các bảng của M1/M2 ra ngoài; thêm M3-X2 (RQ5). Nặng nhất: nếu trễ, M3-X2a lùi sang W12 ngày 4 trước M3-X2b |

## 6. Thứ tự cắt nếu trễ (theo Phụ lục A của v2 và quy tắc cắt của plan)

1. Cắt trước: M1-W11-1/M1-W12-1 incremental thu về fixture (bảng U1 chỉ 1 kịch bản); read redundancy; rule layer theo config (M2-W11-2b); M3-X1 Methodology dời sang W13.
2. Cắt sau: M1-X2 (I1) và M1-X1 (G1) giảm cỡ mẫu; M3-X2b giảm còn 3 task; A3 chỉ là phép đo (không vào verdict).
3. **Không cắt:** B10, chạy lại A1/A2 sau tune, mutant pool (V1), security S1–S9, dry-run 2 lần, protocol freeze.
