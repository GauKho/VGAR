# W11–12: phân công song song cho M1, M2, M3 (phát triển W11–12 và sửa nợ W3–W10)

> **Ngày:** 31/10/2026 · **Người soạn:** M3 (cùng Claude Code)
> **Trạng thái:** M3 đã chốt hướng chia việc. Cả nhóm duyệt ở buổi họp ngày 1 của W11 (§1.3).
>
> **Đọc thế nào:**
> - Mọi người đọc **§1 (chung)** và **phần của mình**: §2 cho M1, §3 cho M2, §4 cho M3.
> - Tra mã test ở **Phụ lục A**, mã nợ ở **Phụ lục B**.
> - Mỗi việc trong phần của bạn đã ghi file được sửa, test phải viết, lệnh kiểm chứng và bàn giao cho ai. Thiết kế kỹ thuật sâu hơn của từng task nằm ở `docs/superpowers/specs/2026-10-31-w11-w12-design.md` (*spec kỹ thuật*).
>
> **Thứ tự ưu tiên giữa các tài liệu:**
> 1. **Plan chính thức:** deliverables v2 (`D:\kltn\VGAR_W9_W16_Deliverables (1).md`). Tiêu chí nghiệm thu lấy từ đó.
> 2. **Tài liệu này:** quy định ai làm, khi nào, trên máy nào. Nó **thay** `docs/status/w11_w12_assignment.md`.
> 3. **Spec kỹ thuật:** quy định làm thế nào. Riêng Q3 và §6 của spec kỹ thuật được thay bằng §1.6 của tài liệu này.

---

## 1. Chung cho cả nhóm

### 1.1. Mục tiêu hai tuần

**Cổng cuối W11.** Đã merge vào `main`:
- sửa B10 và config ranking đã đóng băng;
- `api_check` và `structural_check`;
- evidence có hai check mới và `A3.json`;
- security cho 4 MCP server;
- envelope lỗi chung.

**Cổng cuối W12 (milestone M6 của v2):**
- [ ] Protocol đã ký và gắn tag `protocol-freeze`.
- [ ] Harness chạy ổn định: dry-run 2 lần, không có ERROR hạ tầng.
- [ ] A3 có record trên dev.
- [ ] Có báo cáo cold/warm của incremental update và MCP overhead.
- [ ] Tool không chạy lệnh tùy ý.

### 1.2. Quy tắc làm việc

| Quy tắc | Nội dung |
|---|---|
| **Một file, một người sửa** | Trong W11–12 mỗi file chỉ có **một chủ được sửa** (bảng §1.4). Cần đổi file của người khác thì mở issue cho chủ file, **không tự sửa**. |
| PR | Mỗi PR 0,5–2 ngày việc, khoảng 300 dòng diff trở xuống. Tên nhánh `m{1,2,3}/w11-<việc>`, sống tối đa 3 ngày. Cần 1 review khác vai trò và CI xanh. |
| CI | `pytest -m "not hf and not docker"` phải xanh. Test cần GPU gắn marker `hf`, test cần Docker gắn marker `docker`. |
| Contract | Code theo contract đã chốt ngày 1 (§1.3). Trước khi có code thật của người khác thì dùng fake hoặc fixture. Đổi contract cần cả 3 người đồng ý. |
| Kết quả chạy | Không commit `results/`, `artifacts/runs/`. Chỉ commit config, script, bảng sinh từ script. Đường dẫn record ghi vào `docs/status/m{1,2,3}.md`. |
| Trạng thái | Mỗi người cập nhật `docs/status/m{1,2,3}.md`. Chỉ M3 sửa `Task Status.md`. |
| Daily sync | 10 phút mỗi ngày, mỗi người trả lời ba câu: hôm qua merge gì, hôm nay sửa file nào, đang bị ai chặn. |
| GPU | Chỉ M3 bật hoặc tắt run có model. Không chạy hai việc nặng cùng lúc trên một máy. |
| Không được | Đổi `policy_hash` của A0–A2; dùng generator fake cho task SWE-bench; chạy held-out trước khi có tag `protocol-freeze`. |

### 1.3. Buổi họp ngày 1 của W11 (45 phút, M3 chủ trì)

**Chuẩn bị trước buổi họp:** mỗi người viết sẵn bản đề xuất các contract mình phụ trách, dài nửa trang, dán vào `docs/m3_w11_decisions.md`.

**Phải chốt bảy contract:**

