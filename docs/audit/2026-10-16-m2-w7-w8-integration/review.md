# Review độc lập và xử lý — 16/10/2026

Reviewer: fresh context `review_m2_vgar_integration_20261016`, read-only, không
đổi code/Git hoặc chạy lại suite. Đối chiếu package-level integration theo plan;
không đánh giá MCP như chức năng được yêu cầu.

## Kết luận

- Critical:0.
- Important:1 — explicit relative Python/SavedRoot đổi nghĩa sau nested chdir.
  Đã tái hiện trước fix: command `20261016T070857760064Z-bf5301c48832`, exit1,
  underlying child exit2. Root launcher normalize Python/SavedRoot/OutputRoot
  theo caller PowerShell location; GREEN7tests/8.98s command
  `20261016T071003225820Z-424ac56f6133`.
- Minor wording: guard description chưa nhắc b_inputs adapter. Đã cập nhật
  đúng trong lượt hoàn thiện tài liệu, không thêm behavior/code cho prose.
- Full VGAR sau fix review:571PASS/2SKIP/1knownFAIL81.14s. Known HF failure vẫn
  được báo; không dùng số tests M2 để gọi toàn VGAR PASS.

## Reviewer đã kiểm

- Sáu current/backed-up hashes khớp relocation receipt.
- Default launcher, CLI và HF worker prepend embedded source, không MCP.
- Historical paths chỉ rebase trong memory; phân biệt r002 old/integration hashes.
- Giữ output boundaries/no-overwrite/reparse checks; tách pytest/venv.

## Những phần reviewer không tự nghiệm thu và quyết định của implementer

| Nội dung | Quyết định/evidence |
|---|---|
| Fresh real model | Không chạy/không claim; Check, ReadSaved, fake được ghi riêng |
| Full-core/preservation cuối | Implementer kiểm receipts:236PASS; final preservation zero mismatches |
| Known HF failure | Tồn tại trước integration; giữ nguyên ngoài scope, báo rõ trong handoff |
| MCP/LangChain | Ngoài phương án người dùng đã chọn |
| Portable venv/bare imports | Ngoài scope; docs cảnh báo editable .pth cũ; chỉ supported launcher/scripts dùng embedded source |
| Toàn vendor/generated corpus | Reviewer đọc receipt, implementer SHA từng file13071 trước/sau |

Không dispatch re-review hoặc lặp inference. User chưa yêu cầu commit/push;
HEAD giữ nguyên và source M2 độc lập không đổi.
