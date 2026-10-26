# M2 tuần 9 — Nhật ký đề xuất và quyết định cần review

Lập ngày 21/10/2026; cập nhật xử lý review M3 ngày 22/10/2026; baseline `525f9936a3c0abe5ea056c532c1f889ce84627a7`.

**Tài liệu ban đầu lập ở M2-W9-0; bổ sung W9-1 và W9-2 theo từng yêu cầu riêng.** Ngày 22/10 đã xử lý [review M3](reviews/2026-10-22-m2-w9-0-m3-review-resolution.md): D2 chấp thuận entrypoint hiện tại, D8 ghi nhận M3 đồng ý hướng interface có điều kiện. Không suy ra cả nhóm đã duyệt các mục khác. Xem [hợp đồng runner/session](repair_runner_interface.md).

## 1. Các điều đã được người dùng xác nhận

- Triển khai trong repo `VGAR`; tuần 1–8 giữ trạng thái Done của nhóm.
- W9–16 theo `VGAR_W9_W16_Deliverables.md`; không mở rộng theo proposal gốc.
- Mỗi lần một task; kết thúc hoặc đến dependency thì ghi checkpoint và dừng.
- W9-0 chỉ chuẩn bị interface/baseline. Sau đó người dùng giao riêng W9-1: policy/config/tests độc lập; chưa triển khai admission, baseline-delta hoặc execution adapter.
- Sau đó người dùng giao riêng W9-2: diagnostic/comparator và verifier opt-in đã implement. Ngày 23/10 giao riêng W9-4: root session/provenance wiring đã implement, đang nghiệm thu; admission/environment bridge W9-3 chưa triển khai.
- Baseline thiếu môi trường thì ghi blocker và tiếp tục phần tài liệu của W9-0.

## 2. Quyết định liên thành viên

| ID | Nội dung và đề xuất | Lý do | Reviewer cần có | Trạng thái / phần bị chặn |
|---|---|---|---|---|
| D1 | A0=BM25/tests; A1=graph/tests; A2=graph/tests+syntax/mypy/Ruff delta | Tách retrieval và verification; required sets bám plan W9, khác nhãn proposal gốc | M1/M2/M3 | Đề xuất, chưa phê duyệt mapping; chặn pilot/config liên arm cuối cùng |
| D2 | Runner gọi direct `run_repair`, tối đa một generation/attempt, trả `RunHandle`; optional experiment W9-4 | Tái sử dụng engine/session, M3 quản lý batch và retry | M3 | M3 APPROVE entrypoint; lifecycle docs đã chỉnh. Keyword experiment nay có trong API; không suy runner M3 đã tích hợp |
| D3 | M1 xuất pinned env profile; M2 bridge task commands, Git host/private lease | Session hiện từ chối external executor; host Python không phải Python của target | M1/M2 | Gate W9-3 đã implement Docker/profile v1 + standalone report/private mapping; Xarray scripted run_repair PASS. Batch/M3 review riêng |
| D4 | Chốt riêng oracle/test visibility trước pilot | Gold patch hoặc gold-derived allowed paths làm lệch thí nghiệm | M1/M2/M3 | Smoke W9-3 dùng independent issue reproduction, không benchmark oracle; protocol pilot batch vẫn cần nhóm chốt |
| D5 | Giữ retrieval export 8k; đề xuất thêm repair-compatible export chung hai arm | 8k snippets không bằng full chat 6k; tránh cắt context không có provenance | M1/M3, M2 kiểm prompt | Chờ review packing/budget; chặn generation từ bundle quá cap |
| D6 | Allowed source/static scope chung theo inventory/protocol, không theo gold | Tránh quyền sửa khác nhau giữa arm và diagnostic scope drift | M1/M2/M3 | W9-3 có inventory/source-roots protocol; smoke dùng toàn bộ36 production files xarray/core, không gold. Scope batch cuối chưa ghi nhóm duyệt |
| D7 | Qualification model/runtime/budget trước real run; lưu config identity | Demo profile chưa phải protocol SWE-bench; timeout phụ thuộc backend | M3 và người dùng nếu đổi tài nguyên | Chưa qualification W9; chặn real pilot |
| D8 | W9 profile opt-in; legacy W78 giữ nguyên; provenance trong metadata | Giữ tương thích consumers, không đổi public DTO | M2/M1; M3 đã review hướng interface | Plan W9-4 người dùng duyệt chọn names M3 đề xuất; save/load/direct/MCP đã implement. Gate nghiệm thu mới xem báo cáo W9-4; không ghi M3 duyệt code hoặc runner interoperability |

