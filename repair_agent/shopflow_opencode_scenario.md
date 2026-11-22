# Kịch bản prompt: OpenCode + VGAR MCP trên repo ShopFlow (bản 2, 22/11/2026)

Repo: `D:\kltn\shopflow-buggy-no-tests\shopflow-buggy-no-tests` (không có test, 13 lỗi cài sẵn).
Bảng đáp án để chấm: `shopflow_answer_key.md` (không dán vào prompt).

Bản 2 sửa theo phân tích phiên `ses_e009bef39ffeXxSzCK452yqpSW`: kiểm diff khi file còn giống code mà graph đang giữ,
tức sau `git stash` và trước khi dựng lại graph (đã chạy thử 22/11: file đã sửa tại chỗ → cả hai tool báo lỗi; sau
`git stash` → analyze OK, verify PASS; sau khi dựng lại graph → diff không áp được nữa), truyền nguyên văn `git diff` (mô hình chép tay làm mất dòng ngữ
cảnh chỉ có một dấu cách), báo nguyên văn lỗi của tool thay vì kết luận thay, không tạo file trong repo, commit mốc sau
mỗi lỗi, chiều của `explain_dependency_path`, và dùng `search_symbols` khi `find_task_anchors` không có anchor.

## Bước 0: Chuẩn bị (PowerShell, một lần)

```powershell
Set-Location "D:\kltn\shopflow-buggy-no-tests\shopflow-buggy-no-tests"
$repo = (Get-Location).Path
# Không để thư mục khác lọt vào repo (graph sẽ index cả nó):
if (Test-Path .\vgar-demo-shop) { Move-Item .\vgar-demo-shop D:\kltn\vgar-work\vgar-demo-shop-from-shopflow }

# Tắt Code Mode và tăng timeout (ghi file KHÔNG BOM; có BOM thì OpenCode bỏ qua cấu hình):
$cfg = Get-Content "$repo\opencode.json" -Raw | ConvertFrom-Json
foreach ($n in "vgar-graph","vgar-execution","vgar-repository") {
  $cfg.mcp.servers.$n | Add-Member -NotePropertyName codemode -NotePropertyValue $false -Force }
$cfg.mcp | Add-Member -NotePropertyName timeout -NotePropertyValue ([pscustomobject]@{ execution = 900000 }) -Force
[System.IO.File]::WriteAllText("$repo\opencode.json", ($cfg | ConvertTo-Json -Depth 10), (New-Object System.Text.UTF8Encoding($false)))

Add-Content .git\info\exclude "opencode.json"
# Giữ kết quả lượt trước trên nhánh của nó (nếu còn thay đổi chưa commit), rồi tạo nhánh mới từ code gốc (main):
git add -A; git commit -m "agent-run-1: ket qua luot truoc"
git switch -c agent-run-2 main
opencode.cmd mcp list              # cả 3 server phải "connected"
opencode.cmd
```

Ghi lại cho mỗi lượt chạy: ID phiên OpenCode, mô hình, phiên bản server VGAR (commit của `vgar_mcp_mvp_demo`, và đã
áp đợt sửa server nào). Lượt trước và sau khi sửa server không so trực tiếp được.

## Bước 1: Hiểu repo

```text
Dùng các tool của vgar-graph. Gọi build_or_update_graph cho repo này, rồi tóm tắt kiến trúc: các component, luồng đặt
đơn từ API -> service -> repository, và module nào phụ thuộc module nào. Chỉ đọc, chưa sửa gì.
```

## Bước 2: Rà lỗi (chưa sửa)

```text
Repo này không có test. README có mục "Quy tắc nghiệp vụ chính". Với TỪNG quy tắc:
- gọi find_task_anchors, truyền nguyên câu quy tắc làm issue_text; nếu không có anchor, gọi search_symbols với các từ
  khoá của quy tắc để tìm hàm liên quan;
- gọi get_related_context từ các anchor (không gọi với danh sách anchor rỗng); nếu logic đi qua nhiều file thì lần theo
  bằng get_callers, get_callees; với explain_dependency_path, source là nơi GỌI và target là hàm BỊ GỌI;
- đọc các file liên quan.
Liệt kê mọi chỗ code vi phạm quy tắc hoặc trái với docstring/comment của chính nó: file:dòng, triệu chứng người dùng sẽ
thấy, lỗi có liên quan nhiều file không. Xét đủ mọi module trong shopflow/ và cuối cùng liệt kê các module đã xét.
Xếp theo mức nghiêm trọng, không lặp một lỗi ở nhiều dòng. CHƯA sửa code.
```

```text
Rà tiếp các phần README không nói tới: api/handlers.py (mã lỗi HTTP), repositories, notifications, reporting, utils.
Cùng định dạng, chưa sửa code.
```

## Bước 3: Sửa từng lỗi (một lỗi một lượt)

Không sửa nhiều lỗi trong một diff: các tool kiểm chỉ nhận diff tối đa 5 file / 500 dòng, và sau mỗi lần dựng lại
graph thì diff phải chỉ chứa thay đổi mới. Thứ tự gợi ý: lỗi 3 trước (nó làm nhiễu mọi lần tái hiện khác), rồi 1, 2,
4 (gộp được với 6), 5, sau đó 7–13.

