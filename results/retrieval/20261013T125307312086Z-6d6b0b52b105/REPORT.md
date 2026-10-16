# Kết quả retrieval M2 tuần 5–6

Run: `20261013T120702363418Z-b067d65c7d70`; dataset: `princeton-nlp/SWE-bench_Verified` @ `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
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

`bm25@cap` = BM25 chấm lại trên top-100 chunk (Graph tối đa 100 node); đây là ablation phụ. Baseline chính là `bm25 (full rank)`; `graph+F2P` là oracle chẩn đoán.

### Rank đầy đủ (chính)

| Metric | bm25 (full rank) | bm25@cap (diagnostic) | graph | graph+F2P |
|---|---:|---:|---:|---:|
| file_recall@3 | 0.3485 (n=22) | 0.3485 (n=22) | 0.3598 (n=22) | 0.3598 (n=22) |
| file_recall@5 | 0.5379 (n=22) | 0.5379 (n=22) | 0.4470 (n=22) | 0.4962 (n=22) |
| file_recall@10 | 0.6136 (n=22) | 0.6136 (n=22) | 0.5720 (n=22) | 0.6023 (n=22) |
| function_recall@3 | 0.2008 (n=22) | 0.2008 (n=22) | 0.2471 (n=22) | 0.2471 (n=22) |
| function_recall@5 | 0.2746 (n=22) | 0.2746 (n=22) | 0.3152 (n=22) | 0.3228 (n=22) |
| function_recall@10 | 0.4261 (n=22) | 0.4261 (n=22) | 0.3471 (n=22) | 0.3471 (n=22) |
| file_mrr | 0.5782 (n=22) | 0.5773 (n=22) | 0.6054 (n=22) | 0.6168 (n=22) |
| function_mrr | 0.4282 (n=22) | 0.4273 (n=22) | 0.4184 (n=22) | 0.4296 (n=22) |
| file_reach | 1.0000 (n=22) | 0.8598 (n=22) | 0.7235 (n=22) | 0.7614 (n=22) |
| function_reach | 1.0000 (n=22) | 0.6561 (n=22) | 0.5622 (n=22) | 0.5849 (n=22) |

### Context đóng gói (phụ)

| Metric | bm25 (full rank) | bm25@cap (diagnostic) | graph | graph+F2P |
|---|---:|---:|---:|---:|
| packed_gold_file_in_context | 0.6932 (n=22) | 0.6932 (n=22) | 0.6098 (n=22) | 0.6629 (n=22) |
| packed_gold_function_in_context | 0.4459 (n=22) | 0.4459 (n=22) | 0.4137 (n=22) | 0.4251 (n=22) |
| packed_all_gold_files_in_context | 0.4545 (n=22) | 0.4545 (n=22) | 0.4091 (n=22) | 0.4545 (n=22) |
| packed_all_gold_functions_in_context | 0.2273 (n=22) | 0.2273 (n=22) | 0.2727 (n=22) | 0.2727 (n=22) |
| context_tokens | 7997.9 (n=22) | 7997.9 (n=22) | 7966.5 (n=22) | 7904.9 (n=22) |
| packed_tokens_to_first_gold_file | 1233.2 (n=21) | 1233.2 (n=21) | 805.6 (n=18) | 788.5 (n=19) |
| packed_tokens_to_first_gold_function | 1785.9 (n=16) | 1785.9 (n=16) | 1340.9 (n=14) | 1323.5 (n=15) |
| packed_items_packed | 23.3 (n=22) | 23.3 (n=22) | 41.1 (n=22) | 38.8 (n=22) |
| packed_truncated | 1.0000 (n=22) | 1.0000 (n=22) | 0.9545 (n=22) | 0.9545 (n=22) |

### Delta theo cặp task

**graph − BM25 full rank** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 22 | +0.0114 | [-0.1553, +0.1856] | 7 / 8 / 7 |
| file_recall@5 | 22 | -0.0909 | [-0.2917, +0.1212] | 6 / 7 / 9 |
| file_recall@10 | 22 | -0.0417 | [-0.2424, +0.1591] | 7 / 8 / 7 |
| function_recall@3 | 22 | +0.0463 | [-0.1087, +0.2194] | 5 / 12 / 5 |
| function_recall@5 | 22 | +0.0406 | [-0.1568, +0.2497] | 7 / 9 / 6 |
| function_recall@10 | 22 | -0.0791 | [-0.3021, +0.1492] | 7 / 7 / 8 |
| file_mrr | 22 | +0.0272 | [-0.1511, +0.1952] | 6 / 7 / 9 |
| function_mrr | 22 | -0.0097 | [-0.1624, +0.1432] | 6 / 7 / 9 |
| packed_gold_file_in_context | 22 | -0.0833 | [-0.3258, +0.1515] | 7 / 8 / 7 |
| packed_gold_function_in_context | 22 | -0.0322 | [-0.2670, +0.2061] | 7 / 9 / 6 |
| context_tokens | 22 | -31.4 | [-68.0, -10.4] | 2 / 2 / 18 |

**graph+F2P − BM25 full rank** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 22 | +0.0114 | [-0.1553, +0.1856] | 7 / 8 / 7 |
| file_recall@5 | 22 | -0.0417 | [-0.2424, +0.1591] | 6 / 8 / 8 |
| file_recall@10 | 22 | -0.0114 | [-0.2008, +0.1818] | 7 / 9 / 6 |
| function_recall@3 | 22 | +0.0463 | [-0.1087, +0.2194] | 5 / 12 / 5 |
| function_recall@5 | 22 | +0.0482 | [-0.1518, +0.2530] | 7 / 9 / 6 |
| function_recall@10 | 22 | -0.0791 | [-0.3117, +0.1553] | 8 / 5 / 9 |
| file_mrr | 22 | +0.0386 | [-0.1370, +0.2093] | 7 / 7 / 8 |
| function_mrr | 22 | +0.0014 | [-0.1523, +0.1528] | 7 / 7 / 8 |
| packed_gold_file_in_context | 22 | -0.0303 | [-0.2500, +0.1894] | 7 / 9 / 6 |
| packed_gold_function_in_context | 22 | -0.0208 | [-0.2614, +0.2186] | 8 / 8 / 6 |
| context_tokens | 22 | -93.0 | [-250.0, -11.4] | 2 / 2 / 18 |

### Chẩn đoán Graph (quyết định hybrid vs giảm nhiễu anchors)

| Arm | Task không có anchor | Anchors/task | Unmapped (tổng) | Unmapped/task | Candidates/task |
|---|---:|---:|---:|---:|---:|
| graph | 0 | 49.8 | 4 | 0.18 | 99.1 |
| graph+F2P | 0 | 52.2 | 4 | 0.18 | 99.1 |

### Theo repo (mean File R@5 / Function R@5)

| Repo | n | bm25 (full rank) | graph | graph+F2P |
|---|---:|---:|---:|---:|
| astropy/astropy | 2 | 0.42 / 0.00 | 0.50 / 0.50 | 0.50 / 0.50 |
| django/django | 10 | 0.62 / 0.36 | 0.33 / 0.20 | 0.41 / 0.25 |
| matplotlib/matplotlib | 1 | 0.00 / 0.17 | 0.67 / 0.33 | 0.67 / 0.33 |
| pydata/xarray | 3 | 0.50 / 0.11 | 0.83 / 0.89 | 0.83 / 0.78 |
| pylint-dev/pylint | 3 | 0.33 / 0.00 | 0.25 / 0.00 | 0.33 / 0.00 |
| sphinx-doc/sphinx | 3 | 0.78 / 0.63 | 0.56 / 0.30 | 0.56 / 0.30 |

### Task cần kiểm tay (Δ = Δfile R@5 + Δfunction R@5 so với BM25 full rank)

- graph · Graph thua · `sphinx-doc__sphinx-8120` (-2.00); anchors: `sphinx.ext.doctest.DocTestBuilder.finish.s`, `sphinx.jinja2glue.idgen.current`, `sphinx.testing.fixtures.make_app.make`, `sphinx.util.osutil.cd`, `tests.roots.test-ext-autodoc.autodoc_dummy_module.test`, `sphinx.application.Sphinx`, `doc/conf.py`, `sphinx.domains.c.ASTDeclaration.clone`
- graph · Graph thua · `django__django-12325` (-1.50); anchors: `django.core.exceptions.ImproperlyConfigured`, `tests.many_to_one.models.First`, `tests.model_fields.models.Document`, `tests.model_forms.models.Document`, `tests.schema.tests.SchemaTests.test_creation_with_db_table_double_quotes.Document`, `django.db.models.fields.related.OneToOneField`, `django.db.models.options.Options.managers`, `django.setup`
- graph · Graph thua · `django__django-13195` (-1.33); anchors: `django.http.response.HttpResponseBase.delete_cookie`, `django.db.models.aggregates.Max`, `django.http.response.HttpResponseBase`, `django.utils.dateformat.DateFormat.I`, `tests.model_formsets_regress.models.Host`, `django.http.response.HttpResponseBase.set_cookie`, `django.contrib.messages.api.warning`, `django.db.models.fields.related_descriptors.ManyToManyDescriptor.through`
- graph · Graph thắng · `pydata__xarray-3993` (+1.50); anchors: `xarray.core.dataarray.DataArray.integrate`, `xarray.core.dataset.Dataset.integrate`, `xarray.core.dataarray.DataArray.differentiate`, `xarray.core.dataset.Dataset.differentiate`, `xarray.core.coordinates.Coordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.coords`
- graph · Graph thắng · `pydata__xarray-3305` (+1.50); anchors: `xarray.core.dataarray.DataArray.quantile`, `xarray.backends.common.AbstractDataStore.attrs`, `xarray.core.coordinates.AbstractCoordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.attrs`, `xarray.core.dataarray.DataArray.attrs`, `xarray.core.dataarray.DataArray.dims`
- graph · Graph thắng · `astropy__astropy-8707` (+1.50); anchors: `astropy.io.fits.card.Card.fromstring`, `astropy.io.fits.header.Header.fromfile`, `astropy.io.fits.header.Header.fromstring`, `astropy.time.core.Time.now`, `astropy.coordinates.baseframe.BaseCoordinateFrame.data`, `astropy.io.fits.hdu.base.NonstandardExtHDU.data`, `astropy.io.fits.hdu.base._BaseHDU.header`, `astropy.io.fits.hdu.base._BaseHDU.header`
- graph+F2P · Graph thua · `sphinx-doc__sphinx-8120` (-2.00); anchors: `sphinx.ext.doctest.DocTestBuilder.finish.s`, `sphinx.jinja2glue.idgen.current`, `sphinx.testing.fixtures.make_app.make`, `sphinx.util.osutil.cd`, `tests.roots.test-ext-autodoc.autodoc_dummy_module.test`, `sphinx.application.Sphinx`, `doc/conf.py`, `sphinx.domains.c.ASTDeclaration.clone`
- graph+F2P · Graph thua · `django__django-12325` (-1.50); anchors: `django.core.exceptions.ImproperlyConfigured`, `tests.invalid_models_tests.test_models.OtherModelTests`, `tests.invalid_models_tests.test_relative_fields.ComplexClashTests`, `tests.many_to_one.models.First`, `tests.model_fields.models.Document`, `tests.model_forms.models.Document`, `tests.schema.tests.SchemaTests.test_creation_with_db_table_double_quotes.Document`, `django.db.models.fields.related.OneToOneField`
- graph+F2P · Graph thua · `django__django-12741` (-1.00); anchors: `tests.backends.base.test_operations.SqlFlushTests`, `tests.backends.tests.LongNameTest`, `django.db.backends.base.operations.BaseDatabaseOperations.execute_sql_flush`, `tests.backends.base.test_operations.SqlFlushTests.test_execute_sql_flush_statements`, `tests.backends.tests.LongNameTest.test_sequence_name_length_limits_flush`, `django.core.signing.Signer.signature`, `django.test.html.Parser.current`, `django.core.management.sql.sql_flush`
- graph+F2P · Graph thắng · `pydata__xarray-3993` (+1.50); anchors: `xarray.tests.test_dataset.test_integrate`, `xarray.core.dataarray.DataArray.integrate`, `xarray.core.dataset.Dataset.integrate`, `xarray.core.dataarray.DataArray.differentiate`, `xarray.core.dataset.Dataset.differentiate`, `xarray.core.coordinates.Coordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`
- graph+F2P · Graph thắng · `pydata__xarray-3305` (+1.50); anchors: `xarray.tests.test_dataarray.TestDataArray.test_quantile`, `xarray.core.dataarray.DataArray.quantile`, `xarray.backends.common.AbstractDataStore.attrs`, `xarray.core.coordinates.AbstractCoordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.attrs`, `xarray.core.dataarray.DataArray.attrs`
- graph+F2P · Graph thắng · `astropy__astropy-8707` (+1.50); anchors: `astropy.io.fits.card.Card.fromstring`, `astropy.io.fits.header.Header.fromfile`, `astropy.io.fits.header.Header.fromstring`, `astropy.time.core.Time.now`, `astropy.coordinates.baseframe.BaseCoordinateFrame.data`, `astropy.io.fits.hdu.base.NonstandardExtHDU.data`, `astropy.io.fits.hdu.base._BaseHDU.header`, `astropy.io.fits.hdu.base._BaseHDU.header`


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
