# TV2 · GT-1: chạy thật `G_task` (09/11/2026)

> Plan: `docs/superpowers/plans/2026-11-09-tv2-gt-1-g-task.md` (Task 5).
> Spec: `docs/superpowers/specs/2026-11-09-tv2-gt-1-g-task-design.md` §8.

**Kết quả: ĐẠT phần có luật sinh.** Requirement, UserStory, Constraint, Actor mới chỉ khai báo trong schema, nên GT-1 chưa đóng hẳn.

## Trích trên 50 issue của bộ dev

Chỉ dùng `problem_statement`, không truyền `failing_tests` hay label.

| Chỉ số | Kết quả |
|---|---|
| StackTraceFrame | 72, ở 5 issue |
| ErrorMessage sau khi gộp trùng | 11, ở 10 issue |
| BugReport | 10 issue |
| AcceptanceCriterion | 0 |

## Overlay cho `pydata__xarray-4629`

Graph `static`, không truyền `failing_tests`, chỉ để kiểm tra. **Luật không được chỉnh theo số này.**

- Qua validate. 32 anchor, 32 cạnh `MENTIONS`, 2 cạnh `TRACES_TO`.
- Issue này không có traceback, dòng lỗi hay tiêu chí, nên không có node `G_task` mới.

| `TRACES_TO` tới | Confidence | Số anchor |
|---|---|---|
| `xarray.core` | 0.7 | 2 |
| `xarray.util` | 0.45 | 1 |

Nhiều anchor bị coi là mơ hồ nên không tạo `TRACES_TO`. Chưa đo trace link P/R; việc đó thuộc TR-1 và G1.

## Test

- `tests/test_task_graph.py`: 52 passed, chạy với CLI tree-sitter-graph thật.
- Test tầng 1 Layer 1–3 (spec §8 mục 2): **489 passed, 1 skipped**. Test bị skip là test symlink có sẵn.
- **Toàn bộ test suite sau khi sửa** (bỏ marker `hf`, `docker`): 2.421 passed, 20 skipped, 1 xfailed, **3 failed**. Cả 3 đã có từ trước và không thuộc plan 2 tuần: `test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`, `m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`.
- `ruff check` trên các file mới: sạch.

**Test cũ phải sửa:**
- 6 test trong `tests/test_task_overlay.py` ghim số node, cạnh của overlay; nay chỉ đếm anchor `MENTIONS` và `Test → Issue`. Ý nghĩa giữ nguyên: selector không resolve thì không có `REPRODUCES` tới Issue.
- `test_schema_declares_g_arch` trong `tests/test_arch_lift.py`: bỏ ghim `SCHEMA_VERSION` v2 và cặp `DEPENDS_ON` duy nhất.

## Review độc lập

Một reviewer không tham gia viết code đã đọc toàn bộ thay đổi: 0 Critical, 3 Important, 5 Minor. Đã sửa 3 Important và 1 Minor nâng hạng, mỗi lỗi có test tái hiện:

- Issue có số dòng cực dài làm crash (cả ở `grounding.py`).
- Luật tiêu đề acceptance bắt nhầm gạch đầu dòng và câu văn.
- `test_node_ids` khớp nhầm test trùng tiền tố tên.
- Dấu `/` đứng một mình trong văn bản bị coi là route gốc.

## Giới hạn đã biết

- **GT-1 chưa đủ:** Requirement, UserStory, Constraint, Actor, `DEPENDS_ON` và `CONFLICTS_WITH` giữa Requirement chưa có luật sinh. Nguồn chỉ định nghĩa kiểu; nhóm cần chốt.
- BugReport chỉ dựa trên dấu hiệu cấu trúc, nên 10/50 issue có; những bug không kèm traceback hay dòng lỗi sẽ không có node này.
- AcceptanceCriterion có luật nhưng bộ dev chưa có dữ liệu.
- Chất lượng `TRACES_TO` phụ thuộc chất lượng anchor. Ví dụ trên xarray có một cạnh tới `xarray.util` chỉ từ 1 anchor.
- Label chưa được `sqlite_service` và MCP truyền vào; việc đó thuộc L6-2.
- Còn để lại: phần tử rỗng trong `failing_tests` vẫn nằm ở `properties.failing_tests` của Issue; tiêu đề trong blockquote không ra tiêu chí; test retrieval chưa kiểm được trường hợp lọc mất mọi `REPRODUCES`.

## Tái tạo

```bash
source .superpowers/sdd/2026-11-08-tv2-layer1-remaining-facts/env.sh
python -m pytest -q -p no:cacheprovider tests/test_task_graph.py

env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR PYTHONPATH=src \
  python .superpowers/sdd/2026-11-09-tv2-gt-1-g-task/real_run.py
```
