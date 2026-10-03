# Inspection 10 task thật — M2 W5–6

Ngày: 01/10/2026. Run dùng để bàn giao: `20261001T134641055034Z-5295e04e781d`.

Đây là kiểm tra từng case do assistant thực hiện bằng cách đọc issue, developer diff, base function signatures/snippets, gold events và ranking của 10 task đầu theo manifest đã khóa. **Không phải chứng nhận của leader/người audit độc lập, không phải kiểm thử repair/test harness**. Người trong nhóm cần xác nhận lại và ký tên khi bàn giao.

Evidence cho mỗi hàng: `../results/retrieval/20261001T134641055034Z-5295e04e781d/tasks/<instance_id>.json`; developer diff: `../data/gold/patches/<instance_id>.patch`. File task lưu query/base_commit/source/corpus hashes, source archive provenance, candidate spans và complete ranking identities. Không chỉnh prompt/tham số theo inspection này; giữ nguyên toàn bộ 25 task, kể cả score thấp.

## Bảng kiểm tra

| Instance | Gold files/functions | File R@5 | Function R@5 | Kết luận kiểm tra |
|---|---:|---:|---:|---|
| astropy__astropy-13398 | 3 / 5 | 0.3333 | 0.0000 | Đúng miền tọa độ nhưng chưa trúng các function thay đổi ở top5 |
| django__django-10554 | 2 / 1 | 0.5000 | 0.0000 | Tìm đường gọi QuerySet, chưa đến đúng get_order_by |
| matplotlib__matplotlib-14623 | 3 / 6 | 0.0000 | 0.1667 | Từ khóa log/axis bị docstring/examples lấn; hunk offset đã xử lý đúng |
| mwaskom__seaborn-3187 | 2 / 2 | 0.5000 | 0.5000 | Một gold function xuất hiện; đầu ranking vẫn có plotting examples nhiễu |
| pydata__xarray-3095 | 2 / 8 | 0.5000 | 0.0000 | Trúng API copy, chưa định vị adapter giữ dtype |
| pylint-dev__pylint-4551 | 4 / 4 | 0.0000 | 0.0000 | Từ typing/Python dẫn sang checker, bỏ lỡ pyreverse |
| pytest-dev__pytest-5840 | 2 / 4 | 0.5000 | 0.0000 | Trúng pathlib nhưng chưa tới đúng conftest handlers |
| scikit-learn__scikit-learn-12682 | 2 / 13 | 1.0000 | 0.1538 | File retrieval tốt; gold patch sửa nhiều function ngoài symbol nêu trong issue |
| sphinx-doc__sphinx-10673 | 3 / 5 | 0.3333 | 0.4000 | Định vị đúng resolve/nested helper, chưa cover mọi file |
| sympy__sympy-13091 | 21 / 56 | 0.0476 | 0.0179 | Tìm đúng Basic.__eq__ nhưng patch rất rộng, recall tuyệt đối cần diễn giải denominator |

Mười cases đều có mapping coverage 1.0 trong run này. Điều đó nghĩa các line-change events được phân loại, **không chứng minh gold là toàn bộ causal relevance**.

## Nhận xét từng case

