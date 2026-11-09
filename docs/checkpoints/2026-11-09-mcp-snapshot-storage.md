# Checkpoint L6-7 — SQLite snapshots — 09/11/2026

## Phạm vi và baseline

Chỉ thực hiện L6-7 theo plan đã được duyệt: SQLite production, một DB mỗi snapshot, legacy compatibility và optional-backend survey. Không L6-6/L6-8, model/Docker/campaign/install/commit/push.

Branch `m2/w12-a3-verifier-d15-20261105`, HEAD `3f77fcf6ba68d7cfc6356dfe9757f6f53eed691b`. Artifact UTC: `results/mcp_server/storage/20261108T185307Z-snapshots/`. Baseline giữ status/staged/unstaged và 2.605 hashes gồm dirty tracked/untracked, `.git/index`, sealed MCP artifacts trước L6-7. Ngày local 09/11/2026.

## Điểm khôi phục — IN_PROGRESS

- Đã thêm `storage_capabilities.py`: identity/host profile port, writer có context/grant/locks/transaction/staging/publication và strict reader per-operation/thread.
- Legacy `sqlite_store.py` chỉ thêm hook `_before_ready` mặc định no-op; `factory.py` thêm opt-in snapshot mode, không đổi default/launchers.
- 38 tests đầu PASS, regression lượt đầu 314 SDK2 PASS + legacy102 PASS/1skip cũ. Đây **chưa phải final gate** sau review.
- Reviewer tái hiện 2 lỗi: reader tự infer trusted profile từ manifest; canonical JSON chưa chứng minh normalized SQL rows. Đã viết 7 RED regression, sửa thành explicit trusted profiles + projection scan đầy đủ cả scalar ranges. GREEN45 PASS, review độc lập xác nhận hai findings đóng.
- Bổ sung source/deadline/cancel trong transaction, coordinated manifest/DB binding forgery và hard crash sau manifest fsync. Unit50 PASS. Hai real SDK2 STDIO lanes (modern/legacy) snapshot factory PASS; tổng storage cases hiện52. Final release/regression đang chạy; kiểm logs/XML trước khi chạy lại hoặc tuyên bố DONE.
- Factory snapshot mode cần manifest/version và **operator-pinned** resolver/profile hashes; không lấy hashes từ manifest làm đăng ký trusted. Storage write context.snapshot_hash=identity.snapshot_id, GraphService vẫn trả graph_version nguyên gốc. Đây là ruling về namespace, không tự nối build/provider của L6-6.
- Source plans không bị sửa. `docs/mcp_server/storage_backends.md` có runbook, survey primary sources, SQLite3.42.0 thực chạy, Kùzu0.11.3/Neo4jDriver6.4 chỉ khảo sát OPTIONAL_NOT_SELECTED.

Final gate/artifact preservation sẽ được append phía dưới. Chưa đóng schema mới: **WAITING_SCHEMA_PROVIDER**.


## Kết quả cuối


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
