# Đợt 6: SCIP mặc định, LSP dự phòng trong graph MCP (TV2, 24/11/2026)

Trạng thái: **bản nháp 2, chờ TV2 duyệt**. Hướng đi đã chốt với TV2 ngày 24/11 (§6.1). Nguồn: proposal §2 (RQ1), §5.4,
§6.4, §15; spike 24/11 (script `D:\kltn\vgar-work\spikes\scip_mcp_spike.py`, `scip_checks_spike.py`; kết quả `off.json`,
`on.json`, `scip_lsp.json`, `lsp_only.json`, `replay_off.md`, `replay_on.md`). Giai đoạn sau (JARVIS, Joern) ở §7, ngoài
phạm vi đợt này.

## 1. Vì sao

- **RQ1** hỏi có xây được Arch-CPG từ tool open-source có sẵn mà không viết static analyzer từ đầu không. Graph mà agent
  đang dùng lấy cạnh CALLS từ resolver tĩnh tự viết (`python.call.static.resolve.v1`), nên chưa phải bằng chứng cho RQ1.
- **Proposal §5.4** xếp "SCIP hoặc LSP-backed symbol resolver" vào phần *bắt buộc cho bản đầu*. **§6.4** nối lời gọi bằng
  "SCIP/LSP/language-specific analyzer" và "nếu không resolve được, vẫn giữ edge với confidence thấp" (MAY_CALL).
- Code đã có SCIP, LSP, đã nối vào MCP (`layer_config.py`), và builder đã có thứ tự SCIP → LSP → tĩnh → MAY_CALL khi cả hai
  được cấu hình (`builder.py:247-258`, `1073-1093`, `1196-1256`). Nhưng cả hai tắt mặc định: mọi lượt OpenCode đến nay có
  `layers` = tất cả `off`.
- **Spike 24/11** (ShopFlow `68c96af`, server MCP chạy trong process, Windows; scip-python 0.6.6 và pyright 1.1.414 cài
  bằng `scripts/install_scip_runtime.ps1`, `install_lsp_runtime.ps1`):

| Cấu hình | Dựng lần đầu / cập nhật | CALLS | MAY_CALL | `layers` |
|---|---|---|---|---|
| Không layer (hiện tại) | 0,4 s / 0,13 s (từng phần) | 87 (tĩnh) | 67 | tất cả `off` |
| Chỉ SCIP | 2,9 s / 2,9 s (dựng lại đầy đủ) | 136 (SCIP) | 5 | `scip: ready` |
| SCIP + LSP cùng chạy | 5,4 s / 4,8 s | 136 (SCIP); LSP hỏi 4, xác định 0 | 5 | `scip, lsp: ready` |
| Chỉ LSP (như khi SCIP lỗi) | 3,9 s / 4,1 s | 136 (52 LSP + 84 tĩnh); LSP hỏi 163 | 5 | `lsp: ready` |

- Chạy lại 13 lần `get_related_context` của phiên A với SCIP: không mất hàm lỗi nào, kích thước gần như cũ.
  `analyze_patch_impact`, `run_relevant_tests` đúng khi bật SCIP.

Ba vấn đề chặn việc bật cho lượt agent thật:

| # | Hiện tượng | Nguyên nhân trong code |
|---|---|---|
| V1 | `verify_patch_graph_constraints` luôn ERROR `BUILDER_OPTIONS_OR_SOURCE_DIFFER_FROM_SNAPSHOT` khi graph dựng bằng SCIP (LSP cũng vậy); `checks_before_update` theo đó | `graph_version` băm kết quả SCIP/LSP (`builder.py:334-339`); `verify_patch` dựng lại bằng builder không có SCIP/LSP rồi so version (`patch_evidence.py:153-170`) |
| V2 | Mỗi lần dựng ghi một thư mục mới khoảng 3 MB vào `artifacts/m1/w7-w8/scip/<uuid>` (LSP: `artifacts/m1/w5-w6/lsp/`) **dưới thư mục đang đứng của server**, không bao giờ xoá; với OpenCode có thể là repo của agent (chưa kiểm) | `output_directory` mặc định là đường dẫn tương đối (`scip_resolver.py:27`, `lsp_resolver.py:31`) |
| V3 | Khi có layer, kết quả dựng sau một lần sửa báo `mode: "cold"`, `changed_files: []` | Nhánh có layer của `LiveGraphBuilder._compute` trả `[]` (`live_build.py:172-175`) |

## 2. Mục tiêu

