# M3-X2b — chẩn đoán vì sao 3 lần thử ReAct đều fail (04/11)

Nguồn: run `results/m3/w12/agent/20261104T050429Z` (clone `~/vgar-x2b`, code sau các sửa trace 04/11) và run
`20261103T151652Z`. Chỉ đọc artifact, chưa sửa code. Qwen3-4B-Instruct-2507, `--generator agent`, A2.

## Kết luận

Vòng ReAct của agent chạy đúng: agent theo `NEXT` ở mọi lượt, trừ một lần gọi `analyze_patch_impact` mà system
prompt cho phép; không có lần gọi sai do agent. 0/5 resolved đến từ ba nguyên nhân:
1. Ngữ cảnh không chứa đoạn code cần sửa ở 3/5 task (retrieval/đóng gói ngữ cảnh).
2. Model không viết diff đúng định dạng V11 (NO_OP, output bị cắt).
3. Phản hồi cho lần thử sau quá nghèo và model sinh greedy, nên các lần thử ra diff giống hệt nhau từng byte.

Ngoài ra có 4 lỗi trong code M3 (mục "Lỗi code").

## Bằng chứng theo triệu chứng

- **`apply_patch` NO_OP** (astropy 3/3 lần, matplotlib 3/3 lần): diff không thay đổi gì.
  - Astropy lần 1: 12 dòng `-` và 12 dòng `+` giống hệt nhau.
  - Astropy lần 2 và 3: mọi dòng có tiền tố dấu cách. Model có sửa một dòng thành `plural, required_columns))`, nhưng
    viết như dòng ngữ cảnh, nên bộ chuẩn hóa bỏ hunk vì no-op (`patch_normalize.py:139`). Viết đúng định dạng thì thay
    đổi này đã qua test repro (`assert "found 'time'" not in message`).
  - 22/22 diff của hai run có dòng ngữ cảnh, dù V11 yêu cầu chỉ có khối `-` rồi khối `+`; 12/22 lặp header cho cùng file.
- **`run_relevant_tests` FAIL** (django 3/3 lần): test kiểm `global_settings.FILE_UPLOAD_PERMISSIONS == 0o644` và báo
  `None != 420`. File gold `django/conf/global_settings.py` không nằm trong 100 ứng viên graph, nên model sửa sai file.
- **`analyze_patch_impact` INVALID_ARGUMENT "Rename/duplicate file"**: lỗi ở host.
  - `tool_agent.py:275` lưu diff thô của model.
  - Bộ chuẩn hóa chấp nhận header lặp liên tiếp (`patch_normalize.py:60-62`), nên engine apply được; `applied.diff`
    chỉ còn 2 header.
  - Tool impact parse diff thô bằng parser strict (`patch.py:80-81`), nên báo lỗi. Docstring `tool_agent.py:6` và spec
    W10-3 §3.1 đều ghi tool nhận **diff đã apply**; batch W10 chạy trên `applied.diff`, ra 16/16 report, 0 lỗi.
  - Lỗi này làm django bị ghi `invalid 1` trong bảng M1, dù agent không truyền tham số nào.
- **`static ✗` ở django**: mypy ra `UNAVAILABLE` (Python 3.6, `TESTBED_PYTHON_UNSUPPORTED`), Ruff và syntax PASS.
  Engine không tính `UNAVAILABLE` là fail (`verification.py:175`), nhưng `trace_report.py:38` in ✗.

## Vòng thử lại

- Phản hồi cho NO_OP chỉ có câu "Previous attempt ended with FAIL NO_OP.": `feedback.py:60` chỉ đọc `error_detail`,
  còn ở chế độ normalized lý do lỗi nằm trong `stages.parse_patch.error`.
- Phản hồi cho TEST_FAILED chỉ có tên test, không có dòng assertion dù record có.
- Prompt lần 2 và lần 3 chỉ khác nhau ở `source_run_id`. Với greedy, output giống hệt nhau từng byte: astropy lần
  2 = lần 3; django lần 1 = lần 2; matplotlib lần 2 = lần 3.
