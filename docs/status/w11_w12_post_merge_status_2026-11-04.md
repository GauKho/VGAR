# Trạng thái chi tiết W11–W12 sau merge m3/w12-all

**Ngày đối chiếu: 04/11/2026.** Checkout `D:\Project\CAPSTONES\VGAR`, HEAD
`c88290a147bc42b70261b39e50b7f11d5e5137ea`, nhánh
`m2/w11-checkers-evidence-c7-20261102`, kèm phần M2 local chưa commit.

Đây là bản đối chiếu trạng thái, không phải biên bản nghiệm thu hoặc chữ ký review.
Phiên cập nhật này chỉ sửa tài liệu, không triển khai task kế tiếp hoặc chạy lại
model, Docker, held-out hay campaign. Các kết quả test dưới đây lấy từ JUnit đã
lưu của gate sau merge; không phải một lượt test mới của phiên cập nhật trạng thái.

## 1. Nguồn và cách đọc trạng thái

Hai nguồn chính:

1. [Phân công song song](../superpowers/specs/2026-10-31-w11-w12-parallel-split-design.md):
   người làm, sở hữu file, H1–H5, máy chạy và thứ tự công việc.
2. [Spec kỹ thuật](../superpowers/specs/2026-10-31-w11-w12-design.md):
   phương pháp, V/G/S/P tests và tiêu chí từng deliverable.

Theo chính tài liệu phân công, deliverables v2 vẫn là nguồn tiêu chí nghiệm thu;
§1.6 của phân công thay Q3/§6 về lịch máy chạy của spec kỹ thuật. Không tự áp dụng
các đề xuất mới chỉ vì chúng xuất hiện trong nhánh vừa merge.

Phân biệt ba loại bằng chứng:

| Loại | Ý nghĩa | Giới hạn |
|---|---|---|
| Code/JUnit local | Đã đọc code hoặc kiểm file/log/JUnit thực có trên máy này | Không thay real campaign, GitHub CI hay human review |
| Số liệu M1/M3 báo cáo | Có số và đường dẫn được ghi trong tài liệu đã commit | Raw trên máy khác chưa được import/đọc thì chưa kiểm toán lại |
| Chưa có bằng chứng bàn giao | Chưa có record/bảng/approval cần thiết trong phạm vi kiểm tra | Không suy rằng mọi máy của nhóm đều chưa chạy |

**Code đã commit trên nhánh và có trong local HEAD** khác với **đã merge main**.
Phiên này không truy vấn GitHub PR/review/CI. Các điều kiện đó ghi **chưa xác minh**,
không tự ghi PASS/approve. Các trạng thái HT/MP/CT trong bảng M3 là lịch sử, không
tự chuyển thành DONE theo deliverables chỉ từ nhãn.

## 2. Những gì thay đổi sau merge

- Đã fast-forward 12 commit/82 file từ `32fd4723` tới `c88290a1`.
- Code M1/M3 W12 trước đây ghi “chưa commit” nay đã có trong HEAD này; các dòng
  03/11 trong `m1.md`/`m3.md` được giữ làm lịch sử.
- API/structural/evidence và C7 của M2 đã commit từ `32fd4723` và được giữ lại.
- A3/fairness/policy, neutral static measurements, mutant pool/evaluator và test
  W12 của M2 vẫn là thay đổi local chưa commit; không bị incoming ghi đè.
- **Cầu nối signature risk đã có:** `graph/impact.py::analyze_patch_impact`
  gọi `check_api`/`with_api_risk` trên baseline/predicted bytes. Không còn ghi
  “chờ M1 viết bridge” như trạng thái trước merge. Review/tích hợp thật vẫn riêng.
- Bản freeze mới vẫn là **nháp**: ba dòng chữ ký còn trống; local không có tag
  `protocol-freeze` hoặc amendment. Không mở held-out.

Bằng chứng merge: [checkpoint](../checkpoints/2026-11-04-merge-m3-w12-all.md),
[summary](../../results/integration/merge-m3-w12-all-20261104-c88290a1/summary.json),
[JUnit](../../results/integration/merge-m3-w12-all-20261104-c88290a1/merge-gate-approved.xml).

