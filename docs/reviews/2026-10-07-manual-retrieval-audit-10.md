# Audit thủ công 10 task retrieval — tuần 5–6

Ngày: **07/10/2026**. Người thực hiện: **Codex tự đối chiếu tài liệu và source**, không phải đánh giá độc lập hoặc chữ ký của owner M1/M2/M3. Đây là kiểm tra retrieval, **không chạy model, không sửa lỗi SWE-bench, không chạy test của các repository bên ngoài**.

## 1. Input, cách chọn và evidence

- Graph: [dev25 no-Jedi](../../results/retrieval/20261007T014445273889Z-664d06a6c1c0/result.json), cùng dataset Verified revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, issue-only, snippet budget 8.000 token. No-Jedi được người dùng duyệt làm profile chính; **không đổi app default Jedi**.
- BM25: [bản sao nguyên bytes từ Git](../../artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/recovered-run/result.json). Đây là measurement lịch sử, không phải BM25 chạy mới. [Evidence phục hồi](../../artifacts/fixes/w3-w6/manual10-no-jedi/baseline-recovery/20261007T020222087444Z-9d7a6463840c/result.json) xác minh 25 Git blobs tại HEAD `b39e0dbf87645d39b9a68e87b19d0655df264a05` khớp raw SHA256 đã lưu. Checkout Windows chỉ khác LF→CRLF; không overwrite bản cũ, không sửa recorded hashes và không bỏ comparator guards.
- [JSON evidence của 10 case](../../artifacts/fixes/w3-w6/manual10-no-jedi/evidence/20261007T020305188540Z-617ca4415d05/result.json): issue, developer patch, base commit/tree, gold definitions/spans/excerpts, anchors, top5 items/files/functions, snippets, metrics, tokens và kiểm tra hash. Collector chỉ kiểm kỹ thuật; trường `manual_review_completed=false` trong artifact gốc là đúng tại thời điểm thu thập. **Phần diễn giải thủ công được hoàn tất bằng báo cáo này**, không ghi lại artifact terminal cũ.
- Chọn **10 task SUCCEEDED đầu tiên theo thứ tự manifest**, dựa status/availability, không theo điểm hoặc mức thắng BM25. Có 6 repository; Sympy lỗi vẫn giữ trong dev25 và báo cáo failures, không biến mất khỏi denominator. Đây là audit thuận tiện trên case có output, không đại diện thống kê cho mọi task.

Mỗi case đã đối chiếu: yêu cầu issue với developer patch; definition có thực trong base AST; path/span và snippet trong raw tree; anchors và top5 deduplicate riêng ở file/function level; metrics của context đã pack. Integrity collector đạt **10/10**; query/patch/corpus/base/gold khớp giữa hai arm, source inventory/hash và token budget hợp lệ, `unmapped_count=0`. Điều này **không chứng minh retrieval đúng về ngữ nghĩa**.

Gold-file/function là **proxy từ developer patch**, không phải toàn bộ vị trí sửa hợp lệ hoặc chứng minh causal necessity. File mới không có trong base được báo riêng, không tính như file rank-miss. Function mới không có base definition không được giả tạo thành label. Comment/docstring-only changes và outer/nested functions có thể cùng thuộc proxy; phải đọc patch để giải thích.

## 2. Bảng số liệu đã đối chiếu

Giá trị recall/coverage dưới đây là tỷ lệ 0–1, không phải repair pass rate. `F5` = file Recall@5; `N5` = function Recall@5; `PF`/`PN` = gold file/function coverage trong **packed context**. `B` = BM25 full rank; `G` = issue-only Graph. Không lấy `graph_f2p` oracle làm kết quả chính. Số token là packed Graph counter chính thức, không phải prompt/model cost.

