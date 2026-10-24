# Review M2-W9-3 — 24/10/2026

Một reviewer fresh-context, read-only (`final_m2_w9_3_review`, gpt-6-astra/high),
không dispatch reviewer khác hoặc ghi files. Không đổi HEAD/index/branch.
Phạm vi admission/bridge mới; không review lại các task M1/M2 đã hoàn thành.

## Findings và xử lý

- Critical: không có.
- Important R1: Git replacement refs có thể thay tree của pinned commit trong
  admission; config non-Python đổi nhưng profile Python inventory vẫn khớp.
  Target base_identity/reset cũng cần cùng bảo vệ `git --no-replace-objects`.
  Root đồng ý Important vì phá exact-base contract. Hai regressions đã tái hiện
  đúng finding: `review_r1_red.json` **2 FAIL**, không thay refs của repo thật.
  Sau khi smoke04 kết thúc, đã thêm `git --no-replace-objects` vào host reads
  và target reset/identity. `review_r1_green.json`: **2 PASS**; final full W78/W9
  **317 PASS**, 0 FAIL/ERROR/SKIP/exclusion (`full_w78_w9_final.json`, 371,876 giây).
  Một fix pass hoàn tất; root xác nhận R1 resolved, không có review vòng hai.
- Minor: draft từng ghi V9 có sẵn. Đã sửa lịch sử: smoke03 bị preflight chặn vì
  chỉ đăng ký V11; smoke04 dùng V11 với handoff source-only đủ dòng, consumer PASS.

Reviewer kiểm focused30PASS, full315PASS và lint; chưa xác nhận smoke04 lúc review.
Các boundary còn lại được đánh giá coherent: external pins, image identity,
protected overlay, fixed argv/report paths, target syntax, incomplete-output và
cleanup fail-closed; native fixture guard giữ nguyên.

## Declined to judge và ruling

- Smoke04 runtime còn chạy: root phải đọc terminal artifacts/audit trước closure.
- Malicious target reporter authenticity: nằm ngoài guarantee đã công khai;
  container isolation/source consistency không tạo cryptographic attestation.
- Model/retrieval performance, đủ năm task runnable, M3/MCP integration và thay
  đổi từ task trước: ngoài M2-W9-3; root đồng ý không tự thêm thành acceptance gate.

Đây là review kỹ thuật độc lập, không là phê duyệt nhóm/M1/M3 hoặc benchmark/model
qualification. Một fix pass cho Important, RED→GREEN và regression; không re-review.
Smoke04 canonical PASS và audit độc lập 14 operations PASS, baseline FAIL/PASS →
post PASS/PASS. Wrapper chỉ lỗi summary sau canonical publish; giữ raw lỗi,
khôi phục summary riêng. Smoke05 trên source freeze sau fix: canonical/wrapper PASS, audit độc lập
14operations/cleanup PASS, original source unchanged, không owned containers.
Full317PASS và audit cuối xác nhận đủ gates; root chốt hoàn thành kỹ thuật.