Gate sau merge: **1419 PASS, 20 SKIP, 0 FAIL/ERROR, 1737,190 giây theo JUnit**.
Phạm vi: test incoming, toàn bộ `tests/m2`, `tests/m3` và các ranh giới agent/MCP
liên quan; **không phải full offline suite**. SKIP có lý do Windows/POSIX/symlink,
vermin chưa cài, thiếu local agent traces và Docker opt-in; không biến SKIP thành PASS.
18 policy hash/payload legacy và 301 hash artifact M2 cũ đã được đối chiếu PASS.

## 3. Mười lăm deliverable chính thức

### 3.1. M1 — Graph, retrieval, incremental và dry-run

| Task | Yêu cầu chính | Tình trạng sau merge | Bằng chứng/số liệu | Còn lại và người giữ |
|---|---|---|---|---|
| **M1-W11-1** | Incremental parse/relink/invalidate; modify/add/delete/rename/move-import khớp full rebuild, no-op giữ version/cache | Có implementation và tests trong HEAD; gate kỹ thuật được bảng M3 ghi HT; chưa xác minh nghiệm thu nhóm | `src/vgar/graph/incremental.py`, `tests/test_incremental.py` cho G3–G5. Test file này không nằm trong gate merge 1419; không gán cho nó số PASS mới. Benchmark fixture sau merge có 9 PASS | M1/M3 xác nhận review/CI và bằng chứng incremental gốc; không cần làm lại implementation chỉ vì chưa có số U1 thật |
| **M1-W11-2** | Tune trên dev, ghi từng bước/heuristic và đóng băng hash | Có kết quả được M1 báo cáo; config giữ trọng số cũ sau các thử nghiệm bị reject | Dev retrieval 25 task, ghép cặp graph N=22 vì 3 Sympy timeout. BM25 File R@5=0,527; graph=0,447; Δ ghép cặp −0,091, CI95 [−0,292;0,121]. Hash `sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a` | M1/M3 review protocol deviations và bằng chứng raw. Các thư mục retrieval được dẫn không có tại Windows root đã kiểm; chưa audit lại raw |
| **M1-W12-1** | Script benchmark và bảng cold/warm U1, thời gian/node/cache, so full rebuild | Code đã commit; **chờ benchmark thật** | `scripts/bench_incremental.py`, `evaluation/incremental_bench.py`; **9 PASS**. Có 3 kịch bản body edit, thêm/xóa file, đổi public signature | M1 chạy trên source đã pin, theo runbook là xarray-4629, sinh `u1.json/u1.md` với môi trường/hash/repeats. Chưa có bảng U1 thật được bàn giao |
| **M1-W12-2** | Dry-run trên dev chuẩn bị held-out; theo split plan là toàn chuỗi 2 lần không ERROR hạ tầng | Code/runbook/derive config đã commit; **chưa có hai run PASS được bàn giao** | `evaluation/dry_run.py`, `scripts/dry_run_heldout_chain.py`: **12 PASS**; `tests/m3/test_derive_config.py`: **10 PASS**. Hai dev task là astropy-13033 và django-10914 | M1 bàn giao script/config; **M3 khởi chạy** trên máy GPU/WSL. Cần H3 publication, inputs/images đúng pin và hai dry-run records; làm rõ xung đột thứ tự ở §8 |

Chi tiết R1 theo [retrieval method](../m1_retrieval_method.md): D5 bị reject với
Δ File R@5=0; `public_api_risk=0,05` bị reject, Function R@5 giảm 0,038; mức0,10
bị dừng vì RAM ở6/25 task và người dùng chọn không chạy lại sau khi thấy mức0,05.
Đây là lệch giao thức đã công khai, không ghi thành một run hoàn tất. D3/IMPORTS
hop2 được chuyển sang đánh giá impact, chưa được chứng minh đã xử lý bằng bảng I1.
Δ−0,091 là trên22 task ghép cặp, không lấy phép trừ trực tiếp hai mean có N25/N22.
Tập dev25 retrieval dùng tune khác population25 repair W10.

### 3.2. M2 — API, structural, evidence, A3 và verifier evaluation

