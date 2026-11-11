# T3 — Gold Astropy-13033 bị test tái hiện từ chối nhầm

## Kết luận và trạng thái

**Đã xác định và sửa oracle repro; đối chiếu Docker local đạt kỳ vọng.**
Không phải kết quả chạy lại campaign M3 cũ hoặc nghiệm thu A3 đầy đủ.

| Overlay/test oracle | Source base | Sau gold patch | Ý nghĩa |
|---|---|---|---|
| Repro cũ | FAIL | FAIL | Assertion cấm actual `found 'time'` từ chối cả gold |
| Repro sửa | FAIL | PASS | Vẫn bắt được issue trên base và chấp nhận message đã sửa |

Trong cả bốn phép đo, pytest collect đúng **1 node**, không collection error,
không timeout/truncation. Hai workspace dùng cùng base/image/profile và gold;
khác biệt chủ động là bytes của overlay repro. Không có model call.

## Nguyên nhân

Task dùng TimeSeries với hai cột bắt buộc `time`, `flux`, sau đó xóa `flux`.
Actual còn `time` nên thông báo `found 'time'` hoàn toàn đúng. Lỗi issue nằm ở
vế **expected**: baseline chỉ nêu `time` thay vì danh sách cột bắt buộc có `flux`.

Repro cũ có:

```python
assert "found 'time'" not in message
assert 'flux' in message
```

Gold đã bổ sung danh sách expected, nhưng vẫn đúng khi mô tả actual time.
Do đó assertion đầu từ chối nhầm gold. Ngoài ra, kiểm `flux` ở bất kỳ chỗ nào
trong message không chứng minh nó thuộc expected; fixture đã tái hiện điểm yếu này.

Repro sửa chia message tại ` but found `, yêu cầu vế expected nêu `time` và `flux`,
vế actual nêu `time`. Giữ nguyên exception type, thao tác xóa cột, selectors và
protected paths. Không skip/xfail, không bỏ required check hoặc đổi environment.

## Phương pháp và nguồn dữ liệu

1. Lưu hashes/status/HEAD/index, repro cũ và các file đang thay đổi trước thao tác.
2. Dùng `vgar.evaluation.harness.gold_inputs.select_rows()` với manifest W10 và
   Parquet local đã pin để lấy đúng **một task**. Gold/official-test diff chỉ lưu
   trong `evaluation-only/`, không đưa vào retrieval/context/prompt.
3. Đọc gold và official test bổ sung để phân biệt expected/actual. Official test
   chỉ dùng đối chiếu tài liệu trong bước này, **không được apply hoặc execute**.
4. Viết oracle contract fixture trên Windows: dependency doubles chỉ cung cấp
   các ValueError message cố định cho hàm test thật; không chạy Astropy ngoài Docker.
   RED4 fail/2 pass → sửa oracle → GREEN6 pass.
5. Dùng `load_experiment → plan_task → admit_task → prepare_admitted_workspace`
   để tạo hai lease riêng. Mỗi lease: collect/run baseline, strict apply gold
   trên source riêng bằng API hiện có, collect/run post, kiểm inventory rồi cleanup.
6. Chạy test bằng `DockerExecutor` và reporter hiện có. Không thêm native target
   fallback, không disable image pytest plugins hoặc sửa Docker settings.
7. Đọc lại JSON/JUnit, command/runtime/source attestation, report size/SHA256,
   cleanup và snapshot-transport receipts; copy/hashing lại evidence độc lập.

## Pins và môi trường thật

| Nội dung | Giá trị |
|---|---|
| Task | `astropy__astropy-13033` |
| Base commit | `298ccb478e6bf092953bca67a3d29dc6c35f6752` |
| Dataset revision | `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` |
| Parquet SHA256 | `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd` |
| Gold SHA256 | `7de34e6ed106dd91f81473f3646ed1340692a28c437324bf78adaf093d2c0c8d` |
| Docker image | `swebench/sweb.eval.x86_64.astropy_1776_astropy-13033@sha256:22f4f193fbf69d61c59e285494be18041934f8b528190dfe8c6c0d8051d8d6de` |
| Python / pytest trong image | `3.9.20` / `7.4.0` |
| Selector | `tests/vgar_w9_repro_13033.py` |
| Gold thay source | Chỉ `astropy/timeseries/core.py` |
| Command / global timeout | Giữ `120 / 1800` giây; không đổi timeout generation `900` |

## Kết quả và bằng chứng

Artifact mới:

```text
D:\Project\CAPSTONES\VGAR\results\m2\w1112\t3\20261107T065504Z\
```

- Docker attempt2: exit0, launcher wall **116,953s**. Mode repro cũ **42,726s**,
  mode repro sửa **57,285s**; launcher gồm cả thời gian gate/orchestration khác.
- **8 Docker operations**, **16 JSON/JUnit report artifacts** được consumer audit
  xác minh. Baseline/post collection đều PASS; execution có ba FAIL và một PASS
  đúng ma trận trên. Không infrastructure/collection failure bị đổi thành patch FAIL.