```text
<MÔ TẢ LỖI>
Làm theo thứ tự, không tạo file mới trong repo:
1. find_task_anchors với mô tả lỗi; nếu không có anchor thì dùng search_symbols để tìm hàm liên quan.
2. get_related_context từ các anchor; lần theo get_callers / get_callees nếu lỗi đi qua nhiều file.
   (explain_dependency_path: source là nơi GỌI, target là hàm BỊ GỌI.)
3. Đọc các file graph chọn. Tái hiện lỗi bằng `python -c` dùng shopflow.app.build_app.
4. Sửa tối thiểu nhưng đúng quy tắc trong README, rồi chạy lại đoạn tái hiện.
5. Chạy `git diff` và giữ nguyên văn kết quả. Chạy `git stash` (đưa file về đúng code mà graph đang giữ; các tool kiểm
   báo lỗi nếu file đã bị sửa), truyền NGUYÊN VĂN diff đó vào analyze_patch_impact và verify_patch_graph_constraints,
   rồi chạy `git stash pop` để lấy lại bản sửa. Nếu tool báo lỗi thì báo nguyên văn lỗi đó và coi như CHƯA kiểm; không
   được kết luận thay.
6. Gọi build_or_update_graph, rồi `git commit -am "fix: <tên lỗi>"` để lần sau diff chỉ có thay đổi mới.
7. Báo: nguyên nhân, file:dòng đã sửa, kết quả từng bước kiểm (đã kiểm hay chưa kiểm được).
```

| # | `<MÔ TẢ LỖI>` |
|---|---|
| 1 | Khách C003 đặt 1 MOU-2001 với coupon WELCOME10 thì luôn báo "discount rate out of range". Sau lỗi đó, số hàng "reserved" của MOU-2001 tăng lên dù không có đơn nào được tạo. |
| 2 | Khách C003 (hạng standard) đặt 2 KEY-1001 (159.80 USD, 2.4 kg). Báo giá ra phí ship 244.70 và thuế tính cả trên phí ship. Theo README, đơn này phải được miễn ship, thuế 15.98, tổng 175.78. |
| 3 | Alice (C001) đặt 1 MOU-2001, sau đó Bob (C002) đặt 1 CAB-4001. Đơn của Bob lại chứa cả dòng MOU-2001 của Alice, và subtotal cộng luôn tiền của đơn kia. |
| 4 | Đặt 2 HUB-5001, xác nhận, rồi gọi POST /orders/<id>/ship thì nhận 500 "internal error". Dù báo lỗi, đơn vẫn chuyển sang shipped và tồn kho đã bị trừ; sau đó "available" của HUB-5001 còn ra số âm. |
| 5 | Huỷ được một đơn đã ở trạng thái shipped, và việc huỷ còn cộng trả lại hàng vào kho. README nói shipped là trạng thái cuối. |
| 6 | HUB-5001 còn 3 cái. Đơn thứ nhất đặt 2 cái thành công; đơn thứ hai đặt thêm 2 cái cũng thành công, nên tổng số giữ chỗ vượt tồn kho. |
| 7 | Với build_app(today=lambda: date(2026, 11, 20)) (thứ 6), giao một đơn: ngày giao dự kiến ra 2026-11-26, sớm hơn một ngày, như thể thứ 7 được tính là ngày làm việc. |
| 8 | Giá 2.675 được làm tròn thành 2.67, trong khi README quy định ROUND_HALF_UP (phải là 2.68). |
| 9 | Có 2 đơn confirmed (tổng 100 và 50) và 1 đơn pending. average_order_value trả 50, đáng lẽ phải là 75. |
| 10 | GET /products?page=1&size=2 chỉ trả 1 sản phẩm. |
| 11 | GET /products/XYZ-9999 (SKU không tồn tại) trả 500, đáng lẽ phải là 404. |
| 12 | Sản phẩm còn khả dụng đúng 5 cái không hiện trong danh sách tồn kho thấp, dù docstring ghi "<= threshold". |
| 13 | Tìm khách bằng email "ALICE@EXAMPLE.COM" (viết hoa) thì không thấy Alice. |

Các số ở lỗi 1, 2, 7, 8, 10, 11 đã được kiểm bằng chạy code gốc (22/11).

## Bước 4: Kiểm lại cuối

Không kiểm graph trên diff tổng: graph đã được dựng lại sau mỗi lỗi, và diff tổng thường quá 5 file.

```text
Chạy lại tất cả các đoạn tái hiện đã dùng ở các lỗi trước, mỗi đoạn một lệnh `python -c` riêng, và báo kết quả từng
đoạn. Liệt kê các commit sửa lỗi (`git log --oneline`) và các file mỗi commit đã đổi.
```

## Bước 5: Báo cáo bằng chứng

```text
Viết báo cáo cuối dạng bảng: lỗi -> nguyên nhân -> file:dòng đã sửa -> bằng chứng (đoạn tái hiện trước/sau, kết quả
analyze_patch_impact và verify_patch_graph_constraints ghi nguyên văn) -> rủi ro còn lại. Ghi rõ phần nào đã kiểm thật,
phần nào chưa kiểm được (tool báo lỗi, hoặc repo không có test).
```

## So sánh A/B (tuỳ chọn)

Chạy đúng các prompt trên một nhánh mới từ code gốc, với `"disabled": true` cho cả ba server và bỏ các câu nhắc tool
`vgar-*`. So: số lỗi tìm và sửa đúng (theo bảng đáp án), số file đọc, số lượt, thời gian, token.
