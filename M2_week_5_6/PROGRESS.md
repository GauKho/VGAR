# Tiến độ M2 tuần 5–6

Plan: `docs/IMPLEMENTATION_PLAN.md`. Phạm vi được người dùng xác nhận ngày 01/10/2026.

**Checkpoint hiện tại: BM25/gold/evaluation25/docs/tests đã hoàn tất. Không code lại. Còn thiếu M1 export thật và xác nhận phối hợp M1/M3.** Xem mục “Trạng thái bàn giao cuối” bên dưới; các checkpoint trước là nhật ký lịch sử.

## Quyết định và ranh giới

- Thư mục độc lập `M2_week_5_6`; không sửa/import/chạy hệ thống trong VGAR hoặc vgar_mcp_mvp.
- Không commit/push tự động. Không tạo worktree từ repo cũ: thư mục mới chính là isolation người dùng yêu cầu. CAPSTONES không phải Git repo.
- Dùng unittest (stdlib), Python venv riêng; pyarrow chỉ cần khi tải parquet. Không cài torch, LLM, Docker.
- Gold patch chỉ dùng tạo nhãn offline; query chỉ lấy problem_statement. Không đọc gold vào ranking.
- M1 W5–6 chưa có graph retrieval trong output VGAR W3–4: adapter/evaluation được chuẩn bị; không giả kết quả Graph.
- Giữ checkpoint và mọi JSON test/run; không xóa artifacts khi kết thúc.
- Plan/spec được ghi tại đây từ kế hoạch đã duyệt trong hội thoại; không triển khai plan repair đang đóng băng của vgar_mcp_mvp.

## Milestones

- [x] M0: scope, môi trường riêng, recorder và tests RED.
- [x] M1: function/code chunking và fingerprint source.
- [x] M2: BM25 và context packing.
- [x] M3: patch → gold-file/gold-function, mapping coverage (fixtures đã pass).
- [x] M4: retrieval metrics, locked manifest, 25 SWE-bench tasks thật.
- [ ] M5: adapter/tests/docs và inspection10 đã xong; **chưa có output Graph thật/phiên phối hợp M1/M3** để hoàn tất paired comparison.

## Checkpoint

M0–M3 đã triển khai; 9 core tests PASS tại `results/tests/20261001T132118824537Z-a1041c2eebe3/result.json`. Pipeline RED lưu tại `results/tests/20261001T132250447816Z-6a9101c95d91/result.json`. Full suite lần đầu 22/23 PASS, lỗi fixture instance_id chứa `/`; đã sửa fixture, không nới path validation. Venv riêng và pyarrow 23.0.1 đã cài. Tiếp theo: chạy full suite, prepare pinned dataset, smoke/pilot rồi 25 task thật; hoàn thiện comparison/report/guide.

Pre-flight: chunks → BM25 dùng `text/chunk_id`; gold → metrics dùng canonical `path::qualified_name`; windows dedup parent trước k; ContextPayload M1 có token count tự khai báo, adapter recount bằng estimator chung; source_revision không đồng nghĩa checkout thật nên đọc Git object đã verify commit. Chưa có M1 W5–6 output để paired comparison.

