# TV2 · IM-1: chạy thật impact theo `G_arch` và check "mất port" (09/11/2026)

> Plan: `docs/superpowers/plans/2026-11-09-tv2-im-1-impact.md` (Task 6).
> Spec: `docs/superpowers/specs/2026-11-09-tv2-im-1-impact-design.md` (§8, §10).

**Kết quả: ĐẠT.** `analyze_patch_impact` báo thêm Port, Component bị ảnh hưởng và Port, public API bị mất.

## Chạy thật trên `pydata__xarray-4629`

Graph `static`, `source_roots=("xarray",)`: 40.406 node, 70.303 cạnh, 7 Component, 1.065 Port. Patch nhắm vào hàm công khai `merge` ở `xarray/core/merge.py`. Số này chỉ để kiểm tra, **không dùng để chỉnh luật**.

| Patch | Node bị sửa | Item theo loại | Component | `port_check` | `ports_lost` |
|---|---|---|---|---|---|
| Sửa thân hàm | `core.merge.merge` | 1 Port, 5 Component, 5 Function, 11 Test, 23 Module | 5/7 | `COMPLETE`, không mất | 0 |
| Đổi tên hàm | `core.merge.merge` | 1 Port, 5 Component, 5 Function, 11 Test, 23 Module | 5/7 | `COMPLETE`, mất `core.merge.merge` (`API_SYMBOL_REMOVED`) | 1 |

Port `core.merge.merge` có 0 consumer vì `CONSUMES_PORT` chỉ có khi `CALLS` đã resolve qua component khác; Component liên quan vẫn được báo qua `DEPENDS_ON`.

**Thời gian trên xarray:**

| Bước | Thời gian |
|---|---|
| `_map_patch` (có sẵn, gồm 2 lần `_snapshot` khoảng 3,6 s mỗi lần) | 9,1 s |
| `compute_impact` | 1,5 s |
| `check_lost_ports` (mới) | 0,055 s |

Cả lần gọi mất 11–15 s, phần lớn là của `_map_patch` có sẵn. Thực nghiệm ở spec §10 đã chỉ ra phép `data[:offset]` lặp lại cho từng node; IM-1 không sửa phần này.

## Test

- `tests/test_impact_arch.py`, `tests/test_port_check.py`, `tests/test_impact.py`, `tests/test_w10_impact_mcp.py`, có bật CLI tree-sitter-graph: **175 passed, 1 skipped**. Test bị skip là test symlink có sẵn.
- **Toàn bộ test suite sau khi sửa** (bỏ marker `hf`, `docker`): 2.489 passed, 20 skipped, 1 xfailed, **3 failed**. Cả 3 đã có từ trước và không thuộc plan 2 tuần: `test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`, `m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`.
- `ruff check` trên các file mới: sạch.

**Test cũ phải sửa:** `tests/test_impact.py` và `tests/test_w10_impact_mcp.py` ghim số item và danh sách risk feature; nay chỉ so item code và thêm feature mới. Ý nghĩa giữ nguyên, và có thêm test kiểm graph không có `G_arch` cho đúng kết quả như cũ.

## Review độc lập

Một reviewer không tham gia viết code đã đọc toàn bộ thay đổi: 1 Critical, 1 Important, 3 Minor. Đã sửa cả Critical và Important, mỗi lỗi có test tái hiện:

- `removed_api` báo xóa giả khi `check_api` không đọc được symbol sau patch (lỗi cú pháp, `__all__` động, decorator lạ), và báo cả Port vẫn còn.
- Luật override chạy cả trên graph không có Component, trái yêu cầu báo cáo giữ nguyên.

3 lỗi Minor cũng đã xử lý theo yêu cầu: byte không phải UTF-8 báo `AFTER_PARSE_FAILED`; ý nghĩa `checked_paths` được ghi rõ; test `select_ports` so đúng tập Port viết tay.

## Giới hạn đã biết

- Component là package, nên kể cả đi 1 bước `DEPENDS_ON` vẫn rộng với repo ít Component như xarray (5/7 ở trên).
- Chưa đo được độ chính xác của impact vì chưa có nhãn đúng/sai; override cũng chưa biết bao nhiêu item là đúng.
- `dependency_cycle_introduced` ([P] 1021) và `covering_tests_pass` ([P] 1023) luôn báo chưa tính.
- `check_api` không kết luận ở nhiều file, nên `removed_api` chỉ là phần đã biết.
- Port `route` chỉ gồm hàm tên `_` có route: không kiểm được mất port cho nhóm này, file đó báo `PARTIAL`.
- `G_arch` với snapshot của checkpoint TV1 (`f37df85f`) chưa kiểm được ở máy này; `docs/mcp_server/tools.md:15` của TV1 cần cập nhật.

## Tái tạo

```bash
source .superpowers/sdd/2026-11-08-tv2-layer1-remaining-facts/env.sh
python -m pytest -q -p no:cacheprovider tests/test_impact_arch.py tests/test_port_check.py tests/test_impact.py

env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR PYTHONPATH=src \
  python .superpowers/sdd/2026-11-09-tv2-im-1-impact/real_run.py <xarray-4629 checkout>
```
