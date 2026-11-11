# Trạng thái MCP server — hướng triển khai mới

## TV1-H1 — 08/11/2026

- **H1: DONE phần chuẩn bị contract / ACCEPTED_FOR_IMPLEMENTATION.** Theo xác nhận của người dùng ngày 08/11/2026, nhóm đã chốt plan `Final_Task`; không yêu cầu thêm vòng review TV2/TV3 cho H1.
- **Chuẩn bị local: PASS — 15/15 kiểm tra tĩnh**, 0 failure/error/skip tại gate H1 gốc. Xác nhận plan không thay nghiệm thu implementation/runtime; không tạo chữ ký riêng của TV2/TV3.
- Đầu ra: [contract](contract.md), [oracle synthetic](../../tests/fixtures/mcp_server/expected_contract.json), [checkpoint](../checkpoints/2026-11-08-mcp-contract-baseline.md).
- Artifact mới: `results/mcp_server/contract/20261108T100021Z-baseline/`.
- Baseline HEAD `3f77fcf6`, branch `m2/w12-a3-verifier-d15-20261105`; 20 tracked dirty, 23 untracked, 0 staged trước H1. Không dùng kết quả plan cũ để suy ra DONE cho hướng mới.
- Đã ghi baseline hash 480 file và 7 tài liệu nguồn, runtime metadata và inventory metadata của bốn output A3 cũ. Không đọc/rebuild model hoặc dữ liệu WSL.
- Hiện trạng qua AST: 15 decorated tools / 14 bare names, 3 resource, 0 prompt. Mục tiêu contract: 11 core tools, 8 canonical resources, 1 prompt; legacy/alias được đếm riêng.
- H1 không sửa production code, không install/migrate runtime, Docker, model, campaign hoặc external-client smoke. SDK2/no-LangChain được nghiệm thu riêng ở mục L6-1 bên dưới, không phải bằng gate H1.

## Kết quả và giới hạn kiểm chứng

- Đã có 11 core-tool descriptors, 8 canonical resources, 1 prompt 7 bước; giữ riêng 15 legacy tools, 3 current resources và alias.
- Oracle synthetic gồm 5 file source, 4 symbols, 3 callsites, 7 cạnh evidence, 2 patch GOOD/BAD và 2 behavior examples. Legacy callers/callees gồm Test đúng SQLite; phần production impact có oracle riêng.
- Gate dùng Python stdlib/AST, không import hoặc execute code VGAR/target. Log/JUnit: `validation-final.log`, `validation-final.xml` trong artifact H1. Đây không phải production pytest suite hoặc wire test.
- Review kỹ thuật độc lập phát hiện một lỗi oracle thiếu Test caller; đã tái hiện RED, sửa fixture và gate GREEN. Bổ sung yêu cầu cancellation/concurrency vào contract. Việc không yêu cầu review thêm TV2/TV3 được ghi nhận từ chỉ dẫn của người dùng, không suy từ technical review này.
- Preservation: các file cũ giữ bytes, riêng `PROGRESS.md` chỉ nối thêm mục H1; source documents/index/HEAD/branch được đối chiếu. Bằng chứng chi tiết ở `preservation.json`.
- Whitespace phần H1 PASS. Global `git diff --check` vẫn báo 15 dòng trailing whitespace có sẵn trong báo cáo M2 cũ `docs/BAO_CAO_TONG_HOP_M2_W12_D15.md`; hash báo cáo không đổi, không sửa ngoài phạm vi để làm xanh toàn repo.
- Artifact có baseline/status/diffs, source/runtime/output inventories, commands, validation, review, preservation và checksums. Raw results không được stage/commit.

## Yêu cầu implementation và đầu vào thực tế

Không yêu cầu duyệt lại H1. C01–C05 là yêu cầu provider/schema/lease/bounds cần hiện thực theo plan; E01–E04 và M01–M05 theo dõi dữ liệu/config/định nghĩa đo thực tế phải có trước protocol freeze/real experiment. Không tự điền giá trị chưa được cung cấp. External-host controls vẫn UNVERIFIED; provider/tính năng chưa có không được đánh dấu đã triển khai.

