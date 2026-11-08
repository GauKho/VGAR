# TV2 phản hồi hồ sơ MCP của TV1 (H1, 08/11/2026)

> **Bản nháp, TV2 chưa ký duyệt.** Trả lời `status.md`, `contract.md`, `expected_contract.json` và các mục cần review trong
> `2026-11-08-mcp-server-implementation-plan.md`.
>
> **Nguồn:** chỉ proposal (**[P]**, dẫn số dòng) và 4 file context: **[cp]** `check proposal.txt`, **[test]** `test.txt`,
> **[rq]** `rq metrics matrix.txt`, **[mm]** `metrics matrix.txt`.
>
> **Nhãn:** **ĐÃ RÕ** là nguồn trả lời trực tiếp. **SUY RA** là ghép từ nguồn, cần TV2 xác nhận. **CHƯA CÓ** là nguồn không nói, phải chốt
> trong nhóm; phần "Đề xuất" ở đó là ý kiến, không phải nguồn.

## 1. Tóm tắt

| Nhóm | Kết quả |
|---|---|
| C01–C05 (TV2 review) | C01 trả lời được. C02–C05 trả lời một phần, phần còn lại ghi rõ ở mục 2 |
| E01–E04, M01–M05 (quyết định của nhóm) | Nguồn chỉ cho khung và tên metric; hầu hết định nghĩa cụ thể phải do nhóm chốt |
| Số lượng 11 tool, 8 resource, 1 prompt 7 bước | **ĐÃ RÕ, khớp** [P] 1074–1084, 1045–1052, 1108–1120 |
| Cần TV1 sửa hoặc bổ sung | 5 điểm ở mục 4, trong đó quan trọng nhất là thêm `MAY_CALL` |
| Phát hiện về nguồn | [rq] ghi bộ dev có `min_source_files=2`, nhưng manifest thật ghi `min1`. TV1 đúng (xem E01) |

## 2. Trả lời C01–C05

### C01. Hướng `REPRODUCES`

**SUY RA: dùng hướng Test → Issue, đồng ý với đề xuất của TV1.**

- [P] 322 định nghĩa kiểu `FailingTest -> BugReport`, và pseudocode [P] 652 viết `REPRODUCES(TestNode(test), issue)`. Cả hai đều đi từ test sang issue.
- Chỉ ví dụ [P] 339 đảo chiều, đặt `--REPRODUCES-->` dưới node Issue. Đây là cách trình bày trong một ví dụ, không phải định nghĩa kiểu.
- [cp] 93 xác nhận repo đã có cạnh này trong `task_overlay.py`.
- **Còn lại:** tên hai đầu chưa thống nhất: [P] 322 dùng `FailingTest`/`BugReport`, [P] 652 dùng test/issue. Đề xuất: schema mới cho phép nguồn là `FailingTest`, đích là `Issue` hoặc `BugReport`; view legacy giữ Test → Issue.

### C02. Module dùng chung, `DEPENDS_ON`, Lift/Trace, namespace id

| Nội dung | Trạng thái | Trả lời |
|---|---|---|
| Endpoint `DEPENDS_ON` | **ĐÃ RÕ** | Hai cặp: Component → Component ([P] 264) và Requirement → Requirement ([P] 320). Dòng 871 chỉ là ví dụ ("Ví dụ:" ở dòng 868). `beta(DEPENDS_ON)` phải cho phép cả hai cặp |
| Thuộc tính của `DEPENDS_ON` | **ĐÃ RÕ** | Có `weight` bằng số cạnh qua ranh giới component ([P] 609–612) |
| `TRACES_TO` | **ĐÃ RÕ** | Requirement/Issue → Component ([P] 318, 873) |
| Lift | **ĐÃ RÕ** | Tín hiệu [P] 576–585; cohesion/coupling [P] 590–595, "chỉ nên là heuristic" (587) |
| Lift cho Python | **ĐÃ RÕ** | Component = package có `__init__.py`; Port = hàm/method công khai hoặc trong `__all__`; Route = decorator ([cp] 82–84) |
| Trace | **ĐÃ RÕ** | Nối `G_task` với cả `G_repo` và `G_arch` ([cp] 98) |
| Module dùng chung | **CHƯA CÓ** | Module có ở cả `G_repo` ([P] 213) và `G_arch` ([P] 256), và là nguồn của `CONTAINS_COMPONENT` ([P] 268). Nguồn không nói có phải cùng một node. TV2 chốt ở GA-2. Đề xuất: một node Module duy nhất |
| Namespace id | **CHƯA CÓ** | Nguồn chỉ yêu cầu id entity trong GraphDiff phải trùng id node `G_repo` ([cp] 110). Định dạng id chưa có. Đề xuất: giữ id `G_repo` hiện có làm chuẩn; node mới dùng tiền tố theo tầng |