| Task | Gold file / function | F5 B→G | N5 B→G | PF B→G | PN B→G | Graph tokens | Anchors |
|---|---:|---:|---:|---:|---:|---:|---:|
| astropy13398 | 3 / 5 | .333→0 | 0→0 | .333→0 | .800→0 | 7.993 | 188 |
| django11138 | 4 / 13 | .500→0 | 0→0 | .750→.250 | .077→0 | 7.466 | 111 |
| matplotlib14623 | 3 / 6 | 0→0 | .167→0 | .333→.333 | .167→.333 | 6.953 | 50 |
| xarray3305 | 2 / 2 | .500→1 | 0→0 | .500→1 | 0→0 | 6.396 | 23 |
| pylint4551 | 4 / 4 | 0→.250 | 0→0 | 0→1 | 0→0 | 7.969 | 323 |
| sphinx10673 | 3 / 5 | .333→0 | .400→0 | .667→0 | .200→0 | 7.217 | 40 |
| astropy8707 | 2 / 2 | .500→0 | 0→0 | .500→0 | .500→0 | 7.997 | 52 |
| django11734 | 3 / 3 | .333→0 | .333→0 | .333→.333 | .333→.333 | 6.482 | 72 |
| xarray3993 | 2 / 2 | .500→1 | 0→.500 | 1→1 | 0→1 | 7.970 | 16 |
| pylint4604 | 2 / 1 | .500→0 | 0→0 | 1→0 | 0→0 | 7.956 | 9 |

Giá trị được làm tròn để đọc; JSON lưu precision đầy đủ. Không dùng trung bình 10 case này làm headline dev25/CI; comparator đánh giá toàn bộ valid pairs với exclusions/failures rõ ràng.

## 3. Đối chiếu từng case

### 3.1. astropy__astropy-13398 — chuyển đổi ITRS trực tiếp

Issue yêu cầu chuyển topocentric ITRS↔AltAz/HADec trực tiếp, tránh đổi vị trí do tuyến qua frame khác. Patch thêm `itrs_observed_transforms.py` và thay location/rotation handling ở `intermediate_rotation_transforms.py`, thuộc tính EarthLocation của ITRS, import đăng ký transforms.

Gold base gồm ba file và năm hàm trong `intermediate_rotation_transforms.py`: `cirs_to_itrs`197–206, `itrs_to_cirs`209–217, `itrs_to_tete`159–167, `tete_to_itrs`147–156, `tete_to_itrs_mat`64–87. Hàm cuối có sửa chính tả comment `siderial`→`sidereal`: gold-changed không đồng nghĩa mọi hàm đều cần sửa để chữa bug. File mới chưa tồn tại ở base nên file-retrievability=.75; denominator chính có ba file retrievable, không bốn.

188 anchors có ITRS đúng file nhưng top5 files lại là `matrix_utilities.py`, `jparser.py`, `fits2bitmap.py`, `spectral_quantity.py`, `converters.py`. Top1 `rotation_matrix` đúng chủ đề toán quay nhưng **không phải transform cần sửa**. Không gold file/function nào được pack; BM25 pack .333 file và .800 function. Đây là semantic/localization miss thực, không mapping error. Không đổi scoring sau khi thấy gold.

### 3.2. django__django-11138 — timezone của connection

Issue mô tả date filtering trên database connection TIME_ZONE khác UTC. Patch sửa SQL conversion MySQL/Oracle và các registered SQLite datetime functions/arity, lấy timezone connection thay giả định UTC.

Đối chiếu base: MySQL `_convert_field_to_tz`71–74 chứa CONVERT_TZ từ UTC; Oracle97–104 dùng FROM_TZ0:00; SQLite `_convert_tzname_to_sql`87–88 chỉ truyền timezone đích. Có 4 file/13 hàm base, trong đó `get_new_connection`194–243 và các helper datetime. Mapping/spans hợp lệ.

111 anchors có `DatabaseWrapper.close` trong gold file, nhưng không phải hàm sửa. Top5 files là template/defaultfilters, cache/base, db/backends/base/base, forms/boundfield, mail/base; top1 `defaultfilters.date` **format ngày cho template, không sửa SQL timezone**. Packed file=.25 nhưng function=0; file-level hit không đủ. BM25 packed file=.75, function=1/13. Anchor trùng từ `date/default/close` là dấu hiệu nhiễu quan sát được, chưa là profiling hoặc chứng minh một weight duy nhất gây lỗi.

### 3.3. matplotlib__matplotlib-14623 — đảo chiều axis log

Issue dùng `set_ylim(y.max(), y.min())` làm mất thứ tự đảo trên log axis. Patch giữ orientation ở setters2D/3D và bỏ forcing `increasing=False` ở `Locator.nonsingular`.