| # | Contract | Người đề xuất | Người duyệt | Nội dung tối thiểu |
|---|---|---|---|---|
| C1 | Kết quả `api_check` và `structural_check` | M2 | M1, M3 | `{status: PASS\|FAIL\|NOT_RUN\|ERROR, reasons: [code], details_ref}`. Mã reason tối thiểu: `API_SYMBOL_REMOVED`, `API_SIGNATURE_INCOMPATIBLE`, `NEW_IMPORT_CYCLE`, `FORBIDDEN_IMPORT`, `LAYER_VIOLATION` |
| C2 | Trường mới trong `src/vgar/contracts/evidence.py` | M2 | M1, M3 | Hai trường theo C1. Ở A0–A2 chỉ ghi lại ("recorded"), không bắt buộc. Có test khóa `policy_hash` A0–A2 (V11) |
| C3 | `configs/m2/variants/A3.json` và luật fairness | M2 | M3 | A3 = A2 + `required_checks += ["api", "structural"]`. A3 chỉ được khác A2 ở `required_checks`. Dùng cùng vòng retry với A2, không re-plan riêng |
| C4 | Envelope và enum mã lỗi MCP | M3 | M1, M2 | `{ok, data \| error{code, message, retryable}, audit_id}`; enum nằm trong `src/vgar/mcp/schemas.py` |
| C5 | Schema config ranking và cách tính hash | M1 | M3 | Danh sách trọng số và cờ. Hash được ghi vào output retrieval (G6), dùng cho fairness và freeze |
| C6 | Runner test chung cho `execution_server` | M2 | M3 | Hàm do M2 cung cấp: nhận root theo lease và selector đã kiểm; timeout và giới hạn output do server đặt. Trả kết quả theo C4 |
| C7 | Kết quả sampler VRAM | M2 | M3 | `gpu.py` trả `gpu_peak_mib` (peak của các mẫu thành công) và `samples_failed`. `runner.py` (M3) ghi cả hai vào attempt record |

**Bốn quyết định nhóm:**

| # | Câu hỏi | Đề xuất |
|---|---|---|
| N1 | Metric chính của held-out | Funnel F3/F4, Recall@k, FAR/FRR là **chính**; resolved là **phụ** (dev đang 0/25) |
| N2 | Timeout cho held-out | M2 phân tích theo arm ở W12 ngày 3–4 rồi đề xuất số |
| N3 | Các mục [Bổ sung] của spec kỹ thuật: A3 trên 25 task, dry-run toàn chuỗi 2 lần, chạy lại A1/A2 nếu ranking đổi | Duyệt từng mục |
| N4 | Hai việc chưa có chủ: kiểm tay edge (RQ1), phép đo impact (RQ3) | M1 |

**Một câu hỏi về máy:** máy M2 (hoặc M1) có chạy được Docker trong WSL2 và còn khoảng 150 GB đĩa trống không? Câu trả lời quyết định phương án D hay N (§1.6).

**Nếu N3 không được duyệt:**
- GPU W12 chỉ còn pilot A3 × 5 task.
- Dry-run thu về phạm vi retrieval như v2.
- Cổng "harness ổn định" lấy từ lần chấm của pilot A3.

Phân chia người và file **không đổi** trong trường hợp này.

### 1.4. Sở hữu file

