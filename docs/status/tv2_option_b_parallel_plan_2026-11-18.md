# TV2 · Luồng B: chuẩn bị freeze và held-out R1, chạy song song với luồng A (18/11/2026)

Hai người làm cùng lúc, mục tiêu chung là **một lần freeze và một lần chạy held-out**:

| Luồng | Người | Việc chính |
|---|---|---|
| **A** | TV2 | Cải tiến retrieval (phạm vi A): lọc anchor top-20, mở rộng method con theo file có xếp hạng lại, đóng gói khung xương + dừng sớm. Chỉnh trên `tune25`, kiểm chứng trên 25 task còn lại |
| **B** | thành viên hỗ trợ | Làm mọi việc của freeze và held-out **không phụ thuộc vào A**, để khi A xong thì ký và chạy được ngay. Nếu A không kịp, B đã có sẵn bản freeze với cấu hình hiện tại (phương án dự phòng) |

Nguồn: `docs/protocol_freeze_r1_heldout.md` (bản nháp 17/11), `docs/status/tv2_open_issues_2026-11-18.md`,
plan 2 tuần (tuần 2 ngày 5–6: freeze rồi chạy held-out đúng một lần).

## 1. Luật bắt buộc cho luồng B

1. **Không mở held-out.** Không chạy `prepare_manifest.py --split heldout`, không dùng `--allow-heldout`, không đọc
   patch hay kết quả của task held-out. Mọi lần chạy thử chỉ dùng task dev. Lần đọc held-out duy nhất cho tới nay là
   lệnh chỉ đếm (`results/heldout_access.log`).
2. **Không chạy held-out sớm với cấu hình hiện tại.** Held-out chỉ chạy một lần. Nếu chạy trước khi A xong, A sẽ không
   bao giờ có số held-out; và nếu A được chỉnh sau khi đã thấy kết quả held-out thì là rò dữ liệu.
3. **Không sửa code xếp hạng.** `src/vgar/graph/retrieval.py`, `RetrievalConfig`, `RT1_CONFIG`,
   `ablation_matrix/retrieval_variants.py` thuộc luồng A. Đổi chúng làm đổi `ranking_config_hash` đã ghi trong bản freeze.
4. **Ranh giới file để tránh đụng nhau:**

   | Luồng A sửa | Luồng B sửa | Chỉ sửa khi đã báo người kia |
   |---|---|---|
   | `src/vgar/graph/retrieval.py`, `ablation_matrix/retrieval_variants.py`, test của chúng | `docs/protocol_freeze_r1_heldout.md`, `docs/status/*` (báo cáo mới), script báo cáo mới trong `ablation_matrix/`, 3 test ghi đè `sample_graph.db` | `ablation_matrix/run_r1_ablation.py` (`PRIMARY_PAIRS`, `PAIRS`), `scripts/g1_evaluate.py`, `src/vgar/graph/layer_config.py` |

5. **Một lượt nặng cho mỗi máy** (R1, G1, embedding GPU, Docker). Máy của TV2 đang chạy R1 với SCIP; luồng B không chạy
   thêm gì nặng trên máy đó.
6. Làm trên nhánh riêng, ví dụ `tv2/option-b-freeze-prep`; người phụ trách tự commit.

## 2. Việc của luồng B

Thứ tự là thứ tự nên làm. Mỗi việc có tiêu chí "xong".

### B-1. Hoàn thiện bản freeze, chừa sẵn chỗ cho cánh A

| Mục trong `protocol_freeze_r1_heldout.md` | Việc | Xong khi |
|---|---|---|
| §3 Lọc task (D3-1) | Ghi quyết định nhóm: min1 (292 task, đề xuất) hay min2 (42 task); nêu rõ hệ quả cho điều kiện §8.3 của proposal | Không còn chữ "ĐỀ XUẤT" ở dòng D3-1 |
| §4 Cấu hình | Thêm một dòng **chỗ trống** cho cánh A: tên (ví dụ `task_trace_a`), cờ, `ranking_config_hash` = "điền khi A chốt". Thêm một dòng ghi SCIP: bật hay tắt, theo kết quả mục B-3 | Có dòng chỗ trống; layer SCIP có quyết định |
| §5 Kết quả chính | Viết sẵn hai phương án cặp chính: (i) có A: `task_trace_a − bm25 / embedding / grep` và `task_trace_a − task_trace_rt1`; (ii) không có A: giữ nguyên như hiện tại. Tính lại họ Holm cho từng phương án | Hai bảng sẵn sàng, chỉ cần xóa một |
| §6 Kết quả phụ | Chốt có giữ Hit@k/Acc@k (`paper_metrics.py`) không. Thêm "token tới gold đầu tiên" báo cáo **cả hai cách tính** (chỉ task trúng, và đủ task với task trượt = 12.000) | Không còn chữ "ĐỀ XUẤT" |
| §2 Commit và môi trường | Ghi phiên bản SCIP (`@sourcegraph/scip-python@0.6.6`, node v24.15.0, `node-big`, `NODE_OPTIONS=--max-old-space-size=6144`) nếu SCIP được bật | Đủ để người khác dựng lại môi trường |
| §9 Ký duyệt | Thêm một dòng luật: "Nếu cánh A chưa đạt tiêu chí trước ngày X thì freeze với phương án (ii)" | Có ngày X do nhóm chốt |

