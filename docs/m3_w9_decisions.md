# Quyết định M3 cho pilot W9

Lập 25/10/2026. Phạm vi: pilot 5 task × A0/A1/A2 trên **dev** (M3-W9-3). Không áp dụng cho held-out; held-out theo `protocol_freeze` W12.
Nguyên tắc của plan: không đổi model, prompt, budget hay manifest mà không ghi lại. Mỗi mục dưới đây ghi lựa chọn, lý do, phương án đã bỏ và hệ quả.

**Trạng thái chung: M3 ĐỀ XUẤT.** Chuyển một mục sang "Chốt" khi M3 quyết định (ghi ngày) hoặc nhóm duyệt. Liên quan: `docs/m2_w9_decisions.md` (D1–D8 gốc), spec `docs/superpowers/specs/2026-10-25-m3-w9-design.md`.

| ID | Quyết định | Trạng thái |
|---|---|---|
| D1 | A0 = bm25, A1 = graph, A2 = graph | Đề xuất |
| D4 | Test tái hiện viết tay từ issue, không dùng F2P/P2P | Đề xuất |
| D5 | Giữ `input_cap` 6000; một budget snippet chung **B = 1500** cho cả hai arm | **Chốt 25/10** (người dùng duyệt), M1 review code |
| D7 | Qwen3-4B-Instruct-2507 fp16, policy `demo.json`, `docker_admitted`, global 1800 s | Đề xuất |
| D9 | A2 khi image thiếu mypy/Ruff: chạy và ghi ERROR, không dựng image mới | Đề xuất |
| D10 | Dữ liệu pilot do M3 tự sinh lại thì ghi rõ nguồn gốc của hash | **Áp dụng 25/10** |
| D11 | Trình bày snippet method thụt lề thành dòng nguyên (prompt V11) | **Chốt 25/10** (người dùng duyệt), M2 review code |

## D1. Variant → arm

- **Chọn:** A0 = `bm25`, A1 = `graph`, A2 = `graph`. Ghi trong `configs/m3/w9_pilot.json` (`variants[].arm`), không sửa `configs/m2/variants/*.json`.
- **Lý do:** A0 với A1 chỉ khác retrieval (cùng tests-only), nên đo được tác động của graph. A1 với A2 chỉ khác verification (thêm static delta). Đây đúng là thiết kế ablation của plan.
- **Đã bỏ:** A2 = bm25 (khi đó A1 với A2 khác hai biến cùng lúc).
- **Hệ quả:** `policy_hash` của mỗi variant gắn với arm; đổi mapping thì ra `experiment_id` mới.

## D4. Oracle kiểm tra lỗi

- **Chọn:** mỗi task có một test tái hiện **viết từ nội dung issue**, đặt ở `tests/vgar_w9_repro_*.py` (engine chỉ nhận overlay dạng này). Người viết **không đọc gold patch, test_patch hay F2P/P2P** của SWE-bench.
- **Lý do:** engine hiện không nhận `test_patch` của SWE-bench; dùng F2P/P2P còn làm lộ đáp án. Smoke W9-3 của M2 trên Xarray đã đi theo hướng này.
- **Đã bỏ:** (a) dùng F2P/P2P (cần M2 sửa admission, và phải gọi là "oracle-assisted"); (b) bỏ hẳn Matplotlib và Pylint (vẫn hợp lệ nếu không viết kịp, khi đó hai task ra `TASK_INPUT_MISSING`).
- **Hệ quả:** kết quả resolved của pilot dựa trên test tái hiện, **không phải** điểm chính thức. Điểm chính thức do harness của M1 chấm ở W10.
- **Kiểm bắt buộc:** test phải **FAIL trên base commit** bên trong image của task trước khi dùng (runbook bước 5).
- Bản nháp: xem `configs/m3/w9_pilot/tasks/README.md`.

## D5. Cỡ context của prompt