Điểm dừng lịch sử phiên H1: chỉ H1. Trạng thái L6-1 được cập nhật riêng bên dưới; lượt cập nhật xác nhận plan không triển khai thêm task.


---

## L6-1 — Runtime/SDK migration — 08/11/2026

- **DONE kỹ thuật riêng L6-1 / runtime ACCEPTED** sau dependency, import, wire, regression và preservation gates; không phải DONE L6-2…L6-8 hoặc nghiệm thu graph/provider mới.
- Runtime riêng `D:\Project\CAPSTONES\environments\vgar-mcp-server-sdk2\Scripts\python.exe`, MCP2.2.0/MCP-types2.2.0, Windows amd64/CPython3.11. Lock56 distributions exact version + wheel SHA256; không LangChain/LangGraph/Torch/Transformers. Không đổi venv CUDA hoặc cài root VGAR metadata.
- Factory SDK2→MCPServer/SDK1→FastMCP, không fallback khi SDK2 hỏng; lazy legacy client export và name-only registry. Giữ15 tool signatures,3 resources,0 prompts và payload fixture legacy.
- RED→GREEN factory14 checks; CLI RED→GREEN; optimized-gate reproducer RED→GREEN. Final SDK2 unit gate **19 PASS**; legacy MCP regression **99 PASS +1 skip cũ** (Windows symlinks unavailable); targeted repair/legacy final **28 PASS**. Các gate có overlap, không cộng thành số test unique.
- Final wire **16/16 server/protocol cases PASS**: SDK2→SDK2 modern4 +legacy4; SDK1→SDK2 legacy4; SDK1→SDK1 legacy4. Actual protocol2026-07-28/2025-11-25 được ghi trong receipt.
- Repair smoke synthetic: trusted single_file_login + hash-pinned local tokenizer + supplied reference patch, đủ context/apply/tests/verify đến ACCEPT; không model/generator/Docker/campaign. DB dùng temp copy; nguồn gốc và fixture DB tracked được bảo vệ.
- `pip check`, lock dry-run require-hashes, Ruff scoped `--no-cache`, whitespace L6-1 PASS. Global diff-check còn15 whitespace cũ trong protected báo cáo M2; không sửa ngoài phạm vi.
- Technical review đã sửa blocker gate dùng assert bị bỏ bởi -O; final gates dùng explicit checks và child PYTHONOPTIMIZE=0. Đây không phải review/chữ ký TV2/TV3.
- [Runtime/runbook](runtime.md), config `configs/mcp_server/runtime.json`, [checkpoint](../checkpoints/2026-11-08-mcp-sdk-runtime.md).
- Artifact `results/mcp_server/runtime/20261108T121938Z-sdk2/`: commands, RED/GREEN/JUnit, install/resolver/lock reports, wire responses/audit, review, acceptance, preservation, summary/checksums. Artifact H1 sealed không bị ghi đè; PROGRESS/status chỉ append.
- **Còn chờ đúng phạm vi:** prompt PENDING_L6-4; concurrency/security đầy đủ L6-5; implementation provider/schema TV2/TV3 và Inspector/Claude Code L6-8. H1 ACCEPTED_FOR_IMPLEMENTATION theo xác nhận plan của người dùng; không cần thêm vòng review TV2/TV3.
- **Dừng sau L6-1**, chưa triển khai L6-5; không commit/push.

## Cập nhật xác nhận plan — 08/11/2026

Theo chỉ dẫn người dùng: nhóm đã chốt các plan trong `Final_Task`, bỏ yêu cầu review lặp lại TV2/TV3 cho H1. Contract/fixture/checkpoint hiện hành đã đồng bộ trạng thái; nội dung source/oracle và kết quả gate cũ không đổi. `PROGRESS.md` chỉ append. Artifact H1/L6-1 đã seal giữ nguyên; bằng chứng cập nhật nằm tại `results/mcp_server/contract/20261108T130221Z-plan-confirmation/`. Không chạy lại campaign hoặc thay production code.


