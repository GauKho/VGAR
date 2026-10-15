# Real acceptance V3/V4 — terminal FAIL, chưa đạt 3/3

Campaign chạy từ 21:36:10 đến 21:41:56 ngày 14/10/2026, Asia/Saigon (JSON dùng UTC).
Controller hoàn tất và dừng đúng giới hạn **hai failures**, dùng **4/6 attempts**.
Không chạy C, không tạo V5, không đổi model/guards hoặc sửa diff do model sinh.
`final_version=null`: chưa có phiên bản prompt cuối đạt ba cases PASS.

| Attempt | Prompt | Task | Status / lý do | Input/output tokens | Pipeline duration | Original unchanged |
|---|---|---|---|---|---|---|
| 01 | V3 | single_file_login | PASS | 1026/38 | 72.938s | true |
| 02 | V3 | multi_file_invoice | FAIL TEST_FAILED; chỉ sửa pricing.py | 1387/55 | 79.219s | true |
| 03 | V4 | single_file_login | PASS; chạy lại từ A, không gộp PASS của V3 | 1233/38 | 62.922s | true |
| 04 | V4 | multi_file_invoice | FAIL PATCH_APPLY_FAILED; invoice hunk bắt đầu dòng 1 thay vì 4 | 1594/122 | 127.813s | true |

## Vì sao B thất bại?

V3: diff parse/apply được nhưng chỉ sửa `pricing.py`. Test discount PASS,
test invoice tax vẫn FAIL. Đây là lỗi bỏ sót thay đổi semantic đa tệp,
không phải lỗi format. Xem outcomes và stdout/stderr trong canonical record.

V4: `invoice.py` có import ở dòng 1, hai dòng trắng 2–3; function bắt đầu dòng 4.
Prompt đã ghi `Source_start: 4:0` và tổng file có sáu dòng, nhưng model vẫn sinh
`@@ -1,3 +1,3 @@`. Counts bằng 3 hợp lệ, song dòng bắt đầu 1 không khớp source.
Parser PASS; strict all-file preflight từ chối trước khi apply. Không có partial
change ở pricing; selection và post verification **NOT_RUN**. Host không sửa
hunk/counts để biến thất bại thành PASS.

## Điều gì đã được và chưa được chứng minh?

Chỉ **A** là real task đã PASS. Hai PASS của cùng A dưới hai versions không
thành hai tasks khác nhau, cũng không đủ gate ba tasks cùng version.
**C NOT_RUN** vì failure limit, không kết luận C sẽ PASS hay FAIL.
Real acceptance chưa đạt; đây không phải resolved rate của benchmark.

## Evidence và tài nguyên

Đường dẫn từng attempt có trong `summary.json` và `campaign.json`. Mỗi run lưu
full prompt/raw output, candidate/transport/applied diff nếu stage tương ứng đạt,
canonical commands/stdout/stderr/exit codes, timings/tokens/device metadata và
public EvidenceBundle. `summary.json` là projection, không thay canonical.
Failures V1/V2 cũ được giữ nguyên ngoài campaign.

Model cố định `Qwen/Qwen3-4B-Instruct-2507` tại revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, greedy, FP16, auto CUDA;
Native chỉ cho ba fixtures đã duyệt. Không timeout/OOM trong bốn runs này.
Lỗi quan sát là model bỏ sót file và ghi sai hunk coordinate; chưa có evidence
để quy lỗi hai runs này cho thiếu GPU. Tổng pipeline duration: **342.892 giây**;
wall time campaign: **345.559 giây**. Không phát sinh API bill; điện/local compute
vẫn có chi phí, không gọi là miễn phí.

## Điểm dừng và kiểm thử package

Không reset manifest để sử dụng hai slots còn lại vượt failure cap. Phương pháp
mới cần user/owner duyệt; không tự đổi backend, training hoặc nới parser.
Full self-test cuối sau campaign: **126 passed in 87.16s**, exit 0, tại
`../../tests/20261014T144408789514Z-d6a80718ea70/run_record.json`.
Tests package PASS không có nghĩa real campaign PASS. Teammate reproduction và
M3 integration chưa được nghiệm thu thay cho các thành viên phụ trách.
