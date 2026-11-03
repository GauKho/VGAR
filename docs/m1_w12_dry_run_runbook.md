# Runbook: dry-run held-out chain (M1-W12-2)

> Spec: `docs/superpowers/specs/2026-11-03-m1-w12-design.md` §4. Script: `scripts/dry_run_heldout_chain.py`.
> **Người dùng tự chạy** trên máy GPU (WSL). Script không bao giờ chạy held-out.

## Mục đích

Chạy toàn chuỗi trên 2 dev task `astropy__astropy-13033`, `django__django-10914` với model thật:

1. `export_bundles`: export lại bundle bằng ranking đã đóng băng → `~/w9/w12/bundles/repair/<run-id>/`
2. `derive_config`: sinh `w12_dry_run.json` với hash của bundle mới (template `configs/m3/w10_dev_stage1.json`)
3. `preflight`, 4. `run`: `run_repair_experiment.py`
5. `grade`: `grade_repair_candidates.py --execute` (Docker)
6. `aggregate`

Cổng "harness ổn định" (H7) đạt khi **2 lần chạy liên tiếp, ở 2 phiên máy khác nhau**, đều có `gate = PASS`.

## Tiền điều kiện

- `configs/m2/variants/A3.json` đã merge (M2-W12-1). Chưa có thì chạy với `--arms A0,A1,A2`; khi đó
  `gate = INCOMPLETE_A3_MISSING` và cổng **không** tính là đạt.
- Mutant pool đã chạy xong (H9/H10), vì dry-run dùng chung máy.
- Docker image của 2 task có sẵn; checkout ở `~/w9/repositories/<task>` sạch, đúng base commit.
- Parquet SWE-bench đã pin (cùng file dùng cho aggregate W10).
- Variant dùng là `configs/m2/variants/A*.json` (bản hiện hành), không phải `configs/m2/variants/w10/`.

## Lệnh

Lần 1 (đầu cửa sổ GPU):

```bash
wsl -d Ubuntu -- bash -lc "cd ~/vgar && .venv/bin/python scripts/dry_run_heldout_chain.py \
  --data-root ~/w9 --parquet <parquet đã pin> --out results/m1/w12/dry_run/$(date -u +%Y%m%dT%H%M%SZ)"
```

Lần 2: cùng lệnh, ở một phiên máy khác (cuối cửa sổ GPU), thư mục `--out` mới.

Ước tính: 4 arm × 2 task, khoảng 13 phút cho mỗi cặp task–arm theo số W9, tức khoảng 1,7 giờ mỗi lần,
cộng thời gian export và chấm.

## Đọc kết quả

Script in một dòng JSON và trả mã 0 chỉ khi `gate = PASS`. Chi tiết trong `<out>/`:

| File | Nội dung |
|---|---|
| `dry_run.json` | commit, task, arm, hash (ranking, manifest, config, variant, model), từng bước (lệnh, thời gian, exit code, log), `infra_errors`, `gate` |
| `logs/<bước>.log` | stdout/stderr của từng bước |
| `heldout_commands.md` | Lệnh để chép vào protocol (manifest held-out để trống). **Không chạy** trước tag `protocol-freeze` |
| `runs/`, `grades/`, `aggregate/` | Record runner, kết quả harness, bảng tổng hợp |

**Tính là ERROR hạ tầng:** bước exit khác 0; attempt không `TERMINAL`; record `ERROR` với lý do
`INTERNAL_ERROR`, `WORKTREE_ERROR`, `FINALIZATION_ERROR`, `RUNNER_INFRA_ERROR`, `ADMISSION_REJECTED`;
harness `ERROR`; chấm điểm `BLOCKED`/`ERROR`.
**Không tính:** kết cục của model (`PATCH_PARSE_ERROR`, `PATCH_APPLY_FAILED`, `UNRESOLVED`, verifier từ chối…).

Sau mỗi lần chạy: ghi đường dẫn `<out>` và `gate` vào `docs/status/m1.md`. Hai lần PASS → bàn giao H7 cho M3.