- **Chọn:** giữ `input_cap` 6000 (cấu hình duy nhất đã chạy model thật trên RTX 4050 6 GB). Export bundle hai arm với **một budget chung B** cho mọi task, sao cho mọi cặp trong preflight đều `FITS`.
- **Cách tính B:**
  1. Chạy `preflight` với bundle 8000 hiện có.
  2. Với mỗi cặp, phần cố định = `input_tokens` − `total_token_count` của bundle (trong `context_manifest.json` hoặc audit export).
  3. B = 6000 − max(phần cố định) − 300 (dự phòng cho phần `present_context` thêm vào).
- **Cần M1 sửa code**, vì budget 8000 đang viết cứng:
  - `src/vgar/evaluation/retrieval/pilot_export.py:55` gọi `retriever.retrieve(anchors, 8000, …)`;
  - `create_bm25_handoff` dùng mặc định `budget_tokens=8000`;
  - `scripts/export_w9_pilot_bundles.py:39–42` từ chối mọi profile khác `configs/m1/w9_bundle_profile.json`.

  Đề xuất cho M1: thêm tham số `budget_tokens` cho `export_task` và truyền xuống cả hai arm; cho script nhận thêm một profile repair mới (`configs/m1/w9_bundle_profile_repair.json`, chỉ khác `profile` và `budget_tokens`). Thay đổi thuộc module của M1 nên M1 làm hoặc duyệt.
- **Đã bỏ:** (b) nâng `input_cap`, vì GPU 6 GB đang offload và prompt khoảng 11–12k token có nguy cơ timeout hoặc hết bộ nhớ; (a) bundle smoke cắt tay, vì không phải output của retrieval và hai arm nhận context giống hệt nhau.
- **Hệ quả:** budget repair nhỏ hơn 8000 dùng khi đánh giá retrieval. Ghi vào protocol W12, và M1 báo thêm Recall@B.

## D7. Model, runtime, timeout

- **Chọn:** `Qwen/Qwen3-4B-Instruct-2507@cdbee75f…`, fp16, `do_sample=false`. Policy giữ nguyên `configs/m2/demo.json`: `prompt_version m2-w78-v11`, input 6000, output 1536, generation 900 s, command 120 s, global 1800 s; chỉ đổi `runtime` thành `docker_admitted`. File: `configs/m2/w9_pilot_linux.json`.
- **Lý do:** giữ đúng cấu hình model đã chạy thật ở W7–W8. 1800 s bằng ngưỡng 30 phút/task của plan.
- **Hệ quả:** attempt chạm global deadline có `timed_out=true`; thời gian của nó báo là "≥ 30 phút" và không tính vào trung bình.

## D9. A2 khi image thiếu mypy/Ruff

- **Chọn:** vẫn chạy A2; nếu tool thiếu thì record ERROR kèm lý do của engine.
- **Lý do:** dựng image mới làm đổi digest, kéo theo phải chạy lại profile và harness. Không đáng cho pilot.
- **Hệ quả:** pilot không đo được tác động của static check. Ghi trong phần giới hạn của `docs/status/m3.md`.

## D10. Nguồn gốc hash khi M3 tự sinh dữ liệu

- Admission yêu cầu hash manifest, profile và bundle được "duyệt độc lập". Nếu M3 tự chạy lại `prepare_task_env.py` và `export_w9_pilot_bundles.py` rồi pin hash từ chính output đó, thì ghi trong `docs/status/m3.md`: "hash do M3 sinh ngày …, lệnh …, chưa được M1 duyệt".
- Với pilot trên dev thì chấp nhận được. Với held-out, hash phải do người khác người chạy cung cấp.

## Kết quả 25/10 (M3 tự sinh dữ liệu, người dùng duyệt từng bước)

### D5: đo thật và chốt B = 1500

- Code M1 đã sửa (chờ M1 review):
  - `pilot_export.export_task(..., budget_tokens=8000)` truyền budget xuống cả hai arm;
  - `export_w9_pilot_bundles.py` nhận thêm `configs/m1/w9_bundle_profile_repair.json` (chỉ khác `profile` và `budget_tokens`);
  - test ở `tests/test_w9_pilot_bundles.py`.