01/10 checkpoint bổ sung: 28 tests PASS `results/tests/20261001T132834046133Z-4ecdaa98114d/result.json`. Dataset pin `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, 500 raw / 70 multi-file eligible / 25 selected, manifest `data/manifests/verified-c104f840cc67-25.json`. Smoke `20261001T132614642557Z-91f7f9d14f23`: astropy và django PASS; matplotlib Git fetch timeout 240s; riêng các process fetch của lần chạy này đã được dừng để giải phóng pipe, không tác động repo cũ.

Ruling: dùng source-only commit archive (GitHub codeload) thay Git fetch — bằng chứng HTTP 200 của đúng matplotlib SHA, tránh hang khi fetch pack; giá phải trả: không có cryptographic Git tree verification, bù bằng pinned URL/root/archive SHA256/corpus hash, ghi rõ provenance. RED archive tests đã lưu `results/tests/20261001T133111182135Z-cf2e7b525bd4/result.json`.

## Checkpoint sau review

- Smoke archive3: `20261001T133215660548Z-8981af35fd7b`, 3/3 SUCCEEDED.
- Pilot5: `20261001T133419928382Z-6c5cdad50f71`, 5/5, 52.09s.
- Initial25: `20261001T133709088254Z-c694a841581c`, 25/25, nhưng là code trước final review, **không dùng làm kết quả cuối**.
- Review độc lập chỉ đọc, không chạy/đụng repo khác, đã tìm 7 Important; các regression RED tại `results/tests/20261001T134120716670Z-ab8ea11e4e6e/result.json`.
- Một fix pass đã sửa physical line splitting, module-only eligibility, function definition collision, task artifact hashes/metadata ở resume, malformed M1 export isolation, complete dedup ranking trace cho tail MRR, deterministic BM25 sum. Gold hunk offset thực trong matplotlib được căn bằng context exact unique (+2 lines), không fuzzy/đoán.
- Full suite **40/40 PASS** tại `results/tests/20261001T134305016392Z-20d23783e5ab/result.json`.
- Chuẩn bị dataset và comparison được bổ sung fingerprint/duration/stdout/stderr vì là yêu cầu evidence, không chỉ polish.
- **Đang chạy final25 OFFLINE bằng code sau fix pass.** Source backend cache đã có đủ25. Tiếp theo: đọc kết quả final, compare missing-M1 explicit, inspection10 actual, update handoff status/docs và verify cuối. Không sửa production code khi chưa có lỗi cụ thể; nếu thay source phải chạy fresh run, không resume artifact cũ khác binding.

Ruling: manifest pilot stratify theo repository (round-robin) và IDs, chưa stratify difficulty/patch-size — lấy đa repo cho debug tuần 5–6; giá phải trả: không suy rộng như random representative/final blind set. Cần đồng thuận M3 manifest trước nghiên cứu final.

Ruling: hunk lệch line được relocate chỉ khi context exact khớp duy nhất (hoặc vị trí đã căn trước khớp exact), offset được ghi events — gold không bị mất vì header offset thực trong dataset; giá phải trả: hunk ambiguous bị đánh unmapped/N/A, không tự ý fuzzy match.

Final review declined-to-judge rulings: real Graph quality/paired score và human leader inspection chờ M1/người thật; Git object proof ngoài backend đã công khai; billing/LLM token không nằm trong estimator; execution reliability sẽ dựa run logs thật. Không coi bất kỳ mục này đã PASS. Không có minor code fix tự ý ngoài evidence requirements.

## Trạng thái bàn giao cuối — 01/10/2026

**Không tiếp tục các task repo cũ. Code M2 đang hoạt động; chưa cần code lại.**

| Yêu cầu New_task | Trạng thái | Bằng chứng |
|---|---|---|
| BM25 function/code chunks | Hoàn thành | chunks.py, bm25.py, core/regression tests |
| Gold-file/gold-function extraction | Hoàn thành trong policy được ghi rõ | gold_labels.py, events/coverage trong25 task artifacts |
| Evaluation ban đầu 20–30 task | Hoàn thành: 25 task thật | run cuối bên dưới |
| Phối hợp M1 debug context/gold mapping | Hạ tầng handoff sẵn; chưa hoàn thành collaboration thật | m1_adapter.py, docs/M1_M3_HANDOFF.md, m1_requests/ |
| Graph vs BM25 Recall@3/5/10 + token cost | Chưa hoàn thành vì chưa có M1 exports | AWAITING_M1, paired=0/25 |
| Inspect ≥10 task | Có10 case notes do assistant | docs/INSPECTION_10_TASKS.md; human/team confirmation chưa có |

### Kết quả chuẩn để sử dụng

- Final retrieval: `results/retrieval/20261001T134641055034Z-5295e04e781d/result.json` — **25/25 SUCCEEDED, 0 failed**, offline cache, **152.95s**. Không chạy benchmark code/agent/LLM.
- Fingerprint: `sha256:37df2c82422c1dfcd37411fbe36b95fe26f7929eeffc8afc934335f775997f15`.
- Suite **41 PASS**, verification khi viết tài liệu: `results/tests/20261001T143918867222Z-bd8d53c32643/result.json`; run trước `results/tests/20261001T135440291251Z-0d46873dde55/result.json` được giữ nguyên. Source giữ đúng fingerprint của final25.
- Dataset re-pin với filter cuối: `results/dataset/20261001T134557108756Z-d1e9786391ab/result.json`, 500 raw /70 eligible /25 fixed.
- Comparison: `results/comparison/20261001T135005639423Z-ff60c4173af5/result.json` — **AWAITING_M1**, exit2 đúng chủ đích, không Graph score giả.
- Report: `results/retrieval/20261001T134641055034Z-5295e04e781d/REPORT.md`.
- Artifact audit PASS: `results/checks/20261001T135217743162Z-b135549b9a16/result.json` — 25 task hashes/current source binding, budgets, Recall/MRR replay, gold-free M1 requests.
- Dependency check PASS: `results/checks/20261001T135228577181Z-b587af9d79b3/result.json`.
- Compile check PASS: `results/checks/20261001T135441526941Z-b8f01a8b63d4/result.json`.

BM25 macro file Recall@3/5/10 = **0.2086 / 0.3952 / 0.6152**; function Recall@3/5/10 = **0.0895 / 0.1095 / 0.1855**; eligible denominator25. Mean packed context3995.96 estimated tokens, mapping coverage1.0. File retrievability coverage mean0.99: Astropy case có1 new-only file, coverage3/4; đã báo riêng, không silent drop. Đây là ranking metrics, không phải bounded-context paired Graph metrics/repair success.

Sau inspection sửa thêm `testing/` filtering với RED→GREEN; manifest vẫn70 eligible và giữ nguyên25. Run `20261001T134352042074Z-b14408f97217` là intermediate trước thay đổi filtering, không dùng làm bảng bàn giao cuối.

### Phục hồi lần sau

1. Đọc file này và docs/M1_M3_HANDOFF.md; không rebuild lại phần BM25/gold đã xong.
2. Nếu người dùng/M1 gửi output W5–6 thật, kiểm tra sidecar, đúng25 IDs/commits/query/corpus/budget. Đặt exports trong data/m1_exports, chạy compare_m1.py đối với **run chuẩn** ở trên.
3. Cùng M1/M3 xác nhận inspection/subset, cập nhật paired table sau khi validation không lỗi. Nếu chỉ có subset exports, báo incomplete, không đánh100%.
4. Không resume run cũ khác source/config; không chỉnh VGAR/vgar_mcp_mvp, không tự push/commit.

Các edits phiên này chỉ nằm trong M2_week_5_6. Repo VGAR vẫn25 dirty paths từ trước, vgar_mcp_mvp giữ các edits/untracked cũ; không test/import/sửa source của hai repo đó. Không xóa dữ liệu/material nào; chỉ dừng các child Git fetch do smoke này tạo sau timeout, đã giữ cache và failure record.

## Checkpoint tài liệu giải thích — hoàn thiện 02/10/2026

- Đã tạo `GIAI_THICH_M2_W5_W6_VA_CACH_KIEM_THU.md`: yêu cầu tuần5–6, bảng trạng thái, vai trò từng file/folder, thuật ngữ/thuật toán, bốn luồng input → xử lý → output, ví dụ Django thật, test coverage, kết quả và hướng dẫn PowerShell có phân biệt setup lần đầu/chạy lại.
- README có link đến tài liệu mới. Không sửa src/scripts/tests/pyproject, không chạy lại evaluation25, không thay input/manifest/metrics cũ.
- Evidence suite khi viết tài liệu: `results/tests/20261001T143918867222Z-bd8d53c32643/result.json`,41 tests PASS, exit0, unittest0.706s; recorder0.927s. Phiên tiếp tục chỉ đọc lại evidence, không chạy lại phần đã hoàn thành.
- Kiểm tra tài liệu ở phiên trước:15 PowerShell code blocks parse được, không thiếu file ở các links nội bộ, không có ký tự thay thế Unicode. Kiểm tra cuối được thực hiện lại sau bổ sung link/checkpoint.
- Task tạo tài liệu giải thích đã hoàn thành; còn M1 output thật/paired comparison và xác nhận M1/M3 như mục phục hồi phía trên. Không tự chuyển sang các task chưa được yêu cầu.

## Bổ sung phạm vi bàn giao GitHub — 03/10/2026

- Theo xác nhận của người dùng, nhánh M2 được bổ sung25 gold patches, toàn bộ logs nhỏ và full artifacts của run bàn giao `20261001T134641055034Z-5295e04e781d`, gồm25 tasks/25 M1 requests.
- `.gitignore` giữ loại `.venv`, bytecode và source/download caches, nhưng không còn loại gold hoặc toàn bộ results. Task details của các runs ngoài run bàn giao vẫn không đưa trực tiếp vào Git.
- Lịch sử `results/` đầy đủ, gold và manifest được đóng gói riêng cho GitHub Releases; xem `docs/GITHUB_HANDOFF.md` để lấy ZIP/checksum. Các files local và metrics cũ giữ nguyên; không chạy lại retrieval25 hoặc sửa src/scripts/tests.
- Nhánh chỉ chứa `M2_week_5_6/` ở cấp gốc; không merge trực tiếp các commit loại file VGAR vào main.
