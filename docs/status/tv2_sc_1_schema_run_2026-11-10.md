# TV2 · SC-1: kết quả schema `S`, 10/11/2026

Spec: `docs/superpowers/specs/2026-11-10-tv2-sc-1-schema-design.md`. Plan: `docs/superpowers/plans/2026-11-10-tv2-sc-1-schema.md`.

## `S` sau SC-1

| Thành phần | Kết quả |
|---|---|
| `TN`, `TE`, `beta` | 32 loại node, 26 loại cạnh, giữ nguyên |
| `delta` cho node | 31 khóa bắt buộc trên 14 loại; 18 loại chỉ có trường chung |
| `delta` cho cạnh | `DEPENDS_ON` (Component → Component) cần `weight`, `TRACES_TO` (Issue → Component) cần `anchor_count`, đều là số nguyên ≥ 1 |
| `Gamma` | 14 bất biến: 9 đã có (gồm `endpoints_exist` và `may_call_bounded` vốn được kiểm nhưng chưa có tên) và 5 mới (`port_owner`, `port_symbol`, `method_owner`, `failing_test_targets`, `ast_single_parent`) |
| `SCHEMA_HASH` | `sha256:5de556ce2d9e2475b82c1ef476c56c338eb1fc08b29868854c414ddce8a01109`, giống nhau trên Windows và WSL (tính lại sau khi nới `port_owner`) |

`delta` chỉ gồm khóa builder luôn ghi và có code khác đọc. Đã bỏ khỏi bảng trong spec sau khi mở từng chỗ đọc: `Repository.repository_revision`, `Repository.root_uri` (code đọc trường cùng tên ở cấp document), `File.size_bytes`, `Import.raw_text`, `Class.decorators`, `Component.kind`, `Component.tests`, `Port.kind`, `ErrorMessage.message`, `ErrorMessage.occurrences`, `AcceptanceCriterion.text`, `Issue.failing_tests`, `Issue.task_id`. `Module.is_package` có code đọc nhưng không bắt buộc, vì graph lưu từ builder cũ trong fixture của repo không có khóa này. Trong 7 loại chỉ có khi bật công cụ, chỉ `Route` có khóa bắt buộc (`route_path`, `methods`).

## Test

- `tests/test_schema_contract.py`: document tối thiểu dựng từ `S` có đủ 32 loại node, 26 loại cạnh và qua validate. Từ đó sinh 103 mutant (thiếu hoặc sai kiểu từng khóa, sai đầu cuối từng loại cạnh, vi phạm từng bất biến); cả 103 đều bị từ chối.
- Chuỗi `CONTAINS` lồng 5.000 tầng qua validate. Vòng ở tầng 3.000 được báo kèm đường đi `n:a -> n:b -> n:c -> n:a`.
- Windows: các test của SC-1 cùng test của builder, overlay, trace, `G_code`, `G_arch`, impact, port, SQLite: 688 passed (Task 2) và 130 passed (Task 3, Task 4).
- WSL Ubuntu (Python 3.11.17), với code cuối cùng: 602 passed, 4 skipped, 1 xfailed. `tests/test_port_check.py` không chạy trên WSL vì venv thiếu `langchain_mcp_adapters` mà `vgar.mcp` import; file này pass trên Windows.

## Graph thật qua validate

| Bộ | Kết quả |
|---|---|
| 31 task dev (16 task trước, 15 task django, matplotlib, scikit-learn, sphinx, sympy), graph cùng overlay task | 31/31 qua |
| `tests/fixtures/vgar-demo-shop` (137 node, 217 cạnh, 7 Component, 10 Port, 10 `MAY_CALL`), graph cùng overlay | Qua |
| 5 repo `tests/fixtures/vgar-arch-cases` | Qua (qua test) |

Graph lớn nhất là `sympy__sympy-20590`: 905.735 node, 1.286.005 cạnh, build và validate trong 278 giây.

## Benchmark tuyến tính

`scripts/bench_schema_validation.py`, chạy trên WSL, 20 lần mỗi mức, lấy trung vị.

| Graph | `\|V\|+\|E\|` | Thời gian validate | µs mỗi phần tử |
|---|---|---|---|
| Tổng hợp | 1.001 | 2,7 ms | 2,70 |
| Tổng hợp | 2.501 | 7,7 ms | 3,09 |
| Tổng hợp | 6.001 | 22,1 ms | 3,68 |
| Tổng hợp | 14.001 | 50,3 ms | 3,59 |
| Tổng hợp | 33.001 | 122,6 ms | 3,71 |
| Tổng hợp | 80.001 | 315,9 ms | 3,95 |
| Tổng hợp | 200.001 | 921,6 ms | 4,61 |
| xarray (thật) | 90.590 | 361 ms | 3,99 |
| django (thật) | 455.984 | 1.981 ms | 4,35 |
| sympy (thật) | 707.510 | 2.914 ms | 4,12 |

