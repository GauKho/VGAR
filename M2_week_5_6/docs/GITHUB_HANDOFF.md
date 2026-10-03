# Bàn giao M2 tuần 5–6 qua GitHub

Ngày: 03/10/2026. Repository đích: `https://github.com/GauKho/VGAR.git`.

Project được đặt tại `M2_week_5_6/` trên nhánh riêng `m2-week-5-6-20261003`, không tích hợp logic vào code VGAR và không thay đổi nhánh main.

Sau điều chỉnh bố trí theo yêu cầu, snapshot mới nhất của nhánh chỉ có `M2_week_5_6/` ở cấp gốc; các file VGAR kế thừa từ main không còn xuất hiện trên nhánh M2. Lịch sử commit được giữ để khôi phục, không dùng force push.

**Không merge trực tiếp nhánh bàn giao này vào main:** commit điều chỉnh bố trí loại các file VGAR khỏi snapshot của nhánh M2. Khi muốn tích hợp, lấy riêng thư mục M2 hoặc cherry-pick commit thêm package `b453d0e`; không đưa các thay đổi xóa file VGAR vào main.

## Những gì được đưa lên nhánh

- Code `src/`, các CLI `scripts/`, toàn bộ source tests, `pyproject.toml` và `.gitignore`.
- README, PROGRESS, bản giải thích tiếng Việt và docs.
- Manifest pin `data/manifests/verified-c104f840cc67-25.json`.
- 25 developer gold patches trong `data/gold/patches/`, dùng cho scorer, không cấp làm context cho agent/M1.
- Toàn bộ retrieval run bàn giao `20261001T134641055034Z-5295e04e781d`: `result.json`, `REPORT.md`, 25 task JSON và 25 M1 request JSON. Người clone có thể mở trực tiếp case details, không cần chạy lại evaluation để xem bằng chứng.
- Tất cả logs nhỏ hiện có trong `results/bootstrap`, `tests`, `dataset`, `comparison`, `checks`, cùng `result.json`/`REPORT.md` ở các retrieval runs. Logs RED/FAIL lịch sử được giữ, không chỉ đưa các lần PASS.

## Lịch sử kết quả chi tiết qua Releases

Release bàn giao: [M2 W5–6 artifacts — 03/10/2026](https://github.com/GauKho/VGAR/releases/tag/m2-w5-w6-artifacts-20261003).

- Asset: `M2_W5_W6_results_history_20261003.zip` chứa toàn bộ `results/` tại thời điểm đóng gói, gold patches và manifest. Bao gồm các runs cũ/intermediate và các lần người dùng chạy lại ngày03/10, không chỉ run bàn giao ngày01/10.
- Asset checksum: `SHA256SUMS.txt` để kiểm tra file ZIP sau download.
- ZIP giữ prefix `M2_week_5_6/`. Giải nén vào folder mới để so sánh, không ghi đè các runs mới bạn đã tạo. Toàn bộ entries đã được đối chiếu SHA256 với bản local trước upload.
- Snapshot ZIP có299 files/entries, 404.231.767 bytes nén (khoảng385,51 MiB), từ3.064.884.285 bytes inputs. SHA256 của ZIP: `0ab280b57d52faff7a3bb36939602ce1ce33bd90c915ee9072d911c6aae1751a`.
- Release này là gói evidence dành cho nhánh M2, không phải bản phát hành chính của VGAR. Không đưa lịch sử artifacts trùng lặp nhiều GiB vào Git history.

## Những gì không được đưa lên Git

- `.venv/`, `__pycache__/`, dependencies và các secrets/credentials.
- Dataset Parquet tải về và source tar archives/bare Git caches; các inputs này có thể tải lại bằng scripts đã có.
- Task JSON/candidate snippets/M1 requests của các runs ngoài run bàn giao không nằm trực tiếp trên nhánh; xem ZIP lịch sử ở Releases.

Các file này **không bị xóa khỏi bản local** tại `D:\Project\CAPSTONES\M2_week_5_6`. Riêng run bàn giao đã có đủ task artifacts trên nhánh; các runs khác cần lấy ZIP lịch sử để audit/resume đầy đủ. Giữ cả `result.json`, `tasks/`, `m1_requests/` khi đối chiếu, không chỉ dùng report tổng hợp.

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

# CHỈ KHI CẦN LẤY PARQUET/TÁI TẠO INPUT: manifest và gold patches đã có trên nhánh.
# Không cần bước này nếu chỉ mở saved artifacts hoặc chạy evaluation với inputs hiện có.
& '.\.venv\Scripts\python.exe' '.\scripts\prepare_dataset.py' --count 25 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
$LASTEXITCODE

# LẦN ĐẦU CHẠY RETRIEVAL: không dùng --offline vì source archives chưa có.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --budget-tokens 4000
$LASTEXITCODE
```

Chạy từng bước, chỉ sang bước tiếp khi exit code0; đọc Evidence JSON nếu lỗi. Run bàn giao trên nhánh có full artifacts để audit; nếu muốn resume, phải giữ nguyên source/config/manifest binding và archive cache phù hợp, không coi cached outputs là source archive. Khi đã tải đủ source archives, lần chạy sau có thể dùng `--offline`. Không cần cài VGAR, LLM, GPU, Docker hoặc pytest để chạy package này.

Kết quả Graph vẫn chờ output thật của M1; việc push lên GitHub không thay đổi trạng thái DoD.