---

## L6-5 — Security/concurrency nền — 08/11/2026

- **DONE kỹ thuật riêng L6-5.** H1 ACCEPTED_FOR_IMPLEMENTATION theo quyền người dùng; không chờ vòng review TV2/TV3, không tạo chữ ký thành viên.
- Đã có host-only immutable BoundContext/HMAC grants, exact single-use authorization liên process, pairwise-disjoint roots, regular-handle reads/path jail, known-secret/capability redaction và bounded audit reader.
- OS locks serialize audit và toàn bộ legacy repair load→mutate→save/finalize; commit/managed sidecar phát hiện crash/torn state. SQLite READY snapshot được kiểm8 queries đồng thời qua SDK2 worker threads trên temp copy; không claim concurrent schema migration đã được sửa.
- Guarded subprocess jobs có deadline/output caps, event/shared-marker cancellation, process-tree kill, awaited cleanup/receipt; SDK async wrapper ghi một terminal ERROR khi bị hủy. Atomic publication dùng staging + source/deadline recheck + request commit lock chung với cancellation.
- Gate SDK2 cuối **78 PASS,0 fail/error/skip** (59 security/concurrency cases +19 runtime/compatibility cases); legacy regression **100 PASS +1 skip cũ**, Windows symlinks unavailable. Các nhóm có overlap, không cộng unique tests.
- Legacy wire smoke **16/16 PASS**: SDK2 modern4+legacy4, SDK1→SDK2legacy4, SDK1→SDK1legacy4. Production surface vẫn15tools/3resources/0prompts; không provider mới.
- Test có native Windows junction, hai process audit120/120 records, replay chỉ một grant thành công, session24 updates không mất, crash integrity reject, hai real repair apply chỉ một thành công, cancellation6 build/copy/test × event/context, SDK cancellation, source drift, -O, staging/commit ordering và cleanup khi marker I/O lỗi.
- Ruff scoped và whitespace L6-5 PASS. Global15 whitespace cũ trong báo cáo M2 được bảo vệ giữ nguyên. Không thêm skip/xfail để che lỗi; unsupported native symlink được ghi riêng, không gọi simulated reparse là native symlink PASS.
- Direct dependency filelock4.2.9 đã có trong lock; không install/nâng package/venv. H1/L6-1/plan-confirmation artifacts giữ nguyên, PROGRESS/status/contract chỉ append.
- [Security runbook](security.md); [checkpoint](../checkpoints/2026-11-08-mcp-security-concurrency.md); artifact `results/mcp_server/security/20261108T131906Z-guards/` có commands/logs/JUnit/review/preservation/summary/hashes.
- **Chưa làm:** adapter/provider L6-2, graph jobs L6-6, storage ingest L6-7, prompt/integration khác; không model/generator/Docker/campaign. **Dừng sau L6-5**, không commit/push.


## L6-2 — DONE kỹ thuật adapter / WAITING_PROVIDER — 08/11/2026