| Người | Được sửa | Không sửa |
|---|---|---|
| **M1** | `src/vgar/graph/**`<br>`src/vgar/contracts/impact.py`<br>`src/vgar/evaluation/retrieval/**` (trừ `dataset.py`)<br>`src/vgar/evaluation/harness/**`<br>`src/vgar/mcp/servers/graph_server.py` **chỉ phần B02, chỉ W11 ngày 1–2**<br>`scripts/bench_incremental.py`, `scripts/dry_run_heldout_chain.sh`<br>`docs/m1_retrieval_method.md`, `docs/status/m1.md` | Phần còn lại của `src/vgar/mcp/**`. Từ W11 ngày 3, `graph_server.py` thuộc M3; cần đổi cách expose `analyze_patch_impact` thì mở issue cho M3 |
| **M2** | `src/vgar/repair/**`<br>`src/vgar/contracts/evidence.py`<br>`configs/m2/**`<br>`src/vgar/evaluation/repair/fairness.py`<br>`src/vgar/evaluation/repair/gpu.py`, `tests/m3/test_gpu.py`<br>`src/vgar/evaluation/repair/verifier_eval.py` (mới), `scripts/build_mutant_pool.py` (mới)<br>`tests/test_hf_model.py` (B01), `docs/status/m2.md` | `runner.py`, `aggregate.py`, `launch.py`, `manifest.py`, `preflight.py`: cần đổi thì mở issue cho M3 |
| **M3** | `src/vgar/mcp/**` (trừ phần B02 trong W11 ngày 1–2)<br>`src/vgar/agents/**`<br>`src/vgar/observability/**`<br>`src/vgar/evaluation/repair/{runner,aggregate,launch,manifest,preflight}.py`<br>`src/vgar/evaluation/retrieval/dataset.py` (chỉ phần khóa held-out, P1)<br>`src/vgar/cli.py`, `configs/mcp.yaml`, `src/vgar/agents/prompts/system.md`, `scripts/smoke_mcp.py`<br>`docs/mcp_tool_contract.md`, `docs/security_checklist.md`, `docs/protocol_freeze_heldout.md`, `Task Status.md` | Cách tính `policy_hash` trong `manifest.py` (D17) |

**Review:** theo CODEOWNERS. Một số file thuộc module M3 trong CODEOWNERS nhưng do M2 sửa (`fairness.py`, `gpu.py`, `tests/m3/test_gpu.py`), nên M3 review. `contracts/evidence.py` cần **cả 3 người** review.

### 1.5. Năm điểm bàn giao

Chỉ có 5 lúc một người cần kết quả của người khác. Ngoài 5 lúc này, ai cũng làm tiếp được bằng fake hoặc fixture.

| Mã | Hạn | Từ → đến | Nội dung | Nếu trễ |
|---|---|---|---|---|
| **H1** | W11 ngày 1 | Cả nhóm | C1–C7, N1–N4 đã chốt; đã chọn phương án D hoặc N | Làm tiếp theo bản đề xuất; chốt muộn nhất ngày 2 |
| **H2** | W11 ngày 2 | M1 → M2, M3 | B10 đã merge (M2 chạy lại V6–V8 trên graph sạch). B02 đã merge (M3 nhận `graph_server.py`) | M2 tiếp tục trên fixture; M3 làm security ở file khác trước |
| **H3** | W11 ngày 4 | M1, M2 → M3 | Hash ranking đã đóng băng; `evidence.py` và `A3.json` đã merge; `gpu.py` theo C7 đã merge | **Đường găng.** Còn ngày 5 làm dự phòng; quá ngày 5 thì lùi GPU, mỗi ngày trễ lùi freeze một ngày |
| **H4** | W12 ngày 3 | M3 → M1, M2 | Record GPU và dry-run đã xong (đường dẫn trong `docs/status/m3.md`) | Bảng dùng số W10, ghi rõ |
| **H5** | W12 ngày 4 | M1, M2 → M3 | M1 gửi bảng R1, G1, I1, U1 và kết quả dry-run. M2 gửi bảng V1, V2 và số timeout đề xuất | Freeze vẫn chốt định nghĩa metric; số liệu điền ở W13 ngày 1 |

### 1.6. Máy chạy trong W12

Run có model chỉ chạy trên **máy M3** (RTX 4050, WSL2). Thời gian ước tính theo W10, khoảng 7,4 phút/run.

| Thứ tự | Việc trên máy M3 | Ước tính |
|---|---|---|
| 1 | Dry-run lần 1: 2 dev task × 4 arm | khoảng 1 giờ |
| 2 | Batch: A3 × 25 task; cộng chạy lại A1/A2 × 25 **nếu ranking đổi**. Chạy qua đêm như W10 | 3 giờ đến 10 giờ |
| 3 | Dry-run lần 2 | khoảng 1 giờ |
| 4 | **Chỉ phương án N:** mutant pool, khoảng 150 lần verify, không gọi model | 3–5 giờ |
| 5 | `vgar solve --agent` × 5 dev task (RQ5) | 1–3 giờ |

**Phương án D** (máy M2 có Docker): mutant pool chạy trên máy M2 ở W12 ngày 1–2, **song song** với bước 1–3. Điều kiện:
- M2 pull image theo đúng digest đã pin, dùng kho overlay2 và tắt containerd (D21).
- M2 lấy profile và test tái hiện từ data root của M3, kiểm hash trước khi chạy.

**Phương án N:** pool chạy ở bước 4 trên máy M3.

