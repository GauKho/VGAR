# Kế hoạch 3 tuần tới bảo vệ lần 1 (đề xuất, 06/11/2026)

> **ĐỀ XUẤT, CHƯA ĐƯỢC NHÓM DUYỆT.** Không thay thế deliverables v2; chỉ sắp lại thứ tự cho 3 tuần còn lại.
> Nguồn: `m3_status_synthesis_2026-11-06.md` (25 vấn đề, task T1–T19), `m2_w12_pool_dev_results_2026-11-06.md`
> (kết quả pool trên dev, việc M2 T1–T11), `D:\kltn\project_plan_16_weeks.md` (bảng metric tối thiểu).
>
> **Giả định** (sửa nếu sai):
> - Bảo vệ khoảng ngày 27/11.
> - Chỉ có một máy GPU 6 GB có Docker và image (máy M3).
> - Ai làm gì: bạn làm M3 và code M1; M2 code phần M2 và review mọi PR; người thứ ba (M1) làm harness, retrieval, repo
>   demo và tài liệu.
>
> Mã task: **Tn** là task trong bản tổng hợp; **M2-Tn** là task trong file pool của M2.

## 1. Mục tiêu khi ra hội đồng

1. **Demo trên repo thật, chạy Qwen thật:**
   - Đưa đường dẫn repo demo vào.
   - Agent chỉ đọc, chỉ ra lỗi ở file nào, hàm nào.
   - Yêu cầu sửa → generator V11 sinh diff → engine M2 verify và đưa ra kết luận.
   - Bug thứ hai không được nhắc tới thì vẫn FAIL.
2. **Có số liệu cho từng nhóm metric của plan,** mỗi số có lệnh tái tạo và mẫu số rõ ràng. Không cần có task nào được
   sửa thành công (resolved); metric chính đã chốt ngày 03/11 là F3, F4, Recall@k và FAR/FRR.

Ba việc **không làm trước bảo vệ**, đưa sang Hướng phát triển:
- thống nhất chat (G2/T19 đầy đủ);
- giữ session MCP (T17) — việc này sẽ đổi số latency, nên chỉ báo cáo số đo hiện tại;
- chọn điểm xuất phát bằng embedding.

## 2. Bảng metric của plan: dự kiến có gì