- 20 tools đăng ký, đủ 11 core names; giữ legacy required arguments/payload depth 1, 3 resources và 0 prompts.
- SDK2 final **139 PASS, 0 skip/fail/error**; legacy **100 PASS, 1 skip cũ** (Windows symlink unavailable), thêm scoped pin regression; các gate có overlap, không cộng thành unique tests.
- Legacy/runtime wire **16/16 PASS** (SDK2 modern/legacy và SDK1 cross/native). 4 synthetic core STDIO cases nằm trong SDK2 gate; simulated execution không phải task/model experiment.
- Đã kiểm context/grant/replay, source/provider/output binding, exact UTF-8 diff hash, persisted evidence, required-check ranking, multihop capability, async serialization/deadline/cancellation, full lease cleanup và pinned/no-latest bound legacy query.
- Independent review đã đóng cleanup false-PASS, source drift khi chờ lock, legacy host-factory bypass và event-loop blocking. Giữ RED/failed logs, không thêm skip/xfail để che lỗi.
- Production provider mới vẫn WAITING_PROVIDER (build/path/traversal/verification/ranking/tests); build orchestration thuộc L6-6. Không tự làm thuật toán TV2/TV3 hoặc tuyên bố 11 tool production READY.
- Runbook `docs/mcp_server/tools.md`; checkpoint `docs/checkpoints/2026-11-08-mcp-core-tools.md`; artifact `results/mcp_server/tools/20261108T141511Z-adapters/` chứa commands/logs/JUnit/wire/readiness/preservation/hashes.
- Bảo toàn thay đổi M2 và artifact H1/L6-1/L6-5; không cài package, đổi venv/DB, chạy Docker/model/campaign hoặc commit/push. **Dừng sau L6-2.**


## L6-3 — DONE kỹ thuật resource serving / WAITING_PROVIDER — 09/11/2026

- Graph server đăng ký8 canonical resources +1 alias legacy (4static/5templates); tools20 và prompts0 giữ nguyên. Ba legacy URI/raw JSON/MIME text/plain tiếp tục tương thích.
- SDK2 final **211 PASS,0skip/fail/error**, gồm72 resource cases mới và139 gates hiện có. Legacy **100 PASS +1skip cũ**; groups overlap, không cộng unique tests. Compatibility wire16/16 PASS; resource-positive synthetic wire3 sessions nằm trong SDK2 gate.
- Raw URI router decode ID đúng một lần, strict query k=2/cursor, bounded public JSON, pinned source/snapshot/task/run/config binding, evidence refs/hash, unavailable/error rõ. Audit resource cứng256KiB/200records, cursor chỉ tiến qua record đã trả; default caller read_audit cũ giữ nguyên.
- Đã đóng review findings về metadata/protocol secret redaction và high-host audit-record cap. SQLite temp-copy proof/source immutability, optimized-Python denial, legacy payload hashes, Ruff scoped/pip check và final preservation PASS. Không thêm skip/xfail, không đổi package/venv/DB tracked.
- Schema/component/task/baseline production **WAITING_PROVIDER**. Canonical subgraph/audit cần trusted host binding; synthetic fixture không chứng minh provider/experiment production hoàn thành.
- Runbook `docs/mcp_server/resources.md`; checkpoint `docs/checkpoints/2026-11-09-mcp-resource-serving.md`; artifacts UTC `results/mcp_server/resources/20261108T173125Z-serving/` có commands/log/JUnit/wire/review/readiness/preservation/hashes. Ngày local09/11, không đổi timestamp UTC.
- Bảo toàn dirty changes M2/L6-1/L6-2/L6-5 và sealed history. **Dừng sau L6-3**; không L6-4/L6-6/L6-7, Docker/model/campaign/commit/push.


## L6-4 — DONE kỹ thuật MCP prompt — 09/11/2026