**Điều kiện của batch** là `preflight` FITS và fairness PASS, **không phải** dry-run. Nếu script dry-run chưa sẵn sàng thì batch vẫn chạy. Khi đó dry-run lần 1 chạy ngay sau batch, và lần 2 chạy ở một phiên máy khác (W12 ngày 3–4).

### 1.7. Thứ tự cắt nếu trễ

1. **Cắt trước:** incremental thu về fixture (bảng U1 chỉ 1 kịch bản); rule layer theo config; read redundancy.
2. **Cắt sau:** giảm cỡ mẫu RQ1/RQ3; `solve --agent` còn 3 task; A3 chỉ là phép đo, không vào verdict.
3. **Không cắt:** B10, chạy lại A1/A2 sau tune (nếu ranking đổi), mutant pool, security S1–S9, dry-run 2 lần, protocol freeze.

### 1.8. Tải ước tính (ngày công)

| | W11 | W12 |
|---|---|---|
| M1 | khoảng 5 | khoảng 5 |
| M2 | khoảng 5 | khoảng 4,5 (+ giám sát pool nếu phương án D) |
| M3 | khoảng 5 | khoảng 5 + giám sát GPU |

---

## 2. M1: Graph, retrieval, harness

**Mục tiêu:** graph sạch (B10, B02), ranking tune xong và đóng băng, incremental update, dry-run toàn chuỗi, hai phép đo RQ1/RQ3.
**Deliverable v2:** M1-W11-1, M1-W11-2, M1-W12-1, M1-W12-2. **Việc thêm:** M1-X1 (RQ1), M1-X2 (RQ3), nợ D1, D3, D4, D5, D8, D16.
**Bàn giao:** H2 (ngày 2 W11), H3 (ngày 4 W11), H5 (ngày 4 W12). **Người review mặc định:** M3.

### Tuần 11

| Ngày | Việc | File | Test (Phụ lục A) | Xong khi |
|---|---|---|---|---|
| 1 | Họp H1; chuẩn bị đề xuất C5 | `docs/m3_w11_decisions.md` | — | C5 được duyệt |
| 1–2 | **Sửa B10 (D1):** tên đã import tường minh mà target không có trong repo thì ghi unresolved, không fallback theo tên duy nhất (`builder.py:1355`) | `src/vgar/graph/builder.py` | G1, G2 trong `tests/test_graph_builder.py` | PR merge → **H2** |
| 2 | **Sửa B02 (D8):** decode node id đúng một lần ở biên resource | `src/vgar/mcp/servers/graph_server.py` | S11 trong `tests/test_w3_w4_graph_resources.py` | PR merge → **H2**; từ ngày 3 không sửa file này nữa |
| 3 | **Tune ranking (M1-W11-2)** trên dev 25 task, mỗi bước một dòng bảng R1: (a) sau B10; (b) bật `public_api_risk` (D4) | `src/vgar/graph/retrieval.py`, `docs/m1_retrieval_method.md` | — | Mỗi bước có số Recall@k trên dev |
| 4 | Tune (c): giảm trọng số IMPORTS hop 2 (D3); xử lý anchor nhiễu (D5) nếu còn thời gian. **Đóng băng config** bằng hash (C5) | như trên | G6 trong `tests/test_graph_retrieval.py` | Hash ghi vào `docs/m1_retrieval_method.md` → **H3** |
| 4–5 | **Incremental (M1-W11-1):** sửa, thêm, xóa file; link lại closure ngược; tăng `graph_version` | `src/vgar/graph/incremental.py` (mới), `builder.py`, `task_overlay.py` | G3, G4, G5 trong `tests/test_incremental.py` (mới) | `pytest tests/test_incremental.py` PASS |

### Tuần 12

