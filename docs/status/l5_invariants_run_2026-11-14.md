# L5-1/L5-2 invariant ngữ nghĩa: kết quả chạy (14/11/2026)

Spec: `docs/superpowers/specs/2026-11-14-layer5-invariants-design.md`. Plan: `docs/superpowers/plans/2026-11-14-layer5-invariants.md`.

**Invariant ở đây là "likely invariant" suy từ trace của test, là bằng chứng, không phải chứng minh** ([P] §5.3, §8.5).

## 1. Đã làm gì

- `run_relevant_tests` (EV-3) ghi trace trong đúng hai lần chạy test vốn có (trước và sau patch), học invariant trên bản gốc, kiểm trên bản patch. Kết quả nằm trong trường `semantic_invariants` của evidence EV-3; `rank_patch_candidates` đọc nó để điền `semantic_invariant_preserved`.
- Chỉ học và kiểm trên các test **pass ở bản gốc**. Hành vi trên đường đi của test đang fail vốn phải thay đổi nên không kiểm.
- Lõi là Daikon khi đã cấu hình `VGAR_DAIKON_JAR` và `VGAR_JAVA_HOME` (đường dẫn tuyệt đối). Không có Java hoặc Daikon lỗi/quá giờ thì dùng bộ suy Python và ghi lý do trong `reasons`.
- Phần Python luôn chạy: invariant về exception (Daikon bỏ qua lần thoát bằng exception), cờ `x_is_none` cho Daikon, lọc nhiễu theo danh sách cố định, gắn `node_id` của graph cho mỗi vi phạm.
- Mặc định **tắt**: host bật bằng `DiffTestsProvider(..., invariants=InvariantSettings(daikon=DaikonConfig.from_env()))`.

## 2. Kết quả trên vgar-demo-shop (bản có bug, 10 test pass + 1 test fail)

| Biến thể | Loại | Test bắt? | Bộ suy Python (đo trong CI, `tests/test_invariants_demo_shop.py`) | Daikon 5.9.0 (spike 14/11) |
|---|---|---|---|---|
| base | gốc | – | PASS | 0 vi phạm |
| gold_fix | sửa đúng | đổi `test_bug` | **PASS** | 13 vi phạm khi học trên mọi test; quy tắc "chỉ test pass ở gốc" chưa chạy lại với Daikon |
| R1–R4 | refactor | không | PASS | 0 |
| M3 tổng bỏ phí ship | mutant | có | FAIL | 2 |
| M4 VAT chia nguyên | mutant | có | FAIL | 4 |
| M5 tên sản phẩm viết hoa | mutant | **không** | **FAIL** | 1 |
| M6 tự áp coupon SAVE10 | mutant | **không** | **FAIL** | 2 |
| M7 cho phép số lượng 0 | mutant | có | FAIL | 10 (6 sau lọc nhiễu) |
| M1, M2, M8 | mutant | không | PASS (bỏ sót) | 0 (bỏ sót) |

Đọc bảng: invariant bắt thêm 2 mutant mà test bỏ sót (M5, M6), không báo động giả trên 4 refactor và trên bản sửa đúng. Cả hai engine bỏ sót M1, M2, M8 vì test không đi qua giá trị bị đổi.

Chạy lại phần Daikon (bạn chạy, cần Java):

```
.venv\Scripts\python.exe scripts\invariant_spike\spike.py trace D:\kltn\vgar-demo-shop\vgar-demo-shop C:\Users\<user>\AppData\Local\Temp\vgar-daikon-spike
.venv\Scripts\python.exe scripts\invariant_spike\spike.py daikon C:\Users\<user>\AppData\Local\Temp\vgar-daikon-spike D:\tools\daikon-5.9.0\daikon-5.9.0\daikon.jar D:\tools\jdk21\jdk-21.0.13+9\bin\java.exe
```

Cột Daikon ở trên là spike (học trên mọi test). Muốn có số Daikon theo đúng quy tắc của code chính thức, chạy `compute_semantic_invariants` với `DaikonConfig` đã cấu hình trên trace của `tests/invariant_helpers.run_variant` (chưa chạy).

## 3. Chưa đo

- **Mutant pool W10 (tầng 3):** pool chạy bằng Docker admission. Executor Docker chỉ chấp nhận một dòng lệnh pytest cố định và chỉ copy ra `nodeids.json`/`junit.xml`, nên với Docker kết quả là `NOT_RUN` / `TRACE_OUTPUT_UNAVAILABLE`. Cần một thay đổi riêng cho executor Docker (thêm plugin và copy trace ra) trước khi đo RQ4 trên W10.
- Tỉ lệ báo động giả trên repo lớn; thời gian chạy thêm do trace.
- L5-3 (`coverage_count`), trọng số `w_sem`.

## 4. Giới hạn

- Repo mẫu nhỏ, code tất định: invariant phần lớn có dạng "một trong {…}", nên chỉ bắt được mutant làm đổi giá trị mà test đã đi qua.
- Danh sách lọc nhiễu được chốt từ demo-shop; repo khác có thể có mẫu nhiễu khác.
- Trace giới hạn 1.000 lần gọi mỗi hàm và 50 MB mỗi lần chạy; vượt thì có `TRACE_TRUNCATED` trong `limitations`.
