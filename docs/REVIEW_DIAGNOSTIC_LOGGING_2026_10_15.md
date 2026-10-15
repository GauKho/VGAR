# Review diagnostics — 15/10/2026

Một fresh-context reviewer, read-only; không chạy model hoặc sửa code. So sánh
với86 baseline files ở diagnostics-preflight. Historical76/protectedVGAR4 còn nguyên.

| Finding | Mức độ theo tác động | Xử lý |
|---|---|---|
| HF4.57.6 dispatch `_sample` qua class, observer instance bị bỏ qua | Important | RED test mô phỏng class dispatch; chuyển sang instance `_get_logits_processor`, giữ args/return, khôi phục hook |
| Body hợp lệ `--- old`/`+++ new` bị nhầm là file headers, counts sai | Important | RED paired body cases; dùng boundary parser đã consume và đánh dấu ambiguous khi chưa xác định |
| Sai raw line ở header thứ2 hoặc hunk thiếu | Reviewer Minor, xử lý như Important vì đúng vị trí lỗi là yêu cầu chính task | RED line2/line3; cập nhật vị trí trước validate |

Fix observer RED: results/tests/20261015T013536417965Z-ba6ef1de23bf/run_record.json;
GREEN18: results/tests/20261015T013605840135Z-e391ac68bd6c/run_record.json.
Fix parser RED4: results/tests/20261015T013701917442Z-c416874c84cc/run_record.json;
first fix còn2fail: results/tests/20261015T013726379181Z-a2d3c1803ffa/run_record.json;
GREEN32: results/tests/20261015T013810640202Z-39ea8e309fcb/run_record.json.

Reviewer không nghiệm thu GPU/model behavior, inference quality hoặc performance;
chưa có real inference mới. Root xác nhận chỉ claim offline diagnostics tests và
đối chiếu source của pinned Transformers, không claim chữa B hoặc real qualification.
Không yêu cầu review thứ hai; fullsuite sau fixes và audit ở PROGRESS.

Bổ sung boundary SyntaxError ở quoted header: giữ nguyên exception type và thêm
location, RED tại014046447327Z-3caba67f403c -> GREEN tại014056192189Z-ecfef23a96ea.
Full suite cuối175PASS92.28s tại014057460231Z-bae22e94edc3; RuffPASS.
Offline guard comparison19cases và4rawB replay không có acceptance/message/class
khác baseline; canonical/evidence cũ không chỉnh sửa.
