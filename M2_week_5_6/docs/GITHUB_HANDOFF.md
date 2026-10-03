# Bàn giao M2 tuần 5–6 qua GitHub

Ngày: 03/10/2026. Repository đích: `https://github.com/GauKho/VGAR.git`.

Project được đặt tại `M2_week_5_6/` trên nhánh riêng `m2-week-5-6-20261003`, không tích hợp logic vào code VGAR và không thay đổi nhánh main.

Sau điều chỉnh bố trí theo yêu cầu, snapshot mới nhất của nhánh chỉ có `M2_week_5_6/` ở cấp gốc; các file VGAR kế thừa từ main không còn xuất hiện trên nhánh M2. Lịch sử commit được giữ để khôi phục, không dùng force push.

**Không merge trực tiếp nhánh bàn giao này vào main:** commit điều chỉnh bố trí loại các file VGAR khỏi snapshot của nhánh M2. Khi muốn tích hợp, lấy riêng thư mục M2 hoặc cherry-pick commit thêm package `b453d0e`; không đưa các thay đổi xóa file VGAR vào main.

## Những gì được đưa lên nhánh

- Code `src/`, các CLI `scripts/`, toàn bộ source tests, `pyproject.toml` và `.gitignore`.
- README, PROGRESS, bản giải thích tiếng Việt và docs.
- Manifest pin `data/manifests/verified-c104f840cc67-25.json`.
- Báo cáo và `result.json` tổng hợp của retrieval run chuẩn `20261001T134641055034Z-5295e04e781d`.
- Evidence test/check/dataset/comparison được dẫn ở bảng kết quả của bản giải thích, cùng evidence kiểm thử trước publish.

## Những gì không được đưa lên Git

- `.venv/`, `__pycache__/`, dependencies và các secrets/credentials.
- Dataset Parquet tải về, source tar archives/bare Git caches, gold patch inputs.
- Các task JSON/candidate snippets/M1 requests dung lượng lớn và toàn bộ lịch sử artifacts chi tiết. Riêng run chuẩn có khoảng648 MB dữ liệu; không đưa bộ này lên Git.

Các file này **không bị xóa khỏi bản local** tại `D:\Project\CAPSTONES\M2_week_5_6`. Những đường dẫn `tasks/<id>.json`/`m1_requests/<id>.json` trong tài liệu mô tả bản local đầy đủ; sau clone chúng chưa tồn tại cho đến khi evaluation được chạy lại. `result.json`/REPORT trên GitHub là bằng chứng tổng hợp, không thay thế đầy đủ task artifacts khi audit hoặc resume.

`New_task/project_plan_16_weeks.md` là tài liệu đầu vào ngoài package; không được sao chép vào nhánh này. Link tới file đó trong bản giải thích có thể chỉ hoạt động trong workspace CAPSTONES gốc; các yêu cầu tuần5–6 đã được trình bày trong bản giải thích.

## Thành viên lấy về và chạy

```powershell
# LẦN ĐẦU: clone đúng nhánh vào thư mục mới chưa tồn tại.
git clone --branch m2-week-5-6-20261003 --single-branch https://github.com/GauKho/VGAR.git VGAR-M2-W5-W6

# MỖI PHIÊN: chuyển vào package độc lập, không chạy từ root VGAR.
Set-Location '.\VGAR-M2-W5-W6\M2_week_5_6'

# LẦN ĐẦU: tạo môi trường và cài dependency đọc Parquet.
py -3.11 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install pyarrow==23.0.1

# KIỂM THỬ CODE: tạo evidence mới trong results/tests/.
& '.\.venv\Scripts\python.exe' '.\scripts\record_tests.py'
$LASTEXITCODE

# CHUẨN BỊ INPUT: lấy đúng revision và tái tạo gold patches.
& '.\.venv\Scripts\python.exe' '.\scripts\prepare_dataset.py' --count 25 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
$LASTEXITCODE

# LẦN ĐẦU CHẠY RETRIEVAL: không dùng --offline vì source archives chưa có.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --budget-tokens 4000
$LASTEXITCODE
```

Chạy từng bước, chỉ sang bước tiếp khi exit code0; đọc Evidence JSON nếu lỗi. Không dùng resume từ bản tổng hợp trên GitHub vì task artifacts cũ không được commit. Khi đã tải đủ archives, lần chạy sau có thể dùng `--offline`. Không cần cài VGAR, LLM, GPU, Docker hoặc pytest để chạy package này.

Kết quả Graph vẫn chờ output thật của M1; việc push lên GitHub không thay đổi trạng thái DoD.