- **Thuế trình bày:** mỗi snippet tốn thêm khoảng **210 token** metadata trong prompt V11. Graph trả nhiều node nhỏ (29–55 snippet), BM25 trả ít đoạn lớn (3–8 snippet). Vì vậy với cùng B, prompt của graph tốn khoảng 1,8–2,5 lần B, còn bm25 khoảng 1,1–1,2 lần B. Phần cố định F của prompt: matplotlib ≈ 2306, xarray ≈ 1550, pylint ≈ 966 token.
- Preflight theo B:

  | B | Kết quả |
  |---|---|
  | 8000 | mọi cặp `OVER_CAP` (graph 16–20k token) |
  | 1800 | xarray graph vượt 722 |
  | 1300 | cả 9 cặp `FITS` |
  | **1500** | **cả 9 cặp `FITS`**, cặp dư ít nhất còn 847 token |

  Số token không tăng đều theo B, vì packer chọn tập snippet khác nhau.
- **Cần nhóm xem trước W10:**
  - với budget chung, graph bị thuế trình bày nặng hơn; A0 với A1 khác nhau cả ở yếu tố này, không chỉ ở chất lượng retrieval;
  - phương án: gọn bớt metadata trình bày (phải qualify lại V11), hoặc báo cáo kèm số token prompt của từng arm.

### D11: snippet method thụt lề

- **Phát hiện:** preflight trên bundle thật bị từ chối toàn bộ với `Replacement requires complete source lines`. Node range của M1 bắt đầu một method ở cột thụt lề (`start_col = 4`), còn V11 đòi dòng nguyên bắt đầu ở cột 0. Ví dụ xarray graph có 44/47 snippet như vậy.
- **Sửa** (`src/vgar/repair/context_presentation.py`, chờ M2 review): nếu phần trước snippet trên cùng dòng chỉ toàn khoảng trắng thì lấy lại khoảng trắng đó từ source và ghi `leading_whitespace_added`. Code khác đứng trước snippet vẫn bị từ chối; snippet read-only không đổi. Test ở `tests/m2/w910/test_context_presentation_lines.py`; `tests/m2` pass 398/398.

### D10: nguồn gốc dữ liệu pilot (M3 sinh, chưa được M1 duyệt)

Toàn bộ dữ liệu nằm dưới `~/w9` trong WSL Ubuntu trên laptop.

- **Dataset:** parquet SWE-bench_Verified `c104f840` lấy từ cache HF trên Windows; hash `sha256:a45b1fe4…` trùng bản đã pin.
- **Checkout:** `prepare_w9_pilot_inputs.py --prepare-sources`; manifest hash trùng `98984466…`; 5 repo đúng base commit.
- **Bundle:** `export_w9_pilot_bundles.py`:
  - 8000: `~/w9/bundle-runs/b8000/20261025T101036Z-5db45bfa162f` (10/10 PASS);
  - repair B = 1500: `~/w9/bundle-runs/repair/20261025T122406Z-9df5307bf620` (10/10 PASS).
- **Profile:** `prepare_task_env.py --execute` (run `w95-61e1a90b…`, COMPLETE). Astropy EXCLUDED `COLLECTION_FAILED`, Django EXCLUDED `PYTEST_UNAVAILABLE`, ba task còn lại COLLECTED, khớp kết quả M1-W9-5.
  - Image được pull trước theo đúng digest đã pin, thay cho `--prepare-images`.
  - Ngưỡng tài nguyên không hạ. Đã chạy `drop_caches=1` một lần trong WSL trước collection để RAM Windows vượt ngưỡng 4 GiB.
- **Hash trong `configs/m3/w9_pilot.json`** đọc từ chính output ở trên, nên **không độc lập**. Nếu M1 muốn duyệt thì so với lần chạy của họ.