| Ngày | Việc | File | Test | Xong khi |
|---|---|---|---|---|
| 1 | Incremental (tiếp): relink, cache. **Script dry-run** chạy được trên fixture | `incremental.py`, `scripts/dry_run_heldout_chain.sh` | G3–G5 | Script in ra lệnh, hash config, thời gian, đường dẫn output |
| 2 | **`bench_incremental.py` (M1-W12-1):** 3 kịch bản (sửa thân hàm, thêm/xóa file, đổi chữ ký public) → bảng U1 | `scripts/bench_incremental.py` | — | Bảng U1 sinh từ script |
| 2 | **M1-X1 (RQ1):** kiểm tay mẫu edge CALLS/IMPORTS/TESTS trước và sau B10 → bảng G1 | ghi chú trong `docs/status/m1.md` | — | Có precision/recall và % call site unresolved (D2) |
| 3 | **M1-X2 (RQ3):** impact trên gold patch, đo recall test F2P và file gold, so với baseline chỉ dùng diff → bảng I1 | script trong `scripts/` | — | Bảng I1 |
| 3–4 | Đọc kết quả dry-run lần 1 và 2 (M3 chạy trên máy GPU, §1.6). Sửa harness nếu lỗi (D16) | `src/vgar/evaluation/harness/**` | — | 2 lần không có ERROR hạ tầng → **H5** |
| 4 | Bảng R1 cuối cùng (BM25, graph trước tune, graph sau tune) | — | — | → **H5** |
| 5 | Ký protocol freeze | — | — | — |

**Bảng M1 sinh:** R1, G1, I1, U1 (mẫu ở `docs/status/w11_w12_remediation_plan.md` §4).

---

## 3. M2: Repair, verification

**Mục tiêu:** `api_check`, `structural_check`, evidence v2, A3, mutant pool và FAR/FRR, phân tích timeout.
**Deliverable v2:** M2-W11-1, M2-W11-2, M2-W11-3, M2-W12-1, M2-W12-2. **Việc thêm:** nợ D10, D11, D14, D15, D17, D18; runner test chung cho `execution_server` (C6).
**Bàn giao:** H3 (ngày 4 W11), H5 (ngày 4 W12). **Người review mặc định:** M1.

### Tuần 11

| Ngày | Việc | File | Test (Phụ lục A) | Xong khi |
|---|---|---|---|---|
| 1 | Họp H1; chuẩn bị đề xuất C1, C2, C3, C6, C7. **Sửa B01 (D11):** sửa test HF hoặc `xfail(strict=True)` kèm lý do | `tests/test_hf_model.py` | P2 | CI xanh mà không cần deselect |
| 2 | **`api_check.py` (M2-W11-1):** trích chữ ký bằng `ast`; public theo `__all__`, nếu không có thì là tên không bắt đầu bằng `_`; không tương thích khi xóa symbol, thêm tham số bắt buộc, bỏ hoặc đổi thứ tự tham số positional, bỏ default | `src/vgar/repair/api_check.py` (mới) | V1–V5 trong `tests/m2/w1112/test_api_check.py` (mới) | PR merge |
| 3 | **`structural_check.py` (M2-W11-2):** không thêm cycle IMPORTS mới so với baseline, chỉ tính edge đã resolve và đủ confidence. Rule theo config `configs/m2/structural/<repo>.yaml`; không có config thì layer `NOT_RUN` | `src/vgar/repair/structural_check.py` (mới), `configs/m2/structural/` | V6–V9 trong `tests/m2/w1112/test_structural_check.py` | PR merge; chạy lại V6–V8 sau **H2** |
| 4 | **Evidence (M2-W11-3):** thêm `api_check`, `structural_check` (C2). `NOT_RUN` không bao giờ tính là PASS. **Giữ `policy_hash` A0–A2 (D17)** | `src/vgar/contracts/evidence.py`, `src/vgar/repair/verification.py` | V10, V11 trong `tests/m2/w1112/test_evidence_checks.py` | PR có **3 review** trong ngày → **H3** |
| 4 | **`A3.json` (M2-W12-1, kéo sớm):** mở rộng fairness để A3 chỉ khác A2 ở `required_checks` | `configs/m2/variants/A3.json`, `src/vgar/evaluation/repair/fairness.py` | V12 trong `tests/m2/w910/test_arm_fairness.py` | PR merge → **H3** |
| 5 | **Sampler VRAM (C7, D14):** giữ peak của các mẫu thành công, ghi `samples_failed` | `src/vgar/evaluation/repair/gpu.py`, `tests/m3/test_gpu.py` | M2 (test) | PR merge (trước GPU W12) |
| 5 | **Runner test chung cho `execution_server` (C6)** | `src/vgar/repair/` (module do M2 chọn) | Test đơn vị của M2; M3 dùng ở S3, S4, S5 | PR merge; báo M3 |

### Tuần 12

