# Đợt 3: kiểm patch trên code của graph, server tự tính diff (TV2, 22/11/2026)

Trạng thái: **đã cài đặt 22/11/2026** theo plan `docs/superpowers/plans/2026-11-22-tv2-patch-checks-from-snapshot.md`;
**đã duyệt 22/11/2026** (bản nháp 2, rà với code cùng ngày). Quyết định ở §6. Không báo TV1 (theo
yêu cầu của TV2); contract `DiffRequest` của TV1 không đổi.

## 1. Vì sao

Các tool kiểm (`analyze_patch_impact`, `verify_patch_graph_constraints`, `run_relevant_tests`, `rank_patch_candidates`)
lấy **code gốc từ thư mục làm việc** (`impact._snapshot(document, root)`, `shutil.copytree(root)` trong
`patch_evidence`), rồi áp diff agent gửi lên đó. Database graph chỉ có `graph_metadata`, `nodes`, `edges`; không lưu
nội dung file. Ba lượt OpenCode trên ShopFlow (`ses_e009…` lượt 1–2, `ses_dfdde501…` bản clean) đều hỏng bước kiểm:

| Hiện tượng | Số lượt | Nguyên nhân |
|---|---|---|
| Agent chép tay diff sai (mất dòng ngữ cảnh `" "`, sai đường dẫn, cắt hunk, thụt lề, lẫn suy luận) | 3/3 | Tool bắt agent truyền nguyên văn diff dài |
| File đã sửa tại chỗ → tool từ chối | 2/3 (lượt còn lại hỏng sớm hơn, ở bước đọc diff) | Thư mục làm việc ≠ code của graph |
| `git stash` để về bản gốc: agent quên `pop`; `core.autocrlf=true` ghi lại CRLF nên vẫn lệch | 1/3 (bản clean) | Cách vòng qua phụ thuộc cấu hình git và sự cẩn thận của agent |

Đợt 2 đã làm thông báo lỗi rõ (nêu file lệch), nhưng không gỡ được nguyên nhân. Lượt clean 2 (cùng phiên) lần đầu kiểm
được: `verify` PASS, `analyze` COMPLETE, nhờ `core.autocrlf=false`, graph vừa dựng lại và agent stash/pop đúng. Nhưng agent
vẫn tự viết lại diff (bỏ `diff --git`/`index`, bỏ một dòng ngữ cảnh, sửa header hunk thành `@@ -38,6 +38,6 @@`), lần này
khớp nên qua. Kết quả vẫn phụ thuộc may rủi.

## 2. Mục tiêu

- Agent gọi tool kiểm **không truyền diff**: server tự tính diff giữa thư mục làm việc và code mà graph giữ.
- Diff truyền vào (vẫn hỗ trợ, cho ứng viên chưa ghi ra file) được áp lên **code của graph**, chạy được dù file đã sửa.
- Kết quả luôn ghi **diff nào đã được kiểm** và **file nào không kiểm được**.

Không làm: hỗ trợ thêm/xoá file trong patch (PatchPolicy chỉ cho sửa file đã có; giữ nguyên nhưng báo rõ); đổi nội dung
các bước kiểm hay cách xếp hạng; sửa giới hạn có sẵn của `verify_patch` với graph bật layer tuỳ chọn (xem §4.6).

Không chấp nhận: tool sửa thư mục làm việc của người dùng (mọi bước vẫn chạy trên bản sao tạm hoặc trong bộ nhớ); kết quả
phụ thuộc hệ điều hành (cùng nội dung thì cùng kết quả trên Windows và Linux, kể cả khi git đổi CRLF/LF).

## 3. Các cách đã cân nhắc

