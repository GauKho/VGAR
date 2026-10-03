# Kế hoạch triển khai đã được duyệt — M2 Week 5–6

Nguồn yêu cầu: `../New_task/project_plan_16_weeks.md`, mục tuần 5–6; contract freeze của New_task; yêu cầu triển khai thư mục độc lập. Không thay public contract M1/M3 và không thêm schema_version.

## M0 — Setup và ghi nhận

Tạo package tối giản, venv riêng, test runner ghi JSON duy nhất mỗi lần, lưu stdout/stderr/exit/duration/hash/config. Giữ mọi thay đổi repo khác. RED: test thiếu implementation phải fail; GREEN: recorder bắt được exit và timeout.

## M1 — Chunks

AST Python chỉ đọc source tại base_commit. Function/method/test/nested functions + module code fallback; chia function dài thành windows nhưng giữ parent ID để dedup metrics. UTF-8 source range theo byte columns, qualified name, content hash. Loại test/docs khỏi corpus chính; lưu parse failures, không âm thầm bỏ. M1 adapter nhận export thay vì import VGAR. Fixtures: decorator, nested, class method, Unicode, syntax error.

## M2 — BM25

Tokenizer snake/camel/path, lowercase deterministic; BM25 k1=1.2, b=0.75, positive log1p Robertson IDF. Inverted index; zero hits trả rỗng, không score giả. Packing cùng budget/token policy, không cắt source tùy tiện. Token estimate là UTF-8 bytes/4, ghi rõ không phải tokenizer LLM thực.

## M3 — Gold labels

Unified diff old/new paths và hunks; old-side deletion/update → source function/module; additions → insertion boundary, new-only function/file có disposition riêng. Phân biệt top-level edit với function, decorator/signature, nested ownership, rename/delete. File/function labels là changed-code proxy, không chứng minh root cause. Mapping không rõ không được gán bừa; báo coverage và denominator.

## M4 — Dataset và evaluation

Pin HF dataset revision; developer patches dùng offline. Chọn deterministic 25 multi-file Python task, stratify round-robin repository trước khi retrieval, ghi manifest/query hashes. Ưu tiên manifest chung M3 nếu cung cấp; manifest tự chọn là pilot provisional. Tải/cached source snapshot tuần tự dưới folder mới, xác thực commit theo backend/provenance công khai ở quyết định dưới đây. Không checkout hoặc thực thi code benchmark trong bản cuối.

Đo file/function Recall@1/3/5/10/20, MRR, all-gold file coverage, mapping eligibility, token estimate, retrieval/index latency, errors. Dedup file/function trước top-k. Mỗi run lưu ranked chunks, context, labels, fingerprint và metrics per task; failure không silent drop. Chạy smoke rồi pilot/25 thực, không claim benchmark repair.

Quyết định triển khai sau smoke: Git fetch matplotlib timeout 240s trong khi GitHub codeload trả 200 nhanh. Dùng commit archive thay bare Git fetch: URL SHA cố định + root tar chứa đúng SHA + SHA256 archive + source fingerprint. Đọc stream .py, không extract/execute. Đây là xác thực nguồn HTTP/SHA/root, không tuyên bố đã kiểm chứng Git object hash. Bare caches từ smoke cũ giữ nguyên, không tái sử dụng hoặc xóa.

## M5 — M1 handoff

Validate real ContextPayload export: graph_version, anchors, paths/ranges/snippets/scores/confidence/token budget. Join bằng repo/base_commit/query hash + function span/name, không fixture IDs. Recount tokens bằng policy chung. Graph vs BM25 paired Recall@3/5/10 và context cost chỉ khi outputs thật đầy đủ. Inspection 10 cases có notes/evidence; checklist cho M1/M3.

## Gate hoàn tất

BM25/gold/20–30 task có bằng chứng thật; ≥10 inspections; M1 comparison phải có export thật. Nếu thiếu M1, báo rõ phần chưa hoàn thành, không gọi toàn bộ Week 5–6 100%. Không train/LLM/repair/Docker trong task retrieval này.