| Task | Yêu cầu chính | Tình trạng sau merge | Bằng chứng/số liệu | Còn lại và người giữ |
|---|---|---|---|---|
| **M2-W11-1** | So export/public signature baseline–post bằng AST, body-only không breaking; cung cấp signature risk | **Đạt kỹ thuật local**, checker đã commit; bridge impact M1 nay đã có trong HEAD | API tests **71 PASS**; impact **99 PASS/1 SKIP**, MCP impact **8 PASS**. `repair/api_check.py`, `graph/impact.py` | Review M1/M3 và qualification trên target thật. Unsupported exports/inherited constructors vẫn có thể NOT_RUN/NOT_COMPUTED; không coi unknown là false |
| **M2-W11-2** | Import cycle mới so baseline, forbidden-import/layer theo config, resolved edges/confidence | **Đạt kỹ thuật local**, đã commit | Structural tests **120 PASS**, dùng builder/resolver hiện hành. `repair/structural_check.py`, `structural_config.py`, `configs/m2/structural/` | M1 review và config repo thật nếu có. Chỉ có schema/example, không tự tạo rule kiến trúc cho25 repo. Thiếu config: cycle vẫn quyết định tổng, layer/forbidden subchecks NOT_RUN theo lựa chọn đã duyệt |
| **M2-W11-3** | Điền API/structural evidence, sidecar thật, NOT_RUN không thành PASS, giữ policy hash legacy | **Đạt kỹ thuật local**, đã commit, nối pipeline/session/MCP chung | Contract **41 PASS**, evidence checks **33 PASS**, có native integration trong gate. 18 policy hash/payload giữ nguyên. `contracts/evidence.py`, `repair/verification_checks.py`, `verification.py`, `pipeline.py`, `session.py` | Review contract C1/C2 của ba vai trò và CI/main chưa xác minh. Reader nhận placeholder legacy; DTO API/structural mới không đồng nghĩa mọi serialized evidence cũ giữ nguyên hình dạng |
| **M2-W12-1** | A3=A2 W10 cộng required API/structural, fairness V12; có record dev | **Code/fixture local xong; chưa DONE thực nghiệm**, chưa commit phần W12 | `configs/m2/variants/A3.json`, `repair/policy.py`, `evaluation/repair/fairness.py`; A3 verification **24 PASS**, A3 integration **6 PASS**; policy/fairness tests trong gate. Artifact hiện có ghi **0/25 real A3 attempts** | M2 publication/review/CI; M3 experiment config/preflight/fairness và campaign đúng population11+14=25. Giữ exclusions/errors trong ledger. Chưa duyệt ĐX1 thì không tự thay bằng record A3 suy từ A1 |
| **M2-W12-2** | Pool GOOD/BAD độc lập verifier; verify-once, suy verdict A0–A3; ma trận/FAR/FRR với mẫu số rõ | **Code/fixture local xong; chưa DONE thực nghiệm**, chưa commit phần W12 | Builder **46 PASS**, evaluator **54 PASS**, campaign **13 PASS**, native integration **4 PASS**. Demo6 slot:4 verified/2 NOT_APPLICABLE, sinh bảng lặp giống bytes. Readiness thật:25 task/150 slot danh nghĩa, **0 CREATED/150 input ERROR**, không phải150 verification failures | M3 cung cấp pinned inputs và chạy Docker theo phương án N; M2 kiểm records/sinh V1/V2 thật. Công khai NA/exclusions/errors/NOT_RUN, không dựng đủ150 patch giả. Profile/repro/exclusion phải được xử lý đúng policy |

Hai task W12 có code/fixture hoàn chỉnh nhưng output thực nghiệm bắt buộc chưa
được bàn giao. Người vận hành GPU/Docker là M3; trách nhiệm engine, kiểm evidence
và bảng verifier vẫn ở M2. Có artifact fixture không thay thế bảng V1/V2 thật.

### 3.3. M3 — MCP, metrics, protocol và Results