- Server `vgar-graph` (khởi động bằng `python -m vgar.mcp.servers.graph_server`) dùng thứ tự resolver
  **SCIP → LSP → tĩnh → MAY_CALL** mặc định, khi máy có runtime đã ghim:
  - SCIP `ready`: dùng SCIP; LSP không chạy.
  - SCIP không `ready` (lỗi, quá thời gian, thiếu runtime hoặc node): dùng LSP cho các lời gọi chưa xác định.
  - LSP cũng không `ready`: resolver tĩnh; lời gọi không xác định giữ MAY_CALL confidence thấp như hiện nay (§6.4).
  - `layers` nói rõ tầng nào đã chạy và vì sao bỏ qua tầng khác.
- Các tool kiểm patch chạy đúng trên graph dựng bằng SCIP hoặc LSP (V1).
- SCIP/LSP không ghi gì vào thư mục đang đứng hay repo của agent; số thư mục chạy có giới hạn (V2).
- Kết quả dựng luôn cho biết file nào đã đổi (V3).
- Một lượt OpenCode thật trên ShopFlow có `layers.scip = ready` ở mọi lần dựng: bằng chứng RQ1 trong hệ thống agent dùng.

Không làm:
- Không bật tsg, JARVIS, Joern mặc định (JARVIS, Joern ở §7).
- Không chạy LSP song song khi SCIP đã `ready` (spike: thêm 1,9 s mỗi lần dựng, không thêm cạnh nào).
- Không làm cập nhật từng phần khi có layer: mỗi lần dựng vẫn dựng lại đầy đủ (đo ở lượt thật rồi mới quyết định).
- Không thêm dự phòng ở retrieval (text/embedding, proposal §15): thay đổi retrieval, để đợt riêng.
- Không đổi retrieval, `ContextPayload`, hình dạng output tool (đợt 5), R1, G1, script đo. Script đo vẫn chạy SCIP và LSP
  cùng lúc khi được truyền cả hai tùy chọn, như hiện nay.

Tránh:
- So graph dựng bằng resolver này với graph dựng bằng resolver khác trong `verify`: khác biệt do resolver sẽ bị báo như do
  patch.
- Bật SCIP/LSP mặc định trong lúc chạy test của repo (bộ test phải chạy giống nhau dù máy có hay không có runtime).

## 3. Các hướng đã cân nhắc

| Vấn đề | Hướng | Đánh đổi | Kết luận |
|---|---|---|---|
| Bật | Chỉ đặt biến trong `opencode.json` | Không sửa code; server mặc định vẫn lệch §5.4 | Bỏ |
| | **Mặc định khi khởi động server, nếu có runtime đã ghim; tắt từng tầng bằng `VGAR_SCIP=off`, `VGAR_LSP=off`** | Đúng §5.4; chỉ áp cho tiến trình server | **Chọn** |
| Vị trí LSP | LSP chạy cùng SCIP mọi lần dựng (cơ chế builder hiện có) | Có dự phòng cho từng lời gọi SCIP bỏ trống; tốn 1,9 s mỗi lần, không thêm cạnh trên ShopFlow | Bỏ |
| | **LSP chỉ chạy khi SCIP không `ready` (TV2 chọn, cách A)** | Không tốn gì khi SCIP chạy được; khi SCIP lỗi, LSP cho số CALLS bằng SCIP trên ShopFlow | **Chọn** |
| | Dự phòng ở retrieval (text/embedding) | Đổi retrieval, ảnh hưởng R1 và freeze | Đợt riêng |
| V1 | So version bỏ phần SCIP/LSP, dựng ứng viên bằng resolver tĩnh | Rẻ; nhưng so chéo resolver → khác biệt giả | Bỏ |
| | Dựng cả baseline lẫn ứng viên bằng resolver tĩnh | Nhất quán; không phải graph agent thấy, thêm một lần dựng | Bỏ |
| | **Ứng viên dùng đúng resolver mà graph đã dùng thật; bỏ tính lại version khi graph có mã nguồn lưu trong DB** | Nhất quán với graph agent thấy; thêm một lần chạy SCIP hoặc LSP mỗi (graph, diff), đã cache | **Chọn** |
| V2 | Thư mục tạm, xoá ngay | Mất log khi lỗi | Bỏ |
| | **`<thư mục của VGAR_GRAPH_DATABASE>/scip-runs`, `/lsp-runs`, giữ 3 lần chạy mới nhất** | Còn log, dung lượng có giới hạn | **Chọn** |
| V3 | Thêm `mode: "full"` | Đổi hợp đồng tool | Bỏ |
| | **Giữ `mode: "cold"` (dựng lại đầy đủ), điền `changed_files` bằng so hash file với graph trước** | Không đổi hợp đồng | **Chọn** |

## 4. Thiết kế

### 4.1 Bật mặc định cho tiến trình server