- Graph server có1 prompt repair_with_graph_context,3 required string arguments; hai user messages, đúng7 bước proposal §10.4. Các server khác0 prompt; tools20/resources8 canonical+1alias không đổi.
- Pure deterministic renderer không source/env/gold/tokenizer/provider/tool/model/grant access; frozen lower-only65.536-byte caps, strict JSON/tests/positive ASCII budget, secret redaction và audit counts/templatehash. Không default budget mới hoặc sửa V11/policies.
- SDK2 final **266 PASS,0skip/fail/error**, gồm55 prompt/controller cases mới và211 gates hiện có; legacy **102 PASS +1skip cũ**. Groups overlap, không cộng unique tests. Wire compatibility16/16 PASS;4 graph lanes đều get_prompt/oracle PASS, không chỉ listing.
- Ba dedicated prompt wire sessions và hai raw-protocol cases thuộc SDK2 gate. Unknown/missing/extra/invalid dispatched requests được audit prompt_render và trả lỗi an toàn. SDK malformed params trước dispatch không phải render attempt: SDK1 warning generic +protocol_reject; SDK2 safe generic rejection, không fake prompt event/correlation. Review đã kiểm lại fixes và leading-zero normalization.
- Ruff scoped/pip check/preservation PASS; packages, V11, policies, DB, old dirty files và seals H1/L6-1/L6-2/L6-3/L6-5 giữ nguyên. PROGRESS/contract/status chỉ append; process cleanup inventory không có worker/server sót.
- Runbook docs/mcp_server/prompts.md; checkpoint docs/checkpoints/2026-11-09-mcp-repair-prompt.md; artifact UTC results/mcp_server/prompts/20261108T181049Z-template/ có commands/log/JUnit/template/hash/wire/review/preservation.
- Prompt PASS không chứng minh agent đã làm workflow, không đóng provider dependencies của L6-2/L6-3. Inspector/Claude Code thực thuộc L6-8. **Dừng sau L6-4**, không L6-7/L6-6/L6-8, Docker/model/campaign/commit/push.


## L6-7 — DONE kỹ thuật SQLite/legacy profile; WAITING_SCHEMA_PROVIDER — 09/11/2026

- Storage mới mỗi snapshot một DB/manifest, identity gồm graph version/source/schema/resolver/profile/canonical document. Không rewrite graph_version/node IDs hoặc migrate DB tracked/frozen; opt-in snapshot factory không đổi legacy defaults/launchers.
- Writer kiểm trusted context, exact single-use storage_ingest grant, repo/snapshot locks, source/deadline/cancellation; rows/full-document/identity/READY cùng SQL transaction. Close/round-trip/projection/hash trước atomic directory publication dưới request commit guard. Crash/orphan không là public READY, không tự adopt/xóa dữ liệu cũ.
- Reader explicit manifest/version và trusted profile fingerprints từ host, mode=ro/query_only/read transaction riêng mỗi operation/thread, không initialize/ALTER/latest/demo fallback/immutable=1. Canonical document giữ extensions; query vẫn SQL. Guard kiểm file identity và SQLite sidecars, schema/profile/DB/binding/projection consistency.
- Final SDK2 **328 PASS,0skip/fail/error**,69,48 giây: 52 storage cases (50 unit/process/worker-thread +2 real STDIO snapshot lanes),10 SQLite legacy cases và266 MCP gates đã có. Legacy **102 PASS +1skip cũ**,83,11 giây; groups overlap, không cộng unique total. Không thêm skip/xfail.
- Review 2 findings đã có7 RED regression và GREEN: không cho manifest tự đăng ký trusted profile; đối chiếu mọi SQL fact/scalar ranges/JSON với canonical document. Reviewer kiểm lại không còn finding quan trọng trong phạm vi. Source/deadline/cancel trong transaction, process crash trước/sau staging manifest, cross-process replay và coordinated forgery có evidence synthetic, không giả làm schema/provider production.
- Ruff phần mới/factory PASS; hook SQLite không có lint mới (3 findings cũ được so với HEAD); whitespace phần thay đổi/pip check/preservation PASS. DB/V11/policy/báo cáo Linux/M2 dirty files/seals H1/L6-1/2/3/4/5, index/HEAD/staged và hai package inventories giữ nguyên. Không có process test/server còn sót sau gate.
- Runbook/survey `docs/mcp_server/storage_backends.md`; checkpoint `docs/checkpoints/2026-11-09-mcp-snapshot-storage.md`; artifact UTC `results/mcp_server/storage/20261108T185307Z-snapshots/` có commands/log/JUnit, examples, crash/concurrency/review/preservation/checksums. SQLite3.42.0 chạy thật; Kùzu0.11.3 và Neo4jDriver6.4 chỉ khảo sát chính thức, **OPTIONAL_NOT_SELECTED**, không cài backend/đổi runtime.
- **L6-7 chưa DONE hoàn toàn:** schema Component/Port/layers và provider/SQL projection thật chưa bàn giao, round-trip mới còn WAITING_SCHEMA_PROVIDER. Không dùng synthetic validator/H1 để đóng dependency. Chưa nối build_or_update_graph hay incremental orchestration (L6-6), chưa integration external host (L6-8).
- Không model/Docker/campaign/commit/push; chỉ task L6-7. **Dừng sau L6-7.**