Fit log-log trên 7 mức tổng hợp: hệ số góc **1,086**, R² **0,9993**. Giữa xarray và sympy (gấp 7,8 lần kích thước), thời gian tăng 8,07 lần, tức hệ số góc khoảng 1,02.

Chi phí mỗi phần tử của graph tổng hợp tăng nhẹ theo kích thước (2,7 lên 4,6 µs). Tắt bộ dọn rác của Python chỉ giảm một chút (4.000 file: 5,25 xuống 4,93 µs), nên phần tăng không đến từ GC. Mỗi check trong validator chỉ duyệt một lượt, nên nhiều khả năng phần tăng đến từ chi phí bộ nhớ của dict lớn; điều này chưa được đo riêng.

Tỉ lệ cạnh trên node: graph tổng hợp 1,27; graph SWE-bench thật 1,5–1,8 (astropy 1,5, xarray 1,75, django 1,6). Spec ghi 1,15–1,33 theo fixture nhỏ; đã sửa lại.

## Kiểm tra đủ ba tầng trên `vgar-demo-shop`

Build bằng `scripts/build_graph.py` với SCIP, tree-sitter-graph, Joern (`--joern`) và JARVIS (`--enable-jarvis`): 272 node, 554 cạnh, 23 giây. Không có Pyright trên máy nên không chạy resolver LSP.

| Tầng | Kết quả |
|---|---|
| `G_repo` | 490 phần tử; tree-sitter-graph `ready` (Field, GlobalVariable, Schema); SCIP `ready` resolve 36/46 call site, 10 call site còn lại gọi ra ngoài repo (`int`, `sum`, `ValueError`, `pytest.raises`, method của dict) |
| `MAY_CALL` | Build không có SCIP sinh 10 cạnh `MAY_CALL` (`cart.add`, `cart.subtotal`); bật SCIP thì cả 10 thành `CALLS` đúng đích, nên không còn `MAY_CALL` |
| `G_code` (Joern) | `ready`, khớp 11/11 hàm; 29 Statement; `AST_CHILD` 120, `CFG_NEXT` 16, `DATA_DEPENDS_ON` 27, `CONTROL_DEPENDS_ON` 10 |
| JARVIS | `ready`, xác nhận 9 cạnh `CALLS` |
| `G_arch` | 7 Component, 10 Port, `DEPENDS_ON` 7, `CONSUMES_PORT` 7 |
| `G_task` và trace | Issue có traceback và failing test: frame → `discount_amount` (0,95), failing test → Test (1,0), Issue → Component `discounts` (0,95) |
| Schema | Graph và graph cùng overlay đều hợp lệ |
| Retrieval | Context gồm test bị fail, `discount_amount`, `is_eligible`; giống hệt khi không có Joern, vì retrieval không đi theo cạnh `G_code` |
| Impact (patch `>` → `>=`) | Node bị đổi `is_eligible`; 2 caller, 4 test, 2 component bị ảnh hưởng; không mất port |
| SQLite và service | Nạp được graph đủ ba tầng; chuỗi gọi `checkout → discount_amount → is_eligible` đúng |

Không lộ lỗi nào giữa các tầng. Hiện không code nào trong `src` đọc cạnh `G_code`, và chỉ `build_graph.py --joern` mới bật Joern.

## Ghi nhận

- Build một thư mục có `__init__.py` ngay ở gốc (ví dụ `src/vgar`) sinh ra Module có `name` rỗng, và validator từ chối. Lỗi của builder Layer 1, chưa sửa.
- Repo mẫu chung của nhóm (plan dòng 97, 470) chưa chốt định dạng đáp án. `vgar-demo-shop` hiện có trong `tests/fixtures` nhưng chưa được commit; khi nhóm chốt, thêm ca "repo mẫu qua validate".
- Lượt suite đầu tiên làm lộ một luật quá chặt: `tests/test_w9_bm25_handoff.py::test_edges_cannot_influence_bm25_ranking` xóa hết cạnh để chứng minh BM25 không phụ thuộc cạnh, và `port_owner` khi đó đòi cạnh `EXPOSES_PORT`. Luật đã được nới: chỉ yêu cầu `owner_component_id` là một Component có thật. Thêm test `test_document_without_edges_keeps_valid_ports`, fail trước khi sửa và pass sau khi sửa.
- Toàn bộ test suite trên Windows với code cuối cùng (`-m "not hf and not docker"`, 32 phút 14 giây): 2929 passed, 20 skipped, 2 xfailed, 3 failed đúng là 3 test đã biết (`tests/m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`, `tests/test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`).