### C03. DTO, ownership/path/range, confidence/unknown, capability, snapshot identity

| Nội dung | Trạng thái | Trả lời |
|---|---|---|
| Confidence và provenance | **ĐÃ RÕ** | Mọi cạnh lưu `confidence`, `source_tool`, `evidence` ([P] 557–567; [cp] 65) |
| Lời gọi chưa resolve | **ĐÃ RÕ** | "vẫn giữ edge với confidence thấp" ([P] 551–554). Xem điểm 1, mục 4 |
| Hai mức biểu diễn `CALLS` | **ĐÃ RÕ** | `Function/Method -> Function/Method` ([P] 231) và CallSite nối tới Method ([P] 547–548). Oracle "folded CALLS" của TV1 phù hợp với cả hai |
| Capability thiếu backend | **ĐÃ RÕ** | Hệ thống vẫn chạy khi không có backend nặng ([P] 1462; [mm] 128), và lõi nhẹ cộng backend tùy chọn ([mm] 152). Nguyên tắc báo unavailable rõ ràng của TV1 phù hợp |
| Quy ước path/range | **CHƯA CÓ** | [P] 566 chỉ nhắc "definition range" như một loại evidence |
| Snapshot identity | **Đã quyết định** | Nguồn không định nghĩa `graph_version` hay identity. TV2 đã đưa schema/builder/resolver vào định danh (mục 5) |
| Tách schema legacy và schema mới | **Đã quyết định** | [P] 857–866 định nghĩa một `S` duy nhất và không nói tới profile. TV2 giữ một `S`, kiểm theo hai profile (mục 5) |

### C04. Định danh Port, cập nhật caller, workspace lease

| Nội dung | Trạng thái | Trả lời |
|---|---|---|
| Cạnh Port | **ĐÃ RÕ** | `EXPOSES_PORT`, `CONSUMES_PORT`: Component → Port ([P] 265–266) |
| Biểu diễn Port | **SUY RA** | Ví dụ `Auth.login(username, password) -> Session` ([P] 276), còn resource mẫu chỉ ghi tên `login` ([P] 1061). Cần cả tên và chữ ký |
| Định danh Port | **CHƯA CÓ** | Đề xuất: id gắn với id symbol `G_repo`, chữ ký để ở thuộc tính, để đổi chữ ký vẫn là cùng một port bị thay đổi ([P] 1235) |
| Cập nhật caller | **ĐÃ RÕ** | "no public port deletion without corresponding caller update" ([P] 1228); "caller/test updated accordingly?" ([P] 1239) |
| Nguyên tắc so baseline | **ĐÃ RÕ** | Chỉ báo khi patch làm xấu hơn baseline hoặc vi phạm luật repo ([P] 285–293) |
| Workspace lease, cleanup | **CHƯA CÓ** | Nguồn chỉ có path jail và allowlist ([P] 1130–1134). Thuộc TV3/TV1 |

### C05. Giới hạn, truncation, lỗi