- Source tree/blob trước–sau và cleanup của hai lease PASS; không owned container
  hoặc private source còn lại. Giữ reports mà consumer cần.
- T6:8 snapshot archives đã copy rồi REMOVED, retained0; tổng logical archive
  bytes **310.231.040**. Đây không phải lượng physical disk được thu hồi.
- **265 raw files /14.283.000 bytes** được copy và đối chiếu SHA256 nguồn/đích.
- Regression Windows liên quan: **68 PASS,1 SKIP /84,49s**. Skip có sẵn là
  `test_control_dir_is_usable_by_capless_container_root` — `POSIX modes only`;
  không tự thêm skip/deselect. Sáu oracle tests đã nằm trong số68 PASS.
- Ruff scoped `--no-cache` và whitespace PASS. Không chạy lại suite T1 dài vì
  không đổi code checker/verifier/runner; bảo toàn thay đổi T1 và các task trước.
- Repo Windows giữ raw bytes CRLF; loader task inputs đọc text UTF-8 và chuẩn
  hóa newline về LF trước khi tạo overlay. Vì vậy raw-file SHA và overlay-text
  SHA khác nhau; hai giá trị được lưu riêng trong `overlay_bindings.json`.
  Không so trực tiếp hai loại hash hoặc dùng raw hash thay canonical admission hash.

Log/report chính:

- `docker-launch-attempt-2.json`, `docker-attempt-2.stdout.log`;
- `docker-summary-attempt-2.json`, `consumer_audit.json`, `raw_inventory.json`;
- `raw-docker/attempt-2/{original-overlay,corrected-overlay}/baseline.json`;
- `raw-docker/attempt-2/{original-overlay,corrected-overlay}/post.json`;
- thư mục `docker/<operation_id>/`: `command.json`, `target_result.json`,
  `nodeids.json`, `junit.xml`, cleanup/snapshot-transport receipts;
- `oracle-red.*`, `oracle-green.*`, `regression.*`, `commands.json`, review,
  source fingerprints, preservation và artifact checksums.

Linux raw vẫn tại `/home/vgar/w10-a3-local/t3/20261107T065504Z/`.
Attempt1 dừng ở RAM gate trước workspace/target; không phải một test Astropy FAIL.
Lỗi finally của helper one-off được giữ và sửa riêng; không sửa production do lỗi đó.

Docker Desktop ban đầu đang tắt, được khởi động bình thường. Đĩa C ban đầu dưới
10GiB, lần đo sau đã đủ. Bốn lượt T3 reclaim RAM page cache tại idle theo quyền
user đã cấp, tổng agent từ13 lên17, giữ journals/quota cũ bất biến; không xóa disk
cache/images/data. Snapshot cuối host RAM≈3,45GiB: **không dùng để launch chặng4**,
phải kiểm tài nguyên mới ở chặng được giao sau.

## Thay đổi và bàn giao

- Sửa `configs/m3/w10_dev/tasks/astropy__astropy-13033.repro.py`: oracle issue.
- Thêm `tests/m2/w1112/test_astropy13033_repro.py`: fixture regression.
- Thêm tài liệu này và checkpoint T3; cập nhật trạng thái M2/PROGRESS.
- Không sửa runner, plugin pytest, verifier, policy, task JSON, profile, source
  checkout, graph/bundle hoặc các input/code copies Linux đã seal trước đó.

Repro thuộc task input dùng chung của M3; cần review bàn giao M3, không tự tạo
sign-off/merge hoặc sửa board. Trước batch, chặng4 phải đưa **cả T1 và repro T3**
vào code/input root mới có hashes, tạo admission/overlay binding và experiment
fingerprint đúng bytes mới, kiểm fairness A2/A3 cùng inputs rồi fresh preflight.
Không âm thầm ghi đè code/input root lịch sử hoặc dùng preflight/experiment ID cũ.
Base/image không đổi không tự đòi tải lại25 task; chỉ tái tạo phần binding thiếu.

Đổi oracle là thêm một lý do không coi A3 mới và A2 W10 lịch sử là phép so sánh
paired cùng protocol. Không tự mở campaign A2 mới trong T3.

**Giới hạn:** mỗi scope chỉ có1 repro,0 passing regression cases được chọn.
Chưa chạy official F2P/P2P, static/API/structural trên gold hoặc full A3 verdict.
Chưa kiểm raw record M3 cũ; kết luận là đã tái hiện nguyên nhân tương ứng trên
local pinned base/image và sửa oracle, không sửa kết quả lịch sử hoặc FRR.

T3 local hoàn tất rồi dừng. Chặng4 và campaign tiếp theo cần lệnh riêng.

Review kỹ thuật độc lập đã đọc raw evidence, xác minh đủ265 file/16 reports và
delta snapshot đúng phạm vi; không có finding correctness/integrity chặn. Đây
không thay thế review khác vai trò hoặc quyết định protocol/freeze của nhóm.