| Cách | Ý tưởng | Được | Mất |
|---|---|---|---|
| A. Bản gốc lấy từ git `HEAD` | Diff = `git diff HEAD`, gốc = `git show HEAD:path` | Không đổi database | Sai khi graph không dựng trên `HEAD` sạch (dựng lại sau khi sửa mà chưa commit); không chạy khi repo không có git; vẫn dính `autocrlf` |
| **B. Lưu byte file `.py` vào database khi dựng graph** (đề xuất) | Bảng `sources`; gốc = đúng byte graph đã dựng | Chính xác theo byte, không phụ thuộc git hay xuống dòng, chạy ở mọi trạng thái thư mục làm việc | Database to thêm bằng tổng byte `.py` của repo (ShopFlow: 27.718 byte, đã đo). Live build chỉ giữ **một** version (`prune_other_versions`), nên không nhân lên theo số lần dựng |
| C. Giữ nguyên, hướng dẫn stash | Đợt 1–2 | Không tốn code | Đã hỏng ở cả 3 lượt |

Chọn **B**. Graph vốn đã đối chiếu từng node với byte của file gốc (`impact._snapshot` so `content_hash`), nên giữ chính
các byte đó là nguồn sự thật tự nhiên.

## 4. Thiết kế

### 4.1 Lưu code gốc khi dựng graph

- `SQLiteGraphStore.initialize`: thêm
  `sources(graph_version TEXT, path TEXT, content BLOB, PRIMARY KEY(graph_version, path), FOREIGN KEY(graph_version)
  REFERENCES graph_metadata(graph_version) ON DELETE CASCADE)`. SQLite đã bật `foreign_keys = ON` (`_connect`), nên
  `prune_other_versions` tự xoá `sources` của version cũ; không cần code prune mới.
- `ingest(document, sources=None)`: tham số tuỳ chọn `Mapping[str, bytes]`. Mỗi lần dựng, live build ingest lại **toàn bộ**
  document (`live_build.py:151`), nên chỉ cần ghi đủ `sources` mỗi lần, không cần chép dòng từ version trước.
- Byte lấy từ đâu: builder không giữ byte (`IncrementalGraphBuilder` chỉ giữ sha256, `incremental.py:190`). Sau khi dựng,
  đọc lại từng File node trong thư mục repo và đối chiếu `sha256 == content_hash`. Lệch nghĩa là file bị sửa trong lúc
  dựng: báo lỗi `file changed during the build: <path>; call build_or_update_graph again`, không ingest.
- Ai ghi `sources`: `LiveGraphBuilder` (tool `build_or_update_graph`) và `vgar index` (`indexing.py`). Không đổi: graph
  của harness (không cần kiểm patch) và đường ingest của TV1 (`storage_capabilities`, `graph_jobs`).
- `artifacts/sample_graph.db` sẽ có thêm bảng rỗng khi được mở (như lần thêm cột 10/10): commit bản đã nâng cấp cùng đợt.

### 4.2 Code gốc cho các bước kiểm

- `snapshot_sources(service, graph_version) -> dict[path, bytes]`: đọc `sources`, kiểm `sha256 == content_hash` của File
  node; thiếu file hoặc lệch hash thì báo lỗi, không dùng.
- `analyze_patch_impact`: dựng các file `.py` đã lưu ra một thư mục tạm (`materialize_snapshot`, chỉ `.py`) và đưa thư
  mục đó làm `source_repo` cho `impact.analyze_patch_impact`. Lý do: `_map_patch` và `patch._bind` đọc file từ đĩa
  (`(root / path).read_bytes()`); dựng thư mục tạm giữ nguyên `impact.py` và `patch.py`.
- `verify_patch`, `run_patch_tests`: `materialize_snapshot` = `copytree(root, ignore=_IGNORED)` như hiện nay, rồi trên
  bản sao, theo đúng chính sách `discover_python_files` của builder: ghi đè file `.py` của graph bằng byte đã lưu, khôi
  phục file của graph bị xoá, xoá file `.py` mà builder thấy nhưng graph không có. `graph_version` chỉ phụ thuộc file
  `.py` (`_calculate_graph_version`), nên bước so version của `verify_patch` khớp; file khác `.py` lấy từ thư mục làm việc.
- Không có `sources` cho version đang phục vụ: giữ hành vi hiện tại (§4.4).

### 4.3 `diff` thành tham số tuỳ chọn

