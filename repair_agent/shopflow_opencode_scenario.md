# Kịch bản prompt: OpenCode + VGAR MCP trên ShopFlow clean (bản 3, 22/11/2026)

Repo: `D:\kltn\shopflow-clean\shopflow` (package `shopflow/`; 17 lỗi B01–B17; không README, không docstring/comment, không
test). Đáp án và bộ test ẩn 105 case: `D:\kltn\shopflow-clean-ground-truth.zip` (`bugs.json`, `hidden_tests/`,
`reference_fixed/`) — không để lọt vào thư mục repo.

Bản 3 dùng server sau đợt 3: các tool kiểm **không cần truyền diff** (server tự so thư mục làm việc với code mà graph đã
lưu), không cần `git stash`, commit là tuỳ chọn. Lịch sử: bản 2 (repo `shopflow-buggy-no-tests`, phải stash) nằm trong git.

## Bước 0: Cài MCP (PowerShell, một lần)

```powershell
$py   = "D:\kltn\vgar_mcp_mvp_demo\.venv\Scripts\python.exe"
$repo = "D:\kltn\shopflow-clean\shopflow"          # thư mục CHA của package shopflow/
$data = "D:\kltn\vgar-work\data\shopflow-clean"
Set-Location $repo
New-Item -ItemType Directory -Force $data | Out-Null

git init                                            # bỏ qua nếu đã là git repo
git config core.autocrlf false
Add-Content .git\info\exclude "opencode.json`n__pycache__/"
git add -A; git commit -m "shopflow clean (17 bugs)"

opencode.cmd mcp add vgar-graph `
  --env PYTHONUTF8=1 --env VGAR_GRAPH_BACKEND=sqlite `
  --env VGAR_REPOSITORY_ROOT=$repo --env VGAR_GRAPH_DATABASE=$data\graph.db `
  --env VGAR_MCP_AUDIT_LOG=$data\graph.jsonl `
  -- $py -m vgar.mcp.servers.graph_server
opencode.cmd mcp add vgar-execution `
  --env PYTHONUTF8=1 --env VGAR_GRAPH_BACKEND=sqlite `
  --env VGAR_REPOSITORY_ROOT=$repo --env VGAR_GRAPH_DATABASE=$data\graph.db `
  --env VGAR_MCP_AUDIT_LOG=$data\execution.jsonl `
  -- $py -m vgar.mcp.servers.execution_server
opencode.cmd mcp add vgar-repository `
  --env PYTHONUTF8=1 --env VGAR_LEASE_ROOT=$repo `
  --env VGAR_MCP_AUDIT_LOG=$data\repository.jsonl `
  -- $py -m vgar.mcp.servers.repository_server

# Tắt Code Mode, tăng timeout (ghi KHÔNG BOM; có BOM thì OpenCode bỏ qua file)
$cfg = Get-Content "$repo\opencode.json" -Raw | ConvertFrom-Json
foreach ($n in "vgar-graph","vgar-execution","vgar-repository") {
  $cfg.mcp.servers.$n | Add-Member -NotePropertyName codemode -NotePropertyValue $false -Force }
$cfg.mcp | Add-Member -NotePropertyName timeout -NotePropertyValue ([pscustomobject]@{ execution = 900000 }) -Force
[IO.File]::WriteAllText("$repo\opencode.json", ($cfg | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding($false)))

opencode.cmd mcp list    # cả 3 server phải "connected"
opencode.cmd             # phiên MỚI, MỘT mô hình cố định (không dùng combo)
```

Mỗi lượt đo: nhánh mới từ commit gốc (`git switch -c <tên> <commit gốc>`), phiên OpenCode mới, cùng mô hình. Ghi lại ID
phiên, mô hình, commit của `vgar_mcp_mvp_demo`. Graph dựng trước đợt 3 chưa lưu code gốc: gọi `build_or_update_graph` một
lần trước khi kiểm.

## Bước 1: Hiểu repo

