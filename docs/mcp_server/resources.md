# L6-3 — Resource serving và tương thích legacy

Ngày làm việc: **09/11/2026 (Asia/Saigon)**. Artifact run ID dùng UTC: `results/mcp_server/resources/20261108T173125Z-serving/`.

## Phạm vi và mức sẵn sàng

Graph server đăng ký **8 canonical resources + 1 alias legacy**, gồm 4 static resources và 5 templates. Tools vẫn 20; prompt vẫn 0. L6-3 không tạo schema/graph/component/task hoặc thuật toán provider mới.

| URI | Nội dung / dependency |
|---|---|
| `vgar://repo/summary` | Raw RepositorySummaryResult của backend hiện có; giữ legacy shape. |
| `vgar://repo/schema` | Schema provider; **WAITING_PROVIDER** trong bootstrap production mặc định. |
| `vgar://graph/node/{node_id}` | Raw GraphNodeRef `{repo: ...}`; không tự chuyển thành rich document. |
| `vgar://graph/subgraph/{node_id}?k=2` | Bounded GraphSubgraphResult, cần trusted context và snapshot đã pin. |
| `vgar://component/{component_id}` | Public component/Lift view; **WAITING_PROVIDER**. |
| `vgar://task/{task_id}` | Task/trace view đúng bound task; **WAITING_PROVIDER**. |
| `vgar://evidence/baseline` | Public baseline view và evidence refs/hash đúng run/task; **WAITING_PROVIDER**. |
| `vgar://audit/log` | Audit reader có giới hạn, cần bound context và đúng log của run/task/snapshot. |

Alias `vgar://graph/subgraph/{node_id}` giữ depth 2; không tính thành resource canonical thứ chín. Ba URI legacy tiếp tục chạy theo service/config cũ khi chưa cấu hình context. Khi host đã cấu hình factory hoặc scope, cả legacy reads cũng phải kiểm source/snapshot; SQLite phải pin `requested_graph_version`/`VGAR_GRAPH_VERSION`, không tự lấy latest.

Đăng ký resource không đồng nghĩa provider production đã hoàn thành. Default registry chưa có resource schema/component/task/baseline. Resource canonical subgraph và audit là **sẵn sàng khi host bind đủ context/backend/log**; không tự cấp context hoặc authorization từ URI/model.

## Routing và kiểu dữ liệu

`proposal/resources.py` nhận URI gốc, tách query trước và percent-decode ID **một lần** bằng UTF-8 strict. SDK1 và SDK2 có template matcher/decoding khác nhau; `create_resource_server()` dùng public `read_resource()` override để không phụ thuộc matcher của SDK. Không patch package đã cài. `create_server()` và ba server còn lại giữ API/hành vi.

- `quote("fixture:a/b:π", safe="")` dùng cho ID chứa slash/colon/Unicode.
- `%252F` trở thành literal `%2F`, không trở thành `/` ở lần giải mã tiếp theo.
- ID chỉ được chuyển cho graph/provider lookup; không trở thành path filesystem.
- Subgraph chấp nhận duy nhất query `k=2`; không có query là alias cũ. Query trùng/khác, fragment, percent escape hỏng, empty ID hoặc query run/task/path không được hỗ trợ đều bị từ chối.
- `vgar://audit/log?cursor=N` là địa chỉ trang tiếp theo của cùng canonical audit resource; N phải là số nguyên không âm và đúng byte boundary trong log đã bind. Không thêm canonical resource hoặc template thứ mười cho pagination.

Nội dung resource là JSON string, **không dùng tool envelope**. MIME giữ `text/plain` như default decorators/legacy wire; client dùng JSON parser để đọc body. Không đổi legacy summary/node/subgraph content sang wrapper khác.

Resource mới dùng frozen DTO `ResourceRequest`/`ResourceResult`, `extra='forbid'`. Result có binding snapshot/source/config/task/run, resource kind/ID, JSON payload, availability/reasons và evidence refs. JSON payload phải là object hữu hạn, không duplicate key; không chấp nhận JSON rỗng như bằng chứng provider hoạt động.

Public payload mới được bổ sung trường `_resource` chứa binding, availability/reasons và evidence refs/hash; provider không được tự chiếm trường này. `PARTIAL` phải có reason. `UNAVAILABLE`/thiếu capability trả protocol error rõ, không trả thành công rỗng. Error data dùng các mã VGAR hiện có; không thêm error-code namespace tùy tiện.

## Trusted bootstrap và bảo vệ dữ liệu

Resource capabilities trong immutable ProviderRegistry: `resource_schema`, `resource_component`, `resource_task`, `resource_baseline`; mỗi capability dùng `snapshot_resource(request, context)`. Host cung cấp provider, binding và context factory trước khi serving; không nhận class/module/root/snapshot từ URI. Tham khảo cách cấu hình CoreTools trong [tools runbook](tools.md).

