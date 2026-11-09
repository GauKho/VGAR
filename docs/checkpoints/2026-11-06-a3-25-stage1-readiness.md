# A3 × 25 dev — chặng 1 readiness, 06/11/2026

**Chặng 1 hoàn tất inventory; WAITING_ENVIRONMENT_AND_PREPARATION, chưa LAUNCH_READY. Dừng trước chặng 2.**

Plan: [A3 25 dev local campaign](../superpowers/plans/2026-11-06-a3-25-dev-local-campaign.md). Repo `D:\Project\CAPSTONES\VGAR`, nhánh `m2/w12-a3-verifier-d15-20261105`, HEAD `3f77fcf6` cùng dirty work T2/T4/T5/T6/T7 và báo cáo người dùng. Chỉ làm readiness, không triển khai T1/T3/T10.

## Kết quả có bằng chứng

| Hạng mục | Kết quả |
|---|---|
| Population | 25 unique dev IDs, 11+14, đúng prefix25 của manifest50; tự tính lại manifest hash khớp pin |
| Repro/overlay | 23/25 có input và đủ overlay, đã hash; requests-1724/pylint-4970 thiếu repro theo EXCLUDED.md |
| Checkout/profile/bundle W10 ready tại roots đã kiểm | 0/25; không nhầm pins trong JSON với assets thực |
| Model Qwen3 | Cache D: có đúng thư mục revision `cdbee75f17c01a7cc42f958dc650907174af0554`, đủ3 shards/8.044.982.000 bytes; toàn bộ model files đã stream SHA-256. Chưa kiểm Linux/CUDA/inference |
| Tokenizer | Hai manifest M1/M2, 4/4 files mỗi manifest đúng size/hash |
| Parquet | Có file local 2.096.679 bytes, SHA-256 `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`, đúng pin. Chỉ hash bytes, không đọc oracle rows |
| Source cache | 3 archive candidates xarray-3993/pylint-4604/sphinx-10673 đúng base-name/root, không traversal; chưa là Git checkout được admission. 9 probes trong3 Git caches cũ không có commit W10 tương ứng |
| WSL/Docker | Cả VGAR-Harness-W9 và docker-desktop Stopped tại phép đo. Docker client28.5.1, context desktop-linux có mặt; image count UNKNOWN, không phải0 |
| Host resources | 18:49:54 giờ Việt Nam: RAM trống9.640.300.544 bytes≈8,98GiB; C14.143.574.016≈13,17GiB; D66.264.588.288≈61,71GiB. Đạt ngưỡng ban đầu, chưa chứng minh đủ image unpack hoặc full batch |

**Đính chính mức độ đầy đủ so với câu trả lời trước:** máy chưa có bộ checkout/profile/bundle W10 runnable, nhưng **đã có model/tokenizer/Parquet trong cache ngoài repo**, không cần mặc định tải lại tất cả. Không quét toàn máy để khẳng định mọi nơi không có data.

WSL đã được đọc trực tiếp ở lượt trao đổi trước: `/home/vgar/w9` có harness và venv, chưa thấy W10 tại locations đã kiểm. Lượt readiness này distro đã dừng, không bật lại; ghi quan sát trước riêng trong `environment.json`. Chưa kiểm Linux MemAvailable, CUDA/venv hay nội dung Docker image store. Không mount/hash VHDX.

## Artifact và kiểm chứng

Root: `results/m2/w1112/a3-25/20261106T114534Z-readiness/`.

- `readiness.json`, `assets.json` và `assets.csv`: đúng25 rows, availability riêng, pins và missing reasons.
- `model.json`, `tokenizers.json`, `dataset.json`, `archive_checks.json`: đường dẫn local, size/hash/proof và giới hạn.
- `host_fresh.json`, `environment.json`, `resource_gates.json`: số đo, timestamp và phần chưa biết.
- `missing_inputs.md`: hướng dẫn bàn giao/chuẩn bị tiếp theo.
- `commands.json`, các helper `.py`, collection/finalize/verification logs: tái hiện audit; `dirty-before.patch`, `staged-before.patch`, preservation before/after và `input_hashes.json` bảo vệ dữ liệu hiện có.
- `verification.json`: **18/18 inventory assertions PASS**, kiểm75 input/assets và32 file đang có (dirty/untracked, DB, báo cáo Linux, Git index). Đây không phải18 pytest case hoặc kết quả Docker/model.
- `artifact_hashes.json`: checksum bộ bằng chứng. Các tài liệu tiến độ/checkpoint được cập nhật sau phép đo, giữ lịch sử và kiểm preservation bổ sung riêng.

Review độc lập chỉ đọc: không Critical/Important. Ba Minor clarity được ghi hoãn trong `supplemental_review.json`: docker_operations=0 chỉ daemon/container (đã giải thích CLI queries); assets.json giữ archive status bảo thủ còn structural proof ở archive_checks.json; quan sát WSL lượt trước không có raw command bundle tại đây, chỉ được dẫn như lịch sử hội thoại. Không dùng các điểm này để suy data/launch READY.

TEMP: `C:\Users\pc\AppData\Local\Temp\vg-a3-readiness-c546e264`. Lệnh chính (đã chạy, logs trong artifact):

```powershell
$vgarPython = 'D:\Project\CAPSTONES\environments\vgar-week78-cuda\Scripts\python.exe'
$auditTmp = 'C:\Users\pc\AppData\Local\Temp\vg-a3-readiness-c546e264'
& $vgarPython -B "$auditTmp\collect_readiness.py"
& $vgarPython -B "$auditTmp\finalize_inventory.py"
& $vgarPython -B "$auditTmp\verify_inventory.py"
```

Các helpers là one-off artifact audit, không phải CLI production. Collector cần quyền chỉ đọc hệ thống ngoài sandbox cho CIM/WSL-state; archive cần quyền ghi output results mới. Không chạy lại archive vào thư mục đã tồn tại. Verification trước khi bổ sung tài liệu sẽ phát hiện thay đổi PROGRESS/status sau đó; dùng closing preservation để phân biệt tài liệu được phép với code bị drift.

## Còn chờ và điểm tiếp tục

1. Người dùng xác nhận **chặng 2** mới bật môi trường, nhận/fetch sources, pull digests thiếu hoặc tạo local config.
2. Tận dụng model/tokenizer/Parquet cache D:. Chuẩn bị25 source checkout có proof Git; kiểm3 archive candidates để tận dụng phù hợp, không suy chỉ cần22 checkout.
3. Khi Docker hoạt động mới inventory images/digests và ước lượng dung lượng download/unpack; hiện tổng dung lượng thiếu giữ unknown.
4. Relocate model/SDK/interpreter paths của máy M3 vào config riêng; qualification local, graph/bundle đúng freeze và smoke riêng.
5. Full batch vẫn sau T1; T3 phải có kết luận/giới hạn được nhóm chấp nhận; raw10 gold và D15 chờ M3. Giữ900/1800, không mở ĐX hoặc task khác.

Không source/config/test production nào bị sửa, không download, test, model generation hoặc container execution. Không commit/push. **Dừng ở đây.**