| Ngày | Việc | File | Test | Xong khi |
|---|---|---|---|---|
| 1 | **`build_mutant_pool.py` (M2-W12-2):** 5 loại mutant từ gold patch của 25 dev task (đảo điều kiện, xóa hàm public, đổi chữ ký, import tạo cycle, làm test bị skip: D10), seed cố định. Nhãn do loại mutant quyết định; script **không import** verifier | `scripts/build_mutant_pool.py` (mới) | V13, V14, V15 trong `tests/m2/w1112/test_mutant_pool.py` (fixture, CI) | PR merge |
| 2 | **`verifier_eval.py`:** verify mỗi patch **một lần** với đủ check, rồi suy verdict A0–A3 theo `required_checks` | `src/vgar/evaluation/repair/verifier_eval.py` (mới) | V16 | PR merge. **Phương án D:** chạy pool trên máy M2 |
| 3 | Kiểm record A3 sau **H4**. **Phân tích timeout (D15):** độ dài prompt so với thời gian sinh, theo arm | ghi chú `docs/status/m2.md` | — | Có số timeout đề xuất |
| 4 | Bảng V1 (FAR/FRR), V2 (theo loại mutant). Không gọi static hint là "coverage" (D18) | script sinh bảng | — | → **H5** |
| 5 | Ký protocol freeze | — | — | — |

**Bảng M2 sinh:** V1, V2, cột verify của bảng P1.

---

## 4. M3: MCP, đánh giá, paper

**Mục tiêu:** 4 MCP server an toàn, envelope lỗi chung, đo RQ5, chạy GPU, protocol freeze.
**Deliverable v2:** M3-W11-1, M3-W11-2, M3-W11-3, M3-W12-1, M3-W12-2, M3-W12-3. **Việc thêm:** nợ D6, D7, D9, D19, D20; kiểm D13; chạy toàn bộ việc trên máy GPU.
**Bàn giao:** H1 (chủ trì), H4 (ngày 3 W12). **Người review mặc định:** M2.
**Thứ tự ba task MCP:** W11-2 → W11-1 → W11-3, làm nối tiếp vì cùng sửa các file server.

### Tuần 11

| Ngày | Việc | File | Test (Phụ lục A) | Xong khi |
|---|---|---|---|---|
| 1 | Chủ trì họp H1, ghi `docs/m3_w11_decisions.md`; chuẩn bị đề xuất C4 | — | — | 3 người đồng ý |
| 1–2 | **Legacy server (M3-W11-2; D7, D9, D19):**<br>• `repository_server` chỉ còn `read_file` read-only, root theo lease, bỏ `apply_patch`.<br>• `execution_server.run_pytest` gọi runner chung (C6; dùng fake tới khi M2 xong).<br>• `vgar run` không còn `ok=True` khi không có selector.<br>• Sửa `src/vgar/agents/prompts/system.md` | `src/vgar/mcp/servers/{repository,execution}_server.py`, `src/vgar/cli.py`, `configs/mcp.yaml`, `src/vgar/agents/prompts/system.md`, `scripts/smoke_mcp.py` | S2, S3, S9, S14, S16 | PR merge; `vgar tools` chỉ liệt kê tool đã qua guard |
| 3 | **Redact secret (D6, B12):** sửa regex ở `instrumentation.py:31`; dùng một hàm redact chung; env tiến trình con theo allowlist | `src/vgar/observability/instrumentation.py`, `phase_logger.py`, `src/vgar/mcp/client.py` | S6, S7 | PR merge |
| 4 | **Security (M3-W11-1):** giới hạn do server đặt (timeout, output trong lúc capture, selector), path jail. Review PR `evidence.py` của M2 | `src/vgar/mcp/{tooling,audit,registry}.py` | S1–S5 | PR merge |
| 5 | Security (tiếp): audit mọi call kể cả lỗi; gắn `untrusted`; graph server read-only. **Envelope C4 (M3-W11-3).** `runner.py` ghi `samples_failed` (C7). **Smoke `solve --agent`** chế độ fake trên 1 dev task (D20) | `src/vgar/mcp/**`, `src/vgar/mcp/schemas.py`, `docs/mcp_tool_contract.md`, `src/vgar/evaluation/repair/runner.py` | S8, S10, S12, S13, S15 | `pytest tests/test_mcp_tool_contract.py` PASS |

### Tuần 12