### Bổ sung từ M2-W9-1

- Required checks được implement đúng plan: A0/A1 `{tests}`, A2 `{tests,syntax,mypy,ruff}`. Ba configs khai báo ghi nhận đủ bốn checks; evaluator chạy theo policy sẽ do W9-2 thực hiện.
- `arm=null` ở cả ba config có nghĩa mapping retrieval chưa chốt. Loader không suy ra arm từ variant; `arm` có thể được đặt rõ thành `bm25` hoặc `graph` ở một config sau review. Thay đổi đó làm policy hash đổi.
- `static_mode=baseline_delta` và `diagnostic_identity_version=m2-static-delta-v1` chỉ là định danh ngữ nghĩa dự kiến để bind config; chưa có thuật toán comparator hay baseline-delta verdict trong W9-1.
- `policy_hash` được tính từ canonical effective policy, gồm defaults, không tự khai trong file; không thay model/budget/environment hash. W9-1 không tự phê duyệt các D; cập nhật D2/D8 ngày 22/10 chỉ dựa trên phản hồi M3 được dẫn ở trên.
- Ruling W9-1: tách arm chưa duyệt khỏi required-check policy để triển khai phần độc lập đã được người dùng cho phép. Không yêu cầu M1/M3 duyệt lại required sets vốn đã có trong plan chính.
- Ruling W9-1: test policy/contract/config dùng dependencies tối thiểu hiện có, không thay environment dùng chung. Ruff 0.16.5 chỉ là supplementary lint; full suite và lint pin 0.17.0 chưa được qualification.
- Ruling W9-1: thực hiện tại checkout VGAR người dùng đã chỉ định; giữ source/defaults cũ và mọi thay đổi chưa commit của W9-0; không tạo worktree/commit hoặc thực hiện task tiếp theo.

D4 cần ghi lựa chọn cụ thể: dùng benchmark F2P/P2P/test_patch hoặc baseline feedback trong repair thì ghi oracle-assisted development pilot cùng mức hiển thị. Nếu không dùng oracle thì M1 phải cung cấp reproduction tests/scopes riêng. Code hiện vẫn cần failing selectors; không giả định mode không-oracle đã sẵn sàng.

### Bổ sung từ M2-W9-2

- Required-check verdict đã có ở các hàm verification với keyword `variant`; không tự chuyển các caller W78 sang mode mới. Đường `variant=None` giữ strict static như trước.
- Comparator chọn multiset + source lines duy nhất/không đổi; ambiguity xử lý bảo thủ, file trên 10.000 dòng không map. Đổi phạm vi lớn hoặc comparator phức tạp hơn cần review, chưa tự triển khai.
- Nguồn parser format đối chiếu tài liệu chính thức; actual native smoke dùng mypy 1.20.2/Ruff 0.16.5, không giả thành pins 2.4.0/0.17.0. Mẫu JSON mang tên pin trong unit test là synthetic format fixtures.
- Ruling: chạy tools thật trên fixture riêng, không cần M1 tokenizer/model, để kiểm integration tối thiểu; giữ qualification pin/full suite pending. Không cài/hạ cấp môi trường dùng chung.
- Ruling: caller/session chịu global guard trước/sau operation; đã tách TimeoutError khỏi OSError để optional tool failure không nuốt exception hết deadline. W9-4 phải giữ outer guard `session.observe` hiện có.
- Ruling: lỗi JSON roundtrip list/tuple đã có test RED→GREEN; raw static FAIL giữ nguyên, delta/policy status ghi riêng.
- Review minor ngày 21/10 là raw JSON mypy boolean column thành integer trước validate; đã sửa hẹp qua RED→GREEN ngày 22/10 trong W9-2. Xem báo cáo W9-2, không coi parser bao phủ mọi malformed schema.
- Ruling review: các mục pinned runtime, full-suite, M1/M3 approval và W9-3/4 integration chưa được nghiệm thu; review code độc lập không thay các gate đó.

