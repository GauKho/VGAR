# TV2 · GA-1, GA-2: chạy thật tầng `G_arch` (09/11/2026)

> Plan: `docs/superpowers/plans/2026-11-09-tv2-ga-g-arch.md` (Task 6).
> Spec: `docs/superpowers/specs/2026-11-09-tv2-ga-g-arch-design.md` §8.

**Kết quả: ĐẠT.** `vgar-demo-shop` khớp đúng đáp án viết tay. Graph xarray qua validate, và phần `G_repo` giống hệt graph đã lưu trước khi có `G_arch`.

Lần chạy dùng resolver `static`, không bật tree-sitter-graph.

## Số đếm

| | `vgar-demo-shop` | `pydata__xarray-4629` (chỉ để kiểm tra) |
|---|---|---|
| Chế độ chia Component | `module` | `package` |
| Component | 7 | 7 |
| Port | 10 | 1.065 |
| `DEPENDS_ON` | 7 | 14 |
| `EXPOSES_PORT` | 10 | 1.065 |
| `CONSUMES_PORT` | 7 | 30 |
| `CONTAINS_COMPONENT` | 7 | 7 |
| File không phải test, không thuộc Component | 1 (`shop/__init__.py` rỗng) | 13 |
| DeploymentUnit, Service | 0 | 0 |
| Node / cạnh tổng | 137 / 217 | 40.351 / 72.508 |
| `build_time_ms` | 133 | 9.201 |

Theo spec §8 mục 8, số của xarray không được dùng để chỉnh quy tắc.

## `DEPENDS_ON` của demo-shop, khớp spec §8 mục 7

| Từ | Tới | `weight` |
|---|---|---|
| `cart` | `catalog` | 3 |
| `checkout` | `cart` | 2 |
| `checkout` | `discounts` | 2 |
| `checkout` | `shipping` | 2 |
| `checkout` | `tax` | 2 |
| `discounts` | `money` | 2 |
| `tax` | `money` | 2 |

## Tính chất "chỉ thêm vào"

So xarray với `.superpowers/sdd/2026-11-08-tv2-l2-2-may-call/run/xarray-static.json` (bỏ `graph_version`): sau khi bỏ `G_arch`, **39.279 node và 71.392 cạnh giống hệt**.

## Test

- `tests/test_arch_lift.py`: 43 passed, chạy với CLI tree-sitter-graph thật. Đáp án viết tay từ nội dung fixture.
- 13 file test tầng 1 của Layer 1–3 (spec §8 mục 6) cùng `test_arch_lift.py`: **426 passed, 1 skipped**. Test bị skip là test symlink có sẵn.
- `ruff check` trên `arch_lift.py` và `test_arch_lift.py`: sạch.
- **Toàn bộ test suite** (bỏ marker `hf`, `docker`): lần đầu 25 failed, 2.338 passed. 22 test fail do lỗi thật của GA (xem dưới). Sau khi sửa, chạy lại đúng các nhóm đã fail (`tests/m2/w1112`, `tests/m2/w78` và 3 test riêng): 725 passed, 1 skipped, còn 3 failed. Chưa chạy lại nguyên suite sau khi sửa (lần đầu mất 36 phút).

Ba test còn fail không thuộc phạm vi plan 2 tuần và đã có từ 08/11: `test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`, `m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`.

**Lỗi bộ test tầng 1 không bắt được:** spec ban đầu xếp Port vào `SOURCE_BACKED_NODE_TYPES`. `structural_check.py` đòi mọi loại trong nhóm đó có cạnh `CONTAINS` tới file, nên `structural_check` trả `ERROR` trên mọi graph có `G_arch`. Đã bỏ Port khỏi nhóm này, cập nhật spec §5.4 và §6, thêm `test_structural_check_accepts_graph_with_g_arch`. Chỉ toàn bộ suite mới phát hiện được, vì 13 file ở spec §8 mục 6 không gồm test của check này.

**Test cũ phải sửa (1):** `tests/test_may_call.py::test_legacy_projection_matches_graph_without_new_facts`. Test so với graph "không có fact mới" chỉ bằng cách tắt `MAY_CALL`, nên dư node `G_arch`. Đã thêm một dòng tắt pha lift trong lần build dùng để so sánh.

## Chạy trên các repo mẫu trong `tests/fixtures`

13 repo, resolver `static`, bật tree-sitter-graph: cả 13 build được, qua validate, `structural_check` đều `PASS`. Sửa một file rồi cập nhật incremental (không bật tree-sitter-graph) đều cho graph giống hệt build lại.

