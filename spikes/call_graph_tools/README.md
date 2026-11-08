# Spike L2-1: PyCG và JARVIS (08/11/2026)

**Kết luận: đã thử, chưa tích hợp.** Trên repo test case, cả hai bổ sung được cho SCIP. Nhưng không công cụ nào xử lý xong xarray-4629 trong giới hạn thời gian,
và cả hai cần vá mới chạy được trên Windows.

Task: L2-1 của `docs/status/plan_2_weeks_mcp_server_2026-11-07.md`. Proposal ghi analyzer này là "optional" (dòng 1455) và yêu cầu hệ thống vẫn chạy khi không có
backend nặng (dòng 1462).

## Chạy trên xarray-4629

| Công cụ | Cấu hình | Giới hạn | Kết quả |
|---|---|---|---|
| PyCG | 149 file, vòng lặp mặc định | 900 s | Hết giờ |
| PyCG | 149 file, `--max-iter 2` | 900 s | Hết giờ |
| PyCG | 78 file không phải test, vòng lặp mặc định | 900 s | Hết giờ |
| PyCG (đã vá) | 78 file không phải test, `--max-iter 1` | 580 s | Hết giờ |
| JARVIS (đã vá) | 149 file, chế độ mặc định | 900 s | Hết giờ |

Để so sánh, SCIP xử lý cùng 149 file trong khoảng 90 giây. Chưa điều tra nguyên nhân chậm. Hai lần PyCG ở giữa chạy song song với nhau.

## Chạy trên repo test case

`tests/fixtures/vgar-callgraph-cases`: 62 lời gọi có đáp án (51 đích nội bộ với 59 đích đúng, 8 ngoài repo, 3 không thể biết tĩnh), đã đối chiếu 62/62 bằng cách chạy thật.

| Chế độ | Precision | Recall | Lời gọi ngoài repo nhận nhầm |
|---|---|---|---|
| `static`, chỉ `CALLS` | 1,000 | 0,237 | 0 |
| `static` + `MAY_CALL` | 0,597 | 0,729 | 3 |
| `scip`, chỉ `CALLS` | 1,000 | 0,559 | 0 |
| `scip` + `MAY_CALL` | 0,768 | 0,729 | 0 |
| PyCG riêng | 0,848 | 0,661 | 1 |
| JARVIS riêng | 0,812 | 0,661 | 1 |
| SCIP, rồi PyCG | 0,955 | 0,712 | 1 |
| SCIP, rồi JARVIS | 0,953 | 0,695 | 1 |

PyCG và JARVIS trả về quan hệ hàm gọi hàm, không có vị trí lời gọi. Cột trên gắn kết quả vào `CallSite` bằng tên cuối của lời gọi; cách gắn này do spike viết. Hai dòng SCIP
ghép với công cụ là mô phỏng trong `score.py`, không phải code trong builder.

Hai hạn chế rõ nhất của cách gắn:
- Nhóm 3 (cùng tên trong một hàm): cả hai sai 6 lần, vì không biết dòng nào gọi đích nào.
- Nhóm 4 (callback): tìm được 7/8 ở mức hàm nhưng gắn vào lời gọi được 0/8.

Repo test case được thiết kế để làm lộ điểm yếu, nên các con số không đại diện cho code thực tế.

## Trở ngại khi cài đặt

| Công cụ | Vấn đề |
|---|---|
| PyCG 0.0.8 từ PyPI | Cài vào thư mục `PyCG` nhưng code `import pycg`, nên không chạy được ngay |
| PyCG, JARVIS | Cắt đường dẫn theo `/`, nên trên Windows tên module bị tách đôi và import tương đối hỏng |
| PyCG | Crash khi repo khác ổ đĩa với Python (`path is on mount 'C:', start on mount 'D:'`) |
| JARVIS | README yêu cầu Python 3.8; trên 3.11 crash vì thiếu `import importlib.abc`. Không có gói PyPI; mã nguồn lấy từ `github.com/pythonJaRvis/pythonJaRvis.github.io` |

Các bản vá chỉ áp dụng trên bản sao tạm, gồm: đổi tên thư mục gói PyCG; thay `\` thành `/` trước khi đổi đường dẫn thành tên module và trước khi lấy `mod_dir`; thêm `import importlib.abc` cho JARVIS.

## Tái tạo

```bash
# Chép repo test case sang cùng ổ với Python, vào <cases>/src_repo và <cases>/flat_repo.
# Build graph: <cases>/out/<repo>-static.json và <repo>-scip.json bằng scripts/build_graph.py.
# Chạy công cụ: <cases>/out/<repo>-pycg.json hoặc <repo>-jarvis.json; kết quả đã lưu trong results/.
python -I spikes/call_graph_tools/score.py <cases> pycg
python -I spikes/call_graph_tools/score.py <cases> jarvis
```

`analyze.py` so sánh kết quả công cụ với một graph JSON ở mức hàm và mức `CallSite`.