Áp dụng cho `analyze_patch_impact`, `verify_patch_graph_constraints`, `run_relevant_tests`. Chữ ký tool
`analyze_patch_impact(graph_version, diff="", …)`: đổi thứ tự để `diff` có giá trị mặc định. MCP gọi theo tên tham số; trong
repo không có chỗ nào gọi tool này theo vị trí. `rank_patch_candidates` giữ nguyên (ứng viên phải có diff), nhưng tự được
lợi vì `verify`/test của nó chạy trên code của graph.

Khi `diff` trống, server tính diff từ `snapshot_sources` → file `.py` hiện tại (theo `discover_python_files`):

- định dạng như `git diff`: `diff --git a/p b/p`, `--- a/p`, `+++ b/p`, hunk `@@`, 3 dòng ngữ cảnh,
  `\ No newline at end of file`. Parser hiện có (`patch.parse_unified_diff`) đã đọc các dòng này;
- so theo nội dung dòng, **bỏ qua CRLF/LF**, đúng ngữ nghĩa của pipeline hiện có: `parse_unified_diff` dùng
  `splitlines()`, `_bind` so dòng bằng `rstrip('

')` và ghi dòng mới theo kiểu xuống dòng của file gốc
  (`patch.py:133,147,151`), nên một thay đổi chỉ về xuống dòng không biểu diễn được bằng diff. Vẫn phân biệt có/không
  newline cuối file. File chỉ khác xuống dòng: coi như không đổi, liệt kê `line endings only: <path>` trong `not_checked`;
- **yêu cầu chấp nhận:** áp diff sinh ra lên code đã lưu qua đúng `parse_unified_diff` + `_bind` phải ra đúng byte của
  file trong thư mục làm việc khi hai bên cùng kiểu xuống dòng;
- file `.py` mới hoặc bị xoá so với graph: **không báo lỗi**, bỏ khỏi diff, liệt kê trong `checked_diff.not_checked`;
  `verify` thêm lý do `NOT_CHECKED: new file <path>` / `deleted file <path>` (verdict tính trên phần đã kiểm). Nhờ vậy
  file nháp (ví dụ `reproduce_bug.py`) không chặn bước kiểm, còn bản sửa cần module mới thì hiện rõ là chưa kiểm đủ;
- không có thay đổi: `verify`/`run_relevant_tests` trả `NOT_RUN` với lý do `NO_CHANGES`; `analyze_patch_impact` trả lỗi
  `INVALID_ARGUMENT` "no change … if you just rebuilt the graph, the change is already in it: check before rebuilding";
- vượt 5 file / 500 dòng: lỗi hiện có, thêm gợi ý "dựng lại graph sau mỗi lỗi đã kiểm".

Kết quả có thêm `checked_diff = {"source": "worktree" | "argument", "files": [...], "sha256": ..., "diff": <nội dung nếu
≤ 8 KB>, "not_checked": [...]}`. Trường này **thêm ở tầng tool** (`graph_server`, `execution_server`), không thêm vào
`ImpactReport` (contract `extra='forbid', strict=True`). Audit ghi `diff_sha256` của diff đã kiểm và `diff_source`.

Cache `_verified`/`_tested` (đợt 2) khoá theo hash của **diff đã kiểm**, không theo tham số (tham số trống thì luôn
giống nhau). Với code gốc cố định theo `graph_version`, cache luôn đúng.

Tài liệu khuyên **không truyền `git diff`**: diff đó so với `HEAD`, có thể chứa thay đổi đã nằm trong graph (dựng lại
sau khi sửa mà chưa commit). Commit sau mỗi lỗi không còn cần cho VGAR; điều cần là dựng lại graph **sau** khi đã kiểm.

### 4.4 Tương thích

- Database cũ: bảng `sources` được tạo rỗng khi mở; "chưa có code gốc" nghĩa là không có dòng nào cho version đang phục
  vụ. Khi đó giữ hành vi hiện tại (đọc thư mục làm việc, thông báo đợt 2), và thêm gợi ý "dựng lại graph để kiểm được
  trên file đã sửa". Live build ingest lại mỗi khi có thay đổi, nên chỉ cần một lần dựng là có `sources`.