- Ở nhánh `__main__` của `graph_server` (trước `require_host_config("graph")`), một hàm thuần nhận env và đường dẫn hai
  runtime đã ghim (`layer_config.SCIP_RUNTIME`, `LSP_RUNTIME`) rồi đặt:
  - `VGAR_SCIP_ENTRY` = runtime SCIP, nếu biến chưa đặt, `VGAR_SCIP` khác `off`, và file runtime tồn tại;
  - `VGAR_LSP_ENTRY` = runtime LSP, với cùng quy tắc theo `VGAR_LSP`.
  Biến đã đặt sẵn thì giữ nguyên.
- Import module (test, script) không qua `__main__` nên không bị ảnh hưởng.
- Log khởi động (INFO, dòng `server=vgar-graph ...` đã có) ghi mỗi tầng: dùng runtime nào, hoặc tắt vì sao.

### 4.2 Thứ tự resolver SCIP → LSP → tĩnh

- `LayerConfigs` của server đánh dấu LSP là **dự phòng của SCIP** khi cả hai có mặt. Builder nhận dấu này:
  - sau `prepare_scip`, nếu SCIP `ready` thì không chạy LSP; `graph_version` chỉ băm phần SCIP (bằng version của cấu hình chỉ
    SCIP);
  - nếu SCIP không `ready` (kể cả lỗi khi dựng `ScipResolver`), chạy LSP như cấu hình chỉ LSP hiện nay (`requested="lsp"`,
    LSP hỏi cho lời gọi thiếu hoặc yếu); `graph_version` băm phần LSP;
  - LSP cũng lỗi: resolver tĩnh và MAY_CALL như hiện nay.
- Không có dấu (script đo truyền cả hai tùy chọn): giữ hành vi hiện tại, SCIP và LSP cùng chạy.
- `layers` (`layer_config.layer_summary`): `lsp` có thêm trạng thái `skipped` với lý do "SCIP ready"; khi SCIP lỗi, `scip`
  là `fallback` kèm lý do, `lsp` là `ready` hoặc `fallback`.

### 4.3 `verify_patch_graph_constraints` trên graph dựng bằng SCIP hoặc LSP (V1)

- `verify_patch` nhận thêm cấu hình resolver của server (`layer_configs(os.environ)` ở `graph_server._verified`).
- Ứng viên dùng đúng resolver mà baseline đã thật sự dùng (`document["statistics"]["resolver"]["active"]`): `scip` → SCIP;
  `lsp` → LSP; `static` → resolver tĩnh như hiện nay.
- Graph có mã nguồn lưu trong DB (mọi graph do `build_or_update_graph` dựng từ đợt 3): bản sao đã dựng từ đúng mã nguồn đó,
  nên bỏ bước tính lại `graph_version` (bước gây V1). Graph không lưu mã nguồn giữ kiểm như cũ.
- Resolver chạy trên ứng viên không `ready` trong khi baseline đã dùng nó: `status` NOT_RUN, reason
  `CANDIDATE_RESOLVER_UNAVAILABLE: <resolver>: <lý do>`; không so chéo resolver.
- Kết quả vẫn cache theo (graph, diff); `checks_before_update` dùng chung đường này.
- `analyze_patch_impact`, `run_relevant_tests` không đổi.

### 4.4 Nơi SCIP/LSP ghi file (V2)

- Trong `layer_configs`, khi có `VGAR_GRAPH_DATABASE`: `output_directory` của SCIP = `<thư mục chứa database>/scip-runs`,
  của LSP = `<thư mục chứa database>/lsp-runs`. Không có biến đó thì giữ mặc định cũ.
- Sau mỗi lần chạy (kể cả lần chạy cho ứng viên trong `verify`), mỗi thư mục trên chỉ giữ 3 thư mục chạy mới nhất.

### 4.5 `changed_files` khi dựng lại đầy đủ (V3)

- Nhánh có layer của `LiveGraphBuilder` so hash nội dung các File node của graph vừa dựng với graph đã công bố trước đó:
  `changed_files` = file đổi, thêm, xoá, sắp xếp. Lần dựng đầu vẫn `[]`.
- `mode` vẫn `"cold"`; docstring nói rõ: khi có layer, mọi lần dựng là dựng lại đầy đủ.

### 4.6 Tài liệu

- Docstring `build_or_update_graph`: thứ tự resolver, ý nghĩa `layers`, `mode`, `changed_files`.
- `README.md` (bảng biến môi trường, mục cài đặt): hai script cài runtime, `VGAR_SCIP=off`, `VGAR_LSP=off`, nơi ghi file chạy.
- `docs/mcp_server/contract.md` (dòng `build_or_update_graph`, `verify_patch_graph_constraints` ở bảng §3).

## 5. Kiểm chứng

### 5.1 Test mới (TDD)

1. Hàm quyết định mặc định: có runtime + chưa có biến → đường dẫn runtime; `VGAR_SCIP=off` / `VGAR_LSP=off` → không đặt;
   biến đã có → giữ nguyên; không có runtime → không đặt.
