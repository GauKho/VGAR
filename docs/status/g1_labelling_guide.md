# Hướng dẫn gán nhãn G1: lời gọi và tên dùng (16/11/2026)

Mục đích: đo **call edge P/R** và **symbol resolution P/R** của graph (proposal dòng 1342–1343; plan 2 tuần, tuần 2 ngày 2, G1). Spec: `docs/superpowers/specs/2026-11-16-g1-labelled-edges-design.md`.

## Ai gán nhãn

- **Claude** gán cả 300 mục (150 lời gọi trong `calls.csv`, 150 tên dùng trong `name_uses.csv`), chỉ nhìn code và danh sách ứng viên, trước khi graph được build. Báo cáo luôn gọi đây là "nhãn do Claude gán", không phải "gán nhãn tay".
- **Lượt gán thứ hai cho 30 mục** (15 + 15) trong `agreement_user.csv`: theo kế hoạch ban đầu là người dùng gán mù, nhưng người dùng nhờ Claude làm (16/11), nên đây là **Claude gán lại lần hai từ code, không mở nhãn lần đầu**. Tỉ lệ khớp và Cohen's kappa vì thế chỉ đo **độ nhất quán của Claude với chính mình**, không phải độ khớp với người; không được ghi là "khớp với người". Mục nào lệch thì người dùng quyết, nên các mục lệch vẫn có người kiểm.

## Cách đọc một mục

Mở `items.md`, tìm mã mục (ví dụ `C007`). Mỗi mục có 7 dòng code (dòng của mục đánh dấu `>>`) và danh sách **mọi định nghĩa trong repo có cùng tên**, sắp theo tên đầy đủ. Danh sách lấy từ bảng định nghĩa của repo, không lấy từ graph, nên không lộ graph đã nối gì.

## Cú pháp cột `label`

| Ghi | Nghĩa |
|---|---|
| `2` hoặc `1;3` | số thứ tự ứng viên đúng; nhiều số khi lời gọi đa hình |
| `external` | đích nằm ở thư viện ngoài (numpy, pandas, matplotlib khi repo khác, astroid…) |
| `builtin` | hàm/kiểu dựng sẵn của Python hoặc thư viện chuẩn (`dict.update`, `str.format`, `os.path`) |
| `unknown` | không xác định được từ code (callable truyền vào làm tham số, `getattr` với chuỗi, bí danh module) |
| `other:<tên đầy đủ>` | đích có trong repo nhưng không nằm trong danh sách (ví dụ class mà `self.func` trỏ tới) |

Không dùng dấu phẩy; khoảng trắng và chữ hoa/thường được bỏ qua. Cột `note` ghi tự do.

## Luật cho ca khó

- **Đa hình:** ghi mọi override trong repo mà caller này đến được. Nếu đọc code không quyết được, ghi method khai báo và viết `polymorphic` vào `note`. Ví dụ `self.reporter.display_reports(sect)` → các reporter thật trong `pylint/reporters`.
- **Gọi class `C(...)`:** ghi class (như graph), không ghi `__init__`.
- **`super().m()`:** method `m` ở lớp cha gần nhất có định nghĩa `m`. Riêng mục mà chính lời gọi là `super()` thì ghi `builtin`.
- **Decorator:** ghi hàm được trang trí.
- **Thuộc tính gán ở nhiều chỗ** (`self.x` gán trong `__init__` và `reset`): ghi ứng viên thuộc tính (field), không ghi dòng gán.
- **Biến toàn cục chứa class/hàm** (`Eq = Equality`, `request_class = Request`): ghi class/hàm mà nó trỏ tới bằng `other:`. Biến toàn cục chứa đối tượng sinh động (proxy lazy, registry) thì ghi chính biến đó.
- **Tham số lambda, biến cục bộ** mà bộ liệt kê lỡ đưa vào: `unknown`, `note` = `local`.

## Khóa nhãn và chốt chênh lệch

```bash
# 1. Claude điền xong calls.csv, name_uses.csv
python scripts/g1_label_kit.py --out ~/rt1/g1 --lock          # ghi SHA-256 vào manifest.json
# 2. Người dùng điền agreement_user.csv
python scripts/g1_evaluate.py --kit ~/rt1/g1 --out ~/rt1/g1/report \
    --tsg-executable ~/tsg/bin/tree-sitter-graph --tsg-tree-sitter-dir ~/tsg/config --enable-jarvis
# Nếu có mục lệch: bộ chấm ghi ~/rt1/g1/disagreements.csv và dừng (mã 3).
# 3. Người dùng điền cột final_label, lưu thành ~/rt1/g1/settlement.csv (item_id, final_label), chạy lại bước 2.
```

Bộ chấm từ chối (mã 2) nếu `agreement_user.csv` mới điền một phần hoặc có nhãn sai cú pháp. Lần đầu dùng, hash của file này được ghi vào `manifest.json` (`agreement_lock`); sửa file sau đó (ví dụ sau khi xem `disagreements.csv`) bị từ chối. `settlement.csv` chỉ được chứa các mục có trong `disagreements.csv`.

Sửa `calls.csv`/`name_uses.csv` sau khi khóa làm bộ chấm từ chối chạy (mã 2). Việc chốt chênh lệch không sửa các file đã khóa: nhãn cuối của các mục lệch lấy từ `settlement.csv`, và báo cáo ghi hash của file này cùng danh sách mục bị đổi.

## Lượt người (17/11/2026)

`agreement_user.csv` là lượt Claude thứ hai và đã khóa. Lượt người dùng **file riêng** `agreement_human.csv` (cùng 30 mục, cột `label` để trống; nội dung từng mục trong `agreement_human_items.md`). Người gán không mở `calls.csv`, `name_uses.csv`, `agreement_user.csv` trước khi gán xong.

```bash
python scripts/g1_evaluate.py --kit ~/rt1/g1 --out ~/rt1/g1/report_human --agreement-sheet agreement_human.csv \
    --tsg-executable ~/tsg/bin/tree-sitter-graph --tsg-tree-sitter-dir ~/tsg/config --enable-jarvis
# Mục lệch: bộ chấm ghi ~/rt1/g1/disagreements_agreement_human.csv và dừng (mã 3).
# Người dùng điền final_label, lưu thành ~/rt1/g1/settlement_agreement_human.csv, chạy lại.
```

Khóa của file này nằm ở `manifest.json` → `agreement_locks["agreement_human.csv"]`, tách khỏi `agreement_lock` của lượt Claude; hai lượt có file chốt riêng. Báo cáo ghi `agreement_source: human` và gọi số này là "độ khớp với người".