## L6-6 — DONE kỹ thuật build/update legacy; graph mới WAITING_PROVIDER — 09/11/2026

- Trusted controller nối build_or_update_graph với IncrementalGraphBuilder thật và SQLite snapshots L6-7. Một worker subprocess giữ cache extraction RAM theo phiên/repo, cold/warm/reuse rõ; relink vẫn toàn repo, không claim O(Δ+Fanout) hoặc benchmark production.
- Controller thread sở hữu validate/authorization/repo lock/copy/worker/storage/receipt; adapter không giữ OS lock ở thread khác. Build grant single-use trước staging/spawn; worker không authority/grants/DB và không import/execute target. Request-scoped registry/binding, opt-in bootstrap, default/legacy API/payload/inventory20tools/8canonical+alias/1prompt giữ nguyên.
- Source private copy/hash và worker job/instance/document/summary/ACK được kiểm trước publication. Repository metadata normalize về host repo sau proof, không để URI staging đã xóa. Effective profile bind operator profile/config/code; cache pin full identity/manifest/DB/original publication receipt, không latest/graph_version-only. Reuse snapshot cũ khác worker lineage reset worker; receipt ghi baseline thật hoặc cold-empty.
- Derived storage context dùng exact identity grant, cùng parent request scope; parent cancellation/operation deadline được kiểm cả trước/sau source scan và trong commit/publication guard. Timeout/cancel/error kill process tree và bỏ extraction cache; thiếu ACK không publish; native crash/orphan không tự adopt. Error khi source root biến mất vẫn cleanup worker, không che integrity thành PASS.
- Final SDK2 **399 PASS,0skip/fail/error**:45 cases L6-6 mới +354 regression MCP/storage/incremental/SQLite đã có. Legacy **102 PASS +1skip cũ**; các nhóm overlap, không cộng unique totals. Ba real STDIO lanes SDK2modern/legacy và SDK1server thực hiện cold→reuse→warm→read snapshot, nằm trong45 cases mới. Native process/cancellation/crash, optimized Python, config/source/schema/resolver/profile/code invalidation và semantic full-build equivalence có evidence.
- Review read-only đã đóng metadata staging, worker baseline và deadline sau source-scan; có RED→GREEN regressions. Intermediate gate từng phát hiện default expired-context exception bị đổi và lỗi fixture đăng ký lại authority; đã giữ ValueError legacy và sửa helper test, không nới grants/checks hoặc thêm skip/xfail.
- Ruff scoped/pip check/whitespace/preservation PASS. HEAD/branch/index/staged, package inventories, source plans, DB/V11/policies/M2/Linux reports và sealed artifacts trước giữ nguyên; PROGRESS/contract/status chỉ append. Process inventory sau gates không có server/worker còn sót.
- Runbook docs/mcp_server/graph_jobs.md; checkpoint docs/checkpoints/2026-11-09-mcp-graph-jobs.md; artifact results/mcp_server/graph_jobs/20261109T050523Z-incremental/ chứa actual commands/log/JUnit, worker/cache/equivalence/wire/crash/review, snapshot examples và checksums. Fixture source là synthetic, provider/builder/storage thật; không dùng làm bằng chứng dataset/model repair hoặc schema mới.
- **G_arch/G_task/Trace/Component/Port vẫn WAITING_SCHEMA_PROVIDER/WAITING_PROVIDER**. Chưa đóng toàn11 core tools production hoặc L6-8/external-host integration. Không model/Docker/campaign/install/commit/push. **Dừng sau L6-6.**