| Ngày | Việc | File | Test | Xong khi |
|---|---|---|---|---|
| 1 | **Máy GPU:** preflight → dry-run lần 1 (script của M1) → bắt đầu batch (qua đêm). **Đo lường (M3-W12-1):** invalid call rate, audit completeness, p50/p95 theo tool; kiểm usage có sẵn (D13, `local_hf_chat_model.py:128`) | `src/vgar/observability/**`, `src/vgar/agents/tool_agent.py` | M1, M3, M4 trong `tests/m3/test_mcp_metrics.py` (mới) | PR merge |
| 2 | Batch (tiếp). Thêm A3 vào `aggregate.py`. `docs/security_checklist.md` (bảng S1, mỗi dòng trỏ tới test). Soạn khung `protocol_freeze_heldout.md` từ `docs/research_design.md` | `aggregate.py`, `tests/m3/test_aggregate.py`, docs | — | Aggregate chạy 2 lần ra giống từng byte |
| 3 | Batch xong → dry-run lần 2 → **H4**. **Phương án N:** chạy mutant pool trên máy M3 | — | — | Record ghi đường dẫn trong `docs/status/m3.md` |
| 4 | `solve --agent` × 5 dev task RUNNABLE đầu tiên theo thứ tự manifest, config như A2. Ráp Results draft từ R1, P1, V1, V2, I1, G1, U1 | — | — | Mọi số trỏ tới script |
| 5 | Bảng M1 (RQ5). **Protocol freeze (M3-W12-2):** điền O1–O9 của `docs/research_design.md` §11; khóa held-out trong `dataset.py`; cả 3 ký; gắn tag `protocol-freeze` | `docs/protocol_freeze_heldout.md`, `src/vgar/evaluation/retrieval/dataset.py` | P1 | Tag đã gắn |

**Bảng M3 sinh:** P1 (ráp), M1 (RQ5), S1.

---

## Phụ lục A: Mã test

Chi tiết input và kỳ vọng ở `docs/status/w11_w12_remediation_plan.md` §3. Tên file là đề xuất; người làm có thể đổi, miễn ghi lại.

| ID | Người | Kiểm gì |
|---|---|---|
| G1 | M1 | Import tường minh từ module ngoài không bị nối nhầm vào hàm nội bộ trùng tên (B10) |
| G2 | M1 | Gọi hàm không có import vẫn resolve như cũ |
| G3 | M1 | Incremental cho ra node/edge và `graph_version` giống hệt full rebuild (sửa, thêm, xóa, đổi tên, chuyển import) |
| G4 | M1 | Xóa hàm được gọi thì edge từ caller cũng bị xóa |
| G5 | M1 | Không có file đổi thì version giữ nguyên, cache hit 100% |
| G6 | M1 | Output retrieval có hash config; đổi trọng số thì hash đổi |
| S11 | M1 | Node id chứa `/` và `:` đi qua resource MCP vẫn tìm thấy (B02) |
| V1–V5 | M2 | `api_check`: xóa hàm public FAIL; thêm tham số bắt buộc FAIL; thêm có default PASS; đổi private hoặc chỉ đổi thân hàm PASS; tôn trọng `__all__`; baseline lỗi cú pháp ra ERROR/NOT_RUN, không PASS |
| V6–V9 | M2 | `structural_check`: cycle IMPORTS mới FAIL; cycle có sẵn PASS; bỏ qua edge unresolved và confidence thấp; không có config thì layer `NOT_RUN` |
| V10 | M2 | A3 với `api_check = NOT_RUN` ra `VERIFICATION_INCOMPLETE`, không ACCEPT |
| V11 | M2 | `policy_hash` của A0–A2 trùng giá trị trong record W10 |
| V12 | M2 | A3 chỉ khác A2 ở `required_checks`; khác field khác thì runner từ chối |
| V13–V15 | M2 | Mutant pool không import verifier; chạy 2 lần cùng seed ra giống từng byte; mutant skip test bị bắt |
| V16 | M2 | Verdict suy ra cho A0–A3 trùng với verify trực tiếp từng arm |
| M2 | M2 | Sampler giữ peak khi một số mẫu lỗi; có `samples_failed` |
| P2 | M2 | Test HF constructor (B01) sửa xong hoặc `xfail(strict=True)` |
| S1–S5 | M3 | Path traversal, root sai, selector độc, timeout cắt cả cây tiến trình, output bị chặn trong lúc capture |
| S6, S7 | M3 | Secret giả không xuất hiện trong audit, log, error; env tiến trình con theo allowlist |
| S8 | M3 | Mọi call, kể cả lỗi, có audit entry |
| S9, S14 | M3 | `vgar tools` và tool của chat chỉ có tool đã qua guard; không còn tool ghi file ngoài `repair_server` |
| S10 | M3 | Mọi tool trả đúng envelope C4 |
| S12, S16 | M3 | Text từ repo gắn `untrusted: true`; `read_file` có trần output và cờ `truncated` |
| S13 | M3 | Graph server không có tool ghi |
| S15 | M3 | Smoke `solve --agent` fake trên 1 dev task (marker `docker`, chạy tay) |
| M1, M3, M4 | M3 | Có usage theo lượt model; invalid call rate và audit completeness đúng trên fixture; p50/p95 đúng |
| P1 | M3 | `dataset.py` từ chối held-out khi chưa có hoặc sai hash freeze |