- Lần thử 1 ngày 04/11 giống hệt lần thử 1 ngày 03/11 ở cả 3 task. Lần 2 của django khác nhau giữa hai ngày chỉ vì
  mã run trong prompt khác (output phụ thuộc yếu tố ngẫu nhiên).

## Ngữ cảnh (đoạn gold có trong prompt không)

| task | đoạn code cần sửa | có trong prompt |
|---|---|---|
| astropy-13033 | `_check_required_columns` hạng 1 | có |
| seaborn-3069 | `_finalize_figure` hạng 1 | có |
| flask-5014 | `Blueprint.__init__` hạng 21 | không, bị bỏ vì vượt giới hạn token |
| matplotlib-13989 | `Axes.hist` hạng 7 | không, bị bỏ vì hàm quá dài |
| django-10914 | `global_settings.py` | không nằm trong top 100 |

`failing_test_proximity` bằng null ở cả 100 ứng viên, vì bundle W12 không có link test REPRODUCES. Đây là thiết kế
theo `docs/m1_retrieval_method.md`, nên xếp hạng dựa chủ yếu vào độ trùng từ với issue (trọng số 0.5).

## Prompt và Qwen3-4B

- Prompt agent (`repair_agent.md`): ổn. Agent chỉ chọn 1 trong 6 tool không có tham số, mỗi lượt khoảng 15 token.
- Prompt V11 được đưa vào đúng: chat template đúng, hash khớp, kết thúc `<|im_start|>assistant\n`. Cách sinh giống
  worker M2 (greedy, cùng tham số). Cảnh báo attention mask vô hại vì chỉ có một chuỗi, không padding.
- Nhưng V11 chưa hợp với model 4B:
  - Định dạng "chép toàn bộ đoạn cũ rồi viết lại toàn bộ đoạn mới" khiến model chép y nguyên và bỏ mất chỗ sửa.
  - Đoạn lớn làm output bị cắt ở 1536 token (seaborn 03/11 viết lại class `Nominal` 158 dòng).
  - Mỗi item ngữ cảnh có khoảng 16 dòng metadata; khoảng 1/3 item không liên quan.
  - Issue còn giữ comment HTML của template GitHub.
  - Prompt không có dòng assertion của test fail.
- Model card Qwen khuyên sampling (Temperature 0.7, TopP 0.8, TopK 20); dự án chọn greedy để tái lập được.
- Tốc độ khoảng 1,6 token/s vì 45% model bị offload sang CPU; bước sinh patch chiếm 52–65% thời gian mỗi task.

## Lỗi code (M3) — đã sửa 04/11, chưa commit

Test: `tests/unit/test_x2b_diagnosis_fixes.py`. Cả 4 test fail trước khi sửa và pass sau khi sửa; thêm một test giữ
trường hợp gọi impact sai lúc vẫn là "không theo".
1. `tool_agent.py` (`apply_patch`): tool impact nhận `run_dir/applied.diff` của engine, chỉ dùng diff thô khi không có file đó.
2. `feedback.py` (`build_feedback`): đọc `error_detail`, nếu không có thì đọc `stages.parse_patch.error`. Phản hồi NO_OP
   giờ là "Every hunk is a no-op or leaves its file unchanged".
3. `trace_report.py` (`_static`): `UNAVAILABLE` không tính là fail, hiển thị `✓ (mypy n/a)`.
4. `tool_agent.py` (`optional_tools`, `ModelTurns`): lần gọi `analyze_patch_impact` khi host cho phép (patch đã apply,
   test fail, chưa gọi, còn lượt) được tính là theo NEXT. Gọi sai lúc vẫn là "không theo".

