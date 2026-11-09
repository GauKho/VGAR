# TV2 · L2-1: kết quả chạy thật JARVIS

Spec: `docs/superpowers/specs/2026-11-10-tv2-l2-1-jarvis-design.md`. Số liệu chỉ để kiểm tra, không dùng để chỉnh luật. Image `vgar/jarvis-analyzer:v1.0` dựng từ `python:3.11-slim@sha256:07d48240...`, JARVIS commit `8871b86`, `PYTHONHASHSEED=0`, giới hạn 120 s.

## 1. Fixture có đáp án

Chấm bằng cách của `tests/test_callgraph_cases.py` trên `vgar-callgraph-cases` và bản `-flat`, resolver static, kết quả JARVIS thật đã ghi lại ở `tests/fixtures/jarvis/`.

| | tp | fp | fn | Precision | Recall |
|---|---|---|---|---|---|
| `CALLS`, không có JARVIS | 14 | 0 | 45 | 1,000 | 0,237 |
| `CALLS`, có JARVIS | 26 | 0 | 33 | 1,000 | 0,441 |
| `CALLS + MAY_CALL`, không có JARVIS | 44 | 32 | 15 | 0,579 | 0,746 |
| `CALLS + MAY_CALL`, có JARVIS | 53 | 28 | 6 | 0,654 | 0,898 |

`CALLS` nhận nhầm lời gọi ngoài repo hoặc không xác định: 0 ở cả hai. **Đạt tiêu chí** precision của `CALLS` không giảm, recall tăng, và số nhận nhầm không tăng. Test `test_jarvis_meets_the_precision_goal` giữ tiêu chí này.

## 2. Repo thật

Tất cả `ready`, không repo nào hết 120 s, không có file bị loại. Số cạnh là tổng của `graph.json`; cột 3.8 lấy từ lần chạy cũ, chưa cố định seed và chưa dàn file theo source root.

| Repo | File | Thời gian | Cạnh JARVIS | Cạnh, lần 3.8 | `CALLS` trước → sau | `MAY_CALL` trước → sau |
|---|---|---|---|---|---|---|
| boundary_cases | 12 | 1,3 s | 52 | 52 | 15 → 18 | 2 → 3 |
| multi_package | 6 | 1,2 s | 15 | 15 | 8 → 9 | 1 → 0 |
| callgraph_cases | 23 | 1,5 s | 133 | 108 | 55 → 69 | 70 → 61 |
| sample_repo | 7 | 1,2 s | 12 | 10 | 5 → 5 | 0 → 0 |
| m2_clean_repo | 1 | 1,1 s | 0 | 0 | 1 → 1 | 0 → 0 |
| demo_shop | 8 | 1,2 s | 25 | 25 | 26 → 26 | 10 → 10 |
| requests | 19 | 2,2 s | 612 | 612 | 253 → 267 | 215 → 211 |
| click | 17 | 2,5 s | 979 | lỗi | 499 → 528 | 363 → 350 |
| jinja2 | 25 | 3,4 s | 1.703 | 1.662 | 1.052 → 1.166 | 599 → 460 |
| httpx | 23 | 2,7 s | 898 | 897 | 369 → 410 | 291 → 247 |
| rich | 78 | 6,1 s | 2.396 | 2.394 | 1.015 → 1.209 | 1.282 → 1.178 |
| vgar | 170 | 10,8 s | 5.315 | 5.357 | 2.513 → 2.750 | 1.879 → 1.751 |
| networkx | 288 | 33,5 s | 11.725 | 11.827 | 5.191 → 6.202 | 43.290 → 43.321 |
| xarray-4629 | 101 | 13,6 s | 5.686 | hết giờ | 8.042 → 8.493 | 16.707 → 16.243 |

- `click` trước đây lỗi trên 3.8 vì `click/utils.py` dùng `match`; trên 3.11 chạy được.
- `callgraph_cases` tăng từ 108 lên 133 cạnh vì import trong `src/` giờ được hiểu là nội bộ.
- **xarray không còn hết giờ**, khác với lần thử trước (580–900 s). Lần đó chạy trên Windows với bản vá, gồm cả code test; chưa tách được yếu tố nào quyết định.

| Trên xarray | Số lượng |
|---|---|
| `CALLS` được xác nhận | 1.828 |
| `MAY_CALL` nâng thành `CALLS` | 347 |
| `CALLS` mới | 104 |
| `MAY_CALL` mới | 164 |
| Xung đột | 6 |
| Lời gọi ra ngoài repo | 2.411 |

## 3. Lặp lại và đa nền tảng

| Repo | sha256 của `graph.json`, Windows | WSL Ubuntu |
|---|---|---|
| requests | `a6c19de9af8c3f06` | `a6c19de9af8c3f06` |
| jinja2 | `f4b15c10ac787161` | `f4b15c10ac787161` |
| fixture | `997180a46aecda0c` | `997180a46aecda0c` |

Số `CALLS`, `MAY_CALL` và các số đếm cũng giống nhau trên hai máy. Trên WSL, `tests/test_jarvis_runner.py`: 36 pass, gồm 4 test Docker thật. Không còn container `vgar-jarvis` sau khi chạy.

## 4. Test suite

Toàn bộ test (bỏ marker `hf`, `docker`), sau khi sửa theo review: 2.696 pass, 20 skip, 2 xfail; 3 fail đã biết từ trước (`test_runner_contract`, `test_official_harness`, `test_w9_bundle`). Lần chạy bị dừng ở 97% vì thiếu RAM nên 63 test cuối được chạy riêng.

Các lỗi đã sửa theo review: một file có biểu thức quá sâu làm mất kết quả cả repo; tên mơ hồ không chặn `CALLS`; call site không mang tên đích vẫn được coi là chắc chắn. Số liệu ở §1–§3 đo lại sau khi sửa và không đổi.

## 5. Giới hạn

Như spec §9. Thước đo độ đúng mới có trên hai repo fixture; trên repo thật chỉ có số lượng, chưa có đáp án. Chưa đo khi bật SCIP.