2. Thứ tự resolver (test dùng runtime thật; **bỏ qua** khi máy thiếu runtime hoặc node):
   - SCIP và LSP đều có: `scip: ready`, `lsp: skipped`, CALLS có `python.call.scip.resolve.v1`, `graph_version` bằng cấu hình
     chỉ SCIP;
   - SCIP trỏ tới runtime không tồn tại, LSP có: `scip: fallback`, `lsp: ready`, có CALLS `python.call.lsp.definition.v1`;
   - cả hai trỏ tới runtime không tồn tại: resolver tĩnh, cả hai `fallback` kèm lý do, MAY_CALL vẫn có.
3. `verify` trên graph dựng bằng SCIP, và trên graph dựng bằng LSP (runtime thật, bỏ qua khi thiếu):
   - sửa `pricing.py` (fixture `SHOP`) → PASS;
   - sửa hằng số không đọc được (fixture `ORDER` của đợt 5) → NOT_RUN, `unsupported_changes` có `ALLOWED`;
   - không có thay đổi → NOT_RUN `NO_CHANGES`; không còn `BUILDER_OPTIONS_OR_SOURCE_DIFFER_FROM_SNAPSHOT`.
4. Resolver trên ứng viên không `ready` khi baseline đã dùng nó → NOT_RUN `CANDIDATE_RESOLVER_UNAVAILABLE`.
5. Thư mục chạy: sau 5 lần dựng, `<db dir>/scip-runs` có đúng 3 thư mục; thư mục đang đứng không có `artifacts/`.
6. `changed_files` khi có layer: sửa 1 file → `["<file>"]`; thêm 1 file và xoá 1 file → có cả hai.

### 5.2 Chạy lại spike (tự động, phía server)

`scip_mcp_spike.py`, `scip_checks_spike.py`, `replay_shopflow_session.py` với cấu hình mặc định mới, và với SCIP trỏ tới runtime
không tồn tại (để LSP chạy): `verify` lỗi 5 trả NOT_RUN nêu `ALLOWED_TRANSITIONS`; `verify` sửa thuế trả PASS; replay đạt;
không có file mới dưới thư mục đang đứng.

### 5.3 Bộ test đầy đủ

Pass hết trừ các lỗi Docker/harness đã biết (7 test: JARVIS 4, Joern 2, official harness 1).

### 5.4 Lượt OpenCode thật (TV2 chạy)

A-en big-pickle medium trên ShopFlow, `opencode.json` giữ nguyên (thứ tự resolver mặc định). Báo cáo trong
`docs/status/tv2_opencode_ab_shopflow_2026-11-22.md`: `layers` ở mọi lần dựng, thời gian mỗi lần dựng, trạng thái các lần
`verify`, có file lạ trong repo không, test ẩn, token. So với Lượt lặp 5 (cùng mô hình, không layer).

## 6. Quyết định

### 6.1 Đã chốt với TV2 (24/11)

- Bật các tool của Core MVP stack (§5.4) để chạy MCP thật; làm SCIP trước, nhận xét, rồi tới JARVIS và Joern.
- SCIP thử với cách dựng lại đầy đủ mỗi lần trước; đo ở lượt thật rồi mới quyết định cập nhật từng phần.
- Dự phòng theo proposal, cách A: SCIP không `ready` → LSP → resolver tĩnh (→ MAY_CALL như §6.4).

### 6.2 Mình tự chọn (sửa được khi duyệt)

- SCIP là tầng chính, LSP là dự phòng (SCIP đo được chất lượng graph tốt hơn trong G1; LSP chạy cùng SCIP không thêm cạnh).
- Mặc định bật ở nhánh `__main__` của server; tắt từng tầng bằng `VGAR_SCIP=off`, `VGAR_LSP=off`; test không bị ảnh hưởng.
- `verify` dùng đúng resolver của graph thật; resolver lỗi trên ứng viên → NOT_RUN, không so chéo.
- Thư mục chạy cạnh database, giữ 3 lần mới nhất.
- Giữ `mode: "cold"`, chỉ điền `changed_files`; thêm trạng thái `skipped` cho `layers.lsp`.

## 7. Giai đoạn sau: JARVIS và Joern

- Cùng cơ chế bật: `VGAR_JARVIS=1`, `VGAR_JOERN=1`; cần Docker Desktop đang chạy và hai image
  (`docker build -t vgar/jarvis-analyzer:v1.0 src/vgar/graph/jarvis`; Joern pull theo digest đã ghim).
- Trước khi bật cần kiểm cùng ba điểm V1–V3 cho hai tool này (`graph_version` có băm kết quả của chúng: `builder.py:340` trở
  đi; thư mục ghi file; thời gian dựng). Spec riêng sau khi có kết quả lượt SCIP.