Gold: `_AxesBase.set_xlim`3161–3284, `set_ylim`3540–3664; `Locator.nonsingular`1523–1525; ba setters3D589–759. Top5 files table/pyplot/widgets/github_stats/scale; top1 `Table.scale` chỉ thay kích thước cell, không axis bounds. Gold-path anchor `_AxesBase.axis` có liên quan nhưng khác setters cần sửa.

Graph F5/N5=0 nhưng packed file=1/3,function=2/6; các candidate hữu ích xuất hiện **sau top5**. BM25 packed function=1/6. Không đồng nhất top-k với packed coverage. Với hàm dài và snippet cap80 dòng, label hit theo span/scorer cũng không chứng minh context chứa toàn bộ logic thực thi cần thiết.

### 3.4. pydata__xarray-3305 — keep_attrs của quantile

Issue `DataArray.quantile(keep_attrs=True)` trả attrs rỗng. Patch chuyển keep_attrs từ Dataset xuống Variable.quantile và xử lý option attrs. Gold hai hàm: `Dataset.quantile`4694–4790 có keep_attrs ở base; `Variable.quantile`1595–1661 chưa có argument này.

Top5 files rasterio/dataarray/dataset/variable/coordinates, nên Graph F5=1 (BM25=.5). Nhưng top1 `_parse_envi.default` chỉ strip braces; function top5 gồm getters/setters attrs/dims, **không quantile**. Packed file=1 nhưng function=0. Đây là localization đúng file, thiếu đúng function; không thể kết luận coding agent đủ context để sửa chỉ vì đạt file recall.

### 3.5. pylint-dev__pylint-4551 — annotation trong Pyreverse

Issue UML thiếu kiểu khi argument default None dù có annotation. Patch thay inference trong `ClassDiagram.class_names`, `Linker.visit_assignname`, `Linker.handle_assignattr_type`, hiển thị annotation ở `DotWriter.get_values`; thêm helpers trong utils.

Bốn gold hàm base ở các spans118–132,192–224,226–237,126–145; các helpers mới không có base definition nên không giả thêm function label. `utils.py` vẫn là gold file trong base dù phần logic sửa chủ yếu là function mới.

323 anchors là số lớn, không tự mang nghĩa coverage tốt. Function top5 help/type/default/Relationship.__init__/CustomHelpFormatter.__init__; top1 là CLI help, **không xử lý annotation inference**. Filetop5 có diagrams.py nên F5=.25; packed đủ4file nhưng 0/4goldfunctions. BM25 packedfile/function0. Phải giữ kết luận “Graph tốt hơn ở file nhưng chưa đúng function”, không gộp thành repaired.

### 3.6. sphinx-doc__sphinx-10673 — generated pages trong toctree

Issue cảnh báo genindex/modindex/search không có trong found_docs. Patch nhận generated names trong `TocTree.parse_content`, resolve link và bỏ qua generated pages khi assign figure numbers.

Gold ba file/năm hàm, gồm outer `TocTree.resolve`41–259 và nested `_entries_from_toctree`110–216; `assign_figure_numbers`202–283 và nested `_walk_doctree`249–269. Đây là labels lồng nhau có thật; không duplicate cùng identity nhưng không phải năm lỗi độc lập.

40 anchors không có goldpath anchor. Top5 files builders/__init__, latex/theming, io, directives/code, util/docutils; top1 `Builder.read` có liên quan quá trình build nhưng **không toctree logic cần sửa**. Graph packed coverage0; BM25 file=2/3,function=1/5, N5=.4. Evidence không hỗ trợ tuyên bố graph thắng ở case này.

### 3.7. astropy__astropy-8707 — FITS bytes vs str

Issue Header/Card.fromstring với bytes trên Python3; patch normalize Latin1, xử lý separator/END/CONTINUE và hướng dẫn doctest. Gold chỉ hai file source card.py/header.py, hai hàm `Card.fromstring`547–559, `Header.fromstring`329–397; docs/tests không được tính source gold.

52 anchors không có goldpath anchor. Top5 Time/core, XML writer, Quantity, Unit, compressed HDU; top1 `TimeDelta.to` chuyển unit, **không decode FITS header**. Graph F5 và packed coverage0; BM25 packed file/function=.5. “data/to” là từ quá rộng so với issue, không phải gold mapping sai.

