# S15: smoke `vgar solve --agent` trên một task SWE-bench (M3-X2a)

Lập 02/11/2026. Người dùng tự chạy, vì cần Docker image của task. Không cần GPU: chế độ `fake` dùng agent
kịch bản (`ScriptedRepairAgent`) và lấy gold patch làm patch kịch bản.

## Mục đích

Chứng minh `solve --agent` mở được run trên task SWE-bench đã qua admission, đi đủ vòng tool và đóng run
bằng `repair_verify_patch` (D20). Đây là điều kiện trước lần chạy RQ5 thật (M3-X2b, W12 ngày 4, E7).
Smoke **không** phải record thí nghiệm, không đưa vào bảng nào. Output nằm riêng ở `results/solve`.

## Code liên quan (02/11)

- `vgar solve --agent --experiment CONFIG --task-id ID [--variant A2] [--data-root DIR]`: host lập kế hoạch và
  admission giống runner (`plan_task` → `admit_task`), ghi task ra `results/solve/tasks/<ID>.json`, rồi mở mọi
  run với `experiment` (policy của variant) và `admission` (`src/vgar/agents/admitted.py`).
- `repair_get_task_context(..., admission=...)` chuyển snapshot vào `start_session`; engine kiểm lại snapshot.
- `--mode fake` bắt buộc có `--scripted-patch FILE`. `--mode real` dùng generator V11 như A2.

## Các bước (trong WSL, cùng cách chạy W10)

1. Chuẩn bị data root (ví dụ `~/w10`, giống W10): checkout, profile và bundle của **một** task trong
   `configs/m3/w10_dev_stage2.json`. Image đã bị xóa từ 29/10, nên phải pull và qualify lại profile theo
   `docs/m3_w9_runbook.md` Phần C, bước 3 (cách 2). Nếu profile hash đổi thì config phải đổi theo (D10).
2. Preflight để chắc task đó `FITS`:
   ```bash
   cd ~/vgar && .venv/bin/python scripts/run_repair_experiment.py preflight \
     --config configs/m3/w10_dev_stage2.json --data-root ~/w10 --output-root /tmp/s15-preflight
   ```
3. Chạy smoke (thay `T` bằng task đã chọn; gold patch lấy ở `data/gold/patches/$T.patch`):
   ```bash
   T=psf__requests-1766
   cd ~/vgar && .venv/bin/python -m vgar.cli solve --agent --mode fake \
     --experiment configs/m3/w10_dev_stage2.json --task-id $T --variant A2 --data-root ~/w10 \
     --scripted-patch data/gold/patches/$T.patch
   ```
4. Gửi lại 3 dòng cuối (`[status]`, `[run]`, `[trace]`) và kết quả của:
   ```bash
   python -c "import json,sys;r=json.load(open(sys.argv[1]));print(r['status'],r.get('reason'),[c['tool'] for c in r['mcp_calls']])" <run_dir>/run_record.json
   ```

## Tiêu chí PASS (bảng S15 trong remediation plan)

- Run kết thúc bằng `repair_verify_patch`: tool cuối trong `mcp_calls` là `verify_patch`.
- Có trace (`[trace]`) và `run_record.json`.
- Repo nguồn không đổi (`source_unchanged` trong kết quả).
- Kỳ vọng thêm: verdict `PASS`, vì gold patch phải làm test FAIL_TO_PASS chuyển sang PASS. Nếu ra `FAIL` hoặc
  `ERROR`, đọc `reason` và `error_detail.stage` trong `run_record.json` trước khi kết luận là lỗi của agent.

## Lỗi có thể gặp

| Thấy | Nghĩa |
|---|---|
| `cannot run: TASK_INPUT_MISSING` | Thiếu profile, checkout, input hoặc bundle dưới data root |
| `cannot run: TASK_EXCLUDED` | Profile không `COLLECTED` |
| `Source differs from qualified profile Python inventory` | Checkout không khớp profile |
| `Independent handoff bundle hashes required/mismatched` | Bundle khác hash ghi trong config |
| Lỗi Docker ở `docker_environment` | Docker daemon chưa chạy hoặc `docker_host` sai |
| `PATCH_PARSE_ERROR` | Gold patch chạm file ngoài `allowed_source_paths` hoặc sai định dạng |

## Kết quả lần chạy 02/11/2026 (`psf__requests-1766`, variant A2, WSL, code chưa commit qua `PYTHONPATH`)

- Preflight: A0 `FITS` (3494/6000), A1 và A2 `FITS` (4223/6000).
- Smoke: **đạt cả ba tiêu chí S15.** `mcp_calls` = get_task_context → apply_patch → run_relevant_tests →
  verify_patch; có trace và run record; `source_hash_before == source_hash_after`. Admission và envelope C4
  chạy đúng trên task SWE-bench trong Docker, nên rủi ro D20 đã được gỡ.
- Verdict lại là `FAIL TYPECHECK_FAILED`, `recommendation REVISE`, dù test tái hiện đã PASS. Đây là **từ chối
  nhầm của verifier A2**:
  - Gold patch chỉ sửa `requests/auth.py`, nhưng mypy báo 10 lỗi "mới" ở các file không bị sửa
    (`urllib3/connectionpool.py`, `ntlmpool.py`, `poolmanager.py`, `compat.py`, `pyopenssl.py`). Đồng thời có
    đúng 10 lỗi "đã hết", trùng hoàn toàn với 10 lỗi "mới".
  - Nguyên nhân: `build_line_map` (`src/vgar/repair/static_diagnostics.py`) chỉ ánh xạ những dòng xuất hiện
    đúng một lần trong file. Các dòng bị báo lỗi đều lặp lại trong file của chúng (`extra_params = {}`,
    `err = e`, `res.fp = None`), nên không khớp được với baseline. File trên 10.000 dòng cũng không được ánh
    xạ dòng nào.
- **Đã sửa (02/11, chờ review):** file giống hệt baseline thì ánh xạ mọi dòng vào chính nó, ở mọi kích thước.
  File đã bị sửa vẫn theo luật cũ (dòng lặp vẫn coi là mơ hồ). Test:
  `tests/m2/w910/test_static_diagnostics.py::test_line_map_maps_every_line_of_an_unchanged_file_even_repeated_or_large`
  và `::test_unchanged_file_with_repeated_lines_introduces_no_error`.
- Chạy lại offline trên run record của smoke: mypy `PASS` (0 lỗi mới, 228 lỗi cũ giữ nguyên), ruff `PASS`.
- Chạy lại trên 75 record W10: tổng số lỗi "mới" giảm từ 2.684 xuống 22. Đã kiểm: cả 22 lỗi còn lại đều nằm
  trong file mà patch có sửa. Verdict W10 không đổi, vì cả 26 lần đo có lỗi mới đều đã `TEST_FAILED` trước đó.
- Còn lại: dòng lặp trong chính file bị sửa vẫn có thể gây từ chối nhầm. Đây là lựa chọn bảo thủ có chủ đích
  của M2, nên giữ nguyên.
- **Chạy lại sau bản sửa (02/11, 09:51 UTC, run `20261102T095142203255Z-62264b9b8700`):** `[status] COMPLETED after
  1 attempt(s)`, verdict `PASS`, `recommendation ACCEPT`, `raw_pytest_status PASS`, repo nguồn không đổi.
  S15 đạt đầy đủ, kể cả kỳ vọng phụ.
