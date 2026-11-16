# TV2 · GT-1 phần còn lại: chạy thật Requirement, Constraint, UserStory, Actor (17/11/2026)

> Spec: `docs/superpowers/specs/2026-11-17-tv2-gt-1-requirements-design.md` (luật do nhóm chốt 16/11).
> Phần GT-1 trước đó: `tv2_gt_1_g_task_run_2026-11-09.md`.

**Kết quả: ĐẠT.** Mọi loại node và cạnh của `G_task` trong [P] dòng 299–323 đều đã có luật sinh; GT-1 đóng.

## Thay đổi

| File | Thay đổi |
|---|---|
| `src/vgar/graph/task_graph.py` | Trích Requirement, Constraint, UserStory (kèm actor) và liên kết giữa các Requirement từ văn bản issue |
| `src/vgar/graph/task_overlay.py` | Sinh node, `MENTIONS`, `DEPENDS_ON`/`CONFLICTS_WITH` giữa Requirement; profile overlay lên `task-overlay-v12-requirements` |
| `src/vgar/graph/trace_links.py` | `TRACES_TO` Requirement → Component, dùng lại luật Issue → Component với anchor có chữ nằm trong câu |
| `src/vgar/contracts/schema.py` | `MENTIONS` thêm 4 đích; thuộc tính bắt buộc của 4 node; `anchor_count` cho `TRACES_TO` Requirement → Component; producer `overlay` |
| `tests/test_task_graph.py` | 13 test mới (tính cả tham số) |
| `tests/test_schema_contract.py`, `tests/test_trace_links.py` | Không còn loại nào "chưa có producer"; đổi tên profile |
| `scripts/gt1_requirements_run.py` | Script chạy trên bộ dev |

## Thay đổi so với luật chốt 16/11

1. Bỏ `instead of` khỏi luật `CONFLICTS_WITH`: trong bug report cụm này nằm trong một câu ("should return X instead of Y"), không chỉ tới requirement thứ hai.
2. Câu tham chiếu ngược (`This requires …`) đứng ngay sau một Requirement cũng là Requirement (`source = follow_up`), vì không có động từ khuyết thiếu; nếu không, `DEPENDS_ON` không thể sinh.

## Lỗi phát hiện nhờ chạy thật (đã sửa, có test)

Lần chạy đầu, câu gợi ý của mẫu issue (`<!-- What did you expect to happen.`) và chính dòng tiêu đề `Expected:` bị lấy làm Requirement. Sửa: bỏ comment HTML; coi `Expected:` đứng một mình là tiêu đề.

## Trích trên 50 issue của bộ dev

Chỉ dùng `problem_statement`.

| Loại | Tổng | Số issue có |
|---|---|---|
| Requirement | 61 (30 từ mục Expected, 31 từ động từ khuyết thiếu) | 29/50 |
| Constraint | 20 (15 phiên bản, 5 câu cấm) | 15/50 |
| UserStory, Actor | 0 | 0 |
| `DEPENDS_ON`, `CONFLICTS_WITH` giữa Requirement | 0 | 0 |

Ví dụ Requirement: "I expect the HTML table output to respect the formatting given by the `formats` argument." (astropy-13453); "Engine.render_to_string() should honor the autoescape attribute" (django-11119).
Ví dụ Constraint: "`unused-import` should not be emitted." (pylint-4604); "When using proxies in python 3.8.12, I get an error 407." (requests-6028).

## `TRACES_TO` Requirement → Component

Overlay thật trên 12 task có base commit trùng cây repo đã giải nén (một task mỗi repo):

- 11 Requirement, 3 Requirement có trace, 4 cạnh `TRACES_TO`.
- 3/4 cạnh trỏ tới Component chứa file gold: astropy-13033 → `astropy/timeseries` (gold `astropy/timeseries/core.py`); seaborn-3069 → `seaborn/_core` hai lần (gold `seaborn/_core/plot.py`). Cạnh còn lại (astropy-13033 → `astropy/io/fits`) sai.
- Cỡ mẫu quá nhỏ để kết luận về precision.

## Test

- `tests/test_task_graph.py`, `test_trace_links.py`, `test_schema_contract.py`, `test_task_overlay.py`: 284 passed, 3 skipped.
- Toàn bộ suite (bỏ marker `hf`, `docker`, gồm cả thay đổi GA-2 cùng ngày): 3.404 passed, 27 skipped, 1 xfailed, 3 failed. Cả 3 không liên quan: `test_official_harness` đã fail từ trước; `test_tv2_removed_stack::test_verification_tools_survive` và `m3/test_manifest::test_pilot_experiment_id_is_unchanged_by_w10_fields` băm byte của file, chỉ fail trong worktree checkout CRLF.
- `ruff check` trên các file đã sửa: sạch.

## Nhận xét

- Đúng như dự kiến khi chốt luật: bug report có Requirement và Constraint ở khoảng một nửa số issue; UserStory, Actor và hai cạnh giữa Requirement ra 0. Luật và test trên mẫu đã có, nên GT-1 đóng với giới hạn ghi rõ.
- Constraint loại `version` phần lớn là thông tin môi trường ("Python 3.9.12") chứ không phải ràng buộc của bản sửa.
- Các node mới không đi vào retrieval (retrieval chỉ đọc Issue và `REPRODUCES` của overlay), nên số R1 không đổi.

## Giới hạn

- Luật theo từ khóa, không NLP: câu có `should` mô tả ý kiến ("this should be related to …") cũng thành Requirement; câu hỏi "Should X?" cũng vậy.
- Chưa có nhãn tay nên chưa đo precision/recall của các node mới.

## Tái tạo

```
# WSL, tại ~/rt1
PYTHONPATH=<repo>/src ~/.vgar-wsl/bin/python <repo>/scripts/gt1_requirements_run.py ~/w9/dataset/test-00000-of-00001.parquet ~/rt1/data/manifests/w10-dev-50-gold.json
```
Kết quả gốc: `~/rt1/gt1_run.json`, `~/rt1/gt1_traces.json` (WSL).