- Đường provider của TV1 (`core_tools.respond(... DiffRequest.from_diff(diff))`, `diff: StrictStr` + `diff_hash`):
  `diff` chỉ tuỳ chọn ở đường mặc định. Có provider mà `diff` trống thì trả `INVALID_ARGUMENT` "diff is required with
  the host's provider". Không đổi contract `DiffRequest`.
- Agent/host cũ vẫn truyền `diff`: chạy được, và không còn cần stash.

### 4.5 Tài liệu

- README "Working session" bước 4: bỏ hướng dẫn stash; "gọi các tool kiểm không truyền diff, **trước khi** dựng lại
  graph".
- Docstring ba tool: `diff` tuỳ chọn, mặc định là thay đổi trong thư mục làm việc so với graph; có `checked_diff`.
- Kịch bản OpenCode (bước 3, mục 5): "gọi analyze_patch_impact và verify_patch_graph_constraints, không truyền diff"; bỏ
  stash và commit bắt buộc.

### 4.6 Ngoài phạm vi (ghi nhận)

- `verify_patch` dựng lại bằng `PythonGraphBuilder` không có cấu hình layer tuỳ chọn, nên graph bật SCIP/LSP/TSG luôn bị
  `BUILDER_OPTIONS_OR_SOURCE_DIFFER_FROM_SNAPSHOT`. Có từ trước, không đổi ở đợt này.
- File test mới do agent viết không được `run_relevant_tests` chạy (file mới nằm ngoài PatchPolicy).
- `get_related_context` cũng đòi file khớp graph (`Source content differs from graph snapshot; rebuild graph`, lượt clean
  2). Thông báo này đủ rõ (agent tự dựng lại graph), nên giữ nguyên; sau này có thể đọc từ `sources`.

## 5. Kiểm chứng

Test viết trước (TDD), trên repo nhỏ dựng bằng builder thật:

1. Sửa file tại chỗ, `analyze`/`verify` **không** truyền diff → PASS; `checked_diff.files` đúng file đã sửa.
2. Cùng trạng thái, truyền diff đúng → PASS, không cần stash.
3. Round-trip: diff sinh ra áp lên code đã lưu bằng `parse_unified_diff` + `_bind` ra đúng byte, gồm file không có
   newline cuối và file CRLF (hai bên cùng CRLF); file chỉ khác xuống dòng không có trong diff, nằm trong `not_checked`.
4. Không thay đổi → `NOT_RUN`/`NO_CHANGES` (verify), lỗi rõ ràng (analyze).
5. Thêm file `.py` nháp → bước kiểm vẫn chạy trên file đã sửa; file nháp nằm trong `not_checked`, `verify` có lý do
   `NOT_CHECKED`.
6. Hai lần gọi không truyền diff, giữa hai lần sửa thêm → kết quả khác nhau (cache theo diff đã kiểm).
7. Database cũ (không có dòng `sources`) → hành vi cũ + gợi ý dựng lại.
8. Dựng tăng dần: version mới có `sources` cho mọi File node; prune xoá `sources` của version cũ.
9. `content` trong database bị sửa (hash sai) → lỗi, không dùng.
10. File đổi trong lúc dựng → lỗi build, không ingest.
11. Có provider, `diff` trống → `INVALID_ARGUMENT`.
12. `run_relevant_tests` không truyền diff chạy trên code của graph + thay đổi.

Sau đó: toàn bộ bộ test; chạy lại tình huống ShopFlow bằng tool thật (gồm repo `core.autocrlf=true`); một lượt OpenCode
với mô hình cố định.

## 6. Quyết định (22/11/2026)

1. Cách **B**: lưu byte `.py` trong database.
2. Database cũ (không có dòng `sources`): giữ hành vi cũ, kèm gợi ý dựng lại graph.
3. Gộp `run_relevant_tests` (server `vgar-execution`) vào đợt này.
4. File `.py` mới/bị xoá: bỏ khỏi diff, liệt kê trong `checked_diff.not_checked`, `verify` thêm lý do `NOT_CHECKED`.
5. Không báo TV1.