### B-2. Chạy thử toàn bộ đường held-out trên task dev

Mục đích: bảo đảm lệnh ở §7 chạy được từ đầu tới cuối **trước** khi ký, để ngày chạy thật không gặp lỗi.

- Dùng đúng các cờ của §7, nhưng trên 2–3 task **dev** (không có `--allow-heldout`), ra thư mục mới, ví dụ
  `~/rt1/results/dryrun_freeze`.
- Kiểm tra: cánh embedding chạy được (cần GPU), RRF và `paper_metrics.py` đọc được kết quả, `summarize` ra đủ cặp,
  `builder_hash` khớp giá trị trong §2.
- Ghi thời gian và RAM mỗi task để ước lượng lại 292 task.
- **Xong khi:** có một ghi chú ngắn trong báo cáo B-6 gồm lệnh, thời gian/task, RAM đỉnh, và không có bước nào phải sửa tay.

Cần máy có `~/rt1` (dữ liệu dev, cache archive) và GPU. Nếu làm trên máy khác máy TV2 thì phải chép
`~/rt1/data/manifests`, `~/rt1/data/gold` và cài môi trường theo §2.

### B-3. Báo cáo R1 SCIP và G1 SCIP

Luồng A bận viết code, nên B viết hai báo cáo này.

- **R1 SCIP:** khi `~/rt1/results/r1_scip50` đủ 50 task, so với `~/rt1/results/r1_50` theo cặp (CI95 bootstrap như R1),
  đếm task SCIP lỗi, liệt kê task xấu đi và vì sao (hàm gold bị đẩy khỏi top-5 dù reach không đổi).
- **G1 SCIP:** số trong `~/rt1/g1/report_scip3` (SCIP chạy được 10/12 repo; `CALLS` P 0,967 / R 0,527; `CALLS + MAY_CALL`
  P 0,687 / R 0,618). Ghi rõ nhãn do Claude gán, người kiểm tra 30 mục (kappa 0,599).
- **Ghi rõ giới hạn C8:** G1 dùng `import_roots=()`, R1 dùng `("src", "lib")`. Sau khi luồng A (hoặc ai được giao) sửa C8,
  G1 cần chạy lại (khoảng 1 giờ) rồi cập nhật báo cáo.
- **Xong khi:** có `docs/status/tv2_r1_scip_2026-11-18.md` và `docs/status/tv2_g1_scip_2026-11-18.md`, kèm khuyến nghị
  bật hay tắt SCIP cho bản freeze.

### B-4. Một lệnh ra bảng báo cáo held-out

- Viết (hoặc gom từ `summarize`, `fusion.py`, `paper_metrics.py`) một lệnh nhận thư mục kết quả và in ra đúng các bảng
  của §5 và §6 (`mean_delta`, CI95, `p`, `p_holm`, số task thành công/lỗi, `builder_hash`, `manifest_hash`).
- Thử trên `r1_50` và `r1_emb50_t1024` (dev): số phải khớp các báo cáo dev đã có.
- **Xong khi:** một lệnh ra bản nháp `tv2_r1_heldout_<ngày>.md`; số trên dev khớp báo cáo cũ.

### B-5. Dọn repo trước khi tag

Những việc nhỏ, không đụng code xếp hạng (chi tiết ở `tv2_open_issues_2026-11-18.md`):

- **E8:** ba test mở thẳng `artifacts/sample_graph.db` → chép vào `tmp_path` trước khi mở, như `tests/mcp_server/test_resources.py:266`.
- **E7:** xóa `requirement.txt` (ghi `mcp<2` và LangChain, trái với `pyproject.toml`); sửa comment lỗi thời trong
  `requirements/mcp-server.in`.