```text
Dùng các tool của vgar-graph. Gọi build_or_update_graph cho repo này, rồi tóm tắt kiến trúc: các component, luồng đặt
đơn từ API -> service -> repository, và module nào phụ thuộc module nào. Chỉ đọc, chưa sửa gì.
```

## Bước 2: Rà lỗi (chưa sửa)

```text
Repo này không có test và không có tài liệu. Đặc tả nghiệp vụ là:
- Tiền tệ dùng Decimal, làm tròn ROUND_HALF_UP đến 2 chữ số.
- Chiết khấu hạng khách + coupon kết hợp kiểu nhân dồn, tối đa 50%. Coupon trong config.COUPONS lưu theo phần trăm.
- Miễn phí ship khi giá trị sau chiết khấu >= 100; thuế 10% chỉ tính trên tiền hàng sau chiết khấu, không tính trên phí ship.
- Đặt đơn giữ chỗ (reserve) hàng; mọi lỗi khi đặt đơn phải nhả lại toàn bộ chỗ đã giữ.
- Trạng thái: pending -> confirmed -> shipped; pending/confirmed -> cancelled. shipped và cancelled là trạng thái cuối.
- Ngày giao dự kiến tính theo ngày làm việc (thứ 2 - thứ 6).
Với TỪNG quy tắc: gọi find_task_anchors với nguyên câu quy tắc; nếu không có anchor thì gọi search_symbols với từ khoá;
gọi get_related_context từ các anchor (không gọi với danh sách rỗng); lần theo get_callers/get_callees nếu logic qua
nhiều file (explain_dependency_path: source là nơi GỌI, target là hàm BỊ GỌI); đọc các file liên quan.
Ngoài đặc tả, tìm cả chỗ code mâu thuẫn với chính nó giữa các file: gọi sai thứ tự tham số, dùng thuộc tính không tồn
tại, dữ liệu lưu một kiểu nhưng đọc kiểu khác, so sánh biên sai, phân trang, mã lỗi HTTP.
Liệt kê: file:dòng, triệu chứng người dùng thấy, lỗi có liên quan nhiều file không. Xét đủ mọi module trong shopflow/,
cuối cùng liệt kê các module đã xét. Không lặp một lỗi ở nhiều dòng. CHƯA sửa code.
```

## Bước 3: Sửa từng lỗi (một lỗi một lượt)

```text
<MÔ TẢ LỖI>
Làm theo thứ tự, không tạo file mới trong repo:
1. find_task_anchors với mô tả lỗi; nếu không có anchor thì dùng search_symbols để tìm hàm liên quan.
2. get_related_context từ các anchor; lần theo get_callers / get_callees nếu lỗi đi qua nhiều file.
   (explain_dependency_path: source là nơi GỌI, target là hàm BỊ GỌI.)
3. Đọc các file graph chọn. Tái hiện lỗi bằng `python -c` dùng shopflow.app.build_app.
4. Sửa tối thiểu nhưng đúng đặc tả, rồi chạy lại đoạn tái hiện.
5. Gọi analyze_patch_impact và verify_patch_graph_constraints, KHÔNG truyền diff (server tự so thư mục làm việc với
   code của graph). Báo nguyên văn kết quả, kể cả checked_diff.not_checked. Nếu tool báo lỗi thì coi như CHƯA kiểm.
6. Gọi build_or_update_graph (commit là tuỳ chọn).
7. Báo: nguyên nhân, file:dòng đã sửa, kết quả từng bước kiểm (đã kiểm hay chưa kiểm được).
```

Thứ tự gợi ý: lỗi 3 trước (làm nhiễu các lần tái hiện khác), rồi 1, 2, 4, 5, 6, sau đó các lỗi còn lại.