| Task | Yêu cầu chính | Tình trạng sau merge | Bằng chứng/số liệu | Còn lại và người giữ |
|---|---|---|---|---|
| **M3-W11-1** | Path jail/lease, selector/argv/output/timeout, redact/env allowlist, audit mọi call | Có code guard trong HEAD và test suite; bảng M3 ghi HT kỹ thuật; nghiệm thu nhóm chưa xác minh | `mcp/tooling.py`, `audit.py`, `registry.py`, `observability/redact.py`. Merge gate: redaction **24 PASS**, contract **18 PASS**; không phải đã chạy lại toàn bộ S1–S16 | M1/M2 review; full security tests/platform cases và GitHub CI. Checklist nêu rõ pytest vẫn chạy code target, không phải sandbox tuyệt đối |
| **M3-W11-2** | Vá legacy servers, giữ4 server, không tool ghi ngoài repair; execution dùng runner chung; run/chat không báo thành công giả | Có code trong HEAD, thay đổi kiến trúc theo hướng vá thay vì gỡ | `repository_server.py`, `execution_server.py`, `cli.py`, `mcp/pytest_runner.py`; đường thật `run_selector`→`repair.executor.run_bounded`. S15 được M3 báo cáo ACCEPT sau fix line-map ngày02/11 | Review/CI/main chưa xác minh. Raw smoke trên máy M3 chưa import; không gọi đó là test vừa chạy trên Windows |
| **M3-W11-3** | Shared envelope/error taxonomy C4 cho mọi server, audit và retryable nhất quán | Code/contract đã có trong HEAD; gate transport/contract local đạt | `mcp/schemas.py`, `docs/mcp_tool_contract.md`, `tests/test_mcp_tool_contract.py`: **18 PASS**. Runtime dùng `{status,data,error,metadata}` | M1/M2 xác nhận C4 và đồng bộ shorthand `{ok,...,audit_id}` trong nguồn kế hoạch; giữ transport status riêng verdict repair |
| **M3-W12-1** | Latency/token/tool calls, p50/p95 theo tool và lượt model, invalid/audit metrics | Code/script/trace v2 đã commit; **có số liệu do M3 báo cáo**, raw chưa được audit local | `agent_metrics.py`, `trace_report.py`, `aggregate_agent_traces.py`; metrics **15 PASS/1 SKIP** (không có local traces). M3 báo cáo run03/11 N5,47 lượt model, invalid2/42=4,8%, audit47/47=100%, theo NEXT40/42,0/5 resolved | M3 bàn giao trace/audit/config/code provenance và bảng M1 được script sinh lại; review tính hợp lệ sau các fix. Read redundancy là N/A có lý do, không phải0 |
| **M3-W12-2** | Protocol đủ fields, ba approval, tag, held-out hash gate | **Khung và gate đã commit; protocol chưa freeze** | `docs/protocol_freeze_heldout.md` còn ĐANG CHỜ,3 dòng chữ ký trống; local **0 freeze tags**. Gate tests **12 PASS**, có dataset-split tests của M2 | M3 điền pins/model/prompt/variants/timeouts/N/metric/statistics/lệnh dry-run; cả nhóm review/ký/tag. Không tự điền chữ ký, không mở held-out |
| **M3-W12-3** | Security checklist và Results draft v1 dev, mỗi số có nguồn script | **Đã có đầu ra tài liệu dạng draft trong HEAD**; review/CI/main chưa xác minh | `docs/security_checklist.md`: S1–S16; kiểm liên kết **2 PASS**. `docs/paper/results_draft_v1.md`, source checker **7 PASS**. R1/P1 có số; V1/V2/I1/G1/U1/M1 còn placeholder | M3 review và ráp khi nhận bảng từ đúng chủ. Placeholder được ghi rõ là hợp lệ cho draft; không ép draft thành Results cuối hoặc tự điền số chưa có |

Các run X2b/agent **không phải batch A3**: agent chọn tool và có tối đa3 generation,
còn batch A0–A3 hiện sinh một lần/attempt. Tài liệu M3 còn báo cáo run04/11 có
3 INFRA/2 MODEL do Docker/RAM; raw trên clone WSL khác chưa được đọc trong phiên này.
Các con số agent kể trên là DOC-reported, không phải số mới được tái tạo từ c88290a1.

## 4. Phần bổ trợ đã được giao trong split plan