## Phụ lục B: Nợ W3–W10

Mã D lấy từ `docs/status/w11_w12_remediation_plan.md` §1. "Chặn" nghĩa là có việc khác đang chờ mục này.

| Nợ | Người | Khi nào | Chặn? |
|---|---|---|---|
| D1 B10 nối sai import | M1 | W11 ngày 1–2 | **Có**: tune ranking, structural check |
| D8 B02 resource node | M1 | W11 ngày 2 | **Có**: M3 cần `graph_server.py` từ ngày 3 |
| D7 B04/B05 legacy server; D9 `vgar run`; D19 `vgar chat` | M3 | W11 ngày 1–2 | **Có**: DoD "tool không chạy lệnh tùy ý" |
| D6 B12 redact secret | M3 | W11 ngày 3 | **Có**: test S6 |
| D11 B01 test HF | M2 | W11 ngày 1 | **Có**: CI là điều kiện của branch protection |
| D17 giữ `policy_hash` A0–A2 | M2 | W11 ngày 4 (V11) | Có: bảng dev W10 |
| D4 `public_api_risk`, D3 IMPORTS hop 2, D5 anchor | M1 | Trong tune ranking | Không |
| D2 79% call site chưa resolve | M1 | Không sửa; đo trong RQ1, ghi limitation | Không |
| D10 skip-only false accept | M2 | Thành một loại mutant | Không |
| D14 VRAM | M2 (`gpu.py`), M3 (`runner.py`) | W11 ngày 5 | Không (cần trước GPU) |
| D13 usage | M3 | Đã có ở `local_hf_chat_model.py:128`; chỉ kiểm | Không |
| D15 timeout dồn vào arm graph | M2 | W12 ngày 3 | Không |
| D16 harness và Docker dễ vỡ | M1 | Dry-run 2 lần ở W12 | Có: cổng "harness ổn định" |
| D18 wording "coverage" | M2 | Khi viết bảng V1 | Không |
| D20 nguồn số liệu RQ5 | M3 | Smoke W11 ngày 5, chạy thật W12 ngày 4 | Không |
| D12 pin model | — | **Đã xong** trong `docs/research_design.md` §6 | — |

## Phụ lục C: Thay đổi so với tài liệu trước

| Chỗ | Trước | Bây giờ |
|---|---|---|
| Spec kỹ thuật Q3 | Mutant pool trên máy M3, sau GPU | Phương án D: máy M2, song song GPU. Phương án N: như cũ |
| Spec kỹ thuật §6 | Dry-run ×2 sau mutant pool | Dry-run lần 1 đầu cửa sổ GPU, lần 2 cuối cửa sổ; dry-run không chặn batch |
| Assignment D13 | M3 sửa `local_chat.py` | Đã có sẵn (`local_chat.py` chỉ là tokenizer); M3 chỉ kiểm |
| Assignment D14 | M3 | M2 sửa `gpu.py`; M3 ghi trường vào `runner.py` |
| Assignment B02 | M1, W12 ngày 1 | M1, W11 ngày 2; giao `graph_server.py` cho M3 từ ngày 3 |
| Khung Methodology (M3-X1) | W12 ngày 3 | W13, theo S6 của v2 |
| Hạn hash ranking và `A3.json` | Cuối W11 | W11 ngày 4 |
| Điểm bàn giao | 11 | 5 |

Sau khi nhóm duyệt: sửa Q3 và §6 của spec kỹ thuật cho khớp, và ghi đầu `docs/status/w11_w12_assignment.md` dòng "đã được thay bằng `docs/superpowers/specs/2026-10-31-w11-w12-parallel-split-design.md`".
