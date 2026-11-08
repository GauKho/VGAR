# TV2 · L2-2: chạy thật cạnh `MAY_CALL` (08/11/2026)

> Plan: `docs/superpowers/plans/2026-11-08-tv2-l2-2-may-call.md` (Task 5).
> Spec: `docs/superpowers/specs/2026-11-08-tv2-l2-2-may-call-design.md` §7.

**Kết quả: ĐẠT.** Cả ba lần build thành công. Mọi cạnh `MAY_CALL` có confidence không quá 0.50 và `evidence` không rỗng. Bỏ cạnh
`MAY_CALL` thì graph xarray `static` khớp graph đã lưu từ trước.

## Test

- Lần cuối (sau khi sửa lỗi Minor và thêm profile schema, xem mục "Cập nhật"): `tests/test_may_call.py` 56 passed, `tests/test_callgraph_cases.py` 5 passed.
- Nhóm test graph cùng hai file trên, `test_tsg_enrichment.py`, `test_layer1_facts.py`, chạy với CLI tree-sitter-graph thật:
  **1063 passed, 1 skipped**. Mốc cũ là 1002 passed; 61 test là mới. Test bị skip là test symlink có sẵn.
- Một test cũ phải sửa có chủ đích: `test_b10_keeps_graph_version_and_records_resolver_profile` nay kiểm tra `statistics.legacy_graph_version`, theo quyết định định danh ngày 08/11.

## Cập nhật sau khi sửa (số mới nhất)

Sau khi bỏ các receiver literal/builtin và loại chính class hiện tại khỏi ứng viên của `super()`:

| | demo-shop `static` | demo-shop `lsp` | xarray `static` | xarray `scip` | xarray `scip-lsp` |
|---|---|---|---|---|---|
| Cạnh `MAY_CALL` | 10 | 0 | 16.944 | 3.885 | 3.884 |
| Lời gọi bị bỏ vì quá 5 ứng viên | 0 | 0 | 573 | 172 | 172 |
| Lời gọi chưa resolve | 20 | 10 | 22.644 | 16.739 | 16.736 |

LSP chạy thật bằng pyright 1.1.414. Trên demo-shop resolve được 10 lời gọi. Trên xarray LSP dừng ở giới hạn mặc định 200 request (`partial`), chỉ thêm 3 lời gọi. Chưa gặp trường hợp `lsp_ambiguous` thật; nhánh này mới được kiểm bằng giả lập.

Chấm trên repo test case (`--lsp-max-requests 2000`, pyright 1.1.414), 59 đích nội bộ:

| Chế độ | `CALLS`: P / R | `CALLS` + `MAY_CALL`: P / R | Lời gọi ngoài repo nhận nhầm |
|---|---|---|---|
| `static` | 1,000 / 0,237 | 0,579 / 0,746 | 2 |
| `scip` | 1,000 / 0,559 | 0,768 / 0,729 | 0 |
| `lsp` | 1,000 / 0,542 | **0,780 / 0,780** | 0 |
| `scip-lsp` | 1,000 / 0,559 | 0,768 / 0,729 | 0 |

`lsp` sinh được 4 cạnh `lsp_ambiguous` thật, ở nhóm 11. `scip-lsp` cho kết quả giống hệt `scip` vì LSP không thêm lời gọi nào (0 lời gọi, 12 request). `lsp` chạy riêng tốt hơn ở nhóm 7 (import, 6/6 so với 5/6) và nhóm 11 (4 đúng so với 2).

**Kiểm tra toàn diện Layer 1 + Layer 2 (08/11):** toàn bộ test suite: 2326 passed, 3 failed, 20 skipped, 1 xfailed (26 phút 44 giây).

| Test fail | Nguyên nhân | Bằng chứng |
|---|---|---|
| `tests/test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe` | Do `graph_version` mới | Pass trên commit `3f77fcf6`; pass khi builder trả định danh legacy |
| `tests/m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt` | Do `graph_version` mới | Lỗi `Context identity differs`; pass khi builder trả định danh legacy |
| `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory` | Có từ trước | Fail cả trên commit `3f77fcf6` |

Bật cùng lúc tree-sitter-graph với `static`, `scip`, `lsp`, `scip-lsp` trên repo test case, và `static`, `scip` trên xarray: tất cả qua validate, `tsg.status=ready`, `unmatched={}`.
Layer 1 chỉ thêm vào graph: bỏ fact Layer 1 thì phần còn lại, gồm cả `MAY_CALL`, giống hệt graph không bật tree-sitter-graph. Precision và recall trên repo test case không đổi. `project_legacy_w10` của xarray `static` khớp graph đã lưu trước khi làm L1/L2.

Đối chiếu lại với graph đã lưu: bỏ `MAY_CALL` thì 54.448 cạnh cũ vẫn khớp hoàn toàn. Bảng "Số đếm" bên dưới là lần chạy đầu, trước khi sửa.

