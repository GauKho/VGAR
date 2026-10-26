# Task inputs cho pilot W9 (D4 trong `docs/m3_w9_decisions.md`)

Mỗi task có `<task_id>.json` (source_roots, selectors, scope, protected paths, overlay) và file test tái hiện đi kèm.
Test được viết **chỉ từ problem statement trong `configs/m1/w9_pilot_manifest.json`**, không đọc gold patch, test_patch hay F2P/P2P.

| Task | Trạng thái | Ghi chú |
|---|---|---|
| `pydata__xarray-3305` | **Đã kiểm trong image** | 25/10, image `@sha256:0e234dad…`: commit cha = base `69c7e01e`, 0 file khác base; test FAIL đúng lý do (`attrs` rỗng sau `quantile(..., keep_attrs=True)`) |
| `matplotlib__matplotlib-14623` | **Đã kiểm trong image** | 25/10, image `@sha256:52cdd8ac…`: commit cha = base `d65c9ca2`, 0 file khác base; test FAIL đúng lý do (`yaxis_inverted()` = False trên trục log). `source_roots` rộng (`lib/matplotlib`): xem số token ở preflight |
| `pylint-dev__pylint-4551` | **Đã kiểm trong image** | 25/10, image `@sha256:f0f898ca…`: commit cha = base `99589b08`, 0 file khác base; test FAIL đúng lý do (`a : NoneType`, không có `str`). Viết theo API pyreverse ở base (`project_from_files` → `Linker` → `ClassDiagram.get_attrs`) |
| `astropy__astropy-13398`, `django__django-11138` | Không cần | Profile EXCLUDED, runner tự ghi `TASK_EXCLUDED` |

Trước khi dùng, mỗi test **phải FAIL trên base commit** trong image của task (runbook bước 5). Image SWE-bench có thêm một commit `SWE-bench` nằm trên base và không đổi file nào, nên kiểm bằng commit cha cùng `git diff`, không so trực tiếp `HEAD`. Test PASS trên base là test sai: sửa test, không sửa ngưỡng.
Chỉnh file trong thư mục này làm đổi `experiment_id`, vì nội dung task inputs nằm trong định danh experiment.
