# ADR — Inventory, rollback và identity của Python definitions

Ngày: 06/10/2026. Phạm vi: sửa tích hợp tuần 3–6, milestone 2.
Trạng thái: đã triển khai và kiểm thử kỹ thuật; **chưa có sign-off của owner M1/M2**. Không thay cho phê duyệt của nhóm.

## Vấn đề

File extraction lỗi đã bị xóa khỏi nodes nhưng còn trong cây source. Retriever so file set với File nodes khiến mọi retrieval của task thất bại. Symbol/call/class/scope phụ trợ cũng còn trỏ vào nodes đã bị rollback. Các định nghĩa cùng qualified name làm mất cả file vì ID trùng; nhánh `if/try` không được duyệt. Inheritance resolve sau khi class mới ghi đè binding gây self-loop sai.

## Quyết định

1. `statistics.source_inventory` là map path tương đối → SHA256 **raw bytes** của toàn bộ Python files đã discover, kể cả file extraction thất bại. Không thêm node giả cho file đó. Retriever kiểm toàn bộ file set và hash; File node phải khớp inventory. Graph cũ không có inventory vẫn dùng File nodes và kiểm hash như trước. Graph cũ có failed files phải rebuild để có inventory đầy đủ.
2. Toàn bộ extraction, kể cả scope indexing, nằm trong transaction của một file. Rollback các list nodes/edges/calls/classes, indexes, scope tables/location/parent, module binding và counters. Journal chỉ giữ binding có thể bị ghi đè của module, không deepcopy toàn graph cho từng file. Inventory vẫn giữ file lỗi và diagnostics vẫn ghi failed file.
3. Compound blocks không tạo lexical scope mới. Duyệt `if/elif/else`, `try/except/else/finally`, `for/while/with/match`, nhưng không vào thân definition hai lần.
4. Definition đầu giữ ID cũ. Definition trùng ID được thêm `@definition:<start_byte>:<end_byte>`; qualified name giữ nguyên, range/content hash đúng từng occurrence. Property setter vẫn dùng hậu tố `.setter` đã có. Suffix theo span xác định trong cùng snapshot, không cam kết ổn định qua mọi lần chỉnh file. Đây không phải GraphDiff/incremental identity.
5. M2 adapter tiếp tục dùng qualified name **và range** để map từng occurrence sang canonical function ID của AST corpus. Không đổi gold, Recall denominator hoặc scorer để tăng số đẹp. Test thật tại `tests/test_graph_transaction_bindings.py` kiểm distinct M1 IDs và distinct M2 function IDs.
6. Scope lookup cho calls dùng node ID và symtable location (qualified name + definition line), không dùng table của occurrence cuối cho mọi definition cùng tên. Các qualified names có nhiều definitions không được coi là một symbol duy nhất chắc chắn; nếu thiếu execution proof thì calls giữ unresolved. Không suy luận nhánh runtime đã chạy.
7. Class bases dùng bản binding **trước** khi gán class name: local definition IDs tại điểm khai báo và explicit imports. Import sau một definition phải rebind namespace. Import target chưa resolve, dynamic bases hoặc ambiguous definitions được ghi `statistics.unresolved_bases`; không tạo self-loop, không nới schema validator. Không hỗ trợ full dynamic runtime semantics/data flow.
8. Setter chỉ nhận AST attribute có terminal `.setter`; `@app.get(...)`, `@pytest.mark.parametrize(...)`, deleter và `.setter()` không phải setter rule này.

Builder resolver profile đổi từ `lexical-v2` sang `transaction-bindings-v3`, làm graph_version khác để không dùng lẫn graph cũ. Tính toàn vẹn graph cache/file-meta pair sẽ xử lý tại milestone 5; không xóa cache cũ hàng loạt.

## Bằng chứng và giới hạn

- RED: `artifacts/fixes/w3-w6/20261006T143045093388Z-c60497ad17fc/result.json` — 18 failed, 6 passed trước sửa.
- Binding order RED: `artifacts/fixes/w3-w6/20261006T143426412508Z-1bddf4f92a82/result.json` — import sau class resolve sai trước sửa bổ sung.
- Targeted: `artifacts/fixes/w3-w6/20261006T143342652531Z-1b1e51eca99a/result.json` — 113 passed (trước thêm regression import order cuối).
- Full suite sau sửa cuối: `artifacts/fixes/w3-w6/20261006T143502696933Z-6cb5ab8fc972/result.json` — **262 passed, 1 skipped**, exit 0.

Chưa chạy dev25 hoặc đo cải thiện retrieval benchmark ở milestone này. Không thay frozen ContextPayload, vocabulary/status hay public schema version. M1/M2 cần review ADR/occurrence mapping khi bàn giao; agent không tự ghi đã được nhóm phê duyệt.
