# TV2 · U1: incremental benchmark (4 repo dev), 11/11/2026

Plan 2 tuần, tuần 2 ngày 4 ("Incremental benchmark: `bench_incremental.py`", [rq] mục 6). Metric theo [P] dòng 1201–1207: cold build time, warm update time, changed files, affected nodes, cache hit rate. Cột "Trùng full rebuild" cũng là số `incremental update correctness` của G1 ([P] dòng 1341–1347).

## Cách đo

- Công cụ có sẵn: `scripts/bench_incremental.py` → `vgar.evaluation.incremental_bench.run_bench`. Không sửa `src/`.
- Code: bản chép `src/` và `scripts/` của commit `6569702d` (cộng phần follow-up SC-1 chưa commit ở `src/vgar/contracts/schema.py`) vào `~/vgar-u1` (WSL). Vì bản chép không có `.git` nên `u1.md` ghi `commit None`.
- Repo: cây Python tại `base_commit` của 4 task dev trong `w10-dev-50-gold.json`, lấy bằng helper tải/giải nén của R1 (chỉ file `.py`). Chọn theo kích thước: requests (75 file), pytest (210), xarray (149 file nhưng graph khoảng 40k node), django (2.545 file).
- Mỗi repo: 3 lần cold build, 3 kịch bản × 10 lần warm update. Mỗi lần warm: khôi phục bản gốc, build, sửa đúng một chỗ, rồi `update`. Ở lần đầu, so graph sau update với graph build lại từ đầu (sau chuẩn hóa).
  - `body_edit`: thêm một dòng vào thân hàm.
  - `public_signature`: thêm tham số `_vgar_bench=None` vào chữ ký.
  - `add_delete_file`: thêm module mới ở lần chẵn, xóa nó ở lần lẻ.
- Resolver `tree-sitter+python-static-v4-external-import`, không bật tree-sitter-graph, JARVIS hay Joern. Máy: WSL2 Ubuntu (Linux 6.6), 16 luồng, 7,8 GB RAM, Python 3.11.17.

```bash
~/u1/u1_run.sh          # 4 lệnh: bench_incremental.py --repo ~/u1/repos/<id> --source-roots <root> --repeats 10 --out <dir>/<id>
```

Kết quả: `~/u1/results/20261111T100231Z/<task>/u1.json` và `u1.md` (WSL), log `~/u1/u1.log`.

## Kết quả

| Repo (node graph) | Kịch bản | Cold build (s) | Warm update p50 / p95 (s) | Speedup | File đổi | Node bị ảnh hưởng | Cache hit | Trùng full rebuild |
|---|---|---|---|---|---|---|---|---|
| requests (khoảng 3,6k) | body_edit | 0,782 | 0,090 / 0,143 | 8,7× | 1 | 206 | 98,7% | có |
| | add_delete_file | 0,782 | 0,070 / 0,132 | 11,1× | 1 | 6 | 98,7% | có |
| | public_signature | 0,782 | 0,102 / 0,145 | 7,7× | 1 | 208 | 98,7% | có |
| pytest (khoảng 25k) | body_edit | 3,957 | 1,048 / 1,557 | 3,8× | 1 | 1.040 | 99,5% | có |
| | add_delete_file | 3,957 | 0,885 / 0,968 | 4,5× | 1 | 6 | 99,5% | có |
| | public_signature | 3,957 | 0,943 / 1,464 | 4,2× | 1 | 1.038 | 99,5% | có |
| xarray (khoảng 40k) | body_edit | 7,138 | 1,664 / 1,959 | 4,3× | 1 | 2.341 | 99,3% | có |
| | add_delete_file | 7,138 | 1,499 / 1,535 | 4,8× | 1 | 6 | 99,3% | có |
| | public_signature | 7,138 | 1,681 / 2,224 | 4,2× | 1 | 2.334 | 99,3% | có |
| django (khoảng 177k) | body_edit | 29,644 | 8,856 / 11,722 | 3,3× | 1 | 1.291 | 100,0%\* | có |
| | add_delete_file | 29,644 | 9,363 / 12,085 | 3,2× | 1 | 6 | 100,0%\* | có |
| | public_signature | 29,644 | 8,722 / 10,318 | 3,4× | 1 | 1.291 | 100,0%\* | có |

\* Làm tròn từ 2.544/2.545 file.

RAM lớn nhất của cả tiến trình benchmark: requests 0,1 GB, pytest 0,5 GB, xarray 0,8 GB, django 3,4 GB. Thời gian chạy: requests 36 giây, pytest 3,5 phút, xarray 6,6 phút, django 27,6 phút.

## Nhận định

- **Đúng (G1 incremental update correctness): 12/12** kịch bản cho graph sau update trùng graph build lại.
- **Nhanh hơn build lại 3,2–11,1 lần.** Repo càng lớn thì speedup càng nhỏ: django chỉ 3,3×, warm update khoảng 9 giây. Lý do: phần parse là O(Δ) (chỉ parse lại file đổi, cache hit ≥ 98,7%), nhưng **phần link vẫn O(N)**: liên kết lại toàn repo. Đây cũng đúng với nhận xét của TV1 ở L6-6 ("parse changed files, relink toàn repo").
- **Chưa đạt thuật toán §11.2 của proposal** (chỉ relink phần bị ảnh hưởng: reverse dependencies, tests, components). Muốn speedup tăng theo kích thước repo thì phải làm link theo phần bị ảnh hưởng. Với django, phần còn lại khoảng 9 giây gần như toàn là link.
- "Node bị ảnh hưởng" được định nghĩa ở `incremental.py:56`: các node thêm hoặc bớt, cộng hai đầu của mọi cạnh chỉ có ở một trong hai graph. Với `body_edit` / `public_signature` con số là 206 đến 2.341. Nó phụ thuộc file đích (bao nhiêu node và cạnh của file đó đổi khi một dòng chen vào), không phụ thuộc kích thước repo: django ra 1.291, ít hơn xarray. `add_delete_file` luôn là 6 node của module thêm hoặc xóa.

## Giới hạn

- 4 repo, mỗi repo một đích sửa duy nhất (do `pick_target` chọn); chưa đo sửa nhiều file cùng lúc.
- Chỉ graph Python tĩnh: không tree-sitter-graph (L1), JARVIS (L2-1), Joern (L3-1), không overlay `G_task`. Kiểm "trùng build lại" có bật tree-sitter-graph thì báo cáo GA (13 repo) đã làm riêng.
- Cây repo chỉ gồm file `.py`, nên không có ConfigEntry/DeploymentUnit từ file không phải Python.
- Đo trên WSL2, đĩa ext4 của VM; thời gian trên Windows có thể khác.
