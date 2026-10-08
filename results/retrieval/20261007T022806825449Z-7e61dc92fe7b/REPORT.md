# Kết quả retrieval M2 tuần 5–6

Run: `20261005T082810770056Z-7a3ad261d8e4`; dataset: `princeton-nlp/SWE-bench_Verified` @ `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
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

Comparison status: **COMPARED_PARTIAL**; paired tasks: 19/25.

| Run | Attempted | Succeeded | Failed/Error | NOT_RUN |
|---|---:|---:|---:|---:|
| bm25 | 25 | 25 | 0 | 0 |
| graph | 25 | 19 | 6 | 0 |

Các mean dưới đây chỉ dùng paired successes; không coi tasks lỗi là successes hoặc bỏ denominator của chúng khỏi coverage.

Primary: BM25 full rank và Graph ranking đã lưu; Graph max_candidates = 100. Số reach phải đọc cùng giới hạn candidate universe, không coi hai ranking có cùng độ dài.

`graph` là issue-only; `graph+F2P` là **oracle-assisted** dùng test IDs FAIL_TO_PASS từ benchmark metadata, không phải failing tests đã được quan sát khi chạy base environment. Không gộp hai arm khi claim fairness.

### Rank đầy đủ (chính)

| Metric | bm25 (full rank) | graph | graph+F2P (oracle-assisted) |
|---|---:|---:|---:|
| file_recall@3 | 0.3640 (n=19) | 0.1754 (n=19) | 0.1754 (n=19) |
| file_recall@5 | 0.5439 (n=19) | 0.2412 (n=19) | 0.2412 (n=19) |
| file_recall@10 | 0.6184 (n=19) | 0.3509 (n=19) | 0.3509 (n=19) |
| function_recall@3 | 0.2193 (n=19) | 0.0877 (n=19) | 0.0877 (n=19) |
| function_recall@5 | 0.2982 (n=19) | 0.0877 (n=19) | 0.0877 (n=19) |
| function_recall@10 | 0.4421 (n=19) | 0.1140 (n=19) | 0.1140 (n=19) |
| file_mrr | 0.5888 (n=19) | 0.3023 (n=19) | 0.3017 (n=19) |
| function_mrr | 0.4334 (n=19) | 0.1944 (n=19) | 0.1944 (n=19) |
| file_reach | 1.0000 (n=19) | 0.5307 (n=19) | 0.5307 (n=19) |
| function_reach | 1.0000 (n=19) | 0.2632 (n=19) | 0.2632 (n=19) |

### Context đóng gói (phụ)

| Metric | bm25 (full rank) | graph | graph+F2P (oracle-assisted) |
|---|---:|---:|---:|
| packed_gold_file_in_context | 0.6711 (n=19) | 0.5132 (n=19) | 0.5132 (n=19) |
| packed_gold_function_in_context | 0.4690 (n=19) | 0.2316 (n=19) | 0.2140 (n=19) |
| packed_all_gold_files_in_context | 0.4211 (n=19) | 0.3684 (n=19) | 0.3684 (n=19) |
| packed_all_gold_functions_in_context | 0.2632 (n=19) | 0.1053 (n=19) | 0.1053 (n=19) |
| context_tokens | 7997.7 (n=19) | 7142.2 (n=19) | 7126.1 (n=19) |
| packed_tokens_to_first_gold_file | 1298.9 (n=18) | 1402.4 (n=14) | 1439.5 (n=14) |
| packed_tokens_to_first_gold_function | 1781.6 (n=14) | 2022.2 (n=8) | 1754.9 (n=7) |
| packed_items_packed | 23.2 (n=19) | 56.1 (n=19) | 54.4 (n=19) |
| packed_truncated | 1.0000 (n=19) | 0.5263 (n=19) | 0.4737 (n=19) |

### Delta theo cặp task

**graph − bm25 (full rank)** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 19 | -0.1886 | [-0.3333, -0.0351] | 2 / 7 / 10 |
| file_recall@5 | 19 | -0.3026 | [-0.5088, -0.0921] | 4 / 2 / 13 |
| file_recall@10 | 19 | -0.2675 | [-0.4518, -0.0702] | 3 / 4 / 12 |
| function_recall@3 | 19 | -0.1316 | [-0.2474, -0.0211] | 1 / 10 / 8 |
| function_recall@5 | 19 | -0.2105 | [-0.3596, -0.0702] | 1 / 8 / 10 |
| function_recall@10 | 19 | -0.3281 | [-0.5439, -0.1123] | 1 / 6 / 12 |
| file_mrr | 19 | -0.2865 | [-0.4433, -0.1397] | 2 / 4 / 13 |
| function_mrr | 19 | -0.2391 | [-0.4206, -0.0457] | 1 / 2 / 16 |
| packed_gold_file_in_context | 19 | -0.1579 | [-0.3860, +0.0877] | 4 / 6 / 9 |
| packed_gold_function_in_context | 19 | -0.2374 | [-0.4584, -0.0228] | 2 / 7 / 10 |
| context_tokens | 19 | -855.5 | [-1663.3, -275.9] | 1 / 1 / 17 |

**graph+F2P (oracle-assisted) − bm25 (full rank)** (cùng task, bootstrap 95% CI của mean delta)

| Metric | n | Mean Δ | 95% CI | Thắng / Hòa / Thua |
|---|---:|---:|---|---:|
| file_recall@3 | 19 | -0.1886 | [-0.3333, -0.0351] | 2 / 7 / 10 |
| file_recall@5 | 19 | -0.3026 | [-0.5088, -0.0921] | 4 / 2 / 13 |
| file_recall@10 | 19 | -0.2675 | [-0.4518, -0.0702] | 3 / 4 / 12 |
| function_recall@3 | 19 | -0.1316 | [-0.2474, -0.0211] | 1 / 10 / 8 |
| function_recall@5 | 19 | -0.2105 | [-0.3596, -0.0702] | 1 / 8 / 10 |
| function_recall@10 | 19 | -0.3281 | [-0.5439, -0.1123] | 1 / 6 / 12 |
| file_mrr | 19 | -0.2871 | [-0.4438, -0.1402] | 2 / 4 / 13 |
| function_mrr | 19 | -0.2391 | [-0.4206, -0.0457] | 1 / 2 / 16 |
| packed_gold_file_in_context | 19 | -0.1579 | [-0.3860, +0.0877] | 4 / 6 / 9 |
| packed_gold_function_in_context | 19 | -0.2549 | [-0.4772, -0.0397] | 2 / 7 / 10 |
| context_tokens | 19 | -871.6 | [-1685.7, -293.4] | 2 / 2 / 15 |

### Chẩn đoán Graph (quyết định hybrid vs giảm nhiễu anchors)

| Arm | Task không có anchor | Anchors/task | Unmapped (tổng) | Unmapped/task | Candidates/task |
|---|---:|---:|---:|---:|---:|
| graph | 0 | 78.6 | 0 | 0.00 | 79.3 |
| graph+F2P (oracle-assisted) | 0 | 80.4 | 0 | 0.00 | 77.8 |

### Theo repo (mean File R@5 / Function R@5)

| Repo | n | bm25 (full rank) | graph | graph+F2P (oracle-assisted) |
|---|---:|---:|---:|---:|
| astropy/astropy | 2 | 0.42 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| django/django | 8 | 0.65 / 0.41 | 0.17 / 0.15 | 0.17 / 0.15 |
| matplotlib/matplotlib | 1 | 0.00 / 0.17 | 0.00 / 0.00 | 0.00 / 0.00 |
| pydata/xarray | 3 | 0.50 / 0.11 | 1.00 / 0.17 | 1.00 / 0.17 |
| pylint-dev/pylint | 2 | 0.25 / 0.00 | 0.12 / 0.00 | 0.12 / 0.00 |
| sphinx-doc/sphinx | 3 | 0.78 / 0.63 | 0.00 / 0.00 | 0.00 / 0.00 |

### Task cần kiểm tay (Δ = Δfile R@5 + Δfunction R@5 so với bm25 (full rank))

- graph · Graph thua · `sphinx-doc__sphinx-8120` (-2.00); anchors: `sphinx.application.Sphinx`, `sphinx.domains.index.IndexDomain.entries`, `sphinx.ext.doctest.DocTestBuilder.finish.s`, `sphinx.jinja2glue.idgen.current`, `sphinx.search.IndexBuilder.label`, `sphinx.testing.fixtures.make_app.make`, `sphinx.util.i18n.CatalogRepository.locale_dirs`, `sphinx.util.osutil.cd`
- graph · Graph thua · `django__django-12325` (-1.50); anchors: `django.core.exceptions.ImproperlyConfigured`, `django.db.models.options.Options.managers`, `tests.many_to_one.models.First`, `django.setup`, `django.contrib.admin.views.autocomplete.AutocompleteJsonView.get`, `django.contrib.gis.gdal.feature.Feature.get`, `django.contrib.gis.gdal.raster.source.GDALRaster.origin`, `django.contrib.sessions.backends.base.SessionBase.get`
- graph · Graph thua · `sphinx-doc__sphinx-8548` (-1.50); anchors: `sphinx.locale._TranslationProxy.data`, `sphinx.builders.linkcheck.CheckExternalLinksBuilder.check_thread.check`, `tests.test_domain_c.check`, `tests.test_domain_cpp.check`, `tests.test_domain_cpp.test_build_domain_cpp_with_add_function_parentheses_is_False.check`, `tests.test_domain_cpp.test_build_domain_cpp_with_add_function_parentheses_is_True.check`, `tests.test_domain_cpp.test_xref_parsing.check`
- graph · Graph thắng · `pydata__xarray-3993` (+1.00); anchors: `xarray.core.coordinates.Coordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.coords`, `xarray.core.dataarray.DataArray.differentiate`, `xarray.core.dataarray.DataArray.dims`, `xarray.core.dataarray.DataArray.dims`, `xarray.core.dataarray.DataArray.integrate`
- graph · Graph thắng · `pydata__xarray-3305` (+0.50); anchors: `xarray.backends.rasterio_._parse_envi.default`, `xarray.backends.common.AbstractDataStore.attrs`, `xarray.backends.locks.CombinedLock.release`, `xarray.backends.locks.DummyLock.release`, `xarray.core.coordinates.AbstractCoordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.attrs`
- graph · Graph thắng · `pylint-dev__pylint-4551` (+0.25); anchors: `pylint.checkers.format.TokenWrapper.type`, `pylint.config.option_manager_mixin.OptionsManagerMixIn.help`, `tests.functional.i.invalid.invalid_name.a`, `tests.functional.u.useless.useless_super_delegation.Base.something`, `pylint.checkers.base.BasicChecker.__init__`, `pylint.checkers.base.NameChecker.__init__`, `pylint.checkers.base_checker.BaseChecker.__init__`, `pylint.checkers.classes.ClassChecker.__init__`
- graph+F2P (oracle-assisted) · Graph thua · `sphinx-doc__sphinx-8120` (-2.00); anchors: `sphinx.application.Sphinx`, `sphinx.domains.index.IndexDomain.entries`, `sphinx.ext.doctest.DocTestBuilder.finish.s`, `sphinx.jinja2glue.idgen.current`, `sphinx.search.IndexBuilder.label`, `sphinx.testing.fixtures.make_app.make`, `sphinx.util.i18n.CatalogRepository.locale_dirs`, `sphinx.util.osutil.cd`
- graph+F2P (oracle-assisted) · Graph thua · `django__django-12325` (-1.50); anchors: `django.core.exceptions.ImproperlyConfigured`, `django.db.models.options.Options.managers`, `tests.many_to_one.models.First`, `django.setup`, `django.contrib.admin.views.autocomplete.AutocompleteJsonView.get`, `django.contrib.gis.gdal.feature.Feature.get`, `django.contrib.gis.gdal.raster.source.GDALRaster.origin`, `django.contrib.sessions.backends.base.SessionBase.get`
- graph+F2P (oracle-assisted) · Graph thua · `sphinx-doc__sphinx-8548` (-1.50); anchors: `sphinx.locale._TranslationProxy.data`, `sphinx.builders.linkcheck.CheckExternalLinksBuilder.check_thread.check`, `tests.test_domain_c.check`, `tests.test_domain_cpp.check`, `tests.test_domain_cpp.test_build_domain_cpp_with_add_function_parentheses_is_False.check`, `tests.test_domain_cpp.test_build_domain_cpp_with_add_function_parentheses_is_True.check`, `tests.test_domain_cpp.test_xref_parsing.check`
- graph+F2P (oracle-assisted) · Graph thắng · `pydata__xarray-3993` (+1.00); anchors: `xarray.tests.test_dataset.test_integrate`, `xarray.core.coordinates.Coordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`, `xarray.core.dataarray.DataArray.coords`, `xarray.core.dataarray.DataArray.differentiate`, `xarray.core.dataarray.DataArray.dims`, `xarray.core.dataarray.DataArray.dims`
- graph+F2P (oracle-assisted) · Graph thắng · `pydata__xarray-3305` (+0.50); anchors: `xarray.tests.test_dataarray.TestDataArray.test_quantile`, `xarray.backends.rasterio_._parse_envi.default`, `xarray.backends.common.AbstractDataStore.attrs`, `xarray.backends.locks.CombinedLock.release`, `xarray.backends.locks.DummyLock.release`, `xarray.core.coordinates.AbstractCoordinates.dims`, `xarray.core.coordinates.DataArrayCoordinates.dims`, `xarray.core.coordinates.DatasetCoordinates.dims`
- graph+F2P (oracle-assisted) · Graph thắng · `pylint-dev__pylint-4551` (+0.25); anchors: `tests.unittest_pyreverse_writer.test_dot_files`, `tests.unittest_pyreverse_writer.test_get_visibility`, `pylint.checkers.format.TokenWrapper.type`, `pylint.config.option_manager_mixin.OptionsManagerMixIn.help`, `tests.functional.i.invalid.invalid_name.a`, `tests.functional.u.useless.useless_super_delegation.Base.something`, `pylint.checkers.base.BasicChecker.__init__`, `pylint.checkers.base.NameChecker.__init__`


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
