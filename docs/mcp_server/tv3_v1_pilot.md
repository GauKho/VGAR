# TV3 · V1 pilot trên hai fixture

Pilot chạy mười diff đã gán nhãn cho `single_file_login` và `multi_file_invoice`. Hai cách đầu dùng cùng kết quả EV-3 của mỗi diff. Cách thứ ba chạy thêm ba ví dụ contract cho task login (`bob`, `charlie`, chuỗi rỗng). Cả ba cách ghim cùng snapshot, binding, diff hash và hash file ứng viên trong từng task. Pilot cũng đối chiếu verdict cuối với điều kiện đủ tư cách của EV-1.

| Patch | Nhãn | Chỉ test | Graph + test | Graph + test + contract | Kết quả quyết định |
|---|---|---|---|---|---|
| Sửa kiểm tra tên chỉ chứa khoảng trắng | GOOD | Chấp nhận | Chấp nhận | Chấp nhận | |
| Sửa test mục tiêu và làm hỏng test tên hợp lệ | BAD | Từ chối | Từ chối | Từ chối | Test hồi quy fail |
| Đổi tên tham số công khai `value` thành `text` | BAD | Chấp nhận | Từ chối | Từ chối | `API_SIGNATURE_INCOMPATIBLE` |
| Thêm import `pathlib` bị policy fixture cấm | BAD | Chấp nhận | Từ chối | Từ chối | `FORBIDDEN_IMPORT` |
| Thêm keyword parameter tùy chọn vào `login` và sửa bug | GOOD | Chấp nhận | Chấp nhận | Chấp nhận | |
| Chỉ chấp nhận chính xác tên `alice` | BAD | Chấp nhận | Chấp nhận | Từ chối | Contract thất bại với `bob` và `charlie` |
| Sửa phần trăm discount và tax, giữ import baseline | GOOD | Chấp nhận | Chấp nhận | Chấp nhận | Vi phạm import đã có được giữ làm baseline |
| Chỉ sửa discount, còn lỗi tax | BAD | Từ chối | Từ chối | Từ chối | Test tax vẫn fail |
| Sửa discount và tax, thêm import cấp module tạo vòng `pricing → invoice → pricing` | BAD | Chấp nhận | Từ chối | Từ chối | `NEW_IMPORT_CYCLE` |
| Cùng vòng phụ thuộc, import nằm trong hàm `discounted_price` | BAD | Chấp nhận | Từ chối | Từ chối | `NEW_SOURCE_IMPORT_CYCLE`, kèm chứng cứ dòng source |

| Cách kiểm | FAR, patch BAD được chấp nhận | FRR, patch GOOD bị từ chối | ERROR hoặc NOT_RUN |
|---|---:|---:|---:|
| Chỉ test | 5/7 | 0/3 | 0 |
| Graph + test | 1/7 | 0/3 | 0 |
| Graph + test + contract | 0/7 | 0/3 | 0 |

Mẫu gồm bảy BAD và ba GOOD trên hai task fixture. Nhãn dựa trên contract hoặc chủ đích thay đổi của từng ca. Các ví dụ login được bổ sung sau khi quan sát lỗi overfit trong pilot. Chúng đo khả năng bắt lại lỗi đã biết. Đánh giá độc lập trên tập dev và đối chiếu đầy đủ các baseline của kế hoạch vẫn còn mở.

## Chạy lại

Dùng môi trường MCP SDK2 của TV1 có pytest, chạy từ gốc repo.

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $PWD 'src'
$runId = [guid]::NewGuid().ToString('N').Substring(0, 8)
$pilotRoot = Join-Path ([IO.Path]::GetTempPath()) "vgar-v1-$runId"
python -B -m pytest -q -p no:cacheprovider tests/mcp_server/test_tv3_v1_pilot.py `
  --basetemp $pilotRoot --junitxml "$pilotRoot.xml"
```

Kết quả dự kiến là một test pass. `v1-pilot*/tv3-v1-pilot.json` dưới `$pilotRoot` ghi nhãn, trạng thái, lý do, SHA-256 của sidecar và ma trận đếm của ba cách kiểm. Mục `fixtures` giữ binding và `evidence_directory` cho từng task. Các sidecar EV-1, EV-2 và EV-3 nằm trong thư mục output tương ứng.