| Repo | Chế độ | Component | Port | `DEPENDS_ON` |
|---|---|---|---|---|
| `m2/clean_repo`, `m2/failing_repo` | `module` | 1 | 1 | 0 |
| `sample_repo` | `module` | 6 | 6 | 3 |
| `typed_repo` | `module` | 2 | 2 | 1 |
| `m1_w10_impact` | `module` | 2 | 4 | 1 |
| `vgar-callgraph-cases` | `package` | 2 | 72 | 1 |
| `vgar-callgraph-cases-flat` | `module` | 4 | 4 | 2 |

Các repo này không có đáp án viết tay cho `G_arch`, nên chỉ chứng minh chạy được và không làm hỏng check khác. Không repo nào có Route, ConfigEntry hay file deploy; các phần đó chỉ được kiểm trong `tests/fixtures/vgar-arch-cases`. `m2/w10_normalize` là các bản chụp từng file, không phải một repo, nên số Component của nó không có ý nghĩa.

## Repo mẫu `boundary_cases`: các ca khó nằm trên ranh giới Component

`tests/fixtures/vgar-arch-cases/boundary_cases` có 4 package. 20 lời gọi có `# expect:`, đối chiếu bằng chạy thật (`verify_expect.py`): 0 sai lệch. Trong đó 15 đích gọi đi qua ranh giới Component. Đáp án gồm 21 Port, 6 cặp phụ thuộc thật, 12 cặp `CONSUMES_PORT` thật.

| | `static` | `scip` |
|---|---|---|
| Component, Port | Đúng hết (4, 21) | Đúng hết (4, 21) |
| Cặp `DEPENDS_ON` thật tìm được | 5/6 | 5/6 |
| Cặp `DEPENDS_ON` thừa | 0 | 0 |
| Đích gọi qua ranh giới được đếm vào `call_count` | 10/15 | 12/15 |
| `CONSUMES_PORT` đúng | 6/12 | 8/12 |
| `CONSUMES_PORT` thừa | 1 | 1 |

| Ca | `static` | `scip` |
|---|---|---|
| Import thường, alias, `import x as y`, re-export | Đúng | Đúng |
| Lazy import trong hàm | Thiếu | Đúng |
| `self.flush()` kế thừa từ package khác | Chỉ là `MAY_CALL`, không đếm | Đúng |
| Duck typing, không có import (`api → plugins`) | Thiếu cả cặp | Thiếu cả cặp |
| Callback truyền qua tham số | Thiếu | Thiếu |
| Tham số có kiểu lớp cha | Nối vào `BaseStore.save`, thiếu 2 lớp con | Giống `static` |

`test_arch_lift.py` chỉ chốt số của `static`. Số của `scip` lấy từ một lần chạy tay.

## Giới hạn đã biết

- **GA-2 chưa đủ:** Connector và ExternalSystem chỉ được khai báo trong schema, chưa có luật sinh. [P] chỉ nêu tên (dòng 254, 258), nhóm cần định nghĩa.
- **Co-change:** báo `unavailable` cho tới khi có L4-1 của TV3.
- `CONFIGURES` và Port từ Route chỉ có khi bật tree-sitter-graph.
- Gọi constructor (`CALLS` tới Class) có tính vào `weight` nhưng không tạo `CONSUMES_PORT`.
- Handler nằm trong hàm khác (app factory của Flask) không thành Port, vì hàm lồng bị loại theo spec §5.4.
- Dockerfile trong thư mục test hoặc fixture vẫn thành DeploymentUnit.
- Luật Docker và compose mới được kiểm trên repo mẫu viết tay; demo-shop và xarray không có các file này.
- Chưa có nhãn tay nên chưa đánh giá được chất lượng ranh giới Component (G1, [plan] O7).
- **Lỗi có sẵn, chưa sửa:** repo có `__init__.py` ở thư mục gốc làm builder tạo Module có tên rỗng và validate lỗi. Lỗi này xảy ra trước pha lift và nằm ngoài GA; quy tắc bỏ qua package gốc của lift được kiểm trực tiếp.

## Tái tạo

```bash
R=.superpowers/sdd/2026-11-09-tv2-ga-g-arch/run
env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR \
  python scripts/build_graph.py D:/kltn/vgar-demo-shop/vgar-demo-shop $R/demo.json --repo-key demo/shop --revision base
env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR \
  python scripts/build_graph.py C:/Users/nlhnh/.claude/jobs/46c4db36/tmp/repos/pydata__xarray-4629 $R/xarray-static.json \
  --repo-key pydata/xarray --revision base
python $R/report.py

source .superpowers/sdd/2026-11-08-tv2-layer1-remaining-facts/env.sh
python -m pytest -q -p no:cacheprovider tests/test_arch_lift.py
```