**Quyết định kèm theo:** sửa 1 và 2 đổi nội dung phản hồi mà generator nhận ở lần thử lại. Lần sửa 1 bỏ được lỗi
INVALID_ARGUMENT, nên dòng impact có thể vào phản hồi. Lần sửa 2 đưa lý do lỗi parse vào phản hồi. Run X2b 04/11
(`20261104T050429Z`) và 03/11 chạy trên code **trước** khi sửa; bảng M1 phải ghi rõ commit của từng run.

## Thay đổi protocol cần bàn với nhóm và M2 (trước khi freeze held-out, áp dụng cho mọi arm)

- Phản hồi: thêm dòng assertion (có giới hạn độ dài), giải thích NO_OP, bỏ `source_run_id`/`task_id` khỏi phần chữ của
  prompt.
- Ngữ cảnh (M1): lấy đoạn cửa sổ của hàm lớn thay vì bỏ cả hàm, thêm link test REPRODUCES, xử lý module settings.
- Định dạng và cách sinh V11 (M2): định dạng diff dễ hơn cho model, hoặc luật cứu hunk chỉ có dòng ngữ cảnh; sampling
  có seed cố định cho lần thử lại.
- Tốc độ: quantize 8-bit/4-bit để model nằm gọn trên GPU 6 GB (model profile riêng vì đổi kết quả tính toán).

Cập nhật 04/11: các đề xuất này đã được đánh giá lại theo mục tiêu hoàn thành bảng A0–A3, xem
`docs/status/m3_a0_a3_plan_2026-11-04.md`. Trước freeze chỉ giữ đề xuất tăng timeout. Feedback chỉ agent dùng; runner
A0–A3 không có lần thử lại.

## Run 3 sau 4 bản sửa (04/11, `20261104T083227Z`)

Run chẩn đoán trên clone `~/vgar-x2b` (`eded53c` cộng file chưa commit, gồm 4 bản sửa ở trên). X2b chính thức vẫn là run
03/11. Kết quả 0/5 resolved; INFRA 3, MODEL 2; agent theo NEXT 21/22; invalid 1/22 (lần gọi `analyze_patch_impact` bị
host từ chối).

| Task | Nhãn | Nguyên nhân |
|---|---|---|
| astropy-13033 | INFRA (`INTERNAL_ERROR`) | Ở baseline, `docker rm -f` lúc dọn container bị kill sau 29,4 s |
| django-10914 | INFRA (`INTERNAL_ERROR`) | Ở baseline, `docker rm -f` bị kill sau 16,6 s |
| matplotlib-13989 | INFRA (`TOOL_TIMEOUT`) | Lần 1 ra NO_OP như hai run trước. Khi mở lại, mypy của baseline bị dừng ở 60 s, nên ra `BASELINE_NOT_QUALIFIED` |
| seaborn-3069 | MODEL (`OUTPUT_TRUNCATED`) | Lần 1 `GENERATION_TIMEOUT` ở 900 s. Lần 2 và 3 bị cắt ở 1536 token và giống nhau từng byte. Feedback chỉ ghi "Previous attempt ended with ERROR VERIFICATION_INCOMPLETE." |
| flask-5014 | MODEL (`CONTEXT_NOT_FOUND`) | Model sửa `register_blueprint`, trong khi `Blueprint.__init__` không có trong prompt. Khối code cũ model viết thiếu dòng trống sau "on the blueprint." (dòng 279 của prompt), nên cả 3 lần đều `CONTEXT_NOT_FOUND` |

### Docker bị treo khi chạy agent

Bước dọn container có tổng cộng 30 s (`docker_executor.py:430`).