| Mục | Trạng thái thực tế | Bằng chứng/việc còn lại |
|---|---|---|
| B10/D1, B02/D8 — M1 | Code có trong HEAD | `builder.py`, graph resource decode. G1/G2/S11 files có sẵn nhưng không nằm trong gate merge1419; không tự ghi PASS mới |
| H3 signature bridge — M1/M2 | Đã có code trong HEAD | Không còn thiếu hàm nối. Giá trị vẫn có thể unknown khi AST/export không hỗ trợ; không cam kết mọi task thật có available=true |
| M1-X1 G1/RQ1 | Chưa có bảng gán tay được bàn giao | Cần mẫu CALLS/IMPORTS/TESTS, labels và precision/recall/%unresolved. Không lấy số79% cũ làm kết quả mới |
| M1-X2 I1/RQ3 | Script/fixture đã có, chờ dữ liệu và run | `measure_patch_impact.py`, `gold_impact.py`:22 PASS; chưa có bảng I1 trên25 dev |
| R1 cuối — M1 | Có số M1 báo cáo và phương pháp | Raw4 thư mục retrieval được dẫn không có tại các đường dẫn local đã kiểm; giữ N22/N25, CI và deviation, không overclaim graph thắng BM25 |
| C6 — M2/M3 | Có đường thực thi chung, không làm lại | `execution_server` gọi `mcp.pytest_runner.run_selector`→`repair.executor.run_bounded`; bounded-runner tests trong M2; review security/consumer riêng |
| C7/D14 — M2/M3 | Đạt kỹ thuật, code đã commit | Sampler29 PASS; runner19 PASS và code-state5 PASS. Peak đo thành công được giữ, có samples_failed. Cần M3 review và record GPU thật; không coi7 VRAM thiếu ở W10 đã được sửa ngược |
| B01/D11 — M2 | Đã có xfail strict có lý do, không gọi là đã sửa HF bug | `tests/test_hf_model.py`; test này không nằm trong gate merge, full offline trước merge ghi1 XFAIL |
| D17 — M2 | Policy legacy được bảo toàn |18 hash/payload W9/W10 PASS trong biên bản merge. Không suy hash policy đủ để chứng minh context/code/runtime giống nhau |
| D10/D18 — M2 | Logic skip-mutant và mẫu số có test; số liệu thật còn chờ | ERROR là non-ACCEPT theo lựa chọn đã duyệt nhưng tách khỏi FAIL; static hints không được gọi runtime coverage |
| D15/N2 — M2 | **Chưa thực hiện task D15** | M3 có đề xuất1500/2700 và số liệu chẩn đoán, nhưng chưa là phân tích/bàn giao M2 theo arm. Chưa có script/report D15 mới hoặc timeout được nhóm chốt; giữ900/1800 hiện hành |
| D13 — M3 | Usage và thống kê lượt model đã có đường code | Không cần viết lại local_chat chỉ để thêm usage; cần kiểm missing fields từ record thật |
| D16 — M1/M3 | Chưa đủ evidence harness ổn định W12 | Chưa có hai dry-run PASS được bàn giao. Agent gặp Docker/RAM không chứng minh batch cũng hỏng, nhưng vẫn cần qualification đúng image/profile |
| D20/S15 — M3 | Có smoke được M3 báo cáo đạt | `docs/m3_w11_s15_smoke.md`: rerun02/11 ACCEPT sau fix unchanged-file line map. Smoke1 task không thay25-task A3 hoặc mutant pool |

## 5. Contract, bàn giao và cổng tuần

| Contract | Code hiện tại | Phần cần xác nhận |
|---|---|---|
| C1/C2 | DTO API/structural, sidecars và required-vs-supplemental đã nối engine | Human review ba vai trò; không đồng nhất reader legacy với mọi output mới byte-identical |
| C3 | A3 local kế thừa A2 W10,6 required checks,4 serialized recorded checks, bind graph; không re-plan riêng | Publication/CI/review; ghi quyết định25 task thay5 và xử lý đề xuất ĐX1 trước thay cách chạy |
| C4 | Runtime `{status,data,error,metadata}`, enum/retryable dùng chung | Đồng bộ mô tả nguồn; không thay envelope trong phiên cập nhật trạng thái |
| C5 | Hash ranking993f02c9… đã ghi và ghim trong test | Context equivalence/rerun list và freeze bản cuối; cùng config hash không tự bảo đảm cùng source/graph |
| C6 | Runner chung có đường gọi thật, giới hạn do server đặt | Review consumer/security còn tách riêng |
| C7 | Sampler và consumer runner có code/test | Review M3 và số đo trên GPU thật |