Trên repo test case ở `static`, `CALLS` + `MAY_CALL` đạt precision 0,579, recall 0,746 (trước khi sửa 0,597 và 0,729), số lời gọi ngoài repo bị nhận nhầm giảm từ 3 xuống 2. Precision giảm vì loại class hiện tại khiến một số lời gọi `super()` không còn vượt ngưỡng 5 ứng viên và có thêm cạnh.

## Số đếm

| | demo-shop `static` | xarray-4629 `static` | xarray-4629 `scip` |
|---|---|---|---|
| Node | 120 | 39.279 | 39.279 |
| Cạnh trước `MAY_CALL` | 176 | 54.448 | 62.902 |
| Cạnh `MAY_CALL` | 10 | 17.041 | 3.926 |
| Cạnh sau `MAY_CALL` | 186 | 71.489 | 66.828 |
| Mức tăng | +5,7% | **+31,3%** | **+6,2%** |
| Lời gọi chưa resolve | 20 | 22.644 | 16.739 |
| Lời gọi có `MAY_CALL` | 10 | 7.948 | 1.665 |
| Lời gọi bị bỏ vì quá 5 ứng viên | 0 | 579 | 172 |
| `match_kind` | `name` 10 | `name` 17.041 | `name` 3.880, `scip_ambiguous` 46 |
| Confidence 0.30 | 0 | 13.390 | 3.003 |
| Confidence 0.50 | 10 | 3.651 | 923 |
| Thời gian build (`build_time_ms`) | | 6,9 s | 90,9 s |

- Chỉ khoảng một phần ba lời gọi chưa resolve ở `static` có cạnh `MAY_CALL` (7.948 / 22.644).
- `scip_ambiguous` có 46 cạnh, đều ở mức 0.50, tức đều có ứng viên cùng module hoặc được import; không có cạnh 0.42 trên xarray.
- Ước tính trước khi làm là 15.914 cạnh; số thật cao hơn 1.127 (7%). Bản ước tính dùng danh sách thư viện liệt kê tay và chưa quy đổi class. Chưa tách
  riêng phần chênh lệch của từng yếu tố.
- Thời gian trước đây ở `static` là 8,8 s, đo theo thời gian chạy cả script nên không so trực tiếp được với `build_time_ms`.

## Đối chiếu với graph đã lưu

So xarray `static` với `C:\Users\nlhnh\.claude\jobs\46c4db36\tmp\graphs\xarray_plain.json`, là graph build trước khi có `MAY_CALL`:

- File cũ dùng `repo_key` là `xarray`, lần này là `pydata/xarray`, nên phải bỏ `repo_key` khỏi id trước khi so.
- **54.448 cạnh khớp hoàn toàn** về loại, hai đầu, confidence, resolution, `rule_id`, `properties`.
- 39.279 node khớp, trừ `qualified_name` của node Repository, vốn chính là `repo_key`.

## Giới hạn đã biết

- Ở `static`, `data.get()` với `data` là dict của Python không phân biệt được là gọi ra ngoài repo, nên vẫn có thể sinh cạnh sai.
- Builder chỉ ghi import cấp module, nên `import numpy as np` đặt trong hàm không được nhận là thư viện ngoài (`test_function_local_import_known_limit`).
- Confidence không phụ thuộc số ứng viên.
- Số liệu trên là số lượng cạnh, chưa đo độ chính xác. Muốn biết đúng sai cần mẫu gán nhãn tay (G1).
- Graph hoặc DB đã lưu không có `MAY_CALL` cho tới khi build lại; graph mới có `graph_version` khác nên ghi được vào DB hiện có.
- Repo không dùng layout `src` có thể bị coi import nội bộ là bên ngoài, nên sinh thiếu cạnh.

## Tái tạo

```bash
OUT=.superpowers/sdd/2026-11-08-tv2-l2-2-may-call/run
XARRAY=C:/Users/nlhnh/.claude/jobs/46c4db36/tmp/repos/pydata__xarray-4629
PYTHONIOENCODING=utf-8

env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR \
  python scripts/build_graph.py D:/kltn/vgar-demo-shop/vgar-demo-shop $OUT/demo.json --repo-key demo/shop --revision base
env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR \
  python scripts/build_graph.py $XARRAY $OUT/xarray-static.json --repo-key pydata/xarray --revision base
env -u VGAR_TSG_EXECUTABLE -u VGAR_TSG_TREE_SITTER_DIR \
  python scripts/build_graph.py $XARRAY $OUT/xarray-scip.json --repo-key pydata/xarray --revision base --resolver scip \
  --scip-entry C:/Users/nlhnh/AppData/Roaming/npm/node_modules/@sourcegraph/scip-python/index.js --scip-timeout 900
python $OUT/compare.py demo xarray-static xarray-scip
python $OUT/compare2.py
```