| Run | `docker info` p50 / lâu nhất | `rm -f` p50 / lâu nhất | Lệnh quá giờ |
|---|---|---|---|
| X2b `20261103T151652Z` | 0,32 / 21,2 s | 0,41 / 26,4 s | mypy 60 s (matplotlib, baseline khi mở lại); tests 47,6 s (django lần 3) |
| X2b `20261104T050429Z` | 0,34 / 59,4 s | 0,45 / 23,0 s | Ở baseline của seaborn: mypy 61,8 s, rồi `container inspect` lúc dọn 4,3 s; một lệnh tests 57,0 s |
| X2b `20261104T083227Z` | 0,36 / 33,6 s | 0,49 / 29,4 s | `rm -f` 29,4 s (astropy); `rm -f` 16,6 s (django); mypy 60 s (matplotlib) |
| Batch W10, nấc 1 và nấc 2 | 0,57 / 3,4 s | 0,47 / 3,0 s | Không có lệnh nào trong 7.825 lệnh |

- **Nguyên nhân khả dĩ:** khi chạy agent, model nằm thường trực trên RAM (khoảng 3,6 GB) cùng Docker Desktop, trong một
  VM 7,4 GiB. Batch W10 mở worker cho từng request rồi thoát, nên không bị. Chi tiết ở §2 của
  `m3_a0_a3_plan_2026-11-04.md`.
- Không phải do test chạy trên Windows: lần cuối xong lúc 08:12 UTC, còn run bắt đầu lúc 08:32.
- **Container bị bỏ lại:** `7822427f65f3` (`vgar-m2w93-7506d66a…`, image seaborn) của run 05:04. Cleanup hỏng ở
  `container inspect` nên `rm` chưa bao giờ được gửi. Lúc 10:12 UTC container vẫn đang chạy.

### Lần thử 1 giống hệt nhau giữa các run (greedy)

Bảng dưới ghi 12 ký tự đầu của sha256. Run nào không có mặt là run mà task đó hỏng hạ tầng trước stage prompt.

| Task | Prompt | Output | Có ở các run |
|---|---|---|---|
| astropy-13033 | `dfb016e3a2bb` | `29e0d8e6717b` | 03/11, 04/11 05:04 |
| django-10914 | `e03b9aa5e0a9` | `6528e9ddbb8b` | 03/11, 04/11 05:04 |
| matplotlib-13989 | `f626f0e7d949` | `e0ee94a0a755` | Cả 3 run |
| seaborn-3069 | `c8365e8c282c` | `ce4414e66a8b` (03/11); run 08:32 hết giờ trước khi có output | 03/11, 04/11 08:32 |
| flask-5014 | `4c43addd8bc4` | `2dadd006cb34` | 03/11, 04/11 08:32 |

### 4 bản sửa trên run thật

| Bản sửa | Kết quả |
|---|---|
| 2. Feedback đọc lỗi parse | Đã thấy ở flask: feedback có "src/flask/blueprints.py: old block not found after line 0", và 3 lần cho 3 diff khác nhau (vẫn sai). NO_OP của matplotlib chưa tới được lần thử 2 |
| 4. Gọi impact khi không được phép tính là "không theo" | Đã thấy ở seaborn: gọi `analyze_patch_impact` khi patch chưa apply → `not followed`, `HOST_REFUSED` |
| 1, 3, và trường hợp được phép của 4 | Chưa thấy: không task nào tới được bước apply PASS rồi test FAIL (django hỏng ở baseline). Hiện mới có unit test |

### Việc tiếp theo cho agent (không ảnh hưởng bảng A0–A3)

- **Môi trường:** `.wslconfig` với `memory=10GB`, `wsl --shutdown`, `docker rm -f 7822427f65f3`.
- **Run chẩn đoán kế tiếp:** chạy đủ 5 task (spec §3: không chạy lại có chọn lọc), ghi `vmstat -t 10` vào
  `$OUT/vmstat.log`.
- **Sau freeze:**
  - cleanup chịu được Docker chậm (cần M2 review);
  - feedback nói rõ output bị cắt hay hết giờ, đưa dòng code thật khi `CONTEXT_NOT_FOUND`, thêm dòng assertion;
  - bỏ `source_run_id` khỏi phần chữ của prompt.
