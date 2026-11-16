# TV2 · GA-2 phần còn lại: chạy thật Connector và ExternalSystem (17/11/2026)

> Spec: `docs/superpowers/specs/2026-11-17-tv2-ga-2-connector-external-design.md` (luật do nhóm chốt 16/11).
> Phần GA-1/GA-2 trước đó: `tv2_ga_g_arch_run_2026-11-09.md`.

**Kết quả: ĐẠT.** Hai loại node còn thiếu của `G_arch` đã có luật sinh; GA-2 đóng.

## Thay đổi

| File | Thay đổi |
|---|---|
| `src/vgar/graph/arch_lift.py` | `_lift_external`: ExternalSystem, Connector, `DEPENDS_ON` Component → ExternalSystem, `COMMUNICATES_WITH` Component → Connector → ExternalSystem. `RULE_VERSION` lên `arch-lift-v2`. Báo cáo `statistics.arch` thêm `external_system_count`, `connector_count` |
| `src/vgar/contracts/schema.py` | 3 cặp cạnh mới, thuộc tính bắt buộc của 2 node, bỏ khỏi danh sách "chưa có producer"; `SCHEMA_VERSION` lên `vgar-schema-full-v6` |
| `src/vgar/graph/sqlite_service.py` | Resource `vgar://component/{id}`: `dependencies` chỉ lấy Component (không lẫn thư viện) |
| `tests/test_arch_lift.py` | 6 test mới, 1 test schema sửa; 3 test khác chỉ đổi số phiên bản schema |

## Hai lỗi phát hiện nhờ chạy thật (đã sửa, có test)

1. **Package lồng trong thư mục con bị coi là ExternalSystem.** Khi build từ thư mục cha (`vgar-demo-shop/shop`), module trong repo tên `vgar-demo-shop.shop.*` nhưng code import `shop`. Sửa: tên nằm ở bất kỳ cấp nào của module trong repo đều tính là nội bộ.
2. **Module chuẩn của Python 2 bị coi là ExternalSystem.** `StringIO`, `cPickle`, `httplib`, `urllib2`, `__builtin__`… nằm sau `try/except ImportError`; `sys.stdlib_module_names` chỉ có Python 3. Thêm danh sách loại trừ cố định (kèm `_typeshed`, chỉ dùng khi type-check).

## Chạy trên 12 repo SWE-bench (base commit của bộ dev, WSL, build mặc định không bật layer)

Mọi graph qua `validate_graph_document`.

| Repo | Build (s) | Component | ExternalSystem | Connector | `DEPENDS_ON` → ExternalSystem | Connector → ExternalSystem | Loại Connector |
|---|---|---|---|---|---|---|---|
| astropy | 28,2 | 66 | 16 | 10 | 78 | 0 | http 7, process 3 |
| django | 37,2 | 172 | 11 | 30 | 21 | 3 | http 19, process 7, database 4 |
| matplotlib | 15,8 | 18 | 18 | 5 | 30 | 0 | process 4, http 1 |
| seaborn | 6,9 | 6 | 10 | 1 | 21 | 0 | http 1 |
| flask | 1,0 | 5 | 7 | 2 | 10 | 0 | database 1, http 1 |
| requests | 1,1 | 7 | 5 | 1 | 5 | 0 | http 1 |
| xarray | 8,5 | 7 | 16 | 2 | 25 | 0 | process 1, http 1 |
| pylint | 4,9 | 13 | 6 | 2 | 12 | 0 | process 2 |
| pytest | 4,7 | 14 | 9 | 1 | 16 | 0 | process 1 |
| scikit-learn | 14,4 | 28 | 5 | 2 | 55 | 0 | http 2 |
| sphinx | 11,0 | 24 | 19 | 8 | 26 | 0 | http 5, process 3 |
| sympy | 57,2 | 69 | 7 | 2 | 22 | 0 | process 2 |
| **Tổng** | | **429** | **129** | **66** | **321** | **3** | |

Ví dụ ExternalSystem: django → `psycopg2`, `MySQLdb`, `cx_Oracle`, `sqlparse`, `pytz`, `yaml`; flask → `werkzeug`, `jinja2`, `click`, `itsdangerous`, `blinker`; xarray → `dask`, `netCDF4`, `h5netcdf`, `scipy`.
Ba cạnh Connector → ExternalSystem đều ở django (connector `database` → `psycopg2`).

Repo demo: `vgar-demo-shop` 0/0 (không có thư viện ngoài, đúng); `shopflow-clean` 0 ExternalSystem, 1 Connector `http` (`urllib`).

## Test

- `tests/test_arch_lift.py`: 48 passed, 1 skipped (6 test mới).
- Toàn bộ suite (bỏ marker `hf`, `docker`): 3.381 passed, 27 skipped, 1 xfailed, 4 failed. Sau đó sửa `test_schema_contract` (danh sách "chưa có producer" cũ còn Connector, ExternalSystem), chạy lại nhóm schema/arch/service/MCP: 697 passed, 1 skipped. Ba fail còn lại không liên quan:
  - `test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`: fail đã biết từ trước.
  - `test_tv2_removed_stack.py::test_verification_tools_survive` và `m3/test_manifest.py::test_pilot_experiment_id_is_unchanged_by_w10_fields`: băm byte của file; worktree mới checkout với `core.autocrlf=true` nên file thành CRLF. Bỏ `\r` thì hash khớp đúng giá trị mong đợi.
- `ruff check` trên các file đã sửa: sạch, trừ 3 cảnh báo import có sẵn ở `sqlite_service.py`.

## Nhận xét

- Hầu hết Connector là `http` qua `urllib` (thường là `urllib.parse`, xử lý URL chứ không gọi mạng) và `process` qua `subprocess`. Thư viện chuẩn không có node ExternalSystem, nên chỉ 3/66 Connector nối tới ExternalSystem.
- ExternalSystem gồm cả dependency tùy chọn và dependency lúc test (`pytest`, `IPython`) nếu code nguồn import chúng.
- Hai cạnh mới không đi vào impact hay retrieval (spec §3), nên số R1 không đổi.

## Giới hạn

- ExternalSystem là thư viện bên thứ ba, không phải hệ thống ở xa thật; static analysis không biết URL hay chuỗi kết nối.
- Connector chỉ tính lời gọi resolve được qua import. `urllib.parse.quote` cũng bị tính là `http`.
- Danh sách thư viện giao tiếp và danh sách loại trừ Python 2 là cố định, không đầy đủ.
- Chưa có nhãn tay nên chưa đo precision/recall của hai loại node này.

## Tái tạo

```
# WSL, tại ~/rt1
PYTHONPATH=<repo>/src ~/.vgar-wsl/bin/python scripts/ga2_connector_external_run.py ~/rt1/data/repositories/trees/* > ga2_run.json
```
Script: `scripts/ga2_connector_external_run.py`. Kết quả gốc: `~/rt1/ga2_run.json` (WSL).
