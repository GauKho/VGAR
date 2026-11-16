# TV2 · GA-2 phần còn lại: Connector và ExternalSystem (17/11/2026)

> Plan 2 tuần, task GA-2 ([P] dòng 251–270). Phần đã làm: `docs/superpowers/specs/2026-11-09-tv2-ga-g-arch-design.md`.
> Luật dưới đây là **quyết định của nhóm, chốt 16/11**. Proposal chỉ nêu tên hai loại node (dòng 254, 258), không định nghĩa cách sinh.

## 1. Luật sinh

Tĩnh và tất định; chỉ dùng node và cạnh `G_repo` đã có; chỉ xét file thuộc một Component (file test không thuộc Component nên bị bỏ qua).

| Node hoặc cạnh | Luật | Confidence |
|---|---|---|
| **ExternalSystem** | Mỗi tên gốc (phần trước dấu `.` đầu tiên) của module mà một Component import (cạnh `IMPORTS` tới Module `is_external`), loại bỏ: thư viện chuẩn (`sys.stdlib_module_names`), tên gốc của module trong repo, tên không phải identifier. Id `vgar:<repo>:python:external_system:<tên>` | — |
| `DEPENDS_ON` Component → ExternalSystem | Một cạnh cho mỗi cặp; `import_count` = số câu import; evidence = id các cạnh `IMPORTS` | 0.9, heuristic |
| **Connector** | Lời gọi (`CallSite`) mà `callee_text` resolve qua bảng import của file ra một thư viện giao tiếp đã biết. Mỗi cặp (Component, loại) sinh một node. Id `vgar:<repo>:python:connector:<component key>:<loại>` | — |
| `COMMUNICATES_WITH` Component → Connector | Một cạnh cho mỗi Connector; `call_count` | 0.8, heuristic |
| `COMMUNICATES_WITH` Connector → ExternalSystem | Một cạnh cho mỗi thư viện của Connector có node ExternalSystem (thư viện chuẩn như `subprocess`, `sqlite3` không có) | 0.8, heuristic |

Thư viện giao tiếp và loại:

| Loại | Thư viện |
|---|---|
| `http` | `requests`, `httpx`, `aiohttp`, `urllib`, `urllib3`, `http` |
| `database` | `sqlite3`, `sqlalchemy`, `psycopg`, `psycopg2`, `pymysql`, `pymongo` |
| `queue_cache` | `redis`, `pika`, `kafka`, `aiokafka` |
| `process` | `subprocess` |

## 2. Schema

- Thêm cặp: `DEPENDS_ON` (Component, ExternalSystem); `COMMUNICATES_WITH` (Component, Connector), (Connector, ExternalSystem). Dùng lại tên cạnh của proposal, không thêm tên mới.
- Thuộc tính bắt buộc: Connector `kind`, `owner_component_id`; ExternalSystem `import_name`.
- `SCHEMA_VERSION` lên `vgar-schema-full-v6`; `arch_lift.RULE_VERSION` lên `arch-lift-v2`.

## 3. Ảnh hưởng tới phần khác

- Impact: không đổi, vì ExternalSystem không bao giờ là component bị sửa.
- Retrieval: không đổi, vì chỉ đọc `DEPENDS_ON` giữa hai Component.
- Resource `vgar://component/{id}`: `dependencies`/`dependents` chỉ lấy Component, để giữ nghĩa cũ.

## 4. Giới hạn

- ExternalSystem là **thư viện bên thứ ba**, không phải hệ thống ở xa thật (máy chủ HTTP, DB cụ thể). Static analysis không biết URL hay chuỗi kết nối lúc chạy.
- Connector chỉ nhận lời gọi resolve được qua import; gọi qua biến (`session.get` với `session = requests.Session()`) không được tính.
- Danh sách thư viện giao tiếp là cố định, không đầy đủ.