| Nội dung | Trạng thái | Trả lời |
|---|---|---|
| Độ sâu mặc định | **ĐÃ RÕ** | `k=2` ([P] 972, 1048); `max_depth` mặc định 2 ([P] 1098) |
| Ngân sách context | **ĐÃ RÕ** | Mặc định `budget_tokens=12000` ([P] 972), xếp hạng rồi `pack_until_budget` ([P] 993) |
| Hướng của `explain_dependency_path` | **SUY RA** | Theo chiều caller → callee, ví dụ `pay → discount_amount → is_eligible` ([test] 19, 21). Oracle "directed CALLS" của TV1 phù hợp |
| Quan hệ được đi qua | **CHƯA CÓ** | [P] 1080 chỉ có tên tool. Đề xuất: bắt đầu bằng `CALLS`; `IMPORTS` và `DEPENDS_ON` thêm khi có `G_arch`; `MAY_CALL` chỉ đi qua khi caller yêu cầu rõ |
| Trần path, rank, audit, build | **CHƯA CÓ** | [P] 1134 chỉ yêu cầu có timeout và resource limit, không có con số |
| Ánh xạ lỗi và partial | **CHƯA CÓ** | Nguồn không định nghĩa |

## 3. Trả lời E01–E04, M01–M05

| Mã | Nguồn nói gì | Còn phải chốt |
|---|---|---|
| **E01** Dataset | Proposal không chỉ định dataset ([rq] 1). Repo dùng SWE-bench Verified, bộ dev 50 task trên 12 repo, truy vấn `problem_statement_only_no_hints_or_gold`, held-out gắn protocol đã freeze ([rq] 21–25) | [rq] 23 ghi `min_source_files=2`, nhưng manifest 50 task ghi `min1-excluding-w9-pilot`. TV1 đúng. Điều kiện cross-file ([P] 840) vì vậy chưa được đảm bảo. Nhóm chọn tập; số task sửa từ 2 file trở lên chưa đếm được ([test] 70) |
| **E02** Model, agent | Không chỉ định; chỉ nêu "Claude Code hoặc coding agents khác" ([P] 54) | Toàn bộ |
| **E03** Ngân sách, timeout | Có `budget_tokens=12000` ([P] 972); phải có timeout ([P] 1134); ngân sách phải hữu hạn ([P] 839) | Con số còn lại, số vòng lặp, seed |
| **E04** A4 và khác biệt giữa các arm | A4: `graph checks` ([P] 1367); baseline "tests + graph structural checks" ([P] 1303); các check ở [P] 1213–1240. So từng cặp liền kề ([rq] 93–94). A0–A3 của repo khác nghĩa ([mm] 87) | A4 có gồm tests không: cột bảng không ghi, dòng 1303 có. A5 đổi cả Graph lẫn Verification so với A4 ([P] 1367–1368), trong khi [rq] 94 coi là tác dụng của invariant |
| **M01** Token | Có "LLM token cost", "context token cost" ([P] 1326, 1316); lấy từ trace ([rq] 48) | Định nghĩa input/output/tool, cách gộp |
| **M02** Iteration | Có "number of iterations" ([P] 1324); lấy từ trace ([rq] 48) | Đơn vị đếm |
| **M03** Thời gian | Có cold build, warm update ([P] 1203–1204); latency ([P] 1325, 1353) | Ranh giới cold/warm, timeout bị cắt |
| **M04** Đọc file thừa | Có "unnecessary file reads avoided" ([P] 1355); prompt "Read only files selected by graph" ([P] 1116) | Toàn bộ định nghĩa |
| **M05** Audit | Audit mọi tool call ([P] 1136); trường mẫu `timestamp, tool, input_hash, repo, result, reason` ([P] 1143–1150); "auditability of final patch" ([P] 1356) | `request_id`, task/run là bổ sung của TV1, không trái nguồn; mẫu số chưa có |

## 4. Điểm cần TV1 sửa hoặc bổ sung trong contract

