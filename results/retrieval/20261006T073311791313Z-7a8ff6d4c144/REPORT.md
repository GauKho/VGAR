# Kết quả retrieval M2 tuần 5–6

Run: `20261005T045625580136Z-7fa20ac5dd80`; dataset: `princeton-nlp/SWE-bench_Verified` @ `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
Attempted: 25; completed: 25; failed: 0.
Scoring: `retrieval-scoring-v1`; budget: 8000 token; counter: `local-hf:Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554:sha256=aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4:no-special-tokens`.

Đây là retrieval pilot, không chạy agent sửa code, không chứng minh tỷ lệ repair PASS. Gold là changed-code proxy từ developer patch.

## Số chính — rank đầy đủ (dedup trước k)

Recall@k và MRR tính trên toàn bộ ranking, không phụ thuộc budget. Gold mà arm không chạm tới là miss (MRR đóng góp 0), task không bị loại. `*_reach` = tỉ lệ gold xuất hiện ở bất kỳ hạng nào.

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| file_recall@3 | 0.3600 | 25 |
| file_recall@5 | 0.5267 | 25 |
| file_recall@10 | 0.5933 | 25 |
| function_recall@3 | 0.2000 | 25 |
| function_recall@5 | 0.2783 | 25 |
| function_recall@10 | 0.4217 | 25 |
| file_mrr | 0.5907 | 25 |
| function_mrr | 0.4168 | 25 |
| file_reach | 1.0000 | 25 |
| function_reach | 1.0000 | 25 |

## Số phụ — context đóng gói @8000 token

Phản ánh thứ agent thực sự nhìn thấy: cùng counter, cùng budget, cùng snippet policy (tối đa 80 dòng/snippet, có header `path::symbol`). `tokens_to_first_gold_*` chỉ tính trên task có gold trong context (xem Eligible).

| Metric | Mean (macro) | Eligible tasks |
|---|---:|---:|
| packed_gold_file_in_context | 0.6767 | 25 |
| packed_gold_function_in_context | 0.4391 | 25 |
| packed_all_gold_files_in_context | 0.4400 | 25 |
| packed_all_gold_functions_in_context | 0.2000 | 25 |
| context_tokens | 7997.3 | 25 |
| packed_tokens_to_first_gold_file | 1163.0 | 23 |
| packed_tokens_to_first_gold_function | 1694.4 | 18 |
| packed_items_packed | 22.9 | 25 |
| packed_truncated | 1.0000 | 25 |

## Graph vs BM25

Hai chế độ cùng đọc từ một rank mỗi task. Số chính là rank đầy đủ; số phụ là context đóng gói. Nếu hai số mâu thuẫn (Graph thắng ở rank, thua ở packed) thì phân tích, không chọn số đẹp hơn.

Comparison status: **COMPARED**; paired tasks: 22/25.

`bm25@cap` = BM25 chấm lại trên top-100 chunk (Graph tối đa 100 node); `bm25 (full rank)` giữ nguyên để tham khảo, `*_reach` của nó không so được với Graph.

### Rank đầy đủ (chính)

| Metric | bm25 (full rank) | bm25@cap | graph | graph+F2P |
|---|---:|---:|---:|---:|
| file_recall@3 | 0.3485 (n=22) | 0.3485 (n=22) | 0.1970 (n=22) | 0.1970 (n=22) |
| file_recall@5 | 0.4924 (n=22) | 0.4924 (n=22) | 0.2955 (n=22) | 0.3182 (n=22) |
| file_recall@10 | 0.5530 (n=22) | 0.5530 (n=22) | 0.3674 (n=22) | 0.3902 (n=22) |
| function_recall@3 | 0.1864 (n=22) | 0.1864 (n=22) | 0.0909 (n=22) | 0.0909 (n=22) |
| function_recall@5 | 0.2299 (n=22) | 0.2299 (n=22) | 0.0909 (n=22) | 0.1136 (n=22) |
| function_recall@10 | 0.3701 (n=22) | 0.3701 (n=22) | 0.1288 (n=22) | 0.1515 (n=22) |
| file_mrr | 0.5576 (n=22) | 0.5567 (n=22) | 0.3385 (n=22) | 0.3448 (n=22) |
| function_mrr | 0.3964 (n=22) | 0.3955 (n=22) | 0.1845 (n=22) | 0.1936 (n=22) |
| file_reach | 1.0000 (n=22) | 0.8220 (n=22) | 0.5379 (n=22) | 0.5606 (n=22) |
| function_reach | 1.0000 (n=22) | 0.6061 (n=22) | 0.2894 (n=22) | 0.3121 (n=22) |

### Context đóng gói (phụ)

| Metric | bm25 (full rank) | bm25@cap | graph | graph+F2P |
|---|---:|---:|---:|---:|
| packed_gold_file_in_context | 0.6477 (n=22) | 0.6477 (n=22) | 0.5227 (n=22) | 0.5455 (n=22) |
| packed_gold_function_in_context | 0.3990 (n=22) | 0.3990 (n=22) | 0.2417 (n=22) | 0.2379 (n=22) |
| packed_all_gold_files_in_context | 0.4091 (n=22) | 0.4091 (n=22) | 0.3636 (n=22) | 0.3636 (n=22) |
| packed_all_gold_functions_in_context | 0.1364 (n=22) | 0.1364 (n=22) | 0.0909 (n=22) | 0.0909 (n=22) |
| context_tokens | 7997.0 (n=22) | 7997.0 (n=22) | 7373.5 (n=22) | 7350.8 (n=22) |
| packed_tokens_to_first_gold_file | 1215.8 (n=20) | 1215.8 (n=20) | 1305.3 (n=18) | 1387.7 (n=19) |
| packed_tokens_to_first_gold_function | 1733.7 (n=15) | 1733.7 (n=15) | 2539.5 (n=10) | 1576.1 (n=9) |
| packed_items_packed | 22.8 (n=22) | 22.8 (n=22) | 56.5 (n=22) | 54.9 (n=22) |
| packed_truncated | 1.0000 (n=22) | 1.0000 (n=22) | 0.6364 (n=22) | 0.5455 (n=22) |

### Delta theo cặp task

**graph − bm25@cap** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 22 | -0.1515 | [-0.2727, -0.0227] | 2 / 10 / 10 |
| file_recall@5 | 22 | -0.1970 | [-0.3598, -0.0189] | 5 / 4 / 13 |
| file_recall@10 | 22 | -0.1856 | [-0.3409, -0.0152] | 4 / 6 / 12 |
| function_recall@3 | 22 | -0.0955 | [-0.1917, -0.0045] | 1 / 13 / 8 |
| function_recall@5 | 22 | -0.1390 | [-0.2413, -0.0379] | 1 / 11 / 10 |
| function_recall@10 | 22 | -0.2413 | [-0.4098, -0.0625] | 1 / 9 / 12 |
| file_mrr | 22 | -0.2182 | [-0.3605, -0.0884] | 3 / 5 / 14 |
| function_mrr | 22 | -0.2110 | [-0.3745, -0.0417] | 1 / 6 / 15 |
| packed_gold_file_in_context | 22 | -0.1250 | [-0.3295, +0.0947] | 5 / 8 / 9 |
| packed_gold_function_in_context | 22 | -0.1573 | [-0.3250, +0.0098] | 2 / 10 / 10 |
| context_tokens | 22 | -623.5 | [-1287.4, -161.2] | 0 / 0 / 22 |

**graph+F2P − bm25@cap** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 22 | -0.1515 | [-0.2727, -0.0227] | 2 / 10 / 10 |
| file_recall@5 | 22 | -0.1742 | [-0.3371, -0.0038] | 5 / 5 / 12 |
| file_recall@10 | 22 | -0.1629 | [-0.3220, +0.0000] | 4 / 7 / 11 |
| function_recall@3 | 22 | -0.0955 | [-0.1917, -0.0045] | 1 / 13 / 8 |
| function_recall@5 | 22 | -0.1163 | [-0.2337, +0.0049] | 2 / 10 / 10 |
| function_recall@10 | 22 | -0.2186 | [-0.4019, -0.0303] | 2 / 8 / 12 |
| file_mrr | 22 | -0.2119 | [-0.3566, -0.0843] | 3 / 6 / 13 |
| function_mrr | 22 | -0.2019 | [-0.3688, -0.0289] | 2 / 6 / 14 |
| packed_gold_file_in_context | 22 | -0.1023 | [-0.2992, +0.1023] | 5 / 8 / 9 |
| packed_gold_function_in_context | 22 | -0.1611 | [-0.3418, +0.0268] | 3 / 9 / 10 |
| context_tokens | 22 | -646.2 | [-1313.4, -185.0] | 2 / 0 / 20 |

### Chẩn đoán Graph (quyết định hybrid vs giảm nhiễu anchors)

| Arm | Task không có anchor | Anchors/task | Unmapped (tổng) | Unmapped/task | Candidates/task |
|---|---:|---:|---:|---:|---:|
| graph | 0 | 79.7 | 0 | 0.00 | 83.0 |
| graph+F2P | 0 | 81.8 | 0 | 0.00 | 81.2 |

### Theo repo (mean File R@5 / Function R@5)

| Repo | n | bm25@cap | graph | graph+F2P |
|---|---:|---:|---:|---:|
| astropy/astropy | 2 | 0.42 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| django/django | 10 | 0.62 / 0.36 | 0.18 / 0.12 | 0.23 / 0.17 |
| matplotlib/matplotlib | 1 | 0.00 / 0.17 | 0.00 / 0.00 | 0.00 / 0.00 |
| pydata/xarray | 3 | 0.50 / 0.11 | 1.00 / 0.17 | 1.00 / 0.17 |
| pylint-dev/pylint | 3 | 0.33 / 0.00 | 0.17 / 0.00 | 0.17 / 0.00 |
| sympy/sympy | 3 | 0.44 / 0.31 | 0.39 / 0.11 | 0.39 / 0.11 |

### Task cần kiểm tay (Δ = Δfile R@5 + Δfunction R@5 so với bm25@cap)

- graph · Graph thua · `django__django-12325` (-1.50); anchors: `django.core.exceptions.ImproperlyConfigured`, `django.db.models.options.Options.managers`, `tests.many_to_one.models.First`, `django.setup`, `django.contrib.admin.views.autocomplete.AutocompleteJsonView.get`, `django.contrib.gis.gdal.feature.Feature.get`, `django.contrib.gis.gdal.raster.source.GDALRaster.origin`, `django.contrib.sessions.backends.base.SessionBase.get`
- graph · Graph thua · `django__django-13195` (-1.33); anchors: `django.contrib.messages.api.warning`, `django.db.models.aggregates.Max`, `django.db.models.fields.related_descriptors.ManyToManyDescriptor.through`, `django.db.models.query.QuerySet.none`, `django.db.models.query.QuerySet.only`, `django.http.request.HttpRequest.headers`, `django.http.response.HttpResponseBase`, `django.http.response.HttpResponseBase.delete_cookie`
- graph · Graph thua · `django__django-12741` (-1.00); anchors: `django.core.signing.Signer.signature`, `django.db.backends.base.operations.BaseDatabaseOperations.execute_sql_flush`, `django.test.html.Parser.current`, `django.core.management.sql.sql_flush`, `django.db.backends.base.operations.BaseDatabaseOperations.sql_flush`, `django.db.backends.mysql.operations.DatabaseOperations.sql_flush`, `django.db.backends.oracle.operations.DatabaseOperations.sql_flush`, `django.db.backends.postgresql.operations.DatabaseOperations.sql_flush`
- graph · Graph thắng · `pydata__xarray-3993` (+1.00); anchors: `xarray.core.coordinates.Coordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.coords`, `xarray.core.dataarray.DataArray.differentiate`, `xarray.core.dataarray.DataArray.dims`, `xarray.core.dataarray.DataArray.dims`, `xarray.core.dataarray.DataArray.integrate`
- graph · Graph thắng · `pydata__xarray-3305` (+0.50); anchors: `xarray.backends.rasterio_._parse_envi.default`, `xarray.backends.common.AbstractDataStore.attrs`, `xarray.backends.locks.CombinedLock.release`, `xarray.backends.locks.DummyLock.release`, `xarray.core.coordinates.AbstractCoordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.attrs`
- graph · Graph thắng · `pylint-dev__pylint-4551` (+0.25); anchors: `pylint.checkers.format.TokenWrapper.type`, `pylint.config.option_manager_mixin.OptionsManagerMixIn.help`, `tests.functional.i.invalid.invalid_name.a`, `tests.functional.u.useless.useless_super_delegation.Base.something`, `pylint.checkers.base.BasicChecker.__init__`, `pylint.checkers.base.NameChecker.__init__`, `pylint.checkers.base_checker.BaseChecker.__init__`, `pylint.checkers.classes.ClassChecker.__init__`
- graph+F2P · Graph thua · `django__django-12325` (-1.50); anchors: `django.core.exceptions.ImproperlyConfigured`, `django.db.models.options.Options.managers`, `tests.many_to_one.models.First`, `django.setup`, `django.contrib.admin.views.autocomplete.AutocompleteJsonView.get`, `django.contrib.gis.gdal.feature.Feature.get`, `django.contrib.gis.gdal.raster.source.GDALRaster.origin`, `django.contrib.sessions.backends.base.SessionBase.get`
- graph+F2P · Graph thua · `django__django-13195` (-1.33); anchors: `django.contrib.messages.api.warning`, `django.db.models.aggregates.Max`, `django.db.models.fields.related_descriptors.ManyToManyDescriptor.through`, `django.db.models.query.QuerySet.none`, `django.db.models.query.QuerySet.only`, `django.http.request.HttpRequest.headers`, `django.http.response.HttpResponseBase`, `django.http.response.HttpResponseBase.delete_cookie`
- graph+F2P · Graph thua · `django__django-12741` (-1.00); anchors: `django.core.signing.Signer.signature`, `django.db.backends.base.operations.BaseDatabaseOperations.execute_sql_flush`, `django.test.html.Parser.current`, `tests.backends.base.test_operations.SqlFlushTests.test_execute_sql_flush_statements`, `tests.backends.tests.LongNameTest.test_sequence_name_length_limits_flush`, `django.core.management.sql.sql_flush`, `django.db.backends.base.operations.BaseDatabaseOperations.sql_flush`, `django.db.backends.mysql.operations.DatabaseOperations.sql_flush`
- graph+F2P · Graph thắng · `pydata__xarray-3993` (+1.00); anchors: `xarray.tests.test_dataset.test_integrate`, `xarray.core.coordinates.Coordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.coords`, `xarray.core.dataarray.DataArray.differentiate`, `xarray.core.dataarray.DataArray.dims`, `xarray.core.dataarray.DataArray.dims`
- graph+F2P · Graph thắng · `pydata__xarray-3305` (+0.50); anchors: `xarray.tests.test_dataarray.TestDataArray.test_quantile`, `xarray.backends.rasterio_._parse_envi.default`, `xarray.backends.common.AbstractDataStore.attrs`, `xarray.backends.locks.CombinedLock.release`, `xarray.backends.locks.DummyLock.release`, `xarray.core.coordinates.AbstractCoordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`
- graph+F2P · Graph thắng · `django__django-13512` (+0.50); anchors: `django.contrib.gis.gdal.geomtype.OGRGeomType.django`, `django.utils.dateformat.DateFormat.I`, `django.utils.text.Truncator.chars`, `django.utils.xmlutils.SimplerXMLGenerator.characters`, `tests.admin_utils.tests.UtilsTests.test_json_display_for_field`, `tests.admin_utils.tests.UtilsTests.test_label_for_field`, `django.contrib.gis.gdal.feature.Feature.encoding`, `django.contrib.gis.gdal.geometries.OGRGeometry.contains`


## Per task

| Instance | Status | File R@5 | Function R@5 | Gold fn in context | Mapping coverage |
|---|---|---:|---:|---:|---:|
| astropy__astropy-13398 | SUCCEEDED | 0.3333 | 0.0000 | 0.8000 | 1.0000 |
| django__django-11138 | SUCCEEDED | 0.5000 | 0.0000 | 0.0769 | 1.0000 |
| matplotlib__matplotlib-14623 | SUCCEEDED | 0.0000 | 0.1667 | 0.1667 | 1.0000 |
| pydata__xarray-3305 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-4551 | SUCCEEDED | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| sphinx-doc__sphinx-10673 | SUCCEEDED | 0.3333 | 0.4000 | 0.2000 | 1.0000 |
| sympy__sympy-16597 | SUCCEEDED | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| astropy__astropy-8707 | SUCCEEDED | 0.5000 | 0.0000 | 0.5000 | 1.0000 |
| django__django-11734 | SUCCEEDED | 0.3333 | 0.3333 | 0.3333 | 1.0000 |
| pydata__xarray-3993 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
| pylint-dev__pylint-4604 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
| sphinx-doc__sphinx-8120 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| sympy__sympy-17318 | SUCCEEDED | 1.0000 | 0.6667 | 0.6667 | 1.0000 |
| django__django-11885 | SUCCEEDED | 0.5000 | 0.3750 | 0.5000 | 1.0000 |
| pydata__xarray-6992 | SUCCEEDED | 0.5000 | 0.3333 | 0.6667 | 1.0000 |
| pylint-dev__pylint-6386 | SUCCEEDED | 0.5000 | 0.0000 | 0.4000 | 1.0000 |
| sphinx-doc__sphinx-8548 | SUCCEEDED | 1.0000 | 0.5000 | 1.0000 | 1.0000 |
| sympy__sympy-20438 | SUCCEEDED | 0.3333 | 0.2500 | 0.5000 | 1.0000 |
| django__django-12155 | SUCCEEDED | 0.5000 | 0.3333 | 0.6667 | 1.0000 |
| django__django-12325 | SUCCEEDED | 1.0000 | 0.5000 | 1.0000 | 1.0000 |
| django__django-12741 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| django__django-13195 | SUCCEEDED | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| django__django-13212 | SUCCEEDED | 0.5000 | 0.1000 | 0.5000 | 1.0000 |
| django__django-13344 | SUCCEEDED | 0.3333 | 0.0000 | 0.0000 | 1.0000 |
| django__django-13512 | SUCCEEDED | 0.5000 | 0.0000 | 0.0000 | 1.0000 |
