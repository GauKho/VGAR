# T1 — API checker theo phạm vi symbol chịu ảnh hưởng

## Phạm vi được giao

Người dùng yêu cầu thực hiện riêng T1 ngày 07/11/2026, sau chặng 3 smoke PASS.
Mục tiêu: public symbol không đổi ở chỗ khác trong file không làm toàn check
NOT_RUN. Không giảm required checks A3 hoặc biến unknown thành PASS.
Không T3/T10/chặng 4/campaign/model/Docker, không commit/push.

## Thiết kế và trình tự

- Giữ `check_api()` mặc định kiểm toàn bộ surface như trước. Bổ sung keyword
  `changed_only=False`; collector dùng `True`. Chỉ phân tích AST, không chạy code.
- So binding AST không kèm vị trí để xác định thêm/xóa/thay đổi symbol và export.
  Class constructor/header và public method là các phạm vi riêng; sửa method
  không đồng nghĩa sửa inherited constructor ở cùng class.
- Giữ unknown cho binding/decorator/export bị tác động; xét phụ thuộc binding
  cục bộ bắc cầu để không bỏ qua alias public khi private implementation đổi.
  Dynamic exports không chứng minh được phạm vi vẫn unknown.
- Evidence ghi mode, selected symbols, diagnostics nằm ngoài phạm vi được bỏ qua
  và coverage chỉ trong phạm vi patch; không tuyên bố hiểu toàn bộ runtime API.
- RED: regression bốn nguyên nhân NOT_RUN không liên quan, inherited method,
  export/removal, alias/dependency, ambiguity, syntax và collector thật.
- GREEN: implementation tối thiểu; regression API/evidence/A3/static/verifier;
  Ruff scoped, whitespace và preservation; review độc lập ở cuối.

## Điểm bắt đầu

- HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`, branch
  `m2/w12-a3-verifier-d15-20261105`, dirty T2/T4/T5/T6/T7 giữ nguyên.
- Root cause: `run_compatibility_checks` lọc changed files nhưng `_surface`
  phân tích mọi public symbol trong file, mọi diagnostic làm NOT_RUN.
- Artifact mới `results/m2/w1112/t1/20261107T063335Z/`.
- Đã lưu hashes các file có thay đổi từ trước, index/HEAD và tài liệu bảo vệ;
  chưa sửa production tại mốc này. Sandbox chặn tạo results lần đầu, đã dùng
  escalation để lưu evidence; không thay quyền filesystem.

## Trạng thái

IN_PROGRESS — chuẩn bị regression RED. T1 local chưa hoàn tất; 133 vector cũ
không được sửa hoặc kết luận đã hết NOT_RUN khi chưa có run/raw mới.

## Triển khai và review

- Thêm opt-in `changed_only` vào API checker, collector bật chế độ này. Giữ
  default full-surface và policy A0–A3/hash/schema/timeouts hiện có.
- RED đầu:29 failed do chưa có keyword và collector vẫn kiểm file đầy đủ.
  GREEN đầu còn2 lỗi (export removal bị nhận nhầm unsupported và dynamic exports
  không đổi bị PASS); sửa giữ export membership và ưu tiên unknown động.
- Gate API/collector145 PASS. Thêm A3 fixture qua verifier thật với tool I/O
  kiểm soát: body-only PASS, breaking FAIL/API_BREAK, affected unknown ERROR/incomplete.
- Review độc lập chỉ đọc `/root/t1_api_scope_review` phát hiện5 ca:
  alias public của private class; conditional siblings; lexical shadowing;
  conditional constructor guard; conditional method global trùng class attribute.
  Đã RED6 ca (3 finding đầu, gồm tham số hóa), sau đó RED2 ca cuối; sửa dependency
  theo lexical symtable, guard riêng từng binding và dependency constructor.
- `guards-green.xml`: **190 PASS** cho API scope/legacy checker/evidence/A3.
  Reviewer tái hiện độc lập xác nhận cả5 finding đã đóng; không đồng nghĩa đã
  kiểm mọi runtime API hoặc133 vector thật. Ruff `--no-cache` PASS.
- Regression lượt trước reviewfix:788 PASS/166,33s. Lượt sau3 finding đầu:
  795 PASS/159,43s. Gate acceptance đang chạy trên bản cuối sau đủ5 finding;
  không dùng lượt cũ làm kết luận code cuối.
- Không sửa sealed codecopy/inputs/results của chặng2/3. Không WSL/Docker/model
  hoặc gold/campaign trong T1. T3 chưa được xử lý; dừng sau khi chốt local evidence.

## Kết thúc — DONE kỹ thuật local

- Gate cuối `acceptance.xml`: **797 PASS,0 fail/error/skip,164,27s**. Gate bao
  gồm toàn bộ `tests/m2/w1112`, A3/evidence/verifier integration, policy/fairness,
  static diagnostics/baseline delta/static tools. Không chạy Docker/model hoặc
  suite ngoài dependency liên quan chỉ để tăng số test.
- Reviewer xác nhận đóng đủ5 finding bằng repro độc lập trên code cuối; vẫn
  không tuyên bố blanket coverage. Scoped gate190 PASS và Ruff/whitespace PASS.
- Artifact `results/m2/w1112/t1/20261107T063335Z/` có `commands.json`, log/JUnit
  mọi lượt, `synthetic_examples.json` (không phải real campaign), `review.json`,
  source fingerprints, preservation và artifact checksums. Helper đóng evidence
  ở TEMP, không thêm production tool ngoài phạm vi T1.
- Mốc nghiệm thu là local code/fixture; không khẳng định133 vector thật đã được
  sửa hoặc A3 accept rate tăng. Linux copy của chặng2/3 vẫn là phiên bản cũ đã
  seal; chỉ cập nhật khi được giao chặng4 rồi kiểm byte hash/freeze/regression.
- **Điểm tiếp theo:** xử lý T3 hoặc có giới hạn được nhóm chấp nhận; sau đó giao
  chặng4 riêng. Không tự chạy T3/T10/chặng4/A3 batch, commit hoặc push.