- **E9:** chuyển `"worktree": {"bgIsolation": "none"}` từ `.claude/settings.json` sang `.claude/settings.local.json`.
- **G1-doc:** sửa dòng 88 và 116 của `tv2_r1_full_layers_2026-11-16.md` (xarray-4629 thua do layer, xarray-6992 thua do cờ).
- Lập **danh sách commit cho tag**: mọi file mà bản freeze yêu cầu phải nằm trong commit có tag (thay đổi embedding,
  `paper_metrics.py` nếu giữ Hit@k, phần SCIP nếu bật).
- Chạy toàn bộ test suite; ghi số pass/fail và các lỗi đã biết từ trước.
- **Xong khi:** `git status` sạch trừ những file chủ ý để ngoài; test suite chạy xong và được ghi lại.

### B-6. Ngân sách và lịch cho ngày chạy held-out

- Dung lượng đĩa (292 archive, có `--prune`), kích thước cache embedding, thời gian dự kiến:
  khoảng 7,5 giờ không embedding, 15–16 giờ có embedding; **khoảng 30 giờ nếu bật SCIP** (R1 SCIP trên 50 task mất khoảng 5–6 giờ).
- Chọn khung giờ và máy chạy (không chạy gì nặng khác cùng lúc); quy trình khi bị ngắt (`--resume`, chạy lại đúng task lỗi hạ tầng).
- **Xong khi:** có một đoạn "Kế hoạch chạy held-out" trong báo cáo B-2, nhóm đồng ý khung giờ.

### B-7. Việc cần người, nếu còn thời gian

- **C2:** gán nhãn component boundary (bộ kit đã có từ plan 17/11, Task 3) để G1 đủ 5/5 metric.
- **G5:** đối chiếu số CoSIL/ARISE trong `tv2_r1_paper_comparison_2026-11-17.md` với bản PDF.

## 3. Điểm đồng bộ giữa A và B

| # | Khi nào | Ai | Việc |
|---|---|---|---|
| S1 | R1 SCIP chạy xong | B | Báo cáo B-3; nhóm quyết bật hay tắt SCIP cho freeze |
| S2 | A xong kiểm chứng trên 25 task | A → B | A gửi: tên cánh, cờ, `ranking_config_hash`, số trên dev so với tiêu chí ghi trước. B điền vào §4, §5; A sửa `PRIMARY_PAIRS` trong `run_r1_ablation.py` |
| S3 | Sau S2, hoặc hết hạn ngày X | cả nhóm | Chọn phương án (i) hoặc (ii) ở §5; ký §9; commit; tạo tag `protocol-freeze-r1` |
| S4 | Sau tag | một người, một máy | Tạo manifest held-out (sau tag), chạy held-out **đúng một lần** theo §7 |
| S5 | Held-out xong | B | Chạy lệnh B-4 ra báo cáo; A kiểm tra phần cánh A |

**Tiêu chí của A (ghi trước, dùng ở S2):** reach hàm ≥ 0,64; R@5 hàm ≥ 0,363 (mức của `RT1_CONFIG`), mục tiêu khoảng 0,40–0,42;
Recall@B không giảm; token cùng nội dung giảm khoảng 30–40%. Đạt thì dùng phương án (i); không đạt hoặc quá hạn thì phương án (ii),
và phạm vi A chỉ báo cáo như thử nghiệm trên dev.

## 4. Lịch dự kiến

| Ngày | Luồng A | Luồng B |
|---|---|---|
| 18/11 | Chờ R1 SCIP xong; viết thiết kế phạm vi A | B-5 (dọn repo), B-1 (phần không phụ thuộc A) |
| 19/11 | Code lọc anchor + mở rộng method con; chỉnh trên `tune25` | B-3 (báo cáo SCIP, khi R1 xong), B-4 (lệnh báo cáo) |
| 20/11 | Khung xương + dừng sớm; kiểm chứng 25 task (graph tĩnh và SCIP) | B-2 (chạy thử đường held-out trên dev), B-6 |
| 21/11 | S2: gửi cấu hình cánh A | Điền §4–§5; S3: ký + tag |
| 21–22/11 | — | S4: chạy held-out (một lần); S5: báo cáo |

Ngày X (hạn chót cho cánh A) do nhóm chốt; đề xuất **20/11 tối**, để còn một ngày cho ký và chạy held-out.