## L6-8 — DONE kỹ thuật preflight offline; PARTIAL/BLOCKED_DEPENDENCIES — 09/11/2026

- Chỉ preflight được yêu cầu: thêm CLI `scripts/mcp_server/smoke_mcp.py --preflight`, fixed helper `_preflight_worker.py`, consumer tests, ba config templates + metadata và runbook. Không sửa domain/runner/adapter production, cài/download, model/agent, login, Docker, global host settings hoặc commit/push.
- Lượt thật `campaign-02` **exit 2 / PARTIAL**, `preflight_completed=true`, `local_checks=PASS`; đây là hoàn thành công cụ và kiểm tra cục bộ, không phải DONE toàn L6-8. Inventory20 tools gồm11 core,8 canonical resources+1alias,1prompt. Bốn server × hai mode = **8/8 wire PASS**; protocol thực modern2026-07-28 và legacy2025-11-25.
- Real legacy builder/controller/SQLite trên source fixture: hai mode đều **COLD_BUILD → SNAPSHOT_REUSE → WARM_UPDATE → read PASS**, sáu build/reuse calls. Consumer kiểm job/evidence hash, trusted storage profile/identity, manifest/DB/source và resource binding; DB không đổi sau read. Fixture không phải provider schema mới hoặc repair campaign production.
- Final SDK2 **50 PASS**, gồm31 preflight cases; legacy compatibility **40 PASS +1skip cũ**. Các nhóm có overlap, không cộng thành unique total. Scoped Ruff/pip check PASS. Giữ15 trailing-whitespace findings cũ trong báo cáo M2 ngoài phạm vi; phần task mới kiểm riêng. Không thêm skip/xfail.
- Review đã đóng3 findings có RED→GREEN: await lazy SDK fixture initialization trước source fingerprint; consumer yêu cầu successful named calls/denials/resource data/legacy protocol, không chỉ listing/producer PASS; bảo vệ cả8 roots artifact cũ bị Git ignore. Lượt `campaign-01` ERROR và intermediate RED/GREEN logs giữ nguyên để audit, không tính thành nghiệm thu.
- CLI preservation **2.903 file PASS**; baseline task2.894 file được bảo vệ, chỉ ba tài liệu PROGRESS/contract/status được append. HEAD/index/staged/source plans/package inventories/DB/V11/policies/báo cáo Linux/M2 và mọi seal trước không đổi. Process receipt không còn server/worker của preflight.
- Ma trận **20 dòng** có owner/task/handoff/phần TV1 tích hợp/gate: TV1 còn trusted bootstrap/binding, rich-schema storage projection và external integration; TV2 còn SC-1, rich builder/query/path/architecture/task/trace/retrieval/impact; TV3 còn contract evidence/graph verification/ranking/admitted diff-tests/baseline. Legacy code đã có được ghi riêng, không coi là toàn bộ implementation chưa tồn tại.
- Node v22.22.2/npm10.9.7, Claude CLI2.1.193 đã đọc version/help; auth **NOT_CHECKED_OFFLINE**, session **NOT_RUN**. Inspector không tìm thấy tại các vị trí đã kiểm, không kết luận toàn máy. Templates **TEMPLATE_NOT_EXECUTED**; Inspector/Claude/full chain production đều **NOT_RUN**. SDK smoke không thay nghiệm thu external host.
- Artifact `results/mcp_server/preflight/20261109T055933Z-offline/`; báo cáo chính `campaign-02/report.md`, ma trận `campaign-02/dependencies.md`, checkpoint `docs/checkpoints/2026-11-09-mcp-preflight.md`, runbook `docs/mcp_server/runbook.md`. **Dừng sau preflight**, không tự triển khai dependency hoặc thực nghiệm tiếp theo.