| # | Mã lỗi | `<MÔ TẢ LỖI>` |
|---|---|---|
| 1 | B03 + B08 | Khách C003 đặt 1 MOU-2001 với coupon WELCOME10 thì luôn báo "discount rate out of range". Sau lỗi đó, số hàng "reserved" của MOU-2001 tăng lên dù không có đơn nào được tạo. |
| 2 | B16 + B11 | Khách C003 (hạng standard) đặt 2 KEY-1001 (159.80 USD, 2.4 kg). Báo giá ra phí ship 244.70 và thuế tính cả trên phí ship. Đúng ra phải miễn ship, thuế 15.98, tổng 175.78. |
| 3 | B04 | Alice (C001) đặt 1 MOU-2001, sau đó Bob (C002) đặt 1 CAB-4001. Đơn của Bob lại chứa cả dòng MOU-2001 của Alice, và subtotal cộng luôn tiền của đơn kia. |
| 4 | B09 + B17 | Đặt 2 HUB-5001, xác nhận, rồi gọi POST /orders/<id>/ship thì nhận 500 "internal error". Dù báo lỗi, đơn vẫn chuyển sang shipped và tồn kho đã bị trừ; sau đó "available" của HUB-5001 ra số âm. |
| 5 | B13 | Huỷ được một đơn đã ở trạng thái shipped, và việc huỷ còn cộng trả lại hàng vào kho. |
| 6 | B06 | HUB-5001 còn 3 cái. Đơn thứ nhất đặt 2 cái thành công; đơn thứ hai đặt thêm 2 cái cũng thành công, nên tổng giữ chỗ vượt tồn kho. |
| 7 | B07 | Với build_app(today=lambda: date(2026, 11, 20)) (thứ 6), giao một đơn: ngày giao dự kiến ra 2026-11-26, sớm hơn một ngày, như thể thứ 7 là ngày làm việc. |
| 8 | B02 | Giá 2.675 được làm tròn thành 2.67, trong khi phải là 2.68 (ROUND_HALF_UP). |
| 9 | B10 | Có 2 đơn confirmed (tổng 100 và 50) và 1 đơn pending. average_order_value trả 50, đáng lẽ phải là 75. |
| 10 | B01 | GET /products?page=1&size=2 chỉ trả 1 sản phẩm. |
| 11 | B12 | GET /products/XYZ-9999 (SKU không tồn tại) trả 500, đáng lẽ phải là 404. |
| 12 | B05 | CAB-4001 còn khả dụng đúng 5 cái (bằng ngưỡng LOW_STOCK_THRESHOLD = 5) nhưng không có trong danh sách tồn kho thấp. Sản phẩm bằng ngưỡng cũng phải được liệt kê. |
| 13 | B15 | Tìm khách bằng email "ALICE@EXAMPLE.COM" (viết hoa) thì không thấy Alice. |
| 14 | B14 | Đăng ký khách với email hợp lệ "user+tag@example.com" bị báo "invalid email". |

## Bước 4–5: Kiểm lại cuối và báo cáo

```text
Chạy lại tất cả các đoạn tái hiện đã dùng, mỗi đoạn một lệnh `python -c` riêng, báo kết quả từng đoạn. Sau đó viết bảng:
lỗi -> nguyên nhân -> file:dòng đã sửa -> bằng chứng (tái hiện trước/sau, kết quả analyze_patch_impact và
verify_patch_graph_constraints ghi nguyên văn) -> phần chưa kiểm được.
```

## Nhánh đối chứng không có VGAR

`git switch -c agent-run-nomcp <commit gốc>`, đặt `"disabled": true` cho cả ba server, phiên mới với **cùng mô hình**,
cùng prompt nhưng bỏ các câu nhắc tool `vgar-*` và bỏ mục 5 của Bước 3.

## Chấm

Chép `reference_fixed/` ra thư mục tạm, thay vào đó các file agent đã sửa (mỗi file chỉ chứa lỗi agent đã nhận), chép
`hidden_tests/` thành `tests/`, chạy pytest: 105/105 PASS nghĩa là các bản sửa đúng và không làm hỏng gì khác trong các
file đó. Tổng số FAIL trên toàn repo bị nhiễu bởi các lỗi chưa sửa (nhất là B04).