D5 không cho phép tự tăng cap hoặc sửa payload M1 tại chỗ. Nếu nhóm chọn tăng full-chat cap thay export bổ sung, ghi amendment và qualification tài nguyên trước chạy.

Những quyết định này chưa cần để viết unit tests policy/diagnostics độc lập sau khi người dùng giao task tương ứng; nhưng phải giải quyết trước đóng phần real integration phụ thuộc.

## 3. Kết quả kiểm tra môi trường, không phải kết quả model

Interpreter đã kiểm: `D:\Project\CAPSTONES\.venv\Scripts\python.exe`, Python **3.13.0**, phù hợp khoảng `>=3.11,<3.14` của VGAR host. Việc kiểm hiện tại dùng metadata package, chưa import/chạy tất cả dependency và chưa kiểm CUDA.

| Dependency | Yêu cầu repo | Đã cài / kết quả |
|---|---|---|
| accelerate | Không pin trong core | Chưa có |
| transformers | `>=4.51.0,<5` | 5.16.1 — lệch |
| tokenizers | `>=0.22.0,<=0.23.0` | 0.23.1 — lệch |
| langchain | `>=1.4,<2` | 1.3.18 — lệch |
| tree-sitter | `==0.25.2` | 0.26.0 — lệch |
| pyarrow | `==23.0.1` | 25.0.1 — lệch |
| datasets | `==4.8.5` | Chưa có |
| peft | `>=0.18,<1` | Chưa có |
| trl | `>=0.24,<1` | Chưa có |
| mypy | `==2.4.0` | 1.20.2 — lệch |
| ruff | `==0.17.0` | 0.16.5 — lệch |

Có 11 dependency thiếu/lệch trong bộ core+dev đã đọc, không có nghĩa cả 11 đều là dependencies cần thiết của mọi unit test. Riêng tokenizer assets thiếu và mypy/Ruff lệch pin đã đủ khiến baseline tích hợp W78 chưa đủ điều kiện so sánh theo profile repo. Không quy đây là lỗi code W78.

Thiếu cả bốn assets tại đường dẫn manifest yêu cầu:

`artifacts/m1/tokenizers/Qwen3-4B-Instruct-2507/cdbee75f17c01a7cc42f958dc650907174af0554/`

Gồm `tokenizer.json`, `tokenizer_config.json`, `vocab.json`, `merges.txt`. Manifest có SHA-256 kỳ vọng; chưa có file để xác minh actual hash. Chưa chứng minh cache ở nơi khác có đủ assets.

**Quyết định thực thi W9-0:** không chạy full baseline trong môi trường chưa đạt; lưu NOT_RUN/ENVIRONMENT_NOT_READY. Không cài/hạ cấp môi trường dùng chung hoặc tải model/tokenizer trong phiên này. Đề xuất lần xử lý môi trường sau: dùng environment riêng đúng requirements, provision tokenizer từ manifest và xác minh hash, rồi chạy lại baseline với evidence mới.

## 4. Rulings trong lần thực hiện này

| Ruling | Căn cứ | Hệ quả/giới hạn |
|---|---|---|
| Làm tài liệu tại checkout `VGAR` người dùng chỉ định; không tạo worktree, không commit | Plan đã duyệt nêu rõ repo và artifact; W9-0 không đổi production code | Chỉ docs/checkpoint và ignored evidence mới; kiểm hashes bảo toàn source |
| Dùng `docs/status/m2.md` cùng PROGRESS làm checkpoint; giữ raw evidence | Người dùng yêu cầu checkpoint và dừng từng task, chưa cho commit | Không dùng lịch sử commit thay cho trạng thái chưa commit |
| Không tạo test RED/GREEN cho nội dung tài liệu | Không thay behavior/product code trong task này | Kiểm nội dung bằng AST/signature/path/Markdown; không claim pytest PASS |
| Baseline blocked không chặn viết interface | Nhánh được duyệt từ đầu; xử lý review ngày 22/10 đóng riêng deliverable interface | Full baseline vẫn NOT_RUN; không chuyển thành gate bổ sung để chặn đóng interface W9-0 |
| Chỉ đọc/đối chiếu code, không sửa lỗi phát hiện ngoài scope | Giới hạn M2-W9-0 | Ghi limitation hoặc chuyển người sở hữu, không tự triển khai W9-1..4 |

## 5. Nội dung chuyển cho M1/M3