1. **Astropy**: issue yêu cầu ITRS ↔ AltAz/HADec ở địa tâm/topocentric, có cả draft code trong issue (đó là input công khai hợp lệ, không phải gold bị đưa thêm). BM25 ưu tiên `cirs_to_observed`, `observed_to_cirs`, `icrs_to_observed`. Gold có các chuyển đổi ITRS ở `intermediate_rotation_transforms.py`, module import và ITRS class. Gold-only new functions/files không ép thành retrievable base functions. Các kết quả đầu có liên quan miền nhưng không nhất thiết là location cần sửa.
2. **Django**: issue/stack trace nêu `values_list`, `union`, ordering và compiler. Ranking đầu là các Iterable.__iter__, hợp lý về lexical proximity. Developer diff sửa `SQLCompiler.get_order_by` và thêm `add_select_col`; function mới không được gán thành function có sẵn trong base. Gold function count=1 không phải thiếu mapping. Đây là case để M1 kiểm tra caller/callee path tới compiler.
3. **Matplotlib**: issue đảo trục log khi `set_ylim(max,min)`. Developer hunk của `_base.py` có exact old context tại header+2 dòng; events ghi hai `hunk_relocated=+2`. Gold có set_xlim/set_ylim/nonsingular và các setters 3D. BM25 ưu tiên `hexbin` vì docstring chứa log/axis/limits. File R@5 và function R@5 khác nhau vì module chunks bị loại khỏi function ranking trước k, không phải metric mâu thuẫn.
4. **Seaborn**: issue nêu `ScalarFormatter` offset/scientific formatting. Developer thêm `set_useOffset(False)`/`set_scientific(False)` trong setup và legend utility. Gold là `ContinuousBase._setup`, `locator_to_legend_entries`. Lexical hits bao gồm code dùng plotting API nhưng chỉ một nửa gold functions ở top5. Cần M1 kết nối formatter/legend utilities thay vì chỉ tên plotting symbols.
5. **Xarray**: issue public `Dataset.copy`/`DataArray.copy` làm Unicode index thành object. Top results đúng public API copy; developer sửa `PandasIndexAdapter` và `IndexVariable.copy` sâu hơn. Nhiều function signatures/dtype-related edits là legitimate changed-code proxy, không bỏ chúng để tăng recall. Case này kiểm tra graph dependency giữa public API và adapter.
6. **Pylint**: issue thật là pyreverse/UML không đọc annotation khi value mặc định None. Diff sửa ClassDiagram, Linker và DotWriter, thêm helper utilities. Top lexical results lại nằm lint/checker/config. Đánh giá retrieval yếu, không gọi pipeline lỗi. M1 nên audit task anchors `pyreverse` và component/module proximity.
7. **Pytest**: lỗi Windows conftest import/casing, diff chuyển dùng realpath và loại unique_path normalization. Corpus trước inspection còn `testing/python/collect.py`; đã xác định đây là test directory, thêm RED→GREEN regression và loại `testing/`, không loại `src/_pytest/`. Run bàn giao không có testing directory trong corpus; ranking vẫn có pathlib/import helper nhưng chưa đúng gold conftest handlers.
8. **Scikit-learn**: issue SparseCoder không expose max_iter cho lasso_cd. BM25 tìm đúng dict_learning.py và example source. Diff thực sự còn chỉnh ricker formula ở example và luồng sparse_encode/dict_learning constructors/fit; gold proxy rộng hơn symptom. File Recall@5=1 không tương đương toàn bộ function context đủ để sửa.
9. **Sphinx**: issue có exact warning `toctree contains reference to nonexisting document`, genindex/modindex/search. Ranking `TocTree.resolve` có chính warning này; nested `_entries_from_toctree` được phân biệt với parent. Gold còn parse_content và collectors/_walk_doctree, hợp lý để thử graph traversal qua pipeline directive→adapter→collector.
10. **Sympy**: issue yêu cầu NotImplemented thay False khi comparison với unknown type; có explicit Basic.__eq__ mention. Ranking tìm Basic.__eq__ nhưng cả Basic._subs/helper lexically gần cũng lên cao. Developer patch trải 21 file/56 functions. Ngay cả top5 hoàn hảo, upper bound file Recall@5 chỉ 5/21 và function Recall@5 chỉ 5/56. Không dùng một symbol hit để tuyên bố toàn bộ patch scope đã cover.

## Kết luận và việc cần phối hợp

- Baseline chạy đúng pipeline không có nghĩa score cao. Giữ các case khó và công bố macro mean + denominators.
- Inspection đã tìm và dẫn đến sửa lỗi filtering thực; regression/evidence lưu trong `results/tests`.
- Case stack trace/public API → implementation sâu là điểm cần M1 debug. Không thay BM25 thành graph để làm mất baseline.
- Cần cùng M1 xem đủ10, chạy Graph thật cùng query/commit/corpus/budget; M3 xác nhận subset. Các bước phối hợp này chưa hoàn thành.

Người xác nhận của nhóm: **chưa có**. Ngày xác nhận: **chưa có**.