1. **Thêm `MAY_CALL`.** Contract §5 không nhắc cạnh này, trong khi [P] 554 định nghĩa nó và [P] 1472 coi là cách giảm nhiễu. Câu "không dùng confidence tự đoán" cũng cần nói rõ không áp dụng cho `MAY_CALL`, vì proposal yêu cầu giữ cạnh confidence thấp ([P] 551). `get_callers`/`get_callees` không được trộn `MAY_CALL` với kết quả chắc chắn ([test] 21).
2. **Tham số `analyze_patch_impact`.** Mẫu [P] 1096–1100 dùng `repo_path`, `diff`, `max_depth`; contract dùng `graph_version`, `max_hops`, `max_nodes`. Cần ghi cách ánh xạ `max_depth` sang `max_hops`.
3. **Resource `vgar://component/{id}`.** Mẫu [P] 1058–1066 có `component, files, public_ports, dependencies, dependents, tests, risk`. Contract §4 chưa có `files`, `dependents`, `risk`.
4. **Ánh xạ tên giữa proposal và legacy.** Proposal dùng `TestCase` ([P] 220), `FailingTest` ([P] 307), `Test` ([P] 319); `IMPORTS` là Module/File → Module/File ([P] 230) còn legacy là Import → Module (contract §5). Contract nên có bảng ánh xạ.
5. **Oracle `draft_architecture`.** `DEPENDS_ON` của `CLI → Auth` và cặp `EXPOSES_PORT`/`CONSUMES_PORT` khớp [P] 264–266. Khi có GA-2, thêm `weight` ([P] 609–612).

## 5. Quyết định của TV2 về các xung đột và phần đã làm trong code

Các quyết định dưới đây là của TV2 (08/11), proposal không quy định. Code chưa commit, TV1 chưa có trên baseline `3f77fcf6`.

| Chủ đề | Quyết định | Trong code |
|---|---|---|
| Schema | Một schema `S`, hai profile | `validate_graph_document(document, profile=...)`, mặc định `full_vgar_mcp`; `legacy_w10` từ chối mọi loại ngoài bộ W10 |
| `legacy_view.py` | Nhận graph đầy đủ từ một builder duy nhất rồi lọc | TV2 cung cấp `project_legacy_w10(document)` trong `contracts/schema.py`; TV1 gọi hàm này |
| `MAY_CALL` | Builder sinh mặc định | Đã làm. Đường W10 lọc bỏ qua `project_legacy_w10`. Decay ở đường MCP thuộc RT-1, chưa làm |
| `vgar://repo/summary` | Báo đủ mọi loại cạnh, gồm `MAY_CALL` | Giữ nguyên; TV1 không so khớp cứng toàn bộ dictionary số đếm |
| Kết quả W12, mutant | Giữ bằng artifact và commit cũ, không bắt buộc chạy lại | Không đổi |
| `graph_version` | Hai graph khác bộ luật phải khác định danh | Hash gồm `repo_key`, revision, **nội dung file**, schema, builder, resolver profile. Lưu trong document, `statistics`, và `graph_metadata` |
| Định danh W10 | Vẫn cần làm baseline | `statistics.legacy_graph_version`; `project_legacy_w10` trả graph mang định danh này |
| Ghi trùng vào DB | Idempotent | Đã `ready`: log và giữ graph đã lưu. Chưa `ready`: vẫn báo lỗi, để không coi bản build dở là đã xong |
| `RESOLVER_PROFILE` | Baseline cũ tiếp tục hợp lệ | Giá trị không đổi vì logic `CALLS` không đổi, nên chưa cần registry. Khi cần, profile đọc từ `statistics.resolver.profile`, vì `graph_version` là hash không đọc ngược được |
| PyCG/JARVIS (L2-1) | Đã thử, chưa tích hợp | Không xong xarray trong giới hạn thời gian; xem `spikes/call_graph_tools/README.md` |

**Quy tắc E04, cần nhóm xem lại:** TV2 đề xuất A0–A1 chỉ dùng `CALLS`, A2–A5 được dùng `MAY_CALL`. Nhưng [rq] 93 yêu cầu mỗi cấu hình chỉ bật thêm một thành phần, và A2 đã bật task trace ([P] 1364–1365). Nếu `MAY_CALL` cũng bật ở A2, so sánh A1 với A2 không còn tách được tác dụng của task trace. Cần chốt trước khi freeze protocol.

## 6. Các phần đã đối chiếu và không có ý kiến

Không phản đối: cấu trúc envelope và mã lỗi legacy, tách `BoundContext`, oracle "folded CALLS" gồm caller Test, lộ trình lên SDK 2.x ([cp] 40), và nguyên tắc báo unavailable khi thiếu provider. Oracle không dùng cho số liệu báo cáo là phù hợp với tách biệt ở [test] 7–9.