Mọi resource mới bắt buộc BoundContext hợp lệ. Reader kiểm source/deadline trước và sau, provider/result binding phải khớp toàn bộ snapshot/source/config/task/run. Task ID khác bound task bị từ chối trước provider call. Baseline cần evidence file thực trong output root và SHA-256 đúng; không quét latest hoặc tự đọc nguyên session/run record.

Redaction áp dụng lên **toàn bộ public document**, gồm `_resource.reasons` và metadata. Secret/control fields, env/session/run record/generation/gold/test patch/oracle không được trả raw. Nếu redaction làm thay đổi binding hoặc evidence reference, reader trả ERROR thay vì công bố một reference giả không còn trỏ artifact thực.

Provider/validation exceptions được chuẩn hóa và scrub khi trusted context còn tồn tại; lỗi protocol sau khi thread/scope đã kết thúc không được làm lộ opaque secrets. Lỗi legacy unbound giữ class/code và read behavior hiện có.

Giới hạn ordinary JSON tối đa **65.536 UTF-8 bytes** hoặc host limit thấp hơn; URI tối đa 2.048 ký tự. Subgraph depth 2, node cap tối đa 200 hoặc host cap thấp hơn; host cho dưới 2 hops thì từ chối query thay vì âm thầm đổi depth. Cap không phải chứng minh graph đã được duyệt toàn bộ. Vượt cap trả lỗi, không cắt JSON gây hỏng payload.

Đây là synchronous bounded read contract. SDK wrapper offload read-only adapter sang worker thread nhưng **await completion**, không abandon thread rồi tuyên bố cancellation đã dừng công việc. Provider phải thực hiện read có giới hạn; CPU/blocking job nặng cần guarded worker lifecycle của L6-5, không được giấu thành resource read. L6-3 không cung cấp hard-kill sandbox cho plugin Python cùng tài khoản.

## Audit và pagination

Audit chỉ đọc `ctx.output_root/audit.jsonl`, không nhận log path do model chọn. Phải đúng run/task/snapshot. Trần resource page là **256 KiB serialized UTF-8 JSON và 200 records**, ngay cả khi host cấu hình cao hơn; host đặt thấp hơn vẫn được tôn trọng.

`read_audit(ctx, cursor=0, *, output_bytes=None)` mở rộng tương thích: caller cũ không truyền output_bytes giữ default behavior. Resource reader đo serialized candidate page trước khi advance cursor. Record chưa được trả không làm cursor tiến; không bỏ hoặc lặp record vì chạm cap. Record/header không thể vừa một trang thì trả lỗi rõ.

Mỗi lời gọi reader có một terminal `resource_read`; known context có request/run/task/snapshot correlation. Malformed URI bị từ chối trước khi context factory chạy chỉ ghi hashed URI label và lỗi, không giả correlation chưa được cấp. Audit failure/incomplete tail/oversized record không được đổi thành success. Audit read có thể tạo thêm một event về chính lần đọc; `truncated` phản ánh kích thước log tại lúc đọc trang.

## Chạy lại gate và xem bằng chứng

```powershell
$sdk2 = 'D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
vgar index <repo> --db <graph>.db   # dựng graph thật (backend demo đã bỏ)
$env:VGAR_GRAPH_BACKEND = 'sqlite'; $env:VGAR_GRAPH_DATABASE = '<graph>.db'; $env:VGAR_REPOSITORY_ROOT = '<repo>'
$env:PYTHONPATH = "$PWD\src"
& $sdk2 -B -m pytest tests/mcp_server/test_resources.py tests/mcp_server/test_resource_wire.py -q -p no:cacheprovider --basetemp "$env:TEMP\vg-l63-user-01"
```

Luôn dùng temp mới. Wire tests dùng SDK2 official client với server SDK2 modern/legacy và SDK1 legacy. Fixture được đánh dấu synthetic; không thay provider production hoặc nghiệm thu thí nghiệm bằng fixture. SQLite tests chỉ dùng DB temp copy, prewarm trước khi chụp read hash; tracked DB và source không đổi.

Artifact lưu log/XML, commands, public synthetic receipts, schema/URI inventory, independent technical review, preservation và checksums. Helper runtime checker giữ historical scope label L6-1 nhưng đã kiểm inventory resources mới; provider-positive resource reads có wire fixture riêng. Không sửa oracle H1 hoặc seal L6-1/L6-2/L6-5.

**Điểm dừng:** DONE kỹ thuật resource serving khi final gate/preservation PASS. Production capabilities còn thiếu vẫn WAITING_PROVIDER. Không tự chuyển L6-4/L6-6/L6-7 hoặc chạy model/Docker/campaign.