| Nhóm (plan) | Metric | Lấy từ | Cần làm | Người |
|---|---|---|---|---|
| Retrieval | Recall@3/5/10, MRR, token cost | R1 (dev đã có) + held-out (chỉ cần CPU) | Chạy held-out một lần; **thêm Recall@B=1.500 trên đúng bundle repair** (#8) | M1 |
| Repair | F3, F4 (chính); resolved, multi-file resolved, latency/task, token/task | A0 và A1 sinh patch trên held-out; `aggregate.py` (đã có trường cost) | Chạy theo §4, tuần 2; chấm harness | Bạn (chạy), M1 (harness) |
| Verification | FAR/FRR; API-break detection (mutant `signature_change`, `public_function_delete`); structural detection (`import_cycle`) | Mutant pool chính thức (V1/V2) | M2-T1, T2, T4, T5, T6 rồi chạy lại pool (M2-T11) | M2 |
| Graph quality | edge precision/recall trên mẫu tay; thời gian build/update | Gán tay M1-X1; `bench_incremental.py` | Mẫu khoảng 50 cạnh; sửa định nghĩa U1 (T15) | M1 |
| MCP usability | tool calls/task, latency p50/p95, invalid rate, audit completeness | Bảng M1 của X2b (N=5) + số đo overhead ngày 06/11 | Tách latency phía client và phía server; tuỳ chọn chạy lại X2b trên code đã sửa | Bạn |
| Thống kê | McNemar exact + Holm; bootstrap 10.000 vòng | — | T4 | Bạn |

## 3. Bốn quyết định nhóm phải chốt ngay đầu tuần 1

| # | Quyết định | Đề xuất | Lý do |
|---|---|---|---|
| Q1 | A2/A3 có sinh patch riêng không (ĐX1)? | **Không.** Chỉ sinh A0 và A1. Lấy patch của A1, chạy `verify_once` để có vector, rồi dùng `derive_verdict` cho A2/A3 (code đã có trong `verifier_eval.py`) | Tiết kiệm một nửa thời gian GPU; cùng patch thì so sánh check sạch hơn (review §5) |
| Q2 | A3 làm gì khi check API ra `NOT_RUN` ở 133/133 vector? | Thử M2-T1(b) tối đa 2 ngày: check API chỉ xét symbol public mà patch thật sự đổi. Hết 2 ngày mà phần lớn vẫn `NOT_RUN` → chọn (a): A3 chỉ báo cáo coverage và tỉ lệ phát hiện ở những chỗ check chạy được, không dùng McNemar | Hiện A3 ra FRR 100%, nên phép so A3/A2 chưa có nghĩa |
| Q3 | Timeout (ĐX2) | 1.500 / 2.700 s cho mọi arm | D15: trung vị 615 ms/token, nên 1.536 token mất khoảng 945 s, vượt hạn 900 s |
| Q4 | Có chạy held-out trước bảo vệ không? N bằng bao nhiêu? | **Có, nếu cổng cuối tuần 1 PASS; N = 30–40.** 2 arm × 40 × khoảng 9 phút ≈ 12 giờ GPU | Không qua được cổng → báo số dev, ghi rõ "dev, khám phá", không gọi là held-out |

## 4. Lịch theo tuần

### Tuần 1 (09–15/11): sửa code và freeze

**Bạn (M3 + code M1):**
- **Demo:**
  - T1, T2: truyền tokenizer, repo root và `graph_version` cho `vgar run`/`chat`.
  - T3: sửa dòng phản hồi impact.
- **Repo intake bản tối giản** (một phần của G1, không cần chat):
  - `vgar solve --agent --repo PATH --issue "…"` tự dựng task.
  - Chạy pytest ban đầu: test fail là FAIL_TO_PASS, test pass là PASS_TO_PASS.
  - File được sửa: mọi `.py` không phải test; thư mục test bị khoá; revision = git HEAD.
  - Xuất bundle bằng exporter graph sẵn có, rồi ghi hash vào `trusted_fixtures.json`.
  - Tận dụng `AgentRepairHost` có sẵn: 3 attempt, mỗi attempt mở run mới, nên tránh được G2.
- **Thống kê:**
  - T4: `evaluation/stats.py`.
  - T9: dựng vector cho A2/A3 từ patch A1, nếu nhóm chọn Q1.
- **Độ tin cậy:**
  - T8: chỉ cho chạy lại attempt INFRA.
  - T10: đóng run trong `finally`.
- **Tài liệu protocol:**
  - Đổi đường dẫn variant sang `variants/w10/`.
  - Sửa câu "F3/F4 đổi qua feedback".
  - Sửa định nghĩa Recall@k.
  - Ghi Q1–Q4.

**M2:**
- M2-T1 (A3, theo Q2), M2-T2 (vì sao mypy từ chối 10 patch gold), M2-T5 (`nodeids.json`), M2-T6 (xoá
  `snapshot.tar`), M2-T4 cùng T7 (FAR qualified và FAIL-detection).
- T6 cùng M1: truyền thư mục gốc module thật cho check structural.
- Review mọi PR.

**M1:**
- **Repo demo:**
  - `git init`.
  - Tách `test_bug` thành 2 test: một cho `discounts.is_eligible`, một cho VAT trong `checkout`.
  - Thêm test chặn kiểu sửa ăn gian: `discount_amount(2_000_000, "SAVE20") == 400_000`.
- **Freeze:**
  - M2-T8 (CRLF).
  - Manifest held-out và dry-run chuỗi chạy trên 1 task (M1-W12-2).
- **Retrieval:**
  - Script đo Recall@B=1.500 trên bundle repair.
  - Bắt đầu gán tay mẫu cạnh.

**Cổng cuối tuần 1 (thứ sáu 13/11).** Đủ cả 5 điều kiện thì gắn tag `protocol-freeze`:
1. CI xanh. Riêng `test_official_harness` đã có lý do rõ hoặc đã sửa.
2. Dry-run held-out PASS trên 1 task.
3. Pool cho A3 có PASS hoặc FAIL ở phần lớn vector, hoặc nhóm đã chọn Q2(a).
4. FRR của A2 có giải thích.
5. Ba người ký protocol.

### Tuần 2 (16–22/11): chạy thí nghiệm, dựng demo

Máy GPU chạy **tuần tự**, không bao giờ hai job cùng lúc:

| Thời gian | Job | Ước lượng |
|---|---|---|
| T2 đêm | Mutant pool chính thức trên commit freeze (M2-T11) | 6–7 giờ |
| T3–T5 | Held-out A0 + A1 sinh patch, theo Q4 | khoảng 12 giờ, chạy đêm |
| T6 | `verify_once` trên patch A1 (để có A2/A3) + chấm harness mọi candidate đã apply | Chỉ cần Docker, vài giờ |
| T7 ngày | Chạy thử demo với Qwen thật trên repo demo (lần 1) | 1–2 giờ |

**Song song, không cần GPU:**
- **M1:** retrieval held-out, bảng R1 cùng Recall@1.500, bench U1, Methodology phần graph.
- **M2:** codebook phân loại lỗi, **viết trước khi xem kết quả**; Methodology phần repair/verify; trực sự cố
  trong lúc chạy; có lỗi môi trường thì ghi amendment, không sửa code giữa chừng.
- **Bạn:**
  - Hoàn thiện intake và `vgar run` chỉ đọc.
  - Viết kịch bản demo.
  - Viết `scripts/make_tables.py`: checkout sạch → một lệnh → ra mọi bảng.

### Tuần 3 (23–27/11): phân tích và tập demo

- **Thứ hai:** code freeze; từ đây chỉ sửa bug chặn demo.
- **Bảng và thống kê:**
  - McNemar + Holm cho A1/A0 (F3, F4).
  - FAR/FRR cho A2/A1 và A3/A2, ghép cặp theo mutant.
  - Bootstrap cho Recall@k.
  - Câu chữ khi không có ý nghĩa thống kê: "không đủ bằng chứng về khác biệt".
- **Phân tích 10–15 case lỗi theo codebook:** M1 lo retrieval, M2 lo repair.
- **Demo:**
  - Tập 3 lần với model thật.
  - Quay lại một lần chạy thật làm phương án dự phòng (vẫn là run thật, không phải fake).
- **Slide:**
  - Mỗi claim trỏ tới một bảng.
  - Có slide Hạn chế: grounding yếu, A3 coverage, regression chỉ chạy test tái hiện, constrained agent, MCP
    overhead khoảng 2,3 s mỗi call.

## 5. Kịch bản demo nhắm tới (2 lệnh, không cần chat)

| Bước | Lệnh | Thấy gì | Phụ thuộc |
|---|---|---|---|
| 0 | `pytest` trong repo demo | 2 test fail (2 bug độc lập) | Repo demo (M1) |
| 1 | `vgar run "lỗi giảm giá nằm ở đâu?" --repo shop` | Agent dùng `search_symbols`, `find_task_anchors`, `get_related_context`, `read_file` và chỉ ra `discounts.is_eligible`; không sửa code | T1, T2 |
| 2 | `vgar solve --agent --repo shop --issue "SAVE10 không áp dụng cho đơn đúng 500.000"` | Intake tóm tắt task → các bước get_task_context, generate_patch, apply, test, verify → engine M2 ra PASS | Intake tối giản |
| 3 | `pytest` lại | Test giảm giá PASS; test VAT vẫn FAIL vì nằm ngoài phạm vi | — |

**Rủi ro bước 1:** grounding yếu, như đã thấy trên repo demo. Nếu agent không tìm ra `is_eligible`:
- **Cách sửa:** viết mô tả lỗi có nhắc tới hành vi cụ thể (coupon, min_order), rồi chạy thử trước, ghi lại kết quả.
- **Không được** chỉnh ranking riêng cho repo demo; đó là tune ăn gian.

## 6. Cắt bỏ theo thứ tự nếu chậm

1. Chạy lại X2b trên code đã sửa (giữ bảng M1 cũ N=5, ghi commit).
2. T13–T16 (audit theo request_id, comparator tune, định nghĩa U1, timeout tool graph): ghi vào Hạn chế.
3. T11 (guard junction trên Windows): mọi run chạy trên WSL/Linux, ghi là hạn chế của nền Windows.
4. A3 rơi về Q2(a).
5. Held-out: không qua cổng tuần 1 thì báo số dev.

**Không cắt:** T1, T2, intake tối giản, repo demo, T4, pool chính thức, A0/A1 có số F3/F4.