| Mốc | Đánh giá sau merge | Còn thiếu |
|---|---|---|
| H1 | Người dùng đã xác nhận họp/duyệt; giữ quyết định đã chốt trong hội thoại | Không tự suy các ĐX1–ĐX5 ngày04/11 cũng đã duyệt; approval PR/contract vẫn cần evidence |
| H2 | B10/B02 code có trong HEAD; structural fixture chạy với resolver hiện hành | Xác nhận handoff/review của chủ; G1/G2/S11 không được chạy lại trong gate merge |
| H3 | Ranking/evidence/C7/signature bridge có code; A3 đã có local | A3 và các thay đổi W12 chưa commit/bàn giao đúng nhánh chạy; review/CI/main chưa xác minh |
| H4 | Có báo cáo agent/X2b; **chưa có evidence batch A3 và hai dry-run được bàn giao** | M3 gửi đúng records, exclusions/errors, configs/hashes và đường dẫn; không dùng5 agent task thay batch |
| H5 | R1 có báo cáo; code tạo các bảng khác có phần đã sẵn | G1/I1/U1 và hai dry-run từ M1/M3, V1/V2 thật và timeout D15 từ M2 còn chờ |

**Cổng W11:** nhiều phần code đã sẵn nhưng chưa đủ bằng chứng đóng cổng “đã merge main”:
A3 còn local và chưa xác minh review/CI/main. Không đổi nhãn đó thành cổng đã đạt.

**Cổng W12/M6:** chưa đóng. Protocol chưa ký/tag; A3 thực nghiệm chưa bàn giao;
hai dry-run chưa có evidence đạt; U1 thật chưa có. MCP metrics có số được M3 báo cáo
nhưng raw/bảng mới chưa audit local. Guard code không thay human review hoặc CI.
M3-W12-3 có draft đúng dạng yêu cầu không đồng nghĩa toàn M6 đã đạt.

## 6. Bảng đánh giá và dữ liệu có thể dùng

| Bảng | Tình trạng | Nơi/nguồn |
|---|---|---|
| R1 | Có báo cáo số dev, raw chưa có ở local paths đã kiểm | `docs/m1_retrieval_method.md`, run IDs trong §3.1 |
| P1 | Có bảng W10 A0–A2 được M3 báo cáo, N25 mỗi arm; chưa có A3 mới | `docs/status/m3.md` §6.3, `results_draft_v1.md`. Không dùng `verification_pool_counts.json` làm P1 repair |
| V1/V2 | Có bảng demo fixture; chưa có bảng pool thật | `results/m2/w1112/m2-w12-2-20261104-verifier-eval/fixture_demo/` |
| I1/G1/U1 | I1/U1 có script, G1 cần gán tay; chưa có bảng thật được bàn giao | Scripts và status M1 ở trên |
| M1/RQ5 | Có metrics code và số M3 báo cáo; raw WSL chưa đọc local | `docs/status/m3.md`, `docs/status/m3_x2b_diagnosis_2026-11-04.md` |
| S1 | Checklist đã commit,31 test references theo tài liệu | `docs/security_checklist.md`; test tồn tại không đồng nghĩa toàn bộ security suite đã chạy trong gate này |

Kiểm paths Windows có giới hạn: pinned Parquet dưới `data/downloads/c104f840…/`
và `data/w10` không tồn tại; các paths R1/U1/I1/X2b được kiểm cũng chưa có.
Không khởi động WSL để kiểm `~/w10`/`~/vgar-x2b` trên máy M3.
Population repair vẫn là **11+14=25 unique IDs**. Có **23 repro configs**, thiếu
requests-1724/pylint-4970; [EXCLUDED.md](../../configs/m3/w10_dev/tasks/EXCLUDED.md)
đã giải thích lý do không có reproduction đáng tin trước run. Giữ hai task trong
ledger/mẫu số và xử lý exclusion đúng policy; không tạo test giả hoặc thay task.

## 7. Các test counts được trích từ JUnit merge

| Module | PASS | SKIP |
|---|---|---|
| API / structural |71 /120|0 /0|
| Evidence contract / evidence checks |41 /33|0 /0|
| A3 verification / native integration |24 /6|0 /0|
| Mutant builder / evaluator / campaign / native integration |46 /54 /13 /4|0 /0 /0 /0|
| GPU sampler / runner / runner code-state |29 /19 /5|0 /0 /0|
| U1 bench / I1 gold impact / dry-run / derive config |9 /22 /12 /10|0 /0 /0 /0|
| Held-out gate |12|0|
| Agent metrics |15|1|
| Impact / MCP impact |99 /8|1 /0|
| MCP contract / redaction |18 /24|0 /0|
| Security checklist / Results sources |2 /7|0 /0|