### 3.8. django__django-11734 — OuterRef và exclude

Issue OuterRef trong exclude/~Q bị reference sai query level. Patch bỏ `AutoFieldMixin.get_prep_value`, chỉnh RelatedLookupMixin cho expression, bọc OuterRef thêm lớp trong Query.split_exclude.

Gold ba basefunctions: hàm bị **xóa** vẫn có ở base2335–2337 nên retrieval label hợp lệ; `get_prep_lookup`103–117; `split_exclude`1685–1754. Không lấy post-patch function mới để chấm input trước sửa.

72 anchors không có goldpath anchor. Top5 files admin_list, models/query, template/base, template/library, regex_helper; top1 `admin_list.results` dựng result list, **không resolve OuterRef**. Graph F5/N5=0 so BM25=1/3; packed hai arm đều file/function1/3. Không biến file `django/db/models/query.py` thành gold `django/db/models/sql/query.py` vì tên giống nhau.

### 3.9. pydata__xarray-3993 — tên argument integrate

Issue DataArray dùng `dim` nhưng Dataset dùng `coord`. Patch thêm coord/compatibility warning, chặn ambiguous dim+coord; Dataset.integrate có annotation/doc adjustment. Gold `DataArray.integrate`3483–3532 và `Dataset.integrate`5966–6023. Gold function thứ hai chứa doc/API edits, không đồng nghĩa cả hai có computational bug.

16 anchors có đúng `DataArray.integrate`; function này đứng top1 với signature base dùng dim, phù hợp problem. Filetop5 dataarray/coordinates/dataset/groupby/variable. Graph F5=1,N5=.5; packed file/function1. BM25 F5=.5,N5=0; packedfile1 nhưng function0. Đây là ví dụ graph có giá trị **localization và function context**. Không từ một case suy ra performance tổng thể hoặc repair pass rate.

### 3.10. pylint-dev__pylint-4604 — qualified name trong type comment

Issue `# type: abc.ABC` gây unused-import sai. Patch thêm recursion với astroid.Attribute.expr trong `_store_type_annotation_node` và bổ sung IS_PYPY ở constants.py. Gold hai file, chỉ một hàm base1823–1843: code hiện chỉ chấp nhận Name/Subscript, đúng chỗ thiếu Attribute.

9 anchors không có goldpath anchor. Filetop5 diagrams/format/functional_test_file/mccabe/_check_docs_utils; top1 `PackageDiagram.module` tìm module trong UML, **không type comment của VariablesChecker**. Graph packed0; BM25 pack đủgoldfiles nhưng 0function. constants.py là module-level edit nên file label hợp lệ, không tạo fake function label để tăng recall.

## 4. Kết luận và hành động trong scope

1. Đã hoàn tất **manual evidence/interpretation10 case** ở mức self-audit: labels/base/source/top-k/packing đã đối chiếu, không thấy raw-span mapping mismatch trong10case. Không tuyên bố audit độc lập hoặc mọi label toàn dataset đúng.
2. Graph có ích ở xarray3993 và file localization xarray3305/pylint4551; nhiều case lexical ambiguity làm anchors/rank lệch chủ đích. **Integrity PASS và unit PASS không phải accuracy PASS**.
3. File hit không đảm bảo function hit; top5 misses không đồng nghĩa packed misses; long-function80line cap có hạn chế. Gold patch proxy gồm docs/comments/additions/deletions phải giải thích riêng.
4. No-Jedi giảm một đường call resolution; chưa đo causal impact với Jedi paired cùng tasks nên không quy mọi miss cho no-Jedi. Không sửa weights/hops/budget hoặc gold dựa measurements này.
5. Dev25 failures cần báo riêng, giữ25attempted và valid-pair denominator; cần kết quả comparator/CI trước kết luận toàn bộ. M1/M2/M3 vẫn cần owner review. Environment50–100/smoke3 và inference ngoài đợt này, **NOT_RUN**.

Failures/helper errors cũng giữ nguyên: KeyError do collector đọc sai config level đã sửa helper; BM25 raw-hash mismatch được phục hồi **copy Gitblob có kiểm chứng**, không bỏ guard. Hai lỗi helper không phải retrieval-score thất bại của task đã thành công.