**M3 đã phản hồi:** mục 2–5 của `repair_runner_interface.md` được duyệt kèm điều
kiện; [receipt W9-0](reviews/2026-10-22-m2-w9-0-m3-review-resolution.md) giữ nguyên.
W9-4 nay implement experiment/variant/policy provenance xuyên root session và
MCP, theo names trong plan người dùng duyệt. [Báo cáo W9-4](m2_w9_4_variant_provenance.md)
ghi kết quả, review và gate chưa đạt nếu có. Chưa có runner M3 trong checkout,
không ghi interoperability hoặc phê duyệt code của M3 thay họ.

**Gửi M1:** review mục 6 của interface; cung cấp source/env/bundle identity, interpreter, collection evidence, report/plugin compatibility, test overlay/visibility và workspace mapping. Không chỉ gửi một Docker tag hoặc câu lệnh pytest mà thiếu provenance.

Mẫu receipt cho các quyết định khác còn chờ (không ký thay thành viên):

```text
Decision ID / section:
Reviewer và vai trò:
Ngày:
Commit hoặc SHA-256 tài liệu đã review:
Kết luận: APPROVE / REQUEST_CHANGES
Điều kiện hoặc nội dung cần sửa:
Evidence / PR reference:
```

Review M3 đã được ghi nhận từ nguồn người dùng cung cấp; ngày 22/10 là ngày xử lý của M2, không chứng minh review đúng hạn ngày 1. Không yêu cầu M3 ký thêm mẫu để thay tiêu chí plan. Các quyết định còn lại chỉ cập nhật khi có xác nhận tương ứng; không suy ra chấp thuận từ im lặng. **Chờ người dùng ra lệnh; chưa được phép bắt đầu task tiếp theo.**


### Bổ sung M2-W9-3 — 24/10/2026

Người dùng giao triển khai và hoàn thành W9-3; tiếp tục Docker-only, không vòng
thiết kế duyệt lại. Không commit/push hoặc chuyển task khác.

- D3: tiêu thụ nguyên profile M1 `vgar-task-env-v1`, COLLECTED-only; external
  expected hashes + manifest/base/raw Git blobs/qualified Python inventory.
  Target argv/report/syntax/static dùng Docker, Git/patch private host. Persist
  admission trong session/record/bundle, revalidate trước resume/execution.
  Replacement refs bị tắt sau Important review RED2→GREEN2. Hash là consistency,
  không authentication; MCP start/M3 runner thật chưa thêm input/integration.
- D4: technical smoke chọn independent tests từ public issue MCVE keep_attrs
  cùng false-control, overlay pin/bảo vệ. Không F2P/P2P/test_patch/gold/hints;
  fake scripted candidate và baseline feedback ghi rõ integration-only. Không
  tự phê duyệt oracle visibility của thí nghiệm batch hoặc real-model pilot.
- D5: canonical paired bundles8k/default full-chat6k không đổi. Handoff smoke mới
  chỉ source-only, đủ dòng2827–2878 của quantile, derived identity + ranges/hashes
  và consumer thật; V11 default giữ nguyên. Counter whitespace chỉ integration
  units. Giữ failures V11 column4 và V9 missing-preflight; không gán retrieval/
  Qwen qualification hoặc nói paired bundles đã repair-compatible.
- D6: source_roots là protocol input, allowed scope phải bằng toàn bộ production
  Python inventory dưới roots (không tests/protected). Smoke dùng xarray/core36
  paths, không chọn từ gold. Scope được hash/persist và không đổi giữa phases;
  mapping/scope batch liên arm chưa coi nhóm đã duyệt.
- Kết quả: final run05 PASS toàn loop, baseline FAIL/PASS → post PASS/PASS,
  14 cleanup và independent audit PASS; source/registry/profile/HEAD giữ nguyên.
  Full W78/W9 final317PASS, lint PASS. Raw mypy/Ruff missing-module errors giữ
  optional A0; A2/tools/model qualification không được suy ra.
- M1 vẫn3COLLECTED/2EXCLUDED; không sửa deps, cảnh báo, population hoặc env pins.
  Gate riêng W9-3 hoàn thành kỹ thuật, không là5×3 records, cả tuần9 hay review/
  merge nhóm. Evidence/checkpoint và limitations xem [báo cáo](m2_w9_3_admission.md).