Đây là nhóm con của1419 PASS/20 SKIP, không phải số lượt model hoặc population.
Không cộng các gate khác thời điểm để thành tổng mới. Full offline trước merge
có1994 PASS/18 SKIP/1 XFAIL, nhưng không dùng nó làm full-suite result cho c88290a1.
Các ghi chú M1/M3 cũ “full CI” đã bỏ1 harness test không thay full CI không deselect.
Local mypy1.18.2/Ruff0.13.3 khác dev pins2.4.0/0.17.0; gate local1737s cũng chưa
chứng minh mục tiêu GitHub CI<10 phút. Phiên này không cài lại dependencies.

## 8. Những điểm phải thống nhất, không tự triển khai

1. **Thứ tự máy chạy:** split plan §1.6 yêu cầu dry-run1→batch→dry-run2→pool
   theo phương án N. Runbook03/11 lại yêu cầu pool xong trước dry-run.
   Theo thứ tự ưu tiên của hai nguồn người dùng yêu cầu, không tự dùng điều kiện
   mới để tuyên bố pool là blocker bắt buộc của dry-run; M1/M3 cần chốt amendment.
2. **A3:** bản gốc5 task/re-plan và phương án đã duyệt25 task/không re-plan
   phải có quyết định được ghi thống nhất; code hiện tại theo phương án người dùng đã duyệt.
3. **ĐX1–ĐX5:** file `docs/status/m3_a0_a3_plan_2026-11-04.md` ghi rõ chưa duyệt.
   Không tự suy A3 từ A1, đổi1500/2700, quantize, sửa prompt/ranking hay đổi N.
   ĐX4 nói A3/pool chưa có là snapshot trước code M2 local, không phải lý do làm lại.
4. **Structural và C4:** thiếu config là NOT_RUN ở subchecks theo lựa chọn đã duyệt,
   không mặc định NOT_RUN toàn cycle checker. Envelope runtime là bản trong contract
   M3 hiện hành, không phải literal shorthand cũ trong split/spec.
5. **Metric/protocol:** câu “F3/F4 đổi qua feedback retry” trong freeze nháp cần nhóm
   đối chiếu với batch một generation; ĐX3 chưa tự thành quyết định mới.

## 9. Phần còn lại theo đúng chủ

| Chủ | Việc đang thiếu để nghiệm thu | Không tự suy là đã xong |
|---|---|---|
| M1 | Review/handoff phần graph; bàn giao R1 raw, G1 labels, I1/U1 thật; phối hợp sửa harness nếu dry-run lỗi | Script PASS không thay số đo dev hoặc hai dry-run |
| M2 | Publication/review/CI của A3/pool; kiểm records M3 và sinh V1/V2/P1 verification đúng nguồn; D15 khi được giao | Không tự chạy model, đổi budget/timeout, hoặc tự chuyển task |
| M3 | Nhận code M2, khởi chạy GPU/Docker theo quyết định đã chốt; gửi H4/trace/audit; ráp bảng/draft; quản lý board và freeze | Merge nhánh local không thay PR-main/human review/CI hoặc chữ ký |
| Cả nhóm | Review C1–C7 theo chủ, thống nhất các amendment và nguồn mâu thuẫn, ký/tag đúng thời điểm | Chat approval triển khai không tự tạo chữ ký PR/protocol |

Theo quy tắc sở hữu file của hai nguồn, phiên này **không sửa** `Task Status.md`,
`docs/status/m1.md`, `docs/status/m3.md` hoặc hai spec. M3 có thể dùng đối chiếu này
để cập nhật board: M2-03/M2-04 hiện phù hợp **MP** thay CT (code/fixture đã có,
thực nghiệm chưa xong); M1-03/M3-03 bỏ “chưa commit”; M3-03 phân biệt số liệu agent
được báo cáo với raw đã audit; M2-01 bỏ “bridge chưa commit”; M2-02 sửa mô tả NOT_RUN
ở đúng subcheck. Không tự ghi HT nghiệm thu cuối cho hai task M2 W12.

Bản đối chiếu cập nhật [trạng thái M2](m2.md), [PROGRESS](../../PROGRESS.md) và
[checkpoint](../checkpoints/2026-11-04-w11-w12-status-audit.md).
Evidence của phiên cập nhật: `results/integration/w11-w12-status-20261104-c88290a1/`
gồm facts, counts theo module từ JUnit, input/output hashes và kiểm bảo toàn tài liệu.
